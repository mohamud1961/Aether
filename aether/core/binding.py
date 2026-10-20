"""What a finding about the delivered state is bound to: a manifest of the working directory.

Every entry under the working directory is listed with its type and permission bits, symbolic links with their
target, and regular files with a streamed sha256 of their contents (no size limit). Directories pruned from the
listing (receipt.SKIP) and mount points under the working directory are not bound; they are reported by path as
``unbound``, never dropped silently. Anything outside the working directory is not bound either (stated in the
verification row).

Any failure to list, stat, read a link or hash raises ``BindingUnavailable``: an empty or partial manifest is never
presented as a fingerprint of the delivered tree (Codex re-review of e23ae2ca3: ``; true`` and suppressed errors
turned a missing sha256sum or working directory into an empty, "unchanged" fingerprint, and a 21 MiB deliverable
outside the size filter was repaired in the clone and certified).

A name or link target containing a newline (or a link target containing "|") would let a line be forged, so the
script refuses it and the parser refuses any path listed twice: nothing is bound then.

Uses POSIX sh, find, sha256sum, readlink and GNU/busybox ``stat -c`` (BSD ``stat -f`` where ``-c`` is missing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import shlex
from typing import Any

from . import receipt
from .env import exit_code

TIMEOUT_S = 300
DIGEST = re.compile(
    r"[0-9a-f]{64}  \./"
)  # sha256sum's line for a plain name (an escaped name starts with "\\")


# stat's type names (GNU/busybox %F, BSD %HT) -> what a complete record holds besides type and mode.
KINDS = {
    "regular file": "file",
    "regular empty file": "file",
    "Regular File": "file",
    "symbolic link": "link",
    "Symbolic Link": "link",
    **dict.fromkeys(
        (
            "directory",
            "Directory",
            "fifo",
            "FIFO",
            "socket",
            "Socket",
            "character special file",
            "Character Device",
            "block special file",
            "Block Device",
        ),
        "other",
    ),
}


class BindingUnavailable(OSError):
    """The delivered tree could not be fingerprinted; nothing about it can be bound."""


@dataclass
class Manifest:
    entries: dict[str, str] = field(
        default_factory=dict
    )  # path -> "type|mode[|link][|sha256]"
    unbound: list[str] = field(
        default_factory=list
    )  # pruned directories and mount points


def _script(workdir: str) -> str:
    w = shlex.quote(workdir)
    prune = " -o ".join(f"-name {shlex.quote(n)}" for n in receipt.SKIP)
    walk = f"find . -xdev \\( {prune} \\) -prune"
    return f"""cd -- {w} || {{ echo "working directory unavailable: {workdir}" >&2; exit 3; }}
command -v sha256sum >/dev/null 2>&1 || {{ echo "sha256sum unavailable" >&2; exit 4; }}
nl=$(printf '\\nx'); nl=${{nl%x}}
if [ -n "$({walk} -o -name "*$nl*" -print 2>/dev/null | head -n 1)" ]; then
  echo "a path contains a newline; the manifest cannot be read unambiguously" >&2; exit 9
fi
if stat -c %a . >/dev/null 2>&1; then S='-c'; F='M|%F|%a|%n'; else S='-f'; F='M|%HT|%Lp|%N'; fi
{walk} -exec printf 'U|%s\\n' {{}} + || exit 5
{walk} -o -exec stat "$S" "$F" {{}} + || exit 6
{walk} -o -type l -exec sh -c 'for p; do t=$(readlink "$p") || exit 1; case "$t" in *"|"*|*"$0"*) exit 1;; esac
  printf "L|%s|%s\\n" "$t" "$p"; done' "$nl" {{}} + || {{ echo "a link could not be read, or its target has | or a newline" >&2; exit 7; }}
{walk} -o -type f -exec sha256sum {{}} + || exit 8
if [ -r /proc/mounts ]; then
  here=$(pwd -P)
  while read -r _ mnt _; do case "$mnt" in "$here"/*) echo "U|.${{mnt#"$here"}}";; esac; done < /proc/mounts
fi
echo END"""


def parse(text: str) -> Manifest:
    # Lines are split exactly where the shell ends them, on "\n" only: str.splitlines also breaks on "\r", "\x1c"-"\x1e",
    # "\x85", "\u2028" and more, which a file name may hold, so a name could otherwise split into forged lines.
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines or lines[-1] != "END":
        raise BindingUnavailable("the manifest listing was cut short")
    meta: dict[str, str] = {}
    links: dict[str, str] = {}
    sums: dict[str, str] = {}
    unbound: list[str] = []

    def put(table: dict[str, str], path: str, value: str) -> None:
        # Paths cannot repeat in a real listing; a repeat means injected lines (a name holding a newline that got
        # past the script's guard), so nothing is bound.
        if path in table:
            raise BindingUnavailable(
                f"a path appears twice in the manifest: {path[:200]}"
            )
        table[path] = value

    for line in lines[:-1]:
        if line.startswith("U|"):
            unbound.append(line[2:])
        elif line.startswith("M|"):
            kind, mode, path = line[2:].split("|", 2)
            put(meta, path, f"{kind}|{mode}")
        elif line.startswith("L|"):
            target, path = line[2:].split(
                "|", 1
            )  # the script refuses a target containing "|"
            put(links, path, target)
        elif DIGEST.match(line):
            put(sums, line[66:], line[:64])
        else:
            raise BindingUnavailable(f"unexpected manifest line: {line[:200]}")
    # Every record must be complete for its type: a regular file without its digest (or a link without its
    # target) would compare equal whatever its contents, so a missing line makes the binding unavailable.
    if "." not in meta:
        raise BindingUnavailable(
            "the working directory itself is missing from the manifest"
        )
    orphans = [p for p in [*sums, *links] if p not in meta]
    if orphans:
        raise BindingUnavailable(f"records without metadata: {orphans[:5]}")
    for path, kind in meta.items():
        family = KINDS.get(kind.split("|", 1)[0])
        if family is None:
            raise BindingUnavailable(
                f"unrecognised file type: {kind[:100]} {path[:200]}"
            )
        if (family == "file") != (path in sums) or (family == "link") != (
            path in links
        ):
            raise BindingUnavailable(f"incomplete record for {family} {path[:200]}")
    entries = {}
    for path, kind in meta.items():
        parts = [kind]
        if path in links:
            parts.append("->" + links[path])
        if path in sums:
            parts.append(sums[path])
        entries[path] = "|".join(parts)
    return Manifest(entries, sorted(set(unbound)))


async def manifest(env: Any, workdir: str, timeout_s: float = TIMEOUT_S) -> Manifest:
    result = await env.exec(
        command=_script(workdir), cwd=None, env=None, timeout_sec=max(1, int(timeout_s))
    )
    code = exit_code(result)
    if code != 0:
        err = str(getattr(result, "stderr", "") or "").strip()[:300]
        raise BindingUnavailable(f"fingerprint failed (exit {code}): {err}")
    return parse(str(getattr(result, "stdout", "") or ""))


def changes(before: Manifest, after: Manifest) -> dict[str, list[str]]:
    """Bound entries modified (contents, type, permission bits or link target), deleted or created."""
    b, a = before.entries, after.entries
    return {
        "modified": sorted(p for p in b if p in a and a[p] != b[p]),
        "deleted": sorted(p for p in b if p not in a),
        "created": sorted(p for p in a if p not in b),
    }

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

Uses POSIX sh, find, sha256sum, readlink and GNU/busybox ``stat -c`` (BSD ``stat -f`` where ``-c`` is missing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import shlex
from typing import Any

from . import receipt
from .env import exit_code

TIMEOUT_S = 300


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
if stat -c %a . >/dev/null 2>&1; then S='-c'; F='M|%F|%a|%n'; else S='-f'; F='M|%HT|%Lp|%N'; fi
{walk} -exec printf 'U|%s\\n' {{}} + || exit 5
{walk} -o -exec stat "$S" "$F" {{}} + || exit 6
{walk} -o -type l -exec sh -c 'for p; do t=$(readlink "$p") || exit 1; printf "L|%s|%s\\n" "$t" "$p"; done' sh {{}} + \
  || exit 7
{walk} -o -type f -exec sha256sum {{}} + || exit 8
if [ -r /proc/mounts ]; then
  here=$(pwd -P)
  while read -r _ mnt _; do case "$mnt" in "$here"/*) echo "U|.${{mnt#"$here"}}";; esac; done < /proc/mounts
fi
echo END"""


def parse(text: str) -> Manifest:
    lines = text.splitlines()
    if not lines or lines[-1] != "END":
        raise BindingUnavailable("the manifest listing was cut short")
    meta: dict[str, str] = {}
    links: dict[str, str] = {}
    sums: dict[str, str] = {}
    unbound: list[str] = []
    for line in lines[:-1]:
        if line.startswith("U|"):
            unbound.append(line[2:])
        elif line.startswith("M|"):
            kind, mode, path = line[2:].split("|", 2)
            meta[path] = f"{kind}|{mode}"
        elif line.startswith("L|"):
            target, path = line[2:].rsplit("|", 1)
            links[path] = target
        elif "  " in line:
            digest, path = line.split("  ", 1)
            sums[path] = digest
        elif line:
            raise BindingUnavailable(f"unexpected manifest line: {line[:200]}")
    missing = [p for p in sums if p not in meta]
    if missing:
        raise BindingUnavailable(f"hashed paths without metadata: {missing[:5]}")
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

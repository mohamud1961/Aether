"""What a check in a clone could change, proven in the clone itself, and what it tested besides the delivered files.

``probe``: whether the working directory of a clone is held read-only by the kernel. Two observations, both
required: the mount that holds the working directory is listed read-only in /proc/mounts, and creating a file
there is refused. A permission bit is not a boundary (root, or the owner, can change it back) and a refused write
alone could be a permission bit, so a clone without /proc/mounts, or on a read-write mount, is ``writable`` whatever
a write attempt shows. Mounts below the working directory are reported with their options; a read-write one makes the
whole boundary ``writable`` (same review: listing it while claiming read-only misclassified a writable part).

``scratch_copies``: a read-only delivered tree does not stop a check from copying a delivered file to scratch,
changing the copy, testing that and reporting on the original. Files created or changed in the scratch directories
since the check started are hashed and compared by name with the delivered files: ``same`` copies are exact,
``diverging`` ones share a delivered file's name but not its contents. "Since" is the kernel's ctime against the
clone's clock read by the harness before the check: ``cp -p`` and ``touch`` cannot set a ctime and changing the clock
needs CAP_SYS_TIME, so nothing the check can write moves the cut-off (a marker file in its own writable directory
could be touched or removed: background security review of f85acbd83). It is a record of what was left, by name: a
copy renamed or deleted before the check ends is not in it, and it shows neither what was tested nor decides
anything.
"""

from __future__ import annotations

import re
import shlex
from typing import Any

from .binding import Manifest
from .env import exit_code

MAX_SCRATCH_FILES = 5_000
MAX_SCRATCH_BYTES = 256 * 1024 * 1024
MAX_LISTED = 30
_SUM = re.compile(r"([0-9a-f]{64})  (/.*)")


def _probe_script(workdir: str) -> str:
    return f"""cd -- {shlex.quote(workdir)} || exit 3
[ -r /proc/mounts ] || {{ echo NOMOUNTS; exit 0; }}
here=$(pwd -P); best=""; opts=""
while read -r _ mnt _ o _; do
  case "$here/" in "$mnt"/*|"$mnt/") if [ ${{#mnt}} -ge ${{#best}} ]; then best=$mnt; opts=$o; fi;; esac
  if [ "$mnt" = / ] && [ -z "$best" ]; then best=/; opts=$o; fi
  case "$mnt" in "$here"/*) echo "SUB|$o|$mnt";; esac
done < /proc/mounts
echo "MOUNT|$opts|$best"
p=".aether-boundary-probe-$$"
if ( : > "$p" ) 2>/dev/null; then rm -f -- "$p"; echo CREATED; else echo REFUSED; fi"""


async def probe(env: Any, workdir: str, timeout_s: float = 60) -> dict[str, Any]:
    """``{"boundary": "read_only" | "writable" | "unavailable", ...}`` for the clone ``env``."""
    try:
        result = await env.exec(
            command=_probe_script(workdir),
            cwd=None,
            env=None,
            timeout_sec=max(1, int(timeout_s)),
        )
    except Exception as exc:  # noqa: BLE001 - recorded, and the boundary is then not claimed
        return {
            "boundary": "unavailable",
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }
    out = str(getattr(result, "stdout", "") or "")
    if exit_code(result) != 0:
        return {"boundary": "unavailable", "error": f"probe exit {exit_code(result)}"}
    lines = out.splitlines()
    row: dict[str, Any] = {"write": "created" if "CREATED" in lines else "refused"}
    mount = next((ln for ln in lines if ln.startswith("MOUNT|")), None)
    subs = [ln.split("|", 2) for ln in lines if ln.startswith("SUB|")]
    writable_subs = [m for _, o, m in subs if "rw" in o.split(",")]
    if mount is None:
        row["mount"] = "no /proc/mounts" if "NOMOUNTS" in lines else "not found"
        read_only = False
    else:
        _, opts, point = mount.split("|", 2)
        row["mount"] = f"{point} {opts}"
        read_only = "ro" in opts.split(",")
    if writable_subs:
        row["writable_submounts"] = writable_subs[:MAX_LISTED]
    held = read_only and row["write"] == "refused" and not writable_subs
    row["boundary"] = "read_only" if held else "writable"
    return row


def _scratch_script(roots: tuple[str, ...], since: int) -> str:
    paths = " ".join(shlex.quote(r) for r in roots)
    return f"""if stat -c %Z / >/dev/null 2>&1; then Z='-c %Z'; else Z='-f %c'; fi
n=0; m=$(( ($(date +%s) - {int(since)}) / 60 + 2 ))  # -cmin narrows cheaply; the exact cut-off is below
for r in {paths}; do [ -d "$r" ] && find "$r" -xdev -type f -cmin -"$m" -size -{MAX_SCRATCH_BYTES}c; done |
while IFS= read -r f; do
  c=$(stat $Z "$f" 2>/dev/null) || continue
  [ "$c" -ge {int(since)} ] || continue
  n=$((n + 1)); [ "$n" -le {MAX_SCRATCH_FILES} ] || break
  sha256sum "$f"
done"""


async def clock(env: Any) -> int | None:
    """The clone's clock (epoch seconds), read by the harness: the cut-off for ``scratch_copies``."""
    try:
        result = await env.exec(command="date +%s", cwd=None, env=None, timeout_sec=30)
    except Exception:  # noqa: BLE001 - no cut-off, so no record
        return None
    out = str(getattr(result, "stdout", "") or "").strip()
    return int(out) if exit_code(result) == 0 and out.isdigit() else None


async def scratch_copies(
    env: Any,
    delivered: Manifest,
    roots: tuple[str, ...],
    since: int,
    timeout_s: float = 60,
) -> dict[str, Any]:
    """Scratch files created or changed at or after ``since`` that share a name with a delivered file."""
    try:
        result = await env.exec(
            command=_scratch_script(roots, since),
            cwd=None,
            env=None,
            timeout_sec=max(1, int(timeout_s)),
        )
    except Exception as exc:  # noqa: BLE001 - a record, never a binding
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}
    by_name: dict[str, set[str]] = {}
    for path, entry in delivered.entries.items():
        sha = entry.rsplit("|", 1)[-1]
        if re.fullmatch(r"[0-9a-f]{64}", sha):
            by_name.setdefault(path.rsplit("/", 1)[-1], set()).add(sha)
    same, diverging, seen = [], [], 0
    for line in str(getattr(result, "stdout", "") or "").splitlines():
        match = _SUM.fullmatch(line)
        if not match:
            continue
        seen += 1
        sha, path = match.groups()
        name = path.rsplit("/", 1)[-1]
        if name in by_name:
            (same if sha in by_name[name] else diverging).append(path)
    row: dict[str, Any] = {
        "new_files": seen,
        "same": len(same),
        "diverging": diverging[:MAX_LISTED],
        "diverging_count": len(diverging),
    }
    if seen >= MAX_SCRATCH_FILES:
        row["truncated"] = True
    err = str(getattr(result, "stderr", "") or "").strip()
    if exit_code(result) != 0 or err:
        row["error"] = f"exit {exit_code(result)}: {err[:200]}"
    return row

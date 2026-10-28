"""A copy of the working directory as it was before the first action (AETHER_CORE_START_COPY=on).

Why (pass/fail study, 28 Oct, 47 Luna runs): wrong runs destroyed irreplaceable inputs before reading them (a
database opened before its write-ahead log was copied, a repository reset before the final check) and then
rebuilt or guessed what was lost; correct runs worked from a copy. The harness takes that copy once, before the
model acts, under the control directory, and says where it is in the task message. It never reads or uses it.

Bounded: a working directory over LIMIT_BYTES (or one that cannot be measured or copied) is not copied, and the
task message says nothing. The copy is taken before the start marker, so it is never counted as the run's work.
"""

from __future__ import annotations

import posixpath
import shlex

from .env import Environment, run

START_COPY_ENV = "AETHER_CORE_START_COPY"
LIMIT_BYTES = 512 * 1024 * 1024
NOTE = ("(A copy of {workdir} as it was before your first action is at {copy}. The harness made it and does "
        "not use it.)")


async def take(env: Environment, workdir: str, control_dir: str) -> tuple[str, dict]:
    """Copy ``workdir`` under ``control_dir``; returns the note for the task message ('' when not copied) and a
    trace row."""
    copy = posixpath.join(control_dir, "start", posixpath.basename(workdir.rstrip("/")) or "root")
    q = shlex.quote
    script = (f"k=$(du -sk {q(workdir)} 2>/dev/null | cut -f1); [ -n \"$k\" ] || {{ echo unmeasured; exit 3; }}; "
              f"[ $((k*1024)) -le {LIMIT_BYTES} ] || {{ echo too_large $k; exit 4; }}; "
              f"mkdir -p {q(posixpath.dirname(copy))} && cp -a {q(workdir)} {q(copy)} && echo ok $k")
    try:
        result = await run(env, script, timeout_s=120)
    except Exception as exc:  # an instrument: no copy, no note
        return "", {"copied": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}
    words = result.stdout.split()
    if result.code != 0 or not words or words[0] != "ok":
        return "", {"copied": False, "reason": (result.stdout or result.stderr).strip()[:300], "exit": result.code}
    return NOTE.format(workdir=workdir, copy=copy), {"copied": True, "path": copy, "kib": int(words[1])}

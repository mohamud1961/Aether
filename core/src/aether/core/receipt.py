"""The run's start marker and a bounded observation of current regular files changed since it.

The scan compares both modification time and POSIX change time with the marker. This detects ordinary shell writes
even when the command restores the old mtime. It does not prove a complete custody history: deleted files and a
filesystem restored from an external snapshot may not be observable.
"""

from __future__ import annotations

import shlex
import posixpath

from .env import Environment, exit_code

MARKER = "start_marker"
SKIP = (".git", "__pycache__", "node_modules", "venv", ".venv", "site-packages")


async def mark(env: Environment, control_dir: str) -> None:
    """Record the run's start time on disk; files newer than this are what the run changed.

    File timestamps are clock-tick coarse (a few ms on Linux) and ``find -newer`` is strict, so a write in the
    marker's own tick would be invisible. Return only once ``find -newer`` itself, the inventory's comparator, sees a
    file touched after the marker as newer: every later write is then newer, every earlier one is not.
    """
    marker = shlex.quote(f"{control_dir}/{MARKER}")
    tick = shlex.quote(f"{control_dir}/{MARKER}.tick")
    result = await env.exec(
        command=(
            f"touch {marker} && touch {tick} && n=0 && "
            f"while [ -z \"$(find {tick} -newer {marker})\" ]; do n=$((n+1)); [ $n -le 3000 ] || exit 1; "
            f"sleep 0.001 2>/dev/null; touch {tick} || exit 1; done; rm -f {tick}"
        ),
        cwd=None,
        env=None,
        timeout_sec=30,
    )
    if exit_code(result) != 0:
        raise OSError("finish receipt marker could not be written")


def _find(workdir: str, control_dir: str) -> str:
    marker = shlex.quote(f"{control_dir}/{MARKER}")
    tests = [f"-name {shlex.quote(name)}" for name in SKIP]
    # A configured control store may be inside the workspace. Never treat
    # recorder copies or tool command files as task artifacts, recursively.
    if posixpath.isabs(workdir) and posixpath.isabs(control_dir):
        relative = posixpath.relpath(control_dir, workdir)
        if relative != ".." and not relative.startswith("../"):
            tests.append("-path " + shlex.quote("." if relative == "." else "./" + relative))
    prune = " -o ".join(tests)
    return (
        f"cd {shlex.quote(workdir)} && "
        f"find . -xdev \\( {prune} \\) -prune -o -type f \\( -newer {marker} -o -cnewer {marker} \\) -print0"
    )


async def changed(env: Environment, workdir: str, control_dir: str) -> list[str]:
    """Current regular-file paths with newer mtime or ctime than ``mark``. Raises on listing failure."""
    marker = shlex.quote(f"{control_dir}/{MARKER}")
    command = f"test -e {marker} && {_find(workdir, control_dir)}"  # no marker is an error, not "nothing changed"
    result = await env.exec(command=command, cwd=None, env=None, timeout_sec=30)
    if exit_code(result) != 0:
        raise OSError(
            f"changed files could not be listed: {str(getattr(result, 'stderr', ''))[:200]}"
        )
    # POSIX names may contain every line separator. NUL is the only safe
    # delimiter; sort locally so a pipeline cannot mask find's exit status.
    output = str(getattr(result, "stdout", "") or "")
    if output and not output.endswith("\0"):
        raise OSError("changed files listing was truncated (missing NUL terminator)")
    return sorted(output[:-1].split("\0")) if output else []

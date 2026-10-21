"""The run's start marker and the list of files changed since it (used by the verifier, the finish report and the
binding check).

``mark`` records the start time on disk when the run begins; ``changed`` lists the files under the working directory
that are newer than it.
"""

from __future__ import annotations

import shlex

from .env import Environment, exit_code

MARKER = "start_marker"
SKIP = (".git", "__pycache__", "node_modules", "venv", ".venv", "site-packages")


async def mark(env: Environment, control_dir: str) -> None:
    """Record the run's start time on disk; files newer than this are what the run changed."""
    result = await env.exec(
        command=f"touch {shlex.quote(f'{control_dir}/{MARKER}')}",
        cwd=None,
        env=None,
        timeout_sec=30,
    )
    if exit_code(result) != 0:
        raise OSError("finish receipt marker could not be written")


def _find(workdir: str, control_dir: str) -> str:
    marker = shlex.quote(f"{control_dir}/{MARKER}")
    prune = " -o ".join(f"-name {shlex.quote(name)}" for name in SKIP)
    return (
        f"cd {shlex.quote(workdir)} && "
        f"find . -xdev \\( {prune} \\) -prune -o -type f -newer {marker} -print 2>/dev/null | sort"
    )


async def changed(env: Environment, workdir: str, control_dir: str) -> list[str]:
    """Paths (relative to ``workdir``) of the files changed since ``mark``. Raises if they cannot be listed."""
    marker = shlex.quote(f"{control_dir}/{MARKER}")
    command = f"test -e {marker} && {_find(workdir, control_dir)}"  # no marker is an error, not "nothing changed"
    result = await env.exec(command=command, cwd=None, env=None, timeout_sec=30)
    if exit_code(result) != 0:
        raise OSError(
            f"changed files could not be listed: {str(getattr(result, 'stderr', ''))[:200]}"
        )
    return [
        line for line in str(getattr(result, "stdout", "") or "").splitlines() if line
    ]

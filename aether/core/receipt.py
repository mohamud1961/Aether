"""Finish receipt (opt-in): before the first finish takes effect, show the model the bytes it is about to deliver.

The first-divergence and S4 audits found final summaries that disagreed with the files on disk (a summary saying
R→M over a file encoding M→R; a "verified" construct missing its tagged donor). A confirmation question alone
changed nothing in Terminus (13 of 13 reaffirmed). The receipt adds new evidence instead: the heads of the files
changed under the working directory since the run started. It is information, not a gate: the next finish ends
the work, and it is shown once.
"""

from __future__ import annotations

import shlex

from .env import Environment, exit_code

MARKER = "start_marker"
HEAD_BYTES = 1200
MAX_FILES = 40
BUDGET_CHARS = 8000
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


def _script(workdir: str, control_dir: str) -> str:
    return (
        _find(workdir, control_dir) + " | "
        f"head -n {MAX_FILES} | while IFS= read -r f; do "
        f'sz=$(stat -c %s "$f" 2>/dev/null || wc -c < "$f"); echo "=== $f ($sz bytes)"; '
        f'if [ "$sz" -eq 0 ]; then echo "[empty]"; '
        f'elif head -c 4096 "$f" | grep -qI .; then head -c {HEAD_BYTES} "$f"; '
        f'[ "$sz" -gt {HEAD_BYTES} ] && printf "\\n[... first {HEAD_BYTES} of $sz bytes shown]"; echo; '
        f'else echo "[binary]"; fi; done'
    )


async def receipt(env: Environment, workdir: str, control_dir: str) -> str:
    """The receipt text shown in place of the first finish."""
    result = await env.exec(
        command=_script(workdir, control_dir), cwd=None, env=None, timeout_sec=30
    )
    body = str(getattr(result, "stdout", "") or "")
    if exit_code(result) != 0 and not body:
        body = f"[the changed files could not be listed: {str(getattr(result, 'stderr', ''))[:300]}]"
    elif not body.strip():
        body = f"[no files under {workdir} changed since the run started]"
    if len(body) > BUDGET_CHARS:
        body = (
            body[:BUDGET_CHARS]
            + "\n[... receipt cut at its size limit; read the files for the rest]"
        )
    return (
        "[finish receipt] Your finish has not taken effect yet. These are the files changed under "
        f"{workdir} since the run started (heads only): the bytes that will be judged, not your "
        "description of them.\n\n"
        f"{body}\n\n"
        "Check them against each requirement in the task: content, format, names and locations. If they are "
        "right, call finish again to end the work; if not, fix them first. This receipt is shown once."
    )

"""Reversible task-start state: archive the workdir before the first model call.

Substrate only. The archive is written outside the workdir, so deliverables are untouched,
and the solver is told one plain fact: where the start state is. Nothing is interpreted.
Opt-in with AETHER_CORE_START_ARCHIVE=on. Core's start_copy (default on since 28 Oct) already gives
the run a task-start copy; this tar variant is the Mini A1 study arm and must not be stacked on it by default.
"""

from __future__ import annotations

import shlex
from typing import Any, Mapping

ARCHIVE = "/task-start.tar"
ENV_FLAG = "AETHER_CORE_START_ARCHIVE"


async def add(environment: Any, environ: Mapping[str, str], workdir: str, task: str) -> tuple[str, str]:
    """Return (task, status). The task gains one sentence only when the archive was written."""
    if environ.get(ENV_FLAG) != "on" or not workdir:
        return task, "off"
    parent, name = workdir.rstrip("/").rsplit("/", 1) if workdir.rstrip("/").count("/") else ("", workdir)
    cmd = (
        f"test -d {shlex.quote(workdir)} && ! test -e {ARCHIVE} && "
        f"tar -cpf {ARCHIVE} -C {shlex.quote(parent or '/')} {shlex.quote(name)} && chmod a-w {ARCHIVE} && echo START_ARCHIVE_OK"
    )
    result = await environment.exec(command=cmd, timeout_sec=300)
    out = (result.stdout or "") + (result.stderr or "")
    if not out.strip().endswith("START_ARCHIVE_OK"):
        return task, "failed: " + out.strip()[-200:]
    sentence = f"A tar archive of every file under {workdir} as it was when this task started is at {ARCHIVE}."
    return task.rstrip() + "\n\n" + sentence, "ok"

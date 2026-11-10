"""Reversible task-start state: archive the workdir before the first model call.

Substrate only. The archive is written outside the workdir, so deliverables are untouched,
and the solver is told one plain fact: where the start state is. Nothing is interpreted.
On by default since 10 Nov 2026 (A1: db-wal causal gain, 0 archive-attributable regressions
across Luna + GLM boards, g3/MISSION_LOG.md). AETHER_CORE_START_ARCHIVE=off disables it.
"""

from __future__ import annotations

import shlex
from typing import Any, Mapping

ARCHIVE = "/task-start.tar"
ENV_FLAG = "AETHER_CORE_START_ARCHIVE"


async def add(environment: Any, environ: Mapping[str, str], workdir: str, task: str) -> tuple[str, str]:
    """Return (task, status). The task gains one sentence only when the archive was written."""
    if environ.get(ENV_FLAG, "on") == "off" or not workdir:
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

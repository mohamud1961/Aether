"""Keep the final state of a run (AETHER_CORE_KEEP_FINAL=1): an evidence bank for scoring checks offline.

Why: a check is worth handing to the worker only if it separates finished work that is right from work that is
wrong. CH2 measured its checks on the runs it was helping (no labels until the end, clones discarded), so a
check's quality could never be scored (research/core_mission_20261028/ch2). With this flag, when the agent returns
(after Core's own cleanup, before the grader runs), the task container is committed to a local image and the
processes then running are recorded, so the same state can be re-started later, with its services, and any check
script run against it next to the run's reward. The image holds only the container's own layer; nothing is
shown to the model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from .clone import _UNLABEL, compose_container, host_run, identify
from .env import run

KEEP_ENV = "AETHER_CORE_KEEP_FINAL"
PROCS = "for p in /proc/[0-9]*; do [ -r $p/cmdline ] || continue; c=$(tr '\\0' ' ' < $p/cmdline); " \
        "[ -n \"$c\" ] && printf '%s\\t%s\\t%s\\n' \"${p#/proc/}\" \"$(readlink $p/cwd)\" \"$c\"; done"


async def keep(environment: Any, environ: Mapping[str, str], logs: Path) -> None:
    """Commit the task container to ``aether-bank:<session>`` and write ``bank.json``; failures are recorded."""
    if environ.get(KEEP_ENV, "") != "1":
        return
    from harbor.environments.docker.docker import _sanitize_docker_compose_project_name

    session = _sanitize_docker_compose_project_name(environment.session_id)
    tag = "aether-bank:" + re.sub(r"[^a-z0-9_.-]", "-", session.lower())[:120]
    row: dict[str, Any] = {"image": tag}
    try:
        procs = await run(environment, PROCS)
        row["processes"] = [ln.split("\t", 2) for ln in (procs.stdout or "").splitlines() if ln.count("\t") >= 2]
        cid = await identify(environment, host_run, await compose_container(session))
        code, _, err = await host_run(["docker", "commit", *_UNLABEL, cid, tag], 900)
        row["committed"] = code == 0
        if code:
            row["error"] = err.strip()[:300]
    except Exception as exc:  # noqa: BLE001 - evidence only; the run's outcome never depends on it
        row["error"] = f"{type(exc).__name__}: {exc}"[:300]
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "bank.json").write_text(json.dumps(row))

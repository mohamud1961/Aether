"""Run Core against a running Docker container without Harbor (master checklist H7).

    python -m aether.core.local_run --container NAME --task-file task.txt --logs DIR [--workdir /app] [--timeout 900]
                                    [--resume SESSION_DIR]

``--resume`` continues a run whose controller died, from that run's session log (H10, ``AETHER_CORE_SESSION_LOG``):
the new controller gets the last trusted context; calls whose results were never recorded are answered as unknown
and are not run again. The account of the recovery is written to ``<logs>/session_recovery.json``.

The configuration and provider come from the same environment variables as the Harbor agent (``harbor_config``),
including the route-modality record, so the same run contract applies. There is no grading here: a grade is the
orchestrator's job, and this entry point writes no reward. Every call to a provider is paid; ask before running it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from . import route_modality, session_log
from .docker_env import DockerExecEnv
from .harbor_agent import DEPLOYMENT_ENV, REVIEW_ENV, agent_timeout, build_config, build_provider, discover_workdir
from .loop import Trace, run_agent
from .runrecord import write_record


async def run(container: str, task: str, logs: Path, workdir: str | None, timeout: float | None,
              resume_dir: Path | None = None) -> str:
    environ = dict(os.environ)
    logs.mkdir(parents=True, exist_ok=True)
    started = time.time()
    timeout_s = agent_timeout(timeout, environ=environ)
    config = build_config(environ=environ)
    route = route_modality.check(environ, deployment=environ.get(DEPLOYMENT_ENV, ""), images=config.images)
    if route:
        (logs / "route_modality.txt").write_text(route)
    resume = None
    if resume_dir is not None:
        resume, account = session_log.recover(resume_dir)
        (logs / "session_recovery.json").write_text(json.dumps(account, indent=1))
    env = DockerExecEnv(container)
    workdir = workdir or await discover_workdir(env)
    provider = build_provider(logs, environ=environ)
    result = None
    try:
        result = await run_agent(env=env, task=task, workdir=workdir, provider=provider, timeout_s=timeout_s,
                                 trace=Trace(logs / "core_trace.jsonl"), config=config, resume=resume)
        return result.status
    finally:
        write_record(logs, result, started=started, workdir=workdir, config=config,
                     review=environ.get(REVIEW_ENV), provider=provider)
        await provider.aclose()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--container", required=True)
    ap.add_argument("--task-file", required=True, type=Path)
    ap.add_argument("--logs", required=True, type=Path)
    ap.add_argument("--workdir")
    ap.add_argument("--timeout", type=float)
    ap.add_argument("--resume", type=Path)
    args = ap.parse_args(argv[1:])
    status = asyncio.run(run(args.container, args.task_file.read_text(), args.logs, args.workdir, args.timeout,
                             args.resume))
    print(status)
    return 0 if status == "finished" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

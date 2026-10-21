"""Matched first-finish continuations: an experiment instrument, never a default.

Question (selection of 21 Oct 2026): when the solver finishes wrong with the refuting observation already in its
record, does a continuation repair the work, and does the harness's own record of the run make a difference? At the
first ``finish`` the delivered working directory is exported as it stands (arm A, the run's own outcome: the finish
then takes effect unchanged), and two writable clones of the container each continue the solver's own message
history, answering its finish call:
- B, neutral: ``CONTINUE`` only, so B measures what one more chance alone does;
- C, the same text followed by the harness's finish report on the state at the finish (observed facts and claims
  with no supporting observation identified, rendered by ``finish_report``; the model's own account is left out
  because it already wrote it). C differs from B only by that record.

No model call is added beyond the continuations themselves, nothing reaches the original container, and the
official grader is not involved: each arm's working directory is exported to the run's log directory, to be graded
after the run by ``tools/fork_grade`` against fresh task containers. The arms record what they did; the run's
outcome is A's.
"""

from __future__ import annotations

import asyncio
import dataclasses
import shlex
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from . import finish_report
from .env import exit_code
from .loop import STOP_MARGIN_S, CoreConfig, Trace, run_agent
from .oversight import ReviewPlan
from .verify import _Labelled

FORK_MAX_S = 300.0  # each arm's working time
FORK_MIN_S = 60.0  # with less time left, no fork (recorded as skipped)
EXPORT_TIMEOUT_S = 120.0
CONTINUE = (
    "[Your finish was received. Before it takes effect you may continue working; call finish again to end.]"
)
RECORD_HEAD = (
    "The harness's record of the run at your finish follows. These are observations, not instructions. A flag "
    "means no supporting observation was identified in the captured record, not that something is wrong."
)


def arm_config(config: CoreConfig, arm: str) -> CoreConfig:
    """The solver's configuration for an arm: no fork, check, reviews or clones of its own."""
    return dataclasses.replace(
        config, fork=False, verify=False, reviews=ReviewPlan(finish=False), make_clone=None, contract=False
    )


def record_text(report: dict[str, Any]) -> str:
    """The report without the model's own account."""
    text = finish_report.render(report)
    head, _, rest = text.partition("## The model's account")
    _, _, after = rest.partition("\n## ")
    return head.rstrip() + ("\n\n## " + after if after else "")


async def export(env: Any, workdir: str, target: Path) -> dict[str, Any]:
    """Pack the working directory and copy it to ``target``; the outcome, never an exception."""
    remote = f"/tmp/aether_fork_{target.stem}.tgz"
    try:
        res = await env.exec(
            command=f"tar -C {shlex.quote(workdir)} -czf {remote} .", cwd=None, env=None, timeout_sec=EXPORT_TIMEOUT_S
        )
        if exit_code(res) != 0:
            return {"export": None, "export_error": str(getattr(res, "stderr", ""))[:300]}
        await env.download_file(remote, target)
        return {"export": str(target)}
    except Exception as exc:  # noqa: BLE001 - an export failure is recorded, the run goes on
        return {"export": None, "export_error": f"{type(exc).__name__}: {exc}"}


def continued(s: Any, text: str) -> Any:
    """A copy of the solver's history at its finish, with ``text`` as the result of the finish call."""
    answer = {"role": "tool", "tool_call_id": s.call_id, "content": text}
    if s.clm is None:
        return deepcopy(s.messages) + [answer]
    clm = deepcopy(s.clm)
    clm._reasoning = {id(m): (m, n) for m, n in clm._reasoning.values()}  # keyed by identity: re-key the copies
    clm.append(answer)
    return clm


async def _arm(s: Any, arm: str, text: str, budget: float, logs: Path) -> dict[str, Any]:
    started, row = time.monotonic(), {"arm": arm}
    clone = None
    try:
        clone = await s.clone(s.env, timeout_s=budget, read_only=False)
        row["clone_ready_s"] = round(time.monotonic() - started, 1)
        history = continued(s, text)
        result = await run_agent(
            env=clone,
            task=s.task,
            workdir=s.workdir,
            provider=_Labelled(s.provider, f"fork_{arm}"),
            timeout_s=max(1.0, budget - (time.monotonic() - started)) + STOP_MARGIN_S,
            trace=Trace(logs / f"fork_{arm}_trace.jsonl"),
            config=arm_config(s.config, arm),
            resume=history,
        )
        row.update(status=result.status, steps=result.steps, finished_again=result.status == "finished")
        row.update(await export(clone, s.workdir, logs / f"fork_{arm}_workdir.tgz"))
    except Exception as exc:  # noqa: BLE001 - an arm failure is recorded; the run's own finish is unaffected
        row["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if clone is not None:
            try:
                await asyncio.wait_for(clone.close(), 60)
            except Exception as exc:  # noqa: BLE001
                row["close_error"] = f"{type(exc).__name__}: {exc}"
    row["elapsed_s"] = round(time.monotonic() - started, 1)
    return row


async def at_finish(s: Any) -> tuple[str, bool]:
    """Export A, run B and C on clones in parallel, record; the solver's finish then takes effect unchanged."""
    logs = s.trace.path.parent
    budget = min(FORK_MAX_S, s.remaining() - STOP_MARGIN_S)
    if budget < FORK_MIN_S:
        s.result.extras["fork"] = {"status": "skipped", "reason": "low_time", "remaining_s": round(s.remaining(), 1)}
        return "finished", True
    row: dict[str, Any] = {"status": "ran", "budget_s": round(budget, 1), "a": await export(s.env, s.workdir, logs / "fork_a_workdir.tgz")}
    try:
        report = await finish_report.build(
            s.env, s.workdir, s.config.control_dir, s.report_steps, status="finished",
            finish_summary=(s.result.extras.get("finish_args") or {}).get("summary"),
            left_running=[], task=s.task,
        )
        record = record_text(report)
        row["c_record_chars"] = len(record)
        row["c_flags"] = {
            k: len(v) for k, v in (report.get("unbacked_claims") or {}).items() if isinstance(v, list)
        }
    except Exception as exc:  # noqa: BLE001 - without a record there is no C; B still runs
        record, row["c_error"] = "", f"{type(exc).__name__}: {exc}"
    arms = [("b", CONTINUE)] + ([("c", f"{CONTINUE}\n\n{RECORD_HEAD}\n\n{record}")] if record else [])
    rows = await asyncio.gather(*(_arm(s, arm, text, budget, logs) for arm, text in arms))
    row.update({r["arm"]: r for r in rows})
    s.result.extras["fork"] = row
    s.trace("fork", **row)
    return "finished", True

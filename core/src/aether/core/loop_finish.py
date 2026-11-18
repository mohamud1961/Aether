"""Finish requests: the scheduled review, the finish path and the diffcheck author (split from loop.py)."""

from __future__ import annotations

import json
from typing import Any

from .oversight import final_feedback, progress_feedback
from .record import NEUTRAL_HOLD
from . import finish_facts, finish_settle, open_issues
from .loop_config import CoreConfig
from .loop_session import _Session, _attach


async def _scheduled_review(s: _Session, kind: str) -> None:
    verdict, row = await s.oversight.run(
        kind,
        s.env,
        task=s.task,
        workdir=s.workdir,
        actions=s.actions,
        written=list(s.files.written),
    )
    s.result.reviews.append(row)
    s.trace("review", answers=verdict.answers, **row)
    if verdict.status == "error":
        return
    text = (
        final_feedback(verdict, s.remaining())
        if kind == "final"
        else progress_feedback(verdict, s.elapsed(), s.timeout_s)
    )
    _attach(s.history, text)


def _appendix(config: CoreConfig) -> str:
    """Study arm (XL, 11 Nov): text placed after the task, read from a file named by the launcher. Used to carry the
    solver's own step-0 list of the points the task leaves open, written from the task text before the run starts."""
    path = getattr(config, "task_appendix_file", "")
    if not path:
        return ""
    with open(path, encoding="utf-8") as handle:
        return "\n\n" + handle.read().strip()


def _with_state(s: _Session, out: str) -> str:
    """The run state view after a change or checkpoint; otherwise one line while a check is failing."""
    if s.state.dirty:
        s.state.dirty = False
        return f"{out}\n\n{s.state.view()}"
    line = s.state.reminder()
    return f"{out}\n{line}" if line else out


async def _finish(s: _Session, args: dict[str, Any]) -> tuple[str, bool]:
    if s.config.role == "worker" and (facts := await finish_facts.at_finish(s)):
        s.finish_wait_returned = True  # the facts include pending terminals; no second pending-terminal hold
        return facts, False
    if s.config.terminal_events and s.config.role == "worker":
        pending = s.terminals.pending_names()
        s.result.extras["finish_terminal_frontier"] = pending
        if pending and s.remaining() > 15 and not s.finish_wait_returned:
            s.finish_wait_returned = True
            # A foreground command may be the service the task asks to leave
            # running. Give near-term exits a chance to arrive without using
            # the remaining solve budget as an implicit join.
            observed = await s.terminals.wait_events(pending[:8], mode="all", wait_s=1.0)
            s.trace("finish_pending_terminal_observation", **observed)
            return ("Foreground terminal state at finish. If a pending command is needed, wait for its result. "
                    "If it should remain running, you can finish again.\n" + json.dumps(observed), False)
    s.result.extras["finish_args"] = args
    if s.config.role == "worker" and (settle := await finish_settle.at_finish(s)):
        return settle, False
    if s.config.open_issues and not s.result.extras.get("open_issues_held"):
        text = open_issues.hold(args, s.remaining(), s.timeout_s)
        s.trace("open_issues", issues=open_issues.issues(args), held=text is not None,
                remaining_s=round(s.remaining(), 1))
        if text:
            s.result.extras["open_issues_held"] = True
            return text, False
    if s.record:
        hold, text, _row = await s.record.at_finish()
        if hold:
            return text, False
    elif s.config.finish_hold == "neutral" and not s.held:
        s.held = True
        s.trace("finish_hold", kind="neutral", remaining_s=round(s.remaining(), 1))
        return NEUTRAL_HOLD.format(left=s.remaining()), False
    if s.state:
        held, text = await s.state.at_finish(s.env, s.remaining(), s.timeout_s)
        s.trace("state_finish", held=held, state=s.state.record())
        if held:
            return text, False
    if s.diffcheck:
        note = await s.diffcheck.at_finish()
        if note:
            return note, False
    if s.config.exec_check and not s.config.rival and "rival" not in s.result.extras:
        from . import rival

        text, row = rival.exec_at_finish(s.remaining, s.timeout_s)
        s.result.extras["rival"] = row
        s.trace("rival", handed_back=text is not None, **row)
        if text:
            return text, False
    if s.config.rival and "rival" not in s.result.extras:
        from . import rival

        text, row = await rival.at_finish(
            s.env, s.provider.complete, task=s.task, summary=str(args.get("summary", "")), workdir=s.workdir,
            control_dir=s.config.control_dir, remaining_s=s.remaining, timeout_s=s.timeout_s)
        s.result.extras["rival"] = row
        s.trace("rival", handed_back=text is not None, **row)
        if text:
            return text, False
    if s.config.card and ("rival" not in s.result.extras or s.result.extras["rival"].get("again")):
        from . import attack, card

        text, row = await (attack.at_finish(s) if s.config.card_challenge in ("attack", "observe", "forks") else card.at_finish(
            s.env, s.provider.complete, task=s.task, workdir=s.workdir, control_dir=s.config.control_dir,
            remaining_s=s.remaining, timeout_s=s.timeout_s, probe=s.config.card_probe, challenge=bool(s.config.card_challenge)))
        s.result.extras["rival"] = row
        s.trace("rival", handed_back=text is not None, **row)
        if text:
            return text, False
    if s.config.verify and "verification" not in s.result.extras:
        from . import verify

        return await verify.at_finish(s)
    if s.config.fork and "fork" not in s.result.extras:
        from . import fork

        return await fork.at_finish(s)
    skip = s.oversight.finish_gate(s.remaining())
    if skip:
        s.trace(
            "finish", summary=args.get("summary", ""), review="skipped", reason=skip
        )
        return "finished", True
    verdict, row = await s.oversight.run(
        "finish",
        s.env,
        task=s.task,
        workdir=s.workdir,
        actions=s.actions,
        written=list(s.files.written),
    )
    s.result.reviews.append(row)
    s.trace("review", summary=args.get("summary", ""), answers=verdict.answers, **row)
    return (
        f"finished\n[advisory review; does not block finish]\n{verdict.feedback()}",
        True,
    )

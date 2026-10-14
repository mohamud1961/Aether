"""One independent check of the solver's first finish: the same model, a fresh context, a disposable copy of the state.

At the first ``finish`` a no-network clone of the task container is taken, the solver's control directory (context
mirror, terminal logs, REPL state) is removed from it, and a second run of the Core loop works there as the
verifier: the task in a brief that asks for an independent check, the same tools, its own message history and its
own call-log role. None of the solver's reasoning, transcript, summary or claims reaches it; files the solver left
in the workspace are part of the state, and the brief says to treat them as claims. Everything it runs happens in
the clone, never in the graded container. It ends with a verdict: confirmed, or refuted with evidence.

- confirmed: the finish takes effect.
- refuted: the evidence goes back to the solver as the result of its finish and the work continues. The solver
  decides what to do with it; its next finish ends the work. There is never a second check.
- no verdict (the clone or the verifier failed, or the verifier ran out of time): the finish takes effect and the
  reason is recorded. A failure of the check never holds the work.
- skipped when less than VERIFY_MIN_REMAINING_S is left, so a refutation could not be acted on (recorded).

The check's time comes out of the solver's limit: VERIFY_SHARE of what is left, at most VERIFY_MAX_S.
"""

from __future__ import annotations

import dataclasses
import posixpath
import shlex
import time
from typing import Any

from .env import exit_code
from .loop import VERIFIER_ROLE, CoreConfig, Trace, run_agent
from .oversight import ReviewPlan

VERIFY_SHARE = 0.4
VERIFY_MAX_S = 600.0
VERIFY_MIN_REMAINING_S = 180.0
MAX_EVIDENCE_CHARS = 8_000
TRACE_FILE = "verifier_trace.jsonl"

BRIEF = """Another engineer was given the task below in this container and says it is complete. Check that \
claim independently. You have not seen their work or reasoning and should not rely on it: files they left \
(scripts, notes, test output) are claims, not evidence.

Decide whether the current state meets every requirement of the task, the way the task will be judged. Work out \
what the correct result must be from the task itself and from sources they did not produce, then compare it with \
what is actually there: run the real program, read the real output files, recompute values yourself. Spend your \
effort on what is most likely to be wrong: values taken from an example in the task, definitions or conventions \
the task leaves open, data from a source someone picked, and anything only their own check supports.

This container is a disposable copy without network access; nothing you do changes the real one. Programs that \
were running in the original are not running here.

Finish with verdict "confirmed" only if you checked every requirement and each one holds. Otherwise finish with \
"refuted" and the evidence: what is wrong, how you established it, and the correct result if you know it.

The task:
{task}"""

REFUTED = """[independent check: refuted; the finish did not take effect]
A separate check, made from the task alone in a copy of your current state, found:
{evidence}

It can be wrong. Decide for yourself: fix what it found, or, if you are sure it is mistaken, call finish again. \
There is no second check; your next finish ends the work."""


class _Labelled:
    """The solver's provider with every call recorded under the verifier's role (its helper calls as
    ``verifier.<role>``), so the row's totals include the check and each run reports only its own usage."""

    def __init__(self, provider: Any, role: str) -> None:
        self._provider, self._role = provider, role

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    async def complete(self, *args: Any, role: str, **kwargs: Any) -> Any:
        label = role if role == self._role else f"{self._role}.{role}"
        return await self._provider.complete(*args, role=label, **kwargs)


def verifier_config(config: CoreConfig) -> CoreConfig:
    """The solver's configuration for the verifier's run: its own control directory and context files, no
    reviews, contract, receipt or self-check paragraph, and no check of its own."""
    root = f"{config.control_dir}-verifier"
    return dataclasses.replace(
        config,
        verify=False,
        self_check=False,
        role=VERIFIER_ROLE,
        reviews=ReviewPlan(finish=False),
        contract=False,
        receipt=False,
        control_dir=root,
        clm=dataclasses.replace(
            config.clm,
            mirror_path=f"{root}/ctx/LIVE_CTX.txt",
            history_path=f"{root}/ctx/HISTORY.txt",
        ),
    )


async def _forget_the_solver(clone: Any, config: CoreConfig) -> None:
    """Remove the solver's own files (context mirror and history, terminal logs, REPL state) from the clone."""
    paths = {
        config.control_dir,
        posixpath.dirname(config.clm.mirror_path),
        posixpath.dirname(config.clm.history_path),
    }
    command = "rm -rf " + " ".join(shlex.quote(p) for p in sorted(paths))
    result = await clone.exec(command=command, cwd=None, env=None, timeout_sec=60)
    if exit_code(result) != 0:
        raise OSError(f"could not remove the solver's files from the clone: {command}")


def _usage(provider: Any) -> dict[str, int | None]:
    roles = [
        r
        for r in provider.log.by_role
        if r == VERIFIER_ROLE or r.startswith(VERIFIER_ROLE + ".")
    ]
    return provider.log.usage(roles)


def _record(s: Any, row: dict[str, Any]) -> None:
    s.result.extras["verification"] = row
    s.trace("verification", **row)


async def at_finish(s: Any) -> tuple[str, bool]:
    """Run the one check for the solver's finish. Returns (finish result shown to the solver, finished)."""
    left = s.remaining()
    if left < VERIFY_MIN_REMAINING_S:
        _record(
            s,
            {"status": "skipped", "reason": "low_time", "remaining_s": round(left, 1)},
        )
        return "finished", True
    budget = min(VERIFY_MAX_S, VERIFY_SHARE * left)
    started = time.monotonic()
    row: dict[str, Any] = {"budget_s": round(budget, 1)}
    clone, result = None, None
    try:
        clone = await s.clone(s.env)
        await _forget_the_solver(clone, s.config)
        result = await run_agent(
            env=clone,
            task=BRIEF.format(task=s.task),
            workdir=s.workdir,
            provider=_Labelled(s.provider, VERIFIER_ROLE),
            timeout_s=budget,
            trace=Trace(s.trace.path.with_name(TRACE_FILE)),
            config=verifier_config(s.config),
        )
    except Exception as exc:
        row["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        if clone is not None:
            try:
                await clone.close()
            except Exception as exc:
                row["close_error"] = f"{type(exc).__name__}: {exc}"
    args = result.extras.get("finish_args", {}) if result else {}
    verdict = args.get("verdict") if result and result.status == "finished" else None
    evidence = str(args.get("evidence", ""))
    if len(evidence) > MAX_EVIDENCE_CHARS:
        evidence = evidence[:MAX_EVIDENCE_CHARS] + "\n[evidence truncated]"
    row.update(
        status=verdict or ("error" if "reason" in row else "no_verdict"),
        evidence=evidence,
        verifier_status=result.status if result else None,
        verifier_error=result.error if result else None,
        steps=result.steps if result else 0,
        elapsed_s=round(time.monotonic() - started, 1),
        usage=_usage(s.provider),
    )
    _record(s, row)
    if verdict == "refuted":
        return REFUTED.format(evidence=evidence), False
    return f"finished\n[independent check: {row['status']}]", True

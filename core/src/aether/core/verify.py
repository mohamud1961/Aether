"""One independent check of the solver's first finish: the same model, a fresh context, a disposable copy of the state.

At the first ``finish`` the delivered tree under the working directory is fingerprinted, a no-network clone of the
task container is taken, the solver's control directory is removed from it, and a second run of the Core loop works
there as the verifier: an assessor's system prompt (tools.VERIFIER_PROMPT), the same tools, its own message history
and call-log role. Its brief is neutral (no completion claim) and lists the files the work changed. None of the
solver's reasoning, transcript, summary or claims reaches it. Everything it runs happens in the clone.

It ends with one of three findings (tools.VERDICT_FINISH):
- defect_found: the evidence goes back to the solver as the result of its finish and the work continues; the
  solver decides what to do with it, and its next finish ends the work. There is never a second check.
- no_defect_found: the finish takes effect. It certifies nothing unless it is bound: every file of the delivered
  tree was unchanged in the clone when the verifier concluded, and unchanged in the original when the check ended.
- undetermined: the finish takes effect; missing evidence (no network, no running services in the clone) is not a
  defect (A1: checks that held correct states).

Binding (Codex review 15 Oct: a verifier that repaired its clone and then confirmed was accepted while the graded
file stayed wrong): a delivered file modified or deleted in the clone voids the finding; the solver is shown what
the check changed and what it reported, as a proposed repair, and the work continues. New files (build and scratch
output) are recorded, not voiding. A delivered file that changed in the original during the check (a background
job) makes the finding stale; the finish takes effect and that is recorded.

Time (same review: clone set-up could consume the solver's whole remainder): one absolute deadline spans listing,
fingerprints, clone, review and cleanup, VERIFY_SHARE of what is left and at most VERIFY_MAX_S, so the rest stays
the solver's. A check that cannot finish in time, fails, or is cancelled never holds the finish; every outcome,
including cancellation, is recorded. Skipped when less than VERIFY_MIN_REMAINING_S is left.
"""

from __future__ import annotations

import asyncio
import dataclasses
import posixpath
import shlex
import time
from typing import Any

from . import evidence, receipt
from .env import exit_code
from .loop import VERIFIER_ROLE, CoreConfig, Trace, run_agent
from .oversight import ReviewPlan

VERIFY_SHARE = 0.4
VERIFY_MAX_S = 600.0
VERIFY_MIN_REMAINING_S = 180.0
MAX_EVIDENCE_CHARS = 8_000
TRACE_FILE = "verifier_trace.jsonl"

BRIEF = """Assess whether the current state of this container meets the task below.

Files created or changed while the task was being worked on (under {workdir}):
{files}
Do not open them until you have written down what a correct result must contain.

The task:
{task}"""
MAX_LISTED = 60
# With evidence on (see evidence): the choices the work made, without its reasons. N1 smoke v2: a verifier left to
# find the open choices itself settled the address base the same way the solver had and confirmed.
QUESTIONS = """

Choices the work made where the task does not dictate one (its reasons are not given). Settle each yourself from the \
task and its inputs, with a check whose outcome would differ between the alternatives:
{questions}"""

DEFECT = """[independent check: defect found; the finish did not take effect]
A separate check, made from the task alone in a copy of your current state, found:
{evidence}

It can be wrong. Decide for yourself: fix what it found, or, if you are sure it is mistaken, call finish again. \
There is no second check; your next finish ends the work."""
MODIFIED = """[independent check: void; the finish did not take effect]
A separate check, made from the task alone in a copy of your current state, changed these delivered files in its \
copy before concluding, so its conclusion is about its changed copy, not your state:
{files}
What it reported:
{evidence}

Treat this as a proposed repair, which can be wrong. Decide for yourself; your state is as you left it. There is no \
second check; your next finish ends the work."""
FINDINGS = ("defect_found", "no_defect_found", "undetermined")
CLOSE_RESERVE_S = 30.0  # of the check's own time, kept for removing the clone
FINGERPRINT_MAX_BYTES = (
    "20M"  # larger files are not fingerprinted (recorded as a count)
)


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
        evidence=False,
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


def _listing(paths: list[str]) -> str:
    if not paths:
        return "(none)"
    shown = "\n".join(paths[:MAX_LISTED])
    more = len(paths) - MAX_LISTED
    return shown + (f"\n(and {more} more)" if more > 0 else "")


def _questions(s: Any) -> str:
    rows = s.result.extras.get("evidence")
    return QUESTIONS.format(questions=evidence.open_questions(rows[-1])) if rows else ""


async def fingerprint(env: Any, workdir: str) -> dict[str, str]:
    """sha256 of every file under ``workdir`` (the receipt's skipped directories aside, files under
    FINGERPRINT_MAX_BYTES). Raises when the listing fails."""
    prune = " -o ".join(f"-name {shlex.quote(n)}" for n in receipt.SKIP)
    command = (
        f"cd {shlex.quote(workdir)} && find . -xdev \\( {prune} \\) -prune -o -type f "
        f"-size -{FINGERPRINT_MAX_BYTES} -exec sha256sum {{}} + 2>/dev/null; true"
    )
    result = await env.exec(command=command, cwd=None, env=None, timeout_sec=120)
    if exit_code(result) != 0:
        raise OSError("the delivered tree could not be fingerprinted")
    out = {}
    for line in str(getattr(result, "stdout", "") or "").splitlines():
        digest, _, path = line.partition("  ")
        if path:
            out[path] = digest
    return out


def changes(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    return {
        "modified": sorted(p for p in before if p in after and after[p] != before[p]),
        "deleted": sorted(p for p in before if p not in after),
        "created": sorted(p for p in after if p not in before),
    }


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


async def _review(
    s: Any, row: dict[str, Any], held: dict[str, Any], end: float
) -> None:
    produced = await receipt.changed(s.env, s.workdir, s.config.control_dir)
    row["produced_files"] = len(produced)
    held["before"] = await fingerprint(s.env, s.workdir)
    row["fingerprinted_files"] = len(held["before"])
    held["clone"] = clone = await s.clone(s.env)
    row["clone_ready_s"] = round(time.monotonic() - held["started"], 1)
    await _forget_the_solver(clone, s.config)
    held["result"] = await run_agent(
        env=clone,
        task=BRIEF.format(task=s.task, workdir=s.workdir, files=_listing(produced))
        + _questions(s),
        workdir=s.workdir,
        provider=_Labelled(s.provider, VERIFIER_ROLE),
        timeout_s=max(1.0, end - time.monotonic() - CLOSE_RESERVE_S),
        trace=Trace(s.trace.path.with_name(TRACE_FILE)),
        config=verifier_config(s.config),
    )
    clone_changes = changes(held["before"], await fingerprint(clone, s.workdir))
    original_changes = changes(held["before"], await fingerprint(s.env, s.workdir))
    row["clone_changes"] = clone_changes
    row["original_changed"] = original_changes["modified"] + original_changes["deleted"]


def _finding(row: dict[str, Any], result: Any) -> tuple[str | None, str]:
    args = result.extras.get("finish_args", {}) if result else {}
    finding = args.get("verdict") if result and result.status == "finished" else None
    evidence_text = str(args.get("evidence", ""))
    if len(evidence_text) > MAX_EVIDENCE_CHARS:
        evidence_text = evidence_text[:MAX_EVIDENCE_CHARS] + "\n[evidence truncated]"
    return finding, evidence_text


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
    held: dict[str, Any] = {"started": started, "clone": None, "result": None}
    try:
        await asyncio.wait_for(_review(s, row, held, started + budget), timeout=budget)
    except TimeoutError:
        row["reason"] = f"the check did not end within its {budget:.0f}s"
    except asyncio.CancelledError:
        row.update(status="cancelled", elapsed_s=round(time.monotonic() - started, 1))
        await _close(held, row)
        _record(s, row)
        raise
    except Exception as exc:
        row["reason"] = f"{type(exc).__name__}: {exc}"
    await _close(held, row)
    result = held["result"]
    finding, evidence_text = _finding(row, result)
    if (
        "reason" in row
    ):  # a finding cut short by the deadline or a failure has no standing
        finding = None
    clone_changes = row.get("clone_changes", {})
    voided = bool(clone_changes.get("modified") or clone_changes.get("deleted"))
    if finding and voided:
        status = "void_candidate_modified"
    elif finding and row.get("original_changed"):
        status = "stale_original_changed"
    else:
        status = finding or ("error" if "reason" in row else "no_finding")
    row.update(
        status=status,
        finding=finding,
        evidence=evidence_text,
        verifier_status=result.status if result else None,
        verifier_error=result.error if result else None,
        steps=result.steps if result else 0,
        elapsed_s=round(time.monotonic() - started, 1),
        usage=_usage(s.provider),
    )
    _record(s, row)
    if status == "defect_found":
        return DEFECT.format(evidence=evidence_text), False
    if status == "void_candidate_modified":
        files = clone_changes["modified"] + clone_changes["deleted"]
        return MODIFIED.format(
            files="\n".join(files[:MAX_LISTED]), evidence=evidence_text
        ), False
    return f"finished\n[independent check: {status}]", True


async def _close(held: dict[str, Any], row: dict[str, Any]) -> None:
    clone, held["clone"] = held.get("clone"), None
    if clone is None:
        return
    try:
        await asyncio.wait_for(clone.close(), timeout=CLOSE_RESERVE_S * 4)
    except Exception as exc:
        row["close_error"] = f"{type(exc).__name__}: {exc}"

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

Binding (Codex reviews of 15 Oct: a verifier that repaired its clone, including a 21 MiB file outside a size
filter, was accepted while the graded file stayed wrong; a failing fingerprint read as "unchanged"): the working
directory's manifest (binding.Manifest: every entry's type, permission bits, link target and content hash) is taken
from the original before cloning, from the clone after the review, and from the original again. Any entry
modified, deleted **or created** in the clone's working directory voids the finding: a created file can be the
missing deliverable itself, so the verifier keeps build and scratch output under /tmp. The solver is shown what the
check changed and what it reported, as a proposed repair, and the work continues. A bound entry that changed in the
original during the check makes the finding stale (the finish takes effect). If any manifest cannot be taken, the
finding is recorded as ``<finding>_unbound``; if the tree has unbound parts (pruned directories such as .git, mount
points), as ``<finding>_partial``. A defect it found still goes back to the solver in both cases. Nothing outside
the working directory is bound, and a change made and reverted before the closing manifest is not seen: the
binding compares states, it does not watch the review.

Boundary (Codex D5 reconciliation: a verifier wrote a repair, checked it, restored the original and confirmed,
and equal manifests at both ends hid it): the clone is requested read-only (clone.SCRATCH: the kernel holds the
committed filesystem read-only; /tmp and /var/tmp are writable volumes holding what the work left there), and
boundary.probe observes in the clone whether the working directory is actually held. Only then does the brief say
so; a clone where it is not held (a factory without the option, a working directory under scratch) gives a finding
labelled ``_writable``, an advisory review. The read-only boundary stops changes to the delivered files; it does
not make the review truthful: a check can still copy a file to scratch, repair the copy and report on the original.
boundary.scratch_copies records scratch files that share a delivered file's name (``same`` or ``diverging``), by
name only, as evidence for audit; it decides nothing.

Time (same reviews: clone set-up could take the solver's remainder, and a cancelled clone creation is shielded and
waited for): one absolute end, VERIFY_SHARE of what is left and at most VERIFY_MAX_S, holds listing, manifests,
clone, review and clean-up; the rest stays the solver's. The clone factory receives the work time that is left
(Clone.create bounds every host command by it). The review runs as a task: when its time is up it is cancelled and
given the clean-up reserve to unwind; whatever outlives the end (a shielded docker operation, a slow removal) is
handed to the run's end-of-run clean-up, which records its outcome, and the solver gets its time back. A check that
fails, runs out of time or is cancelled never holds the finish; every outcome is recorded. Skipped when less than
VERIFY_MIN_REMAINING_S is left.
"""

from __future__ import annotations

import asyncio
import dataclasses
import posixpath
import shlex
import time
from typing import Any

from . import binding, boundary, evidence, receipt
from .clone import SCRATCH
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
# Shown only when the probe found the boundary held (boundary.probe), so the brief never claims one that is not.
READ_ONLY_NOTE = """

In this copy everything outside {scratch} is read-only: the files above cannot be changed. Build and run anything \
that writes under /tmp."""
STARTED = ".check-started"  # in the verifier's own control directory: scratch files newer than it are the check's
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
A separate check, made from the task alone in a copy of your current state, made these changes in its copy \
of the working directory before concluding, so its conclusion is about its changed copy, not your state:
{files}
What it reported:
{evidence}

Treat this as a proposed repair, which can be wrong. Decide for yourself; your state is as you left it. There is no \
second check; your next finish ends the work."""
UNBOUND_NOTE = """
(This check's copy could not be fingerprinted, so it is not known whether its copy still matched your state.)"""
FINDINGS = ("defect_found", "no_defect_found", "undetermined")
# The check's own time is split: work (clone and review), then the closing manifests, then removing the clone.
CLEANUP_SHARE, CLEANUP_MAX_S = 0.25, 30.0
MANIFEST_SHARE, MANIFEST_MAX_S = 0.15, 60.0


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


async def _manifest(env: Any, s: Any, row: dict[str, Any], until: float) -> Any:
    """The delivered tree's manifest, or None (recorded) when it cannot be taken."""
    try:
        return await binding.manifest(
            env, s.workdir, timeout_s=max(1.0, until - time.monotonic())
        )
    except binding.BindingUnavailable as exc:
        row.setdefault("binding_unavailable", []).append(str(exc)[:300])
        return None


async def _review(
    s: Any,
    row: dict[str, Any],
    held: dict[str, Any],
    work_end: float,
    manifest_s: float,
) -> None:
    produced = await receipt.changed(s.env, s.workdir, s.config.control_dir)
    row["produced_files"] = len(produced)
    before = await _manifest(s.env, s, row, work_end)
    if before is not None:
        row.update(bound_entries=len(before.entries), unbound=before.unbound)
    held["clone"] = clone = await s.clone(
        s.env, timeout_s=max(1.0, work_end - time.monotonic()), read_only=True
    )
    row["clone_ready_s"] = round(time.monotonic() - held["started"], 1)
    await _forget_the_solver(clone, s.config)
    probed = await boundary.probe(clone, s.workdir, timeout_s=min(60.0, manifest_s))
    row["boundary"] = probed.pop("boundary")
    row["boundary_detail"] = probed
    marker = f"{verifier_config(s.config).control_dir}/{STARTED}"
    marked = await clone.exec(
        command=f"mkdir -p {shlex.quote(posixpath.dirname(marker))} && : > {shlex.quote(marker)}",
        cwd=None,
        env=None,
        timeout_sec=60,
    )
    note = (
        READ_ONLY_NOTE.format(scratch=" and ".join(SCRATCH))
        if row["boundary"] == "read_only"
        else ""
    )
    held["result"] = await run_agent(
        env=clone,
        task=BRIEF.format(task=s.task, workdir=s.workdir, files=_listing(produced))
        + note
        + _questions(s),
        workdir=s.workdir,
        provider=_Labelled(s.provider, VERIFIER_ROLE),
        timeout_s=max(1.0, work_end - time.monotonic() - manifest_s),
        trace=Trace(s.trace.path.with_name(TRACE_FILE)),
        config=verifier_config(s.config),
    )
    if before is None:
        return
    if exit_code(marked) == 0:
        row["scratch_copies"] = await boundary.scratch_copies(
            clone, before, SCRATCH, marker, timeout_s=min(60.0, manifest_s)
        )
    after = await _manifest(clone, s, row, work_end)
    now = await _manifest(s.env, s, row, work_end)
    if after is not None and now is not None:
        row["clone_changes"] = binding.changes(before, after)
        changed = binding.changes(before, now)
        row["original_changed"] = changed["modified"] + changed["deleted"]


def _finding(row: dict[str, Any], result: Any) -> tuple[str | None, str]:
    args = result.extras.get("finish_args", {}) if result else {}
    finding = args.get("verdict") if result and result.status == "finished" else None
    evidence_text = str(args.get("evidence", ""))
    if len(evidence_text) > MAX_EVIDENCE_CHARS:
        evidence_text = evidence_text[:MAX_EVIDENCE_CHARS] + "\n[evidence truncated]"
    return finding, evidence_text


def _hand_off(s: Any, label: str, task: asyncio.Future) -> None:
    """A clone operation that outlived the check's time: run-end cleanup owns it and records its outcome."""
    s.pending_cleanup.append((label, task))


async def _close(s: Any, held: dict[str, Any], row: dict[str, Any], end: float) -> None:
    clone, held["clone"] = held.get("clone"), None
    if clone is None:
        return
    closing = asyncio.ensure_future(clone.close())
    done, _ = await asyncio.wait({closing}, timeout=max(0.0, end - time.monotonic()))
    if not done:
        _hand_off(s, "verifier clone close", closing)
        row["close_error"] = (
            "clone removal outlived the check's time; handed to run-end cleanup"
        )
    elif closing.exception() is not None:
        row["close_error"] = (
            f"{type(closing.exception()).__name__}: {closing.exception()}"
        )


def _status(row: dict[str, Any], finding: str | None) -> str:
    if (
        "reason" in row or not finding
    ):  # a finding cut short by the deadline or a failure has no standing
        return "error" if "reason" in row else "no_finding"
    writable = "_writable" if row.get("boundary") != "read_only" else ""
    if row.get("binding_unavailable") or "clone_changes" not in row:
        return f"{finding}_unbound{writable}"
    changes = row["clone_changes"]
    if changes["modified"] or changes["deleted"] or changes["created"]:
        return "void_candidate_modified"
    if row.get("original_changed"):
        return "stale_original_changed"
    return finding + ("_partial" if row.get("unbound") else "") + writable


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
    end = started + budget
    work_end = end - min(CLEANUP_MAX_S, CLEANUP_SHARE * budget)
    manifest_s = min(MANIFEST_MAX_S, MANIFEST_SHARE * budget)
    row: dict[str, Any] = {"budget_s": round(budget, 1)}
    held: dict[str, Any] = {"started": started, "clone": None, "result": None}
    review = asyncio.ensure_future(_review(s, row, held, work_end, manifest_s))
    try:
        done, _ = await asyncio.wait({review}, timeout=max(0.0, work_end - started))
        if not done:
            review.cancel()
            row["reason"] = (
                f"the check did not end within its {work_end - started:.0f}s"
            )
            done, _ = await asyncio.wait(
                {review}, timeout=max(0.0, end - time.monotonic())
            )
            if not done:
                _hand_off(s, "verifier review", review)
                row["cleanup"] = (
                    "the cancelled review outlived the check's time; handed to run-end cleanup"
                )
        elif review.exception() is not None:
            exc = review.exception()
            row["reason"] = f"{type(exc).__name__}: {exc}"
    except asyncio.CancelledError:
        review.cancel()
        _hand_off(s, "verifier review", review)
        if held.get("clone") is not None:
            _hand_off(
                s, "verifier clone close", asyncio.ensure_future(held["clone"].close())
            )
        row.update(status="cancelled", elapsed_s=round(time.monotonic() - started, 1))
        _record(s, row)
        raise
    await _close(s, held, row, end)
    result = held["result"]
    finding, evidence_text = _finding(row, result)
    status = _status(row, finding)
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
    if finding == "defect_found" and status.startswith("defect_found"):
        note = UNBOUND_NOTE if status.endswith("_unbound") else ""
        return DEFECT.format(evidence=evidence_text) + note, False
    if status == "void_candidate_modified":
        changed = row["clone_changes"]
        files = [
            f"{kind}: {path}"
            for kind in ("modified", "deleted", "created")
            for path in changed[kind]
        ]
        return MODIFIED.format(
            files="\n".join(files[:MAX_LISTED]), evidence=evidence_text
        ), False
    return f"finished\n[independent check: {status}]", True

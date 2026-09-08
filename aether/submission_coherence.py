"""Mechanical coherence gate for Solver submission turns.

This module never judges task semantics. It only ensures that a submission is
not the hidden future turn after a mutation, failed action, repeat block,
protocol-only step, or unchanged prior submission.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ledger import ExecutionLedger, Receipt


@dataclass(frozen=True)
class SubmissionCoherenceDecision:
    allowed: bool
    reason_code: str = ""
    detail: str = ""
    latest_progress_receipt_id: str = ""
    latest_progress_classification: str = ""
    progress_signals: tuple[str, ...] = ()
    prior_submission_receipt_id: str = ""

    def as_payload(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "latest_progress_receipt_id": self.latest_progress_receipt_id,
            "latest_progress_classification": self.latest_progress_classification,
            "progress_signals": list(self.progress_signals),
            "prior_submission_receipt_id": self.prior_submission_receipt_id,
        }


_PROTOCOL_FAILURE_KINDS = frozenset({"solver_parse_error", "turn_validation"})
_PROTOCOL_RECOVERY_KINDS = frozenset({"solver_protocol_correction_result"})
_ALLOWED_OBSERVATION_SIGNALS = frozenset({
    "new_evidence",
    "verification",
    "requirement_evidence",
})
_SUBMISSION_RECOVERY_MESSAGES = {
    "submission_claim_missing": (
        "Submission is currently forbidden because the PCR completion claim was empty. "
        "A later submit turn must state one non-empty external claim."
    ),
    "submission_evidence_missing": (
        "Submission is currently forbidden because no visible evidence alias was cited. "
        "Obtain or select current same-run evidence before submitting."
    ),
    "submission_evidence_reference_invalid": (
        "Submission is currently forbidden because an evidence reference was invalid. "
        "Use only non-empty evidence aliases exactly as exposed in the current context."
    ),
    "duplicate_evidence_reference": (
        "Submission is currently forbidden because the same evidence alias was cited more than once. "
        "Cite each current-context evidence alias at most once."
    ),
    "submission_context_identity_mismatch": (
        "Submission is currently forbidden because the context and ledger task-run identities differ."
    ),
    "submission_evidence_index_missing": (
        "Submission is currently forbidden because no usable PCR evidence index was available."
    ),
    "evidence_reference_not_current_context": (
        "Submission is currently forbidden because a cited evidence alias was not present in the exact "
        "context packet used for this decision."
    ),
    "evidence_receipt_missing": (
        "Submission is currently forbidden because a cited alias no longer resolves to a canonical receipt."
    ),
    "evidence_alias_binding_mismatch": (
        "Submission is currently forbidden because an evidence alias does not match its receipt binding."
    ),
    "future_evidence_reference": (
        "Submission is currently forbidden because cited evidence did not exist before this turn."
    ),
    "evidence_lineage_mismatch": (
        "Submission is currently forbidden because cited evidence belongs to a different task, run, or workspace."
    ),
    "evidence_type_binding_mismatch": (
        "Submission is currently forbidden because an evidence alias misstates the canonical receipt type."
    ),
    "unobserved_state_change": (
        "Submission is currently forbidden. The next Solver turn must be kind='act' and "
        "perform exactly one observation-producing action that inspects the current state or "
        "public behavior affected by the latest mutation. Do not submit again until that new "
        "observation records evidence or verification."
    ),
    "unchanged_resubmission": (
        "Submission is currently forbidden because no new evidence followed the previous "
        "submission. The next Solver turn must be kind='act' and obtain new current-state "
        "evidence or resolve the outstanding completion findings before submitting again."
    ),
    "failed_action_without_recovery": (
        "Submission is currently forbidden. The next Solver turn must be kind='act' and "
        "perform one recovery or observation action that establishes what failed or confirms "
        "a recovered state before submitting."
    ),
    "mixed_action_result_without_recovery": (
        "Submission is currently forbidden. The next Solver turn must be kind='act' and "
        "resolve or observe the failed part of the mixed result before submitting."
    ),
    "equivalent_repeat_blocked": (
        "Submission is currently forbidden. The next Solver turn must be kind='act' and "
        "change target, strategy, or evidence source rather than repeating the blocked action."
    ),
    "no_observed_action_result": (
        "Submission is currently forbidden. The next Solver turn must be kind='act' and "
        "produce one direct observed result before submitting."
    ),
    "no_relevant_observation_before_submit": (
        "Submission is currently forbidden. The next Solver turn must be kind='act' and "
        "obtain new evidence, requirement evidence, or verification before submitting."
    ),
    "protocol_or_turn_failure_without_observation": (
        "Submission is currently forbidden. The next accepted Solver turn must restore the "
        "protocol and produce an observed action result before submitting."
    ),
}


def submission_recovery_directive(reason_code: str, detail: str = "") -> dict[str, Any]:
    """Compile a coherence failure into one dominant, task-agnostic recovery rule.

    The directive never chooses the concrete tool, target, or task action. It only
    states the control-plane condition that must be satisfied before submission can
    be considered again.
    """
    reason = str(reason_code or "").strip()
    message = _SUBMISSION_RECOVERY_MESSAGES.get(reason)
    if not message:
        message = (
            "Submission is currently forbidden. The next Solver turn must be kind='act' "
            "and create a new observed evidence boundary that resolves the stated blocker "
            "before submitting again."
        )
    return {
        "source": "submission_coherence",
        "submission_allowed": False,
        "reason_code": reason,
        "detail": str(detail or "").strip(),
        "required_next_turn_kind": "act",
        "forbidden_next_turn_kind": "submit_outcome",
        "message": message,
        "clears_only_after": (
            "A later accepted action produces new evidence, requirement evidence, or "
            "verification sufficient for the mechanical coherence gate."
        ),
        "task_action_owner": "solver",
    }


# Mechanical coherence failures that describe uncertainty about current task state,
# rather than a malformed/duplicate submission protocol.  PCR production may still
# activate independent verification for these states: the blocker remains
# authoritative and prevents terminal success until currentness is established.
_INDEPENDENT_REVIEWABLE_COHERENCE_REASONS = frozenset({
    "unobserved_state_change",
    "failed_action_without_recovery",
    "mixed_action_result_without_recovery",
    "no_observed_action_result",
    "no_relevant_observation_before_submit",
})


def coherence_block_allows_independent_review(
    decision: SubmissionCoherenceDecision,
) -> bool:
    """True only for factual current-state uncertainty, never protocol invalidity.

    This does not choose a task action or relax completion.  It only separates
    independent inspection activation from Solver-evidence admission.
    """
    return (
        not decision.allowed
        and decision.reason_code in _INDEPENDENT_REVIEWABLE_COHERENCE_REASONS
    )


_BLOCKED_PROGRESS = {
    "state_changed": (
        "unobserved_state_change",
        "The latest Solver action changed task state and no later observation has inspected that mutation.",
    ),
    "equivalent_repeat_blocked": (
        "equivalent_repeat_blocked",
        "The latest Solver action was mechanically blocked as an unchanged repeat and produced no new evidence.",
    ),
    "unsuccessful_result_no_state_change": (
        "failed_action_without_recovery",
        "The latest Solver action failed and no later successful observation established recovery.",
    ),
    "mixed_results_no_state_change": (
        "mixed_action_result_without_recovery",
        "The latest Solver action produced mixed success/failure and no later observation resolved the failure.",
    ),
    "no_direct_result": (
        "no_observed_action_result",
        "The latest Solver decision produced no direct observed action result.",
    ),
}


def _indexed_receipts(ledger: ExecutionLedger) -> list[tuple[int, Receipt]]:
    return list(enumerate(ledger.all_receipts()))


def evaluate_submission_coherence(
    ledger: ExecutionLedger,
    *,
    current_step: int,
) -> SubmissionCoherenceDecision:
    """Return whether the current submit may open checks and Verifier work."""
    rows = _indexed_receipts(ledger)
    latest_progress: tuple[int, Receipt] | None = None
    latest_protocol_failure: tuple[int, Receipt] | None = None
    latest_protocol_recovery: tuple[int, Receipt] | None = None
    prior_submission: tuple[int, Receipt] | None = None

    for index, receipt in rows:
        if receipt.kind == "solver_progress_assessment":
            latest_progress = (index, receipt)
        if receipt.kind in _PROTOCOL_FAILURE_KINDS and not receipt.success:
            latest_protocol_failure = (index, receipt)
        if receipt.kind in _PROTOCOL_RECOVERY_KINDS and receipt.success:
            latest_protocol_recovery = (index, receipt)
        # Only an admitted, evidence-bound completion claim establishes the
        # previous-submission boundary. A raw submit_outcome accounting event
        # can precede PCR evidence-binding validation; malformed/unknown aliases
        # are rejected before ``primary_submission_claim`` is recorded. Treating
        # those rejected attempts as prior submissions deadlocks a later
        # protocol-correct retry against the same still-current observation.
        # Bounded malformed-submit protection remains owned separately by the
        # kernel's submit-without-evidence stalemate counter.
        if (
            receipt.kind == "primary_submission_claim"
            and receipt.step < current_step
            and receipt.success
        ):
            prior_submission = (index, receipt)

    progress_index = latest_progress[0] if latest_progress is not None else -1
    recovery_index = latest_protocol_recovery[0] if latest_protocol_recovery is not None else -1
    if latest_protocol_failure is not None:
        failure_index, failure = latest_protocol_failure
        if failure_index > max(progress_index, recovery_index):
            return SubmissionCoherenceDecision(
                False,
                "protocol_or_turn_failure_without_observation",
                "A Solver protocol or turn-validation failure occurred after the latest observed action boundary.",
                latest_progress_receipt_id=(
                    latest_progress[1].receipt_id if latest_progress is not None else ""
                ),
                prior_submission_receipt_id=(
                    prior_submission[1].receipt_id if prior_submission is not None else ""
                ),
            )

    if latest_progress is not None:
        _index, progress = latest_progress
        payload = progress.payload or {}
        classification = str(payload.get("classification", "")).strip()
        signals = tuple(
            str(item).strip()
            for item in payload.get("progress_signals", ())
            if str(item).strip()
        )
        if classification == "state_changed":
            state_change_verified = bool(
                {"verification", "requirement_evidence"}.intersection(signals)
            )
            if not state_change_verified:
                reason_code, detail = _BLOCKED_PROGRESS[classification]
                return SubmissionCoherenceDecision(
                    False,
                    reason_code,
                    detail,
                    latest_progress_receipt_id=progress.receipt_id,
                    latest_progress_classification=classification,
                    progress_signals=signals,
                    prior_submission_receipt_id=(
                        prior_submission[1].receipt_id if prior_submission is not None else ""
                    ),
                )
        elif classification in _BLOCKED_PROGRESS:
            reason_code, detail = _BLOCKED_PROGRESS[classification]
            return SubmissionCoherenceDecision(
                False,
                reason_code,
                detail,
                latest_progress_receipt_id=progress.receipt_id,
                latest_progress_classification=classification,
                progress_signals=signals,
                prior_submission_receipt_id=(
                    prior_submission[1].receipt_id if prior_submission is not None else ""
                ),
            )
        if not _ALLOWED_OBSERVATION_SIGNALS.intersection(signals):
            return SubmissionCoherenceDecision(
                False,
                "no_relevant_observation_before_submit",
                "The latest action boundary did not record new evidence or verification.",
                latest_progress_receipt_id=progress.receipt_id,
                latest_progress_classification=classification,
                progress_signals=signals,
                prior_submission_receipt_id=(
                    prior_submission[1].receipt_id if prior_submission is not None else ""
                ),
            )

    if prior_submission is not None and prior_submission[0] > progress_index:
        return SubmissionCoherenceDecision(
            False,
            "unchanged_resubmission",
            "A previous submission occurred after the latest observed action boundary; no new evidence intervened.",
            latest_progress_receipt_id=(
                latest_progress[1].receipt_id if latest_progress is not None else ""
            ),
            latest_progress_classification=(
                str((latest_progress[1].payload or {}).get("classification", ""))
                if latest_progress is not None else ""
            ),
            progress_signals=(
                tuple(str(item) for item in (latest_progress[1].payload or {}).get("progress_signals", ()))
                if latest_progress is not None else ()
            ),
            prior_submission_receipt_id=prior_submission[1].receipt_id,
        )

    return SubmissionCoherenceDecision(
        True,
        latest_progress_receipt_id=(
            latest_progress[1].receipt_id if latest_progress is not None else ""
        ),
        latest_progress_classification=(
            str((latest_progress[1].payload or {}).get("classification", ""))
            if latest_progress is not None else ""
        ),
        progress_signals=(
            tuple(str(item) for item in (latest_progress[1].payload or {}).get("progress_signals", ()))
            if latest_progress is not None else ()
        ),
        prior_submission_receipt_id=(
            prior_submission[1].receipt_id if prior_submission is not None else ""
        ),
    )


def record_submission_coherence_block(
    ledger: ExecutionLedger,
    *,
    step: int,
    decision: SubmissionCoherenceDecision,
    blocked_round: int,
    verifier_skipped: bool = True,
) -> None:
    payload = decision.as_payload() | {"blocked_round": blocked_round}
    ledger.record(Receipt(
        receipt_id=f"step-{step}:submission_coherence_blocked",
        step=step,
        kind="submission_coherence_blocked",
        success=False,
        summary=f"submission blocked: {decision.reason_code}",
        failure_class=decision.reason_code,
        payload=payload,
    ))
    if verifier_skipped:
        ledger.record(Receipt(
            receipt_id=f"step-{step}:model_verifier_skipped:submission_coherence",
            step=step,
            kind="model_verifier_skipped",
            success=True,
            summary="model verifier skipped: submission lacked a coherent observed-evidence boundary",
            payload={
                "reason": "submission_coherence_blocked",
                "coherence": payload,
            },
        ))

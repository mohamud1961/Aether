from __future__ import annotations

from aether.ledger import ExecutionLedger, Receipt
from aether.submission_coherence import evaluate_submission_coherence


def _progress(
    receipt_id: str,
    *,
    step: int,
    action_kind: str,
    classification: str,
    signals: list[str],
    success_count: int,
    failure_count: int,
    state_change_count: int = 0,
) -> Receipt:
    return Receipt(
        receipt_id=receipt_id,
        step=step,
        kind="solver_progress_assessment",
        success=True,
        summary=f"mechanical action-result summary: {classification}",
        payload={
            "action_kind": action_kind,
            "classification": classification,
            "progress_signals": signals,
            "successful_result_count": success_count,
            "failed_result_count": failure_count,
            "state_change_count": state_change_count,
            "no_relevant_progress": signals == ["no_relevant_progress"],
        },
    )


def test_rejected_completion_record_update_does_not_erase_prior_observation() -> None:
    ledger = ExecutionLedger()
    ledger.record(_progress(
        "step-1:observed",
        step=1,
        action_kind="run_command",
        classification="successful_result_no_state_change",
        signals=["new_evidence", "verification"],
        success_count=1,
        failure_count=0,
    ))
    ledger.record(_progress(
        "step-2:record-rejected",
        step=2,
        action_kind="update_completion_record",
        classification="mixed_results_no_state_change",
        signals=["failure_observed"],
        success_count=3,
        failure_count=1,
    ))

    decision = evaluate_submission_coherence(ledger, current_step=3)

    assert decision.allowed is True
    assert decision.latest_progress_receipt_id == "step-2:record-rejected"


def test_failed_task_action_still_blocks_after_prior_observation() -> None:
    ledger = ExecutionLedger()
    ledger.record(_progress(
        "step-1:observed",
        step=1,
        action_kind="run_command",
        classification="successful_result_no_state_change",
        signals=["new_evidence", "verification"],
        success_count=1,
        failure_count=0,
    ))
    ledger.record(_progress(
        "step-2:write-failed",
        step=2,
        action_kind="write_file",
        classification="mixed_results_no_state_change",
        signals=["failure_observed"],
        success_count=3,
        failure_count=1,
    ))

    decision = evaluate_submission_coherence(ledger, current_step=3)

    assert decision.allowed is False
    assert decision.reason_code == "mixed_action_result_without_recovery"


def test_rejected_completion_record_without_prior_observation_still_blocks() -> None:
    ledger = ExecutionLedger()
    ledger.record(_progress(
        "step-1:record-rejected",
        step=1,
        action_kind="update_completion_record",
        classification="mixed_results_no_state_change",
        signals=["failure_observed"],
        success_count=3,
        failure_count=1,
    ))

    decision = evaluate_submission_coherence(ledger, current_step=2)

    assert decision.allowed is False
    assert decision.reason_code == "mixed_action_result_without_recovery"

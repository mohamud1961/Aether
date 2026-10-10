from __future__ import annotations

from aether.failed_observation_disposition import (
    CONTROL,
    CURRENT_CANDIDATE_V1,
    current_candidate_failed_observations,
)
from aether.ledger import ExecutionLedger, Receipt


def _record_progress(
    ledger: ExecutionLedger,
    *,
    step: int,
    action_id: str,
    result_ids: list[str],
) -> None:
    ledger.record(Receipt(
        receipt_id=f"step-{step}:{action_id}:solver_progress_assessment",
        step=step,
        kind="solver_progress_assessment",
        success=True,
        summary="mechanical action-result summary",
        payload={
            "action_id": action_id,
            "result_receipt_ids": result_ids,
        },
    ))


def test_current_candidate_failure_persists_across_reads_and_uncertain_boundaries_then_retires_after_confirmed_mutation() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-0:write:result",
        step=0,
        kind="write_file",
        success=True,
        summary="wrote candidate",
        state_change=True,
    ))
    _record_progress(ledger, step=0, action_id="write", result_ids=["step-0:write:result"])

    ledger.record(Receipt(
        receipt_id="step-1:test:result",
        step=1,
        kind="run_command",
        success=False,
        summary="contract check failed",
        failure_class="command_failed",
        payload={"stderr_handle": "stderr:failure"},
    ))
    _record_progress(ledger, step=1, action_id="test", result_ids=["step-1:test:result"])

    rows = current_candidate_failed_observations(
        ledger, mode=CURRENT_CANDIDATE_V1,
    )
    assert len(rows) == 1
    assert rows[0]["source_receipt_id"] == "step-1:test:result"
    assert rows[0]["candidate_generation_anchor_receipt_id"] == "step-0:write:result"
    assert rows[0]["kind"] == "run_command"
    assert rows[0]["stderr_handle"] == "stderr:failure"
    assert rows[0]["currentness"] == "current_candidate"

    ledger.record(Receipt(
        receipt_id="step-2:inspect:result",
        step=2,
        kind="read_file",
        success=True,
        summary="read candidate",
    ))
    _record_progress(ledger, step=2, action_id="inspect", result_ids=["step-2:inspect:result"])
    assert len(current_candidate_failed_observations(
        ledger, mode=CURRENT_CANDIDATE_V1,
    )) == 1

    # Generic shell observations may be marked task-world-uncertain even when
    # they are read-only. They must not retire a known failed check.
    ledger.record(Receipt(
        receipt_id="step-3:opaque-inspect:result",
        step=3,
        kind="run_command",
        success=True,
        summary="opaque diagnostic completed",
        payload={
            "state_delta": {"mutation_detection_status": "coarse"},
        },
    ))
    _record_progress(
        ledger,
        step=3,
        action_id="opaque-inspect",
        result_ids=["step-3:opaque-inspect:result"],
    )
    assert len(current_candidate_failed_observations(
        ledger, mode=CURRENT_CANDIDATE_V1,
    )) == 1

    ledger.record(Receipt(
        receipt_id="step-4:repair:result",
        step=4,
        kind="write_file",
        success=True,
        summary="repaired candidate",
        state_change=True,
    ))
    _record_progress(ledger, step=4, action_id="repair", result_ids=["step-4:repair:result"])
    assert current_candidate_failed_observations(
        ledger, mode=CURRENT_CANDIDATE_V1,
    ) == ()


def test_failed_mutating_result_belongs_to_new_current_candidate_generation() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-0:mutating-test:result",
        step=0,
        kind="run_command",
        success=False,
        summary="mutation occurred but validation failed",
        failure_class="test_failure",
        state_change=True,
    ))
    _record_progress(
        ledger,
        step=0,
        action_id="mutating-test",
        result_ids=["step-0:mutating-test:result"],
    )
    rows = current_candidate_failed_observations(
        ledger, mode=CURRENT_CANDIDATE_V1,
    )
    assert len(rows) == 1
    assert rows[0]["source_receipt_id"] == "step-0:mutating-test:result"
    assert rows[0]["candidate_generation_anchor_receipt_id"] == "step-0:mutating-test:result"


def test_projection_is_default_off_and_ignores_control_plane_failures() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-0:invalid",
        step=0,
        kind="action_validation",
        success=False,
        summary="invalid action",
        failure_class="action_validation",
    ))
    _record_progress(ledger, step=0, action_id="invalid", result_ids=["step-0:invalid"])
    assert current_candidate_failed_observations(ledger, mode=CONTROL) == ()
    assert current_candidate_failed_observations(
        ledger, mode=CURRENT_CANDIDATE_V1,
    ) == ()

from __future__ import annotations

from aether.ledger import ExecutionLedger, Receipt
from aether.runtime_ir import ActionRequest
from aether.solver_progress import build_progress_receipt
from aether.submission_coherence import evaluate_submission_coherence


def _action() -> ActionRequest:
    return ActionRequest(
        action_id="pcr-command",
        kind="run_command",
        capability_id="shell",
        arguments={"command": "touch /git/server/example"},
        intent="",
        expected_observation="",
        if_fail_next="",
    )


def test_successful_coarse_task_world_boundary_is_not_reported_as_observed_no_change() -> None:
    ledger = ExecutionLedger()
    action = _action()
    result = Receipt(
        receipt_id="step-1:pcr-command:cmd",
        step=1,
        kind="run_command",
        success=True,
        summary="command exit=0",
        state_change=False,
        payload={
            "state_delta": {
                "mutation_detection_status": "coarse",
                "workspace_mutation_detection_status": "complete",
                "mutation_detection_scope": "opaque_run_command_task_world",
                "created_paths": [],
                "removed_paths": [],
                "content_changed_paths": [],
                "metadata_changed_paths": [],
            },
        },
    )
    progress = build_progress_receipt(
        action,
        step=1,
        step_receipts=(result,),
        ledger=ledger,
    )
    assert progress.payload["classification"] == "successful_result_task_world_mutation_uncertain"
    assert progress.payload["state_change_count"] == 0
    assert progress.payload["task_world_mutation_uncertain_count"] == 1
    assert progress.payload["task_world_mutation_observability"] == "uncertain"
    assert progress.payload["progress_signals"] == [
        "task_world_mutation_uncertain",
        "new_evidence",
    ]


def test_coarse_projection_does_not_reopen_freshness_or_block_successful_observation_submission() -> None:
    ledger = ExecutionLedger()
    action = _action()
    ledger.record(Receipt(
        receipt_id="step-1:pcr-command:cmd",
        step=1,
        kind="run_command",
        success=True,
        summary="command exit=0",
        state_change=False,
        payload={
            "state_delta": {
                "mutation_detection_status": "coarse",
                "workspace_mutation_detection_status": "complete",
                "mutation_detection_scope": "opaque_run_command_task_world",
            },
        },
    ))
    progress = build_progress_receipt(
        action,
        step=1,
        step_receipts=ledger.all_receipts(),
        ledger=ledger,
    )
    ledger.record(progress)
    decision = evaluate_submission_coherence(ledger, current_step=2)
    assert decision.allowed is True
    assert decision.latest_progress_classification == "successful_result_task_world_mutation_uncertain"


def test_rejected_submit_attempt_does_not_poison_corrected_submission_boundary() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-5:progress",
        step=5,
        kind="solver_progress_assessment",
        success=True,
        summary="fresh current evidence",
        payload={
            "classification": "successful_result_task_world_mutation_uncertain",
            "progress_signals": ["new_evidence"],
        },
    ))

    # A submit attempt is accounted before PCR evidence binding is validated.
    # If the alias is malformed, no primary_submission_claim is admitted.
    for step in (6, 7):
        ledger.record(Receipt(
            receipt_id=f"step-{step}:solver_submission_turn:{step - 5}",
            step=step,
            kind="runtime_accounting",
            success=True,
            summary="solver_submission_turns: submit_outcome",
            payload={"counter": "solver_submission_turns", "event": "submit_outcome"},
        ))
        ledger.record(Receipt(
            receipt_id=f"step-{step}:submission_coherence_blocked",
            step=step,
            kind="submission_coherence_blocked",
            success=False,
            summary="submission blocked: evidence_reference_not_current_context",
            failure_class="evidence_reference_not_current_context",
        ))

    corrected = evaluate_submission_coherence(ledger, current_step=8)
    assert corrected.allowed is True
    assert corrected.prior_submission_receipt_id == ""

    # Once a coherent, evidence-bound claim is admitted, a second submission
    # without a new observation is correctly blocked as unchanged.
    ledger.record(Receipt(
        receipt_id="step-8:primary_submission_claim:claim:accepted",
        step=8,
        kind="primary_submission_claim",
        success=True,
        summary="accepted completion claim",
    ))
    repeated = evaluate_submission_coherence(ledger, current_step=9)
    assert repeated.allowed is False
    assert repeated.reason_code == "unchanged_resubmission"
    assert repeated.prior_submission_receipt_id == "step-8:primary_submission_claim:claim:accepted"


def test_exact_workspace_mutation_keeps_existing_state_changed_semantics() -> None:
    progress = build_progress_receipt(
        _action(),
        step=1,
        step_receipts=(Receipt(
            receipt_id="write",
            step=1,
            kind="run_command",
            success=True,
            summary="changed workspace",
            state_change=True,
            payload={
                "state_delta": {
                    "mutation_detection_status": "coarse",
                    "workspace_mutation_detection_status": "complete",
                },
            },
        ),),
        ledger=ExecutionLedger(),
    )
    assert progress.payload["classification"] == "state_changed"
    assert progress.payload["task_world_mutation_observability"] == "observed_change"
    assert progress.payload["progress_signals"] == [
        "state_change",
        "task_world_mutation_uncertain",
        "new_evidence",
    ]

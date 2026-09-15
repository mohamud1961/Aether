from __future__ import annotations

from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_repeat import (
    evaluate_persistent_repeat,
    record_repeat_observation,
)
from aether.runtime_ir import ActionRequest
from aether.solver_progress import build_progress_receipt


def _ledger() -> ExecutionLedger:
    ledger = ExecutionLedger()
    ledger.install_runtime_identity({
        "task_id": "async-probe-test",
        "run_id": "run-1",
        "primary_agent_id": "primary-1",
        "workspace_id": "/app",
        "environment_id": "env-1",
        "budgets": {"max_kernel_steps": 12},
    })
    ledger.record(Receipt(
        receipt_id="step-0:start:process_launch",
        step=0,
        kind="process_launch",
        success=True,
        summary="registered finite background job",
        state_change=True,
        payload={
            "process_id": "job-1",
            "job_id": "job-1",
            "service_name": "finite",
            "process_generation": "gen-1",
            "live": True,
            "launch_mode": "background_job",
        },
    ))
    return ledger


def _action() -> ActionRequest:
    return ActionRequest(
        action_id="probe",
        kind="probe_job",
        capability_id="managed_process",
        arguments={"target": "job-1"},
        intent="observe the registered finite job",
        expected_observation="exact lifecycle state",
        if_fail_next="inspect the launch receipt",
    )


def _execute_probe(
    ledger: ExecutionLedger,
    action: ActionRequest,
    *,
    step: int,
    status: str,
    completed: bool,
    exit_code: int | None,
):
    decision = evaluate_persistent_repeat(action, ledger, step=step)
    receipt = Receipt(
        receipt_id=f"step-{step}:probe:job_probe",
        step=step,
        kind="job_probe",
        success=True,
        summary=f"probe job job-1: {status}",
        state_change=False,
        payload={
            "target": "job-1",
            "job_id": "job-1",
            "process_id": "job-1",
            "job_status": status,
            "completed": completed,
            "job_succeeded": (exit_code == 0) if completed else None,
            "exit_code": exit_code,
            "detail": status,
            "process_generation": "gen-1",
            "process_generation_verified": True,
            "lifecycle_authority": "host_process_handle",
            "pid": 123,
            "state_delta": {"mutation_detection_status": "complete"},
        },
    )
    ledger.record(receipt)
    observation = record_repeat_observation(
        action,
        decision,
        step=step,
        step_receipts=[receipt],
        ledger=ledger,
    )
    ledger.record(observation)
    progress = build_progress_receipt(
        action,
        step=step,
        step_receipts=[receipt, observation],
        ledger=ledger,
    )
    ledger.record(progress)
    return decision, observation, progress


def test_running_job_can_be_reobserved_without_manufacturing_progress() -> None:
    ledger = _ledger()
    action = _action()

    first, first_obs, first_progress = _execute_probe(
        ledger, action, step=1, status="running", completed=False, exit_code=None,
    )
    assert first.consequence == "allow"
    assert first_obs.payload["temporal_equivalent_repeat"] is False
    assert "new_evidence" in first_progress.payload["progress_signals"]
    assert "verification" in first_progress.payload["progress_signals"]

    second, second_obs, second_progress = _execute_probe(
        ledger, action, step=2, status="running", completed=False, exit_code=None,
    )
    assert second.consequence == "allow_temporal_observation"
    assert second_obs.payload["temporal_equivalent_repeat"] is True
    assert second_progress.payload["progress_signals"] == ["no_relevant_progress"]
    assert second_progress.payload["new_evidence_count"] == 0
    assert second_progress.payload["verification_count"] == 0
    assert second_progress.payload["no_relevant_progress"] is True

    third = evaluate_persistent_repeat(action, ledger, step=3)
    assert third.consequence == "allow_temporal_observation"
    assert third.issue_permit is False


def test_running_to_completed_transition_becomes_fresh_evidence() -> None:
    ledger = _ledger()
    action = _action()
    _execute_probe(ledger, action, step=1, status="running", completed=False, exit_code=None)
    _execute_probe(ledger, action, step=2, status="running", completed=False, exit_code=None)

    decision, observation, progress = _execute_probe(
        ledger, action, step=3, status="completed", completed=True, exit_code=0,
    )
    assert decision.consequence == "allow_temporal_observation"
    assert observation.payload["temporal_equivalent_repeat"] is False
    assert "new_evidence" in progress.payload["progress_signals"]
    assert "verification" in progress.payload["progress_signals"]
    assert progress.payload["new_evidence_count"] == 1
    assert progress.payload["verification_count"] == 1


def test_terminal_job_repeat_remains_bounded() -> None:
    ledger = _ledger()
    action = _action()
    _execute_probe(ledger, action, step=1, status="running", completed=False, exit_code=None)
    _execute_probe(ledger, action, step=2, status="running", completed=False, exit_code=None)
    _execute_probe(ledger, action, step=3, status="completed", completed=True, exit_code=0)

    fourth, _, _ = _execute_probe(
        ledger, action, step=4, status="completed", completed=True, exit_code=0,
    )
    assert fourth.consequence == "allow"

    blocked = evaluate_persistent_repeat(action, ledger, step=5)
    assert blocked.consequence == "block"
    assert blocked.issue_permit is True

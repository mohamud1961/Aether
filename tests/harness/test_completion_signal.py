from __future__ import annotations

from aether.completion_signal import completion_signal_context
from aether.ledger import ExecutionLedger, Receipt


def _record_latest_command(
    ledger: ExecutionLedger,
    *,
    step: int,
    command: str,
    success: bool = True,
    eligible: bool | None = None,
    risk: str = "",
) -> None:
    receipt_id = f"step-{step}:cmd:cmd"
    payload = {"command": command, "exit_code": 0 if success else 1}
    if eligible is not None:
        payload["completion_evidence_eligible"] = eligible
    if risk:
        payload["verification_integrity_risk"] = risk
    ledger.record(Receipt(
        receipt_id=receipt_id,
        step=step,
        kind="run_command",
        success=success,
        summary=f"command exit={0 if success else 1}: {command}",
        payload=payload,
    ))
    ledger.record(Receipt(
        receipt_id=f"step-{step}:cmd:primary_action_result_index",
        step=step,
        kind="primary_action_result_index",
        success=True,
        summary="indexed primary action result",
        payload={
            "action_id": "cmd",
            "action_kind": "run_command",
            "outcome_receipt_ids": [receipt_id],
        },
    ))


def _record_latest_write(ledger: ExecutionLedger, *, step: int) -> None:
    receipt_id = f"step-{step}:write:write"
    ledger.record(Receipt(
        receipt_id=receipt_id,
        step=step,
        kind="write_file",
        success=True,
        summary="wrote x.py",
        state_change=True,
        payload={"path": "x.py"},
    ))
    ledger.record(Receipt(
        receipt_id=f"step-{step}:write:primary_action_result_index",
        step=step,
        kind="primary_action_result_index",
        success=True,
        summary="indexed primary action result",
        payload={
            "action_id": "write",
            "action_kind": "write_file",
            "outcome_receipt_ids": [receipt_id],
        },
    ))


def test_control_never_emits_signal() -> None:
    ledger = ExecutionLedger()
    _record_latest_command(ledger, step=1, command="python3 -m pytest -q")
    assert completion_signal_context(ledger, mode="control") is None


def test_safe_latest_verification_emits_factual_signal() -> None:
    ledger = ExecutionLedger()
    _record_latest_command(ledger, step=1, command="python3 -m pytest -q")
    signal = completion_signal_context(ledger, mode="verification_v1")
    assert signal is not None
    assert signal["basis"] == "latest_primary_result"
    assert signal["semantic_completion_authority"] == "solver_against_raw_task_and_observed_reality"
    assert signal["source_receipt_ids"] == ["step-1:cmd:cmd"]
    assert "If this verification covers all remaining task requirements" in signal["instruction"]


def test_authority_v2_reanchors_local_evidence_scope_without_claiming_completion() -> None:
    ledger = ExecutionLedger()
    _record_latest_command(ledger, step=1, command="python3 -m pytest -q")
    signal = completion_signal_context(ledger, mode="verification_authority_v2")
    assert signal is not None
    assert signal["mode"] == "verification_authority_v2"
    assert signal["semantic_completion_authority"] == "solver_against_raw_task_and_observed_reality"
    assert "supports only the properties it directly observed" in signal["verification_evidence_scope"]
    assert "self-authored or substitute check is not independent evidence" in signal["verification_evidence_scope"]
    assert "Compare this verification against the raw task's stated success authority" in signal["instruction"]
    assert "keep that requirement unresolved" in signal["instruction"]
    assert "task is complete" not in signal["instruction"].lower()


def test_ordinary_success_does_not_emit_signal() -> None:
    ledger = ExecutionLedger()
    _record_latest_command(ledger, step=1, command="python3 script.py --build-index")
    assert completion_signal_context(ledger, mode="verification_v1") is None


def test_failed_verification_does_not_emit_signal() -> None:
    ledger = ExecutionLedger()
    _record_latest_command(
        ledger, step=1, command="python3 -m pytest -q", success=False,
    )
    assert completion_signal_context(ledger, mode="verification_v1") is None


def test_integrity_rejected_verification_does_not_emit_signal() -> None:
    ledger = ExecutionLedger()
    _record_latest_command(
        ledger,
        step=1,
        command="python3 -m pytest -q | tail -20",
        eligible=False,
        risk="verification_exit_status_masked_by_pipeline",
    )
    assert completion_signal_context(ledger, mode="verification_v1") is None


def test_authority_v2_surfaces_integrity_rejected_verification_as_negative_signal() -> None:
    ledger = ExecutionLedger()
    _record_latest_command(
        ledger,
        step=1,
        command='python verify.py 2>&1 | grep -E "FAIL|ALL PASS"',
        eligible=False,
        risk="verification_exit_status_masked_by_pipeline",
    )
    signal = completion_signal_context(ledger, mode="verification_authority_v2")
    assert signal is not None
    assert signal["mode"] == "verification_authority_v2"
    assert signal["verification_integrity_risks"] == [
        "verification_exit_status_masked_by_pipeline"
    ]
    assert "not admissible completion evidence" in signal["observation"]
    assert "Do not finish on the basis of this verification result" in signal["instruction"]
    assert "fail-closed" in signal["instruction"]


def test_stale_verification_is_not_a_signal_after_later_state_change() -> None:
    ledger = ExecutionLedger()
    _record_latest_command(ledger, step=1, command="python3 -m pytest -q")
    _record_latest_write(ledger, step=2)
    assert completion_signal_context(ledger, mode="verification_v1") is None

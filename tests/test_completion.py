"""Completion-gate tests for the sole PCR mechanical custody contract."""
from __future__ import annotations

from aether.completion import CompletionGate, FailureParser
from aether.ledger import ExecutionLedger, Receipt
from aether.monitors import MonitorAlert
from aether.runtime_ir import (
    BootstrapPolicy, CompiledRuntime, CompletionPolicy, ContextPolicy, EvalIndex,
    HelperToolPolicy, ObjectiveGraph, ProcessPolicy, RefusalPolicy,
)


def _compiled(*, require_clean_integrity: bool = False) -> CompiledRuntime:
    return CompiledRuntime(
        task_prompt="test task",
        env_digest="env",
        objective_graph=ObjectiveGraph(),
        eval_index=EvalIndex(),
        selected_capabilities=(),
        stable_prefix_sections=(),
        context_policy=ContextPolicy(),
        process_policy=ProcessPolicy(),
        helper_tool_policy=HelperToolPolicy(),
        bootstrap_policy=BootstrapPolicy(),
        completion_policy=CompletionPolicy(require_clean_integrity=require_clean_integrity),
        refusal_policy=RefusalPolicy(),
        enforced_monitors=(),
        check_plan_ids=(),
        forbidden_paths=(),
    )


def _record_current_observation(ledger: ExecutionLedger, *, step: int = 1) -> None:
    ledger.record(Receipt(
        receipt_id=f"check-{step}", step=step, kind="check_result", success=True,
        summary="current observation", payload={
            "check_id": "current", "passed": True,
            **ledger.current_snapshot_binding_payload(),
        },
    ))


def _record_current_claim(ledger: ExecutionLedger, *, step: int = 2) -> None:
    ledger.record(Receipt(
        receipt_id=f"claim-{step}", step=step, kind="primary_submission_claim",
        success=True, summary="candidate ready", payload={
            "claim_id": "claim",
            "claim": "candidate ready",
            "evidence_refs": [],
            "evidence_receipt_ids": [],
            "evidence_bindings": [],
            **ledger.current_snapshot_binding_payload(),
        },
    ))


def test_current_claim_and_authoritative_observation_are_ready() -> None:
    ledger = ExecutionLedger()
    _record_current_observation(ledger)
    _record_current_claim(ledger)
    decision = CompletionGate().evaluate(_compiled(), ledger, [])
    assert decision.ready is True
    assert decision.blockers == ()


def test_missing_submission_claim_fails_closed() -> None:
    ledger = ExecutionLedger()
    _record_current_observation(ledger)
    decision = CompletionGate().evaluate(_compiled(), ledger, [])
    assert decision.ready is False
    assert "submission_snapshot_unknown" in {b.code for b in decision.blockers}


def test_stale_submission_claim_after_state_change_fails_closed() -> None:
    ledger = ExecutionLedger()
    _record_current_observation(ledger)
    _record_current_claim(ledger)
    ledger.record(Receipt(
        receipt_id="mutation", step=3, kind="write_file", success=True,
        summary="mutated after submit", state_change=True,
        payload={"path": "out.txt", "modified_paths": ("out.txt",)},
    ))
    decision = CompletionGate().evaluate(_compiled(), ledger, [])
    assert decision.ready is False
    assert "submission_snapshot_invalid" in {b.code for b in decision.blockers}


def test_unknown_coarse_task_state_boundary_fails_closed() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="opaque", step=1, kind="run_command", success=True,
        summary="opaque mutation boundary", state_change=False,
        payload={"state_delta": {"mutation_detection_status": "coarse", "mutation_detection_scope": "opaque_run_command_task_world"}},
    ))
    _record_current_claim(ledger, step=2)
    decision = CompletionGate().evaluate(_compiled(), ledger, [])
    assert decision.ready is False
    assert "task_state_snapshot_unknown" in {b.code for b in decision.blockers}


def test_integrity_violation_is_mechanical_blocker() -> None:
    ledger = ExecutionLedger()
    _record_current_observation(ledger)
    _record_current_claim(ledger)
    ledger.integrity_violations.append("protected path changed")
    decision = CompletionGate().evaluate(_compiled(require_clean_integrity=True), ledger, [])
    assert decision.ready is False
    assert "integrity_violation" in {b.code for b in decision.blockers}


def test_error_monitor_alert_is_mechanical_blocker() -> None:
    ledger = ExecutionLedger()
    _record_current_observation(ledger)
    _record_current_claim(ledger)
    alert = MonitorAlert(code="monitor-x", message="observed failure", severity="error", blocker_code="monitor_failed")
    decision = CompletionGate().evaluate(_compiled(), ledger, [alert])
    assert decision.ready is False
    assert "monitor_failed" in {b.code for b in decision.blockers}


def test_failure_parser_keeps_generic_execution_classification() -> None:
    parser = FailureParser()
    assert parser.classify("command not found", exit_code=127) == "missing_capability"
    assert parser.classify("permission denied", exit_code=1) == "integrity_violation"
    assert parser.classify("timed out", exit_code=1) == "timeout"


def _record_opaque_boundary(ledger: ExecutionLedger, *, step: int = 1) -> None:
    ledger.record(Receipt(
        receipt_id=f"opaque-{step}", step=step, kind="run_command", success=True,
        summary="opaque task-world boundary", state_change=False,
        payload={"state_delta": {
            "mutation_detection_status": "coarse",
            "mutation_detection_scope": "opaque_run_command_task_world",
        }},
    ))


def _record_bridge_observation(
    ledger: ExecutionLedger, *, step: int = 2, receipt_id: str = "service-current",
    kind: str = "service_probe", success: bool = True,
) -> None:
    ledger.record(Receipt(
        receipt_id=receipt_id, step=step, kind=kind, success=success,
        summary="typed current observation",
        payload={
            "target": "127.0.0.1:18765", "live": success,
            "process_generation": "gen-current" if success else "",
            "process_generation_verified": bool(success),
        },
    ))


def _record_bound_claim(
    ledger: ExecutionLedger, *, receipt_id: str = "claim-bound", step: int = 3,
    evidence_receipt_id: str = "service-current",
) -> None:
    generation = ledger.task_state_generation()
    ledger.record(Receipt(
        receipt_id=receipt_id, step=step, kind="primary_submission_claim",
        success=True, summary="current Luna completion claim", payload={
            "claim_id": receipt_id,
            "claim": "current candidate is complete",
            "current_anchor_count": 1,
            "evidence_receipt_ids": [evidence_receipt_id],
            "evidence_bindings": [{
                "receipt_id": evidence_receipt_id,
                "role": "current_anchor",
                "task_state_generation": generation,
            }],
            **ledger.current_snapshot_binding_payload(),
        },
    ))


def test_unknown_opaque_boundary_can_be_bridged_by_cited_current_typed_observation() -> None:
    ledger = ExecutionLedger()
    _record_opaque_boundary(ledger)
    _record_bridge_observation(ledger)
    _record_bound_claim(ledger)
    assert ledger.task_state_snapshot_known() is False, "bridge must not factualize global uncertainty"
    claim = ledger.latest_receipt("primary_submission_claim")
    assert ledger.submission_claim_bridges_unknown_snapshot(claim) is True
    decision = CompletionGate().evaluate(_compiled(), ledger, [])
    assert decision.ready is True
    assert decision.blockers == ()
    assert ledger.task_state_snapshot_known() is False


def test_unknown_snapshot_bridge_requires_cited_post_boundary_observation() -> None:
    ledger = ExecutionLedger()
    _record_bridge_observation(ledger, step=0, receipt_id="stale-service")
    _record_opaque_boundary(ledger, step=1)
    _record_bridge_observation(ledger, step=2, receipt_id="uncited-current")
    _record_bound_claim(ledger, evidence_receipt_id="stale-service")
    assert ledger.submission_claim_bridges_unknown_snapshot(
        ledger.latest_receipt("primary_submission_claim")
    ) is False
    decision = CompletionGate().evaluate(_compiled(), ledger, [])
    assert decision.ready is False
    assert "task_state_snapshot_unknown" in {b.code for b in decision.blockers}


def test_unknown_snapshot_bridge_rejects_generic_output_and_failed_observation() -> None:
    for kind, success in (("read_output", True), ("service_probe", False)):
        ledger = ExecutionLedger()
        _record_opaque_boundary(ledger)
        _record_bridge_observation(ledger, kind=kind, success=success)
        _record_bound_claim(ledger)
        assert ledger.submission_claim_bridges_unknown_snapshot(
            ledger.latest_receipt("primary_submission_claim")
        ) is False
        assert CompletionGate().evaluate(_compiled(), ledger, []).ready is False


def test_unknown_snapshot_bridge_rejects_payload_drift() -> None:
    ledger = ExecutionLedger()
    _record_opaque_boundary(ledger)
    _record_bridge_observation(ledger)
    observation = ledger.latest_receipt("service_probe")
    assert observation is not None
    _record_bound_claim(ledger)
    observation.payload["live"] = False
    assert ledger.submission_claim_bridges_unknown_snapshot(
        ledger.latest_receipt("primary_submission_claim")
    ) is False
    decision = CompletionGate().evaluate(_compiled(), ledger, [])
    assert decision.ready is False
    assert "task_state_snapshot_unknown" in {b.code for b in decision.blockers}


def test_unknown_snapshot_bridge_does_not_override_integrity_or_monitor_blockers() -> None:
    ledger = ExecutionLedger()
    _record_opaque_boundary(ledger)
    _record_bridge_observation(ledger)
    _record_bound_claim(ledger)
    ledger.integrity_violations.append("protected path changed")
    decision = CompletionGate().evaluate(_compiled(require_clean_integrity=True), ledger, [])
    assert decision.ready is False
    assert "integrity_violation" in {b.code for b in decision.blockers}

    ledger.integrity_violations.clear()
    alert = MonitorAlert(code="m", message="fatal observation", severity="fatal", blocker_code="fatal_state")
    decision = CompletionGate().evaluate(_compiled(), ledger, [alert])
    assert decision.ready is False
    assert "fatal_state" in {b.code for b in decision.blockers}


def test_unknown_snapshot_bridge_rejects_unowned_service_probe_and_undeclared_binding() -> None:
    ledger = ExecutionLedger()
    _record_opaque_boundary(ledger)
    observation = Receipt(
        receipt_id="unowned-service", step=2, kind="service_probe", success=True,
        summary="unowned endpoint is live", payload={
            "target": "127.0.0.1:18765", "live": True,
            "process_generation": "", "process_generation_verified": False,
        },
    )
    ledger.record(observation)
    _record_bound_claim(ledger, evidence_receipt_id=observation.receipt_id)
    assert ledger.submission_claim_bridges_unknown_snapshot(
        ledger.latest_receipt("primary_submission_claim")
    ) is False

    ledger2 = ExecutionLedger()
    _record_opaque_boundary(ledger2)
    _record_bridge_observation(ledger2, receipt_id="owned-service")
    _record_bound_claim(ledger2, evidence_receipt_id="owned-service")
    claim2 = ledger2.latest_receipt("primary_submission_claim")
    assert claim2 is not None
    claim2.payload["evidence_receipt_ids"] = []
    assert ledger2.submission_claim_bridges_unknown_snapshot(claim2) is False



def _record_same_boundary_command_anchor(
    ledger: ExecutionLedger, *, receipt_id: str = "command-current", step: int = 1,
    success: bool = True, workspace_status: str = "complete", path_status: str = "complete",
    before_truncated: bool = False, after_truncated: bool = False,
    timed_out: bool = False, integrity_violation: str = "",
) -> None:
    payload = {
        "command": "python3 -m pytest -q",
        "exit_code": 0 if success else 1,
        "stdout_handle": f"{step}:command:stdout",
        "stderr_handle": f"{step}:command:stderr",
        "timed_out": timed_out,
        "state_delta": {
            "mutation_detection_status": "coarse",
            "mutation_detection_scope": "opaque_run_command_task_world",
            "workspace_mutation_detection_status": workspace_status,
            "path_set_delta_status": path_status,
            "before_truncated": before_truncated,
            "after_truncated": after_truncated,
        },
    }
    if integrity_violation:
        payload["integrity_violation"] = integrity_violation
    ledger.record(Receipt(
        receipt_id=receipt_id, step=step, kind="run_command", success=success,
        summary="current validation command", state_change=False, payload=payload,
    ))


def test_unknown_snapshot_same_boundary_successful_command_result_can_bridge_claim_locally() -> None:
    ledger = ExecutionLedger()
    _record_same_boundary_command_anchor(ledger)
    _record_bound_claim(ledger, step=2, evidence_receipt_id="command-current")
    assert ledger.task_state_snapshot_known() is False
    claim = ledger.latest_receipt("primary_submission_claim")
    assert ledger.submission_claim_bridges_unknown_snapshot(claim) is True
    decision = CompletionGate().evaluate(_compiled(), ledger, [])
    assert decision.ready is True
    assert ledger.task_state_snapshot_known() is False, "command bridge must never factualize global state"


def test_unknown_snapshot_same_boundary_command_bridge_rejects_incomplete_or_truncated_workspace_inventory() -> None:
    bad_rows = [
        {"workspace_status": "truncated"},
        {"path_status": "unknown_due_truncation"},
        {"before_truncated": True},
        {"after_truncated": True},
    ]
    for kwargs in bad_rows:
        ledger = ExecutionLedger()
        _record_same_boundary_command_anchor(ledger, **kwargs)
        _record_bound_claim(ledger, step=2, evidence_receipt_id="command-current")
        assert ledger.submission_claim_bridges_unknown_snapshot(
            ledger.latest_receipt("primary_submission_claim")
        ) is False
        assert CompletionGate().evaluate(_compiled(), ledger, []).ready is False


def test_unknown_snapshot_same_boundary_command_bridge_rejects_failure_timeout_integrity_and_stale_boundary() -> None:
    for kwargs in (
        {"success": False},
        {"timed_out": True},
        {"integrity_violation": "protected path changed"},
    ):
        ledger = ExecutionLedger()
        _record_same_boundary_command_anchor(ledger, **kwargs)
        _record_bound_claim(ledger, step=2, evidence_receipt_id="command-current")
        assert ledger.submission_claim_bridges_unknown_snapshot(
            ledger.latest_receipt("primary_submission_claim")
        ) is False

    ledger = ExecutionLedger()
    _record_same_boundary_command_anchor(ledger, step=1)
    _record_opaque_boundary(ledger, step=2)
    _record_bound_claim(ledger, step=3, evidence_receipt_id="command-current")
    assert ledger.submission_claim_bridges_unknown_snapshot(
        ledger.latest_receipt("primary_submission_claim")
    ) is False

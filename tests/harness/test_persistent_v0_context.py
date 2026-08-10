"""Deterministic PERSISTENT V0 authoritative-context and exact-evidence tests."""
from __future__ import annotations

import json
from types import SimpleNamespace

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.context_compiler import ContextCompiler
from aether.envmap_builder import build_envmap_from_task
from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_context import evidence_alias, receipt_exact_handle
from aether.persistent_primary import persistent_primary_runtime_ir
from aether.run_adapter import _build_runtime_identity
from aether.runtime_ir import ActionRequest


def _compiled(tmp_path):
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Create out.txt containing hello.",
        workspace_root=str(tmp_path),
    )
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
    objective, eval_index = compiler.analyze_envmap(envmap)
    compiled = compiler.compile(
        persistent_primary_runtime_ir(envmap, eval_index),
        envmap,
        objective_graph=objective,
        eval_index=eval_index,
    )
    return envmap, compiled


def _identity(tmp_path) -> dict[str, object]:
    return {
        "task_id": "task-1",
        "run_id": "run-1",
        "primary_agent_id": "primary-agent:run-1",
        "workspace_id": str(tmp_path),
        "environment_id": "env-1",
        "source_commit": "a" * 40,
        "source_commit_state": "provided",
        "runtime_manifest_sha256": "b" * 64,
        "runtime_manifest_state": "provided",
        "source_custody_complete": True,
        "budgets": {"max_kernel_steps": 8},
    }


def _ledger_with_latest_result(tmp_path) -> tuple[ExecutionLedger, Receipt]:
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    action_id = "persistent-action-1"
    result = Receipt(
        receipt_id=f"step-1:{action_id}:write",
        step=1,
        kind="write_file",
        success=True,
        summary="wrote out.txt",
        state_change=True,
        payload={
            "path": "out.txt",
            "bytes": 5,
            "after_content_hash": "c" * 64,
            "excerpt": "hello",
            "file_handle": "file:out.txt",
        },
    )
    ledger.record(result)
    ledger.record(Receipt(
        receipt_id="step-1:authoritative-check",
        step=1,
        kind="check_result",
        success=True,
        summary="auxiliary check passed",
        payload={"check_id": "check-1", "passed": True},
    ))
    ledger.record(Receipt(
        receipt_id=f"step-1:{action_id}:primary_action_result_index",
        step=1,
        kind="primary_action_result_index",
        success=True,
        summary="indexed Primary Agent result",
        payload={
            "action_id": action_id,
            "action_kind": "write_file",
            "status": "observed",
            "outcome_receipt_ids": [result.receipt_id],
            "outcome_kinds": [result.kind],
        },
    ))
    # Later auxiliary/control receipts must not displace the action result.
    ledger.record(Receipt(
        receipt_id="step-1:later-progress",
        step=1,
        kind="solver_progress_assessment",
        success=True,
        summary="mechanical progress assessment",
    ))
    return ledger, result


def test_persistent_context_pins_latest_primary_result_over_later_auxiliary_receipts(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, result = _ledger_with_latest_result(tmp_path)

    packet = ContextCompiler().compile(compiled, ledger, alerts=[])

    assert list(packet)[:7] == [
        "latest_primary_result",
        "runtime_identity",
        "unresolved_runtime_facts",
        "unresolved_verifier_findings",
        "evidence_index",
        "available_capabilities",
        "budgets",
    ]
    latest = packet["latest_primary_result"]
    assert latest["action_id"] == "persistent-action-1"
    assert latest["outcome_receipt_ids"] == [result.receipt_id]
    assert latest["outcome_receipts"][0]["receipt_id"] == result.receipt_id
    assert latest["outcome_receipts"][0]["exact_access"]["handle"] == receipt_exact_handle(result.receipt_id)
    assert packet["linked_history"]["tool_results"]


def test_evidence_aliases_are_visible_stable_and_lineage_bound(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, result = _ledger_with_latest_result(tmp_path)

    first = ContextCompiler().compile(compiled, ledger, alerts=[])
    second = ContextCompiler().compile(compiled, ledger, alerts=[])
    first_row = next(row for row in first["evidence_index"] if row["receipt_id"] == result.receipt_id)
    second_row = next(row for row in second["evidence_index"] if row["receipt_id"] == result.receipt_id)

    assert first_row["evidence_ref"] == evidence_alias(result.receipt_id)
    assert first_row["evidence_ref"] == second_row["evidence_ref"]
    assert first_row["task_id"] == "task-1"
    assert first_row["run_id"] == "run-1"
    assert first_row["workspace_id"] == str(tmp_path)
    assert first_row["currentness"] == "latest_primary_result"
    assert first_row["exact_access"]["state"] == "receipt_handle_exact"


def test_read_output_pages_the_exact_canonical_receipt_payload(tmp_path) -> None:
    envmap, compiled = _compiled(tmp_path)
    ledger, result = _ledger_with_latest_result(tmp_path)
    action = ActionRequest(
        action_id="read-exact-receipt",
        kind="read_output",
        capability_id="kernel",
        arguments={
            "handle": receipt_exact_handle(result.receipt_id),
            "offset": 0,
            "span": 20000,
        },
        intent="",
        expected_observation="",
        if_fail_next="",
    )

    receipts = dispatch_action(
        SimpleNamespace(), action, 2, compiled, None, envmap, ledger  # type: ignore[arg-type]
    )
    assert len(receipts) == 1
    observed = receipts[0]
    assert observed.success is True
    assert observed.payload["source_receipt_id"] == result.receipt_id
    assert observed.payload["stream"] == "receipt"
    exact = json.loads(observed.payload["chunk"])
    assert exact["receipt_id"] == result.receipt_id
    assert exact["payload"] == result.payload


def test_missing_source_custody_is_truthfully_pinned_not_invented(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    identity = _identity(tmp_path)
    identity.update({
        "source_commit": "",
        "source_commit_state": "not_supplied",
        "runtime_manifest_sha256": "",
        "runtime_manifest_state": "not_supplied",
        "source_custody_complete": False,
    })
    ledger.install_runtime_identity(identity)

    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    assert packet["latest_primary_result"]["status"] == "no_primary_action_yet"
    gaps = [row for row in packet["unresolved_runtime_facts"] if row["kind"] == "source_custody_gap"]
    assert {row["field"] for row in gaps} == {"source_commit", "runtime_manifest_sha256"}
    assert packet["runtime_identity"]["source_custody_complete"] is False


def test_runtime_identity_builder_is_stable_when_supplied_and_truthful_when_not(tmp_path) -> None:
    supplied = {
        "task_id": "task-fixed",
        "run_id": "run-fixed",
        "primary_agent_id": "primary-fixed",
        "source_commit": "d" * 40,
        "runtime_manifest_sha256": "e" * 64,
    }
    first = _build_runtime_identity(
        task_dir=str(tmp_path),
        instruction_text="exact raw task",
        workspace_root=str(tmp_path),
        environment_id="env-fixed",
        max_steps=12,
        supplied=supplied,
    )
    second = _build_runtime_identity(
        task_dir=str(tmp_path),
        instruction_text="exact raw task",
        workspace_root=str(tmp_path),
        environment_id="env-fixed",
        max_steps=12,
        supplied=first,
    )
    assert first == second
    assert first["source_custody_complete"] is True
    assert first["budgets"] == {"max_kernel_steps": 12}


def test_persistent_wrapper_preserves_canonical_linked_history(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, _result = _ledger_with_latest_result(tmp_path)
    ledger.record(Receipt(
        receipt_id="step-2:failed-command",
        step=2,
        kind="run_command",
        success=False,
        summary="command failed",
        failure_class="command_failure",
        payload={"command": "false", "exit_code": 1, "stderr": "failure"},
    ))

    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    assert packet["linked_history"]["command_results"][-1]["summary"] == "command failed"
    failures = [row for row in packet["unresolved_runtime_facts"] if row["kind"] == "mechanical_failure"]
    assert any(row["receipt_id"] == "step-2:failed-command" for row in failures)
    assert failures[-1]["exact_access"]["handle"] == "receipt:step-2:failed-command"



def _finding(finding_id: str, target: str):
    from aether.verifier import VerifierFinding
    return VerifierFinding(
        finding_id=finding_id,
        created_step=1,
        verdict="needs_repair",
        priority="blocking",
        summary=f"verify {target}",
        applies_to=(target,),
        repair_instruction=f"produce current evidence for {target}",
    )


def _apply_findings(ledger: ExecutionLedger, *findings) -> None:
    from aether.verifier import ModelVerifierResult
    ledger.apply_verifier_result(
        ModelVerifierResult("needs_repair", findings=tuple(findings)),
        step=1,
    )


def test_verifier_reentry_state_waits_for_relevant_evidence_not_control_receipts(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    _apply_findings(ledger, _finding("vf-a", "a.txt"))
    ledger.record(Receipt(
        receipt_id="step-2:control",
        step=2,
        kind="runtime_accounting",
        success=True,
        summary="control only",
        payload={"counter": "solver_provider_turns", "action_id": "persistent-control"},
    ))

    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    state = packet["verifier_reentry_state"]

    assert state["active_finding_count"] == 1
    assert state["all_active_findings_have_relevant_evidence"] is False
    assert state["submit_reentry_gate"] == "awaiting_relevant_evidence"
    assert state["findings"] == [{
        "finding_id": "vf-a",
        "relevant_evidence_after_latest_verifier": False,
        "relevant_evidence_receipt_ids": [],
    }]
    assert state["semantic_sufficiency"] == "not_determined_by_this_gate"


def test_verifier_reentry_state_reports_exact_relevant_receipt_without_claiming_sufficiency(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    _apply_findings(ledger, _finding("vf-a", "a.txt"))
    ledger.record(Receipt(
        receipt_id="step-2:persistent-read-a:read",
        step=2,
        kind="read_file",
        success=True,
        summary="read a.txt",
        payload={"action_id": "persistent-read-a", "path": "a.txt", "excerpt": "current"},
    ))

    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    state = packet["verifier_reentry_state"]

    assert state["all_active_findings_have_relevant_evidence"] is True
    assert state["submit_reentry_gate"] == "mechanically_eligible"
    assert state["findings"][0]["relevant_evidence_receipt_ids"] == ["step-2:persistent-read-a:read"]
    assert state["semantic_sufficiency"] == "not_determined_by_this_gate"


def test_verifier_reentry_state_requires_evidence_for_every_active_finding(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    _apply_findings(ledger, _finding("vf-a", "a.txt"), _finding("vf-b", "b.txt"))
    ledger.record(Receipt(
        receipt_id="step-2:persistent-read-a:read",
        step=2,
        kind="read_file",
        success=True,
        summary="read a.txt",
        payload={"action_id": "persistent-read-a", "path": "a.txt"},
    ))

    first = ContextCompiler().compile(compiled, ledger, alerts=[])["verifier_reentry_state"]
    by_id = {row["finding_id"]: row for row in first["findings"]}
    assert first["all_active_findings_have_relevant_evidence"] is False
    assert by_id["vf-a"]["relevant_evidence_after_latest_verifier"] is True
    assert by_id["vf-b"]["relevant_evidence_after_latest_verifier"] is False

    ledger.record(Receipt(
        receipt_id="step-3:persistent-read-b:read",
        step=3,
        kind="read_file",
        success=True,
        summary="read b.txt",
        payload={"action_id": "persistent-read-b", "path": "b.txt"},
    ))
    second = ContextCompiler().compile(compiled, ledger, alerts=[])["verifier_reentry_state"]
    assert second["all_active_findings_have_relevant_evidence"] is True
    assert second["submit_reentry_gate"] == "mechanically_eligible"


def test_verifier_reentry_state_rejects_failed_relevant_receipt(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    _apply_findings(ledger, _finding("vf-a", "a.txt"))
    ledger.record(Receipt(
        receipt_id="step-2:persistent-read-a:failed",
        step=2,
        kind="read_file",
        success=False,
        summary="read a.txt failed",
        failure_class="read_failure",
        payload={"action_id": "persistent-read-a", "path": "a.txt"},
    ))

    state = ContextCompiler().compile(compiled, ledger, alerts=[])["verifier_reentry_state"]
    assert state["all_active_findings_have_relevant_evidence"] is False
    assert state["findings"][0]["relevant_evidence_receipt_ids"] == []

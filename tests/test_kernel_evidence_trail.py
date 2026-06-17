from __future__ import annotations

import hashlib

from runner.kernel_context_pack import build_context_pack
from runner.kernel_control_plane import initialize_control_plane
from runner.kernel_evidence_trail import extract_evidence_trail_records_from_receipt
from runner.kernel_gates import finalize as finalize_governed_gate
from runner.kernel_receipts import build_receipt
from runner.kernel_state import KernelState
from runner.kernel_working_window import build_working_window
from runner.packet04_route_manifest import (
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
)


def test_extract_evidence_trail_records_capture_retrieval_accept_and_reject_signals():
    accepted_receipt = build_receipt(
        receipt_id="r0001",
        action_id="run-a0001",
        action_type="command",
        tool_name="raw_bash",
        command="cat docs/evidence.md",
        cwd="/workspace",
        exit_code=0,
        reason_code="tool_success",
        stdout="accepted evidence_id=evidence.alpha",
    )
    rejected_receipt = build_receipt(
        receipt_id="r0002",
        action_id="run-a0002",
        action_type="command",
        tool_name="raw_bash",
        command="cat docs/stale.md",
        cwd="/workspace",
        exit_code=1,
        reason_code="tool_failure",
        stderr="rejected stale evidence_id=evidence.beta",
    )

    accepted_record = extract_evidence_trail_records_from_receipt(accepted_receipt)[0]
    rejected_record = extract_evidence_trail_records_from_receipt(rejected_receipt)[0]

    assert accepted_record["action"] == "accepted"
    assert accepted_record["claim_supported"] is True
    assert accepted_record["evidence_id"] == "evidence.alpha"
    assert accepted_record["source_path"] == "docs/evidence.md"
    assert rejected_record["action"] == "rejected"
    assert rejected_record["claim_supported"] is False
    assert rejected_record["evidence_id"] == "evidence.beta"
    assert rejected_record["source_path"] == "docs/stale.md"


def test_extract_evidence_trail_records_capture_native_tool_dispatch_receipt():
    receipt = build_receipt(
        receipt_id="r0003",
        action_id="run-a0003",
        action_type="native_tool_call",
        tool_name="sample_tool",
        command="sample_tool --evidence-id dispatch-42 --input request.json",
        cwd="/workspace",
        exit_code=0,
        reason_code="tool_result_recorded",
        changed_files=["outputs/result.json"],
        tool_contract_status={"status": "pass", "missing_required": []},
    )

    record = extract_evidence_trail_records_from_receipt(receipt)[0]

    assert record["action"] == "dispatched"
    assert record["claim_supported"] is True
    assert record["receipt_id"] == "r0003"
    assert record["source_path"] == "request.json"
    assert record["artifact_path"] == "outputs/result.json"
    assert record["evidence_id"] == "dispatch-42"
    assert record["metadata"]["tool_name"] == "sample_tool"
    assert record["metadata"]["action_type"] == "native_tool_call"


def test_extract_evidence_trail_records_hash_transform_artifacts(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_path = workspace / "source.md"
    artifact_path = workspace / "handoff.md"
    source_path.write_text("source evidence\n", encoding="utf-8")
    artifact_path.write_text("handoff summary\n", encoding="utf-8")

    receipt = build_receipt(
        receipt_id="r0004",
        action_id="run-a0004",
        action_type="command",
        tool_name="raw_bash",
        command="cp source.md handoff.md",
        cwd=str(workspace),
        exit_code=0,
        reason_code="tool_success",
        changed_files=["handoff.md"],
    )

    record = extract_evidence_trail_records_from_receipt(receipt, workspace_root=workspace)[0]

    assert record["action"] == "transformed"
    assert record["claim_supported"] is True
    assert record["source_path"] == "source.md"
    assert record["artifact_path"] == "handoff.md"
    assert record["metadata"]["source_sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert record["metadata"]["artifact_sha256"] == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    assert record["metadata"]["artifact_size_bytes"] == artifact_path.stat().st_size


def _build_state_with_trail_receipt(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(
        run_id="run-evidence-trail",
        task_id="task-evidence-trail",
        workspace_root=workspace,
        cwd=str(workspace),
        task_prompt="repair the harness",
    )
    state.note_receipt(
        build_receipt(
            receipt_id="r0005",
            action_id="run-a0005",
            action_type="command",
            tool_name="raw_bash",
            command="cat docs/evidence.md",
            cwd=str(workspace),
            exit_code=0,
            reason_code="tool_success",
            stdout="accepted evidence_id=evidence.alpha",
        )
    )
    return workspace, state


def test_proposed_success_contract_visible_refs_do_not_create_evidence_trail_obligation(tmp_path):
    workspace, state = _build_state_with_trail_receipt(tmp_path)
    state.success_contract = {
        "status": "proposed",
        "contract_id": "contract-evidence-trail",
        "visible_evidence_refs": ["evidence.alpha", "evidence.beta"],
        "criteria": ["deliver the proposed handoff"],
        "required_checks": [],
        "done_checklist": [],
    }
    state.refresh_evidence_trail()
    state.refresh_open_obligations()
    context_pack = build_context_pack(state)

    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    control_plane = initialize_control_plane(
        state,
        state.task_prompt,
        {
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "required_artifact_paths": [],
        },
        route_manifest,
    )
    window = build_working_window(control_plane, state, budget=4000)

    assert context_pack["evidence_trail_state"]["visible_evidence_refs"] == ["evidence.alpha", "evidence.beta"]
    assert context_pack["evidence_trail_state"]["requirements"]["status"] == "not_required"
    assert window["evidence_trail_state"]["visible_evidence_refs"] == ["evidence.alpha", "evidence.beta"]
    assert window["evidence_trail_state"]["requirements"]["status"] == "not_required"
    assert "evidence_trail_missing" not in state.open_obligations


def test_frozen_success_contract_missing_visible_refs_creates_evidence_trail_obligation(tmp_path):
    workspace, state = _build_state_with_trail_receipt(tmp_path)
    state.success_contract = {
        "status": "frozen",
        "contract_id": "contract-evidence-trail",
        "visible_evidence_refs": ["evidence.alpha", "evidence.beta"],
        "criteria": ["deliver the frozen handoff"],
        "required_checks": [],
        "done_checklist": [],
    }
    state.refresh_evidence_trail()
    state.refresh_open_obligations()
    context_pack = build_context_pack(state)

    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    control_plane = initialize_control_plane(
        state,
        state.task_prompt,
        {
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "required_artifact_paths": [],
        },
        route_manifest,
    )
    window = build_working_window(control_plane, state, budget=4000)

    assert context_pack["evidence_trail_state"]["requirements"]["status"] == "fail"
    assert context_pack["evidence_trail_state"]["requirements"]["missing_evidence_ids"] == ["evidence.beta"]
    assert window["evidence_trail_state"]["requirements"]["status"] == "fail"
    assert window["evidence_trail_state"]["requirements"]["missing_evidence_ids"] == ["evidence.beta"]
    assert set(state.open_obligations["evidence_trail_missing"]) == {
        "evidence.beta",
        "evidence_trail_missing",
        "missing_required_evidence_id",
    }


def test_finalize_with_frozen_missing_evidence_blocks_correctly(tmp_path):
    workspace, state = _build_state_with_trail_receipt(tmp_path)
    state.success_contract = {
        "status": "frozen",
        "contract_id": "contract-evidence-trail",
        "visible_evidence_refs": ["evidence.alpha", "evidence.beta"],
        "criteria": ["deliver the frozen handoff"],
        "required_checks": [],
        "done_checklist": [],
    }
    state.refresh_evidence_trail()
    state.refresh_open_obligations()
    result = finalize_governed_gate(
        execution_result={
            "status": "completed",
            "active_kernel_state": state.to_dict(),
            "workspace_state": {
                "execution_status": "done",
                "model_claimed_done": True,
                "success_contract": dict(state.success_contract),
                "open_obligations": dict(state.open_obligations),
            },
        },
        workspace_state={
            "active_kernel_state": state.to_dict(),
            "execution_status": "done",
            "model_claimed_done": True,
            "success_contract": dict(state.success_contract),
            "open_obligations": dict(state.open_obligations),
        },
        verified=True,
    )

    assert result["governed_status"] == "ungoverned_model_claim"
    assert result["final_verdict"] == "unresolved"
    assert "evidence_trail_missing" in result["reason_codes"]
    assert "evidence_trail_missing" in result["open_obligations"]

from __future__ import annotations

from pathlib import Path

from runner.active_evidence_kernel import ActiveEvidenceKernel, orient, run_loop
from runner.kernel_context_pack import build_context_pack
from runner.kernel_compaction import create_compaction_boundary, extract_compaction_summary, rehydrate_after_compaction, validate_compaction_summary
from runner.kernel_control_plane import apply_model_state_update, extract_model_state_update, initialize_control_plane, render_model_contract
from runner.kernel_interrupts import build_interrupt_packet, detect_interrupt, finish_claim_requires_gate
from runner.kernel_gates import check as run_verifier_gate_check
from runner.kernel_gates import finalize as finalize_governed_gate
from runner.kernel_receipts import build_receipt
from runner.kernel_recovery import handle_error
from runner.kernel_native_tools import execute_tool_call, get_tools
from runner.kernel_working_window import build_working_window, estimate_window_size
from runner.kernel_state import KernelState
from runner.model_client import LocalStubModelClient, ModelClientError, make_no_model_route
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
)
from runner.agent import _apply_authoritative_artifact_probe, run_reference_baseline


class _ScriptedModel:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, _messages, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(list(_messages))
        if self._responses:
            return self._responses.pop(0)
        return {"text": "", "tool_calls": []}


def test_active_route_manifest_is_distinct_from_baseline_and_wires_active_modules():
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    active = build_packet04_route_manifest("active_evidence_kernel_v1", scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)

    baseline_by_runtime = {entry["runtime_key"]: entry for entry in baseline["routed_modules"]}
    active_by_runtime = {entry["runtime_key"]: entry for entry in active["routed_modules"]}

    assert active["variant_id"] == "active_evidence_kernel_v1"
    assert active_by_runtime["execution"]["module_import_path"] == "runner.active_evidence_kernel:run_loop"
    assert active_by_runtime["terminal_guard"]["module_import_path"] == "runner.active_evidence_kernel:finalize"
    assert active_by_runtime["verification"]["module_import_path"] == "runner.kernel_gates:check"
    assert active_by_runtime["recovery"]["module_import_path"] == "runner.kernel_recovery:handle_error"
    assert active_by_runtime["context"]["module_import_path"] == "runner.kernel_context_pack:manage"
    assert active_by_runtime["tools_getter"]["module_import_path"] == "runner.kernel_native_tools:get_tools"
    assert active_by_runtime["tool_executor"]["module_import_path"] == "runner.kernel_native_tools:execute_tool_call"
    assert active_by_runtime["execution"]["module_import_path"] != baseline_by_runtime["execution"]["module_import_path"]
    assert baseline_by_runtime["recovery"]["module_import_path"] == "runner.packet04_route_manifest:baseline_recovery_handle_error"
    assert baseline_by_runtime["terminal_guard"]["module_import_path"] == "runner.packet04_route_manifest:baseline_terminal_outcome_guard"


def test_control_plane_variant_routes_the_new_context_stack_and_bootstrap_route():
    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    routed_by_runtime = {entry["runtime_key"]: entry for entry in route_manifest["routed_modules"]}

    assert route_manifest["variant_id"] == "active_evidence_kernel_control_plane_context_v1"
    assert routed_by_runtime["context"]["module_import_path"] == "runner.kernel_working_window:manage"
    assert routed_by_runtime["execution"]["module_import_path"] == "runner.active_evidence_kernel:run_loop"
    assert routed_by_runtime["terminal_guard"]["module_import_path"] == "runner.active_evidence_kernel:finalize"

    bootstrap = orient(
        "finish the task",
        {
            "cwd": "/tmp/workspace",
            "task_id": "task-control-plane",
            "run_id": "run-control-plane",
            "variant_id": "active_evidence_kernel_control_plane_context_v1",
        },
    )
    assert bootstrap["active_kernel_bootstrap"]["route"] == "active_evidence_kernel_control_plane_context_v1"
    assert "semantic_state_update" in bootstrap["messages"][2]["content"]
    assert "hypotheses" in bootstrap["messages"][2]["content"]


def test_control_plane_helpers_keep_pinned_invariants_visible_and_finish_claim_explicit(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    state = KernelState(
        run_id="run-control-plane",
        task_id="task-control-plane",
        workspace_root=workspace,
        cwd=str(workspace),
        task_prompt="repair the harness",
    )
    for index in range(3):
        state.note_receipt(
            build_receipt(
                receipt_id=f"r{index + 1:04d}",
                action_id=f"run-control-plane-a{index + 1:04d}",
                action_type="command",
                tool_name="raw_bash",
                command=f"echo {index}",
                cwd=str(workspace),
                exit_code=0,
                reason_code="tool_success",
                stdout="",
                stderr="",
                changed_files=[f"out-{index}.txt"],
            )
        )

    control_plane = initialize_control_plane(
        state,
        state.task_prompt,
        {
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "required_artifact_paths": ["run_header.json"],
        },
        route_manifest,
    )
    window = build_working_window(control_plane, state, budget=4000)
    interrupt = detect_interrupt(
        control_plane,
        state,
        {
            "step": 1,
            "completion": {"text": "explicit finish", "finish_claim": True},
            "working_window_size": estimate_window_size(window),
        },
    )
    packet = build_interrupt_packet(interrupt, control_plane, state)
    boundary = create_compaction_boundary(control_plane, state, {"summary": "compact"}, "receipt_pressure")
    rehydrated = rehydrate_after_compaction(control_plane, state, boundary)

    assert window["working_window_version"] == "control_plane_working_window.v1"
    assert window["pinned_invariants"]["task_prompt"] == "repair the harness"
    assert window["semantic_sideband"]["current_objective"] == "repair the harness"
    assert window["raw_trace_pointers"]["run_events"] == "run_events.jsonl"
    assert packet["finish_claim"] is True
    assert packet["allowed_decisions"][0] == "finish"
    assert packet["interrupt_reason"] == "completion_claimed"
    assert boundary["preserved_receipt_ids"] == ["r0001", "r0002", "r0003"]
    assert rehydrated["status"] == "pass"
    assert rehydrated["control_plane"]["last_compaction_boundary"]["compact_id"] == boundary["compact_id"]


def test_control_plane_model_update_tracks_proposed_success_criteria_without_overwriting_kernel_truth(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    state = KernelState(
        run_id="run-model-update",
        task_id="task-model-update",
        workspace_root=workspace,
        cwd=str(workspace),
        task_prompt="repair the harness",
    )
    control_plane = initialize_control_plane(
        state,
        state.task_prompt,
        {
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "required_artifact_paths": ["run_header.json"],
        },
        route_manifest,
    )
    completion = {
        "text": "",
        "tool_calls": [],
        "control_plane_update": {
            "plan_state": {
                "current_objective": "repair the harness",
                "current_step": "inspect the service config",
                "next_action": "probe the declared readiness route",
                "active_plan": ["inspect the service config", "probe the declared readiness route"],
                "status": "running",
            },
            "semantic_state": {
                "summary": "The process is running but readiness is still unproven.",
                "discoveries": ["the service process started"],
                "open_questions": ["which port does the readiness route use?"],
                "evidence_notes": ["receipt r0001 proves start-up but not readiness"],
                "hypotheses": ["the readiness route may still be warming up"],
                "evidence_targets": ["readiness route response"],
                "candidate_next_checks": [
                    "probe the declared readiness route",
                    "inspect the service config",
                ],
                "subtasks": ["inspect the service config"],
                "blocked_reason": "need readiness evidence",
                "confidence": "medium",
                "proposed_success_criteria": ["Readiness route responds before governed finish."],
                "replan_requested": True,
            },
        },
    }

    proposal = extract_model_state_update(completion)
    applied = apply_model_state_update(control_plane, proposal, receipt_id="run-model-update-step0001")

    assert applied["status"] == "accepted"
    updated = applied["control_plane"]
    assert updated["plan_state"]["current_step"] == "inspect the service config"
    assert updated["plan_state"]["next_action"] == "probe the declared readiness route"
    assert updated["semantic_state"]["summary"] == "The process is running but readiness is still unproven."
    assert updated["semantic_state"]["proposed_success_criteria"] == [
        "Readiness route responds before governed finish."
    ]
    assert updated["semantic_state"]["hypotheses"] == ["the readiness route may still be warming up"]
    assert updated["semantic_state"]["evidence_targets"] == ["readiness route response"]
    assert updated["semantic_state"]["candidate_next_checks"] == [
        "probe the declared readiness route",
        "inspect the service config",
    ]
    assert updated["semantic_state"]["subtasks"] == ["inspect the service config"]
    assert updated["semantic_state"]["blocked_reason"] == "need readiness evidence"
    assert updated["semantic_state"]["confidence"] == "medium"
    assert updated["semantic_state"]["replan_requested"] is True
    assert updated["semantic_state"]["interrupt_reason"] == "replan_requested"
    assert updated["model_success_criteria"] == ["Readiness route responds before governed finish."]
    assert updated["success_criteria"]["governed_finish_required"] is True
    assert "kernel_pinned_success_criteria" in render_model_contract(state.task_prompt, route_manifest)

    window = build_working_window(updated, state, budget=4000)
    assert window["semantic_sideband"]["hypotheses"] == ["the readiness route may still be warming up"]
    assert window["semantic_sideband"]["blocked_reason"] == "need readiness evidence"
    assert window["semantic_sideband"]["replan_requested"] is True
    assert window["semantic_sideband"]["interrupt_reason"] == "replan_requested"


def test_control_plane_rejects_pinned_truth_mutation_and_text_only_finish_claim_is_false(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    state = KernelState(
        run_id="run-model-update-reject",
        task_id="task-model-update-reject",
        workspace_root=workspace,
        cwd=str(workspace),
        task_prompt="repair the harness",
    )
    control_plane = initialize_control_plane(
        state,
        state.task_prompt,
        {
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "required_artifact_paths": ["run_header.json"],
        },
        route_manifest,
    )
    bad_completion = {
        "text": "explicit finish",
        "tool_calls": [],
        "control_plane_update": {
            "semantic_state": {
                "summary": "done",
                "success_criteria": ["override the kernel truth"],
            }
        },
    }

    proposal = extract_model_state_update(bad_completion)
    applied = apply_model_state_update(control_plane, proposal, receipt_id="run-model-update-reject-step0001")

    assert applied["status"] == "rejected"
    assert any(reason == "semantic_state.success_criteria" or reason == "pinned_invariant_update_blocked" for reason in applied["reason_codes"])
    assert finish_claim_requires_gate({"text": "explicit finish"}, control_plane, state) is False
    assert finish_claim_requires_gate({"text": "{\"finish_claim\":true}"}, control_plane, state) is True


def test_control_plane_interrupts_follow_model_replan_and_blocked_sideband(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    state = KernelState(
        run_id="run-model-interrupt",
        task_id="task-model-interrupt",
        workspace_root=workspace,
        cwd=str(workspace),
        task_prompt="repair the harness",
    )
    base_control_plane = initialize_control_plane(
        state,
        state.task_prompt,
        {
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "required_artifact_paths": ["run_header.json"],
        },
        route_manifest,
    )
    replan_completion = {
        "control_plane_update": {
            "semantic_state": {
                "replan_requested": True,
                "summary": "Need to re-check the service contract before continuing.",
                "hypotheses": ["the service contract may be stale"],
                "candidate_next_checks": ["inspect the declared service route"],
                "confidence": "low",
            }
        }
    }
    replan_proposal = extract_model_state_update(replan_completion)
    replan_applied = apply_model_state_update(base_control_plane, replan_proposal, receipt_id="run-model-interrupt-step0001")
    assert replan_applied["status"] == "accepted"
    replan_interrupt = detect_interrupt(replan_applied["control_plane"], state, {"completion": {"text": "", "tool_calls": []}})
    replan_packet = build_interrupt_packet(replan_interrupt, replan_applied["control_plane"], state)
    assert replan_interrupt["interrupt_reason"] == "model_replan_requested"
    assert replan_packet["semantic_state"]["replan_requested"] is True
    assert replan_packet["semantic_state"]["hypotheses"] == ["the service contract may be stale"]
    assert replan_packet["semantic_state"]["interrupt_reason"] == "replan_requested"

    blocked_control_plane = initialize_control_plane(
        state,
        state.task_prompt,
        {
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "required_artifact_paths": ["run_header.json"],
        },
        route_manifest,
    )
    blocked_completion = {
        "control_plane_update": {
            "semantic_state": {
                "blocked_reason": "waiting on external readiness evidence",
                "summary": "Blocked until the readiness evidence lands.",
                "evidence_targets": ["readiness evidence"],
                "confidence": "low",
            }
        }
    }
    blocked_proposal = extract_model_state_update(blocked_completion)
    blocked_applied = apply_model_state_update(blocked_control_plane, blocked_proposal, receipt_id="run-model-interrupt-step0002")
    assert blocked_applied["status"] == "accepted"
    blocked_interrupt = detect_interrupt(blocked_applied["control_plane"], state, {"completion": {"text": "", "tool_calls": []}})
    blocked_packet = build_interrupt_packet(blocked_interrupt, blocked_applied["control_plane"], state)
    assert blocked_interrupt["interrupt_reason"] == "model_blocked"
    assert blocked_packet["semantic_state"]["blocked_reason"] == "waiting on external readiness evidence"
    assert blocked_packet["semantic_state"]["evidence_targets"] == ["readiness evidence"]
    assert blocked_packet["semantic_state"]["interrupt_reason"] == "model_blocked"


def test_control_plane_compaction_summary_records_model_summary_and_falls_back_for_invalid_summary(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for filename in ("run_header.json", "run_events.jsonl", "route_manifest.json"):
        (workspace / filename).write_text("{}", encoding="utf-8")
    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    history_seed = [{"role": "user", "content": f"history {index}"} for index in range(31)]
    base_env = {
        "run_id": "run-compaction",
        "task_id": "task-compaction",
        "cwd": str(workspace),
        "workspace_root": str(workspace),
        "task_prompt": "repair the harness with compaction",
        "variant_id": "active_evidence_kernel_control_plane_context_v1",
    }

    accepted_model = _ScriptedModel(
        [
            {
                "text": "",
                "tool_calls": [],
                "compaction_summary": {
                    "summary": "Model compaction summary",
                    "artifact_refs": ["run_header.json"],
                    "discoveries": ["history pressure triggered compaction"],
                    "hypotheses": ["the recent suffix is enough to keep the task on track"],
                    "evidence_targets": ["run_events.jsonl"],
                    "candidate_next_checks": ["continue"],
                    "subtasks": ["preserve the recent receipt suffix"],
                    "open_questions": ["which evidence remains open?"],
                    "next_action": "continue",
                    "blocked_reason": "none",
                    "confidence": "medium",
                    "proposed_success_criteria": ["finish only after freshness gates pass"],
                },
            },
            {
                "text": "{\"finish_claim\":true}",
                "tool_calls": [],
                "finish_claim": True,
            },
        ]
    )
    accepted_result = run_loop(
        model=accepted_model,
        tools={},
        context={
            "history": list(history_seed),
            "manage_history": lambda history, observation: [*history, observation],
            "env_info": dict(base_env),
            "task_prompt": base_env["task_prompt"],
            "working_context_pack": {"open_obligations": {}},
            "workspace_state": {
                "cwd": str(workspace),
                "workspace_root": str(workspace),
                "task_prompt": base_env["task_prompt"],
                "required_artifact_paths": ["run_header.json", "run_events.jsonl", "route_manifest.json"],
            },
            "route_manifest": route_manifest,
        },
        max_steps=1,
        tool_definitions=[],
        route_manifest=route_manifest,
        workspace_state={
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "task_prompt": base_env["task_prompt"],
            "required_artifact_paths": ["run_header.json", "run_events.jsonl", "route_manifest.json"],
        },
    )

    accepted_event_types = [event["event_type"] for event in accepted_result["control_plane_events"]]
    assert accepted_result["status"] == "completed"
    assert accepted_result["control_plane_state"]["last_model_compaction_summary_status"] == "accepted"
    assert accepted_result["control_plane_state"]["last_model_compaction_summary"]["summary"] == "Model compaction summary"
    assert accepted_result["control_plane_state"]["last_model_compaction_summary"]["hypotheses"] == [
        "the recent suffix is enough to keep the task on track"
    ]
    assert accepted_result["control_plane_state"]["semantic_state"]["compaction_summary"]["source"] == "model"
    assert accepted_result["control_plane_state"]["semantic_state"]["compaction_summary"]["blocked_reason"] == "none"
    assert "kernel_compaction_boundary" in accepted_event_types
    assert "control_plane_state_updated" in accepted_event_types

    invalid_model = _ScriptedModel(
        [
            {
                "text": "",
                "tool_calls": [],
                "compaction_summary": {
                    "summary": "Invalid compaction summary",
                },
            },
            {
                "text": "{\"finish_claim\":true}",
                "tool_calls": [],
                "finish_claim": True,
            },
        ]
    )
    fallback_result = run_loop(
        model=invalid_model,
        tools={},
        context={
            "history": list(history_seed),
            "manage_history": lambda history, observation: [*history, observation],
            "env_info": dict(base_env),
            "task_prompt": base_env["task_prompt"],
            "working_context_pack": {"open_obligations": {}},
            "workspace_state": {
                "cwd": str(workspace),
                "workspace_root": str(workspace),
                "task_prompt": base_env["task_prompt"],
                "required_artifact_paths": ["run_header.json", "run_events.jsonl", "route_manifest.json"],
            },
            "route_manifest": route_manifest,
        },
        max_steps=1,
        tool_definitions=[],
        route_manifest=route_manifest,
        workspace_state={
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "task_prompt": base_env["task_prompt"],
            "required_artifact_paths": ["run_header.json", "run_events.jsonl", "route_manifest.json"],
        },
    )

    fallback_event_types = [event["event_type"] for event in fallback_result["control_plane_events"]]
    assert fallback_result["control_plane_state"]["last_model_compaction_summary_status"] == "fallback"
    assert fallback_result["control_plane_state"]["last_model_compaction_summary"]["source"] == "deterministic_fallback"
    assert "kernel_compaction_failed" in fallback_event_types
    assert finish_claim_requires_gate({"text": "explicit finish"}, fallback_result["control_plane_state"], KernelState(
        run_id="run-compaction",
        task_id="task-compaction",
        workspace_root=workspace,
        cwd=str(workspace),
        task_prompt=base_env["task_prompt"],
    )) is False


def test_active_kernel_recovery_and_context_pack_capture_failure_and_compress_receipts(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run1", task_id="task1", workspace_root=workspace, cwd=str(workspace), task_prompt="repair")
    kernel = ActiveEvidenceKernel(state=state)

    for index in range(3):
        kernel.state.note_receipt(
            build_receipt(
                receipt_id=f"r{index + 1:04d}",
                action_id=f"run1-a{index + 1:04d}",
                action_type="command",
                tool_name="raw_bash",
                command=f"echo {index} > f{index}.txt",
                cwd=str(workspace),
                exit_code=0,
                reason_code="tool_success",
                stdout="",
                stderr="",
                changed_files=[f"f{index}.txt"],
            )
        )

    failure = kernel.after_tool_result(
        tool_call={"name": "raw_bash", "arguments": {"command": "missing_command"}},
        tool_result={
            "tool_name": "raw_bash",
            "command": "missing_command",
            "exit_code": 127,
            "stdout": "",
            "stderr": "command not found",
            "timed_out": False,
            "reason_code": "tool_runtime_nonzero_exit",
        },
        cwd=str(workspace),
    )

    assert failure["failure_signal"]["failure_class"] == "command_not_found"
    assert kernel.state.recovery_card["failure_signature"] == failure["recovery_signal"]["failure_signature"]
    assert kernel.state.failure_signature_counts[failure["recovery_signal"]["failure_signature"]] == 1
    kernel.state.verifier_status = {"status": "fail", "reason_codes": ["verification_failed"], "output_summary": "missing"}
    pack = build_context_pack(kernel.state, max_recent_receipts=2)

    assert pack["compression"]["total_receipt_count"] == 4
    assert pack["compression"]["recent_receipt_count"] == 2
    assert pack["compression"]["omitted_receipt_count"] == 2
    assert pack["verifier_state"]["status"] == "fail"
    assert pack["failures"]["last_failure"]["failure_class"] == "command_not_found"
    assert pack["recent_receipts"][-1]["reason_code"] == "tool_runtime_nonzero_exit"
    assert pack["failures"]["last_failure"]["reason_code"] == "command_not_found"


def test_kernel_state_refresh_open_obligations_ignores_verifier_not_run_and_rebuilds_state(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run-ob", task_id="task-ob", workspace_root=workspace, cwd=str(workspace), task_prompt="obligations")
    state.open_obligations = {
        "verifier_gate_status": "not_run",
        "artifact_gate_missing_paths": ["stale.txt"],
        "service_not_ready": ["svc-old"],
    }
    state.verifier_status = {"status": "not_run", "reason_codes": [], "output_summary": ""}
    state.artifact_gate = {"status": "pass", "required_paths": ["run_header.json"], "missing_paths": [], "observed_hashes": {}}
    state.service_registry = {}
    state.process_registry = {}

    obligations = state.refresh_open_obligations()

    assert obligations == {}
    assert state.open_obligations == {}


def test_active_kernel_no_tool_claim_with_open_obligations_is_not_governed_pass(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run2", task_id="task2", workspace_root=workspace, cwd=str(workspace), task_prompt="claim")
    workspace_state = {
        "model_claimed_done": True,
        "execution_status": "completed",
        "verifier_artifact_present": False,
        "required_artifact_paths": ["missing.txt"],
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "verifier_status": {"status": "pass", "reason_codes": [], "output_summary": "ok"},
        "active_kernel_state": state.to_dict(),
        "open_obligations": {"stale_facts": ["missing.txt"]},
    }

    result = finalize_governed_gate(
        execution_result={"status": "completed", "active_kernel_state": state.to_dict(), "workspace_state": workspace_state},
        workspace_state=workspace_state,
    )

    assert result["governed_status"] == "ungoverned_model_claim"
    assert result["final_verdict"] == "unresolved"
    assert workspace_state["verification_governed_status"] == "ungoverned_model_claim"


def test_active_kernel_verifier_failure_blocks_governed_pass_and_is_preserved(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run2b", task_id="task2b", workspace_root=workspace, cwd=str(workspace), task_prompt="verify")
    state.verifier_status = {"status": "fail", "reason_codes": ["verifier_failed"], "output_summary": "mismatch"}
    state.artifact_gate = {"status": "pass", "required_paths": ["run_header.json"], "missing_paths": [], "observed_hashes": {}}
    state.refresh_open_obligations()
    pack = build_context_pack(state)
    assert pack["verifier_state"]["status"] == "fail"
    assert pack["verifier_state"]["reason_codes"] == ["verifier_failed"]

    workspace_state = {
        "model_claimed_done": True,
        "execution_status": "completed",
        "verifier_artifact_present": True,
        "required_artifact_paths": ["run_header.json"],
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "verifier_status": state.verifier_status,
        "service_status": {"status": "unknown", "reason_codes": [], "output_summary": ""},
        "native_tool_status": {"status": "shell_only", "reason_codes": [], "output_summary": ""},
        "active_kernel_state": state.to_dict(),
        "open_obligations": {},
    }

    result = finalize_governed_gate(
        execution_result={"status": "completed", "active_kernel_state": state.to_dict(), "workspace_state": workspace_state},
        workspace_state=workspace_state,
    )

    assert result["governed_status"] == "verifier_failed"
    assert result["final_verdict"] == "fail"
    assert "verifier_failed" in result["reason_codes"]


def test_active_kernel_missing_required_artifact_yields_artifact_gate_failed(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run2c", task_id="task2c", workspace_root=workspace, cwd=str(workspace), task_prompt="artifact")
    workspace_state = {
        "model_claimed_done": True,
        "execution_status": "completed",
        "verifier_artifact_present": False,
        "required_artifact_paths": ["missing.txt"],
        "artifact_status": {"status": "fail", "reason_codes": ["artifact_gate_failed"], "output_summary": ""},
        "verifier_status": {"status": "pass", "reason_codes": [], "output_summary": "ok"},
        "service_status": {"status": "unknown", "reason_codes": [], "output_summary": ""},
        "native_tool_status": {"status": "shell_only", "reason_codes": [], "output_summary": ""},
        "active_kernel_state": state.to_dict(),
        "open_obligations": {"artifact_gate_missing_paths": ["missing.txt"]},
    }

    result = finalize_governed_gate(
        execution_result={"status": "completed", "active_kernel_state": state.to_dict(), "workspace_state": workspace_state},
        workspace_state=workspace_state,
    )

    assert result["governed_status"] == "artifact_gate_failed"
    assert result["final_verdict"] == "fail"
    assert "artifact_gate_failed" in result["reason_codes"]


def test_active_kernel_report_provenance_requires_solver_visible_readback(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run2d", task_id="task2d", workspace_root=workspace, cwd=str(workspace), task_prompt="provenance")
    state.note_receipt(
        build_receipt(
            receipt_id="r0001",
            action_id="run2d-a0001",
            action_type="command",
            tool_name="raw_bash",
            command="python3 - <<'PY'\nfrom pathlib import Path\nPath('candidate/readiness_receipt.json').write_text('{\"ok\": true}')\nPY",
            cwd=str(workspace),
            exit_code=0,
            reason_code="tool_success",
            stdout="",
            stderr="",
            changed_files=["candidate/readiness_receipt.json"],
        )
    )

    assert state.provenance_status["status"] == "fail"
    assert state.open_obligations["report_provenance_missing"] == ["candidate/readiness_receipt.json"]

    state.note_receipt(
        build_receipt(
            receipt_id="r0002",
            action_id="run2d-a0002",
            action_type="command",
            tool_name="raw_bash",
            command="cat candidate/readiness_receipt.json",
            cwd=str(workspace),
            exit_code=0,
            reason_code="tool_success",
            stdout='{"ok": true}\n',
            stderr="",
        )
    )

    assert state.provenance_status["status"] == "pass"
    assert "report_provenance_missing" not in state.open_obligations


def test_active_kernel_finalize_blocks_on_provenance_gaps_for_report_like_artifacts(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run2e", task_id="task2e", workspace_root=workspace, cwd=str(workspace), task_prompt="provenance-final")
    state.note_receipt(
        build_receipt(
            receipt_id="r0001",
            action_id="run2e-a0001",
            action_type="command",
            tool_name="raw_bash",
            command="python3 - <<'PY'\nfrom pathlib import Path\nPath('candidate/patch_manifest.json').write_text('{\"ok\": true}')\nPY",
            cwd=str(workspace),
            exit_code=0,
            reason_code="tool_success",
            stdout="",
            stderr="",
            changed_files=["candidate/patch_manifest.json"],
        )
    )

    workspace_state = {
        "model_claimed_done": True,
        "execution_status": "completed",
        "verifier_artifact_present": True,
        "required_artifact_paths": ["run_header.json"],
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "provenance_status": dict(state.provenance_status),
        "verifier_status": {"status": "pass", "reason_codes": [], "output_summary": "ok"},
        "service_status": {"status": "unknown", "reason_codes": [], "output_summary": ""},
        "native_tool_status": {"status": "shell_only", "reason_codes": [], "output_summary": ""},
        "active_kernel_state": state.to_dict(),
        "open_obligations": dict(state.open_obligations),
    }

    result = finalize_governed_gate(
        execution_result={"status": "completed", "active_kernel_state": state.to_dict(), "workspace_state": workspace_state},
        workspace_state=workspace_state,
    )

    assert result["governed_status"] == "provenance_gate_failed"
    assert result["final_verdict"] == "fail"
    assert "report_provenance_missing" in result["reason_codes"]


def test_active_kernel_verifier_gate_passes_for_clean_completed_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run-verifier", task_id="task-verifier", workspace_root=workspace, cwd=str(workspace), task_prompt="verify")
    state.artifact_gate = {
        "status": "pass",
        "required_paths": ["run_header.json"],
        "missing_paths": [],
        "observed_hashes": {},
    }
    state.verifier_status = {"status": "not_run", "reason_codes": [], "output_summary": ""}
    state.refresh_open_obligations()

    workspace_state = {
        "model_claimed_done": True,
        "execution_status": "completed",
        "verifier_artifact_present": True,
        "required_artifact_paths": ["run_header.json"],
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "verifier_status": dict(state.verifier_status),
        "service_status": {"status": "unknown", "reason_codes": [], "output_summary": ""},
        "native_tool_status": {"status": "shell_only", "reason_codes": [], "output_summary": ""},
        "active_kernel_state": state.to_dict(),
        "open_obligations": dict(state.open_obligations),
    }

    verified = run_verifier_gate_check("clean", workspace_state)

    assert verified is True


def test_active_kernel_preserves_first_verified_success_when_later_state_regresses(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run-success", task_id="task-success", workspace_root=workspace, cwd=str(workspace), task_prompt="preserve first success")
    state.note_receipt(
        build_receipt(
            receipt_id="r0001",
            action_id="run-success-a0001",
            action_type="command",
            tool_name="raw_bash",
            command="python3 - <<'PY'\nfrom pathlib import Path\nPath('candidate/output.json').write_text('{\"preflight_success\": true}\\n')\nPY",
            cwd=str(workspace),
            exit_code=0,
            reason_code="tool_success",
            stdout="",
            stderr="",
            changed_files=["candidate/output.json"],
        )
    )
    state.artifact_registry = {
        "candidate/output.json": {
            "path": "candidate/output.json",
            "exists": True,
            "size_bytes": 25,
            "sha256": "old-hash",
            "suffix": ".json",
            "type_guess": "json",
            "origin_receipt_id": "r0001",
            "last_seen_receipt_id": "r0001",
            "generated": True,
            "freshness": "generated",
        }
    }
    state.artifact_gate = {
        "status": "pass",
        "reason_codes": [],
        "required_paths": ["candidate/output.json"],
        "missing_paths": [],
        "empty_paths": [],
        "observed_hashes": {"candidate/output.json": "old-hash"},
    }

    kernel = ActiveEvidenceKernel(state=state)
    workspace_state = {
        "model_claimed_done": False,
        "execution_status": "in_progress",
        "verifier_artifact_present": True,
        "required_artifact_paths": ["candidate/output.json"],
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "verifier_status": {"status": "not_run", "reason_codes": [], "output_summary": ""},
        "service_status": {"status": "unknown", "reason_codes": [], "output_summary": ""},
        "native_tool_status": {"status": "shell_only", "reason_codes": [], "output_summary": ""},
        "active_kernel_state": state.to_dict(),
        "open_obligations": dict(state.open_obligations),
    }

    assert kernel.run_verifier_gate("clean", workspace_state) is True
    assert state.first_verified_success["receipt_id"] == "r0001"
    assert state.first_verified_success["artifact_registry_summary"]["recent_artifacts"][0]["sha256"] == "old-hash"

    state.artifact_registry["candidate/output.json"]["sha256"] = "new-hash"
    state.artifact_registry["candidate/output.json"]["last_seen_receipt_id"] = "r0002"
    state.verifier_status = {"status": "fail", "reason_codes": ["verifier_failed"], "output_summary": "candidate regressed"}
    state.refresh_open_obligations()
    state.refresh_evidence_capsule()

    regression_workspace_state = {
        "model_claimed_done": True,
        "execution_status": "completed",
        "verifier_artifact_present": True,
        "required_artifact_paths": ["candidate/output.json"],
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "verifier_status": dict(state.verifier_status),
        "service_status": {"status": "unknown", "reason_codes": [], "output_summary": ""},
        "native_tool_status": {"status": "shell_only", "reason_codes": [], "output_summary": ""},
        "active_kernel_state": state.to_dict(),
        "open_obligations": dict(state.open_obligations),
    }

    result = kernel.finalize(
        execution_result={"status": "completed", "active_kernel_state": state.to_dict(), "workspace_state": regression_workspace_state},
        workspace_state=regression_workspace_state,
        verified=True,
    )

    assert result["governed_status"] != "governed_pass"
    assert "verified_success_overwritten" in result["reason_codes"]
    assert result["evidence_bundle"]["active_kernel_state"]["first_verified_success"]["artifact_registry_summary"]["recent_artifacts"][0]["sha256"] == "old-hash"
    assert result["evidence_bundle"]["active_kernel_state"]["verified_success_regression"]["status"] == "fail"


def test_active_kernel_path_hints_ignore_shell_noise_but_keep_real_paths(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run-path", task_id="task-path", workspace_root=workspace, cwd=str(workspace), task_prompt="paths")

    state.note_receipt(
        build_receipt(
            receipt_id="r0001",
            action_id="run-path-a0001",
            action_type="command",
            tool_name="raw_bash",
            command="python3 visible_verifier.py --candidate-dir candidate",
            cwd=str(workspace),
            exit_code=0,
            reason_code="tool_success",
            stdout="ok",
            stderr="",
        )
    )

    assert "visible_verifier.py" in state.files_read
    assert "python3" not in state.files_read
    assert "--candidate-dir" not in state.files_read


def test_active_kernel_long_heredoc_failure_uses_bounded_command_fingerprint_and_safe_artifact_paths(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run-unsafe-command", task_id="task-unsafe-command", workspace_root=workspace, cwd=str(workspace), task_prompt="fingerprint")
    kernel = ActiveEvidenceKernel(state=state)
    long_payload = "x" * 5000
    long_command = (
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        f"payload = {long_payload!r}\n"
        "Path('candidate/readiness_receipt.json').write_text('{\"ok\": true}\\n')\n"
        "PY"
    )

    result = kernel.after_tool_result(
        tool_call={"name": "raw_bash", "arguments": {"command": long_command}},
        tool_result={
            "tool_name": "raw_bash",
            "command": long_command,
            "exit_code": 127,
            "stdout": "",
            "stderr": "command not found",
            "timed_out": False,
            "reason_code": "tool_runtime_nonzero_exit",
            "changed_files": ["candidate/readiness_receipt.json"],
        },
        cwd=str(workspace),
    )

    failure_signal = result["failure_signal"]
    recovery_signal = result["recovery_signal"]
    assert len(failure_signal["failure_signature"]) < 220
    assert "\n" not in failure_signal["failure_signature"]
    assert failure_signal["command_digest"] == recovery_signal["command_digest"]
    assert failure_signal["command_excerpt"] == recovery_signal["command_excerpt"]
    assert failure_signal["command_length"] == recovery_signal["command_length"]
    assert len(failure_signal["command_digest"]) == 12
    assert len(failure_signal["command_excerpt"]) <= 96
    assert failure_signal["command_excerpt"].startswith("python3 - <<'PY'")
    assert "candidate/readiness_receipt.json" in kernel.state.artifact_registry
    assert all("\n" not in key and "python3" not in key for key in kernel.state.artifact_registry)


def test_active_kernel_orient_mentions_verifier_provenance_discipline():
    payload = orient("repair the task", {"cwd": "/workspace", "workspace_root": "/workspace", "run_id": "run-orient"})
    content = payload["messages"][0]["content"]

    lowered = content.lower()
    assert "visible verifier success is necessary but not sufficient" in lowered
    assert "report and receipt fields" in content
    assert "provenance" in lowered


def test_active_kernel_recomputes_artifact_state_before_finalization_when_candidate_created_during_execution(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def write_candidate(_call):  # type: ignore[no-untyped-def]
        candidate_dir = workspace / "candidate"
        candidate_dir.mkdir(exist_ok=True)
        (candidate_dir / "result.json").write_text('{"ok": true}\n', encoding="utf-8")
        return {
            "tool_name": "raw_bash",
            "command": "python3 - <<'PY'\nfrom pathlib import Path\nPath('candidate').mkdir(exist_ok=True)\nPath('candidate/result.json').write_text('{\"ok\": true}\\n', encoding='utf-8')\nPY",
            "exit_code": 0,
            "stdout": "created candidate/result.json\n",
            "stderr": "",
            "timed_out": False,
            "reason_code": "tool_success",
            "changed_files": ["candidate/result.json"],
            "mutation_observed": True,
        }

    model = _ScriptedModel(
        [
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "raw_bash",
                        "arguments": {
                            "command": "python3 - <<'PY'\nfrom pathlib import Path\nPath('candidate').mkdir(exist_ok=True)\nPath('candidate/result.json').write_text('{\"ok\": true}\\n', encoding='utf-8')\nPY",
                        },
                    }
                ],
            },
            {
                "text": "{\"status\":\"pass\"}",
                "tool_calls": [],
            },
        ]
    )
    route_manifest = build_packet04_route_manifest("active_evidence_kernel_v1", scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    route_manifest["required_artifact_paths"] = ["candidate/result.json"]
    result = run_loop(
        model=model,
        tools={"raw_bash": write_candidate},
        context={
            "history": [],
            "manage_history": lambda history, observation: [*history, dict(observation)],
            "env_info": {
                "cwd": str(workspace),
                "task_id": "task-artifact-refresh",
                "run_id": "run-artifact-refresh",
                "task_prompt": "create the candidate artifact",
                "workspace_root": str(workspace),
                "variant_id": "active_evidence_kernel_v1",
            },
            "workspace_state": {"cwd": str(workspace)},
            "route_manifest": route_manifest,
            "task_prompt": "create the candidate artifact",
        },
        max_steps=3,
        tool_definitions=[
            {
                "name": "raw_bash",
                "input_schema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ],
        route_manifest=route_manifest,
        workspace_state={"cwd": str(workspace)},
    )

    assert result["workspace_state"]["artifact_status"]["status"] == "pass"
    assert result["workspace_state"]["verifier_artifact_present"] is True
    assert result["workspace_state"]["active_kernel_state"]["artifact_gate"]["status"] == "pass"
    assert result["workspace_state"]["open_obligations"] == {}


def test_run_reference_baseline_self_certifies_candidate_artifact_created_during_execution(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()

    monkeypatch.setattr(
        "runner.agent.resolve_model_client",
        lambda _route, **_kwargs: _ScriptedModel(
            [
                {
                    "text": "",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "name": "raw_bash",
                            "arguments": {
                                "command": "python3 - <<'PY'\nfrom pathlib import Path\nPath('candidate').mkdir(exist_ok=True)\nPath('candidate/result.json').write_text('{\"ok\": true}\\n', encoding='utf-8')\nPY",
                            },
                        }
                    ],
                },
                {
                    "text": "{\"status\":\"pass\"}",
                    "tool_calls": [],
                },
            ]
        ),
    )

    from runner.packet04_route_manifest import load_runtime_callables as real_load_runtime_callables

    def fake_load_runtime_callables(manifest):  # type: ignore[no-untyped-def]
        callables = real_load_runtime_callables(manifest)

        def verification(task_prompt, workspace_state):  # type: ignore[no-untyped-def]
            assert workspace_state["artifact_status"]["status"] == "pass"
            assert workspace_state["verifier_artifact_present"] is True
            assert workspace_state["active_kernel_state"]["artifact_gate"]["status"] == "pass"
            workspace_state["verified"] = True
            workspace_state["verifier_status"] = {
                "status": "pass",
                "reason_codes": [],
                "output_summary": "verification_gate_pass",
            }
            workspace_state["verification_reason_codes"] = []
            workspace_state["verification_governed_status"] = "governed_pass"
            workspace_state["verification_final_verdict"] = "pass"
            return True

        callables["verification"] = verification
        return callables

    monkeypatch.setattr("runner.agent.load_runtime_callables", fake_load_runtime_callables)

    route_manifest = build_packet04_route_manifest("active_evidence_kernel_v1", scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    route_manifest["required_artifact_paths"] = ["candidate/result.json"]
    result = run_reference_baseline(
        run_id="run-artifact-refresh",
        run_dir=run_dir,
        task_id="task-artifact-refresh",
        task_prompt="create the candidate artifact",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        route_manifest=route_manifest,
        seed_id="active_evidence_kernel_v1",
        max_steps=3,
        timeout_sec=10,
    )

    assert result["verified"] is True
    assert result["verification"]["verified"] is True
    assert result["evidence_kernel"]["verifier_gate"]["status"] == "pass"
    assert result["evidence_kernel"]["artifact_gate"]["status"] == "pass"
    completion_events = [event for event in result["run_events"] if event["event_type"] == "model_completion"]
    assert completion_events
    attribution = completion_events[0]["payload"]["details"].get("context_token_attribution")
    assert attribution["schema_version"] == "model_input_context_attribution_estimate.v1"
    assert attribution["bucket_tokens"]["task_prompt"] > 0
    assert "context_pack" in attribution["bucket_tokens"]


def test_run_reference_baseline_emits_control_plane_events_and_artifacts(monkeypatch, tmp_path):
    run_dir = tmp_path / "run-control-plane"
    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_control_plane_context_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    model = _ScriptedModel(
        [
            {
                "text": "explicit governed finish",
                "tool_calls": [],
                "finish_claim": True,
            }
        ]
    )

    monkeypatch.setattr("runner.agent.resolve_model_client", lambda _route, **_kwargs: model)

    result = run_reference_baseline(
        run_id="run-control-plane",
        run_dir=run_dir,
        task_id="task-control-plane",
        task_prompt="repair the harness with governed finish",
        benchmark_family="smoke",
        model_route=LocalStubModelClient.create(response_text="ignored").route,
        route_manifest=route_manifest,
        seed_id="active_evidence_kernel_control_plane_context_v1",
        max_steps=2,
        timeout_sec=10,
    )

    events = result["run_events"]
    event_types = [event["event_type"] for event in events]
    assert "control_plane_state_initialized" in event_types
    assert "control_plane_working_window" in event_types
    assert "kernel_interrupt_packet" in event_types
    assert "kernel_finish_claim" in event_types
    assert "control_plane_state_updated" in event_types
    assert "kernel_finish_gate_result" in event_types
    assert result["execution"]["status"] == "completed"
    assert result["execution"]["control_plane_state"]["route_variant_id"] == "active_evidence_kernel_control_plane_context_v1"
    assert result["execution"]["control_plane_state"]["verification_state"]["final_verdict"] == result["execution"]["final_verdict"]
    assert result["execution"]["control_plane_working_window"]["working_window_version"] == "control_plane_working_window.v1"
    assert (run_dir / "control_plane_state.json").exists()
    assert (run_dir / "control_plane_working_window.json").exists()
    assert result["control_plane_artifacts"]["control_plane_state"] == str(run_dir / "control_plane_state.json")
    assert result["control_plane_artifacts"]["control_plane_working_window"] == str(run_dir / "control_plane_working_window.json")


def test_authoritative_artifact_probe_clears_stale_kernel_artifact_obligation():
    workspace_state = {
        "verifier_artifact_present": False,
        "required_artifact_paths": ["candidate"],
        "artifact_status": {
            "status": "fail",
            "required_paths": ["candidate"],
            "missing_paths": ["candidate"],
            "reason_codes": ["artifact_gate_failed"],
        },
        "open_obligations": {"artifact_gate_missing_paths": ["candidate"]},
        "active_kernel_state": {
            "artifact_gate": {
                "status": "fail",
                "required_paths": ["candidate"],
                "missing_paths": ["candidate"],
            },
            "open_obligations": {"artifact_gate_missing_paths": ["candidate"]},
        },
    }
    execution_result = {
        "workspace_state": {
            "verifier_artifact_present": False,
            "artifact_status": {"status": "fail", "missing_paths": ["candidate"]},
            "open_obligations": {"artifact_gate_missing_paths": ["candidate"]},
            "active_kernel_state": {
                "artifact_gate": {"status": "fail", "missing_paths": ["candidate"]},
                "open_obligations": {"artifact_gate_missing_paths": ["candidate"]},
            },
        },
        "active_kernel_state": {
            "artifact_gate": {"status": "fail", "missing_paths": ["candidate"]},
            "open_obligations": {"artifact_gate_missing_paths": ["candidate"]},
        },
        "open_obligations": {"artifact_gate_missing_paths": ["candidate"]},
    }

    _apply_authoritative_artifact_probe(
        workspace_state=workspace_state,
        execution_result=execution_result,
        artifact_probe={
            "status": "pass",
            "required_paths": ["candidate"],
            "missing_paths": [],
            "hash_algorithm": "sha256",
            "observed_hashes": {"candidate": "dir"},
        },
    )

    assert workspace_state["verifier_artifact_present"] is True
    assert workspace_state["artifact_status"]["status"] == "pass"
    assert workspace_state["open_obligations"] == {}
    assert workspace_state["active_kernel_state"]["artifact_gate"]["status"] == "pass"
    assert workspace_state["active_kernel_state"]["open_obligations"] == {}
    assert execution_result["workspace_state"]["artifact_status"]["status"] == "pass"
    assert execution_result["workspace_state"]["open_obligations"] == {}
    assert execution_result["open_obligations"] == {}


def test_active_kernel_run_loop_finishes_without_spurious_replan_for_verifier_not_run(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for filename in ("run_header.json", "run_events.jsonl", "route_manifest.json"):
        (workspace / filename).write_text("{}", encoding="utf-8")

    model = _ScriptedModel(
        [
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "raw_bash",
                        "arguments": {"command": "echo done"},
                    }
                ],
            },
            {
                "text": "{\"status\":\"pass\"}",
                "tool_calls": [],
            },
        ]
    )
    route_manifest = build_packet04_route_manifest("active_evidence_kernel_v1", scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    result = run_loop(
        model=model,
        tools={
            "raw_bash": lambda _call: {
                "tool_name": "raw_bash",
                "command": "echo done",
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "reason_code": "tool_success",
            }
        },
        context={
            "history": [],
            "manage_history": lambda history, observation: [*history, dict(observation)],
            "env_info": {
                "cwd": str(workspace),
                "task_id": "task-loop",
                "run_id": "run-loop",
                "task_prompt": "finish cleanly",
                "workspace_root": str(workspace),
                "variant_id": "active_evidence_kernel_v1",
            },
            "workspace_state": {"cwd": str(workspace)},
            "route_manifest": route_manifest,
            "task_prompt": "finish cleanly",
        },
        max_steps=3,
        tool_definitions=[
            {
                "name": "raw_bash",
                "input_schema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ],
        route_manifest=route_manifest,
        workspace_state={"cwd": str(workspace)},
    )

    assert len(model.calls) == 2
    assert result["status"] == "completed"
    assert result["steps"][-1]["decision"]["action"] == "finalize"
    assert result["open_obligations"] == {}


def test_active_kernel_run_loop_treats_repeated_layer2_unclear_as_failure_shaped_termination(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for filename in ("run_header.json", "run_events.jsonl", "route_manifest.json"):
        (workspace / filename).write_text("{}", encoding="utf-8")

    route_manifest = {
        "variant_id": "layer2_audit_regression_v1",
        "feature_flags": {
            "layer2_success_audit": True,
        },
    }
    audit_response = {
        "text": (
            '{'
            '"verdict":"UNCLEAR",'
            '"confidence":"medium",'
            '"mismatches":["required_artifacts"],'
            '"missing_evidence":["artifact_refs"],'
            '"reason_codes":["missing_artifact_evidence"],'
            '"repair_instruction":"artifact refs are missing"'
            "}"
        ),
        "tool_calls": [],
    }
    model = _ScriptedModel(
        [
            {"text": "", "tool_calls": [], "finish_claim": True},
            dict(audit_response),
            {"text": "", "tool_calls": [], "finish_claim": True},
            dict(audit_response),
            {"text": "", "tool_calls": [], "finish_claim": True},
            dict(audit_response),
        ]
    )
    result = run_loop(
        model=model,
        tools={},
        context={
            "history": [],
            "manage_history": lambda history, observation: [*history, dict(observation)],
            "env_info": {
                "cwd": str(workspace),
                "task_id": "task-layer2-fail",
                "run_id": "run-layer2-fail",
                "task_prompt": "finish cleanly",
                "workspace_root": str(workspace),
                "variant_id": "model_led_evidence_substrate_v1",
            },
            "workspace_state": {
                "cwd": str(workspace),
                "workspace_root": str(workspace),
                "task_prompt": "finish cleanly",
                "verifier_status": {"status": "pass", "reason_codes": [], "output_summary": "ok"},
                "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
                "provenance_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
                "verifier_artifact_present": True,
                "open_obligations": {},
                "required_artifact_paths": [],
            },
            "route_manifest": route_manifest,
            "task_prompt": "finish cleanly",
        },
        max_steps=3,
        tool_definitions=[],
        route_manifest=route_manifest,
        workspace_state={
            "cwd": str(workspace),
            "workspace_root": str(workspace),
            "task_prompt": "finish cleanly",
            "verifier_status": {"status": "pass", "reason_codes": [], "output_summary": "ok"},
            "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
            "provenance_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
            "verifier_artifact_present": True,
            "open_obligations": {},
            "required_artifact_paths": [],
        },
    )

    assert result["status"] == "max_steps_exhausted"
    assert result["governed_status"] != "governed_pass"
    assert result["final_verdict"] != "pass"
    assert "same_signature_recovery_exhausted" in result["open_obligations"]
    assert result["active_kernel_state"]["layer2_audit_state"]["status"] == "unclear"
    assert result["active_kernel_state"]["layer2_audit_state"]["verdict"] == "UNCLEAR"
    assert len(model.calls) == 6


def test_active_kernel_injects_context_pack_on_initial_turn(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured_prompt_payloads = []

    def manage_history(history, new_observation):  # type: ignore[no-untyped-def]
        observation = dict(new_observation)
        if "evidence_context_pack" in observation:
            captured_prompt_payloads.append(dict(observation))
        return [*history, observation]

    model = _ScriptedModel([{"text": "", "tool_calls": []}])
    route_manifest = dict(build_packet04_route_manifest("active_evidence_kernel_v1", scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE))
    route_manifest["required_artifact_paths"] = ["missing.txt"]
    result = run_loop(
        model=model,
        tools={
            "raw_bash": lambda _call: {
                "tool_name": "raw_bash",
                "command": "true",
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "reason_code": "tool_success",
            }
        },
        context={
            "history": [],
            "manage_history": manage_history,
            "env_info": {
                "cwd": str(workspace),
                "task_id": "task-loop",
                "run_id": "run-loop",
                "task_prompt": "finish cleanly",
                "workspace_root": str(workspace),
                "variant_id": "active_evidence_kernel_v1",
            },
            "workspace_state": {"cwd": str(workspace)},
            "route_manifest": route_manifest,
            "task_prompt": "finish cleanly",
        },
        max_steps=1,
        tool_definitions=[
            {
                "name": "raw_bash",
                "input_schema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ],
        route_manifest=route_manifest,
        workspace_state={"cwd": str(workspace)},
    )

    assert result["step_count"] >= 1
    assert captured_prompt_payloads, "expected the first turn to carry a context pack"
    pack = captured_prompt_payloads[0]["evidence_context_pack"]
    assert pack["open_obligations"]["artifact_gate_missing_paths"] == ["missing.txt"]
    assert pack["artifact_state"]["missing_paths"] == ["missing.txt"]
    assert model.calls, "expected at least one model call"
    assert any(message.get("role") == "user" for message in model.calls[0]), "expected a user input on the first model turn"


def test_active_kernel_service_not_ready_blocks_governed_pass(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run2d", task_id="task2d", workspace_root=workspace, cwd=str(workspace), task_prompt="service")
    state.service_registry["service@unknown"] = {"status": "failed", "reason_codes": ["service_not_ready"], "events": []}
    state.process_registry["service@unknown"] = {"status": "failed"}
    workspace_state = {
        "model_claimed_done": True,
        "execution_status": "completed",
        "verifier_artifact_present": True,
        "required_artifact_paths": ["run_header.json"],
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "verifier_status": {"status": "pass", "reason_codes": [], "output_summary": "ok"},
        "service_status": {"status": "not_ready", "reason_codes": ["service_not_ready"], "output_summary": "probe failed"},
        "native_tool_status": {"status": "shell_only", "reason_codes": [], "output_summary": ""},
        "active_kernel_state": state.to_dict(),
        "open_obligations": {"service_not_ready": ["service@unknown"]},
    }

    result = finalize_governed_gate(
        execution_result={"status": "completed", "active_kernel_state": state.to_dict(), "workspace_state": workspace_state},
        workspace_state=workspace_state,
    )

    assert result["governed_status"] == "service_not_ready"
    assert result["final_verdict"] == "fail"
    assert "service_not_ready" in result["reason_codes"]


def test_active_kernel_native_tool_failure_statuses_block_governed_pass(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run2e", task_id="task2e", workspace_root=workspace, cwd=str(workspace), task_prompt="native")
    state.native_tool_state["attempted_native_tool_call"] = True
    workspace_state = {
        "model_claimed_done": True,
        "execution_status": "completed",
        "verifier_artifact_present": True,
        "required_artifact_paths": ["run_header.json"],
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "verifier_status": {"status": "pass", "reason_codes": [], "output_summary": "ok"},
        "service_status": {"status": "unknown", "reason_codes": [], "output_summary": ""},
        "native_tool_status": {"status": "fail", "reason_codes": ["native_tool_contract_failed"], "output_summary": "contract_status=fail"},
        "active_kernel_state": state.to_dict(),
        "open_obligations": {"tool_contract_violations": ["r0007"]},
    }

    result = finalize_governed_gate(
        execution_result={"status": "completed", "active_kernel_state": state.to_dict(), "workspace_state": workspace_state},
        workspace_state=workspace_state,
    )

    assert result["governed_status"] == "native_tool_contract_failed"
    assert result["final_verdict"] == "fail"
    assert "native_tool_contract_failed" in result["reason_codes"]


def test_native_tool_runtime_unavailable_is_reported_truthfully():
    sandbox = type(
        "_Sandbox",
        (),
        {
            "native_tool_definitions": [
                {
                    "name": "fake_native",
                    "description": "native tool",
                    "input_schema": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                    },
                }
            ]
        },
    )()

    result = execute_tool_call({"name": "fake_native", "arguments": {"value": "x"}}, sandbox)

    assert result["reason_code"] == "native_tool_runtime_unavailable"
    assert result["native_tool_runtime_active"] is False
    assert result["tool_name"] == "fake_native"


def test_native_tool_getter_prefers_native_definitions_over_raw_bash(monkeypatch):
    monkeypatch.setattr(
        "runner.kernel_native_tools.get_raw_bash_tools",
        lambda: [
            {
                "name": "raw_bash",
                "description": "shell",
                "input_schema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ],
    )

    tools = get_tools(
        route_manifest={
            "native_tool_definitions": [
                {
                    "name": "fake_native",
                    "description": "native tool",
                    "input_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
                }
            ]
        }
    )

    assert [tool["name"] for tool in tools] == ["fake_native"]


def test_native_tool_runtime_spec_resolves_bfcl_style_callable(tmp_path):
    module_root = tmp_path / "native_mod"
    module_root.mkdir()
    (module_root / "demo_api.py").write_text(
        "\n".join(
            [
                "class DemoAPI:",
                "    def __init__(self):",
                "        self.loaded = None",
                "",
                "    def _load_scenario(self, initial_config, long_context=False):",
                "        self.loaded = {'initial_config': initial_config, 'long_context': long_context}",
                "",
                "    def do_it(self, value):",
                "        return {",
                "            'result_class': 'success',",
                "            'stdout': f'done:{value}',",
                "            'stderr': '',",
                "            'exit_code': 0,",
                "        }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    sandbox = type("_Sandbox", (), {})()
    sandbox.native_tool_definitions = [
        {
            "name": "do_it",
            "description": "demo",
            "input_schema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            "runtime_spec": {
                "runtime_kind": "bfcl_api_method",
                "module_name": "demo_api",
                "class_name": "DemoAPI",
                "method_name": "do_it",
                "import_root": str(module_root),
                "initial_config": {"seed": 1},
                "long_context": False,
            },
        }
    ]

    result = execute_tool_call({"name": "do_it", "arguments": {"value": "x"}}, sandbox)

    assert result["reason_code"] == "native_tool_runtime_success"
    assert result["native_tool_runtime_active"] is True
    assert result["tool_name"] == "do_it"
    assert result["stdout"] == "done:x"


def test_active_kernel_service_tracking_uses_command_port(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run3", task_id="task3", workspace_root=workspace, cwd=str(workspace), task_prompt="service")
    kernel = ActiveEvidenceKernel(state=state)

    update = kernel.after_tool_result(
        tool_call={"name": "register_service", "arguments": {"service_name": "service@9091", "port": 9091, "pid": 4321}},
        tool_result={
            "tool_name": "register_service",
            "command": "register_service service@9091",
            "exit_code": 0,
            "stdout": "Service successfully registered",
            "stderr": "",
            "timed_out": False,
            "reason_code": "tool_success",
            "service_name": "service@9091",
            "service_status": "running",
            "service_port": 9091,
            "pid": 4321,
        },
        cwd=str(workspace),
    )

    assert update["service_update"]["service_name"] == "service@9091"
    assert kernel.state.service_registry["service@9091"]["status"] == "running"
    assert kernel.state.process_registry["service@9091"]["pid"] == 4321


def test_active_kernel_same_failure_repeats_three_times_trigger_stop():
    state = KernelState(run_id="run4", task_id="task4", workspace_root=Path("."), cwd=str(Path(".")), task_prompt="retry")

    first = handle_error(RuntimeError("command not found"), [], state=state)
    second = handle_error(RuntimeError("command not found"), [], state=state)
    third = handle_error(RuntimeError("command not found"), [], state=state)

    assert first["action"] == "replan"
    assert second["action"] == "replan"
    assert third["action"] == "stop"
    assert third["reason"] == "same_signature_recovery_exhausted"
    assert state.failure_signature_counts[third["failure_signature"]] == 3


def test_active_kernel_model_client_http_400_stops_immediately():
    state = KernelState(run_id="run-model", task_id="task-model", workspace_root=Path("."), cwd=str(Path(".")), task_prompt="retry")

    action = handle_error(
        ModelClientError(
            "azure openai request failed with status 400",
            status_code=400,
            response_body='{"error":{"message":"bad request"}}',
            error_kind="http_error",
        ),
        [],
        state=state,
    )

    assert action["action"] == "stop"
    assert action["reason"] == "invalid_due_to_environment_model_client"
    assert action["reason_code"] == "model_client_http_400"


def test_context_pack_preserves_latest_failure_and_compresses_old_receipts(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = KernelState(run_id="run5", task_id="task5", workspace_root=workspace, cwd=str(workspace), task_prompt="pack")
    state.verifier_status = {"status": "fail", "reason_codes": ["verification_failed"], "output_summary": "verifier mismatch"}
    state.artifact_gate = {"status": "fail", "required_paths": ["missing.txt"], "missing_paths": ["missing.txt"], "observed_hashes": {}}
    state.last_failure_signature = "raw_bash|missing|command_not_found|127|no_timeout"
    state.last_failure = {"failure_class": "command_not_found", "reason_code": "command_not_found"}
    state.recovery_card = {"failure_class": "command_not_found", "reason_code": "command_not_found", "failure_signature": state.last_failure_signature}
    for index in range(4):
        state.note_receipt(
            build_receipt(
                receipt_id=f"r{index + 1:04d}",
                action_id=f"run5-a{index + 1:04d}",
                action_type="command",
                tool_name="raw_bash",
                command=f"echo {index} > file{index}.txt",
                cwd=str(workspace),
                exit_code=0,
                reason_code="tool_success",
                stdout="",
                stderr="",
                changed_files=[f"file{index}.txt"],
            )
        )

    pack = build_context_pack(state, max_recent_receipts=2)
    assert pack["compression"]["total_receipt_count"] == 4
    assert pack["compression"]["recent_receipt_count"] == 2
    assert pack["compression"]["omitted_receipt_count"] == 2
    assert pack["failures"]["last_failure"]["failure_class"] == "command_not_found"
    assert pack["verifier_state"]["output_summary"] == "verifier mismatch"


def test_active_route_tool_getter_kwargs_and_native_mode_activation(monkeypatch, tmp_path):
    captured_kwargs = {}

    def fake_get_tools(**kwargs):  # type: ignore[no-untyped-def]
        captured_kwargs.update(kwargs)
        return [
            {
                "name": "raw_bash",
                "description": "shell",
                "input_schema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
            {
                "name": "fake_native",
                "description": "native tool",
                "input_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
            },
        ]

    monkeypatch.setattr("runner.kernel_native_tools.get_tools", fake_get_tools)
    monkeypatch.setattr(
        "runner.agent.resolve_model_client",
        lambda _route, **_kwargs: _ScriptedModel([{"text": "done", "tool_calls": []}]),
    )

    route_manifest = build_packet04_route_manifest("active_evidence_kernel_v1", scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    run_dir = tmp_path / "run"
    result = run_reference_baseline(
        run_id="run-active",
        run_dir=run_dir,
        task_id="task-active",
        task_prompt="use the active kernel",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        route_manifest=route_manifest,
        max_steps=1,
        timeout_sec=10,
    )

    assert captured_kwargs["cwd"] == str(run_dir.resolve())
    assert captured_kwargs["task_prompt"] == "use the active kernel"
    assert captured_kwargs["route_manifest"]["variant_id"] == "active_evidence_kernel_v1"
    assert captured_kwargs["task_id"] == "task-active"
    assert captured_kwargs["run_id"] == "run-active"
    assert result["execution"]["active_kernel_state"]["native_tool_mode_active"] is True
    assert "fake_native" in result["execution"]["active_kernel_state"]["declared_tool_names"]


def test_active_kernel_injects_context_pack_on_replan(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured_prompt_payloads = []

    def manage_history(history, new_observation):  # type: ignore[no-untyped-def]
        observation = dict(new_observation)
        if "evidence_context_pack" in observation:
            captured_prompt_payloads.append(dict(observation))
        return [*history, observation]

    model = _ScriptedModel(
        [
            {
                "text": "fail first",
                "tool_calls": [{"id": "c1", "name": "raw_bash", "arguments": {"command": "missing_command"}}],
            },
            {"text": "repair second", "tool_calls": []},
        ]
    )
    route_manifest = build_packet04_route_manifest("active_evidence_kernel_v1", scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    result = run_loop(
        model=model,
        tools={
            "raw_bash": lambda _call: {
                "tool_name": "raw_bash",
                "command": "missing_command",
                "exit_code": 127,
                "stdout": "",
                "stderr": "command not found",
                "timed_out": False,
                "reason_code": "tool_runtime_nonzero_exit",
            }
        },
        context={
            "history": [],
            "manage_history": manage_history,
            "env_info": {
                "cwd": str(workspace),
                "task_id": "task-pack",
                "run_id": "run-pack",
                "task_prompt": "use the active kernel",
                "workspace_root": str(workspace),
                "variant_id": "active_evidence_kernel_v1",
            },
            "workspace_state": {"cwd": str(workspace)},
            "route_manifest": route_manifest,
            "task_prompt": "use the active kernel",
        },
        max_steps=2,
        tool_definitions=[{"name": "raw_bash", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}],
        route_manifest=route_manifest,
        workspace_state={"cwd": str(workspace)},
    )

    assert result["step_count"] >= 1
    assert captured_prompt_payloads, "expected a replanning prompt with a context pack"
    pack = captured_prompt_payloads[-1]["evidence_context_pack"]
    assert pack["failures"]["last_failure"]["failure_class"] == "command_not_found"
    assert pack["recent_receipts"][-1]["reason_code"] == "tool_runtime_nonzero_exit"
    assert pack["verifier_state"]["status"] == "not_run"
    assert "verifier_gate_status" not in pack["open_obligations"]


def test_prune_context_packs_from_history():
    from runner.active_evidence_kernel import prune_context_packs_from_history
    history = [
        {"role": "system", "content": "Welcome\n\n[active_evidence_context_pack]\n{\"first\": 1}"},
        {"role": "user", "content": "Help me build this"},
        {"role": "assistant", "content": "Sure, let's run a tool."},
        {"role": "system", "content": "[active_evidence_context_pack]\n{\"second\": 2}"},
        {"role": "assistant", "content": "done"},
        {"role": "system", "content": "[active_evidence_context_pack]\n{\"third\": 3}"},
    ]
    pruned = prune_context_packs_from_history(history)
    assert len(pruned) == len(history)
    assert pruned[5]["content"] == "[active_evidence_context_pack]\n{\"third\": 3}"
    assert pruned[0]["content"] == "Welcome"
    assert pruned[3]["content"] == "(historical context pack omitted)"
    assert pruned[1]["content"] == "Help me build this"
    assert pruned[2]["content"] == "Sure, let's run a tool."
    assert pruned[4]["content"] == "done"

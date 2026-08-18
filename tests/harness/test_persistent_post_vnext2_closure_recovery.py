from __future__ import annotations

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.envmap_builder import build_envmap_from_task
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_context import (
    _factual_persistent_linked_history,
    compile_persistent_context,
)
from aether.context_views import submission_observation_routes
from aether.persistent_primary import persistent_primary_runtime_ir
from aether.verifier import CompletionEvidenceEntry
from aether.verify_completion_gates import _completion_record_problem


def _compiled(tmp_path):
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Produce a correct artifact.",
        workspace_root=str(tmp_path),
    )
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
    objective, eval_index = compiler.analyze_envmap(envmap)
    return compiler.compile(
        persistent_primary_runtime_ir(envmap, eval_index),
        envmap,
        objective_graph=objective,
        eval_index=eval_index,
    )


def _identity(tmp_path) -> dict[str, object]:
    return {
        "task_id": "task-closure",
        "run_id": "run-closure",
        "primary_agent_id": "primary-agent:run-closure",
        "workspace_id": str(tmp_path),
        "environment_id": "env-closure",
        "source_commit": "a" * 40,
        "source_commit_state": "provided",
        "runtime_manifest_sha256": "b" * 64,
        "runtime_manifest_state": "provided",
        "source_custody_complete": True,
        "budgets": {"max_kernel_steps": 30},
    }


def test_final_persistent_packet_keeps_factual_submission_coherence_and_exact_output_route(tmp_path) -> None:
    compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    ledger.record(Receipt(
        "step-8:verify:cmd", 8, "run_command", True, "verification passed and wrote release binary",
        state_change=True,
        payload={
            "command": "compile && ./release",
            "exit_code": 0,
            "stdout": "release_exit:0\n",
            "stdout_handle": "8:verify:stdout",
            "stdout_bytes": len("release_exit:0\n"),
            "stderr_handle": "8:verify:stderr",
            "stderr_bytes": 0,
            "modified_paths": ["release"],
        },
    ))
    ledger.record(Receipt(
        "step-8:progress", 8, "solver_progress_assessment", True, "state changed",
        payload={
            "classification": "state_changed",
            "result_receipt_ids": ["step-8:verify:cmd"],
            "progress_signals": ["state_change", "new_evidence"],
        },
    ))
    routes = submission_observation_routes(
        ledger, progress_receipt_id="step-8:progress",
    )
    assert routes == [{
        "kind": "read_output",
        "arguments": {"handle": "8:verify:stdout"},
        "source_receipt_id": "step-8:verify:cmd",
        "stream": "stdout",
        "bytes": len("release_exit:0\n"),
        "authority": "existing_execution_result_handle",
    }]
    linked_history = {
        "submission_recovery_directive": {
            "source": "submission_coherence",
            "submission_allowed": False,
            "reason_code": "unobserved_state_change",
            "detail": "latest Solver action changed task state",
            "required_next_turn_kind": "act",
            "forbidden_next_turn_kind": "submit_outcome",
            "clears_only_after": "a direct current-state observation records evidence",
            "preflight_step": 9,
            "blocked_receipt_id": "step-9:submission_coherence_blocked",
            "blocked_round": 1,
            "available_direct_observation_routes": routes,
            "record_observation_is_direct_evidence": False,
            "message": "strategy prose intentionally absent from PERSISTENT projection",
            "route_note": "generic explanatory prose intentionally absent from PERSISTENT projection",
        },
        "recent_progress": [],
    }
    packet = compile_persistent_context(compiled, ledger, linked_history)
    state = packet["submission_coherence"]
    assert state["submission_allowed"] is False
    assert state["reason_code"] == "unobserved_state_change"
    assert state["required_next_turn_kind"] == "act"
    assert state["forbidden_next_turn_kind"] == "submit_outcome"
    assert state["record_observation_is_direct_evidence"] is False
    assert state["semantic_task_action_selected"] is False
    assert state["available_direct_observation_routes"] == routes
    assert "message" not in state and "route_note" not in state
    assert "submission_recovery_directive" not in packet["linked_history"]


def test_persistent_linked_history_still_strips_generic_strategy_recovery_text() -> None:
    projected = _factual_persistent_linked_history({
        "submission_recovery_directive": {
            "reason_code": "unobserved_state_change",
            "message": "choose a recovery strategy",
        },
        "recent_progress": [{"step": 1, "summary": "real factual progress"}],
    })
    assert "submission_recovery_directive" not in projected
    assert projected["recent_progress"][0]["step"] == 1
    assert projected["persistent_context_boundary"]["kernel_strategy_guidance_exposed"] is False


def test_persistent_completed_verdict_missing_raw_clause_is_rejected_inside_completion_record_gate() -> None:
    entry = CompletionEvidenceEntry(
        requirement="first requirement",
        observed="inspection observed first requirement",
        falsification_check="counterexample would fail",
        inspection_refs=("inspection:1",),
        clause_ids=("task:a",),
        requirement_status="satisfied",
    )
    result = type("_Result", (), {"completion_evidence": (entry,)})()
    packet = {
        "task_contract": {
            "clauses": [
                {"clause_id": "task:a", "text": "first"},
                {"clause_id": "task:b", "text": "second"},
            ],
            "method_constraints": [],
        },
    }
    problem = _completion_record_problem(
        result,
        {"inspection:1"},
        packet=packet,
        require_requirement_status=True,
    )
    assert "completion_evidence is missing raw task clause coverage: task:b" in problem
    assert _completion_record_problem(
        result,
        {"inspection:1"},
        packet=packet,
        require_requirement_status=False,
    ) == ""

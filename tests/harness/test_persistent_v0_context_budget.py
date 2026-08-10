"""Hard final-packet budgeting and fail-closed PERSISTENT model-call admission."""
from __future__ import annotations

from dataclasses import replace

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.envmap_builder import build_envmap_from_task
from aether.kernel import AetherNextKernel
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_context import compile_persistent_context
from aether.persistent_context_budget import finalize_persistent_context_budget
from aether.persistent_primary import persistent_primary_runtime_ir
from aether.runtime_ir import CapabilityDescriptor, EnvMap, stable_json
from aether.execution import MemoryExecutor


def _compiled(tmp_path, task: str = "Create out.txt containing hello."):
    envmap = build_envmap_from_task(
        str(tmp_path), task, workspace_root=str(tmp_path),
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


def _ledger(tmp_path) -> ExecutionLedger:
    ledger = ExecutionLedger()
    ledger.install_runtime_identity({
        "task_id": "budget-task",
        "run_id": "budget-run",
        "primary_agent_id": "budget-primary",
        "workspace_id": str(tmp_path),
        "environment_id": "budget-env",
        "source_commit": "a" * 40,
        "source_commit_state": "provided",
        "runtime_manifest_sha256": "b" * 64,
        "runtime_manifest_state": "provided",
        "source_custody_complete": True,
        "budgets": {"max_kernel_steps": 8},
    })
    result = Receipt(
        receipt_id="step-1:budget-action:cmd",
        step=1,
        kind="run_command",
        success=True,
        summary="large command output",
        payload={
            "command": "produce-large-output",
            "stdout": "x" * 20_000,
            "stderr": "",
            "stdout_handle": "1:budget-action:stdout",
            "stderr_handle": "1:budget-action:stderr",
            "stdout_bytes": 20_000,
            "stderr_bytes": 0,
        },
    )
    ledger.record(result)
    ledger.record(Receipt(
        receipt_id="step-1:budget-action:primary_action_result_index",
        step=1,
        kind="primary_action_result_index",
        success=True,
        summary="indexed result",
        payload={
            "action_id": "budget-action",
            "action_kind": "run_command",
            "status": "observed",
            "outcome_receipt_ids": [result.receipt_id],
            "outcome_kinds": [result.kind],
        },
    ))
    return ledger


def test_default_final_packet_reports_exact_hard_budget_measurement(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    packet = compile_persistent_context(compiled, _ledger(tmp_path), linked_history={})

    budget = packet["context_budget"]
    assert budget["hard_limit_enforced"] is True
    assert budget["within_budget"] is True
    assert budget["final_bytes_v1"] == len(stable_json(packet).encode("utf-8"))
    assert budget["final_token_estimate_v1"] <= budget["budget_tokens_v1"]
    assert budget["token_estimator"] == "ceil(utf8_bytes/4)"


def test_oversized_linked_history_is_externalized_with_provenance(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    compiled = replace(
        compiled,
        context_policy=replace(
            compiled.context_policy,
            model_context_window_tokens=4_000,
            compression_trigger_ratio=0.80,
        ),
    )
    linked = {
        "command_results": [
            {"receipt_id": f"command-{index}", "stdout": "z" * 40_000}
            for index in range(4)
        ],
        "artifact_history": [
            {"path": f"artifact-{index}.txt", "history": "h" * 10_000}
            for index in range(4)
        ],
        "open_obligations": [],
        "obligation_status": [],
        "persistent_context_boundary": {
            "linked_history_is_factual_projection": True,
            "kernel_strategy_guidance_exposed": False,
            "legacy_automatic_memory_exposed": False,
            "generic_stuck_judgment_exposed": False,
        },
    }

    packet = compile_persistent_context(compiled, _ledger(tmp_path), linked)

    budget = packet["context_budget"]
    assert budget["within_budget"] is True
    assert budget["final_token_estimate_v1"] <= budget["budget_tokens_v1"]
    assert "externalize_linked_history" in budget["compression_stages"]
    assert "command_results" not in packet["linked_history"]
    assert "artifact_history" not in packet["linked_history"]
    records = {
        row["selector"]: row for row in budget["externalized_sections"]
    }
    assert records["command_results"]["sha256"]
    assert records["command_results"]["retrieval_actions"] == [
        "read_output", "query_memory"
    ]
    assert records["artifact_history"]["retrieval_actions"] == [
        "query_artifact_history"
    ]


def test_impossible_packet_returns_small_fail_closed_sentinel(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    compiled = replace(
        compiled,
        context_policy=replace(
            compiled.context_policy,
            model_context_window_tokens=64,
            compression_trigger_ratio=0.50,
        ),
    )
    packet = {
        "runtime_identity": {"task_id": "too-large"},
        "raw_task_authority": {
            "raw_task": "a" * 100_000,
            "authority": "exact_raw_task",
        },
        "latest_primary_result": {"status": "no_primary_action_yet"},
        "evidence_index": [],
        "receipt_exact_handles": {},
        "linked_history": {"command_results": ["b" * 100_000]},
    }

    failed = finalize_persistent_context_budget(packet, compiled)

    budget = failed["context_budget"]
    assert budget["within_budget"] is False
    assert budget["failure_reason"] == (
        "final_persistent_context_exceeds_hard_working_context_budget"
    )
    assert "fail_closed_before_model_call" in budget["compression_stages"]
    assert failed["context_budget_failure"]["model_call_authorized"] is False
    assert failed["context_budget_failure"]["raw_task_bytes"] == 100_000
    assert "raw_task_authority" not in failed


def test_kernel_does_not_call_solver_when_context_budget_is_failed(monkeypatch) -> None:
    calls = {"solve": 0}

    class Hooks:
        verify = None

        def solve(self, messages, compiled):
            del messages, compiled
            calls["solve"] += 1
            raise AssertionError("solver must not be called")

    envmap = EnvMap(
        task_prompt="Do not call the model after a budget failure.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files",
                tool_names=("read_file", "write_file"),
            ),
        },
    )
    kernel = AetherNextKernel(max_steps=2, persistent_primary=True)
    monkeypatch.setattr(
        kernel.context_compiler,
        "compile",
        lambda compiled, ledger, alerts: {
            "context_budget": {
                "within_budget": False,
                "failure_reason": "forced-test-budget-failure",
                "final_token_estimate_v1": 101,
                "budget_tokens_v1": 100,
            }
        },
    )

    result = kernel.run(
        envmap, MemoryExecutor(workspace_root="/app"), Hooks(),
    )

    assert calls["solve"] == 0
    assert result.status == "context_budget_exceeded"
    receipt = next(
        item for item in result.receipts
        if item.kind == "persistent_context_budget_exceeded"
    )
    assert receipt.payload["model_call_made"] is False

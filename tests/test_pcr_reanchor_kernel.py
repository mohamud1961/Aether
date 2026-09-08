from __future__ import annotations

import pytest

from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn
from aether.tracing import RunTrace


def test_kernel_rejects_unknown_reanchor_mode_at_construction() -> None:
    with pytest.raises(ValueError, match="unsupported PCR Solver re-anchor mode"):
        AetherNextKernel(solver_reanchor_mode="unknown")


def test_kernel_accepts_refined_reanchor_for_primary_runtime() -> None:
    kernel = AetherNextKernel(solver_reanchor_mode="refined_m")
    assert kernel.solver_reanchor_mode == "refined_m"




def test_kernel_accepts_continuity_fresh_delta_for_c1_runtime() -> None:
    kernel = AetherNextKernel(solver_reanchor_mode="continuity_fresh_delta_v1")
    assert kernel.solver_reanchor_mode == "continuity_fresh_delta_v1"


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Read the task files and continue from observed evidence.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files", tool_names=("read_file",),
            ),
        },
    )


def _action(path: str, action_id: str) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind="read_file",
        capability_id="filesystem",
        arguments={"path": path},
        intent="",
        expected_observation="",
        if_fail_next="",
    )


class _RefinedHooks:
    verify = None

    def __init__(self) -> None:
        self.calls = 0
        self.seen_contexts: list[dict[str, object]] = []

    def solve(self, messages, compiled):
        del compiled
        self.calls += 1
        marker = "[context_packet]\n"
        context: dict[str, object] = {}
        for message in messages:
            content = str(message.get("content", ""))
            if content.startswith(marker):
                import json
                context = json.loads(content[len(marker):])
        self.seen_contexts.append(context)
        paths = ("input.txt", "second.txt", "third.txt")
        path = paths[self.calls - 1]
        return SolverTurn(
            kind="act",
            summary=f"read {path}",
            actions=(_action(path, f"read-{self.calls}"),),
        )


def test_refined_model_view_is_compact_while_canonical_identity_remains_authoritative() -> None:
    hooks = _RefinedHooks()
    trace = RunTrace()
    runtime_identity = {
        "task_id": "task-a",
        "run_id": "run-a",
        "primary_agent_id": "primary:run-a",
        "source_commit": "a" * 40,
        "runtime_manifest_sha256": "b" * 64,
        "source_custody_complete": True,
    }
    result = AetherNextKernel(
        max_steps=3,
        runtime_identity=runtime_identity,
        solver_reanchor_mode="refined_m",
    ).run(
        _env(),
        MemoryExecutor(
            workspace_root="/app",
            files={"input.txt": "alpha", "second.txt": "beta", "third.txt": "gamma"},
        ),
        hooks,
        trace=trace,
    )

    assert len(hooks.seen_contexts) == 3
    model_identity = hooks.seen_contexts[0]["runtime_identity"]
    assert model_identity["task_id"] == "task-a"
    assert model_identity["run_id"] == "run-a"
    assert "source_commit" not in model_identity
    assert "runtime_manifest_sha256" not in model_identity
    assert "runtime_scope" not in hooks.seen_contexts[0]

    identity_receipt = next(r for r in result.receipts if r.kind == "runtime_identity")
    canonical_identity = identity_receipt.payload["runtime_identity"]
    assert canonical_identity["source_commit"] == "a" * 40
    assert canonical_identity["runtime_manifest_sha256"] == "b" * 64

    second = hooks.seen_contexts[1]
    third = hooks.seen_contexts[2]
    assert second["latest_primary_result"]["status"] == "succeeded"
    assert third["latest_primary_result"]["status"] == "succeeded"
    assert "working_state" not in second
    assert "working_state" not in third
    assert trace.steps[2]["context_seen"] == third


def test_continuity_fresh_delta_kernel_never_replays_historical_evidence_rows() -> None:
    hooks = _RefinedHooks()
    result = AetherNextKernel(
        max_steps=3,
        solver_reanchor_mode="continuity_fresh_delta_v1",
    ).run(
        _env(),
        MemoryExecutor(
            workspace_root="/app",
            files={"input.txt": "alpha", "second.txt": "beta", "third.txt": "gamma"},
        ),
        hooks,
        trace=RunTrace(),
    )
    assert len(hooks.seen_contexts) == 3
    assert hooks.seen_contexts[1]["latest_primary_result"]["status"] == "succeeded"
    assert hooks.seen_contexts[2]["latest_primary_result"]["status"] == "succeeded"
    for context in hooks.seen_contexts:
        assert all(
            row.get("currentness") != "historical_task_evidence"
            for row in context.get("evidence_index", [])
            if isinstance(row, dict)
        )
    # Canonical receipts are still complete; C1 changes only model-facing projection.
    assert len(result.receipts) > 0
    assert any(r.kind == "primary_action_result_index" for r in result.receipts)

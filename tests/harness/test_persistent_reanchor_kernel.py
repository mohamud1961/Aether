from __future__ import annotations

import re

import pytest

from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn
from aether.tracing import RunTrace


def test_kernel_rejects_unknown_reanchor_mode_at_construction() -> None:
    with pytest.raises(ValueError, match="unsupported PERSISTENT Solver re-anchor mode"):
        AetherNextKernel(persistent_primary=True, solver_reanchor_mode="unknown")


def test_kernel_rejects_refined_reanchor_outside_persistent_primary() -> None:
    with pytest.raises(ValueError, match="require persistent_primary"):
        AetherNextKernel(persistent_primary=False, solver_reanchor_mode="refined_m")


def test_kernel_accepts_refined_reanchor_for_persistent_primary() -> None:
    kernel = AetherNextKernel(persistent_primary=True, solver_reanchor_mode="refined_m")
    assert kernel.solver_reanchor_mode == "refined_m"


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Read input.txt, preserve grounded continuity, and continue.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files", tool_names=("read_file",),
            ),
        },
    )


def _action(kind: str, arguments: dict[str, object], *, action_id: str, capability_id: str) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id=capability_id,
        arguments=arguments,
        intent="",
        expected_observation="",
        if_fail_next="",
    )


def _checkpoint(ref: str) -> dict[str, object]:
    return {
        "current_objective": "Continue from observed file evidence.",
        "established_facts": [{"fact": "input.txt contains alpha", "evidence_refs": [ref]}],
        "open_questions": ["What is the next required task-state change?"],
        "active_hypotheses": [{"hypothesis": "alpha is authoritative", "status": "supported"}],
        "current_approach": "Use observed evidence and continue.",
        "rejected_approaches": [],
        "pending_external_state": [],
        "completion_gaps": ["Task continuation still required."],
    }


class _RefinedHooks:
    verify = None

    def __init__(self) -> None:
        self.calls = 0
        self.seen_contexts: list[dict[str, object]] = []

    def solve(self, messages, compiled):
        del compiled
        self.calls += 1
        marker = "[context_packet]\n"
        context = {}
        for message in messages:
            content = str(message.get("content", ""))
            if content.startswith(marker):
                import json
                context = json.loads(content[len(marker):])
        self.seen_contexts.append(context)
        if self.calls == 1:
            return SolverTurn(
                kind="act",
                summary="read input",
                actions=(_action(
                    "read_file", {"path": "input.txt"},
                    action_id="read", capability_id="filesystem",
                ),),
            )
        aliases = list(dict.fromkeys(re.findall(
            r"evidence:[0-9a-f]{16}", str(context)
        )))
        assert aliases
        if self.calls == 2:
            return SolverTurn(
                kind="act",
                summary="author grounded checkpoint",
                working_state=_checkpoint(aliases[0]),
                actions=(_action(
                    "record_observation", {"observation": "checkpoint authored"},
                    action_id="checkpoint", capability_id="kernel",
                ),),
            )
        return SolverTurn(
            kind="act",
            summary="continue after checkpoint",
            actions=(_action(
                "record_observation", {"observation": "continued"},
                action_id="continue", capability_id="kernel",
            ),),
        )


def test_refined_model_view_is_compact_while_canonical_working_state_and_identity_remain_authoritative() -> None:
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
        persistent_primary=True,
        runtime_identity=runtime_identity,
        solver_reanchor_mode="refined_m",
    ).run(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "alpha"}),
        hooks,
        trace=trace,
    )

    # Provider-facing dynamic context uses canonical section names but omits
    # source custody/reconstruction scaffolding.
    assert len(hooks.seen_contexts) == 3
    model_identity = hooks.seen_contexts[0]["runtime_identity"]
    assert model_identity["task_id"] == "task-a"
    assert model_identity["run_id"] == "run-a"
    assert "source_commit" not in model_identity
    assert "runtime_manifest_sha256" not in model_identity
    assert "runtime_scope" not in hooks.seen_contexts[0]

    # The exact canonical identity is still installed in immutable ledger
    # custody; the model projection did not rewrite kernel authority.
    identity_receipt = next(r for r in result.receipts if r.kind == "runtime_identity")
    canonical_identity = identity_receipt.payload["runtime_identity"]
    assert canonical_identity["source_commit"] == "a" * 40
    assert canonical_identity["runtime_manifest_sha256"] == "b" * 64

    # A model-authored checkpoint is validated against the canonical context and
    # stored in full. On the following provider turn only its stable evidence
    # bindings are re-anchored; narrative reconstruction is left to native state.
    checkpoint_receipt = next(
        r for r in result.receipts if r.kind == "persistent_working_state_checkpoint"
    )
    assert checkpoint_receipt.payload["checkpoint"]["current_objective"]
    third = hooks.seen_contexts[2]
    assert third["working_state"] == {
        "evidence_bindings": checkpoint_receipt.payload["evidence_bindings"]
    }
    assert "checkpoint" not in third["working_state"]

    # Trace records the exact Solver-facing packet for forensic comparison.
    assert trace.steps[2]["context_seen"] == third

"""Production-bound tests for the final completion conjunction.

A Verifier verdict is semantic evidence only. Mechanical blockers returned by
CompletionGate must defer terminal review before activation rather than spending a
Verifier call and checking the same blocker again afterward.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import aether.kernel as kernel_module
from aether.completion import Blocker, CompletionDecision
from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel, _completed_result
from aether.ledger import ExecutionLedger
from aether.runtime_ir import CapabilityDescriptor, EnvMap, SolverTurn
from aether.persistent_context import evidence_alias
from aether.runtime_ir import ActionRequest


class _SubmitHooks:
    def __init__(self) -> None:
        self.calls = 0

    def solve(self, messages: list[dict[str, str]], compiled: Any) -> SolverTurn:
        self.calls += 1
        if self.calls == 1:
            return SolverTurn(
                kind="act", summary="observe current state",
                actions=(ActionRequest(
                    action_id="observe", kind="read_file", capability_id="filesystem",
                    arguments={"path":"state.txt"}, intent="observe",
                    expected_observation="current bytes", if_fail_next="stop",
                ),),
                evidence_gap="current state not yet observed",
            )
        return SolverTurn(
            kind="submit_outcome", summary="submit current state",
            claim="state.txt is current",
            evidence_refs=(evidence_alias("step-0:observe:read"),),
        )



class _AlwaysBlockedGate:
    def __init__(self, blocker_code: str) -> None:
        self.blocker_code = blocker_code
        self.calls = 0

    def evaluate(self, compiled: Any, ledger: Any, alerts: Any) -> CompletionDecision:
        self.calls += 1
        return CompletionDecision(
            ready=False,
            blockers=(Blocker(self.blocker_code, "still blocked", "test"),),
        )


def _envmap() -> EnvMap:
    return EnvMap(
        task_prompt="Produce the required task result.",
        workspace_root="/app",
        capabilities={
            "shell": CapabilityDescriptor("shell", "run commands"),
            "filesystem": CapabilityDescriptor("filesystem", "read and write files"),
        },
    )


def test_completed_result_rejects_non_ready_decision() -> None:
    compiled = SimpleNamespace(planned_checks=lambda: (), env_digest="test")
    decision = CompletionDecision(
        ready=False,
        blockers=(Blocker("missing_artifacts", "result.json", "objective_graph"),),
    )

    with pytest.raises(ValueError, match="requires a ready completion decision"):
        _completed_result(0, 0, decision, compiled, ExecutionLedger())


@pytest.mark.parametrize("blocker_code", [
    "missing_artifacts",
    "missing_authoritative_check",
    "missing_clause_evidence",
    "stale_clause_evidence",
    "active_verifier_finding",
    "unsatisfied_obligations",
    "integrity_violation",
    "schema_unverified",
    "process_generation_mismatch",
    "incomplete_state_capture",
])
def test_fresh_gate_blocker_defers_verifier_before_activation(
    monkeypatch: pytest.MonkeyPatch,
    blocker_code: str,
) -> None:
    """Every non-review-resolvable blocker conserves terminal review."""

    def _verifier_must_not_run(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            f"Verifier must be deferred while mechanical blocker {blocker_code!r} is open"
        )

    monkeypatch.setattr(
        kernel_module,
        "run_model_verifier_if_available",
        _verifier_must_not_run,
    )

    kernel = AetherNextKernel(max_steps=2)
    fake_gate = _AlwaysBlockedGate(blocker_code)
    kernel.completion_gate = fake_gate

    result = kernel.run(
        _envmap(),
        MemoryExecutor(workspace_root="/app", files={"state.txt": "ok"}),
        _SubmitHooks(),
    )

    assert result.status != "completed"
    assert fake_gate.calls == 1, "mechanical preflight should block before semantic review"
    receipts = [
        receipt for receipt in result.receipts
        if receipt.kind == "advisory_review_deferred_mechanical_readiness"
    ]
    assert len(receipts) == 1
    assert receipts[0].payload["review_invoked"] is False
    assert receipts[0].payload["blocker_codes"] == [blocker_code]

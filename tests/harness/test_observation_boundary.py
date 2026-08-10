"""Tests for the Solver Closed-Loop V1 single-action observation boundary."""
from __future__ import annotations

import json
from typing import Any, Mapping

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.model_hooks import ModelOutputError, parse_solver_turn
from aether.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    CompletionPolicy,
    EnvMap,
    RuntimeConfigIR,
    SolverTurn,
)


def _envmap() -> EnvMap:
    return EnvMap(
        task_prompt="Inspect the task state.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor("filesystem", "read and write files"),
            "shell": CapabilityDescriptor("shell", "run commands"),
        },
    )


def _ir() -> RuntimeConfigIR:
    return RuntimeConfigIR(
        architect_summary="Inspect current task state.",
        solver_identity_prompt="Use one causal frontier at a time.",
        selected_capabilities=("filesystem", "shell"),
        completion_policy=CompletionPolicy(
            require_authoritative_check=False,
            require_all_obligations=False,
            require_recent_progress=False,
            require_clean_integrity=True,
        ),
    )


def _compiled():
    envmap = _envmap()
    return envmap, ConfigCompiler(CapabilityRegistry.from_envmap(envmap)).compile(_ir(), envmap)


def _action(kind: str, arguments: Mapping[str, Any], action_id: str = "a1") -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id="filesystem",
        arguments=dict(arguments),
        intent="inspect current state",
        expected_observation="current evidence",
        if_fail_next="narrow the inspection",
    )


def test_act_turn_rejects_multiple_arbitrary_actions() -> None:
    turn = SolverTurn(
        kind="act",
        summary="try two frontiers",
        evidence_gap="both inputs are unknown",
        actions=(
            _action("read_file", {"path": "a.txt"}, "a1"),
            _action("write_file", {"path": "b.txt", "content": "x"}, "a2"),
        ),
    )
    assert "act turns require exactly one action frontier" in turn.validate()


def test_observe_batch_is_absent_from_compiled_solver_surface() -> None:
    _env, compiled = _compiled()
    assert "observe_batch" not in dict(compiled.action_schema)
    errors = _action("observe_batch", {"operations": []}).validate(compiled.action_schema)
    assert "unknown action kind: observe_batch" in errors


def test_strict_parser_rejects_observe_batch_even_before_dispatch() -> None:
    raw = json.dumps({
        "kind": "act",
        "summary": "inspect two files",
        "requested_check_ids": [],
        "claimed_artifacts": [],
        "evidence_gap": "both files are unknown",
        "actions": [{
            "action_id": "batch",
            "kind": "observe_batch",
            "capability_id": "filesystem",
            "arguments": {"operations": []},
            "intent": "inspect several files",
            "expected_observation": "several results",
            "if_fail_next": "inspect one file",
        }],
    })
    try:
        parse_solver_turn(raw)
    except ModelOutputError as exc:
        assert "not part of Solver Closed-Loop Control V1" in str(exc)
    else:
        raise AssertionError("observe_batch must fail before dispatch")


class _Hooks:
    def __init__(self, turns: list[SolverTurn]) -> None:
        self.turns = list(turns)

    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        return _ir()

    def solve(self, messages: list[dict[str, str]], compiled: Any) -> SolverTurn:
        return self.turns.pop(0) if self.turns else SolverTurn(
            kind="submit_outcome", summary="submit"
        )


def test_kernel_pairs_one_decision_with_its_real_result_before_next_turn() -> None:
    hooks = _Hooks([
        SolverTurn(
            kind="act",
            summary="inspect the first input",
            evidence_gap="a.txt content is unknown",
            actions=(_action("read_file", {"path": "a.txt"}, "read-a"),),
        ),
        SolverTurn(kind="submit_outcome", summary="submit"),
    ])
    executor = MemoryExecutor(workspace_root="/app", files={"a.txt": "A"})
    result = AetherNextKernel(max_steps=3).run(_envmap(), executor, hooks)

    decisions = [r for r in result.receipts if r.kind == "solver_decision_state"]
    assert len(decisions) == 1
    assert decisions[0].payload["evidence_gap"] == "a.txt content is unknown"
    reads = [r for r in result.receipts if r.kind == "read_file"]
    assert len(reads) == 1 and reads[0].success is True
    progress = [r for r in result.receipts if r.kind == "solver_progress_assessment"]
    assert progress[-1].payload["result_receipt_ids"] == [reads[0].receipt_id]
    assert result.accounting is not None
    assert result.accounting["solver_accepted_task_actions"] == 1

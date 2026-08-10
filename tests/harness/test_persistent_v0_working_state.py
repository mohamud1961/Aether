"""PERSISTENT V0 bounded, evidence-linked Primary Agent working-state continuity."""
from __future__ import annotations

import json
import re

import pytest

from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.model_parse import parse_solver_turn
from aether.persistent_provider_protocol import (
    PCRProviderProtocolError,
    validate_persistent_inner_turn,
)
from aether.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    EnvMap,
    SolverTurn,
)
from aether.tracing import RunTrace


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Inspect input.txt and maintain a concise working state.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files",
                tool_names=("read_file", "write_file"),
            ),
        },
    )


def _action(
    kind: str,
    arguments: dict[str, object],
    *,
    action_id: str,
    capability_id: str,
) -> ActionRequest:
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
        "current_objective": "Determine the exact current input before editing.",
        "established_facts": [{
            "fact": "input.txt currently contains alpha.",
            "evidence_refs": [ref],
        }],
        "open_questions": ["Does the required output need normalization?"],
        "active_hypotheses": [{
            "hypothesis": "A direct transformation is sufficient.",
            "status": "unconfirmed",
        }],
        "current_approach": "Inspect first, then make the smallest verified change.",
        "rejected_approaches": [{
            "approach": "Overwrite before reading.",
            "reason": "It would discard task-state information already available.",
            "evidence_refs": [ref],
        }],
        "pending_external_state": [],
        "completion_gaps": ["Need a post-edit observation."],
    }


def test_protocol_accepts_optional_working_state_without_making_it_mandatory() -> None:
    basic = validate_persistent_inner_turn({
        "kind": "act",
        "action": {
            "kind": "read_file",
            "capability_id": "filesystem",
            "arguments": {"path": "input.txt"},
        },
    })
    assert "working_state" not in basic

    checkpoint = _checkpoint("evidence:0123456789abcdef")
    enriched = validate_persistent_inner_turn({
        "kind": "act",
        "action": {
            "kind": "read_file",
            "capability_id": "filesystem",
            "arguments": {"path": "input.txt"},
        },
        "working_state": checkpoint,
    })
    assert enriched["working_state"] == checkpoint

    submit = validate_persistent_inner_turn({
        "kind": "submit",
        "claim": "done",
        "evidence_refs": ["evidence:0123456789abcdef"],
        "working_state": checkpoint,
    })
    assert submit["working_state"] == checkpoint


def test_protocol_rejects_hidden_reasoning_and_unbounded_freeform_fields() -> None:
    with pytest.raises(PCRProviderProtocolError, match="schema_validation"):
        validate_persistent_inner_turn({
            "kind": "act",
            "action": {
                "kind": "read_file",
                "capability_id": "filesystem",
                "arguments": {"path": "input.txt"},
            },
            "working_state": _checkpoint("evidence:0123456789abcdef") | {
                "chain_of_thought": "private reasoning",
            },
        })


def test_parser_preserves_working_state_exactly() -> None:
    checkpoint = _checkpoint("evidence:0123456789abcdef")
    turn = parse_solver_turn(json.dumps({
        "kind": "act",
        "action": {
            "kind": "read_file",
            "capability_id": "filesystem",
            "arguments": {"path": "input.txt"},
        },
        "working_state": checkpoint,
    }), protocol="persistent_v0")
    assert turn.working_state == checkpoint


class _ContinuityHooks:
    verify = None

    def __init__(self, *, mutate_after_checkpoint: bool = False) -> None:
        self.calls = 0
        self.mutate_after_checkpoint = mutate_after_checkpoint

    def solve(self, messages, compiled):
        del compiled
        self.calls += 1
        if self.calls == 1:
            return SolverTurn(
                kind="act",
                summary="read input",
                actions=(_action(
                    "read_file", {"path": "input.txt"},
                    action_id="read", capability_id="filesystem",
                ),),
            )
        aliases: list[str] = []
        for message in messages:
            aliases.extend(re.findall(
                r"evidence:[0-9a-f]{16}", str(message.get("content", ""))
            ))
        aliases = list(dict.fromkeys(aliases))
        assert aliases
        if self.calls == 2:
            return SolverTurn(
                kind="act",
                summary="checkpoint continuity",
                working_state=_checkpoint(aliases[0]),
                actions=(_action(
                    "record_observation",
                    {"observation": "checkpoint authored"},
                    action_id="checkpoint", capability_id="kernel",
                ),),
            )
        if self.mutate_after_checkpoint and self.calls == 3:
            return SolverTurn(
                kind="act",
                summary="mutate task state",
                actions=(_action(
                    "write_file", {"path": "output.txt", "content": "alpha"},
                    action_id="mutate", capability_id="filesystem",
                ),),
            )
        return SolverTurn(
            kind="act",
            summary="observe continuity",
            actions=(_action(
                "record_observation",
                {"observation": "continuity observed"},
                action_id=f"observe-{self.calls}", capability_id="kernel",
            ),),
        )


def test_kernel_versions_and_pins_evidence_linked_working_state() -> None:
    trace = RunTrace()
    result = AetherNextKernel(max_steps=3, persistent_primary=True).run(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "alpha"}),
        _ContinuityHooks(),
        trace=trace,
    )

    checkpoints = [
        receipt for receipt in result.receipts
        if receipt.kind == "persistent_working_state_checkpoint"
    ]
    assert len(checkpoints) == 1
    assert checkpoints[0].payload["version"] == 1
    assert checkpoints[0].payload["completion_evidence_eligible"] is False
    assert checkpoints[0].payload["semantic_content_interpreted_by_kernel"] is False

    context = trace.steps[2]["context_seen"]
    working = context["working_state"]
    assert working["status"] == "potentially_stale_after_new_primary_observation"
    assert working["new_primary_observation_since_authorship"] is True
    assert working["task_state_mutated_since_authorship"] is False
    assert (
        working["current_latest_primary_result_index_receipt_id"]
        != working["latest_primary_result_index_receipt_id_at_authorship"]
    )
    assert working["version"] == 1
    assert working["checkpoint"] == checkpoints[0].payload["checkpoint"]
    assert working["evidence_bindings"]
    assert working["completion_evidence_eligible"] is False
    evidence_types = {row["evidence_type"] for row in context["evidence_index"]}
    assert "persistent_working_state_checkpoint" not in evidence_types


def test_task_mutation_marks_checkpoint_potentially_stale_without_rewriting_it() -> None:
    trace = RunTrace()
    result = AetherNextKernel(max_steps=4, persistent_primary=True).run(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "alpha"}),
        _ContinuityHooks(mutate_after_checkpoint=True),
        trace=trace,
    )

    checkpoint = next(
        receipt for receipt in result.receipts
        if receipt.kind == "persistent_working_state_checkpoint"
    )
    context = trace.steps[3]["context_seen"]
    working = context["working_state"]
    assert working["status"] == "potentially_stale_after_task_mutation"
    assert working["checkpoint"] == checkpoint.payload["checkpoint"]
    assert (
        working["current_task_state_generation"]
        > working["task_state_generation_at_authorship"]
    )


def test_invalid_working_state_ref_is_rejected_but_task_action_still_executes() -> None:
    checkpoint = _checkpoint("evidence:ffffffffffffffff")

    class Hooks:
        verify = None

        def solve(self, messages, compiled):
            del messages, compiled
            return SolverTurn(
                kind="act",
                summary="continue despite invalid checkpoint",
                working_state=checkpoint,
                actions=(_action(
                    "write_file", {"path": "out.txt", "content": "done"},
                    action_id="write", capability_id="filesystem",
                ),),
            )

    executor = MemoryExecutor(workspace_root="/app")
    result = AetherNextKernel(max_steps=1, persistent_primary=True).run(
        _env(), executor, Hooks(),
    )

    assert executor.files["out.txt"] == "done"
    rejected = [
        receipt for receipt in result.receipts
        if receipt.kind == "persistent_working_state_rejected"
    ]
    assert len(rejected) == 1
    assert rejected[0].failure_class == "persistent_working_state_evidence_not_current"
    assert not any(
        receipt.kind == "persistent_working_state_checkpoint"
        for receipt in result.receipts
    )

from __future__ import annotations

import json
from typing import Any

from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.model_parse import parse_solver_turn
from aether.persistent_provider_protocol import (
    PERSISTENT_DIRECT_PROVIDER_TOOLS,
    PERSISTENT_DIRECT_PROVIDER_TOOLS_COMMITMENT_V1,
    canonicalize_persistent_direct_tool_call,
)
from aether.providers.azure_model import AzureModelCallable
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn


def _tool(tools: tuple[dict[str, Any], ...], name: str) -> dict[str, Any]:
    return next(tool for tool in tools if tool["name"] == name)


def test_commitment_provider_schema_is_default_off_and_requires_only_v1_fields_when_selected() -> None:
    control = _tool(PERSISTENT_DIRECT_PROVIDER_TOOLS, "read_file")["parameters"]
    v1 = _tool(PERSISTENT_DIRECT_PROVIDER_TOOLS_COMMITMENT_V1, "read_file")["parameters"]

    assert control["required"] == ["arguments"]
    assert set(control["properties"]) == {"arguments"}
    assert set(v1["required"]) == {
        "summary", "evidence_gap", "intent", "expected_observation",
        "if_fail_next", "arguments",
    }
    assert set(v1["properties"]) == set(v1["required"])
    # Action argument authority itself is unchanged between arms.
    assert control["properties"]["arguments"] == v1["properties"]["arguments"]


def test_commitment_direct_turn_roundtrip_preserves_model_authored_fields() -> None:
    payload = {
        "summary": "Inspect the current implementation",
        "evidence_gap": "The active algorithm has not been observed",
        "intent": "Read the implementation before choosing a repair",
        "expected_observation": "The file contains the current compact implementation",
        "if_fail_next": "Locate the implementation path from the task workspace",
        "arguments": {"path": "/app/solution.py"},
    }
    canonical, receipt = canonicalize_persistent_direct_tool_call(
        "read_file", json.dumps(payload),
    )
    raw = json.loads(canonical)
    assert raw["summary"] == payload["summary"]
    assert raw["evidence_gap"] == payload["evidence_gap"]
    assert raw["action"]["intent"] == payload["intent"]
    assert raw["action"]["expected_observation"] == payload["expected_observation"]
    assert raw["action"]["if_fail_next"] == payload["if_fail_next"]
    assert receipt["provider_turn_arguments_transport"] == "direct_native_function"

    turn = parse_solver_turn(canonical)
    action = turn.actions[0]
    assert turn.summary == payload["summary"]
    assert turn.evidence_gap == payload["evidence_gap"]
    assert action.intent == payload["intent"]
    assert action.expected_observation == payload["expected_observation"]
    assert action.if_fail_next == payload["if_fail_next"]
    assert action.arguments == payload["arguments"]


def test_control_direct_turn_roundtrip_remains_v0_shape() -> None:
    canonical, _ = canonicalize_persistent_direct_tool_call(
        "read_file", json.dumps({"arguments": {"path": "/app/solution.py"}}),
    )
    assert json.loads(canonical) == {
        "kind": "act",
        "action": {"kind": "read_file", "arguments": {"path": "/app/solution.py"}},
    }
    turn = parse_solver_turn(canonical)
    assert turn.summary == "Primary Agent requested read_file"
    assert turn.evidence_gap == ""
    assert turn.actions[0].intent == ""
    assert turn.actions[0].expected_observation == ""
    assert turn.actions[0].if_fail_next == ""


def test_provider_scope_selects_commitment_tools_without_mutating_control_default() -> None:
    model = AzureModelCallable(
        client=object(),  # type: ignore[arg-type]
        deployment="unit-test-frontier", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )
    scope = ("run-a", "task-a")
    control_tools, _ = model._primary_provider_tools_for_scope(scope)
    assert _tool(tuple(control_tools), "read_file")["parameters"]["required"] == ["arguments"]

    model.set_solver_commitment_mode("commitment_v1", run_id="run-a", task_id="task-a")
    v1_tools, _ = model._primary_provider_tools_for_scope(scope)
    assert set(_tool(tuple(v1_tools), "read_file")["parameters"]["required"]) == {
        "summary", "evidence_gap", "intent", "expected_observation",
        "if_fail_next", "arguments",
    }
    # A different run/task scope remains control.
    other, _ = model._primary_provider_tools_for_scope(("run-b", "task-b"))
    assert _tool(tuple(other), "read_file")["parameters"]["required"] == ["arguments"]


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Inspect the supplied files.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files", tool_names=("read_file",),
            ),
        },
    )


def _commitment_action(path: str, action_id: str) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind="read_file",
        capability_id="filesystem",
        arguments={"path": path},
        intent="Observe the exact file bytes",
        expected_observation=f"{path} is readable and contains task data",
        if_fail_next="Inspect the workspace inventory for the correct path",
    )


class _CommitmentHooks:
    verify = None

    def __init__(self, *, commitment: bool) -> None:
        self.commitment = commitment
        self.calls = 0
        self.contexts: list[dict[str, Any]] = []

    def solve(self, messages, compiled):
        del compiled
        self.calls += 1
        marker = "[context_packet]\n"
        packet: dict[str, Any] = {}
        for message in messages:
            content = str(message.get("content", ""))
            if content.startswith(marker):
                packet = json.loads(content[len(marker):])
        self.contexts.append(packet)
        path = "first.txt" if self.calls == 1 else "second.txt"
        if self.commitment:
            return SolverTurn(
                kind="act",
                summary=f"Observe {path}",
                evidence_gap=f"The bytes of {path} are not yet known",
                actions=(_commitment_action(path, f"read-{self.calls}"),),
            )
        return SolverTurn(
            kind="act",
            summary=f"read {path}",
            actions=(ActionRequest(
                action_id=f"read-{self.calls}", kind="read_file",
                capability_id="filesystem", arguments={"path": path},
                intent="", expected_observation="", if_fail_next="",
            ),),
        )


def test_commitment_receipt_and_next_context_preserve_decision_plus_exact_result() -> None:
    hooks = _CommitmentHooks(commitment=True)
    result = AetherNextKernel(
        max_steps=2,
        solver_reasoning_mode="commitment_v1",
    ).run(
        _env(),
        MemoryExecutor(
            workspace_root="/app", files={"first.txt": "alpha", "second.txt": "beta"},
        ),
        hooks,
    )
    assert len(hooks.contexts) == 2
    assert "latest_solver_transition" not in hooks.contexts[0]
    second = hooks.contexts[1]
    transition = second["latest_solver_transition"]
    decision = transition["decision"]
    assert decision["current_subgoal"] == "Observe first.txt"
    assert decision["evidence_gap"] == "The bytes of first.txt are not yet known"
    assert decision["intent"] == "Observe the exact file bytes"
    assert decision["previous_model_expectation"] == "first.txt is readable and contains task data"
    assert decision["previous_model_contingency"] == "Inspect the workspace inventory for the correct path"
    assert transition["observation_boundary"]["interpretation_authority"] == "solver"
    assert transition["observation_boundary"]["previous_expectation_is_nonbinding"] is True
    assert transition["result_index_receipt_id"].endswith(":primary_action_result_index")
    assert [row["kind"] for row in transition["results"]] == ["read_file"]
    assert transition["results"][0]["success"] is True
    assert second["latest_primary_result"]["outcome_receipts"][0]["evidence_type"] == "read_file"

    states = [r for r in result.receipts if r.kind == "solver_decision_state"]
    assert len(states) == 2
    assert states[0].payload["model_authored"] is True
    assert states[0].payload["interpretation_authority"] == "solver"


def test_control_kernel_adds_no_commitment_receipt_or_context_key() -> None:
    hooks = _CommitmentHooks(commitment=False)
    result = AetherNextKernel(max_steps=2, solver_reasoning_mode="control").run(
        _env(),
        MemoryExecutor(
            workspace_root="/app", files={"first.txt": "alpha", "second.txt": "beta"},
        ),
        hooks,
    )
    assert len(hooks.contexts) == 2
    assert "latest_solver_transition" not in hooks.contexts[0]
    assert "latest_solver_transition" not in hooks.contexts[1]
    assert not any(r.kind == "solver_decision_state" for r in result.receipts)

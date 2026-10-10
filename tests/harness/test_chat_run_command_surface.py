from __future__ import annotations

import json

import pytest

from aether.persistent_provider_protocol import (
    PERSISTENT_DIRECT_PROVIDER_TOOLS,
    PCRProviderProtocolError,
    canonicalize_persistent_direct_tool_call,
    persistent_chat_provider_tools,
)
from aether.providers.chat_model import ChatCompletionsModelCallable


def _tool(tools, name: str):
    return next(row for row in tools if row["name"] == name)


def _chat_function_tool(tools, name: str):
    return next(row["function"] for row in tools if row["function"]["name"] == name)


class _UnusedTransport:
    def create(self, **kwargs):
        raise AssertionError("provider dispatch not expected in surface test")


def test_chat_surface_flattens_standard_run_command_only() -> None:
    chat = persistent_chat_provider_tools()
    standard = _tool(chat, "run_command")
    advanced = _tool(chat, "run_command_advanced")

    params = standard["parameters"]
    assert params["type"] == "object"
    assert params["additionalProperties"] is False
    assert params["required"] == ["command", "timeout_s"]
    assert set(params["properties"]) == {"command", "timeout_s"}
    assert params["properties"]["command"]["type"] == "string"
    assert params["properties"]["command"]["pattern"] == r"\S"
    assert params["properties"]["timeout_s"] == {"type": "integer", "minimum": 1}
    assert advanced["parameters"]["required"] == ["arguments"]
    assert "anyOf" in advanced["parameters"]["properties"]["arguments"]


def test_static_kernel_preserves_advanced_helper_run_command_alias() -> None:
    model = ChatCompletionsModelCallable(
        transport=_UnusedTransport(),
        deployment="unit-test",
        role="solver",
        native_persistent_tools=True,
        tool_surface_mode="static_kernel_v1",
    )
    tools = model._tools_for_scope(("run-static", "task-static"))
    names = {row["function"]["name"] for row in tools}
    assert "run_command" in names
    assert "run_command_advanced" in names

    advanced = _chat_function_tool(tools, "run_command_advanced")
    variants = advanced["parameters"]["properties"]["arguments"]["anyOf"]
    helper_variants = [
        row for row in variants
        if {"helper_path", "helper_mode"} <= set(row.get("properties", {}))
    ]
    assert helper_variants
    assert {
        value
        for row in helper_variants
        for value in row["properties"]["helper_mode"].get("enum", [])
    } == {"smoke_test", "execute"}


def test_chat_model_uses_flat_run_command_in_control_and_research_modes() -> None:
    model = ChatCompletionsModelCallable(
        transport=_UnusedTransport(),
        deployment="unit-test",
        role="solver",
        native_persistent_tools=True,
    )
    scope=("run-a","task-a")

    control=_chat_function_tool(model._tools_for_scope(scope),"run_command")
    assert control["parameters"]["required"] == ["command","timeout_s"]

    model.set_solver_commitment_mode("commitment_v1",run_id=scope[0],task_id=scope[1])
    commitment=_chat_function_tool(model._tools_for_scope(scope),"run_command")
    assert "arguments" not in commitment["parameters"]["properties"]
    assert {"command","timeout_s","summary","evidence_gap","intent",
            "expected_observation","if_fail_next"} == set(commitment["parameters"]["required"])

    model.set_completion_disposition_mode(
        "completion_disposition_v1",run_id=scope[0],task_id=scope[1]
    )
    both=_chat_function_tool(model._tools_for_scope(scope),"run_command")
    assert "arguments" not in both["parameters"]["properties"]
    assert "run_command_advanced" in {
        row["function"]["name"] for row in model._tools_for_scope(scope)
    }


def test_azure_direct_surface_remains_nested_and_unchanged() -> None:
    standard = _tool(PERSISTENT_DIRECT_PROVIDER_TOOLS, "run_command")
    assert standard["parameters"]["required"] == ["arguments"]
    assert set(standard["parameters"]["properties"]) == {"arguments"}
    assert "anyOf" in standard["parameters"]["properties"]["arguments"]
    assert not any(row["name"] == "run_command_advanced" for row in PERSISTENT_DIRECT_PROVIDER_TOOLS)


def test_flat_chat_run_command_roundtrips_to_canonical_action() -> None:
    canonical, receipt = canonicalize_persistent_direct_tool_call(
        "run_command",
        json.dumps({"command": "cd /app && python3 check.py", "timeout_s": 120}),
    )
    assert json.loads(canonical) == {
        "kind": "act",
        "action": {
            "kind": "run_command",
            "arguments": {"command": "cd /app && python3 check.py", "timeout_s": 120},
        },
    }
    assert receipt["provider_direct_action_arguments_normalization"] == "chat_flat_run_command_v1"


def test_flat_chat_run_command_handles_complex_shell_quoting_without_nested_json() -> None:
    command = (
        "cd /app/workspace && { echo '=== spec/current.md ==='; "
        "cat spec/current.md; echo '=== policy.json ==='; cat policy.json; "
        "echo '=== report.py ==='; cat report.py; echo '=== SMOKE ==='; "
        "python3 public_smoke.py > /tmp/smoke.log 2>&1; S=$?; "
        "echo \"SMOKE_EXIT=$S\"; echo '=== CLI ==='; "
        "python3 report.py sample.csv policy.json /tmp/out.json > /tmp/cli.log 2>&1; "
        "C=$?; echo \"CLI_EXIT=$C\"; echo '=== out.json ==='; cat /tmp/out.json; }"
    )
    canonical, receipt = canonicalize_persistent_direct_tool_call(
        "run_command", json.dumps({"command": command, "timeout_s": 120})
    )
    parsed = json.loads(canonical)
    assert parsed["action"] == {
        "kind": "run_command",
        "arguments": {"command": command, "timeout_s": 120},
    }
    assert receipt["provider_direct_action_arguments_normalization"] == "chat_flat_run_command_v1"


def test_advanced_chat_alias_roundtrips_to_canonical_run_command() -> None:
    canonical, receipt = canonicalize_persistent_direct_tool_call(
        "run_command_advanced",
        json.dumps({
            "arguments": {
                "command": "python3 helper.py",
                "timeout_s": 60,
                "helper_path": "/app/helper.py",
                "helper_mode": "smoke_test",
            }
        }),
    )
    parsed = json.loads(canonical)
    assert parsed["action"]["kind"] == "run_command"
    assert parsed["action"]["arguments"]["helper_path"] == "/app/helper.py"
    assert receipt["provider_direct_tool_name"] == "run_command_advanced"
    assert receipt["provider_canonical_action_kind"] == "run_command"


def test_flat_chat_run_command_still_fails_closed_on_cross_variant_fields() -> None:
    with pytest.raises(PCRProviderProtocolError, match="direct_action_fields_invalid"):
        canonicalize_persistent_direct_tool_call(
            "run_command",
            json.dumps({"command": "echo ok", "timeout_s": 10, "helper_path": "x"}),
        )


def test_historical_corrupt_nested_payload_is_not_guessed_or_recovered() -> None:
    corrupt = json.dumps({
        "arguments": '{"command": "cd /app/workspace && echo \\" , "helper_path": "x", "helper_mode": "smoke_test"}'
    })
    with pytest.raises(PCRProviderProtocolError, match="direct_arguments_string_not_object"):
        canonicalize_persistent_direct_tool_call("run_command", corrupt)


def test_commitment_chat_surface_flattens_run_command_and_preserves_commitments() -> None:
    chat = persistent_chat_provider_tools(commitment_v1=True)
    standard = _tool(chat, "run_command")
    params = standard["parameters"]
    assert set(params["required"]) == {
        "summary", "evidence_gap", "intent", "expected_observation",
        "if_fail_next", "command", "timeout_s",
    }
    payload = {
        "summary": "verify repaired source",
        "evidence_gap": "behavior is not yet observed",
        "intent": "run one bounded verification command",
        "expected_observation": "smoke and CLI exit zero",
        "if_fail_next": "inspect the failing output",
        "command": "cd /app/workspace && python3 public_smoke.py",
        "timeout_s": 60,
    }
    canonical, receipt = canonicalize_persistent_direct_tool_call(
        "run_command", json.dumps(payload)
    )
    parsed = json.loads(canonical)
    assert parsed["summary"] == payload["summary"]
    assert parsed["evidence_gap"] == payload["evidence_gap"]
    assert parsed["action"]["kind"] == "run_command"
    assert parsed["action"]["intent"] == payload["intent"]
    assert parsed["action"]["expected_observation"] == payload["expected_observation"]
    assert parsed["action"]["if_fail_next"] == payload["if_fail_next"]
    assert parsed["action"]["arguments"] == {
        "command": payload["command"],
        "timeout_s": 60,
    }
    assert receipt["provider_direct_action_arguments_normalization"] == "chat_flat_run_command_v1"

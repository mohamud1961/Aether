from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.pcr_provider_protocol import PCR_DIRECT_PROVIDER_TOOLS

from aether.providers.azure_model import (
    AzureModelCallable,
    AzureProviderOutputError,
    canonicalize_pcr_native_tool_output,
)


def _direct_args(path: str = "/app/input.txt") -> str:
    return json.dumps({"arguments": {"path": path}})


def _call(arguments: str | None = None, *, name: str = "read_file", ordinal: int = 1):
    return SimpleNamespace(
        id=f"fc-{ordinal}", type="function_call", status="completed",
        call_id=f"call-{ordinal}", name=name,
        arguments=_direct_args() if arguments is None else arguments,
    )


def _response(*items: object, status: str = "completed"):
    return SimpleNamespace(
        id="resp-1", status=status, output=list(items), usage=None,
        reasoning=None, error=None,
        incomplete_details=SimpleNamespace(reason="max_output_tokens") if status == "incomplete" else None,
    )


def test_exactly_one_direct_native_action_call_is_canonicalized() -> None:
    canonical, receipt = canonicalize_pcr_native_tool_output(_response(_call()))
    body = json.loads(canonical)
    assert body == {
        "kind": "act",
        "action": {"kind": "read_file", "arguments": {"path": "/app/input.txt"}},
    }
    assert receipt["native_tool_call_count"] == 1
    assert receipt["provider_duplicate_output"] is False


@pytest.mark.parametrize("items", [(), (_call(ordinal=1), _call(ordinal=2))])
def test_zero_or_multiple_native_calls_fail_closed(items: tuple[object, ...]) -> None:
    with pytest.raises(AzureProviderOutputError, match="native_tool_call_count_invalid"):
        canonicalize_pcr_native_tool_output(_response(*items))


def test_assistant_prose_alongside_one_native_call_is_ignored_mechanically() -> None:
    message = SimpleNamespace(
        id="msg-1", type="message", role="assistant",
        content=[SimpleNamespace(type="output_text", text="extra prose")],
    )
    canonical, receipt = canonicalize_pcr_native_tool_output(_response(_call(), message))
    assert json.loads(canonical) == {
        "kind":"act", "action":{"kind":"read_file","arguments":{"path":"/app/input.txt"}}
    }
    assert receipt["provider_ignored_assistant_message_count"] == 1
    assert len(receipt["provider_ignored_assistant_message_sha256"]) == 1


def test_wrong_native_tool_name_fails_closed() -> None:
    with pytest.raises(AzureProviderOutputError, match="native_tool_name_invalid"):
        canonicalize_pcr_native_tool_output(_response(_call(name="other_tool")))


@pytest.mark.parametrize(
    ("tool_name", "expected_kind"),
    [("finish_intent", "finish_intent"), ("finish", "finish")],
)
def test_direct_native_completion_calls_are_canonicalized(tool_name: str, expected_kind: str) -> None:
    arguments = json.dumps({"claim": "done", "evidence_refs": ["evidence:0123456789abcdef"]})
    canonical, receipt = canonicalize_pcr_native_tool_output(
        _response(_call(arguments, name=tool_name))
    )
    assert json.loads(canonical) == {
        "kind": expected_kind, "claim": "done",
        "evidence_refs": ["evidence:0123456789abcdef"],
    }
    assert receipt["native_tool_name"] == tool_name


def test_retired_capability_id_is_rejected_by_native_boundary() -> None:
    invalid = json.dumps({
        "arguments": {
            "path": "/app/input.txt",
            "capability_id": "filesystem",
        }
    })
    with pytest.raises(AzureProviderOutputError, match="schema_validation"):
        canonicalize_pcr_native_tool_output(_response(_call(invalid)))


def test_duplicate_json_key_is_rejected_by_native_boundary() -> None:
    duplicate = '{"arguments":{"path":"/app/a","path":"/app/b"}}'
    with pytest.raises(AzureProviderOutputError, match="duplicate_key"):
        canonicalize_pcr_native_tool_output(_response(_call(duplicate)))


class _Responses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        return self.response

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("foreground terminal fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("terminal fake must not cancel")


class _Client:
    def __init__(self, response: object) -> None:
        self.responses = _Responses(response)


def _model(response: object) -> AzureModelCallable:
    return AzureModelCallable(
        client=_Client(response),  # type: ignore[arg-type]
        deployment="unit-test-luna", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )


def test_incomplete_native_provider_response_fails_closed() -> None:
    model = _model(_response(status="incomplete"))
    with pytest.raises(AzureProviderOutputError, match="provider_output_incomplete"):
        model.call_with_telemetry_scope(
            [{"role": "user", "content": "inspect current state"}],
            max_output_tokens=16000, run_id="native-boundary-run", task_id="native-boundary-task",
        )


def test_native_request_is_forced_single_nonparallel_tool_call() -> None:
    client = _Client(_response(_call()))
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-luna", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )
    model.call_with_telemetry_scope(
        [{"role": "user", "content": "inspect current state"}],
        max_output_tokens=16000, run_id="native-boundary-run", task_id="native-boundary-task",
    )
    request = client.responses.requests[0]
    assert request["max_tool_calls"] == 1
    assert request["parallel_tool_calls"] is False
    assert request["tool_choice"] == "required"
    assert len(request["tools"]) == len(PCR_DIRECT_PROVIDER_TOOLS)
    assert {tool["name"] for tool in request["tools"]} >= {
        "read_file", "run_command", "finish_intent", "finish"
    }
    assert "submit" not in {tool["name"] for tool in request["tools"]}
    assert all(tool["strict"] is True for tool in request["tools"])
    assert "text" not in request


def test_native_request_omits_output_ceiling_when_unbounded() -> None:
    client = _Client(_response(_call()))
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-luna", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )
    model.call_with_telemetry_scope(
        [{"role": "user", "content": "inspect current state"}],
        run_id="native-unbounded-run", task_id="native-unbounded-task",
    )
    request = client.responses.requests[0]
    assert "max_output_tokens" not in request
    assert request["max_tool_calls"] == 1
    assert request["parallel_tool_calls"] is False


def test_native_request_preserves_explicit_finite_output_ceiling() -> None:
    client = _Client(_response(_call()))
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-luna", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )
    model.call_with_telemetry_scope(
        [{"role": "user", "content": "inspect current state"}],
        max_output_tokens=1234, run_id="native-bounded-run", task_id="native-bounded-task",
    )
    assert client.responses.requests[0]["max_output_tokens"] == 1234

def test_direct_native_tool_set_exactly_matches_kernel_action_authority_plus_completion_controls() -> None:
    from aether.pcr_provider_protocol import PCR_ACTION_ARGUMENT_VARIANTS, PCR_DIRECT_PROVIDER_TOOLS
    names = [str(tool["name"]) for tool in PCR_DIRECT_PROVIDER_TOOLS]
    assert len(names) == len(set(names))
    function_actions = set(PCR_ACTION_ARGUMENT_VARIANTS) - {"computer_action"}
    assert set(names) == {*function_actions, "finish_intent", "finish"}
    assert "submit" not in names
    assert "computer_action" not in names
    assert len(names) == len(function_actions) + 2
    for tool in PCR_DIRECT_PROVIDER_TOOLS:
        assert tool["type"] == "function"
        assert tool["strict"] is True
        params = tool["parameters"]
        # Azure function calling rejects a top-level anyOf even when every
        # branch is an object. The parameters root itself must be an object.
        assert params["type"] == "object"
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])


def test_direct_exact_variants_are_nested_under_one_azure_object_root() -> None:
    from jsonschema import Draft202012Validator
    from aether.pcr_provider_protocol import PCR_DIRECT_PROVIDER_TOOLS, canonicalize_pcr_direct_tool_call

    by_name={tool["name"]:tool for tool in PCR_DIRECT_PROVIDER_TOOLS}
    run_params=by_name["run_command"]["parameters"]
    assert run_params["type"] == "object"
    assert run_params["required"] == ["arguments"]
    assert set(run_params["properties"]) == {"arguments"}
    assert "anyOf" in run_params["properties"]["arguments"]

    canonical, _ = canonicalize_pcr_direct_tool_call(
        "read_file_page", json.dumps({"arguments":{"path":"/app/a"}}),
    )
    assert json.loads(canonical) == {
        "kind":"act", "action":{"kind":"read_file_page","arguments":{"path":"/app/a"}},
    }

    # The exact server-facing grammar itself rejects the cross-variant field
    # combination observed in the live S6.3c failure.
    mixed={"arguments":{
        "command":"echo ok", "timeout_s":10,
        "helper_mode":"execute", "capture_surface":"artifact",
    }}
    errors=list(Draft202012Validator(run_params).iter_errors(mixed))
    assert errors


def test_direct_action_transport_rejects_flat_or_cross_variant_arguments() -> None:
    from aether.pcr_provider_protocol import PCRProviderProtocolError, canonicalize_pcr_direct_tool_call

    with pytest.raises(PCRProviderProtocolError, match="direct_action_fields_invalid"):
        canonicalize_pcr_direct_tool_call("read_file", json.dumps({"path":"/app/a"}))
    with pytest.raises(PCRProviderProtocolError, match="schema_validation"):
        canonicalize_pcr_direct_tool_call(
            "run_command", json.dumps({"arguments":{
                "command":"echo ok", "timeout_s":10,
                "helper_mode":"execute", "capture_surface":"artifact",
            }}),
        )

def test_direct_read_file_and_submit_roundtrip_to_unchanged_canonical_pcr_turn() -> None:
    from aether.pcr_provider_protocol import canonicalize_pcr_direct_tool_call
    action, action_receipt = canonicalize_pcr_direct_tool_call(
        "read_file", json.dumps({"arguments": {"path": "/app/data.txt"}}),
    )
    assert json.loads(action) == {
        "kind": "act",
        "action": {"kind": "read_file", "arguments": {"path": "/app/data.txt"}},
    }
    assert action_receipt["provider_turn_arguments_transport"] == "direct_native_function"
    finish_intent, intent_receipt = canonicalize_pcr_direct_tool_call(
        "finish_intent", json.dumps({"claim": "done", "evidence_refs": ["evidence:0123456789abcdef"]}),
    )
    assert json.loads(finish_intent) == {
        "kind": "finish_intent",
        "claim": "done",
        "evidence_refs": ["evidence:0123456789abcdef"],
    }
    assert intent_receipt["provider_turn_arguments_transport"] == "direct_native_function"
    finish, finish_receipt = canonicalize_pcr_direct_tool_call(
        "finish", json.dumps({"claim": "done", "evidence_refs": ["evidence:0123456789abcdef"]}),
    )
    assert json.loads(finish)["kind"] == "finish"
    assert finish_receipt["provider_turn_arguments_transport"] == "direct_native_function"


def test_stable_prefix_cache_uses_current_provider_retention_literal() -> None:
    client = _Client(_response(_call()))
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-luna", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="stable_prefix",
    )
    model.call_with_telemetry_scope(
        [{"role":"user","content":"inspect current state"}],
        run_id="cache-literal-run", task_id="cache-literal-task",
    )
    request = client.responses.requests[0]
    assert request["prompt_cache_key"]
    assert "prompt_cache_retention" not in request
    event = model.drain_telemetry()[0]
    assert event["prompt_cache_key_mode"] == "stable_prefix"
    assert event["prompt_cache_retention"] is None


def test_usage_telemetry_preserves_cache_write_tokens_and_missing_is_unmeasured() -> None:
    from aether.providers.azure_model import _usage_telemetry

    reported = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=2000,
            output_tokens=25,
            total_tokens=2025,
            input_tokens_details=SimpleNamespace(
                cached_tokens=1500,
                cache_write_tokens=250,
            ),
            output_tokens_details=SimpleNamespace(reasoning_tokens=10),
        )
    )
    row = _usage_telemetry(reported)
    assert row["cache_metrics_status"] == "reported"
    assert row["cached_input_tokens"] == 1500
    assert row["cache_write_tokens"] == 250

    omitted_write = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=2000,
            output_tokens=25,
            total_tokens=2025,
            input_tokens_details=SimpleNamespace(cached_tokens=1500),
            output_tokens_details=SimpleNamespace(reasoning_tokens=10),
        )
    )
    row = _usage_telemetry(omitted_write)
    assert row["cached_input_tokens"] == 1500
    assert row["cache_write_tokens"] is None


def test_one_function_call_plus_assistant_message_never_spends_protocol_repair() -> None:
    message = SimpleNamespace(
        id='msg-live-shape', type='message', role='assistant',
        content=[SimpleNamespace(type='output_text', text='I will inspect the shard metadata now.')],
    )
    canonical, receipt = canonicalize_pcr_native_tool_output(_response(message, _call(name='read_file')))
    assert json.loads(canonical)['action']['kind'] == 'read_file'
    assert receipt['native_tool_call_count'] == 1
    assert receipt['provider_ignored_assistant_message_count'] == 1


def test_inspect_diff_native_description_and_result_semantics_are_truthful() -> None:
    from aether.pcr_provider_protocol import pcr_direct_provider_tools
    tools = {row["name"]: row for row in pcr_direct_provider_tools()}
    description = tools["inspect_diff"]["description"].lower()
    assert "not a current filesystem diff" in description
    assert "exact path" in description

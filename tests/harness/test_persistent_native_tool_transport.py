from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.model_request_contract import ExpectedModelRequest, preflight_model_request
from aether.providers.azure_model import (
    AzureModelCallable,
    AzureProviderOutputError,
    canonicalize_persistent_native_tool_output,
)


def _turn(*, kind: str = "read_file") -> str:
    return json.dumps({
        "turn": {
            "kind": "act",
            "action": {
                "kind": kind,
                "capability_id": "filesystem",
                "arguments": {"path": "/app/input.txt"},
            },
        }
    })


def _function_call(arguments: str | None = None, *, name: str = "persistent_turn", suffix: str = "1") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"fc-{suffix}",
        type="function_call",
        call_id=f"call-{suffix}",
        name=name,
        arguments=_turn() if arguments is None else arguments,
    )


def _message(text: str = "unexpected") -> SimpleNamespace:
    return SimpleNamespace(
        id="msg-1",
        type="message",
        role="assistant",
        content=[SimpleNamespace(type="output_text", text=text)],
    )


def _response(*items: object) -> SimpleNamespace:
    return SimpleNamespace(
        id="resp-1",
        status="completed",
        output=list(items),
        usage=None,
        error=None,
        incomplete_details=None,
    )


def test_native_tool_decoder_accepts_exactly_one_persistent_turn() -> None:
    canonical, receipt = canonicalize_persistent_native_tool_output(_response(_function_call()))
    decoded = json.loads(canonical)
    assert decoded["kind"] == "act"
    assert decoded["action"]["kind"] == "read_file"
    assert receipt["native_tool_name"] == "persistent_turn"
    assert receipt["native_tool_call_count"] == 1
    assert receipt["candidate_message_count"] == 0


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (_response(), "provider_persistent_v0_native_tool_call_count_invalid"),
        (
            _response(_function_call(suffix="1"), _function_call(suffix="2")),
            "provider_persistent_v0_native_tool_call_count_invalid",
        ),
        (
            _response(_function_call(name="wrong_tool")),
            "provider_persistent_v0_native_tool_name_invalid",
        ),
        (
            _response(_function_call(), _message()),
            "provider_persistent_v0_native_tool_mixed_output",
        ),
        (
            _response(_function_call(), SimpleNamespace(type="computer_call", id="cc-1")),
            "provider_persistent_v0_native_tool_mixed_output",
        ),
        (
            _response(_function_call(_turn() + "\n" + _turn())),
            "provider_persistent_v0_multiple_objects_in_message",
        ),
    ],
)
def test_native_tool_decoder_fails_closed(response: object, code: str) -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        canonicalize_persistent_native_tool_output(response)
    assert excinfo.value.code == code


class _FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        return self.response

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("foreground completed fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not cancel")


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.responses = _FakeResponses(response)


def _model(response: object) -> tuple[AzureModelCallable, _FakeClient]:
    client = _FakeClient(response)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-frontier",
        effort="low",
        role="solver",
        solver_protocol="persistent_v0",
        transport="responses_tools",
        responses_background=False,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode="off",
    )
    return model, client


def test_native_tool_transport_forces_one_nonparallel_tool_call() -> None:
    model, client = _model(_response(_function_call()))
    canonical = model([{"role": "user", "content": "Read the file next."}], max_output_tokens=16000)

    assert json.loads(canonical)["action"]["kind"] == "read_file"
    assert len(client.responses.requests) == 1
    request = client.responses.requests[0]
    assert request["background"] is False
    assert request["parallel_tool_calls"] is False
    assert request["max_tool_calls"] == 1
    assert request["tool_choice"] == {"type": "function", "name": "persistent_turn"}
    assert "text" not in request
    tools = request["tools"]
    assert isinstance(tools, list) and len(tools) == 1
    assert tools[0]["name"] == "persistent_turn"
    assert tools[0]["strict"] is True
    assert tools[0]["parameters"]["required"] == ["turn"]

    telemetry = model.drain_telemetry()
    assert len(telemetry) == 1
    assert telemetry[0]["structured_output_mode"] == "persistent_v0_primary_turn_native_tool"
    assert telemetry[0]["max_tool_calls_requested"] == 1
    assert telemetry[0]["parallel_tool_calls"] is False
    assert telemetry[0]["native_tool_call_count"] == 1


def test_native_tool_preflight_is_explicit_and_admitted() -> None:
    model, _client = _model(_response(_function_call()))
    row = preflight_model_request(
        model,
        ExpectedModelRequest(logical_role="solver", max_output_tokens=16000),
    )
    assert row["provider"] == "azure_openai_responses"
    assert row["structured_output_mode"] == "persistent_v0_primary_turn_native_tool"
    assert row["native_tool_name"] == "persistent_turn"
    assert row["max_tool_calls_requested"] == 1
    assert row["parallel_tool_calls"] is False
    assert row["background"] is False


def test_native_tool_transport_rejects_non_persistent_non_verifier_roles() -> None:
    client = _FakeClient(_response(_function_call()))
    with pytest.raises(ValueError, match="PERSISTENT V0 Solver or Verifier"):
        AzureModelCallable(
            client=client,  # type: ignore[arg-type]
            deployment="unit-test-frontier",
            effort="low",
            role="architect",
            solver_protocol="solver_v1",
            transport="responses_tools",
            responses_background=False,
            poll_interval_s=1.0,
            poll_timeout_s=30.0,
            max_retries=0,
        )


def test_native_tool_provider_error_is_preserved_in_telemetry() -> None:
    model, _client = _model(_response(_function_call(_turn() + "\n" + _turn())))
    with pytest.raises(AzureProviderOutputError) as excinfo:
        model([{"role": "user", "content": "Choose one action."}])
    assert excinfo.value.code == "provider_persistent_v0_multiple_objects_in_message"
    event = model.drain_telemetry()[0]
    assert event["status"] == "failed"
    assert event["provider_output_error"] == "provider_persistent_v0_multiple_objects_in_message"

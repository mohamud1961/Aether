import pytest

from runner import kernel_tpm_pacer as kernel_tpm_pacer_module
from runner import model_client as base_model_client
from runner.aether2 import model_client as aether2_model_client
from runner.aether2.model_client import Aether2ModelClient
from runner.aether2.tools import TOOL_SCHEMAS
from runner.model_client import ModelClientError, make_openai_chat_completions_route


def _success_response(
    *,
    text: str = "ok",
    input_tokens: int = 100,
    cached_input_tokens: int = 80,
    output_tokens: int = 20,
    tool_name: str = "run_command",
) -> dict[str, object]:
    return {
        "text": text,
        "tool_calls": [{"type": "function", "name": tool_name, "arguments": "{}"}],
        "usage": {
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        "status": "completed",
    }


def test_model_client_passes_native_tools_and_normalizes_usage(monkeypatch) -> None:
    route = make_openai_chat_completions_route(model_name="aether2-native-tools")
    calls: list[tuple[list[dict[str, object]], dict[str, object]]] = []

    def fake_complete(self, messages, **kwargs):
        calls.append((list(messages), dict(kwargs)))
        return _success_response()

    monkeypatch.setattr(base_model_client.OpenAIAPIKeyModelClient, "complete", fake_complete)

    client = Aether2ModelClient(route)
    response = client.call(
        [{"role": "user", "content": "hi"}],
        TOOL_SCHEMAS[:1],
        cache_prefix_len=4,
    )

    # Aether2ModelClient flattens Responses-API-shaped tool specs
    # ({"type": "function", "function": {...}}) into the flat Chat
    # Completions shape ({"type": "function", **function_spec}) before
    # handing them to the underlying provider client.
    assert calls[0][1]["tools"] == [
        {"type": "function", **TOOL_SCHEMAS[0]["function"]}
    ]
    # `cache_prefix_len` is an Aether-2-internal accounting hint and must NOT
    # be forwarded into the underlying provider client's request kwargs (the
    # Azure/OpenAI adapters splat unrecognized kwargs straight into the HTTP
    # payload, which the API rejects as an unknown parameter).
    assert "cache_prefix_len" not in calls[0][1]
    assert response.tool_calls[0]["name"] == "run_command"
    assert response.usage["fresh_input_tokens"] == 20
    assert response.raw_response["usage"]["cached_input_tokens"] == 80


@pytest.mark.parametrize("status_code", [429, 503])
def test_model_client_retries_transient_errors(monkeypatch, status_code: int) -> None:
    route = make_openai_chat_completions_route(model_name=f"aether2-retry-{status_code}")
    calls: list[tuple[list[dict[str, object]], dict[str, object]]] = []
    attempts = {"count": 0}

    def fake_complete(self, messages, **kwargs):
        calls.append((list(messages), dict(kwargs)))
        if attempts["count"] == 0:
            attempts["count"] += 1
            raise ModelClientError("retry", status_code=status_code)
        return _success_response(text="ok", output_tokens=1)

    sleep_calls: list[float] = []
    monkeypatch.setattr(base_model_client.OpenAIAPIKeyModelClient, "complete", fake_complete)
    monkeypatch.setattr(aether2_model_client.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    client = Aether2ModelClient(route, backoff_sec=0.25)
    response = client.call([{"role": "user", "content": "hi"}], TOOL_SCHEMAS[:1], cache_prefix_len=0)

    assert len(calls) == 2
    assert sleep_calls == [0.25]
    assert response.text == "ok"


def test_model_client_does_not_swallow_non_transient_errors(monkeypatch) -> None:
    route = make_openai_chat_completions_route(model_name="aether2-non-transient")
    calls: list[tuple[list[dict[str, object]], dict[str, object]]] = []

    def fake_complete(self, messages, **kwargs):
        calls.append((list(messages), dict(kwargs)))
        raise ModelClientError("bad request", status_code=400)

    sleep_calls: list[float] = []
    monkeypatch.setattr(base_model_client.OpenAIAPIKeyModelClient, "complete", fake_complete)
    monkeypatch.setattr(aether2_model_client.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    client = Aether2ModelClient(route, backoff_sec=0.25, max_attempts=3)

    with pytest.raises(ModelClientError) as excinfo:
        client.call([{"role": "user", "content": "hi"}], TOOL_SCHEMAS[:1], cache_prefix_len=0)

    assert len(calls) == 1
    assert sleep_calls == []
    assert excinfo.value.status_code == 400


def test_model_client_uses_tpm_pacer_from_route_factory(monkeypatch) -> None:
    route = make_openai_chat_completions_route(
        model_name="aether2-pacer",
        request_settings={
            "tpm_pacer_enabled": True,
            "tpm_limit": 1,
            "tpm_window_sec": 60,
            "tpm_throttle_fraction": 1.0,
            "tpm_pause_sec": 0,
            "tpm_count_mode": "output",
        },
    )
    calls: list[tuple[list[dict[str, object]], dict[str, object]]] = []

    def fake_complete(self, messages, **kwargs):
        calls.append((list(messages), dict(kwargs)))
        return _success_response(text="paced", output_tokens=1)

    sleep_calls: list[float] = []
    monkeypatch.setattr(base_model_client.OpenAIAPIKeyModelClient, "complete", fake_complete)
    monkeypatch.setattr(kernel_tpm_pacer_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    client = Aether2ModelClient(route)

    assert isinstance(client._client, kernel_tpm_pacer_module.RollingTPMPacer)

    first = client.call([{"role": "user", "content": "hi"}], TOOL_SCHEMAS[:1], cache_prefix_len=4)
    second = client.call([{"role": "user", "content": "hi again"}], TOOL_SCHEMAS[:1], cache_prefix_len=4)

    assert len(calls) == 2
    assert calls[0][1]["tools"] == [
        {"type": "function", **TOOL_SCHEMAS[0]["function"]}
    ]
    assert "cache_prefix_len" not in calls[0][1]
    assert sleep_calls and sleep_calls[0] > 0
    assert first.text == "paced"
    assert second.tool_calls[0]["name"] == "run_command"

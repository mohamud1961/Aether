from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

import pytest

from aether.providers.chat_model import (
    ChatCompletionsModelCallable,
    ChatModelError,
    ChatModelOutputError,
    _normalize_endpoint,
    make_chat_completions_callable,
)
from aether.provider_budget import ProviderBudgetError
from aether.long_command_mode import LONG_COMMAND_MODE_ENV
from aether.model_hooks import ModelHooks
from aether.persistent_provider_protocol import PERSISTENT_SHELL_SENTENCE, PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1
from aether.runtime_ir import ACTION_SCHEMA
from aether.run_cancellation import RunCancellationRequested
from aether.run_deadline import KernelRunTimeout, run_deadline


def _tool_response(name: str = "read_file", arguments: str = '{"arguments":{"path":"/tmp/input"}}') -> dict:
    return {
        "id": "chat-response-id-is-not-used-for-continuity",
        "choices": [{
            "index": 0,
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }],
                "reasoning_content": "private reasoning remains provider-local",
            },
        }],
        "usage": {
            "prompt_tokens": 41,
            "completion_tokens": 12,
            "total_tokens": 53,
            "prompt_tokens_details": {"cached_tokens": 4},
            "completion_tokens_details": {"reasoning_tokens": 3},
        },
    }


def test_background_tools_compose_with_edit_surface_without_wrappers_and_keep_shell_state_claim(monkeypatch) -> None:
    monkeypatch.setenv(LONG_COMMAND_MODE_ENV, "background_v1")
    model = ChatCompletionsModelCallable(
        transport=FakeTransport(), deployment="test", role="solver", native_persistent_tools=True,
        tool_surface_mode=PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1,
    )
    tools = model._tools_for_scope(None)
    by_name = {tool["function"]["name"]: tool["function"] for tool in tools}
    assert {"job_output", "job_wait", "job_stop"} <= set(by_name)
    for name in ("job_output", "job_wait", "job_stop"):
        params = by_name[name]["parameters"]
        assert "arguments" not in params["properties"]
    assert PERSISTENT_SHELL_SENTENCE in by_name["run_command"]["description"]


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        return self.responses.pop(0)


def test_provider_request_latency_measures_only_the_transport_call() -> None:
    class SlowTransport(FakeTransport):
        def create(self, **request):
            time.sleep(0.04)
            return super().create(**request)

    model = ChatCompletionsModelCallable(
        transport=SlowTransport(_tool_response()),
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )
    model([{"role": "user", "content": "read /tmp/input"}], max_output_tokens=100)

    telemetry = model.drain_telemetry()
    assert len(telemetry) == 1
    assert telemetry[0]["provider_request_elapsed_s"] >= 0.03
    assert telemetry[0]["elapsed_s"] + 0.001 >= telemetry[0]["provider_request_elapsed_s"]


def test_provider_attempt_reports_request_context_anatomy_as_utf8_bytes() -> None:
    tools = [{
        "type": "function",
        "function": {
            "name": "inspect",
            "description": "simple schema",
            "parameters": {"type": "object", "properties": {}},
        },
    }]
    messages = [
        {"role": "system", "content": "prefix ✓"},
        {
            "role": "assistant",
            "content": "old answer 🌅",
            "reasoning_content": "reasoning ñ",
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "inspect", "arguments": "{}"},
            }],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "tool output 🧾"},
        {"role": "user", "content": "current 🌻"},
    ]
    transport = FakeTransport({
        "choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "ok", "tool_calls": []},
        }],
    })
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        tools=tools,
        native_persistent_tools=False,
    )

    model(messages, max_output_tokens=32)

    assert transport.requests[0]["messages"] == messages
    assert transport.requests[0]["tools"] == tools
    telemetry = model.drain_telemetry()
    assert len(telemetry) == 1
    assert telemetry[0]["request_context_anatomy"] == {
        "tool_schema_bytes": len(json.dumps(
            tools, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
        ).encode("utf-8")),
        "system_bytes": len("prefix ✓".encode("utf-8")),
        "history_assistant_content_bytes": len("old answer 🌅".encode("utf-8")),
        "history_assistant_reasoning_bytes": len("reasoning ñ".encode("utf-8")),
        "history_tool_call_bytes": len(json.dumps(
            messages[1]["tool_calls"], sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, default=str,
        ).encode("utf-8")),
        "history_tool_result_bytes": len("tool output 🧾".encode("utf-8")),
        "current_context_bytes": len("current 🌻".encode("utf-8")),
        "history_exchange_count": 1,
    }


def test_real_model_hooks_reanchors_fresh_thin_context_with_tool_result_history() -> None:
    first_response = _tool_response()
    first_response["choices"][0]["message"].update(annotations=None, audio=None, function_call=None)
    first_response["choices"][0]["message"]["tool_calls"][0]["id"] = "call-1"
    second_response = _tool_response(arguments='{"arguments":{"path":"/tmp/next"}}')
    second_response["choices"][0]["message"]["tool_calls"][0]["id"] = "call-2"
    third_response = _tool_response(arguments='{"arguments":{"path":"/tmp/final"}}')
    third_response["choices"][0]["message"]["tool_calls"][0]["id"] = "call-3"
    transport = FakeTransport(first_response, second_response, third_response)
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="solver", native_persistent_tools=True,
    )
    hooks = ModelHooks(
        model,
        lambda _messages, **_kwargs: "{}",
        run_id="run-1",
        task_id="task-1",
        solver_max_output_tokens=400,
    )
    compiled = SimpleNamespace(
        action_schema=ACTION_SCHEMA,
        config_realization={},
        selected_capability_ids=lambda: set(),
    )
    first_messages = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": "fresh context one"},
    ]
    second_messages = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": "fresh context two"},
    ]
    third_messages = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": "fresh context three"},
    ]
    first = hooks.solve(first_messages, compiled)
    second = hooks.solve(second_messages, compiled)
    third = hooks.solve(third_messages, compiled)

    assert first.actions[0].kind == "read_file"
    assert second.actions[0].arguments["path"] == "/tmp/next"
    assert third.actions[0].arguments["path"] == "/tmp/final"
    sent = transport.requests[1]
    assert sent["messages"][0] == second_messages[0]
    assert sent["messages"][1]["role"] == "assistant"
    assert not {"annotations", "audio", "function_call"} & set(sent["messages"][1])
    assert sent["messages"][1]["tool_calls"][0]["id"] == "call-1"
    assert sent["messages"][1]["reasoning_content"] == "private reasoning remains provider-local"
    assert sent["messages"][2] == {
        "role": "tool", "tool_call_id": "call-1", "content": "fresh context two",
    }
    assert "previous_response_id" not in sent
    assert "response_id" not in sent
    assert sent["tool_choice"] == "required"
    assert sent["parallel_tool_calls"] is False
    sent_third = transport.requests[2]
    assert sent_third["messages"][0] == third_messages[0]
    assert [message["role"] for message in sent_third["messages"][1:]] == [
        "assistant", "tool", "assistant", "tool",
    ]
    assert sent_third["messages"][1]["tool_calls"][0]["id"] == "call-1"
    assert sent_third["messages"][2]["tool_call_id"] == "call-1"
    assert sent_third["messages"][2]["content"] == "fresh context two"
    assert sent_third["messages"][3]["tool_calls"][0]["id"] == "call-2"
    assert sent_third["messages"][4]["tool_call_id"] == "call-2"
    assert sent_third["messages"][4]["content"] == "fresh context three"

    telemetry = model.drain_telemetry()
    assert len(telemetry) == 3
    assert telemetry[0]["run_id"] == "run-1"
    assert telemetry[0]["task_id"] == "task-1"
    assert telemetry[0]["input_tokens"] == 41
    assert telemetry[0]["cached_input_tokens"] == 4
    assert telemetry[0]["reasoning_tokens"] == 3
    assert telemetry[0]["raw_provider_request"]["messages"] == first_messages
    assert telemetry[0]["raw_provider_output"]["choices"][0]["finish_reason"] == "tool_calls"


def test_rejected_model_hooks_turn_does_not_poison_committed_transcript() -> None:
    first_response = _tool_response()
    first_response["choices"][0]["message"]["tool_calls"][0]["id"] = "call-1"
    rejected_response = {
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {"role": "assistant", "content": None, "tool_calls": []},
        }],
    }
    third_response = _tool_response(arguments='{"arguments":{"path":"/tmp/recovered"}}')
    third_response["choices"][0]["message"]["tool_calls"][0]["id"] = "call-3"
    transport = FakeTransport(first_response, rejected_response, third_response)
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="solver", native_persistent_tools=True,
    )
    hooks = ModelHooks(
        model,
        lambda _messages, **_kwargs: "{}",
        run_id="run-reject",
        task_id="task-reject",
        solver_max_output_tokens=400,
    )
    compiled = SimpleNamespace(
        action_schema=ACTION_SCHEMA,
        config_realization={},
        selected_capability_ids=lambda: set(),
    )
    hooks.solve([{"role": "system", "content": "immutable prefix"}, {"role": "system", "content": "first"}], compiled)
    with pytest.raises(Exception, match="solver output could not be parsed"):
        hooks.solve([{"role": "system", "content": "immutable prefix"}, {"role": "system", "content": "rejected"}], compiled)
    hooks.solve([{"role": "system", "content": "immutable prefix"}, {"role": "system", "content": "recovered"}], compiled)

    recovered = transport.requests[2]["messages"]
    assert [message["role"] for message in recovered[1:]] == ["assistant", "tool"]
    assert recovered[1]["tool_calls"][0]["id"] == "call-1"
    assert recovered[2]["content"] == "recovered"


def test_truncated_chat_choice_fails_closed_even_when_partial_content_exists() -> None:
    truncated = {
        "choices": [{
            "finish_reason": "length",
            "message": {"role": "assistant", "content": "partial"},
        }],
    }
    # The adapter escalates once at a doubled cap; the escalated response is
    # also truncated, so the failure is still closed.
    transport = FakeTransport(truncated, truncated)
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="verifier", native_persistent_tools=False,
    )
    with pytest.raises(ChatModelOutputError, match="provider_output_truncated"):
        model([{"role": "user", "content": "Answer."}], max_output_tokens=16)
    assert [r["max_tokens"] for r in transport.requests] == [16, 32]
    row = model.drain_telemetry()[-1]
    assert row["status"] == "failed"
    assert row["raw_provider_output"]["choices"][0]["message"]["content"] == "partial"


class DenyingGuard:
    contract = SimpleNamespace(schema_version="aether.provider_budget.v2")

    def reserve(self, role, request):
        del role, request
        raise ProviderBudgetError("budget deny for test")


def test_budget_admission_denial_happens_before_transport_dispatch() -> None:
    transport = FakeTransport(_tool_response())
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        budget_guard=DenyingGuard(),  # type: ignore[arg-type]
    )
    with pytest.raises(ProviderBudgetError, match="budget deny"):
        model([{"role": "user", "content": "Read."}], max_output_tokens=32)
    assert transport.requests == []
    row = model.drain_telemetry()[0]
    assert row["status"] == "budget_denied"
    assert row["provider_budget_admission"] == "denied"


def test_text_route_requires_one_stop_choice_and_normalizes_missing_usage() -> None:
    transport = FakeTransport({
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "done"}}],
        "usage": None,
    })
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="verifier", native_persistent_tools=False,
    )
    assert model([{"role": "system", "content": "Be exact."}, {"role": "user", "content": "Go."}], max_output_tokens=32) == "done"
    row = model.drain_telemetry()[0]
    assert row["usage_status"] == "omitted"
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None
    assert row["finish_reason"] == "stop"


def test_bound_run_cancellation_is_checked_before_transport_dispatch() -> None:
    transport = FakeTransport(_tool_response())
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="solver", native_persistent_tools=True,
    )
    cancelled = threading.Event()
    cancelled.set()
    model.bind_run_cancellation(cancelled)
    with pytest.raises(RunCancellationRequested):
        model([{"role": "user", "content": "Read."}], max_output_tokens=32)
    assert transport.requests == []


def test_cancellation_after_transport_return_is_not_admitted() -> None:
    cancelled = threading.Event()

    class CancellingTransport(FakeTransport):
        def create(self, **request):
            result = super().create(**request)
            cancelled.set()
            return result

    transport = CancellingTransport(_tool_response())
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="solver", native_persistent_tools=True,
    )
    model.bind_run_cancellation(cancelled)
    with pytest.raises(RunCancellationRequested):
        model([{"role": "user", "content": "Read."}], max_output_tokens=32)
    assert len(transport.requests) == 1
    assert model.drain_telemetry()[0]["status"] == "failed"


def test_bound_run_deadline_is_checked_before_transport_dispatch() -> None:
    transport = FakeTransport(_tool_response())
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="solver", native_persistent_tools=True,
    )
    with run_deadline(time.monotonic() - 1.0):
        with pytest.raises(KernelRunTimeout):
            model([{"role": "user", "content": "Read."}], max_output_tokens=32)
    assert transport.requests == []


def test_azure_chat_factory_uses_openai_v1_and_caps_transport_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    from aether.model_profile import GLM_RESEARCH_PROFILE
    import aether.providers.chat_model as chat_model

    monkeypatch.setenv(GLM_RESEARCH_PROFILE.endpoint_env, "https://resource.openai.azure.com/some/path")
    monkeypatch.setenv(GLM_RESEARCH_PROFILE.key_env, "test-key")
    monkeypatch.setenv(GLM_RESEARCH_PROFILE.deployment_env, GLM_RESEARCH_PROFILE.model_id)
    monkeypatch.setattr(chat_model, "require_provider_authorization", lambda _profile: None)
    captured: dict[str, object] = {}

    class Client:
        def __init__(self) -> None:
            response = _tool_response()
            response["usage"]["completion_tokens"] = 200
            self.chat = SimpleNamespace(completions=FakeTransport(response))

    def factory(**kwargs):
        captured.update(kwargs)
        return Client()

    make_chat_completions_callable(
        profile=GLM_RESEARCH_PROFILE,
        client_factory=factory,
        timeout_s=999.0,
    )
    assert captured == {
        "api_key": "test-key",
        "base_url": "https://resource.openai.azure.com/openai/v1/",
        "max_retries": 0,
        "timeout": 999.0,
    }


    captured.clear()
    make_chat_completions_callable(
        profile=GLM_RESEARCH_PROFILE,
        client_factory=factory,
    )
    assert captured["timeout"] == GLM_RESEARCH_PROFILE.provider_poll_timeout_s == 1800


def test_shared_limiter_factory_requires_and_binds_tpm_and_rpm(monkeypatch, tmp_path) -> None:
    from aether.model_profile import GLM_RESEARCH_PROFILE
    from aether.provider_pacing import SharedDeploymentTokenPacer
    import aether.providers.chat_model as chat_model

    profile = GLM_RESEARCH_PROFILE
    monkeypatch.setenv(profile.endpoint_env, "https://resource.openai.azure.com")
    monkeypatch.setenv(profile.key_env, "test-key")
    monkeypatch.setenv(profile.deployment_env, profile.model_id)
    monkeypatch.setenv("AETHER_PROVIDER_SHARED_LIMITER_PATH", str(tmp_path / "limiter.json"))
    monkeypatch.setenv("AETHER_PROVIDER_TPM_LIMIT", "300000")
    monkeypatch.delenv("AETHER_PROVIDER_RPM_LIMIT", raising=False)
    monkeypatch.setattr(chat_model, "require_provider_authorization", lambda _profile: None)

    class Client:
        chat = SimpleNamespace(completions=FakeTransport(_tool_response()))

    factory = lambda **_kwargs: Client()
    with pytest.raises(ChatModelError, match="both AETHER_PROVIDER_TPM_LIMIT and AETHER_PROVIDER_RPM_LIMIT"):
        make_chat_completions_callable(profile=profile, client_factory=factory)

    monkeypatch.setenv("AETHER_PROVIDER_RPM_LIMIT", "300")
    monkeypatch.delenv("AETHER_PROVIDER_WINDOW_ANCHOR", raising=False)
    model = make_chat_completions_callable(profile=profile, client_factory=factory)
    assert isinstance(model._throughput_pacer, SharedDeploymentTokenPacer)
    assert model._throughput_pacer.token_limit == 300000
    assert model._throughput_pacer.request_limit == 300
    assert model._throughput_pacer.window_anchor == "settlement"

    monkeypatch.setenv("AETHER_PROVIDER_WINDOW_ANCHOR", "dispatch")
    dispatch_model = make_chat_completions_callable(profile=profile, client_factory=factory)
    assert isinstance(dispatch_model._throughput_pacer, SharedDeploymentTokenPacer)
    assert dispatch_model._throughput_pacer.window_anchor == "dispatch"

    monkeypatch.delenv("AETHER_PROVIDER_SHARED_LIMITER_PATH")
    with pytest.raises(ChatModelError, match="AETHER_PROVIDER_RPM_LIMIT requires the shared deployment limiter"):
        make_chat_completions_callable(profile=profile, client_factory=factory)


def test_serial_settlement_factory_defaults_to_cap_and_allows_observed_challenger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aether.model_profile import GLM_RESEARCH_PROFILE
    from aether.provider_pacing import SerialTokenPacer
    import aether.providers.chat_model as chat_model

    profile = GLM_RESEARCH_PROFILE
    monkeypatch.setenv(profile.endpoint_env, "https://resource.openai.azure.com")
    monkeypatch.setenv(profile.key_env, "test-key")
    monkeypatch.setenv(profile.deployment_env, profile.model_id)
    monkeypatch.setenv("AETHER_PROVIDER_TPM_LIMIT", "300000")
    monkeypatch.delenv("AETHER_PROVIDER_RPM_LIMIT", raising=False)
    monkeypatch.delenv("AETHER_PROVIDER_SHARED_LIMITER_PATH", raising=False)
    monkeypatch.delenv("AETHER_PROVIDER_SERIAL_SETTLEMENT", raising=False)
    monkeypatch.setattr(chat_model, "require_provider_authorization", lambda _profile: None)

    class Client:
        def __init__(self) -> None:
            response = _tool_response()
            response["usage"]["completion_tokens"] = 200
            self.chat = SimpleNamespace(completions=FakeTransport(response))

    factory = lambda **_kwargs: Client()
    default_model = make_chat_completions_callable(profile=profile, client_factory=factory)
    assert isinstance(default_model._throughput_pacer, SerialTokenPacer)
    assert default_model._throughput_pacer.settlement_mode == "requested_output_cap"
    default_model([{"role": "user", "content": "Inspect the workspace."}], max_output_tokens=16_384)
    default_row = default_model.drain_telemetry()[0]
    assert default_row["output_tokens"] == 200
    assert default_row["throughput_reconciled_tokens"] == 16_425

    monkeypatch.setenv("AETHER_PROVIDER_SERIAL_SETTLEMENT", "observed_output")
    challenger_model = make_chat_completions_callable(profile=profile, client_factory=factory)
    assert isinstance(challenger_model._throughput_pacer, SerialTokenPacer)
    assert challenger_model._throughput_pacer.settlement_mode == "observed_output"
    challenger_model([{"role": "user", "content": "Inspect the workspace."}], max_output_tokens=16_384)
    challenger_row = challenger_model.drain_telemetry()[0]
    assert challenger_row["output_tokens"] == 200
    assert challenger_row["throughput_reconciled_tokens"] == 241


def test_endpoint_normalization_does_not_retain_deployment_path() -> None:
    assert _normalize_endpoint("https://resource.openai.azure.com/openai/deployments/glm", azure=True) == (
        "https://resource.openai.azure.com/openai/v1/"
    )
    assert _normalize_endpoint("https://api.example.test/v1", azure=False) == "https://api.example.test/v1/"


def test_malformed_tool_response_preserves_actual_usage_without_admitting_history():
    response = _tool_response(name="run_command", arguments="{}")
    response["usage"]["completion_tokens"] = 16000
    model = ChatCompletionsModelCallable(
        transport=FakeTransport(response), deployment="glm-test", role="solver",
        native_persistent_tools=True,
    )
    with pytest.raises(ChatModelOutputError):
        model([{"role": "user", "content": "Inspect the workspace."}], max_output_tokens=16000)
    row = model.drain_telemetry()[0]
    assert row["status"] == "failed"
    assert row["input_tokens"] == 41
    assert row["output_tokens"] == 16000
    assert row["cached_input_tokens"] == 4
    assert not model._pending_continuity_states


class _CapacityPacer:
    def __init__(self, token_limit: int):
        self.token_limit = token_limit
        self.window_s = 60.0
        self.admitted: list[int] = []

    @staticmethod
    def approximate_request_tokens(request_bytes: int, max_output_tokens: int) -> int:
        return (int(request_bytes) + 3) // 4 + int(max_output_tokens)

    def admit(self, *, estimated_tokens: int):
        self.admitted.append(int(estimated_tokens))
        return {
            "throughput_token_limit": self.token_limit,
            "throughput_window_s": self.window_s,
            "throughput_estimated_tokens": int(estimated_tokens),
            "throughput_wait_s": 0.0,
            "throughput_spacing_s": 0.0,
            "throughput_rolling_wait_s": 0.0,
            "throughput_active_reserved_tokens": int(estimated_tokens),
            "throughput_single_request_admission": "provider_authoritative",
        }

    def reconcile_success(self, *, input_tokens, requested_output_tokens, output_tokens=None):
        return {"throughput_usage_reconciled": True}

    def note_rate_limit(self):
        pass


def test_explicit_chat_history_reanchors_only_when_declared_capacity_would_overflow() -> None:
    first_response = _tool_response()
    first_response["choices"][0]["message"]["tool_calls"][0]["id"] = "call-cap-1"
    first_response["choices"][0]["message"]["reasoning_content"] = "r" * 160_000
    second_response = _tool_response(arguments='{"arguments":{"path":"/tmp/after-reanchor"}}')
    second_response["choices"][0]["message"]["tool_calls"][0]["id"] = "call-cap-2"
    transport = FakeTransport(first_response, second_response)
    pacer = _CapacityPacer(token_limit=30_000)
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=pacer,  # type: ignore[arg-type]
    )
    hooks = ModelHooks(
        model,
        lambda _messages, **_kwargs: "{}",
        run_id="run-capacity",
        task_id="task-capacity",
        solver_max_output_tokens=400,
    )
    compiled = SimpleNamespace(
        action_schema=ACTION_SCHEMA,
        config_realization={},
        selected_capability_ids=lambda: set(),
    )
    first_messages = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": "current context one"},
    ]
    second_messages = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": "current context two"},
    ]

    hooks.solve(first_messages, compiled)
    hooks.solve(second_messages, compiled)

    assert transport.requests[0]["messages"] == first_messages
    assert transport.requests[1]["messages"] == second_messages
    rows = model.drain_telemetry()
    assert rows[0].get("throughput_capacity_reanchor") is not True
    assert rows[1]["throughput_capacity_reanchor"] is True
    assert rows[1]["throughput_pre_reanchor_estimated_tokens"] > pacer.token_limit
    assert rows[1]["throughput_post_reanchor_estimated_tokens"] <= pacer.token_limit
    continuity = model.drain_continuity_admission_telemetry()
    assert any(row.get("event_kind") == "chat_continuity_capacity_reanchor" for row in continuity)


def test_fresh_chat_request_over_declared_capacity_fails_before_dispatch() -> None:
    transport = FakeTransport(_tool_response())
    pacer = _CapacityPacer(token_limit=1)
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=pacer,  # type: ignore[arg-type]
    )
    with pytest.raises(ChatModelError, match="declared provider throughput limit"):
        model([{"role": "user", "content": "Read."}], max_output_tokens=32)
    assert transport.requests == []
    row = model.drain_telemetry()[0]
    assert row["throughput_single_request_admission"] == "rejected_local_capacity"
    assert row["status"] == "failed"


def test_per_request_timeout_uses_remaining_task_budget() -> None:
    captured = {}
    class Transport:
        def create(self, **request):
            captured.update(request)
            return {
                "model": "glm-test",
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "ok"},
                }],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
    model = ChatCompletionsModelCallable(
        transport=Transport(),
        deployment="glm-test",
        native_persistent_tools=False,
        provider_timeout_s=1800,
    )
    deadline = time.monotonic() + 5.0
    with run_deadline(deadline):
        assert model([{"role": "user", "content": "x"}], max_output_tokens=8) == "ok"
    assert 0 < captured["timeout"] <= 5.0


def test_sdk_timeout_at_task_deadline_becomes_kernel_timeout() -> None:
    class FakeTimeoutError(Exception):
        pass
    class Transport:
        def create(self, **request):
            time.sleep(0.03)
            raise FakeTimeoutError("timed out")
    model = ChatCompletionsModelCallable(
        transport=Transport(),
        deployment="glm-test",
        native_persistent_tools=False,
        provider_timeout_s=1800,
    )
    with pytest.raises(KernelRunTimeout, match="deadline expired"):
        with run_deadline(time.monotonic() + 0.01):
            model([{"role": "user", "content": "x"}], max_output_tokens=8)


def test_shared_limiter_initial_admission_uses_deadline_exclusion_scope() -> None:
    from aether.provider_pacing import SharedDeploymentTokenPacer
    from aether.run_deadline import run_deadline_wait_exclusion_active

    class ProbeSharedPacer(SharedDeploymentTokenPacer):
        def __init__(self) -> None:
            self.token_limit = 300_000
            self.window_s = 60.0
            self.exclusion_states: list[bool] = []

        @staticmethod
        def approximate_request_tokens(request_bytes: int, max_output_tokens: int) -> int:
            return max(1, (int(request_bytes) + 3) // 4) + min(int(max_output_tokens), 4096)

        def admit(self, *, estimated_tokens: int):
            self.exclusion_states.append(run_deadline_wait_exclusion_active())
            return {
                "throughput_token_limit": self.token_limit,
                "throughput_window_s": self.window_s,
                "throughput_estimated_tokens": int(estimated_tokens),
                "throughput_wait_s": 0.25,
                "throughput_rolling_wait_s": 0.25,
                "throughput_single_request_admission": "provider_authoritative",
                "throughput_reservation_id": "probe-reservation",
            }

        def reconcile_observed_usage(
            self, *, reservation_id, input_tokens, output_tokens, requested_output_tokens,
        ):
            assert reservation_id == "probe-reservation"
            return {"throughput_usage_reconciled": True}

        def release_reservation(self, *, reservation_id: str) -> None:
            pass

        def mark_failed_reservation(self, *, reservation_id: str | None) -> None:
            pass

    pacer = ProbeSharedPacer()
    model = ChatCompletionsModelCallable(
        transport=FakeTransport(_tool_response()),
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=pacer,
    )
    with run_deadline(time.monotonic() + 10.0):
        model([{"role": "user", "content": "Read."}], max_output_tokens=32)

    assert pacer.exclusion_states == [True]
    row = model.drain_telemetry()[0]
    assert row["throughput_task_deadline_excluded_wait_s"] == pytest.approx(0.25)


def test_shared_admission_wait_is_excluded_from_scientific_deadline() -> None:
    from aether.provider_pacing import SharedDeploymentTokenPacer

    class SlowSharedPacer(SharedDeploymentTokenPacer):
        def __init__(self) -> None:
            self.token_limit = 1_000_000
            self.window_s = 60.0

        @staticmethod
        def approximate_request_tokens(request_bytes: int, max_output_tokens: int) -> int:
            return max(1, (int(request_bytes) + 3) // 4 + int(max_output_tokens))

        def admit(self, *, estimated_tokens: int):
            time.sleep(0.12)
            return {
                "throughput_token_limit": self.token_limit,
                "throughput_window_s": self.window_s,
                "throughput_estimated_tokens": int(estimated_tokens),
                "throughput_wait_s": 0.12,
                "throughput_rolling_wait_s": 0.12,
                "throughput_reservation_id": "slow-shared-reservation",
                "throughput_single_request_admission": "provider_authoritative",
            }

        def reconcile_observed_usage(
            self, *, reservation_id, input_tokens, output_tokens, requested_output_tokens,
        ):
            return {"throughput_usage_reconciled": True}

        def mark_failed_reservation(self, *, reservation_id):
            return None

        def release_reservation(self, *, reservation_id):
            return None

    transport = FakeTransport(_tool_response())
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=SlowSharedPacer(),
    )

    started = time.monotonic()
    with run_deadline(started + 0.05):
        model([{"role": "user", "content": "Read."}], max_output_tokens=32)
    elapsed = time.monotonic() - started

    assert elapsed >= 0.1
    assert len(transport.requests) == 1
    row = model.drain_telemetry()[0]
    assert row["throughput_task_deadline_excluded_wait_s"] == pytest.approx(0.12)


def test_chat_attempt_journal_persists_raw_reasoning_and_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    journal = tmp_path / "chat-attempts.jsonl"
    monkeypatch.setenv("AETHER_CHAT_TELEMETRY_JOURNAL", str(journal))
    model = ChatCompletionsModelCallable(
        transport=FakeTransport(_tool_response()),
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )

    model.call_with_telemetry_scope(
        [{"role": "user", "content": "read /tmp/input"}],
        max_output_tokens=100,
        run_id="run-journal",
        task_id="task-journal",
    )

    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["schema_version"] == "aether.chat_provider_attempt_journal.v1"
    event = row["attempt"]
    assert event["event_kind"] == "provider_attempt"
    assert event["status"] == "completed"
    assert event["run_id"] == "run-journal"
    assert event["task_id"] == "task-journal"
    assert event["input_tokens"] == 41
    assert event["cached_input_tokens"] == 4
    assert event["output_tokens"] == 12
    assert event["reasoning_tokens"] == 3
    assert (
        event["raw_provider_output"]["choices"][0]["message"]["reasoning_content"]
        == "private reasoning remains provider-local"
    )
    assert event["native_tool_name"] == "read_file"


def test_chat_attempt_journal_is_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    journal = tmp_path / "chat-attempts.jsonl"
    monkeypatch.delenv("AETHER_CHAT_TELEMETRY_JOURNAL", raising=False)
    model = ChatCompletionsModelCallable(
        transport=FakeTransport(_tool_response()),
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )
    model([{"role": "user", "content": "read /tmp/input"}], max_output_tokens=100)
    assert not journal.exists()


def test_chat_attempt_journal_is_strict_when_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    target = tmp_path / "directory-not-file"
    target.mkdir()
    monkeypatch.setenv("AETHER_CHAT_TELEMETRY_JOURNAL", str(target))
    model = ChatCompletionsModelCallable(
        transport=FakeTransport(_tool_response()),
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )
    with pytest.raises(ChatModelError, match="chat telemetry journal write failed"):
        model([{"role": "user", "content": "read /tmp/input"}], max_output_tokens=100)
    telemetry = model.drain_telemetry()
    assert len(telemetry) == 1
    assert telemetry[0]["status"] == "completed"

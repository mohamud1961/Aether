from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.model_hooks import ModelHooks
from aether.providers.chat_model import (
    ChatCompletionsModelCallable,
    ChatContextCapacityError,
    ChatModelError,
)
from aether.runtime_ir import ACTION_SCHEMA


class _FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class _CapacityPacer:
    def __init__(self, token_limit: int):
        self.token_limit = token_limit
        self.window_s = 60.0

    @staticmethod
    def approximate_request_tokens(request_bytes: int, max_output_tokens: int) -> int:
        return (int(request_bytes) + 3) // 4 + int(max_output_tokens)

    def admit(self, *, estimated_tokens: int):
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


def _tool_response() -> dict:
    return {
        "choices": [{
            "index": 0,
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call-capacity-1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": json.dumps({"arguments": {"path": "/tmp/input"}}),
                    },
                }],
            },
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
    }


def test_oversize_after_current_context_reanchor_is_local_capacity_failure() -> None:
    transport = _FakeTransport(_tool_response())
    pacer = _CapacityPacer(token_limit=1_000_000)
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
    hooks.solve([
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": "small current context"},
    ], compiled)

    # Set the declared ceiling to the known-good first request. The next request
    # is too large both before and after the provider's fresh-context re-anchor.
    pacer.token_limit = int(model.last_call_telemetry["throughput_estimated_tokens"])
    oversized_messages = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": "oversized current context " + "x" * 40_000},
    ]
    with pytest.raises(
        ChatContextCapacityError,
        match=r"^harness_context_capacity:.*fresh current-context re-anchor$",
    ):
        model.call_with_telemetry_scope(
            oversized_messages,
            max_output_tokens=400,
            run_id="run-capacity",
            task_id="task-capacity",
        )

    # Only the initial known-good request reached FakeTransport. The rejected
    # request was classified and recorded locally after the re-anchor attempt.
    assert len(transport.requests) == 1
    rows = model.drain_telemetry()
    rejected = rows[-1]
    assert rejected["throughput_capacity_reanchor"] is True
    assert rejected["throughput_post_reanchor_estimated_tokens"] > pacer.token_limit
    assert rejected["throughput_single_request_admission"] == "rejected_local_capacity"
    assert rejected["error_type"] == "ChatContextCapacityError"
    assert rejected["status"] == "failed"


def test_oversized_first_request_is_rejected_without_reanchor_claim_or_dispatch() -> None:
    transport = _FakeTransport(_tool_response())
    pacer = _CapacityPacer(token_limit=1)
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=pacer,  # type: ignore[arg-type]
    )

    with pytest.raises(ChatContextCapacityError) as caught:
        model(
            [{"role": "user", "content": "oversized first request with no earlier call"}],
            max_output_tokens=32,
        )

    assert str(caught.value).startswith("harness_context_capacity:")
    assert "after fresh current-context re-anchor" not in str(caught.value)
    assert transport.requests == []
    rejected = model.drain_telemetry()[0]
    assert rejected.get("throughput_capacity_reanchor") is not True
    assert rejected["throughput_single_request_admission"] == "rejected_local_capacity"
    assert rejected["error_type"] == "ChatContextCapacityError"


def test_provider_transport_failure_is_not_context_capacity_failure() -> None:
    transport = _FakeTransport(RuntimeError("provider rejected request"))
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )

    with pytest.raises(ChatModelError, match="provider rejected request") as caught:
        model([{"role": "user", "content": "Read the input."}], max_output_tokens=32)

    assert not isinstance(caught.value, ChatContextCapacityError)
    assert len(transport.requests) == 1
    row = model.drain_telemetry()[0]
    assert row["error_type"] == "RuntimeError"
    assert row["error"] == "provider rejected request"

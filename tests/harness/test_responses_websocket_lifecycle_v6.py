from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.providers.responses_websocket import (
    ResponsesWebSocketError,
    ResponsesWebSocketTransport,
)


class _FakeWS:
    def __init__(self, events):
        self.events = list(events)
        self.sent = []
        self.closed = False

    def settimeout(self, _value):
        pass

    def send(self, payload):
        self.sent.append(payload)

    def recv(self):
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event

    def close(self):
        self.closed = True


def test_lifecycle_observer_marks_actual_send_first_event_and_terminal_event():
    ws = _FakeWS([
        json.dumps({"type":"response.created","response":{"id":"resp-1","status":"in_progress"}}),
        json.dumps({"type":"response.completed","response":{"id":"resp-1","status":"completed","model":" vendor/Model-A ","output":[]}}),
    ])
    seen=[]
    transport=ResponsesWebSocketTransport(
        endpoint="https://unit.example", api_key="secret",
        connection_factory=lambda *args, **kwargs: ws,
    )
    response=transport.call(
        {"model":"unit","background":False},
        lifecycle_observer=lambda stage, detail: seen.append((stage,dict(detail))),
    )
    assert response.id == "resp-1"
    assert response.status == "completed"
    assert [stage for stage,_ in seen] == [
        "request_dispatched", "first_provider_event", "provider_terminal_event",
    ]
    assert seen[1][1] == {"event_type":"response.created"}
    assert seen[2][1] == {"event_type":"response.completed"}
    assert len(ws.sent) == 1
    assert ws.closed is True
    assert transport.last_call_observability()["provider_websocket_connection_reused"] is False
    assert transport.last_call_observability()["returned_model"] == " vendor/Model-A "
    assert transport.last_call_observability()["returned_model_known"] is True


def test_terminal_first_event_still_marks_first_and_terminal_boundaries():
    ws = _FakeWS([
        json.dumps({"type":"response.completed","response":{"id":"resp-2","status":"completed","output":[]}}),
    ])
    seen=[]
    transport=ResponsesWebSocketTransport(
        endpoint="https://unit.example", api_key="secret",
        connection_factory=lambda *args, **kwargs: ws,
    )
    transport.call({"model":"unit"}, lifecycle_observer=lambda stage, detail: seen.append((stage,dict(detail))))
    assert [stage for stage,_ in seen] == [
        "request_dispatched", "first_provider_event", "provider_terminal_event",
    ]
    assert seen[1][1]["event_type"] == "response.completed"


def test_failed_reconnect_clears_previous_call_observability():
    ws = _FakeWS([
        json.dumps({
            "type": "response.completed",
            "response": {
                "id": "resp-before-connect-failure",
                "status": "completed",
                "model": "previous-model",
                "output": [],
            },
        }),
    ])
    factory_calls = 0

    def factory(*args, **kwargs):
        nonlocal factory_calls
        factory_calls += 1
        if factory_calls == 1:
            return ws
        raise OSError("connect refused")

    transport = ResponsesWebSocketTransport(
        endpoint="https://unit.example",
        api_key="secret",
        connection_factory=factory,
    )

    transport.call({"model": "unit"})
    prior_obs = transport.last_call_observability()
    assert prior_obs["returned_model"] == "previous-model"
    assert prior_obs["provider_websocket_response_id"] == "resp-before-connect-failure"

    with pytest.raises(ResponsesWebSocketError, match="connect failed"):
        transport.call({"model": "unit"})

    assert transport.last_call_observability() == {}


def test_persistent_treatment_reuses_one_socket_across_completed_turns():
    ws = _FakeWS([
        json.dumps({"type":"response.completed","response":{"id":"resp-1","status":"completed","output":[]}}),
        json.dumps({"type":"response.completed","response":{"id":"resp-2","status":"completed","output":[]}}),
    ])
    factory_calls=[]

    def factory(*args, **kwargs):
        factory_calls.append((args, kwargs))
        return ws

    transport=ResponsesWebSocketTransport(
        endpoint="https://unit.example", api_key="secret",
        connection_factory=factory,
        persist_completed_connection=True,
    )

    first=transport.call({"model":"unit"})
    first_obs=transport.last_call_observability()
    second=transport.call({"model":"unit", "previous_response_id":"resp-1"})
    second_obs=transport.last_call_observability()

    assert first.id == "resp-1"
    assert second.id == "resp-2"
    assert len(factory_calls) == 1
    assert len(ws.sent) == 2
    assert ws.closed is False
    assert first_obs["provider_websocket_connection_reused"] is False
    assert first_obs["provider_websocket_connection_persisted_after_completed"] is True
    assert second_obs["provider_websocket_connection_reused"] is True
    assert second_obs["provider_websocket_connection_persisted_after_completed"] is True

    transport.close()
    assert ws.closed is True


def test_bearer_token_provider_authenticates_persistent_connection_with_native_continuity():
    ws = _FakeWS([
        json.dumps({
            "type": "response.completed",
            "response": {"id": "resp-mi-1", "status": "completed", "output": []},
        }),
        json.dumps({
            "type": "response.completed",
            "response": {"id": "resp-mi-2", "status": "completed", "output": []},
        }),
    ])
    connection_calls = []
    token_calls = []

    def token_provider():
        token_calls.append(len(token_calls) + 1)
        return f"system-mi-token-{len(token_calls)}"

    def factory(*args, **kwargs):
        connection_calls.append((args, dict(kwargs)))
        return ws

    transport = ResponsesWebSocketTransport(
        endpoint="https://unit.example",
        bearer_token_provider=token_provider,
        connection_factory=factory,
        request_timeout_s=5.0,
        persist_completed_connection=True,
    )

    first = transport.call({"model": "GPT-6-Luna"})
    second = transport.call({"model": "GPT-6-Luna", "previous_response_id": first.id})

    assert first.id == "resp-mi-1"
    assert second.id == "resp-mi-2"
    assert token_calls == [1]
    assert [call[1]["header"] for call in connection_calls] == [
        ["Authorization: Bearer system-mi-token-1"],
    ]
    assert json.loads(ws.sent[1])["previous_response_id"] == "resp-mi-1"
    assert len(connection_calls) == 1
    assert ws.closed is False
    assert transport._request_timeout_s == 5.0
    transport.close()
    assert ws.closed is True


def test_expired_deadline_skips_deadline_bearer_auth_and_socket_factory():
    clock_values = iter((0.0, 0.30))

    def monotonic_clock():
        return next(clock_values, 0.30)

    token_calls = []
    factory_calls = []

    def token_provider(remaining_s):
        token_calls.append(remaining_s)
        return "token"

    transport = ResponsesWebSocketTransport(
        endpoint="https://unit.example",
        deadline_bearer_token_provider=token_provider,
        connection_factory=lambda *args, **kwargs: factory_calls.append((args, kwargs)),
        request_timeout_s=1.0,
        monotonic_clock=monotonic_clock,
    )

    with pytest.raises(ResponsesWebSocketError) as excinfo:
        transport.call({"model": "unit"}, timeout_s=0.25)

    assert excinfo.value.replay_safety_reason == "request_deadline_exceeded_before_dispatch"
    assert token_calls == []
    assert factory_calls == []


def test_persistent_treatment_closes_socket_on_inflight_cancellation_without_replay():
    ws = _FakeWS([
        json.dumps({"type":"response.created","response":{"id":"resp-1","status":"in_progress"}}),
    ])
    checks = 0

    def cancellation_check():
        nonlocal checks
        checks += 1
        if checks >= 3:
            raise RuntimeError("cancelled")

    transport=ResponsesWebSocketTransport(
        endpoint="https://unit.example", api_key="secret",
        connection_factory=lambda *args, **kwargs: ws,
        persist_completed_connection=True,
    )

    with pytest.raises(RuntimeError, match="cancelled"):
        transport.call({"model":"unit"}, cancellation_check=cancellation_check)

    assert len(ws.sent) == 1
    assert ws.closed is True


def test_persistent_treatment_closes_dead_socket_after_send_failure():
    class _SendFailureWS(_FakeWS):
        def send(self, payload):
            self.sent.append(payload)
            raise RuntimeError("send failed")

    ws = _SendFailureWS([])
    transport=ResponsesWebSocketTransport(
        endpoint="https://unit.example", api_key="secret",
        connection_factory=lambda *args, **kwargs: ws,
        persist_completed_connection=True,
    )

    with pytest.raises(ResponsesWebSocketError, match="send failed") as excinfo:
        transport.call({"model":"unit"})

    assert len(ws.sent) == 1
    assert ws.closed is True
    assert excinfo.value.replay_safety_reason == "ambiguous_transport_failure_after_dispatch"
    assert excinfo.value.provider_acceptance_unknown_after_dispatch is True
    assert excinfo.value.acceptance_known is False
    assert excinfo.value.retry_safe is False
    import aether.providers.azure_model as azure_model
    assert azure_model.is_retryable_azure_error(excinfo.value) is False
    assert transport.last_call_observability()["provider_websocket_replay_safety_reason"] == (
        "ambiguous_transport_failure_after_dispatch"
    )


def test_receive_settimeout_failure_is_ambiguous_and_not_retryable():
    class _ReceiveTimeoutSetupFailureWS(_FakeWS):
        def __init__(self):
            super().__init__([])
            self.settimeout_calls = 0

        def settimeout(self, _value):
            self.settimeout_calls += 1
            if self.settimeout_calls == 3:
                raise RuntimeError("receive timeout setup failed")

    ws = _ReceiveTimeoutSetupFailureWS()
    transport = ResponsesWebSocketTransport(
        endpoint="https://unit.example",
        api_key="secret",
        connection_factory=lambda *args, **kwargs: ws,
    )

    with pytest.raises(ResponsesWebSocketError, match="receive timeout setup failed") as excinfo:
        transport.call({"model": "unit"})

    exc = excinfo.value
    assert len(ws.sent) == 1
    assert ws.closed is True
    assert exc.replay_safety_reason == "ambiguous_transport_failure_after_dispatch"
    assert exc.provider_acceptance_unknown_after_dispatch is True
    assert exc.acceptance_known is False
    assert exc.retry_safe is False
    import aether.providers.azure_model as azure_model
    assert azure_model.is_retryable_azure_error(exc) is False
    assert transport.last_call_observability()["provider_websocket_replay_safety_reason"] == (
        "ambiguous_transport_failure_after_dispatch"
    )


def test_observability_records_first_native_tool_and_output_item_types():
    ws = _FakeWS([
        json.dumps({"type":"response.created","response":{"id":"resp-obs","status":"in_progress"}}),
        json.dumps({"type":"response.output_item.added","item":{"type":"reasoning","id":"rs-1"}}),
        json.dumps({"type":"response.output_item.added","item":{"type":"function_call","id":"fc-1","call_id":"call-1","name":"act"}}),
        json.dumps({"type":"response.function_call_arguments.delta","delta":"{}"}),
        json.dumps({"type":"response.function_call_arguments.done","arguments":"{}"}),
        json.dumps({"type":"response.completed","response":{"id":"resp-obs","status":"completed","output":[]}}),
    ])
    transport=ResponsesWebSocketTransport(
        endpoint="https://unit.example", api_key="secret",
        connection_factory=lambda *args, **kwargs: ws,
    )

    transport.call({"model":"unit"})
    obs=transport.last_call_observability()

    assert obs["provider_websocket_native_tool_call_observed"] is True
    assert obs["provider_websocket_first_partial_output_elapsed_s"] is not None
    assert obs["provider_websocket_first_native_tool_call_elapsed_s"] is not None
    assert obs["provider_websocket_first_native_tool_call_elapsed_s"] >= obs["provider_websocket_first_partial_output_elapsed_s"]
    assert obs["provider_websocket_output_item_added_type_counts"] == {
        "function_call": 1,
        "reasoning": 1,
    }


def test_observability_keeps_no_native_tool_explicit_on_incomplete_reasoning_stream():
    ws = _FakeWS([
        json.dumps({"type":"response.created","response":{"id":"resp-no-tool","status":"in_progress"}}),
        json.dumps({"type":"response.output_item.added","item":{"type":"reasoning","id":"rs-1"}}),
        json.dumps({"type":"response.output_item.done","item":{"type":"reasoning","id":"rs-1"}}),
        json.dumps({"type":"response.output_item.added","item":{"type":"reasoning","id":"rs-2"}}),
        json.dumps({"type":"response.output_item.done","item":{"type":"reasoning","id":"rs-2"}}),
        json.dumps({"type":"response.incomplete","response":{"id":"resp-no-tool","status":"incomplete","output":[{"type":"reasoning","id":"rs-1"},{"type":"reasoning","id":"rs-2"}],"incomplete_details":{"reason":"max_output_tokens"}}}),
    ])
    transport=ResponsesWebSocketTransport(
        endpoint="https://unit.example", api_key="secret",
        connection_factory=lambda *args, **kwargs: ws,
    )

    with pytest.raises(ResponsesWebSocketError) as excinfo:
        transport.call({"model":"unit"})

    assert excinfo.value.incomplete_reason == "max_output_tokens"
    assert excinfo.value.native_tool_call_observed is False
    obs=transport.last_call_observability()
    assert obs["provider_websocket_native_tool_call_observed"] is False
    assert obs["provider_websocket_first_partial_output_elapsed_s"] is not None
    assert obs["provider_websocket_first_native_tool_call_elapsed_s"] is None
    assert obs["provider_websocket_output_item_added_type_counts"] == {"reasoning": 2}


def test_inflight_guard_can_stop_accepted_partial_no_tool_stream_without_replay():
    ws = _FakeWS([
        json.dumps({"type":"response.created","response":{"id":"resp-guard","status":"in_progress"}}),
        json.dumps({"type":"response.output_item.added","item":{"type":"reasoning","id":"rs-1"}}),
        json.dumps({"type":"response.output_item.done","item":{"type":"reasoning","id":"rs-1"}}),
        json.dumps({"type":"response.completed","response":{"id":"resp-guard","status":"completed","output":[]}}),
    ])
    seen=[]

    def guard(facts):
        seen.append(dict(facts))
        if (
            facts["request_accepted"]
            and facts["partial_output_observed"]
            and not facts["native_tool_call_observed"]
        ):
            raise RuntimeError("protected reserve")

    transport=ResponsesWebSocketTransport(
        endpoint="https://unit.example", api_key="secret",
        connection_factory=lambda *args, **kwargs: ws,
        persist_completed_connection=True,
    )

    with pytest.raises(RuntimeError, match="protected reserve"):
        transport.call({"model":"unit"}, inflight_guard=guard)

    assert len(ws.sent) == 1
    assert ws.closed is True
    assert any(row["partial_output_observed"] is True for row in seen)
    obs=transport.last_call_observability()
    assert obs["provider_websocket_request_accepted"] is True
    assert obs["provider_websocket_partial_output_observed"] is True
    assert obs["provider_websocket_native_tool_call_observed"] is False


def test_request_deadline_closes_after_repeated_receive_timeout_slices_without_replay():
    clock = [0.0]

    class _RepeatedTimeoutWS(_FakeWS):
        def __init__(self):
            super().__init__([])
            self.timeout = None
            self.receive_calls = 0

        def settimeout(self, value):
            self.timeout = value

        def recv(self):
            self.receive_calls += 1
            assert self.timeout is not None
            # Model a real socket timeout with a small scheduling overrun.
            clock[0] += self.timeout + 0.001
            raise TimeoutError("receive slice expired")

    ws = _RepeatedTimeoutWS()
    factory_calls = []

    def factory(*args, **kwargs):
        factory_calls.append((args, kwargs))
        return ws

    transport = ResponsesWebSocketTransport(
        endpoint="https://unit.example",
        api_key="secret",
        request_timeout_s=0.2,
        receive_slice_s=0.05,
        connection_factory=factory,
        monotonic_clock=lambda: clock[0],
    )

    with pytest.raises(ResponsesWebSocketError) as excinfo:
        transport.call({"model": "unit"})

    exc = excinfo.value
    assert exc.replay_safety_reason == "request_deadline_exceeded_after_dispatch"
    assert exc.provider_acceptance_unknown_after_dispatch is True
    assert exc.request_accepted is False
    assert exc.acceptance_known is False
    assert exc.retry_safe is False
    import aether.providers.azure_model as azure_model
    assert azure_model.is_retryable_azure_error(exc) is False
    assert len(factory_calls) == 1
    assert factory_calls[0][1]["timeout"] <= 0.2
    assert len(ws.sent) == 1
    assert ws.receive_calls == 4
    assert ws.closed is True
    obs = transport.last_call_observability()
    assert obs["provider_websocket_request_dispatched"] is True
    assert obs["provider_websocket_acceptance_unknown_after_dispatch"] is True
    assert obs["provider_websocket_receive_timeout_slice_count"] == 4
    assert obs["provider_websocket_request_timeout_s"] == 0.2
    assert obs["provider_websocket_replay_safety_reason"] == (
        "request_deadline_exceeded_after_dispatch"
    )
    assert obs["returned_model"] is None
    assert obs["returned_model_known"] is False


def test_factory_threads_resolved_poll_timeout_to_websocket_transport(monkeypatch):
    import aether.providers.azure_model as azure_model

    client_calls = []

    class _Client:
        pass

    def openai_client(**kwargs):
        client_calls.append(dict(kwargs))
        return _Client()

    monkeypatch.setattr(
        azure_model, "openai", SimpleNamespace(OpenAI=openai_client)
    )
    monkeypatch.setenv("UNIT_WS_ENDPOINT", "https://unit.example")
    monkeypatch.setenv("UNIT_WS_DEPLOYMENT", "unit-deployment")
    monkeypatch.setenv("UNIT_WS_KEY", "not-a-real-key")

    model = azure_model.make_azure_callable(
        deployment_env="UNIT_WS_DEPLOYMENT",
        key_env="UNIT_WS_KEY",
        endpoint_env="UNIT_WS_ENDPOINT",
        role="solver",
        poll_timeout_s=17.25,
        responses_background=False,
        responses_websocket=True,
        max_retries=0,
        sdk_max_retries=0,
    )
    try:
        assert len(client_calls) == 1
        assert model._websocket_transport._request_timeout_s == 17.25
        assert model._poll_timeout_s == 30.0
    finally:
        model.close_run_transport()

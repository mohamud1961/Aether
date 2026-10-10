"""Offline provider-error recovery evals at the real Azure adapter boundary.

The WebSocket is fake, but the production ``AzureModelCallable`` and
``ResponsesWebSocketTransport`` are exercised end to end.  The cases preserve
the distinction between an observed acceptance, an unknown acceptance state
after dispatch, and an ambiguous stream that already exposed provider output
or a native-tool candidate.
"""
from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest

import aether.providers.azure_model as azure_model
from aether.providers.azure_model import AzureModelCallable, AzureModelError
from aether.providers.responses_websocket import ResponsesWebSocketTransport
from aether.run_cancellation import RunCancellationRequested
from aether.run_deadline import KernelRunTimeout


class _FakeWS:
    def __init__(self, events: list[object], *, before_next_event=None) -> None:
        self.events = list(events)
        self.before_next_event = before_next_event
        self.sent: list[str] = []
        self.closed = False

    def settimeout(self, _value: float) -> None:
        return None

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def recv(self) -> str:
        if self.before_next_event is not None:
            self.before_next_event(self)
        if not self.events:
            raise RuntimeError("fake websocket exhausted")
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return str(event)

    def close(self) -> None:
        self.closed = True


def _event(kind: str, **payload: object) -> str:
    return json.dumps({"type": kind, **payload}, separators=(",", ":"))


def _completed_event(
    response_id: str = "resp-completed", *, path: str = "/app/output",
) -> str:
    item = {
        "id": "fc-1",
        "type": "function_call",
        "status": "completed",
        "call_id": "call-1",
        "name": "read_file",
        "arguments": json.dumps({"arguments": {"path": path}}, separators=(",", ":")),
    }
    return _event(
        "response.completed",
        response={"id": response_id, "status": "completed", "output": [item]},
    )


def _partial_server_error_events() -> list[str]:
    return [
        _event("response.created", response={"id": "resp-partial", "status": "in_progress"}),
        _event("response.in_progress", response={"id": "resp-partial", "status": "in_progress"}),
        _event(
            "response.output_item.added",
            response_id="resp-partial",
            item={"type": "function_call", "call_id": "call-partial"},
        ),
        _event(
            "response.function_call_arguments.delta",
            response_id="resp-partial",
            item_id="call-partial",
            delta='{"arguments":',
        ),
        _event("error", error={"code": "server_error", "message": "retry please"}),
    ]


def _model(
    sockets: list[_FakeWS], *, max_retries: int = 1,
) -> tuple[AzureModelCallable, ResponsesWebSocketTransport, list[dict[str, object]]]:
    factory_calls: list[dict[str, object]] = []

    def factory(*args: object, **kwargs: object) -> _FakeWS:
        factory_calls.append({"args_count": len(args), "header_present": bool(kwargs.get("header"))})
        index = len(factory_calls) - 1
        if index >= len(sockets):
            raise AssertionError("unexpected provider retry")
        return sockets[index]

    transport = ResponsesWebSocketTransport(
        endpoint="https://unit.example",
        api_key="secret",
        connection_factory=factory,
        receive_slice_s=0.01,
    )
    model = AzureModelCallable(
        client=SimpleNamespace(responses=SimpleNamespace()),
        websocket_transport=transport,
        deployment="unit-test-frontier",
        effort="low",
        role="solver",
        responses_background=False,
        responses_websocket=True,
        prompt_cache_mode="off",
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=max_retries,
        sleep=lambda _seconds: None,
        rand=lambda: 0.0,
    )
    return model, transport, factory_calls


def _invoke(model: AzureModelCallable, run_id: str) -> str:
    return model.call_with_telemetry_scope(
        [{"role": "user", "content": "inspect one current state"}],
        max_output_tokens=12000,
        run_id=run_id,
        task_id=f"{run_id}-task",
    )


def test_partial_server_error_is_not_replayed_after_provider_output_and_keeps_continuity() -> None:
    run_id = "partial-server-error"
    seed = _FakeWS([_completed_event("resp-seed", path="/app/seed")])
    partial = _FakeWS(_partial_server_error_events())
    model, transport, factory_calls = _model([seed, partial], max_retries=1)
    try:
        assert json.loads(_invoke(model, run_id))["action"]["arguments"]["path"] == "/app/seed"
        model.commit_pending_response(run_id=run_id, task_id=f"{run_id}-task")
        scope = (run_id, f"{run_id}-task")
        committed_before = model._persistent_continuity_state(scope)

        with pytest.raises(AzureModelError, match="retry please"):
            _invoke(model, run_id)

        rows = model.drain_telemetry()
        failed = rows[-1]
        assert len(rows) == 2
        assert len(factory_calls) == 2
        assert len(partial.sent) == 1
        assert failed["provider_terminal_event_type"] == "error"
        assert failed["provider_terminal_error_code"] == "server_error"
        assert failed["provider_terminal_retry_safe"] is False
        assert failed["provider_websocket_request_accepted"] is True
        assert failed["provider_websocket_acceptance_observed"] is True
        assert failed["provider_websocket_acceptance_known"] is True
        assert failed["provider_websocket_acceptance_unknown_after_dispatch"] is False
        assert failed["provider_websocket_partial_output_observed"] is True
        assert failed["provider_websocket_native_tool_call_observed"] is True
        assert failed["provider_websocket_native_tool_execution_observed"] is None
        assert failed["provider_terminal_response_id"] == "resp-partial"
        assert failed["provider_websocket_response_id"] == "resp-partial"
        assert failed["provider_websocket_replay_safety_reason"] == (
            "server_error_after_response_acceptance_or_partial_output"
        )
        assert failed["persistent_continuity_previous_state_present"] is True
        assert failed["persistent_continuity_request_previous_response_id"] == "resp-seed"
        assert model._persistent_continuity_state(scope) == committed_before
        assert model._persistent_pending_continuity_state(scope) is None
    finally:
        transport.close()


def test_first_event_server_error_is_ambiguous_and_never_replayed() -> None:
    first = _FakeWS([
        _event("error", error={"code": "server_error", "message": "retry please"}),
    ])
    model, transport, factory_calls = _model([first], max_retries=1)
    try:
        with pytest.raises(AzureModelError, match="retry please"):
            _invoke(model, "first-event-server-error")
        failed = model.drain_telemetry()[0]
        assert len(factory_calls) == 1
        assert len(first.sent) == 1
        assert first.closed is True
        assert failed["provider_terminal_retry_safe"] is False
        assert failed["provider_websocket_request_accepted"] is False
        assert failed["provider_websocket_acceptance_observed"] is False
        assert failed["provider_websocket_acceptance_known"] is False
        assert failed["provider_websocket_acceptance_unknown_after_dispatch"] is True
        assert failed["provider_websocket_partial_output_observed"] is False
        assert failed["provider_websocket_native_tool_call_observed"] is False
        assert failed["provider_websocket_native_tool_execution_observed"] is None
        assert failed["provider_terminal_response_id"] is None
        assert failed["provider_websocket_response_id"] is None
        assert failed["provider_websocket_replay_safety_reason"] == (
            "server_error_replay_safety_unknown_after_dispatch"
        )
        assert failed["error"] == (
            'Responses WebSocket terminal failure: '
            '{"error": {"code": "server_error", "message": "retry please"}, "type": "error"}'
        )
        assert failed["usage_status"] == "unmeasured"
        assert failed["total_tokens"] is None
        assert len(model._persistent_continuity_pending_states) == 0
    finally:
        transport.close()


def test_unknown_event_before_server_error_remains_acceptance_unknown_and_never_replayed() -> None:
    socket = _FakeWS([
        _event("unknown.event", detail="unrecognized provider event"),
        _event("error", error={"code": "server_error", "message": "retry please"}),
    ])
    model, transport, factory_calls = _model([socket], max_retries=1)
    try:
        with pytest.raises(AzureModelError, match="retry please"):
            _invoke(model, "unknown-before-server-error")
        row = model.drain_telemetry()[0]
        assert len(factory_calls) == 1
        assert len(socket.sent) == 1
        assert row["provider_websocket_event_count"] == 2
        assert row["provider_websocket_event_type_counts"] == {
            "error": 1,
            "unknown.event": 1,
        }
        assert row["provider_websocket_request_accepted"] is False
        assert row["provider_websocket_acceptance_observed"] is False
        assert row["provider_websocket_acceptance_known"] is False
        assert row["provider_websocket_acceptance_unknown_after_dispatch"] is True
        assert row["provider_terminal_retry_safe"] is False
        assert row["provider_websocket_replay_safety_reason"] == (
            "server_error_replay_safety_unknown_after_dispatch"
        )
    finally:
        transport.close()


def test_output_cap_incomplete_is_retained_and_never_replayed() -> None:
    socket = _FakeWS([
        _event("response.created", response={"id": "resp-incomplete", "status": "in_progress"}),
        _event(
            "response.incomplete",
            response={
                "id": "resp-incomplete",
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [],
            },
        ),
    ])
    model, transport, factory_calls = _model([socket], max_retries=1)
    try:
        with pytest.raises(AzureModelError, match="max_output_tokens"):
            _invoke(model, "output-cap-incomplete")
        row = model.drain_telemetry()[0]
        assert len(factory_calls) == 1
        assert len(socket.sent) == 1
        assert row["provider_terminal_event_type"] == "response.incomplete"
        assert row["provider_terminal_response_id"] == "resp-incomplete"
        assert row["provider_websocket_response_id"] == "resp-incomplete"
        assert row["provider_terminal_retry_safe"] is False
        assert row["provider_websocket_request_accepted"] is True
        assert row["provider_websocket_acceptance_observed"] is True
        assert row["provider_websocket_acceptance_known"] is True
        assert row["provider_websocket_acceptance_unknown_after_dispatch"] is False
        assert row["provider_websocket_partial_output_observed"] is False
        assert row["provider_websocket_native_tool_call_observed"] is False
        assert row["provider_websocket_incomplete_reason"] == "max_output_tokens"
        assert row["provider_websocket_replay_safety_reason"] == (
            "provider_incomplete_response_not_replay_safe"
        )
        assert "max_output_tokens" in row["error"]
    finally:
        transport.close()


def test_ambiguous_disconnect_after_dispatch_is_not_replayed() -> None:
    socket = _FakeWS([
        _event("response.created", response={"id": "resp-disconnect", "status": "in_progress"}),
        RuntimeError("connection reset after dispatch"),
    ])
    model, transport, factory_calls = _model([socket], max_retries=1)
    try:
        with pytest.raises(AzureModelError, match="connection reset after dispatch"):
            _invoke(model, "ambiguous-disconnect")
        row = model.drain_telemetry()[0]
        assert len(factory_calls) == 1
        assert len(socket.sent) == 1
        assert row["provider_websocket_request_accepted"] is True
        assert row["provider_websocket_acceptance_observed"] is True
        assert row["provider_websocket_acceptance_known"] is True
        assert row["provider_websocket_acceptance_unknown_after_dispatch"] is False
        assert row["provider_websocket_partial_output_observed"] is False
        assert row["provider_terminal_retry_safe"] is False
        assert row["provider_websocket_replay_safety_reason"] == (
            "ambiguous_transport_failure_after_dispatch"
        )
    finally:
        transport.close()


def test_malformed_event_is_not_replayed_and_is_classified_exactly() -> None:
    socket = _FakeWS([
        _event("response.created", response={"id": "resp-malformed", "status": "in_progress"}),
        "not-json",
    ])
    model, transport, factory_calls = _model([socket], max_retries=1)
    try:
        with pytest.raises(AzureModelError, match="emitted invalid JSON"):
            _invoke(model, "malformed-event")
        row = model.drain_telemetry()[0]
        assert len(factory_calls) == 1
        assert len(socket.sent) == 1
        assert row["provider_websocket_request_accepted"] is True
        assert row["provider_websocket_acceptance_observed"] is True
        assert row["provider_websocket_acceptance_known"] is True
        assert row["provider_websocket_acceptance_unknown_after_dispatch"] is False
        assert row["provider_terminal_retry_safe"] is False
        assert row["provider_websocket_replay_safety_reason"] == "malformed_provider_event"
    finally:
        transport.close()


def test_completed_native_action_is_one_provider_send_and_execution_is_not_inferred() -> None:
    socket = _FakeWS([_completed_event()])
    model, transport, factory_calls = _model([socket], max_retries=1)
    try:
        result = json.loads(_invoke(model, "completed-native-action"))
        row = model.drain_telemetry()[0]
        assert result["kind"] == "act"
        assert result["action"]["kind"] == "read_file"
        assert len(factory_calls) == 1
        assert len(socket.sent) == 1
        assert row["provider_websocket_request_accepted"] is True
        assert row["provider_websocket_acceptance_observed"] is True
        assert row["provider_websocket_acceptance_known"] is True
        assert row["provider_websocket_acceptance_unknown_after_dispatch"] is False
        assert row["provider_websocket_partial_output_observed"] is True
        assert row["provider_websocket_native_tool_call_observed"] is True
        assert row["provider_websocket_native_tool_execution_observed"] is None
        assert row["native_tool_name"] == "read_file"
    finally:
        transport.close()


def test_cancellation_after_dispatch_is_not_replayed() -> None:
    cancellation = threading.Event()

    def cancel_before_next_event(_socket: _FakeWS) -> None:
        cancellation.set()

    socket = _FakeWS([
        _event("response.created", response={"id": "resp-cancel", "status": "in_progress"}),
    ], before_next_event=cancel_before_next_event)
    model, transport, factory_calls = _model([socket], max_retries=1)
    model.bind_run_cancellation(cancellation)
    try:
        with pytest.raises(RunCancellationRequested, match="cancellation requested"):
            _invoke(model, "cancelled-run")
        row = model.drain_telemetry()[0]
        assert len(factory_calls) == 1
        assert len(socket.sent) == 1
        assert row["provider_websocket_request_accepted"] is True
        assert row.get("provider_terminal_retry_safe", False) is False
        assert row["status"] == "failed"
    finally:
        transport.close()


def test_deadline_after_dispatch_is_not_replayed(monkeypatch: pytest.MonkeyPatch) -> None:
    checks = {"count": 0}

    def deadline_check() -> None:
        checks["count"] += 1
        if checks["count"] >= 4:
            raise KernelRunTimeout("task run deadline exceeded")

    monkeypatch.setattr(azure_model, "raise_if_run_deadline_exceeded", deadline_check)
    socket = _FakeWS([_event("response.created", response={"id": "resp-deadline", "status": "in_progress"})])
    model, transport, factory_calls = _model([socket], max_retries=1)
    try:
        with pytest.raises(KernelRunTimeout, match="deadline exceeded"):
            _invoke(model, "deadline-run")
        row = model.drain_telemetry()[0]
        assert checks["count"] >= 4
        assert len(factory_calls) == 1
        assert len(socket.sent) == 1
        assert row["status"] == "failed"
    finally:
        transport.close()

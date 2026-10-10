from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether.provider_budget import ProviderBudgetError
from aether.providers.azure_model import AzureModelCallable, AzureModelError


class _RejectingBudget:
    def reserve(self, role, request, *, input_token_upper_bound=None):
        raise ProviderBudgetError(f"blocked before transport for {role}")


class _StaleWebSocket:
    def __init__(self) -> None:
        self.calls = 0

    def call(self, request, *, cancellation_check=None, lifecycle_observer=None):
        self.calls += 1
        raise AssertionError("transport must not be entered after budget rejection")

    def close(self) -> None:
        pass

    def last_call_observability(self):
        # Simulate observability retained from a prior completed request.  A new
        # pre-dispatch failure must not attach any of these fields to its event.
        return {
            "provider_websocket_acceptance_observed": True,
            "provider_websocket_request_accepted": True,
            "provider_websocket_partial_output_observed": True,
            "provider_websocket_response_id": "resp-stale",
            "provider_websocket_event_count": 99,
        }


def _model(role: str) -> tuple[AzureModelCallable, _StaleWebSocket]:
    ws = _StaleWebSocket()
    client = SimpleNamespace(close=lambda: None)
    model = AzureModelCallable(
        client=client,
        websocket_transport=ws,
        deployment="unit-test-frontier",
        effort="low",
        role=role,
        responses_background=False,
        responses_websocket=True,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode="off",
        budget_guard=_RejectingBudget(),
    )
    return model, ws


def _assert_clean_budget_event(model: AzureModelCallable, ws: _StaleWebSocket) -> None:
    assert ws.calls == 0
    events = model.drain_telemetry()
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "failed"
    assert event["error_type"] == "ProviderBudgetError"
    assert event["attempt_phase"] == "create"
    assert "provider_websocket_acceptance_observed" not in event
    assert "provider_websocket_request_accepted" not in event
    assert "provider_websocket_partial_output_observed" not in event
    assert "provider_websocket_response_id" not in event
    assert "provider_websocket_event_count" not in event


def test_solver_budget_rejection_does_not_inherit_stale_websocket_observability() -> None:
    model, ws = _model("solver")
    with pytest.raises(AzureModelError, match="responses native-tool call failed") as exc:
        model.call_with_telemetry_scope(
            [{"role": "user", "content": "budget-blocked solver turn"}],
            max_output_tokens=2000,
            run_id="run-a",
            task_id="task-a",
        )
    assert isinstance(exc.value.__cause__, ProviderBudgetError)
    _assert_clean_budget_event(model, ws)


def test_verifier_budget_rejection_does_not_inherit_stale_websocket_observability() -> None:
    model, ws = _model("verifier")
    with pytest.raises(AzureModelError, match="Verifier native-tool call failed") as exc:
        model.call_with_telemetry_scope(
            [{"role": "user", "content": "budget-blocked verifier review"}],
            max_output_tokens=2000,
            run_id="run-a",
            task_id="task-a",
        )
    assert isinstance(exc.value.__cause__, ProviderBudgetError)
    _assert_clean_budget_event(model, ws)

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.providers.azure_model import AzureModelCallable, AzureModelError
from aether.verifier_activation_continuity import (
    FRESH_CONTROL,
    PREVIOUS_RESPONSE_V1,
    PREFIX,
    apply_delta,
)


def _verifier_response(n: int, *, verdict: str = "pass") -> SimpleNamespace:
    call = SimpleNamespace(
        id=f"fc-{n}", type="function_call", status="completed",
        call_id=f"vcall-{n}", name="verifier_turn",
        arguments=json.dumps({"turn": {"verdict": verdict}}),
    )
    return SimpleNamespace(
        id=f"vresp-{n}", status="completed", output=[call], usage=None,
        reasoning=None, error=None, incomplete_details=None,
    )


class _Responses:
    def __init__(self, rows: list[object]) -> None:
        self.rows = list(rows)
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        if not self.rows:
            raise AssertionError("no fake verifier response remains")
        return self.rows.pop(0)

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("foreground completed fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("foreground completed fake must not cancel")


class _Client:
    def __init__(self, rows: list[object]) -> None:
        self.responses = _Responses(rows)


def _model(rows: list[object]) -> tuple[AzureModelCallable, _Client]:
    client = _Client(rows)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-verifier", effort="low", role="verifier",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )
    return model, client


def _messages(turn: int) -> list[dict[str, str]]:
    payload = {
        "verifier_packet": {
            "authoritative_check_ids": [],
            "turn": turn,
        },
        "authoritative_task_prompt": "fixed task",
    }
    return [
        {"role": "system", "content": "fixed verifier identity"},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]


def _call(model: AzureModelCallable, turn: int) -> str:
    return model.call_with_telemetry_scope(
        _messages(turn), max_output_tokens=4000,
        run_id="run-a", task_id="task-a",
    )


def test_treatment_first_call_is_fresh_stored_and_staged_until_host_commit() -> None:
    model, client = _model([_verifier_response(1)])
    model.begin_verifier_activation(
        PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    raw = _call(model, 1)
    assert json.loads(raw)["verdict"] == "pass"
    request = client.responses.requests[0]
    assert request["store"] is True
    assert "previous_response_id" not in request
    assert not any(
        isinstance(item, dict) and item.get("type") == "function_call_output"
        for item in (request["input"] if isinstance(request["input"], list) else [])
    )
    event = model.drain_telemetry()[0]
    assert event["verifier_activation_continuity_mode"] == PREVIOUS_RESPONSE_V1
    assert event["verifier_activation_transport_kind"] == "full_snapshot"
    assert event["verifier_activation_candidate_staged"] is True

    with pytest.raises(AzureModelError, match="pending candidate requires admission"):
        _call(model, 2)

    assert model.commit_verifier_activation_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    ) is True


def test_second_treatment_call_uses_exact_previous_response_call_and_lossless_delta() -> None:
    model, client = _model([_verifier_response(1), _verifier_response(2)])
    model.begin_verifier_activation(
        PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    _call(model, 1)
    model.commit_verifier_activation_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    )
    _call(model, 2)

    first, second = client.responses.requests
    assert second["store"] is True
    assert second["previous_response_id"] == "vresp-1"
    assert isinstance(second["input"], list) and len(second["input"]) == 1
    output = second["input"][0]
    assert output["type"] == "function_call_output"
    assert output["call_id"] == "vcall-1"
    assert str(output["output"]).startswith(PREFIX)

    event = model.drain_telemetry()[-1]
    assert event["verifier_activation_transport_kind"] == "delta"
    assert event["verifier_activation_previous_response_id"] == "vresp-1"
    assert event["verifier_activation_previous_call_id"] == "vcall-1"
    # The state object independently reconstructs the exact current user input.
    binding = model._verifier_activation_binding({"run_id": "run-a", "task_id": "task-a"})
    assert binding is not None
    pending = model._verifier_activation_continuity_state.pending_identity(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    )
    assert pending is not None and pending["response_id"] == "vresp-2"
    prepared_state = model._verifier_activation_continuity_state._pending[("run-a", "task-a", "activation-1")]["prepared"]
    assert prepared_state.envelope is not None
    previous_snapshot = model._verifier_activation_continuity_state.committed_identity(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    )["snapshot"]
    assert apply_delta(previous_snapshot, prepared_state.envelope) == prepared_state.snapshot
    assert first.get("previous_response_id") is None


def test_reject_keeps_prior_committed_parent_for_next_attempt() -> None:
    model, client = _model([
        _verifier_response(1), _verifier_response(2), _verifier_response(3),
    ])
    model.begin_verifier_activation(
        PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    _call(model, 1)
    model.commit_verifier_activation_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    )
    _call(model, 2)
    assert model.reject_verifier_activation_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    ) is True
    _call(model, 3)
    assert client.responses.requests[1]["previous_response_id"] == "vresp-1"
    assert client.responses.requests[2]["previous_response_id"] == "vresp-1"


def test_end_activation_forces_new_activation_fresh_and_preserves_global_id_guard() -> None:
    model, client = _model([_verifier_response(1), _verifier_response(2)])
    model.begin_verifier_activation(
        PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    _call(model, 1)
    model.commit_verifier_activation_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    )
    model.end_verifier_activation(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    )
    model.begin_verifier_activation(
        PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-2",
    )
    _call(model, 2)
    second = client.responses.requests[1]
    assert "previous_response_id" not in second
    event = model.drain_telemetry()[-1]
    assert event["verifier_activation_id"] == "activation-2"
    assert event["verifier_activation_transport_kind"] == "full_snapshot"


def test_control_binding_remains_request_fresh_on_every_call() -> None:
    model, client = _model([_verifier_response(1), _verifier_response(2)])
    model.begin_verifier_activation(
        FRESH_CONTROL,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    _call(model, 1)
    model.commit_verifier_activation_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    )
    _call(model, 2)
    assert all("previous_response_id" not in request for request in client.responses.requests)
    assert all("store" not in request for request in client.responses.requests)
    events = model.drain_telemetry()
    assert [event["verifier_activation_transport_kind"] for event in events] == [
        "full_snapshot", "full_snapshot"
    ]

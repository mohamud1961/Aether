from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from aether.persistent_reality_delta import DELTA_MODE, FULL_MODE, reconstruct_snapshot, snapshot_sha256
from aether.providers.azure_model import (
    AzureModelCallable,
    AzureModelError,
    PERSISTENT_REALITY_TRANSPORT_CONTROL,
    PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1,
)


def _function_call(response_no: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"fc-{response_no}", type="function_call", status="completed",
        call_id=f"call-{response_no}", name="read_file",
        arguments=json.dumps({"arguments": {"path": "/app/input.txt"}}),
    )


def _response(response_no: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"resp-{response_no}", status="completed",
        output=[_function_call(response_no)], usage=None, reasoning=None,
        error=None, incomplete_details=None,
    )


class _BadRequest(Exception):
    def __init__(self, code: str) -> None:
        self.status_code = 400
        self.body = {
            "message": code, "type": "invalid_request_error",
            "param": "previous_response_id", "code": code,
        }
        super().__init__(code)


class _Responses:
    def __init__(self, rows: list[object]) -> None:
        self.rows = list(rows)
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(deepcopy(dict(kwargs)))
        if not self.rows:
            raise AssertionError("no fake response remains")
        row = self.rows.pop(0)
        if isinstance(row, BaseException):
            raise row
        return row

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not cancel")


class _Client:
    def __init__(self, rows: list[object]) -> None:
        self.responses = _Responses(rows)


def _model(rows: list[object]) -> tuple[AzureModelCallable, _Client]:
    client = _Client(rows)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-frontier", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )
    return model, client


def _packet(turn: int) -> dict:
    value = {
        "runtime_identity": {
            "task_id": "task-a", "run_id": "run-a", "workspace_id": "/app",
        },
        "latest_primary_result": {
            "status": "succeeded", "action_id": f"action-{turn}",
            "action_kind": "read_file",
        },
        "budgets": {
            "remaining_kernel_steps": 10 - turn,
            "used_solver_provider_turns": turn,
        },
        "stable_section": {"capabilities": ["read_file", "run_command"]},
    }
    if turn >= 3:
        value.pop("stable_section")
        value["new_section"] = {"turn": turn}
    return value


def _boundary(turn: int) -> str:
    return "[context_packet]\n" + json.dumps(
        _packet(turn), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )


def _set_mode(model: AzureModelCallable, mode: str) -> None:
    model.set_reality_transport_mode(mode, run_id="run-a", task_id="task-a")


def _call(model: AzureModelCallable, turn: int, *, commit: bool = True) -> str:
    raw = model.call_with_telemetry_scope(
        [{"role": "system", "content": "stable-prefix"},
         {"role": "system", "content": _boundary(turn)}],
        max_output_tokens=16000, run_id="run-a", task_id="task-a",
    )
    if commit:
        model.commit_pending_response(run_id="run-a", task_id="task-a")
    return raw


def _transport_content(request: dict[str, object]) -> str:
    value = request["input"]
    if isinstance(value, str):
        return value
    assert isinstance(value, list) and len(value) == 1
    item = value[0]
    assert isinstance(item, dict)
    if item.get("role") == "user":
        assert set(item) == {"role", "content"}
        return str(item["content"])
    assert item["type"] == "function_call_output"
    output = json.loads(str(item["output"]))
    assert output == [{"role": "user", "content": output[0]["content"]}]
    return str(output[0]["content"])


def _envelope(request: dict[str, object]) -> dict:
    content = _transport_content(request)
    prefix = "[context_delta]\n"
    assert content.startswith(prefix)
    value = json.loads(content[len(prefix):])
    assert isinstance(value, dict)
    return value


def test_explicit_control_mode_is_request_identical_to_default_control() -> None:
    default, client_default = _model([_response(1)])
    explicit, client_explicit = _model([_response(1)])
    _set_mode(explicit, PERSISTENT_REALITY_TRANSPORT_CONTROL)
    _call(default, 1)
    _call(explicit, 1)
    assert client_default.responses.requests == client_explicit.responses.requests
    assert client_default.responses.requests[0]["input"] == [
        {"role": "user", "content": _boundary(1)}
    ]


def test_delta_only_first_turn_full_then_healthy_parent_sends_lossless_delta() -> None:
    model, client = _model([_response(1), _response(2)])
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 1)
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 2)

    first, second = client.responses.requests
    assert first["input"] == [{"role": "user", "content": _boundary(1)}]
    delta = _envelope(second)
    assert second["previous_response_id"] == "resp-1"
    assert delta["mode"] == DELTA_MODE
    assert reconstruct_snapshot(_packet(1), delta) == _packet(2)
    assert delta["omitted_unchanged_top_level_keys"] == ["runtime_identity", "stable_section"]
    assert "stable_section" not in delta["set"]

    event = model.drain_telemetry()[-1]
    assert event["persistent_reality_transport_mode"] == DELTA_MODE
    assert event["persistent_reality_transport_base_snapshot_sha256"] == snapshot_sha256(_packet(1))
    assert event["persistent_reality_transport_result_snapshot_sha256"] == delta["result_snapshot_sha256"]


def test_rejected_delta_candidate_does_not_advance_snapshot_base() -> None:
    model, client = _model([_response(1), _response(2), _response(3)])
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 1)
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 2, commit=False)
    model.reject_pending_response(run_id="run-a", task_id="task-a")
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 3)

    second = _envelope(client.responses.requests[1])
    third = _envelope(client.responses.requests[2])
    assert second["mode"] == DELTA_MODE
    assert client.responses.requests[2]["previous_response_id"] == "resp-1"
    assert third["mode"] == DELTA_MODE
    assert reconstruct_snapshot(_packet(1), third) == _packet(3)
    assert "stable_section" in third["clear"]


def test_explicit_scope_clear_forces_full_reanchor_under_same_treatment() -> None:
    model, client = _model([_response(1), _response(2)])
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 1)
    model.clear_continuity_scope(run_id="run-a", task_id="task-a")
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 2)
    assert "previous_response_id" not in client.responses.requests[1]
    assert client.responses.requests[1]["input"] == [{"role": "user", "content": _boundary(2)}]
    event = model.drain_telemetry()[-1]
    assert event["persistent_reality_transport_mode"] == FULL_MODE


def test_explicit_scope_clear_drops_transport_selector_until_runtime_reconfigures() -> None:
    model, client = _model([_response(1), _response(2)])
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 1)
    model.clear_continuity_scope(run_id="run-a", task_id="task-a")

    raw = model.call_with_telemetry_scope(
        [{"role": "user", "content": "control-after-explicit-clear"}],
        max_output_tokens=16000, run_id="run-a", task_id="task-a",
    )
    assert raw
    model.commit_pending_response(run_id="run-a", task_id="task-a")
    assert client.responses.requests[1]["input"] == [
        {"role": "user", "content": "control-after-explicit-clear"}
    ]


def test_missing_provider_parent_retries_with_full_not_stale_delta() -> None:
    model, client = _model([
        _response(1), _BadRequest("previous_response_not_found"), _response(2),
    ])
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 1)
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 2)

    assert len(client.responses.requests) == 3
    failed = client.responses.requests[1]
    reanchor = client.responses.requests[2]
    assert failed["previous_response_id"] == "resp-1"
    assert _envelope(failed)["mode"] == DELTA_MODE
    assert "previous_response_id" not in reanchor
    assert reanchor["input"] == [{"role": "user", "content": _boundary(2)}]
    event = model.drain_telemetry()[-1]
    assert event["persistent_continuity_reanchor_succeeded"] is True
    assert event["persistent_reality_transport_mode"] == FULL_MODE


def test_delta_only_rejects_noncanonical_or_non_context_solver_boundary_before_dispatch() -> None:
    model, client = _model([_response(1), _response(2)])
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    with pytest.raises(AzureModelError, match="exact \\[context_packet\\] boundary"):
        model.call_with_telemetry_scope(
            [{"role": "user", "content": "not-a-context-packet"}],
            max_output_tokens=16000, run_id="run-a", task_id="task-a",
        )
    pretty = "[context_packet]\n" + json.dumps(_packet(1), sort_keys=True, indent=2)
    with pytest.raises(AzureModelError, match="not the canonical kernel serialization"):
        model.call_with_telemetry_scope(
            [{"role": "system", "content": pretty}],
            max_output_tokens=16000, run_id="run-a", task_id="task-a",
        )
    assert client.responses.requests == []


def test_transport_mode_is_task_scoped_and_unknown_mode_fails_closed() -> None:
    model, client = _model([_response(1), _response(2)])
    _set_mode(model, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1)
    _call(model, 1)
    raw = model.call_with_telemetry_scope(
        [{"role": "user", "content": "other-task-control"}],
        max_output_tokens=16000, run_id="run-b", task_id="task-b",
    )
    assert raw
    model.commit_pending_response(run_id="run-b", task_id="task-b")
    assert client.responses.requests[1]["input"] == [{"role": "user", "content": "other-task-control"}]
    with pytest.raises(AzureModelError, match="unsupported PERSISTENT reality transport mode"):
        model.set_reality_transport_mode("invented", run_id="run-a", task_id="task-a")

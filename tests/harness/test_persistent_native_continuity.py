from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from aether.providers.azure_model import (
    AzureModelCallable,
    AzureModelError,
    AzureProviderOutputError,
    _prepare_persistent_stateless_input_item,
)


def _turn(*, path: str = "/app/input.txt") -> str:
    return json.dumps({
        "turn": {
            "kind": "act",
            "action": {
                "kind": "read_file",
                "capability_id": "filesystem",
                "arguments": {"path": path},
            },
        }
    })


def _function_call(*, response_no: int, path: str = "/app/input.txt") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"fc-{response_no}",
        type="function_call",
        status="completed",
        call_id=f"call-{response_no}",
        name="persistent_turn",
        arguments=_turn(path=path),
    )


def _reasoning(response_no: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"rs-{response_no}",
        type="reasoning",
        status="completed",
        encrypted_content=f"opaque-{response_no}",
        summary=[],
    )


def _compaction(response_no: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"cmp-{response_no}",
        type="compaction",
        status="completed",
        encrypted_content=f"compact-opaque-{response_no}",
        created_by="server",
    )


def _response(
    response_no: int,
    *items: object,
    reasoning_context: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"resp-{response_no}",
        status="completed",
        output=list(items),
        usage=None,
        reasoning=(
            None
            if reasoning_context is None
            else SimpleNamespace(context=reasoning_context)
        ),
        error=None,
        incomplete_details=None,
    )


class _FakeResponses:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        if not self.responses:
            raise AssertionError("no fake response remains")
        return self.responses.pop(0)

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("foreground completed fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not cancel")


class _FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = _FakeResponses(responses)


def _model(
    responses: list[object],
    *,
    mode: str = "explicit",
    compact_threshold: int | None = None,
    reasoning_context: str | None = None,
    working_state_policy: str = "optional",
) -> tuple[AzureModelCallable, _FakeClient]:
    client = _FakeClient(responses)
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
        persistent_continuity_mode=mode,
        persistent_compact_threshold=compact_threshold,
        persistent_reasoning_context=reasoning_context,
        persistent_working_state_policy=working_state_policy,
    )
    return model, client


def _scoped_call(
    model: AzureModelCallable,
    content: str,
    *,
    run_id: str = "run-a",
    task_id: str = "task-a",
) -> str:
    raw = model.call_with_telemetry_scope(
        [{"role": "user", "content": content}],
        max_output_tokens=16000,
        run_id=run_id,
        task_id=task_id,
    )
    model.commit_pending_response(run_id=run_id, task_id=task_id)
    return raw


def test_explicit_mode_preserves_existing_request_shape() -> None:
    model, client = _model([_response(1, _function_call(response_no=1))])
    _scoped_call(model, "context-one")
    request = client.responses.requests[0]
    for field in ("store", "include", "previous_response_id", "context_management"):
        assert field not in request
    event = model.drain_telemetry()[0]
    assert event["persistent_continuity_mode"] == "explicit"
    assert event["persistent_continuity_state_advanced"] is False


def test_previous_response_continuity_returns_new_aether_boundary_as_tool_output() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2, path="/app/second.txt")),
    ], mode="previous_response")

    _scoped_call(model, "context-one")
    _scoped_call(model, "context-two")

    first, second = client.responses.requests
    assert first["store"] is True
    assert "previous_response_id" not in first
    assert second["store"] is True
    assert second["previous_response_id"] == "resp-1"
    assert second["input"] == [{
        "type": "function_call_output",
        "call_id": "call-1",
        "output": json.dumps(
            [{"role": "user", "content": "context-two"}],
            sort_keys=True,
            separators=(",", ":"),
        ),
    }]


def test_capability_contract_sends_context_and_disables_working_state() -> None:
    model, client = _model(
        [_response(
            1,
            _function_call(response_no=1),
            reasoning_context="current_turn",
        )],
        mode="previous_response",
        reasoning_context="current_turn",
        working_state_policy="disabled",
    )

    _scoped_call(model, "capability-probe")

    request = client.responses.requests[0]
    assert request["reasoning"] == {"effort": "low", "context": "current_turn"}
    assert "working_state" not in json.dumps(request["tools"], sort_keys=True)
    event = model.drain_telemetry()[0]
    assert event["persistent_reasoning_context_requested"] == "current_turn"
    assert event["persistent_reasoning_context_effective"] == "current_turn"
    assert event["persistent_reasoning_context_status"] == "matched"
    assert event["persistent_working_state_policy"] == "disabled"
    assert event["persistent_working_state_mode"] == "disabled"
    assert event["persistent_primary_provider_schema_sha256"]


def test_previous_response_telemetry_proves_exact_current_boundary_and_prior_call_pairing() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ], mode="previous_response")
    _scoped_call(model, "context-one")
    _scoped_call(model, "context-two")
    events = model.drain_telemetry()
    assert events[0]["persistent_continuity_request_previous_response_id"] is None
    assert events[0]["persistent_continuity_current_boundary_direct_input_match"] is True
    assert events[0]["persistent_continuity_request_function_call_output_count"] == 0
    assert events[1]["persistent_continuity_request_previous_response_id"] == "resp-1"
    assert events[1]["persistent_continuity_request_input_item_types"] == ["function_call_output"]
    assert events[1]["persistent_continuity_request_function_call_output_count"] == 1
    assert events[1]["persistent_continuity_current_boundary_function_output_match_count"] == 1
    assert events[1]["persistent_continuity_expected_prior_call_id"] == "call-1"
    assert events[1]["persistent_continuity_prior_call_id_match_count"] == 1
    assert events[1]["persistent_continuity_request_function_call_output_call_ids"] == ["call-1"]
    expected_boundary = json.dumps(
        [{"role": "user", "content": "context-two"}],
        sort_keys=True, separators=(",", ":"),
    )
    assert events[1]["persistent_continuity_current_boundary_sha256"] == hashlib.sha256(
        expected_boundary.encode("utf-8")
    ).hexdigest()
    assert events[1]["persistent_continuity_request_function_call_output_sha256"] == [
        events[1]["persistent_continuity_current_boundary_sha256"]
    ]
    assert client.responses.requests[1]["previous_response_id"] == "resp-1"


def test_previous_response_state_isolated_by_run_and_task_scope() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ], mode="previous_response")

    _scoped_call(model, "task-a-first", run_id="run-a", task_id="task-a")
    _scoped_call(model, "task-b-first", run_id="run-b", task_id="task-b")

    assert "previous_response_id" not in client.responses.requests[0]
    assert "previous_response_id" not in client.responses.requests[1]


def test_native_continuity_requires_modelhooks_scope() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
    ], mode="previous_response")
    with pytest.raises(AzureModelError, match="requires_run_and_task_scope"):
        model([{"role": "user", "content": "unscoped"}])
    assert client.responses.requests == []


def test_rejected_provider_turn_does_not_advance_native_state() -> None:
    bad = _response(
        1,
        _function_call(response_no=1),
        _function_call(response_no=99),
    )
    good = _response(2, _function_call(response_no=2))
    model, client = _model([bad, good], mode="previous_response")

    with pytest.raises(AzureProviderOutputError):
        _scoped_call(model, "first-boundary")
    _scoped_call(model, "retry-boundary")

    assert "previous_response_id" not in client.responses.requests[0]
    assert "previous_response_id" not in client.responses.requests[1]
    events = model.drain_telemetry()
    assert events[0]["status"] == "failed"
    assert events[1]["persistent_continuity_previous_state_present"] is False
    assert events[1]["persistent_continuity_state_advanced"] is False
    assert events[1]["persistent_continuity_candidate_staged"] is True


def test_stateless_encrypted_mode_carries_provider_items_and_host_observation() -> None:
    model, client = _model([
        _response(1, _reasoning(1), _function_call(response_no=1)),
        _response(2, _reasoning(2), _function_call(response_no=2)),
    ], mode="stateless_encrypted")

    _scoped_call(model, "context-one")
    _scoped_call(model, "context-two")

    first, second = client.responses.requests
    assert first["store"] is False
    assert first["include"] == ["reasoning.encrypted_content"]
    assert "previous_response_id" not in first
    assert second["store"] is False
    assert second["include"] == ["reasoning.encrypted_content"]
    assert "previous_response_id" not in second
    items = second["input"]
    assert isinstance(items, list)
    assert items[0] == {"role": "user", "content": "context-one"}
    assert any(item.get("type") == "reasoning" and item.get("encrypted_content") == "opaque-1" for item in items)
    assert any(item.get("type") == "function_call" and item.get("call_id") == "call-1" for item in items)
    assert items[-1]["type"] == "function_call_output"
    assert items[-1]["call_id"] == "call-1"
    assert "context-two" in items[-1]["output"]


def test_stateless_compaction_prunes_history_at_latest_compaction_item() -> None:
    model, client = _model([
        _response(1, _reasoning(1), _function_call(response_no=1)),
        _response(2, _compaction(2), _function_call(response_no=2)),
        _response(3, _reasoning(3), _function_call(response_no=3)),
    ], mode="stateless_compaction", compact_threshold=200000)

    _scoped_call(model, "context-one")
    _scoped_call(model, "context-two")
    _scoped_call(model, "context-three")

    for request in client.responses.requests:
        assert request["store"] is False
        assert request["include"] == ["reasoning.encrypted_content"]
        assert request["context_management"] == [{
            "type": "compaction",
            "compact_threshold": 200000,
        }]
        assert "previous_response_id" not in request

    third_items = client.responses.requests[2]["input"]
    assert isinstance(third_items, list)
    assert all(
        "status" not in item
        for item in third_items
        if isinstance(item, dict)
    )
    assert third_items[0]["type"] == "compaction"
    assert third_items[0]["encrypted_content"] == "compact-opaque-2"
    assert not any(item.get("role") == "user" and item.get("content") == "context-one" for item in third_items)
    assert third_items[-1]["type"] == "function_call_output"
    assert third_items[-1]["call_id"] == "call-2"
    assert "context-three" in third_items[-1]["output"]
    events = model.drain_telemetry()
    assert events[1]["persistent_continuity_compaction_observed"] is True


def test_stateless_history_rejects_unknown_provider_output_item_type() -> None:
    with pytest.raises(
        AzureProviderOutputError,
        match="provider_stateless_history_item_type_unsupported",
    ):
        _prepare_persistent_stateless_input_item(SimpleNamespace(
            id="unknown-1",
            type="unsupported_output_item",
            status="completed",
        ))


def test_continuity_modes_are_restricted_to_persistent_native_solver_route() -> None:
    client = _FakeClient([])
    # responses_tools is valid for a PERSISTENT Verifier, but native cognitive
    # continuation belongs only to the persistent PERSISTENT Solver.
    with pytest.raises(ValueError, match="requires the PERSISTENT V0 Solver responses_tools route"):
        AzureModelCallable(
            client=client,  # type: ignore[arg-type]
            deployment="unit-test-frontier",
            effort="low",
            role="verifier",
            solver_protocol="solver_v1",
            verifier_protocol="persistent_v0",
            transport="responses_tools",
            responses_background=False,
            poll_interval_s=1.0,
            poll_timeout_s=30.0,
            max_retries=0,
            persistent_continuity_mode="previous_response",
        )


def test_compaction_threshold_requires_compaction_mode() -> None:
    with pytest.raises(ValueError, match="accepted only with a compaction continuity mode"):
        _model([], mode="explicit", compact_threshold=1234)
    with pytest.raises(ValueError, match="positive persistent_compact_threshold"):
        _model([], mode="stateless_compaction", compact_threshold=0)



def test_release_scope_discards_native_chain_before_same_scope_is_reused() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
        _response(3, _function_call(response_no=3)),
    ], mode="previous_response")

    _scoped_call(model, "one")
    _scoped_call(model, "two")
    assert client.responses.requests[1]["previous_response_id"] == "resp-1"

    model.clear_continuity_scope(run_id="run-a", task_id="task-a")
    _scoped_call(model, "fresh-after-release")
    assert "previous_response_id" not in client.responses.requests[2]


def test_native_continuity_preflight_is_explicitly_unqualified() -> None:
    model, _client = _model([], mode="stateless_compaction", compact_threshold=200000)
    row = model.preflight_request(max_output_tokens=16000, logical_role="solver")
    assert row["persistent_continuity_mode"] == "stateless_compaction"
    assert row["persistent_compact_threshold"] == 200000
    assert row["persistent_continuity_qualification"] == "experimental_unqualified"
    assert row["certification"] == "experimental_persistent_native_continuity_unqualified"


def test_explicit_preflight_keeps_existing_native_tool_certification() -> None:
    model, _client = _model([])
    row = model.preflight_request(max_output_tokens=16000, logical_role="solver")
    assert row["persistent_continuity_mode"] == "explicit"
    assert row["persistent_continuity_qualification"] == "baseline_explicit"
    assert row["certification"] == "responses_single_persistent_v0_native_tool_call_contract"



def test_continuity_telemetry_measures_exact_transformed_request_input() -> None:
    model, client = _model([
        _response(1, _reasoning(1), _function_call(response_no=1)),
        _response(2, _reasoning(2), _function_call(response_no=2)),
    ], mode="stateless_encrypted")
    _scoped_call(model, "short-one")
    _scoped_call(model, "short-two")
    events = model.drain_telemetry()
    first_wire = json.dumps(client.responses.requests[0]["input"], sort_keys=True, separators=(",", ":"))
    second_wire = json.dumps(client.responses.requests[1]["input"], sort_keys=True, separators=(",", ":"))
    assert events[0]["input_chars"] == len(first_wire)
    assert events[1]["input_chars"] == len(second_wire)
    assert events[1]["input_chars"] > events[0]["input_chars"]
    assert events[1]["persistent_continuity_request_input_item_count"] == len(client.responses.requests[1]["input"])
    assert events[0]["provider_output_item_type_counts"] == {"function_call": 1, "reasoning": 1}
    assert events[0]["provider_reasoning_item_count"] == 1


def test_compaction_item_is_censused_even_though_it_is_not_an_executable_turn() -> None:
    model, _client = _model([
        _response(1, _compaction(1), _function_call(response_no=1)),
    ], mode="stateless_compaction", compact_threshold=200000)
    _scoped_call(model, "context")
    event = model.drain_telemetry()[0]
    assert event["provider_output_item_type_counts"] == {"compaction": 1, "function_call": 1}
    assert event["provider_compaction_item_count"] == 1
    assert event["provider_function_call_item_count"] == 1
    assert event["persistent_continuity_compaction_observed"] is True



def test_compaction_observed_is_current_response_event_not_retained_history() -> None:
    model, _client = _model([
        _response(1, _compaction(1), _function_call(response_no=1)),
        _response(2, _reasoning(2), _function_call(response_no=2)),
    ], mode="stateless_compaction", compact_threshold=200000)

    _scoped_call(model, "first")
    _scoped_call(model, "second")
    events = model.drain_telemetry()
    assert events[0]["persistent_continuity_compaction_observed"] is True
    assert events[0]["persistent_continuity_history_pruned_to_compaction"] is True
    assert events[1]["persistent_continuity_compaction_observed"] is False
    assert events[1]["persistent_continuity_history_pruned_to_compaction"] is False


def test_compaction_after_function_call_keeps_call_item_for_host_output_pairing() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1), _compaction(1)),
        _response(2, _function_call(response_no=2)),
    ], mode="stateless_compaction", compact_threshold=200000)

    _scoped_call(model, "first-boundary")
    _scoped_call(model, "second-boundary")
    second_input = client.responses.requests[1]["input"]
    assert isinstance(second_input, list)
    assert [item.get("type") for item in second_input] == [
        "function_call", "compaction", "function_call_output"
    ]
    assert second_input[0]["call_id"] == "call-1"
    assert second_input[-1]["call_id"] == "call-1"
    assert "second-boundary" in second_input[-1]["output"]


def test_compaction_before_function_call_keeps_provider_output_order() -> None:
    model, client = _model([
        _response(1, _compaction(1), _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ], mode="stateless_compaction", compact_threshold=200000)

    _scoped_call(model, "first-boundary")
    _scoped_call(model, "second-boundary")
    second_input = client.responses.requests[1]["input"]
    assert isinstance(second_input, list)
    assert [item.get("type") for item in second_input] == [
        "compaction", "function_call", "function_call_output"
    ]
    assert second_input[1]["call_id"] == "call-1"
    assert second_input[-1]["call_id"] == "call-1"



def test_rejected_turn_after_compaction_does_not_poison_compacted_chain() -> None:
    bad = _response(
        2,
        _function_call(response_no=2),
        _function_call(response_no=99),
    )
    model, client = _model([
        _response(1, _compaction(1), _function_call(response_no=1)),
        bad,
        _response(3, _function_call(response_no=3)),
    ], mode="stateless_compaction", compact_threshold=200000)

    _scoped_call(model, "first")
    with pytest.raises(AzureProviderOutputError):
        _scoped_call(model, "second-attempt-bad")
    _scoped_call(model, "second-attempt-good")

    bad_request = client.responses.requests[1]
    retry_request = client.responses.requests[2]
    # Both attempts must continue from the same accepted compacted call-1
    # frontier. The rejected response's call-2/call-99 items never enter state.
    for request in (bad_request, retry_request):
        items = request["input"]
        assert isinstance(items, list)
        assert any(item.get("type") == "compaction" for item in items)
        assert any(item.get("type") == "function_call" and item.get("call_id") == "call-1" for item in items)
        assert items[-1]["type"] == "function_call_output"
        assert items[-1]["call_id"] == "call-1"
    assert not any(
        item.get("call_id") in {"call-2", "call-99"}
        for item in retry_request["input"]
        if isinstance(item, dict)
    )



def test_previous_response_compaction_renders_bounded_chain_and_context_management() -> None:
    model, client = _model([
        _response(1, _compaction(1), _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ], mode="previous_response_compaction", compact_threshold=200000)

    _scoped_call(model, "first-boundary")
    _scoped_call(model, "second-boundary")
    first, second = client.responses.requests
    for request in (first, second):
        assert request["store"] is False
        assert request["context_management"] == [{
            "type": "compaction", "compact_threshold": 200000,
        }]
        assert "include" not in request
    assert "previous_response_id" not in first
    assert second["previous_response_id"] == "resp-1"
    assert second["input"][-1]["type"] == "function_call_output"
    assert second["input"][-1]["call_id"] == "call-1"
    assert "second-boundary" in second["input"][-1]["output"]
    events = model.drain_telemetry()
    assert events[0]["persistent_continuity_compaction_observed"] is True
    assert events[0]["persistent_continuity_history_item_count"] == 0
    assert events[1]["persistent_continuity_compaction_observed"] is False


def test_previous_response_compaction_telemetry_proves_store_false_chain_and_exact_host_boundary() -> None:
    model, _client = _model([
        _response(1, _compaction(1), _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ], mode="previous_response_compaction", compact_threshold=200000)
    _scoped_call(model, "first-boundary")
    _scoped_call(model, "second-boundary")
    first, second = model.drain_telemetry()
    assert first["persistent_continuity_store"] is False
    assert first["persistent_continuity_request_previous_response_id"] is None
    assert first["persistent_continuity_current_boundary_direct_input_match"] is True
    assert second["persistent_continuity_store"] is False
    assert second["persistent_continuity_request_previous_response_id"] == first["persistent_continuity_response_id"]
    assert second["persistent_continuity_context_management"] == [{
        "type": "compaction", "compact_threshold": 200000,
    }]
    assert second["persistent_continuity_request_function_call_output_count"] == 1
    assert second["persistent_continuity_current_boundary_function_output_match_count"] == 1
    assert second["persistent_continuity_expected_prior_call_id"] == first["persistent_continuity_call_id"]
    assert second["persistent_continuity_prior_call_id_match_count"] == 1


def test_previous_response_compaction_requires_positive_threshold() -> None:
    with pytest.raises(ValueError, match="previous_response_compaction requires a positive"):
        _model([], mode="previous_response_compaction", compact_threshold=0)


def test_previous_response_compaction_preflight_remains_unqualified() -> None:
    model, _client = _model([], mode="previous_response_compaction", compact_threshold=200000)
    row = model.preflight_request(max_output_tokens=16000, logical_role="solver")
    assert row["persistent_continuity_mode"] == "previous_response_compaction"
    assert row["persistent_compact_threshold"] == 200000
    assert row["persistent_continuity_qualification"] == "experimental_unqualified"
    assert row["certification"] == "experimental_persistent_native_continuity_unqualified"



def test_raw_capture_hashes_opaque_reasoning_and_compaction_without_persisting_ciphertext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reasoning_cipher = "opaque-secret-reasoning"
    compaction_cipher = "opaque-secret-compaction"
    response = _response(
        1,
        SimpleNamespace(
            id="rs-custom", type="reasoning",
            encrypted_content=reasoning_cipher, summary=[],
        ),
        SimpleNamespace(
            id="cmp-custom", type="compaction",
            encrypted_content=compaction_cipher, created_by="server",
        ),
        _function_call(response_no=1),
    )
    model, _client = _model(
        [response], mode="stateless_compaction", compact_threshold=200000,
    )
    monkeypatch.setenv("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT", "1")
    _scoped_call(model, "capture-boundary")
    items = model.drain_telemetry()[0]["raw_provider_output_items"]
    by_type = {item["type"]: item for item in items}
    reasoning = by_type["reasoning"]
    compaction = by_type["compaction"]
    assert "encrypted_content" not in reasoning
    assert "encrypted_content" not in compaction
    assert reasoning["encrypted_content_bytes"] == len(reasoning_cipher.encode("utf-8"))
    assert reasoning["encrypted_content_sha256"] == hashlib.sha256(
        reasoning_cipher.encode("utf-8")
    ).hexdigest()
    assert compaction["encrypted_content_bytes"] == len(compaction_cipher.encode("utf-8"))
    assert compaction["encrypted_content_sha256"] == hashlib.sha256(
        compaction_cipher.encode("utf-8")
    ).hexdigest()
    function = by_type["function_call"]
    assert function["arguments_bytes"] > 0
    assert function["arguments_sha256"] == hashlib.sha256(
        function["arguments"].encode("utf-8")
    ).hexdigest()



def test_pending_candidate_blocks_next_dispatch_until_local_admission() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ], mode="previous_response")
    model.call_with_telemetry_scope(
        [{"role": "user", "content": "first"}],
        max_output_tokens=16000, run_id="run-a", task_id="task-a",
    )
    with pytest.raises(AzureModelError, match="pending_candidate_requires_admission"):
        model.call_with_telemetry_scope(
            [{"role": "user", "content": "must-not-dispatch"}],
            max_output_tokens=16000, run_id="run-a", task_id="task-a",
        )
    assert len(client.responses.requests) == 1
    model.reject_pending_response(run_id="run-a", task_id="task-a")
    _scoped_call(model, "fresh-after-reject")
    assert "previous_response_id" not in client.responses.requests[1]


def test_rejected_pending_candidate_preserves_prior_committed_parent() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
        _response(3, _function_call(response_no=3)),
    ], mode="previous_response")
    _scoped_call(model, "first")
    model.call_with_telemetry_scope(
        [{"role": "user", "content": "candidate-to-reject"}],
        max_output_tokens=16000, run_id="run-a", task_id="task-a",
    )
    assert client.responses.requests[1]["previous_response_id"] == "resp-1"
    model.reject_pending_response(run_id="run-a", task_id="task-a")
    _scoped_call(model, "correction")
    assert client.responses.requests[2]["previous_response_id"] == "resp-1"
    admissions = model.drain_continuity_admission_telemetry()
    assert [row["persistent_continuity_parent_disposition"] for row in admissions] == [
        "committed", "rejected", "committed",
    ]


def test_stateless_rejected_candidate_preserves_committed_history() -> None:
    model, client = _model([
        _response(1, _reasoning(1), _function_call(response_no=1)),
        _response(2, _reasoning(2), _function_call(response_no=2)),
        _response(3, _reasoning(3), _function_call(response_no=3)),
    ], mode="stateless_encrypted")
    _scoped_call(model, "first")
    model.call_with_telemetry_scope(
        [{"role": "user", "content": "candidate-to-reject"}],
        max_output_tokens=16000, run_id="run-a", task_id="task-a",
    )
    model.reject_pending_response(run_id="run-a", task_id="task-a")
    _scoped_call(model, "correction")
    third = client.responses.requests[2]["input"]
    assert isinstance(third, list)
    assert any(item.get("call_id") == "call-1" for item in third if isinstance(item, dict))
    assert not any(item.get("call_id") == "call-2" for item in third if isinstance(item, dict))


def test_scope_release_clears_pending_as_well_as_committed_parent() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ], mode="previous_response")
    model.call_with_telemetry_scope(
        [{"role": "user", "content": "staged-only"}],
        max_output_tokens=16000, run_id="run-a", task_id="task-a",
    )
    model.clear_continuity_scope(run_id="run-a", task_id="task-a")
    _scoped_call(model, "fresh")
    assert "previous_response_id" not in client.responses.requests[1]


def test_store_true_response_inventory_survives_provider_output_rejection() -> None:
    bad = _response(1, _function_call(response_no=1), _function_call(response_no=99))
    model, _client = _model([bad], mode="previous_response")
    with pytest.raises(AzureProviderOutputError):
        model.call_with_telemetry_scope(
            [{"role": "user", "content": "bad-provider-output"}],
            max_output_tokens=16000, run_id="run-a", task_id="task-a",
        )
    event = model.drain_telemetry()[0]
    assert event["persistent_remote_response_inventory_observed"] is True
    assert event["persistent_remote_response_inventory_response_id"] == "resp-1"
    assert event["status"] == "failed"


def test_modelhooks_commits_only_after_local_runtime_validation() -> None:
    from aether.model_hooks import ModelHooks, ModelOutputError

    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
        _response(3, _function_call(response_no=3)),
    ], mode="previous_response")
    hooks = ModelHooks(lambda *_args, **_kwargs: "{}", model, run_id="run-a", task_id="task-a")
    allowed = SimpleNamespace(
        solver_turn_protocol="persistent_v0",
        action_schema=(("read_file", ("path",)),),
    )
    blocked = SimpleNamespace(
        solver_turn_protocol="persistent_v0",
        action_schema=(("write_file", ("path", "content")),),
    )
    messages = [{"role": "user", "content": "current"}]
    hooks.solve(messages, allowed)
    with pytest.raises(ModelOutputError, match="unknown action kind"):
        hooks.solve(messages, blocked)
    assert client.responses.requests[1]["previous_response_id"] == "resp-1"
    hooks.solve(messages, allowed)
    assert client.responses.requests[2]["previous_response_id"] == "resp-1"
    rows = hooks.drain_model_telemetry()
    admissions = [row for row in rows if row.get("event_kind") == "persistent_continuity_parent_admission"]
    assert [row["persistent_continuity_parent_disposition"] for row in admissions] == [
        "committed", "rejected", "committed",
    ]

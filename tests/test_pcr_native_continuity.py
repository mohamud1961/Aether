from __future__ import annotations


import hashlib


import json


from types import SimpleNamespace


import pytest


from aether.providers import azure_model
from aether.providers.azure_model import (
    AzureModelCallable,
    AzureModelError,
    AzureProviderOutputError,
)


def _turn(*, path: str = "/app/input.txt") -> str:
    return json.dumps({
        "turn": {
            "kind": "act",
            "action": {
                "kind": "read_file",
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
        name="read_file",
        arguments=json.dumps({"arguments": {"path": path}}),
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
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("foreground completed fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not cancel")


class _FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = _FakeResponses(responses)


def _model(responses: list[object]) -> tuple[AzureModelCallable, _FakeClient]:
    client = _FakeClient(responses)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-luna",
        effort="low",
        role="solver",
        responses_background=False,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode="off",
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


def test_previous_response_continuity_returns_new_aether_boundary_as_tool_output() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2, path="/app/second.txt")),
    ])

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


def test_native_contract_sends_context_and_has_no_working_state() -> None:
    model, client = _model(
        [_response(
            1,
            _function_call(response_no=1),
            reasoning_context="all_turns",
        )],
    )

    _scoped_call(model, "capability-probe")

    request = client.responses.requests[0]
    assert request["reasoning"] == {"effort": "low", "context": "all_turns"}
    assert "working_state" not in json.dumps(request["tools"], sort_keys=True)
    event = model.drain_telemetry()[0]
    assert event["pcr_reasoning_context_requested"] == "all_turns"
    assert event["pcr_reasoning_context_effective"] == "all_turns"
    assert event["pcr_reasoning_context_status"] == "matched"
    assert event["pcr_primary_provider_schema_sha256"]


def test_previous_response_telemetry_proves_exact_current_boundary_and_prior_call_pairing() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ])
    _scoped_call(model, "context-one")
    _scoped_call(model, "context-two")
    events = model.drain_telemetry()
    assert events[0]["pcr_continuity_request_previous_response_id"] is None
    assert events[0]["pcr_continuity_current_boundary_direct_input_match"] is True
    assert events[0]["pcr_continuity_request_function_call_output_count"] == 0
    assert events[1]["pcr_continuity_request_previous_response_id"] == "resp-1"
    assert events[1]["pcr_continuity_request_input_item_types"] == ["function_call_output"]
    assert events[1]["pcr_continuity_request_function_call_output_count"] == 1
    assert events[1]["pcr_continuity_current_boundary_function_output_match_count"] == 1
    assert events[1]["pcr_continuity_expected_prior_call_id"] == "call-1"
    assert events[1]["pcr_continuity_prior_call_id_match_count"] == 1
    assert events[1]["pcr_continuity_request_function_call_output_call_ids"] == ["call-1"]
    expected_boundary = json.dumps(
        [{"role": "user", "content": "context-two"}],
        sort_keys=True, separators=(",", ":"),
    )
    assert events[1]["pcr_continuity_current_boundary_sha256"] == hashlib.sha256(
        expected_boundary.encode("utf-8")
    ).hexdigest()
    assert events[1]["pcr_continuity_request_function_call_output_sha256"] == [
        events[1]["pcr_continuity_current_boundary_sha256"]
    ]
    assert client.responses.requests[1]["previous_response_id"] == "resp-1"


def test_previous_response_state_isolated_by_run_and_task_scope() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ])

    _scoped_call(model, "task-a-first", run_id="run-a", task_id="task-a")
    _scoped_call(model, "task-b-first", run_id="run-b", task_id="task-b")

    assert "previous_response_id" not in client.responses.requests[0]
    assert "previous_response_id" not in client.responses.requests[1]


def test_native_continuity_requires_modelhooks_scope() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
    ])
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
    model, client = _model([bad, good])

    with pytest.raises(AzureProviderOutputError):
        _scoped_call(model, "first-boundary")
    _scoped_call(model, "retry-boundary")

    assert "previous_response_id" not in client.responses.requests[0]
    assert "previous_response_id" not in client.responses.requests[1]
    events = model.drain_telemetry()
    assert events[0]["status"] == "failed"
    assert events[1]["pcr_continuity_previous_state_present"] is False
    assert events[1]["pcr_continuity_state_advanced"] is False
    assert events[1]["pcr_continuity_candidate_staged"] is True


def test_release_scope_discards_native_chain_before_same_scope_is_reused() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
        _response(3, _function_call(response_no=3)),
    ])

    _scoped_call(model, "one")
    _scoped_call(model, "two")
    assert client.responses.requests[1]["previous_response_id"] == "resp-1"

    model.clear_continuity_scope(run_id="run-a", task_id="task-a")
    _scoped_call(model, "fresh-after-release")
    assert "previous_response_id" not in client.responses.requests[2]


def test_pending_candidate_blocks_next_dispatch_until_local_admission() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ])
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
    ])
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
    assert [row["pcr_continuity_parent_disposition"] for row in admissions] == [
        "committed", "rejected", "committed",
    ]


def test_scope_release_clears_pending_as_well_as_committed_parent() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
    ])
    model.call_with_telemetry_scope(
        [{"role": "user", "content": "staged-only"}],
        max_output_tokens=16000, run_id="run-a", task_id="task-a",
    )
    model.clear_continuity_scope(run_id="run-a", task_id="task-a")
    _scoped_call(model, "fresh")
    assert "previous_response_id" not in client.responses.requests[1]


def test_store_true_response_inventory_survives_provider_output_rejection() -> None:
    bad = _response(1, _function_call(response_no=1), _function_call(response_no=99))
    model, _client = _model([bad])
    with pytest.raises(AzureProviderOutputError):
        model.call_with_telemetry_scope(
            [{"role": "user", "content": "bad-provider-output"}],
            max_output_tokens=16000, run_id="run-a", task_id="task-a",
        )
    event = model.drain_telemetry()[0]
    assert event["pcr_remote_response_inventory_observed"] is True
    assert event["pcr_remote_response_inventory_response_id"] == "resp-1"
    assert event["status"] == "failed"


def test_modelhooks_commits_only_after_local_runtime_validation() -> None:
    from aether.model_hooks import ModelHooks, ModelOutputError

    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2)),
        _response(3, _function_call(response_no=3)),
    ])
    hooks = ModelHooks(model, lambda *_args, **_kwargs: "{}", run_id="run-a", task_id="task-a")
    allowed = SimpleNamespace(
                action_schema=(("read_file", ("path",)),),
    )
    blocked = SimpleNamespace(
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
    admissions = [row for row in rows if row.get("event_kind") == "pcr_continuity_parent_admission"]
    assert [row["pcr_continuity_parent_disposition"] for row in admissions] == [
        "committed", "rejected", "committed",
    ]


def test_production_solver_requests_all_turns_reasoning_context() -> None:
    model, client = _model(
        [_response(
            1,
            _function_call(response_no=1),
            reasoning_context="all_turns",
        )],
    )
    _scoped_call(model, "all-turns-capability-probe")
    request = client.responses.requests[0]
    assert request["reasoning"] == {"effort": "low", "context": "all_turns"}
    event = model.drain_telemetry()[0]
    assert event["pcr_reasoning_context_requested"] == "all_turns"
    assert event["pcr_reasoning_context_effective"] == "all_turns"
    assert event["pcr_reasoning_context_status"] == "matched"


def test_production_preflight_is_single_native_previous_response_route() -> None:
    model, _client = _model([])
    row = model.preflight_request(max_output_tokens=16000, logical_role="solver")
    assert row["provider"] == "azure_openai_responses"
    assert row["structured_output_mode"] == "pcr_v0_direct_native_tools"
    assert row["response_cardinality_contract"] == "exactly_one_required_direct_pcr_function_call"
    assert row["pcr_continuity_mode"] == "previous_response"
    assert row["background"] is False
    assert row["certification"] == "responses_single_direct_pcr_native_tool_call_contract"


class _FakeBadRequest(Exception):
    def __init__(self, code: str) -> None:
        self.status_code = 400
        self.body = {"message": code, "type": "invalid_request_error", "param": "previous_response_id", "code": code}
        super().__init__(code)


def test_previous_response_not_found_reanchors_once_to_full_current_input_and_advances_new_chain() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _FakeBadRequest("previous_response_not_found"),
        _response(2, _function_call(response_no=2)),
        _response(3, _function_call(response_no=3)),
    ])
    _scoped_call(model, "context-one")
    _scoped_call(model, "context-two")
    _scoped_call(model, "context-three")

    assert len(client.responses.requests) == 4
    failed_chain = client.responses.requests[1]
    reanchor = client.responses.requests[2]
    after = client.responses.requests[3]
    assert failed_chain["previous_response_id"] == "resp-1"
    assert failed_chain["input"][0]["type"] == "function_call_output"
    assert "previous_response_id" not in reanchor
    assert reanchor["input"] == [{"role": "user", "content": "context-two"}]
    assert after["previous_response_id"] == "resp-2"
    assert after["input"][0]["call_id"] == "call-2"

    events = model.drain_telemetry()
    assert len(events) == 3
    recovered = events[1]
    assert recovered["status"] == "completed"
    assert recovered["attempt_ordinal"] == 1
    assert recovered["pcr_continuity_reanchor_attempted"] is True
    assert recovered["pcr_continuity_reanchor_succeeded"] is True
    assert recovered["pcr_continuity_reanchor_reason"] == "previous_response_not_found"
    assert recovered["pcr_continuity_reanchor_create_count"] == 2
    assert recovered["pcr_continuity_reanchor_from_response_id"] == "resp-1"
    assert recovered["pcr_continuity_reanchor_from_call_id"] == "call-1"
    assert recovered["pcr_continuity_reanchor_failed_request_previous_response_id"] == "resp-1"
    assert recovered["pcr_continuity_reanchor_failed_request_function_call_output_count"] == 1
    assert recovered["pcr_continuity_reanchor_failed_request_function_call_output_call_ids"] == ["call-1"]
    assert recovered["pcr_continuity_reanchor_failed_request_input_sha256"]
    assert recovered["pcr_continuity_request_previous_response_id"] is None
    assert recovered["pcr_continuity_request_input_item_types"] == ["message:user"]
    assert recovered["pcr_continuity_request_function_call_output_count"] == 0
    assert recovered["pcr_continuity_current_boundary_direct_input_match"] is True


def test_other_bad_request_does_not_reanchor_or_retry() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _FakeBadRequest("invalid_request"),
    ])
    _scoped_call(model, "context-one")
    with pytest.raises(AzureModelError, match="responses native-tool call failed"):
        _scoped_call(model, "context-two")
    assert len(client.responses.requests) == 2
    event = model.drain_telemetry()[-1]
    assert event["pcr_continuity_reanchor_attempted"] is False


def test_previous_response_not_found_with_staged_native_image_fails_closed() -> None:
    model, client = _model([
        _response(1, _function_call(response_no=1)),
        _FakeBadRequest("previous_response_not_found"),
    ])
    _scoped_call(model, "context-one")
    raw = b"image-bytes"
    assert model.stage_native_image_observation(
        image_bytes=raw,
        media_type="image/png",
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        artifact_path="image.png",
        source_receipt_id="receipt:image",
        run_id="run-a",
        task_id="task-a",
    ) is True
    with pytest.raises(AzureModelError, match="native_image_requires_lossless_binding"):
        _scoped_call(model, "context-two")
    assert len(client.responses.requests) == 2
    event = model.drain_telemetry()[-1]
    assert event["pcr_continuity_reanchor_attempted"] is True
    assert event["pcr_continuity_reanchor_succeeded"] is False
    assert event["pcr_continuity_reanchor_blocked_reason"] == "native_image_staged"


class _AsyncSequenceResponses:
    def __init__(self, rows: list[object]) -> None:
        self.rows = list(rows)
        self.requests: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        if not self.rows:
            raise AssertionError("no async fake response remains")
        item = self.rows.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def retrieve(self, _response_id: str) -> object:
        raise AssertionError("foreground completed fake must not poll")

    async def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not cancel")


class _AsyncSequenceClient:
    def __init__(self, responses: _AsyncSequenceResponses) -> None:
        self.responses = responses
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_previous_response_not_found_reanchor_runs_through_production_async_bridge() -> None:
    responses = _AsyncSequenceResponses([
        _response(1, _function_call(response_no=1)),
        _FakeBadRequest("previous_response_not_found"),
        _response(2, _function_call(response_no=2)),
    ])
    async_client = _AsyncSequenceClient(responses)
    transport = azure_model._AsyncResponsesTransport(client_factory=lambda: async_client)
    model = AzureModelCallable(
        client=_FakeClient([]),  # sync fallback must remain unused
        async_transport=transport,
        deployment="unit-async-reanchor",
        effort="low",
        role="solver",
        responses_background=False,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode="off",
    )
    try:
        _scoped_call(model, "context-one")
        _scoped_call(model, "context-two")
        assert len(responses.requests) == 3
        assert responses.requests[1]["previous_response_id"] == "resp-1"
        assert "previous_response_id" not in responses.requests[2]
        event = model.drain_telemetry()[-1]
        assert event["pcr_continuity_reanchor_succeeded"] is True
        assert event["attempt_ordinal"] == 1
    finally:
        model.close_run_transport()
    assert async_client.closed is True


def test_background_mode_uses_same_exact_previous_response_function_output_shape() -> None:
    """Provider-free assembly proof for the S6 background-continuity live canary.

    Azure historically rejected the second request server-side.  Locally we
    prove background mode does not alter Aether's exact continuity binding:
    same stored response id, same native call id, same current-boundary output.
    """
    client = _FakeClient([
        _response(1, _function_call(response_no=1)),
        _response(2, _function_call(response_no=2, path='/app/next.txt')),
    ])
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment='unit-test-luna', effort='low', role='solver',
        responses_background=True, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode='off',
    )
    _scoped_call(model, 'background-one')
    _scoped_call(model, 'background-two')
    first, second = client.responses.requests
    assert first['background'] is True
    assert second['background'] is True
    assert second['previous_response_id'] == 'resp-1'
    assert second['input'] == [{
        'type':'function_call_output',
        'call_id':'call-1',
        'output':json.dumps(
            [{'role':'user','content':'background-two'}],
            sort_keys=True, separators=(',', ':'),
        ),
    }]
    events = model.drain_telemetry()
    assert events[1]['pcr_continuity_request_previous_response_id'] == 'resp-1'
    assert events[1]['pcr_continuity_expected_prior_call_id'] == 'call-1'
    assert events[1]['pcr_continuity_prior_call_id_match_count'] == 1
    assert events[1]['pcr_continuity_request_function_call_output_count'] == 1


def test_websocket_terminal_server_error_retries_once_without_continuity_commit() -> None:
    from aether.providers.azure_model import AzureModelCallable
    from aether.providers.responses_websocket import ResponsesWebSocketError

    class _Ws:
        def __init__(self): self.requests=[]; self.n=0; self.closed=False
        def call(self, request, *, cancellation_check=None):
            if cancellation_check: cancellation_check()
            self.requests.append(dict(request)); self.n+=1
            if self.n == 1:
                raise ResponsesWebSocketError(
                    'terminal server error', terminal=True, retry_safe=True,
                    provider_error_code='server_error',
                )
            return _response(1, _function_call(response_no=1))
        def close(self): self.closed=True
        def last_call_observability(self): return {}

    ws=_Ws(); client=_FakeClient([])
    model=AzureModelCallable(
        client=client, websocket_transport=ws, deployment='unit-test-luna', effort='low', role='solver',
        responses_background=False, responses_websocket=True,
        poll_interval_s=1.0, poll_timeout_s=30.0, max_retries=1,
        backoff_base_s=0.0, sleep=lambda _s: None, rand=lambda: 0.0, prompt_cache_mode='off',
    )
    result=_scoped_call(model,'retry-safe-turn')
    assert result
    assert len(ws.requests)==2
    assert ws.requests[0] == ws.requests[1]
    assert 'previous_response_id' not in ws.requests[0]
    events=model.drain_telemetry()
    assert len(events)==2
    assert [event['attempt_ordinal'] for event in events] == [1,2]
    assert [event['logical_call_id'] for event in events] == [1,1]
    assert events[0]['status']=='failed'
    assert events[1]['status']=='completed'
    assert events[0]['input_sha256']==events[1]['input_sha256']
    assert events[0]['instructions_sha256']==events[1]['instructions_sha256']


def test_websocket_seam_preserves_previous_response_function_output_contract() -> None:
    from aether.providers.azure_model import AzureModelCallable

    class _Ws:
        def __init__(self): self.requests=[]; self.n=0; self.closed=False
        def call(self, request, *, cancellation_check=None):
            if cancellation_check: cancellation_check()
            self.requests.append(dict(request)); self.n+=1
            return _response(self.n, _function_call(response_no=self.n))
        def close(self): self.closed=True

    ws=_Ws(); client=_FakeClient([])
    model=AzureModelCallable(
        client=client, websocket_transport=ws, deployment='unit-test-luna', effort='low', role='solver',
        responses_background=False, responses_websocket=True,
        poll_interval_s=1.0, poll_timeout_s=30.0, max_retries=0, prompt_cache_mode='off',
    )
    _scoped_call(model,'context-one')
    _scoped_call(model,'context-two')
    assert len(ws.requests)==2
    assert ws.requests[0]['store'] is True
    assert 'previous_response_id' not in ws.requests[0]
    assert ws.requests[1]['previous_response_id']=='resp-1'
    assert ws.requests[1]['input']==[{
        'type':'function_call_output','call_id':'call-1',
        'output':json.dumps([{'role':'user','content':'context-two'}],sort_keys=True,separators=(',',':')),
    }]
    events=model.drain_telemetry()
    assert events[0]['provider_transport_mode']=='websocket'
    assert events[1]['provider_transport_mode']=='websocket'

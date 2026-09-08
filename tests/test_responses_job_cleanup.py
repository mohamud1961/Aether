from __future__ import annotations

import asyncio
import json
import threading
import threading
from types import SimpleNamespace

import pytest

from aether.providers import azure_model
from aether.providers.azure_model import AzureModelCallable, AzureModelError
from aether.run_cancellation import RunCancellationRequested


class _Job:
    def __init__(self, status: str, *, job_id: str = "job-cleanup", path: str = "/app/ok") -> None:
        self.id = job_id
        self.status = status
        self.output = ([SimpleNamespace(
            id=f"{job_id}-call",
            type="function_call",
            status="completed",
            call_id=f"{job_id}-call-id",
            name="read_file",
            arguments=json.dumps({"arguments": {"path": path}}),
        )] if status == "completed" else [])
        self.reasoning = None
        self.error = None
        self.incomplete_details = None
        self.usage = None


class _Responses:
    def __init__(self, *, retrieve_error: Exception | None = None, cancel_error: Exception | None = None, completed: bool = False) -> None:
        self.job = _Job("completed") if completed else _Job("queued")
        self.retrieve_error = retrieve_error
        self.cancel_error = cancel_error
        self.create_calls = 0
        self.retrieve_calls = 0
        self.cancel_calls: list[str] = []

    def create(self, **_kwargs):
        self.create_calls += 1
        return self.job

    def retrieve(self, _job_id: str):
        self.retrieve_calls += 1
        if self.retrieve_error is not None:
            raise self.retrieve_error
        return self.job

    def cancel(self, job_id: str):
        self.cancel_calls.append(job_id)
        if self.cancel_error is not None:
            raise self.cancel_error
        self.job = _Job("cancelled", job_id=job_id)
        return self.job


class _Client:
    def __init__(self, responses: _Responses) -> None:
        self.responses = responses


def _model(responses: _Responses) -> AzureModelCallable:
    return AzureModelCallable(
        client=_Client(responses),  # type: ignore[arg-type]
        deployment="unit-cleanup",
        effort="low",
        role="solver",
        responses_background=True,
        prompt_cache_mode="off",
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        sleep=lambda _seconds: None,
        rand=lambda: 0.0,
    )


def _call(model: AzureModelCallable) -> str:
    return model.call_with_telemetry_scope(
        [{"role": "user", "content": "return one current PCR turn"}],
        max_output_tokens=16000,
        run_id="cleanup-run",
        task_id="cleanup-task",
    )


def test_poll_timeout_cancels_remote_nonterminal_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(azure_model.time, "sleep", lambda _seconds: None)
    responses = _Responses()
    model = _model(responses)

    with pytest.raises(AzureModelError, match="timed out after 30s"):
        _call(model)

    assert responses.cancel_calls == ["job-cleanup"]
    event = model.drain_telemetry()[0]
    assert event["provider_job_cancel_attempted"] is True
    assert event["provider_job_cancel_status"] == "cancelled"
    assert event["provider_job_cancel_succeeded"] is True
    assert event["status"] == "failed"


def test_retrieve_failure_cancels_last_known_nonterminal_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(azure_model.time, "sleep", lambda _seconds: None)
    responses = _Responses(retrieve_error=RuntimeError("connection lost"))
    model = _model(responses)

    with pytest.raises(AzureModelError, match="responses.retrieve failed"):
        _call(model)

    assert responses.cancel_calls == ["job-cleanup"]
    event = model.drain_telemetry()[0]
    assert event["provider_job_cancel_succeeded"] is True
    assert "connection lost" in event["error"]


def test_cancel_failure_is_telemetry_and_does_not_mask_original_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(azure_model.time, "sleep", lambda _seconds: None)
    responses = _Responses(cancel_error=RuntimeError("cancel unavailable"))
    model = _model(responses)

    with pytest.raises(AzureModelError, match="timed out after 30s"):
        _call(model)

    event = model.drain_telemetry()[0]
    assert event["provider_job_cancel_attempted"] is True
    assert event["provider_job_cancel_succeeded"] is False
    assert event["provider_job_cancel_error_type"] == "RuntimeError"
    assert event["provider_job_cancel_error"] == "cancel unavailable"
    assert "timed out after 30s" in event["error"]


def test_completed_job_is_never_cancelled() -> None:
    responses = _Responses(completed=True)
    model = _model(responses)

    result = json.loads(_call(model))
    assert result == {
        "kind": "act",
        "action": {"kind": "read_file", "arguments": {"path": "/app/ok"}},
    }
    assert responses.cancel_calls == []
    event = model.drain_telemetry()[0]
    assert "provider_job_cancel_attempted" not in event
    assert event["status"] == "completed"



def test_run_cancellation_cancels_remote_nonterminal_job(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = _Responses()
    model = _model(responses)
    cancellation = threading.Event()
    model.bind_run_cancellation(cancellation)

    def revoke(_seconds: float) -> None:
        cancellation.set()

    monkeypatch.setattr(azure_model.time, "sleep", revoke)
    with pytest.raises(RunCancellationRequested, match="cancellation requested"):
        _call(model)

    assert responses.cancel_calls == ["job-cleanup"]
    event = model.drain_telemetry()[0]
    assert event["provider_job_cancel_attempted"] is True
    assert event["provider_job_cancel_succeeded"] is True
    assert event["error_type"] == "RunCancellationRequested"


class _BlockingAsyncResponses:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.cancelled = threading.Event()
        self.requests: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.requests.append(dict(kwargs))
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class _BlockingAsyncClient:
    def __init__(self, responses: _BlockingAsyncResponses) -> None:
        self.responses = responses
        self.closed = threading.Event()

    async def close(self) -> None:
        self.closed.set()


def test_foreground_solver_request_is_cancelled_and_drained_by_async_transport() -> None:
    responses = _BlockingAsyncResponses()
    async_client = _BlockingAsyncClient(responses)
    transport = azure_model._AsyncResponsesTransport(client_factory=lambda: async_client)
    model = AzureModelCallable(
        client=_Client(_Responses(completed=True)),  # sync fallback must remain unused
        async_transport=transport,
        deployment="unit-cancellable-foreground",
        effort="low",
        role="solver",
        responses_background=False,
        prompt_cache_mode="off",
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        sleep=lambda _seconds: None,
        rand=lambda: 0.0,
    )
    cancellation = threading.Event()
    model.bind_run_cancellation(cancellation)
    outcome: dict[str, str] = {}

    def invoke() -> None:
        try:
            _call(model)
        except BaseException as exc:  # control-flow exception is intentional here
            outcome["type"] = type(exc).__name__

    worker = threading.Thread(target=invoke)
    worker.start()
    assert responses.started.wait(timeout=1.0)
    cancellation.set()
    worker.join(timeout=1.0)
    model.close_run_transport()

    assert not worker.is_alive()
    assert outcome == {"type": "RunCancellationRequested"}
    assert responses.cancelled.is_set()
    assert async_client.closed.is_set()
    assert responses.requests[0]["background"] is False


def test_foreground_vision_request_is_cancelled_and_drained_by_async_transport() -> None:
    responses = _BlockingAsyncResponses()
    async_client = _BlockingAsyncClient(responses)
    transport = azure_model._AsyncResponsesTransport(client_factory=lambda: async_client)
    model = azure_model.AzureVisionCallable(
        _Client(_Responses(completed=True)),
        "unit-cancellable-vision",
        async_transport=transport,
    )
    cancellation = threading.Event()
    model.bind_run_cancellation(cancellation)
    outcome: dict[str, str] = {}

    def invoke() -> None:
        try:
            model("inspect", "AA==", "image/png")
        except BaseException as exc:  # control-flow exception is intentional here
            outcome["type"] = type(exc).__name__

    worker = threading.Thread(target=invoke)
    worker.start()
    assert responses.started.wait(timeout=1.0)
    cancellation.set()
    worker.join(timeout=1.0)
    model.close_run_transport()

    assert not worker.is_alive()
    assert outcome == {"type": "RunCancellationRequested"}
    assert responses.cancelled.is_set()
    assert async_client.closed.is_set()


def test_foreground_verifier_request_is_cancelled_and_drained_by_async_transport() -> None:
    responses = _BlockingAsyncResponses()
    async_client = _BlockingAsyncClient(responses)
    transport = azure_model._AsyncResponsesTransport(client_factory=lambda: async_client)
    model = AzureModelCallable(
        client=_Client(_Responses(completed=True)),
        async_transport=transport,
        deployment="unit-cancellable-verifier",
        effort="low",
        role="verifier",
        responses_background=False,
        prompt_cache_mode="off",
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        sleep=lambda _seconds: None,
        rand=lambda: 0.0,
    )
    cancellation = threading.Event()
    model.bind_run_cancellation(cancellation)
    outcome: dict[str, str] = {}

    def invoke() -> None:
        try:
            _call(model)
        except BaseException as exc:
            outcome["type"] = type(exc).__name__

    worker = threading.Thread(target=invoke)
    worker.start()
    assert responses.started.wait(timeout=1.0)
    cancellation.set()
    worker.join(timeout=1.0)
    model.close_run_transport()

    assert not worker.is_alive()
    assert outcome == {"type": "RunCancellationRequested"}
    assert responses.cancelled.is_set()
    assert async_client.closed.is_set()
    assert responses.requests[0]["background"] is False

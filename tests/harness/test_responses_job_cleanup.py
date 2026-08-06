from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether.providers import azure_model
from aether.providers.azure_model import AzureModelCallable, AzureModelError


class _Job:
    def __init__(self, status: str, *, job_id: str = "job-cleanup", text: str = "") -> None:
        self.id = job_id
        self.status = status
        self.output_text = text
        self.output = ([SimpleNamespace(
            id=f"{job_id}-message",
            type="message",
            role="assistant",
            content=[SimpleNamespace(type="output_text", text=text)],
        )] if text else [])
        self.error = None
        self.incomplete_details = None
        self.usage = None


class _Responses:
    def __init__(self, *, retrieve_error: Exception | None = None, cancel_error: Exception | None = None, completed: bool = False) -> None:
        self.job = _Job("completed", text='{"ok":true}') if completed else _Job("queued")
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
        role="architect",
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        transport="responses",
        sleep=lambda _seconds: None,
        rand=lambda: 0.0,
    )


def test_poll_timeout_cancels_remote_nonterminal_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(azure_model.time, "sleep", lambda _seconds: None)
    responses = _Responses()
    model = _model(responses)

    with pytest.raises(AzureModelError, match="timed out after 30s"):
        model([{"role": "user", "content": "return one object"}])

    assert responses.cancel_calls == ["job-cleanup"]
    event = model.drain_telemetry()[0]
    assert event["provider_job_cancel_attempted"] is True
    assert event["provider_job_status_before_cancel"] == "queued"
    assert event["provider_job_cancel_status"] == "cancelled"
    assert event["provider_job_cancel_succeeded"] is True
    assert event["status"] == "failed"


def test_retrieve_failure_cancels_last_known_nonterminal_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(azure_model.time, "sleep", lambda _seconds: None)
    responses = _Responses(retrieve_error=RuntimeError("connection lost"))
    model = _model(responses)

    with pytest.raises(AzureModelError, match="responses.retrieve failed"):
        model([{"role": "user", "content": "return one object"}])

    assert responses.cancel_calls == ["job-cleanup"]
    event = model.drain_telemetry()[0]
    assert event["provider_job_cancel_succeeded"] is True
    assert "connection lost" in event["error"]


def test_cancel_failure_is_telemetry_and_does_not_mask_original_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(azure_model.time, "sleep", lambda _seconds: None)
    responses = _Responses(cancel_error=RuntimeError("cancel unavailable"))
    model = _model(responses)

    with pytest.raises(AzureModelError, match="timed out after 30s"):
        model([{"role": "user", "content": "return one object"}])

    event = model.drain_telemetry()[0]
    assert event["provider_job_cancel_attempted"] is True
    assert event["provider_job_cancel_succeeded"] is False
    assert event["provider_job_cancel_error_type"] == "RuntimeError"
    assert event["provider_job_cancel_error"] == "cancel unavailable"
    assert "timed out after 30s" in event["error"]


def test_completed_job_is_never_cancelled() -> None:
    responses = _Responses(completed=True)
    model = _model(responses)

    assert model([{"role": "user", "content": "return one object"}]) == '{"ok":true}'
    assert responses.cancel_calls == []
    event = model.drain_telemetry()[0]
    assert "provider_job_cancel_attempted" not in event
    assert event["status"] == "completed"

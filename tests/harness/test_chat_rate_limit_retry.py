from __future__ import annotations

import pytest
from types import SimpleNamespace

from aether.provider_pacing import SerialTokenPacer
from aether.providers.chat_model import ChatCompletionsModelCallable, ChatModelError, ChatModelOutputError


def _text_response(text: str = "ok") -> dict:
    return {
        "choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": text},
        }],
        "usage": {
            "prompt_tokens": 7,
            "completion_tokens": 2,
            "total_tokens": 9,
        },
    }


class RateLimitThenSuccess:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        if len(self.requests) == 1:
            raise RuntimeError("429 rate limit exceeded")
        return _text_response()


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_one_pre_response_429_retries_after_full_pacer_blackout() -> None:
    clock = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=10_000, window_s=10.0, clock=clock, sleep=clock.sleep,
    )
    transport = RateLimitThenSuccess()
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="verifier",
        native_persistent_tools=False,
        throughput_pacer=pacer,
        max_retries=1,
    )

    assert model([{"role": "user", "content": "Answer."}], max_output_tokens=16) == "ok"
    assert len(transport.requests) == 2
    assert clock.now >= 10.0

    rows = model.drain_telemetry()
    assert len(rows) == 2
    assert [row["attempt_ordinal"] for row in rows] == [1, 2]
    assert rows[0]["logical_call_id"] == rows[1]["logical_call_id"] == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["provider_retry_scheduled"] is True
    assert rows[0]["provider_retry_reason"] == "pre_response_rate_limit"
    assert rows[0]["throughput_rate_limit_backoff_recorded"] is True
    assert rows[1]["status"] == "completed"
    assert rows[1]["provider_retry_from_attempt_ordinal"] == 1
    assert rows[1]["throughput_wait_s"] >= 10.0


def test_model_output_failure_is_never_retried() -> None:
    class Transport:
        def __init__(self) -> None:
            self.requests: list[dict] = []

        def create(self, **request):
            self.requests.append(request)
            # Always truncated: the only extra request allowed is the single
            # doubled-cap escalation, never a transport/model-turn retry.
            return {
                "choices": [{
                    "finish_reason": "length",
                    "message": {"role": "assistant", "content": "partial"},
                }],
            }

    transport = Transport()
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="verifier",
        native_persistent_tools=False,
        max_retries=1,
    )

    with pytest.raises(ChatModelOutputError, match="provider_output_truncated"):
        model([{"role": "user", "content": "Answer."}], max_output_tokens=16)
    assert [r["max_tokens"] for r in transport.requests] == [16, 32]
    rows = model.drain_telemetry()
    assert len(rows) == 2
    assert [r["attempt_ordinal"] for r in rows] == [1, 2]
    assert all(r["status"] == "failed" for r in rows)
    assert not any(r.get("provider_retry_scheduled") for r in rows)


def test_retry_count_is_bounded_to_two() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        ChatCompletionsModelCallable(
            transport=RateLimitThenSuccess(),
            deployment="glm-test",
            role="verifier",
            native_persistent_tools=False,
            max_retries=3,
        )


def test_retry_takes_second_reservation_and_only_settles_successful_attempt() -> None:
    class Guard:
        contract = SimpleNamespace(schema_version="aether.provider_budget.v2")
        def __init__(self) -> None:
            self.reserved: list[dict] = []
            self.settled: list[dict] = []
        def reserve(self, role, request):
            row={"reservation_id": len(self.reserved)+1, "role": role}
            self.reserved.append(row)
            return row
        def settle_success(self, reservation, *, input_tokens, output_tokens):
            self.settled.append({
                "reservation": reservation,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            })
            return {"settled": True, "reservation_id": reservation["reservation_id"]}

    guard=Guard()
    transport=RateLimitThenSuccess()
    model=ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="verifier",
        native_persistent_tools=False,
        budget_guard=guard,
        max_retries=1,
    )
    assert model([{"role":"user","content":"Answer."}], max_output_tokens=16) == "ok"
    assert [r["reservation_id"] for r in guard.reserved] == [1, 2]
    assert [r["reservation"]["reservation_id"] for r in guard.settled] == [2]
    rows=model.drain_telemetry()
    assert rows[0]["provider_budget_reservation"]["reservation_id"] == 1
    assert rows[0]["provider_budget_settlement_status"] == "retained_failed_attempt"
    assert rows[1]["provider_budget_reservation"]["reservation_id"] == 2
    assert rows[1]["provider_budget_settlement_status"] == "settled_terminal_success_usage"



class SyntheticServerError(RuntimeError):
    def __init__(self, message: str = "synthetic 500") -> None:
        self.status_code = 500
        super().__init__(message)


class ServerErrorThenSuccess:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        if len(self.requests) == 1:
            raise SyntheticServerError()
        return _text_response()


def test_one_pre_response_500_retries_once_without_rate_limit_blackout() -> None:
    clock = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=10_000, window_s=10.0, clock=clock, sleep=clock.sleep,
    )
    transport = ServerErrorThenSuccess()
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="verifier",
        native_persistent_tools=False,
        throughput_pacer=pacer,
        max_retries=1,
    )

    assert model([{"role": "user", "content": "Answer."}], max_output_tokens=16) == "ok"
    assert len(transport.requests) == 2

    rows = model.drain_telemetry()
    assert len(rows) == 2
    assert [row["attempt_ordinal"] for row in rows] == [1, 2]
    assert rows[0]["status"] == "failed"
    assert rows[0]["provider_retry_scheduled"] is True
    assert rows[0]["provider_retry_reason"] == "pre_response_server_error"
    assert "throughput_rate_limit_backoff_recorded" not in rows[0]
    assert rows[1]["status"] == "completed"
    assert rows[1]["provider_retry_reason"] == "pre_response_server_error"


def test_persistent_pre_response_500_is_bounded_to_two_attempts() -> None:
    class AlwaysServerError:
        def __init__(self) -> None:
            self.requests: list[dict] = []
        def create(self, **request):
            self.requests.append(request)
            raise SyntheticServerError("still unavailable")

    transport = AlwaysServerError()
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="verifier",
        native_persistent_tools=False,
        max_retries=1,
    )
    with pytest.raises(ChatModelError, match="still unavailable") as caught:
        model([{"role": "user", "content": "Answer."}], max_output_tokens=16)
    assert isinstance(caught.value.__cause__, SyntheticServerError)
    assert len(transport.requests) == 2
    rows = model.drain_telemetry()
    assert len(rows) == 2
    assert rows[0]["provider_retry_reason"] == "pre_response_server_error"
    assert rows[1]["attempt_ordinal"] == 2
    assert rows[1]["status"] == "failed"


def test_pre_response_400_is_not_retried() -> None:
    class SyntheticClientError(RuntimeError):
        status_code = 400
    class Transport:
        def __init__(self) -> None:
            self.requests: list[dict] = []
        def create(self, **request):
            self.requests.append(request)
            raise SyntheticClientError("bad request")

    transport = Transport()
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="verifier",
        native_persistent_tools=False,
        max_retries=1,
    )
    with pytest.raises(ChatModelError, match="bad request") as caught:
        model([{"role": "user", "content": "Answer."}], max_output_tokens=16)
    assert isinstance(caught.value.__cause__, SyntheticClientError)
    assert len(transport.requests) == 1
    rows = model.drain_telemetry()
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert "provider_retry_scheduled" not in rows[0]


def test_string_only_5xx_shape_is_retryable_for_sdk_compatibility() -> None:
    class StringServerThenSuccess:
        def __init__(self) -> None:
            self.requests: list[dict] = []
        def create(self, **request):
            self.requests.append(request)
            if len(self.requests) == 1:
                raise RuntimeError("Error code: 503 - backend unavailable")
            return _text_response()

    transport = StringServerThenSuccess()
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="verifier",
        native_persistent_tools=False,
        max_retries=1,
    )
    assert model([{"role": "user", "content": "Answer."}], max_output_tokens=16) == "ok"
    assert len(transport.requests) == 2
    rows = model.drain_telemetry()
    assert rows[0]["provider_retry_reason"] == "pre_response_server_error"

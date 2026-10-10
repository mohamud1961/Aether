from __future__ import annotations

from types import SimpleNamespace

from aether.providers.chat_model import ChatCompletionsModelCallable


def _response() -> dict:
    return {
        "model": "glm-test",
        "choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "ok"},
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


class RawResponse:
    def __init__(self, payload: dict, headers: dict[str, str]) -> None:
        self.headers = headers
        self._payload = payload

    def parse(self) -> dict:
        return self._payload


class RawResponseTransport:
    def __init__(self, *responses: RawResponse) -> None:
        self.responses = list(responses)

    def create(self, **_request) -> RawResponse:
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeTransport:
    def __init__(self, *responses: RawResponse) -> None:
        self.with_raw_response = RawResponseTransport(*responses)

    def create(self, **_request):
        raise AssertionError("raw response path must be used when header capture is enabled")


def test_provider_attempt_captures_capacity_headers_and_omits_absent_headers() -> None:
    transport = FakeTransport(
        RawResponse(_response(), {
            "X-RateLimit-Remaining-Tokens": "91234",
            "x-ratelimit-remaining-requests": "97",
            "X-RateLimit-Reset-Tokens": "2s",
            "X-Ms-RateLimit-Remaining-Tokens": "81234",
            "Retry-After": "3",
            "Retry-After-Ms": "2500",
            "X-MS-Region": "eastus",
            "APIM-Request-Id": "apim-123",
            "X-Request-Id": "request-456",
            "Content-Type": "application/json",
            "Authorization": "secret-value",
            "Set-Cookie": "secret-cookie",
        }),
        RawResponse(_response(), {
            "Content-Type": "application/json",
            "Authorization": "secret-value",
        }),
    )
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="verifier",
        native_persistent_tools=False,
        capture_rate_headers=True,
    )

    for _ in range(2):
        model([{"role": "user", "content": "Answer."}], max_output_tokens=32)

    rows = model.drain_telemetry()
    assert len(rows) == 2
    assert rows[0]["provider_rate_limit_headers"] == {
        "x-ratelimit-remaining-tokens": "91234",
        "x-ratelimit-remaining-requests": "97",
        "x-ratelimit-reset-tokens": "2s",
        "x-ms-ratelimit-remaining-tokens": "81234",
        "retry-after": "3",
        "retry-after-ms": "2500",
    }
    assert "provider_rate_limit_headers" not in rows[1]


def test_rate_limit_exception_headers_stay_on_failed_attempt_only() -> None:
    rate_limited = RuntimeError("HTTP 429 rate limit")
    rate_limited.status_code = 429
    rate_limited.response = SimpleNamespace(headers={
        "Retry-After-Ms": "1500",
        "X-RateLimit-Remaining-Tokens": "0",
        "Authorization": "secret-value",
    })
    transport = FakeTransport(
        rate_limited,
        RawResponse(_response(), {"Content-Type": "application/json"}),
    )
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=False,
        max_retries=1,
        capture_rate_headers=True,
    )

    model([{"role": "user", "content": "Answer."}], max_output_tokens=32)

    rows = model.drain_telemetry()
    assert len(rows) == 2
    assert rows[0]["status"] == "failed"
    assert rows[0]["attempt_ordinal"] == 1
    assert rows[0]["provider_rate_limit_headers"] == {
        "retry-after-ms": "1500",
        "x-ratelimit-remaining-tokens": "0",
    }
    assert rows[1]["status"] == "completed"
    assert rows[1]["attempt_ordinal"] == 2
    assert "provider_rate_limit_headers" not in rows[1]

import json
from pathlib import Path
from urllib.error import HTTPError

from runner.logger import RunLogger
from runner.model_client import (
    CODEX_INFERENCE_ENDPOINT,
    CODEX_REFRESH_ENDPOINT,
    CodexSubscriptionModelClient,
    ModelClientError,
    make_codex_subscription_route,
)


class _FakeHTTPResponse:
    def __init__(self, status_code: int, body: bytes):
        self._status_code = status_code
        self._body = body

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self._status_code

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def close(self) -> None:
        return None


def _sse_bytes(*payloads: object) -> bytes:
    chunks: list[str] = []
    for payload in payloads:
        if isinstance(payload, str):
            rendered = payload
        else:
            rendered = json.dumps(payload, separators=(",", ":"))
        chunks.append(f"data: {rendered}\n\n")
    return "".join(chunks).encode("utf-8")


def _write_auth(auth_path: Path, payload: dict[str, object]) -> None:
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_auth_top_level_layout_is_used_for_bearer(monkeypatch, tmp_path):
    auth_path = tmp_path / ".codex" / "auth.json"
    _write_auth(
        auth_path,
        {"access_token": "top-level-access", "refresh_token": "top-level-refresh"},
    )
    route = make_codex_subscription_route(model_name="gpt-5.4-mini")
    seen_headers: list[str | None] = []
    seen_bodies: list[dict[str, object]] = []
    sse_body = _sse_bytes(
        {"type": "response.completed", "response": {"status": "completed", "output": [], "usage": {}}},
        "[DONE]",
    )

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        assert request.full_url == CODEX_INFERENCE_ENDPOINT
        seen_headers.append(request.get_header("Authorization"))
        seen_bodies.append(json.loads(request.data.decode("utf-8")))
        return _FakeHTTPResponse(200, sse_body)

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = CodexSubscriptionModelClient(route=route, auth_path=auth_path)
    client.complete(messages=[{"role": "user", "content": "hello"}])

    assert seen_headers == ["Bearer top-level-access"]
    assert seen_bodies == [
        {
            "model": "gpt-5.4-mini",
            "store": False,
            "stream": True,
            "instructions": "You are a concise assistant. Follow the user and available tools exactly.",
            "input": [{"role": "user", "content": "hello"}],
            "tools": [],
        }
    ]


def test_auth_nested_layout_is_used_for_bearer(monkeypatch, tmp_path):
    auth_path = tmp_path / ".codex" / "auth.json"
    _write_auth(
        auth_path,
        {"tokens": {"access_token": "nested-access", "refresh_token": "nested-refresh"}},
    )
    route = make_codex_subscription_route(model_name="gpt-5.4-mini")
    seen_headers: list[str | None] = []
    sse_body = _sse_bytes(
        {"type": "response.completed", "response": {"status": "completed", "output": [], "usage": {}}},
        "[DONE]",
    )

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        assert request.full_url == CODEX_INFERENCE_ENDPOINT
        seen_headers.append(request.get_header("Authorization"))
        return _FakeHTTPResponse(200, sse_body)

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = CodexSubscriptionModelClient(route=route, auth_path=auth_path)
    client.complete(messages=[{"role": "user", "content": "hello"}])

    assert seen_headers == ["Bearer nested-access"]


def test_refresh_on_401_retries_once_and_persists_tokens(monkeypatch, tmp_path):
    auth_path = tmp_path / ".codex" / "auth.json"
    _write_auth(
        auth_path,
        {"access_token": "expired-access", "refresh_token": "keep-me"},
    )
    route = make_codex_subscription_route(model_name="gpt-5.4-mini")
    state = {"inference_calls": 0, "refresh_calls": 0, "auth_headers": []}
    success_sse = _sse_bytes(
        {
            "type": "response.completed",
            "response": {
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
            },
        },
        "[DONE]",
    )

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        if request.full_url == CODEX_INFERENCE_ENDPOINT:
            state["inference_calls"] += 1
            state["auth_headers"].append(request.get_header("Authorization"))
            if state["inference_calls"] == 1:
                raise HTTPError(
                    url=request.full_url,
                    code=401,
                    msg="Unauthorized",
                    hdrs=None,
                    fp=None,
                )
            return _FakeHTTPResponse(200, success_sse)
        if request.full_url == CODEX_REFRESH_ENDPOINT:
            state["refresh_calls"] += 1
            body = json.loads(request.data.decode("utf-8"))
            assert body["client_id"] == "app_codex"
            assert body["refresh_token"] == "keep-me"
            return _FakeHTTPResponse(200, json.dumps({"access_token": "new-access"}).encode("utf-8"))
        raise AssertionError(f"unexpected url: {request.full_url}")

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)
    monkeypatch.setattr("runner.model_client.time.sleep", lambda _: None)

    client = CodexSubscriptionModelClient(route=route, auth_path=auth_path, max_retries=0)
    result = client.complete(messages=[{"role": "user", "content": "hello"}])

    assert state["refresh_calls"] == 1
    assert state["inference_calls"] == 2
    assert state["auth_headers"] == ["Bearer expired-access", "Bearer new-access"]
    assert result["text"] == "ok"
    assert result["status"] == "completed"

    persisted = json.loads(auth_path.read_text(encoding="utf-8"))
    assert persisted["access_token"] == "new-access"
    assert persisted["refresh_token"] == "keep-me"


def test_sse_final_response_is_normalized_with_text_tool_calls_usage(monkeypatch, tmp_path):
    auth_path = tmp_path / ".codex" / "auth.json"
    _write_auth(
        auth_path,
        {"tokens": {"access_token": "nested-access", "refresh_token": "nested-refresh"}},
    )
    route = make_codex_subscription_route(model_name="gpt-5.4-mini")
    sse_body = _sse_bytes(
        {"type": "response.output_text.delta", "delta": "partial"},
        {
            "type": "response.completed",
            "response": {
                "status": "completed",
                "usage": {"input_tokens": 11, "output_tokens": 7},
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": "final-text"}]},
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "raw_bash",
                        "arguments": "{\"command\":\"pwd\"}",
                    },
                ],
            },
        },
        "[DONE]",
    )

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        return _FakeHTTPResponse(200, sse_body)

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = CodexSubscriptionModelClient(route=route, auth_path=auth_path)
    result = client.complete(messages=[{"role": "user", "content": "hello"}])

    assert result["text"] == "final-text"
    assert result["tool_calls"] == [
        {
            "type": "function_call",
            "id": "call-1",
            "name": "raw_bash",
            "arguments": "{\"command\":\"pwd\"}",
        }
    ]
    assert result["usage"] == {"input_tokens": 11, "output_tokens": 7}
    assert result["status"] == "completed"
    assert result["model_route"] == route
    assert "access_token" not in result["model_route"]
    assert "refresh_token" not in result["model_route"]


def test_top_level_output_payload_is_normalized(monkeypatch, tmp_path):
    auth_path = tmp_path / ".codex" / "auth.json"
    _write_auth(
        auth_path,
        {"tokens": {"access_token": "nested-access", "refresh_token": "nested-refresh"}},
    )
    route = make_codex_subscription_route(model_name="gpt-5.4-mini")
    sse_body = _sse_bytes(
        {
            "type": "response.completed",
            "status": "completed",
            "usage": {"input_tokens": 3, "output_tokens": 1},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "LIVE_SMOKE_OK"}]}],
        },
        "[DONE]",
    )

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        return _FakeHTTPResponse(200, sse_body)

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = CodexSubscriptionModelClient(route=route, auth_path=auth_path)
    result = client.complete(messages=[{"role": "user", "content": "hello"}])

    assert result["text"] == "LIVE_SMOKE_OK"
    assert result["usage"] == {"input_tokens": 3, "output_tokens": 1}
    assert result["status"] == "completed"


def test_http_error_details_include_response_body(monkeypatch, tmp_path):
    auth_path = tmp_path / ".codex" / "auth.json"
    _write_auth(
        auth_path,
        {"tokens": {"access_token": "nested-access", "refresh_token": "nested-refresh"}},
    )
    route = make_codex_subscription_route(model_name="gpt-5.4-mini")

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        raise HTTPError(
            url=request.full_url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=_FakeHTTPResponse(400, b'{"error":{"message":"tools payload invalid"}}'),
        )

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = CodexSubscriptionModelClient(route=route, auth_path=auth_path, max_retries=0)
    try:
        client.complete(messages=[{"role": "user", "content": "hello"}], tools=[{"name": "raw_bash"}])
    except ModelClientError as err:
        assert err.status_code == 400
        assert err.error_kind == "http_error"
        assert "tools payload invalid" in (err.response_body or "")
        assert err.details["status_code"] == 400
        assert "tools payload invalid" in err.details["response_body"]
    else:
        raise AssertionError("expected ModelClientError")


def test_request_tools_are_normalized_for_codex_route(monkeypatch, tmp_path):
    auth_path = tmp_path / ".codex" / "auth.json"
    _write_auth(
        auth_path,
        {"tokens": {"access_token": "nested-access", "refresh_token": "nested-refresh"}},
    )
    route = make_codex_subscription_route(model_name="gpt-5.4-mini")
    seen_bodies: list[dict[str, object]] = []
    sse_body = _sse_bytes(
        {"type": "response.completed", "response": {"status": "completed", "output": [], "usage": {}}},
        "[DONE]",
    )

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        seen_bodies.append(json.loads(request.data.decode("utf-8")))
        return _FakeHTTPResponse(200, sse_body)

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = CodexSubscriptionModelClient(route=route, auth_path=auth_path)
    client.complete(
        messages=[{"role": "user", "content": "hello"}],
        tools=[
            {
                "name": "raw_bash",
                "description": "Execute a bash command.",
                "input_schema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ],
    )

    assert seen_bodies[0]["tools"] == [
        {
            "type": "function",
            "name": "raw_bash",
            "description": "Execute a bash command.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        }
    ]


def test_run_artifact_header_remains_token_free(tmp_path):
    route = make_codex_subscription_route(
        model_name="gpt-5.4-mini",
        request_settings={"temperature": 0},
    )
    logger = RunLogger(tmp_path / "run-001")
    logger.start_run(
        {
            "run_id": "run-001",
            "started_at_utc": "2026-04-16T12:00:00Z",
            "task_id": "task-001",
            "benchmark_family": "smoke",
            "seed_id": "sc_b_01",
            "block_selection": {
                "orientation": "raw_prompt",
                "tools": "raw_bash",
                "execution": "flat_loop",
                "context": "full_history",
                "verification": "trust_model",
                "recovery": "no_recovery",
            },
            "environment": {
                "sandbox_type": "none",
                "sandbox_image": None,
                "cwd": str(tmp_path),
                "timeout_sec": 30,
            },
            "model_route": route,
            "scoring_contract": {"scoring_contract_version": "score_envelope.v0"},
        }
    )

    header_text = (tmp_path / "run-001" / "run_header.json").read_text(encoding="utf-8")
    assert "access_token" not in header_text
    assert "refresh_token" not in header_text

import json
from email.message import Message
from urllib.error import HTTPError

import pytest

from runner.eval_batch_runner import (
    _accumulate_budget_progress,
    _build_recommendation_draft,
    _budget_summary_from_tracker,
    _init_budget_tracker,
    _resolve_model_tier_selector,
    _token_and_cost_summary,
)
from runner.eval_runner_router import resolve_model_route_for_route
from runner.model_client import (
    AZURE_ENV_API_VERSION,
    AZURE_ENV_ENDPOINT,
    AZURE_ENV_GPT53_CODEX_DEPLOYMENT,
    AZURE_ENV_GPT53_CODEX_KEY,
    AZURE_ENV_GPT54_MINI_DEPLOYMENT,
    AZURE_ENV_GPT54_MINI_KEY,
    AzureOpenAIAPIKeyModelClient,
    ModelClientError,
    make_azure_gpt53_codex_route_from_env,
    make_azure_gpt54_mini_route_from_env,
    make_azure_openai_route,
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


def _set_azure_env(monkeypatch):
    monkeypatch.setenv(AZURE_ENV_ENDPOINT, "https://example-resource.openai.azure.com")
    monkeypatch.setenv(AZURE_ENV_API_VERSION, "2024-12-01-preview")
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_KEY, "secret-mini-key")
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_DEPLOYMENT, "dep-gpt54-mini")
    monkeypatch.setenv(AZURE_ENV_GPT53_CODEX_KEY, "secret-codex-key")
    monkeypatch.setenv(AZURE_ENV_GPT53_CODEX_DEPLOYMENT, "dep-gpt53-codex")


def test_make_azure_route_from_env_contains_metadata_not_secret(monkeypatch):
    _set_azure_env(monkeypatch)
    route = make_azure_gpt54_mini_route_from_env(request_settings={"temperature": 0})

    assert route["provider_route"] == "openai_api"
    assert route["auth_mode"] == "api_key"
    assert route["model_name"] == "dep-gpt54-mini"
    assert (
        route["api_base"]
        == "https://example-resource.openai.azure.com/openai/deployments/dep-gpt54-mini/chat/completions"
    )
    assert route["request_settings"]["api_key_env_var"] == AZURE_ENV_GPT54_MINI_KEY
    assert route["request_settings"]["pricing_model_id"] == "gpt-5.4-mini"
    assert route["request_settings"]["azure_api_version"] == "2024-12-01-preview"
    assert route["request_settings"]["azure_api_surface"] == "deployment_chat_completions"
    assert route["request_settings_fingerprint"]
    assert "secret-mini-key" not in json.dumps(route, sort_keys=True)


def test_make_azure_codex_route_from_env_uses_v1_responses(monkeypatch):
    _set_azure_env(monkeypatch)
    route = make_azure_gpt53_codex_route_from_env()

    assert route["provider_route"] == "openai_api"
    assert route["auth_mode"] == "api_key"
    assert route["model_name"] == "dep-gpt53-codex"
    assert route["api_base"] == "https://example-resource.openai.azure.com/openai/v1/responses"
    assert route["request_settings"]["api_key_env_var"] == AZURE_ENV_GPT53_CODEX_KEY
    assert route["request_settings"]["pricing_model_id"] == "gpt-5.3-codex"
    assert route["request_settings"]["azure_api_surface"] == "v1_responses"
    assert "azure_api_version" not in route["request_settings"]


def test_azure_client_normalizes_chat_completion_usage_and_tool_calls(monkeypatch):
    route = make_azure_openai_route(
        endpoint="https://example-resource.openai.azure.com",
        deployment="dep-gpt54-mini",
        api_key_env_var=AZURE_ENV_GPT54_MINI_KEY,
        pricing_model_id="gpt-5.4-mini",
        api_version="2024-12-01-preview",
    )
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_KEY, "secret-mini-key")
    seen_request = {}

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        seen_request["url"] = request.full_url
        seen_request["headers"] = {key.lower(): value for key, value in request.header_items()}
        seen_request["payload"] = json.loads(request.data.decode("utf-8"))
        body = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "ready",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "raw_bash",
                                    "arguments": "{\"command\":\"pwd\"}",
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {"cached_tokens": 25},
                "completion_tokens_details": {"reasoning_tokens": 11},
            },
        }
        return _FakeHTTPResponse(200, json.dumps(body).encode("utf-8"))

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = AzureOpenAIAPIKeyModelClient(route=route)
    result = client.complete(
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
        ],
        tools=[
            {
                "name": "raw_bash",
                "description": "run command",
                "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}},
            }
        ],
    )

    assert seen_request["url"].endswith(
        "/openai/deployments/dep-gpt54-mini/chat/completions?api-version=2024-12-01-preview"
    )
    assert seen_request["headers"]["api-key"] == "secret-mini-key"
    assert seen_request["payload"]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    ]
    assert "model" not in seen_request["payload"]
    assert seen_request["payload"]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "raw_bash",
                "description": "run command",
                "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
            },
        }
    ]
    assert result["text"] == "ready"
    assert result["tool_calls"] == [
        {
            "type": "function",
            "id": "call_1",
            "name": "raw_bash",
            "arguments": "{\"command\":\"pwd\"}",
        }
    ]
    assert result["usage"]["input_tokens"] == 100
    assert result["usage"]["cached_input_tokens"] == 25
    assert result["usage"]["output_tokens"] == 20
    assert result["usage"]["total_tokens"] == 120
    assert result["reasoning_token_count"] == 11
    assert result["status"] == "completed"


def test_azure_codex_responses_client_normalizes_text_and_usage(monkeypatch):
    route = make_azure_openai_route(
        endpoint="https://example-resource.openai.azure.com",
        deployment="dep-gpt53-codex",
        api_key_env_var=AZURE_ENV_GPT53_CODEX_KEY,
        pricing_model_id="gpt-5.3-codex",
        api_version="2025-04-01-preview",
    )
    monkeypatch.setenv(AZURE_ENV_GPT53_CODEX_KEY, "secret-codex-key")
    seen_request = {}

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        seen_request["url"] = request.full_url
        seen_request["headers"] = {key.lower(): value for key, value in request.header_items()}
        seen_request["payload"] = json.loads(request.data.decode("utf-8"))
        body = {
            "id": "resp_123",
            "status": "completed",
            "output": [
                {
                    "id": "msg_123",
                    "type": "message",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "OK"}],
                    "role": "assistant",
                }
            ],
            "usage": {
                "input_tokens": 10,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }
        return _FakeHTTPResponse(200, json.dumps(body).encode("utf-8"))

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = AzureOpenAIAPIKeyModelClient(route=route)
    result = client.complete(
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
        ],
        max_output_tokens=16,
    )

    assert seen_request["url"] == "https://example-resource.openai.azure.com/openai/v1/responses"
    assert seen_request["headers"]["api-key"] == "secret-codex-key"
    assert seen_request["payload"]["model"] == "dep-gpt53-codex"
    assert seen_request["payload"]["instructions"] == "system"
    assert seen_request["payload"]["input"] == [{"role": "user", "content": "hello"}]
    assert seen_request["payload"]["store"] is False
    assert result["text"] == "OK"
    assert result["tool_calls"] == []
    assert result["usage"]["input_tokens"] == 10
    assert result["usage"]["cached_input_tokens"] == 0
    assert result["usage"]["output_tokens"] == 5
    assert result["usage"]["total_tokens"] == 15
    assert result["status"] == "completed"


def test_azure_codex_responses_client_normalizes_reasoning_summary_items(monkeypatch):
    route = make_azure_openai_route(
        endpoint="https://example-resource.openai.azure.com",
        deployment="dep-gpt53-codex",
        api_key_env_var=AZURE_ENV_GPT53_CODEX_KEY,
        pricing_model_id="gpt-5.3-codex",
        api_version="2025-04-01-preview",
    )
    monkeypatch.setenv(AZURE_ENV_GPT53_CODEX_KEY, "secret-codex-key")

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        body = {
            "id": "resp_reasoning_summary",
            "status": "completed",
            "output": [
                {
                    "id": "rs_123",
                    "type": "reasoning",
                    "summary": [
                        {"type": "summary_text", "text": "Checked target file before editing."},
                        {"type": "summary_text", "text": "Selected one verifier-compatible patch."},
                    ],
                },
                {
                    "id": "msg_123",
                    "type": "message",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "done"}],
                    "role": "assistant",
                },
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 6,
                "total_tokens": 16,
                "output_tokens_details": {"reasoning_tokens": 4},
            },
        }
        return _FakeHTTPResponse(200, json.dumps(body).encode("utf-8"))

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = AzureOpenAIAPIKeyModelClient(route=route)
    result = client.complete(messages=[{"role": "user", "content": "hello"}], max_output_tokens=16)

    assert result["text"] == "done"
    assert (
        result["reasoning_summary"]
        == "Checked target file before editing.\nSelected one verifier-compatible patch."
    )
    assert result["reasoning_token_count"] == 4
    assert result["provider_reasoning"] == {
        "source": "responses.output.reasoning",
        "reasoning_item_count": 1,
        "summary_count": 2,
        "encrypted_item_count": 0,
    }


def test_azure_codex_responses_client_normalizes_encrypted_reasoning_as_hashed_artifact(monkeypatch):
    route = make_azure_openai_route(
        endpoint="https://example-resource.openai.azure.com",
        deployment="dep-gpt53-codex",
        api_key_env_var=AZURE_ENV_GPT53_CODEX_KEY,
        pricing_model_id="gpt-5.3-codex",
        api_version="2025-04-01-preview",
    )
    monkeypatch.setenv(AZURE_ENV_GPT53_CODEX_KEY, "secret-codex-key")
    encrypted_content = "ENC:" + ("abcd1234" * 120)

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        body = {
            "id": "resp_reasoning_encrypted",
            "status": "completed",
            "output": [
                {
                    "id": "rs_123",
                    "type": "reasoning",
                    "encrypted_content": encrypted_content,
                },
                {
                    "id": "msg_123",
                    "type": "message",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "done"}],
                    "role": "assistant",
                },
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 6,
                "total_tokens": 16,
            },
        }
        return _FakeHTTPResponse(200, json.dumps(body).encode("utf-8"))

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = AzureOpenAIAPIKeyModelClient(route=route)
    result = client.complete(messages=[{"role": "user", "content": "hello"}], max_output_tokens=16)

    artifact = result["reasoning_artifact"]
    assert artifact["type"] == "encrypted_reasoning_continuity"
    assert artifact["encoding"] == "provider_encrypted"
    assert artifact["encrypted_content_char_count"] == len(encrypted_content)
    assert len(artifact["encrypted_content_hashes"]) == 1
    assert encrypted_content not in json.dumps(result, sort_keys=True)


def test_azure_codex_responses_client_normalizes_tool_history_to_function_items(monkeypatch):
    route = make_azure_openai_route(
        endpoint="https://example-resource.openai.azure.com",
        deployment="dep-gpt53-codex",
        api_key_env_var=AZURE_ENV_GPT53_CODEX_KEY,
        pricing_model_id="gpt-5.3-codex",
        api_version="2025-04-01-preview",
    )
    monkeypatch.setenv(AZURE_ENV_GPT53_CODEX_KEY, "secret-codex-key")
    seen_request = {}

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        seen_request["url"] = request.full_url
        seen_request["payload"] = json.loads(request.data.decode("utf-8"))
        body = {
            "id": "resp_456",
            "status": "completed",
            "output": [
                {
                    "id": "msg_456",
                    "type": "message",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "done"}],
                    "role": "assistant",
                }
            ],
            "usage": {
                "input_tokens": 12,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 6,
                "total_tokens": 18,
            },
        }
        return _FakeHTTPResponse(200, json.dumps(body).encode("utf-8"))

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = AzureOpenAIAPIKeyModelClient(route=route)
    result = client.complete(
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "name": "raw_bash",
                        "arguments": "{\"command\":\"pwd\"}",
                    }
                ],
            },
            {
                "role": "tool",
                "name": "raw_bash",
                "tool_call_id": "call_1",
                "content": "raw_bash exit=0\\nstdout:\\n/tmp\\nstderr:",
            },
        ],
        max_output_tokens=16,
    )

    assert seen_request["payload"]["input"] == [
        {"role": "user", "content": "hello"},
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "raw_bash",
            "arguments": "{\"command\":\"pwd\"}",
        },
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "raw_bash exit=0\\nstdout:\\n/tmp\\nstderr:",
        },
    ]
    assert result["text"] == "done"


def test_azure_client_reports_auth_error_when_key_missing(monkeypatch):
    route = make_azure_openai_route(
        endpoint="https://example-resource.openai.azure.com",
        deployment="dep-gpt54-mini",
        api_key_env_var=AZURE_ENV_GPT54_MINI_KEY,
        pricing_model_id="gpt-5.4-mini",
    )
    monkeypatch.delenv(AZURE_ENV_GPT54_MINI_KEY, raising=False)
    client = AzureOpenAIAPIKeyModelClient(route=route)

    with pytest.raises(ModelClientError) as excinfo:
        client.complete(messages=[{"role": "user", "content": "hello"}])
    err = excinfo.value
    assert err.error_kind == "auth_error"
    assert err.details["metadata"]["api_key_env_var"] == AZURE_ENV_GPT54_MINI_KEY


def test_azure_client_http_error_exposes_debug_metadata(monkeypatch):
    route = make_azure_openai_route(
        endpoint="https://example-resource.openai.azure.com",
        deployment="dep-gpt54-mini",
        api_key_env_var=AZURE_ENV_GPT54_MINI_KEY,
        pricing_model_id="gpt-5.4-mini",
    )
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_KEY, "secret-mini-key")

    headers = Message()
    headers["Retry-After"] = "12"
    headers["x-ratelimit-remaining-tokens"] = "0"
    headers["x-request-id"] = "req_123"
    headers["authorization"] = "should-not-leak"

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        raise HTTPError(
            url=request.full_url,
            code=429,
            msg="Too Many Requests",
            hdrs=headers,
            fp=_FakeHTTPResponse(429, b'{"error":{"message":"rate limit"}}'),
        )

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)
    client = AzureOpenAIAPIKeyModelClient(route=route, max_retries=0)

    with pytest.raises(ModelClientError) as excinfo:
        client.complete(messages=[{"role": "user", "content": "hello"}])
    err = excinfo.value
    assert err.status_code == 429
    assert err.error_kind == "http_error"
    assert "rate limit" in (err.response_body or "")
    assert err.details["metadata"]["deployment"] == "dep-gpt54-mini"
    assert err.details["response_headers"]["retry-after"] == "12"
    assert err.details["response_headers"]["x-ratelimit-remaining-tokens"] == "0"
    assert err.details["response_headers"]["x-request-id"] == "req_123"
    assert "authorization" not in err.details["response_headers"]


def test_token_summary_computes_local_azure_cost_from_normalized_usage():
    route = make_azure_openai_route(
        endpoint="https://example-resource.openai.azure.com",
        deployment="dep-gpt54-mini",
        api_key_env_var=AZURE_ENV_GPT54_MINI_KEY,
        pricing_model_id="gpt-5.4-mini",
    )
    summary = _token_and_cost_summary(
        {
            "execution": {
                "steps": [
                    {
                        "completion": {
                            "model_route": route,
                            "usage": {
                                "input_tokens": 1000,
                                "cached_input_tokens": 200,
                                "output_tokens": 200,
                                "total_tokens": 1200,
                                "usd": 999.0,
                            },
                        }
                    }
                ]
            }
        }
    )

    assert summary["input_tokens"] == 1000
    assert summary["cached_input_tokens"] == 200
    assert summary["billable_input_tokens"] == 800
    assert summary["output_tokens"] == 200
    assert summary["total_tokens"] == 1200
    assert summary["pricing_model_ids"] == ["gpt-5.4-mini"]
    assert summary["usd"] == pytest.approx(0.001515, rel=0.0, abs=1e-12)


def test_budget_tracker_emits_warnings_and_hard_cap_block():
    tracker = _init_budget_tracker(planned_run_count=5)
    for index, usd in enumerate((120.0, 95.0, 110.0), start=1):
        _accumulate_budget_progress(
            budget_tracker=tracker,
            run_id=f"run-{index}",
            result_record={"budget_used": {"usd": usd}},
        )
    summary = _budget_summary_from_tracker(tracker)

    assert summary["executed_run_count"] == 3
    assert summary["total_usd"] == pytest.approx(325.0, rel=0.0, abs=1e-12)
    assert [event["threshold_usd"] for event in summary["warnings"]] == [100.0, 200.0, 250.0]
    assert summary["hard_cap_reached"] is True
    assert summary["status"] == "blocked_non_promotable"
    assert summary["hard_cap_trigger_run_id"] == "run-3"


def test_recommendation_is_forced_bound_when_budget_hard_cap_reached():
    recommendation = _build_recommendation_draft(
        {
            "batch_id": "packet04-budget-test",
            "variant_ids": ["v1"],
            "fixed_invariants": {"comparator_variant_id": "sc_b_01"},
        },
        [
            {
                "variant_id": "v1",
                "run_id": "run-1",
                "score_summary": {"final_verdict": "pass"},
                "budget_used": {"estimated_tokens": 100, "usd": 325.0},
            }
        ],
        budget_summary={
            "hard_cap_reached": True,
            "status": "blocked_non_promotable",
            "warnings": [],
        },
    )

    assert recommendation["batch_status"] == "blocked_non_promotable"
    assert recommendation["candidate_actions"][0]["proposed_status"] == "bound"
    assert "hard cap" in recommendation["candidate_actions"][0]["rationale"]


def test_route_resolution_supports_packet04_azure_screening_and_promotion_tiers(monkeypatch):
    _set_azure_env(monkeypatch)
    resolved_route = {
        "execution_mode": "one_shot_batchable",
        "model_tier_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
    }
    batch_model_policy = {
        "screening_default": "azure:gpt-5.4-mini",
        "screening_fallback": "azure:gpt-5.4-mini",
        "promotion_tier": "azure:gpt-5.3-codex",
    }

    screening_route = resolve_model_route_for_route(
        resolved_route,
        model_policy_override=batch_model_policy,
        model_tier_selector="screening_default",
    )
    promotion_route = resolve_model_route_for_route(
        resolved_route,
        model_policy_override=batch_model_policy,
        model_tier_selector="promotion_tier",
    )

    assert screening_route["provider_route"] == "openai_api"
    assert screening_route["request_settings"]["pricing_model_id"] == "gpt-5.4-mini"
    assert screening_route["request_settings"]["api_key_env_var"] == AZURE_ENV_GPT54_MINI_KEY
    assert screening_route["request_settings"]["azure_api_surface"] == "deployment_chat_completions"
    assert promotion_route["provider_route"] == "openai_api"
    assert promotion_route["request_settings"]["pricing_model_id"] == "gpt-5.3-codex"
    assert promotion_route["request_settings"]["api_key_env_var"] == AZURE_ENV_GPT53_CODEX_KEY
    assert promotion_route["request_settings"]["azure_api_surface"] == "v1_responses"


def test_model_tier_selector_allows_packet04_promotion_override():
    selector = _resolve_model_tier_selector({"fixed_invariants": {"model_tier_selector": "promotion_tier"}})
    assert selector == "promotion_tier"

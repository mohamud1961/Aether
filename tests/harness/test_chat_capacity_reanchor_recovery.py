from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from aether.model_hooks import ModelHooks
from aether.model_profile import GLM_RESEARCH_PROFILE
from aether.providers.chat_model import (
    ChatContextCapacityError,
    ChatCompletionsModelCallable,
    _capacity_reanchor_recovery_message,
    _recent_complete_tool_exchanges,
    make_chat_completions_callable,
)
from aether.runtime_ir import ACTION_SCHEMA


def _tool_response(call_id: str, path: str, *, reasoning: str = "") -> dict:
    return {
        "choices": [{
            "index": 0,
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": json.dumps({"arguments": {"path": path}}),
                    },
                }],
                "reasoning_content": reasoning,
            },
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
    }


class _Transport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        return self.responses.pop(0)


class _CapacityPacer:
    def __init__(self, token_limit: int):
        self.token_limit = token_limit
        self.window_s = 60.0

    @staticmethod
    def approximate_request_tokens(request_bytes: int, max_output_tokens: int) -> int:
        return (int(request_bytes) + 3) // 4 + int(max_output_tokens)

    def admit(self, *, estimated_tokens: int):
        return {
            "throughput_token_limit": self.token_limit,
            "throughput_window_s": self.window_s,
            "throughput_estimated_tokens": int(estimated_tokens),
            "throughput_wait_s": 0.0,
            "throughput_spacing_s": 0.0,
            "throughput_rolling_wait_s": 0.0,
            "throughput_active_reserved_tokens": int(estimated_tokens),
            "throughput_single_request_admission": "provider_authoritative",
        }

    def reconcile_success(self, *, input_tokens, requested_output_tokens, output_tokens=None):
        return {"throughput_usage_reconciled": True}

    def note_rate_limit(self):
        pass


def _evidence_row(
    receipt_id: str,
    path: str,
    excerpt: str,
    *,
    step: int,
    currentness: str,
) -> dict:
    return {
        "receipt_id": receipt_id,
        "evidence_ref": "evidence:" + receipt_id[-16:].replace(":", "0")[-16:],
        "evidence_type": "read_file",
        "step": step,
        "success": True,
        "completion_evidence_eligible": True,
        "currentness": currentness,
        "bounded_view": {
            "receipt_id": receipt_id,
            "step": step,
            "kind": "read_file",
            "success": True,
            "summary": f"read {path}",
            "path": path,
            "excerpt": excerpt,
        },
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": f"receipt:{receipt_id}",
            "sha256": "a" * 64,
            "bytes": len(excerpt),
        },
    }


def _packet(
    *,
    latest: dict,
    evidence: list[dict],
    generation: int = 0,
) -> str:
    payload = {
        "latest_primary_result": {
            "status": "succeeded",
            "action_kind": "read_file",
            "outcome_receipts": [latest],
        },
        "evidence_index": evidence,
        "task_state_generation": generation,
    }
    return "[context_packet]\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"))


def test_recovery_selects_newest_distinct_observations_and_revalidates_currentness() -> None:
    old_a = _evidence_row(
        "step-0:persistent-old:read", "workspace/a.txt", "old-a",
        step=0, currentness="latest_primary_result",
    )
    b = _evidence_row(
        "step-1:persistent-b:read", "workspace/b.txt", "body-b",
        step=1, currentness="latest_primary_result",
    )
    new_a = _evidence_row(
        "step-2:persistent-new:read", "workspace/a.txt", "new-a",
        step=2, currentness="latest_primary_result",
    )
    history = [
        {"role": "tool", "tool_call_id": "c0", "content": _packet(latest=old_a, evidence=[old_a])},
        {"role": "tool", "tool_call_id": "c1", "content": _packet(latest=b, evidence=[b, old_a])},
        {"role": "tool", "tool_call_id": "c2", "content": _packet(latest=new_a, evidence=[new_a, b, old_a])},
    ]
    fresh_new_a = {**new_a, "currentness": "historical_task_evidence"}
    fresh_b = {**b, "currentness": "historical_task_evidence"}
    fresh = [
        {"role": "system", "content": "prefix"},
        {"role": "system", "content": _packet(
            latest=_evidence_row(
                "step-3:persistent-current:read", "workspace/current.txt", "current",
                step=3, currentness="latest_primary_result",
            ),
            evidence=[
                _evidence_row(
                    "step-3:persistent-current:read", "workspace/current.txt", "current",
                    step=3, currentness="latest_primary_result",
                ),
                fresh_new_a,
                fresh_b,
            ],
            generation=4,
        )},
    ]

    message, meta = _capacity_reanchor_recovery_message(history, fresh)

    assert message is not None
    payload = json.loads(message["content"].split("\n", 1)[1])
    assert meta["selected_count"] == 2
    assert [row["receipt_id"] for row in payload["items"]] == [
        new_a["receipt_id"], b["receipt_id"],
    ]
    assert [row["bounded_view"]["excerpt"] for row in payload["items"]] == [
        "new-a", "body-b",
    ]
    assert all(row["currentness_at_reanchor"] == "historical_task_evidence" for row in payload["items"])
    assert payload["historical_results_are_current_state"] is False
    assert payload["task_state_generation_at_reanchor"] == 4
    assert "old-a" not in message["content"]


def test_recovery_skips_missing_and_oversized_observations_without_summarizing() -> None:
    missing = _evidence_row(
        "step-0:persistent-missing:read", "workspace/missing.txt", "secret-old",
        step=0, currentness="latest_primary_result",
    )
    huge = _evidence_row(
        "step-1:persistent-huge:read", "workspace/huge.txt", "x" * 6000,
        step=1, currentness="latest_primary_result",
    )
    small = _evidence_row(
        "step-2:persistent-small:read", "workspace/small.txt", "small-body",
        step=2, currentness="latest_primary_result",
    )
    history = [
        {"role": "tool", "tool_call_id": "c0", "content": _packet(latest=missing, evidence=[missing])},
        {"role": "tool", "tool_call_id": "c1", "content": _packet(latest=huge, evidence=[huge])},
        {"role": "tool", "tool_call_id": "c2", "content": _packet(latest=small, evidence=[small])},
    ]
    current = _evidence_row(
        "step-3:persistent-current:read", "workspace/current.txt", "current",
        step=3, currentness="latest_primary_result",
    )
    fresh = [
        {"role": "system", "content": "prefix"},
        {"role": "system", "content": _packet(
            latest=current,
            evidence=[
                current,
                {**small, "currentness": "historical_task_evidence"},
                {**huge, "currentness": "historical_task_evidence"},
            ],
        )},
    ]

    message, meta = _capacity_reanchor_recovery_message(history, fresh)

    assert message is not None
    payload = json.loads(message["content"].split("\n", 1)[1])
    assert [row["receipt_id"] for row in payload["items"]] == [small["receipt_id"]]
    assert meta["skipped_missing_current_count"] == 1
    assert meta["skipped_oversize_count"] == 1
    assert "secret-old" not in message["content"]
    assert "x" * 100 not in message["content"]


def test_enabled_capacity_reanchor_recovers_prior_observation_and_persists_segment() -> None:
    responses = [
        _tool_response("call-1", "/tmp/one", reasoning="first-" + "r" * 20_000),
        _tool_response("call-2", "/tmp/two", reasoning="second-" + "s" * 160_000),
        _tool_response("call-3", "/tmp/three", reasoning="third"),
        _tool_response("call-4", "/tmp/four", reasoning="fourth"),
    ]
    transport = _Transport(*responses)
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=_CapacityPacer(token_limit=30_000),  # type: ignore[arg-type]
        capacity_reanchor_recovery_mode="recent_observations_v1",
    )
    hooks = ModelHooks(
        model,
        lambda _messages, **_kwargs: "{}",
        run_id="run-recovery",
        task_id="task-recovery",
        solver_max_output_tokens=400,
    )
    compiled = SimpleNamespace(
        action_schema=ACTION_SCHEMA,
        config_realization={},
        selected_capability_ids=lambda: set(),
    )

    r1 = _evidence_row(
        "step-0:persistent-r1:read", "workspace/a.txt", "DECISIVE_A",
        step=0, currentness="latest_primary_result",
    )
    r2 = _evidence_row(
        "step-1:persistent-r2:read", "workspace/b.txt", "DECISIVE_B",
        step=1, currentness="latest_primary_result",
    )
    r3 = _evidence_row(
        "step-2:persistent-r3:read", "workspace/c.txt", "DECISIVE_C",
        step=2, currentness="latest_primary_result",
    )
    r4 = _evidence_row(
        "step-3:persistent-r4:read", "workspace/d.txt", "DECISIVE_D",
        step=3, currentness="latest_primary_result",
    )

    messages1 = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": _packet(latest=r1, evidence=[r1])},
    ]
    messages2 = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": _packet(
            latest=r1,
            evidence=[{**r1, "currentness": "latest_primary_result"}],
        )},
    ]
    messages3 = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": _packet(
            latest=r2,
            evidence=[
                r2,
                {**r1, "currentness": "historical_task_evidence"},
            ],
            generation=1,
        )},
    ]
    messages4 = [
        {"role": "system", "content": "immutable prefix"},
        {"role": "system", "content": _packet(
            latest=r3,
            evidence=[
                r3,
                {**r2, "currentness": "historical_task_evidence"},
                {**r1, "currentness": "historical_task_evidence"},
            ],
            generation=2,
        )},
    ]

    hooks.solve(messages1, compiled)
    hooks.solve(messages2, compiled)
    hooks.solve(messages3, compiled)
    hooks.solve(messages4, compiled)

    # Call 3 is the capacity boundary caused by call 2's giant reasoning suffix.
    request3 = transport.requests[2]["messages"]
    recovery3 = [
        row for row in request3
        if isinstance(row.get("content"), str)
        and row["content"].startswith("[continuity_reanchor_observations]\n")
    ]
    assert len(recovery3) == 1
    recovered = json.loads(recovery3[0]["content"].split("\n", 1)[1])
    assert [row["receipt_id"] for row in recovered["items"]] == [r1["receipt_id"]]
    assert recovered["items"][0]["bounded_view"]["excerpt"] == "DECISIVE_A"
    assert recovered["items"][0]["currentness_at_reanchor"] == "historical_task_evidence"
    assert "first-" not in recovery3[0]["content"]
    assert "second-" not in recovery3[0]["content"]

    # The bounded recovery system message survives in the new explicit segment.
    request4 = transport.requests[3]["messages"]
    assert any(
        isinstance(row.get("content"), str)
        and row["content"].startswith("[continuity_reanchor_observations]\n")
        for row in request4
    )

    rows = model.drain_telemetry()
    assert rows[2]["throughput_capacity_reanchor"] is True
    recovery_meta = rows[2]["throughput_capacity_reanchor_recovery"]
    assert recovery_meta["admission"] == "included"
    assert recovery_meta["selected_count"] == 1
    assert recovery_meta["estimated_tokens_with_recovery"] <= 30_000


def test_recovery_mode_is_default_off() -> None:
    model = ChatCompletionsModelCallable(
        transport=_Transport(_tool_response("call-x", "/tmp/x")),
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )
    assert model._capacity_reanchor_recovery_mode == "off"


def test_enabled_recovery_is_profile_bound_and_changes_only_enabled_treatment_hash() -> None:
    assert (
        GLM_RESEARCH_PROFILE.manifest()["chat_capacity_reanchor_recovery_mode"]
        == "recent_exchanges_v1"
    )
    disabled = replace(
        GLM_RESEARCH_PROFILE,
        chat_capacity_reanchor_recovery_mode="off",
    )
    assert "chat_capacity_reanchor_recovery_mode" not in disabled.manifest()
    assert disabled.sha256() != GLM_RESEARCH_PROFILE.sha256()

    alternate = replace(
        GLM_RESEARCH_PROFILE,
        chat_capacity_reanchor_recovery_mode="recent_observations_v1",
    )
    assert alternate.sha256() != GLM_RESEARCH_PROFILE.sha256()


def test_factory_propagates_profile_bound_recovery_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aether.providers.chat_model as chat_model

    enabled = replace(
        GLM_RESEARCH_PROFILE,
        chat_capacity_reanchor_recovery_mode="recent_observations_v1",
    )
    monkeypatch.setattr(chat_model, "require_provider_authorization", lambda _profile: None)
    monkeypatch.setenv(enabled.endpoint_env, "https://resource.openai.azure.com")
    monkeypatch.setenv(enabled.key_env, "test-key")
    monkeypatch.setenv(enabled.deployment_env, enabled.model_id)
    monkeypatch.delenv("AETHER_PROVIDER_TPM_LIMIT", raising=False)

    class Client:
        chat = SimpleNamespace(completions=_Transport(_tool_response("call-factory", "/tmp/x")))

    model = make_chat_completions_callable(
        profile=enabled,
        client_factory=lambda **_kwargs: Client(),
    )
    assert model._capacity_reanchor_recovery_mode == "recent_observations_v1"


def test_invalid_recovery_mode_fails_before_any_provider_call() -> None:
    transport = _Transport(_tool_response("call-invalid", "/tmp/x"))
    with pytest.raises(ValueError, match="unsupported Chat capacity reanchor recovery mode"):
        ChatCompletionsModelCallable(
            transport=transport,
            deployment="glm-test",
            role="solver",
            native_persistent_tools=True,
            capacity_reanchor_recovery_mode="semantic_magic",
        )
    assert transport.requests == []


def _assistant_tool_message(call_id: str, *, reasoning: str = "") -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({"arguments": {"path": f"/tmp/{call_id}"}}),
            },
        }],
        "reasoning_content": reasoning,
    }


def _tool_result_message(call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def test_recent_exchange_selector_requires_and_preserves_exact_last_four_pairs() -> None:
    messages = [{"role": "system", "content": "prefix"}]
    for index in range(1, 6):
        cid = f"call-{index}"
        messages += [
            _assistant_tool_message(cid, reasoning=f"reason-{index}"),
            _tool_result_message(cid, f"result-{index}"),
        ]

    selected = _recent_complete_tool_exchanges(messages, count=4)

    assert len(selected) == 8
    assert [selected[i]["tool_calls"][0]["id"] for i in range(0, 8, 2)] == [
        "call-2", "call-3", "call-4", "call-5",
    ]
    assert [selected[i]["content"] for i in range(1, 8, 2)] == [
        "result-2", "result-3", "result-4", "result-5",
    ]
    assert selected[0]["reasoning_content"] == "reason-2"
    assert _recent_complete_tool_exchanges(messages[:7], count=4) == []


def test_recent_exchange_reanchor_keeps_exact_four_complete_pairs() -> None:
    transport = _Transport(_tool_response("call-7", "/tmp/seven", reasoning="new"))
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=_CapacityPacer(token_limit=30_000),  # type: ignore[arg-type]
        capacity_reanchor_recovery_mode="recent_exchanges_v1",
    )
    key = ("run-exchange", "task-exchange")
    history = []
    # Make only the two oldest exchanges huge so six exchanges overflow while
    # the exact trailing four fit.
    for index in range(1, 7):
        cid = f"call-{index}"
        reasoning = ("x" * 70_000) if index <= 2 else f"reason-{index}"
        history.append(_assistant_tool_message(cid, reasoning=reasoning))
        if index < 6:
            history.append(_tool_result_message(cid, f"result-{index}"))
            if index == 3:
                history.append({
                    "role": "user",
                    "content": "[solver_protocol_observation] preserve this feedback separately",
                })
    model._continuity_states[key] = {
        "call_id": "call-6",
        "history": history,
        "request_transcript": [],
    }

    fresh = [
        {"role": "system", "content": "immutable-prefix"},
        {"role": "system", "content": "CURRENT_RESULT_6"},
    ]
    result = model.call_with_telemetry_scope(
        fresh,
        max_output_tokens=400,
        run_id=key[0],
        task_id=key[1],
        call_generation=7,
    )
    assert json.loads(result)["action"]["kind"] == "read_file"
    assert len(transport.requests) == 1

    sent = transport.requests[0]["messages"]
    assert sent[0] == fresh[0]
    assert len(sent) == 1 + 9
    assert [row["tool_calls"][0]["id"] for row in sent if row.get("role") == "assistant"] == [
        "call-3", "call-4", "call-5", "call-6",
    ]
    assert any(row.get("role") == "user" for row in sent)
    assert sent[-1] == {
        "role": "tool",
        "tool_call_id": "call-6",
        "content": "CURRENT_RESULT_6",
    }
    assert not any("call-1" in json.dumps(row) or "call-2" in json.dumps(row) for row in sent)

    telemetry = model.drain_telemetry()
    attempt = next(row for row in telemetry if row.get("event_kind") == "provider_attempt")
    recovery = attempt["throughput_capacity_reanchor_recovery"]
    assert recovery["admission"] == "included_exact_four"
    assert recovery["selected_exchange_count"] == 4
    assert recovery["exact_messages"] is True

    model.commit_pending_response(run_id=key[0], task_id=key[1])
    committed = model._continuity_states[key]["history"]
    # Four exact pairs survive into the new segment, followed by the new assistant.
    assert len(committed) == 10
    assert committed[:9] == sent[1:]


def test_recent_exchange_reanchor_with_too_few_pairs_fails_closed() -> None:
    transport = _Transport(_tool_response("unused", "/tmp/unused"))
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=_CapacityPacer(token_limit=30_000),  # type: ignore[arg-type]
        capacity_reanchor_recovery_mode="recent_exchanges_v1",
    )
    key = ("run-too-few", "task-too-few")
    history = []
    for index in range(1, 3):
        cid = f"call-{index}"
        history.extend((_assistant_tool_message(cid, reasoning="z" * 70_000), _tool_result_message(cid, f"result-{index}")))
        if index == 2:
            history.append({"role": "user", "content": "inert correction feedback"})
    history.append(_assistant_tool_message("call-3"))
    model._continuity_states[key] = {
        "call_id": "call-3",
        "history": history,
        "request_transcript": [],
    }

    with pytest.raises(ChatContextCapacityError, match=r"^harness_context_capacity:"):
        model.call_with_telemetry_scope(
            [
                {"role": "system", "content": "immutable-prefix"},
                {"role": "system", "content": "CURRENT_RESULT_4"},
            ],
            max_output_tokens=400,
            run_id=key[0],
            task_id=key[1],
            call_generation=5,
        )
    assert transport.requests == []
    assert model._continuity_states[key]["call_id"] == "call-3"
    assert len(model._continuity_states[key]["history"]) == len(history)
    attempt = next(row for row in model.drain_telemetry() if row.get("event_kind") == "provider_attempt")
    assert attempt["throughput_capacity_reanchor_recovery"]["admission"] == "unavailable_exact_four"


def test_recent_exchange_reanchor_fails_instead_of_shedding_below_four() -> None:
    transport = _Transport(_tool_response("unused", "/tmp/unused"))
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=_CapacityPacer(token_limit=8_000),  # type: ignore[arg-type]
        capacity_reanchor_recovery_mode="recent_exchanges_v1",
    )
    key = ("run-overflow", "task-overflow")
    history = []
    for index in range(1, 5):
        cid = f"call-{index}"
        history.append(_assistant_tool_message(cid, reasoning="z" * 20_000))
        if index < 4:
            history.append(_tool_result_message(cid, f"result-{index}"))
    model._continuity_states[key] = {
        "call_id": "call-4",
        "history": history,
        "request_transcript": [],
    }

    with pytest.raises(
        ChatContextCapacityError,
        match=r"^harness_context_capacity:",
    ):
        model.call_with_telemetry_scope(
            [
                {"role": "system", "content": "prefix"},
                {"role": "system", "content": "CURRENT_RESULT_4"},
            ],
            max_output_tokens=400,
            run_id=key[0],
            task_id=key[1],
            call_generation=5,
        )

    assert transport.requests == []
    telemetry = model.drain_telemetry()
    attempt = next(row for row in telemetry if row.get("event_kind") == "provider_attempt")
    recovery = attempt["throughput_capacity_reanchor_recovery"]
    assert recovery["admission"] == "rejected_exact_four_over_capacity"
    assert recovery["selected_exchange_count"] == 4

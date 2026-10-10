from __future__ import annotations

import copy
import json

import pytest

from aether.providers.chat_model import (
    ChatCompletionsModelCallable,
    ChatModelError,
)


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        return self.responses.pop(0)


def _tool_response(call_id: str, path: str) -> dict:
    return {
        "model": "glm-test",
        "choices": [{
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
                "reasoning_content": "provider-visible reasoning field",
            },
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _solver(transport: FakeTransport) -> ChatCompletionsModelCallable:
    return ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )


def _call(model: ChatCompletionsModelCallable, content: str) -> str:
    return model.call_with_telemetry_scope(
        [
            {"role": "system", "content": "immutable"},
            {"role": "system", "content": content},
        ],
        max_output_tokens=64,
        run_id="run-restart",
        task_id="task-restart",
    )


def test_committed_chat_continuity_round_trips_across_new_model_instance() -> None:
    first_transport = FakeTransport(_tool_response("call-1", "/tmp/one"))
    first = _solver(first_transport)
    _call(first, "first observation")
    first.commit_pending_response(run_id="run-restart", task_id="task-restart")
    snapshot = first.export_continuity_scope(
        run_id="run-restart", task_id="task-restart"
    )
    assert snapshot is not None
    encoded = json.loads(json.dumps(snapshot))

    second_transport = FakeTransport(_tool_response("call-2", "/tmp/two"))
    resumed = _solver(second_transport)
    resumed.import_continuity_scope(
        encoded, run_id="run-restart", task_id="task-restart"
    )
    _call(resumed, "tool result after restart")

    sent = second_transport.requests[0]["messages"]
    assert [row["role"] for row in sent] == ["system", "assistant", "tool"]
    assert sent[1]["tool_calls"][0]["id"] == "call-1"
    assert sent[1]["reasoning_content"] == "provider-visible reasoning field"
    assert sent[2] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "tool result after restart",
    }
    events = resumed.drain_continuity_admission_telemetry()
    assert any(row["event_kind"] == "chat_continuity_restart_restore" for row in events)


def test_export_refuses_pending_unadmitted_provider_response() -> None:
    model = _solver(FakeTransport(_tool_response("call-1", "/tmp/one")))
    _call(model, "first")
    with pytest.raises(ChatModelError, match="pending_candidate_requires_admission"):
        model.export_continuity_scope(
            run_id="run-restart", task_id="task-restart"
        )


def test_import_rejects_tampered_snapshot_hash() -> None:
    model = _solver(FakeTransport(_tool_response("call-1", "/tmp/one")))
    _call(model, "first")
    model.commit_pending_response(run_id="run-restart", task_id="task-restart")
    snapshot = model.export_continuity_scope(
        run_id="run-restart", task_id="task-restart"
    )
    assert snapshot is not None
    tampered = copy.deepcopy(snapshot)
    tampered["history"][0]["reasoning_content"] = "tampered"

    resumed = _solver(FakeTransport())
    with pytest.raises(ChatModelError, match="snapshot_hash_mismatch"):
        resumed.import_continuity_scope(
            tampered, run_id="run-restart", task_id="task-restart"
        )


def test_import_rejects_wrong_scope_or_deployment_even_with_valid_hash() -> None:
    model = _solver(FakeTransport(_tool_response("call-1", "/tmp/one")))
    _call(model, "first")
    model.commit_pending_response(run_id="run-restart", task_id="task-restart")
    snapshot = model.export_continuity_scope(
        run_id="run-restart", task_id="task-restart"
    )
    assert snapshot is not None

    resumed = _solver(FakeTransport())
    with pytest.raises(ChatModelError, match="snapshot_run_id_mismatch"):
        resumed.import_continuity_scope(
            snapshot, run_id="different-run", task_id="task-restart"
        )

    other = ChatCompletionsModelCallable(
        transport=FakeTransport(),
        deployment="different-deployment",
        role="solver",
        native_persistent_tools=True,
    )
    with pytest.raises(ChatModelError, match="snapshot_deployment_mismatch"):
        other.import_continuity_scope(
            snapshot, run_id="run-restart", task_id="task-restart"
        )


def test_import_refuses_overwriting_existing_scope() -> None:
    first = _solver(FakeTransport(_tool_response("call-1", "/tmp/one")))
    _call(first, "first")
    first.commit_pending_response(run_id="run-restart", task_id="task-restart")
    snapshot = first.export_continuity_scope(
        run_id="run-restart", task_id="task-restart"
    )
    assert snapshot is not None

    resumed = _solver(FakeTransport(_tool_response("call-x", "/tmp/x")))
    _call(resumed, "existing")
    resumed.commit_pending_response(run_id="run-restart", task_id="task-restart")
    with pytest.raises(ChatModelError, match="scope_already_present"):
        resumed.import_continuity_scope(
            snapshot, run_id="run-restart", task_id="task-restart"
        )


def test_export_none_for_scope_without_committed_history() -> None:
    model = _solver(FakeTransport())
    assert model.export_continuity_scope(
        run_id="run-restart", task_id="task-restart"
    ) is None

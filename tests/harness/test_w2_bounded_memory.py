from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from aether.glm_model_view import project_context_packet
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_runtime import SOLVER_WORKING_CONTEXT_MODES
from aether.providers.chat_model import (
    ChatCompletionsModelCallable,
    ChatModelOutputError,
)
from aether.thin_context import build_factual_read_index


class FakeTransport:
    def __init__(self, *responses: dict[str, Any]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> dict[str, Any]:
        self.requests.append(json.loads(json.dumps(request)))
        return self.responses.pop(0)


def _tool_response(call_id: str, *, notes: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"arguments": {"path": "/tmp/input"}}
    if notes is not None:
        payload["working_notes"] = notes
    return {
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
                        "arguments": json.dumps(payload, sort_keys=True),
                    },
                }],
                "reasoning_content": f"reasoning-{call_id}",
            },
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


def _messages(step: int) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "[raw_user_task]\nRead the file."},
        {"role": "system", "content": "[context_packet]\n" + json.dumps(
            {"step": step}, sort_keys=True, separators=(",", ":"),
        )},
    ]


def test_factual_read_index_contains_only_mechanical_observation_metadata() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-1:read",
        step=1,
        kind="read_file",
        success=True,
        summary="DO NOT LEAK THIS SUMMARY",
        payload={
            "path": "FORMAT.md",
            "resolved_path": "/app/workspace/FORMAT.md",
            "content": "SECRET CONTENT MUST NOT ENTER THE INDEX",
            "excerpt": "SECRET EXCERPT",
            "content_sha256": "a" * 64,
            "bytes": 123,
            "file_handle": "file:FORMAT.md",
        },
    ))
    ledger.record(Receipt(
        receipt_id="step-2:cmd",
        step=2,
        kind="run_command",
        success=False,
        summary="DO NOT LEAK COMMAND SUMMARY",
        payload={
            "command": "python3 verify.py",
            "stdout": "SECRET STDOUT",
            "stderr": "SECRET STDERR",
            "stdout_handle": "2:cmd:stdout",
            "stderr_handle": "2:cmd:stderr",
            "stdout_bytes": 20,
            "stderr_bytes": 30,
            "exit_code": 1,
        },
    ))
    # Mutations are deliberately not indexed by R1.
    ledger.record(Receipt(
        receipt_id="step-3:write",
        step=3,
        kind="write_file",
        success=True,
        summary="write summary",
        payload={"path": "solution.py", "content": "print('x')", "bytes": 10},
    ))
    ledger.record(Receipt(
        receipt_id="step-1b:read",
        step=4,
        kind="read_file",
        success=True,
        summary="ANOTHER SUMMARY THAT MUST NOT LEAK",
        payload={
            "path": "FORMAT.md",
            "resolved_path": "/app/workspace/FORMAT.md",
            "content": "NEW SECRET CONTENT",
            "content_sha256": "c" * 64,
            "bytes": 124,
            "file_handle": "file:FORMAT.md",
        },
    ))

    first = build_factual_read_index(ledger)
    second = build_factual_read_index(ledger)
    assert first == second
    assert first["schema"] == "aether.factual_read_index.v1"
    assert [row["tool"] for row in first["entries"]] == ["read_file", "run_command"]

    encoded = json.dumps(first, sort_keys=True, separators=(",", ":"))
    assert "DO NOT LEAK" not in encoded
    assert "SECRET CONTENT" not in encoded
    assert "SECRET EXCERPT" not in encoded
    assert "SECRET STDOUT" not in encoded
    assert "SECRET STDERR" not in encoded
    assert "summary" not in encoded
    assert "content" not in first["entries"][0]
    assert first["entries"][0]["path"] == "FORMAT.md"
    assert first["entries"][0]["content_sha256"] == "c" * 64
    assert first["entries"][0]["receipt_handle"] == "receipt:step-1b:read"
    assert first["entries"][0]["first_step"] == 1
    assert first["entries"][0]["last_step"] == 4
    assert first["entries"][0]["observation_count"] == 2
    assert first["entries"][1]["command"] == "python3 verify.py"
    assert first["entries"][1]["stdout_handle"] == "2:cmd:stdout"
    assert len(first["entries"][0]["observation_sha256"]) == 64


def test_tool_notes_mode_requires_field_and_strips_it_before_action_execution() -> None:
    transport = FakeTransport(_tool_response("call-1", notes=None))
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )
    model.set_reality_transport_mode("latest_exchange_v1", run_id="run", task_id="task")
    model.set_solver_working_context_mode("tool_notes_v1", run_id="run", task_id="task")

    tools = model._tools_for_scope(("run", "task"))
    assert tools
    for tool in tools:
        params = tool["function"]["parameters"]
        assert "working_notes" in params["required"]
        assert params["properties"]["working_notes"]["pattern"] == r"\S"

    with pytest.raises(ChatModelOutputError, match="solver_working_notes_missing"):
        model.call_with_telemetry_scope(
            _messages(0),
            max_output_tokens=64,
            run_id="run",
            task_id="task",
        )


def test_tool_notes_are_verbatim_in_telemetry_and_latest_exchange_but_not_action() -> None:
    note1 = "Checked FORMAT.md; next inspect header bytes."
    note2 = "Header bytes observed; now compare offsets."
    transport = FakeTransport(
        _tool_response("call-1", notes=note1),
        _tool_response("call-2", notes=note2),
    )
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )
    model.set_reality_transport_mode("latest_exchange_v1", run_id="run", task_id="task")
    model.set_solver_working_context_mode("tool_notes_v1", run_id="run", task_id="task")

    first = model.call_with_telemetry_scope(
        _messages(0), max_output_tokens=64, run_id="run", task_id="task",
    )
    first_turn = json.loads(first)
    assert first_turn["action"]["arguments"] == {"path": "/tmp/input"}
    assert "working_notes" not in first_turn["action"]["arguments"]
    model.commit_pending_response(run_id="run", task_id="task")

    second = model.call_with_telemetry_scope(
        _messages(1), max_output_tokens=64, run_id="run", task_id="task",
    )
    second_turn = json.loads(second)
    assert second_turn["action"]["arguments"] == {"path": "/tmp/input"}

    previous_assistant = [
        row for row in transport.requests[1]["messages"]
        if row.get("role") == "assistant"
    ]
    assert len(previous_assistant) == 1
    replayed_args = json.loads(
        previous_assistant[0]["tool_calls"][0]["function"]["arguments"]
    )
    assert replayed_args["working_notes"] == note1

    telemetry = model.drain_telemetry()
    completed = [row for row in telemetry if row.get("status") == "completed"]
    assert completed[0]["solver_working_notes"] == note1
    assert completed[0]["solver_working_notes_utf8_bytes"] == len(note1.encode("utf-8"))
    assert completed[0]["solver_working_notes_sha256"] == hashlib.sha256(
        note1.encode("utf-8")
    ).hexdigest()
    assert completed[1]["solver_working_notes"] == note2


def test_read_index_survives_hygiene_lean_projection_verbatim() -> None:
    packet = {
        "read_index": {
            "schema": "aether.factual_read_index.v1",
            "entries": [{
                "tool": "read_file",
                "path": "FORMAT.md",
                "content_sha256": "b" * 64,
                "receipt_handle": "receipt:step-1:read",
                "step": 1,
                "success": True,
            }],
        },
        "budgets": {"used_kernel_steps": 1},
    }
    projected = project_context_packet(packet, "hygiene_lean_v1")
    assert projected["read_index"] == packet["read_index"]


@pytest.mark.parametrize("mode", ["tool_notes_v1", "tool_notes_grounded_v1", "read_index_tool_notes_v1"])
def test_all_tool_note_modes_require_working_notes(mode: str) -> None:
    model = ChatCompletionsModelCallable(
        transport=FakeTransport(_tool_response("call-1", notes="keep this")),
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )
    model.set_solver_working_context_mode(mode, run_id="run", task_id="task")
    tools = model._tools_for_scope(("run", "task"))
    assert tools
    assert all("working_notes" in tool["function"]["parameters"]["required"] for tool in tools)


def test_grounded_tool_notes_add_only_memory_quality_guidance() -> None:
    model = ChatCompletionsModelCallable(
        transport=FakeTransport(_tool_response("call-1", notes="keep this")),
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
    )
    model.set_solver_working_context_mode("tool_notes_v1", run_id="run", task_id="task")
    plain = model._tools_for_scope(("run", "task"))
    plain_schema = plain[0]["function"]["parameters"]["properties"]["working_notes"]
    assert "description" not in plain_schema

    model.set_solver_working_context_mode(
        "tool_notes_grounded_v1", run_id="run", task_id="task"
    )
    grounded = model._tools_for_scope(("run", "task"))
    grounded_schema = grounded[0]["function"]["parameters"]["properties"]["working_notes"]
    description = grounded_schema["description"]
    assert "verified facts" in description
    assert "receipt/file/output handle" in description
    assert "hypotheses explicitly separate" in description
    assert "failed approaches" in description
    assert "Update or retract" in description
    assert "self-authored test" in description
    assert grounded[0]["function"]["name"] == plain[0]["function"]["name"]
    assert (
        set(grounded[0]["function"]["parameters"]["required"])
        == set(plain[0]["function"]["parameters"]["required"])
    )


def test_grounded_tool_notes_mode_is_in_canonical_runtime_allowlist() -> None:
    assert "tool_notes_grounded_v1" in SOLVER_WORKING_CONTEXT_MODES

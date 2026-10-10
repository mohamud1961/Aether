from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

import pytest

from aether.execution import MemoryExecutor
from aether.model_hooks import ModelHooks
from aether.providers.chat_model import ChatCompletionsModelCallable, ChatModelError
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.thin_loop import ThinLoopConfig, run_thin_loop


class _Transport:
    def __init__(self, *responses: dict[str, Any]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> dict[str, Any]:
        self.requests.append(deepcopy(request))
        return self.responses.pop(0)


def _response(
    call_id: str,
    *,
    content: Any,
    reasoning: str,
    path: str = "/app/workspace/x.txt",
    second_call: bool = False,
) -> dict[str, Any]:
    calls = [{
        "id": call_id,
        "type": "function",
        "function": {
            "name": "read_file",
            "arguments": json.dumps({"arguments": {"path": path}}),
        },
    }]
    if second_call:
        calls.append({
            "id": f"{call_id}-duplicate",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({"arguments": {"path": path}}),
            },
        })
    return {
        "id": f"response-{call_id}",
        "choices": [{
            "index": 0,
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": content,
                "reasoning_content": reasoning,
                "tool_calls": calls,
            },
        }],
        "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
    }


def _run(
    responses: list[dict[str, Any]],
    *,
    working_context_mode: str | None,
    max_steps: int,
) -> tuple[Any, _Transport]:
    transport = _Transport(*responses)
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        native_persistent_tools=True,
    )
    hooks = ModelHooks(model, lambda *_args, **_kwargs: "{}", run_id="c7-run", task_id="c7-task")
    executor = MemoryExecutor(
        workspace_root="/app/workspace",
        files={
            "/app/workspace/x.txt": "CURRENT-REALITY-EXACT-READ",
            "/app/workspace/y.txt": "CURRENT-REALITY-Y",
            "/app/workspace/z.txt": "CURRENT-REALITY-Z",
            "/app/workspace/w.txt": "CURRENT-REALITY-W",
        },
    )
    env = EnvMap(
        task_prompt="Inspect x.txt; preserve the exact task contract.",
        workspace_root="/app/workspace",
        visible_files=tuple(
            f"/app/workspace/{name}.txt" for name in ("x", "y", "z", "w")
        ),
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "task files", tool_names=("read_file",),
            ),
        },
    )
    config_args: dict[str, Any] = {
        "max_steps": max_steps,
        "max_solver_turns": len(responses),
        "solver_reality_transport_mode": "latest_exchange_v1",
        "probe_runtime_capabilities": False,
    }
    if working_context_mode is not None:
        config_args["solver_working_context_mode"] = working_context_mode
    result = run_thin_loop(
        env,
        executor,
        hooks,
        config=ThinLoopConfig(**config_args),
    )
    return result, transport


def _read_response(
    call_id: str,
    *,
    content: Any,
    reasoning: str,
    path: str = "/app/workspace/x.txt",
) -> dict[str, Any]:
    return _response(call_id, content=content, reasoning=reasoning, path=path)


def test_c7_frontier_admits_content_only_opted_in_and_keeps_last_admitted_exchange() -> None:
    responses = [
        _read_response("call-0", content="FACT-A: receipt handle alpha", reasoning="reasoning-A", path="/app/workspace/x.txt"),
        _read_response("call-1", content=None, reasoning="reasoning-null", path="/app/workspace/y.txt"),
        _read_response("call-2", content="", reasoning="reasoning-empty", path="/app/workspace/z.txt"),
        _response(
            "call-rejected",
            content="REJECTED-CANDIDATE-MUST-NOT-ENTER",
            reasoning="reasoning-rejected",
            second_call=True,
        ),
        _read_response("call-4", content=None, reasoning="reasoning-repair", path="/app/workspace/w.txt"),
    ]

    result, transport = _run(
        responses,
        working_context_mode="assistant_content_v1",
        max_steps=4,
    )

    assert len(transport.requests) == 5
    assert result.accounting["solver_protocol_correction_calls"] == 1
    accepted_reads = [row for row in result.receipts if row.kind == "read_file"]
    assert len(accepted_reads) == 4 and all(row.success for row in accepted_reads)

    # The actual Thin -> ModelHooks -> native Chat path admitted content,
    # reasoning and the exact provider tool call, then paired that call with
    # the current canonical result in the next latest-exchange request.
    first_next = transport.requests[1]
    assistant = [row for row in first_next["messages"] if row.get("role") == "assistant"]
    tool_result = [row for row in first_next["messages"] if row.get("role") == "tool"]
    assert len(assistant) == len(tool_result) == 1
    assert assistant[0]["content"] == "FACT-A: receipt handle alpha"
    assert assistant[0]["reasoning_content"] == "reasoning-A"
    assert assistant[0]["tool_calls"][0]["id"] == "call-0"
    assert tool_result[0]["tool_call_id"] == "call-0"
    assert "CURRENT-REALITY-EXACT-READ" in tool_result[0]["content"]

    # Both null and empty assistant content replace the prior text frontier;
    # each remains paired with only its own native tool result.
    null_next = transport.requests[2]["messages"]
    null_assistant = next(row for row in null_next if row.get("role") == "assistant")
    null_result = next(row for row in null_next if row.get("role") == "tool")
    assert null_assistant["content"] is None
    assert null_assistant["reasoning_content"] == "reasoning-null"
    assert null_assistant["tool_calls"][0]["id"] == null_result["tool_call_id"] == "call-1"
    assert "FACT-A" not in json.dumps(null_next)

    empty_next = transport.requests[3]["messages"]
    empty_assistant = next(row for row in empty_next if row.get("role") == "assistant")
    empty_result = next(row for row in empty_next if row.get("role") == "tool")
    assert empty_assistant["content"] == ""
    assert empty_assistant["reasoning_content"] == "reasoning-empty"
    assert empty_assistant["tool_calls"][0]["id"] == empty_result["tool_call_id"] == "call-2"
    assert "FACT-A" not in json.dumps(empty_next)

    # The two-call response is rejected before execution/admission. Its text
    # cannot replace the last committed (empty) frontier on protocol repair.
    repaired = transport.requests[4]["messages"]
    repair_assistant = next(row for row in repaired if row.get("role") == "assistant")
    repair_result = next(row for row in repaired if row.get("role") == "tool")
    assert repair_assistant["content"] == ""
    assert repair_assistant["reasoning_content"] == "reasoning-empty"
    assert repair_assistant["tool_calls"][0]["id"] == repair_result["tool_call_id"] == "call-2"
    assert "REJECTED-CANDIDATE-MUST-NOT-ENTER" not in json.dumps(repaired)
    assert any(
        row.get("role") == "user" and "previous response was rejected" in str(row.get("content"))
        for row in repaired
    )

    # The task, retrieval and native tool surfaces remain protected and live.
    assert all(
        sum("[raw_user_task]\nInspect x.txt; preserve the exact task contract." in str(m.get("content"))
               for m in request["messages"]) == 1
        for request in transport.requests
    )
    tool_names = {
        tool["function"]["name"]
        for tool in transport.requests[0]["tools"]
    }
    assert {"read_file", "query_history", "read_output"} <= tool_names
    current_packet = json.loads(tool_result[0]["content"].split("\n", 1)[1])
    assert "history_access" in current_packet


def test_c7_default_off_is_byte_identical_and_opt_in_adds_one_declared_message() -> None:
    response_sets = [
        [_read_response("call-0", content=None, reasoning="reasoning")]
        for _ in range(3)
    ]
    default_result, default_transport = _run(
        response_sets[0], working_context_mode=None, max_steps=1,
    )
    explicit_off_result, explicit_off_transport = _run(
        response_sets[1], working_context_mode="off", max_steps=1,
    )
    opted_in_result, opted_in_transport = _run(
        response_sets[2], working_context_mode="assistant_content_v1", max_steps=1,
    )
    assert default_result.status == explicit_off_result.status == opted_in_result.status
    default_request = default_transport.requests[0]
    explicit_off_request = explicit_off_transport.requests[0]
    opted_in_request = opted_in_transport.requests[0]
    assert json.dumps(default_request, sort_keys=True, separators=(",", ":")) == json.dumps(
        explicit_off_request, sort_keys=True, separators=(",", ":"),
    )
    guidance = {
        "role": "system",
        "content": (
            "[working_context]\n"
            "After a native tool call is admitted, only that latest assistant message (including its content, "
            "reasoning, and exact native tool call when present) and its matching latest tool result are carried "
            "into the next call. Text you put in your assistant message content alongside the tool call is kept "
            "verbatim for the next call and can hold anything you want to keep (goals, beliefs, failed approaches, "
            "evidence handles). Older results stay retrievable with query_history and read_output. This working "
            "note is fallible and non-authoritative: it must not override the raw task, tool contracts, current "
            "action results, or fresh reality; re-check its claims against current observations and retrieval."
        ),
    }
    assert opted_in_request["messages"].count(guidance) == 1
    assert [row for row in opted_in_request["messages"] if row != guidance] == explicit_off_request["messages"]
    assert opted_in_request["tools"] == explicit_off_request["tools"]


def test_c7_content_plus_tool_call_stays_rejected_without_opt_in() -> None:
    transport = _Transport(_read_response(
        "call-0", content="must remain rejected in control", reasoning="reasoning",
    ))
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        native_persistent_tools=True,
    )
    with pytest.raises(ChatModelError, match="native_tool_mixed_output"):
        model.call_with_telemetry_scope(
            [{"role": "system", "content": "task"}],
            max_output_tokens=64,
            run_id="control-run",
            task_id="control-task",
        )


@pytest.mark.parametrize("working_context_mode", [None, "assistant_content_v1"])
def test_native_tool_rejects_non_text_content_parts_before_continuity_admission(
    working_context_mode: str | None,
) -> None:
    response = _read_response(
        "call-non-text-content",
        content=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}],
        reasoning="reasoning",
    )
    transport = _Transport(response)
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        native_persistent_tools=True,
    )
    if working_context_mode is not None:
        model.set_solver_working_context_mode(
            working_context_mode,
            run_id="non-text-run",
            task_id="non-text-task",
        )

    with pytest.raises(ChatModelError, match="native_tool_content_format_invalid"):
        model.call_with_telemetry_scope(
            [{"role": "system", "content": "protected task"}],
            max_output_tokens=64,
            run_id="non-text-run",
            task_id="non-text-task",
        )


def test_c7_empty_native_call_id_cannot_replace_the_admitted_frontier() -> None:
    transport = _Transport(
        _read_response("call-good", content="KEEP-ADMITTED", reasoning="reasoning-good"),
        _read_response("", content="REJECTED-EMPTY-ID", reasoning="reasoning-bad"),
        _read_response("call-next", content=None, reasoning="reasoning-next"),
    )
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        native_persistent_tools=True,
    )
    model.set_reality_transport_mode("latest_exchange_v1", run_id="id-run", task_id="id-task")
    model.set_solver_working_context_mode(
        "assistant_content_v1", run_id="id-run", task_id="id-task",
    )

    def messages(step: int) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": "[raw_user_task]\nKeep the protected task."},
            {"role": "system", "content": f"[context_packet]\n{{\"step\":{step}}}"},
        ]

    model.call_with_telemetry_scope(
        messages(0), max_output_tokens=64, run_id="id-run", task_id="id-task",
    )
    model.commit_pending_response(run_id="id-run", task_id="id-task")
    with pytest.raises(ChatModelError, match="native_tool_continuity_identity_missing"):
        model.call_with_telemetry_scope(
            messages(1), max_output_tokens=64, run_id="id-run", task_id="id-task",
        )
    model.reject_pending_response(run_id="id-run", task_id="id-task")
    model.call_with_telemetry_scope(
        messages(2), max_output_tokens=64, run_id="id-run", task_id="id-task",
    )

    repaired = transport.requests[2]["messages"]
    assistant = next(row for row in repaired if row.get("role") == "assistant")
    tool_result = next(row for row in repaired if row.get("role") == "tool")
    assert assistant["content"] == "KEEP-ADMITTED"
    assert assistant["reasoning_content"] == "reasoning-good"
    assert assistant["tool_calls"][0]["id"] == tool_result["tool_call_id"] == "call-good"
    assert "REJECTED-EMPTY-ID" not in json.dumps(repaired)
    assert tool_result["content"] == '[context_packet]\n{"step":2}'

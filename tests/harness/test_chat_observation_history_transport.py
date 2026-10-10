from __future__ import annotations

import json
from typing import Any

from aether.providers.chat_model import ChatCompletionsModelCallable

PREFIX = "[context_packet]\n"


class FakeTransport:
    def __init__(self, *responses: dict[str, Any]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> dict[str, Any]:
        self.requests.append(json.loads(json.dumps(request)))
        return self.responses.pop(0)


def _tool_response(call_id: str) -> dict[str, Any]:
    return {
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": call_id, "type": "function", "function": {
                    "name": "read_file", "arguments": json.dumps({"arguments": {"path": "/app/workspace/x"}})}}],
                "reasoning_content": f"reasoning for {call_id}",
            },
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _packet(step: int) -> dict[str, Any]:
    receipts = [{
        "receipt_id": f"step-{i}:read",
        "exact_access": {"handle": f"receipt-handle-{i}"},
        "bounded_view": {"excerpt": f"observed-{i}"},
    } for i in range(step + 1)]
    return {
        "latest_primary_result": {"status": "succeeded", "outcome_receipts": [receipts[-1]]},
        "evidence_index": receipts,
        "linked_history": {"live_processes": [f"process-{step}"]},
        "budgets": {"used_kernel_steps": step},
        "history_access": {"action": "query_history"},
    }


def _system_packet(packet: dict[str, Any]) -> dict[str, str]:
    return {"role": "system", "content": PREFIX + json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=True)}


def _run(mode: str | None, turns: int = 5) -> FakeTransport:
    transport = FakeTransport(*[_tool_response(f"call-{i}") for i in range(turns)])
    model = ChatCompletionsModelCallable(transport=transport, deployment="glm-test", role="solver", native_persistent_tools=True)
    if mode is not None:
        model.set_reality_transport_mode(mode, run_id="run", task_id="task")
    for step in range(turns):
        model.call_with_telemetry_scope(
            [{"role": "system", "content": "[raw_user_task]\nT"}, _system_packet(_packet(step))],
            max_output_tokens=64, run_id="run", task_id="task",
        )
        model.commit_pending_response(run_id="run", task_id="task")
    return transport


def _tool_messages(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in request["messages"] if m["role"] == "tool"]


def _all_values(value: Any, key: str) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        if key in value and isinstance(value[key], str):
            found.add(value[key])
        for child in value.values():
            found |= _all_values(child, key)
    elif isinstance(value, list):
        for child in value:
            found |= _all_values(child, key)
    return found


def test_control_replays_full_packets() -> None:
    third = _run(None).requests[2]
    tools = _tool_messages(third)
    assert len(tools) == 2
    assert all('"linked_history"' in message["content"] for message in tools)


def test_observation_history_preserves_receipts_and_removes_superseded_state() -> None:
    control = _run(None).requests[4]
    treatment = _run("observation_history_v1").requests[4]
    control_tools = _tool_messages(control)
    treatment_tools = _tool_messages(treatment)
    assert len(control_tools) == len(treatment_tools) == 4

    def decoded(message: dict[str, Any]) -> dict[str, Any]:
        return json.loads(message["content"][len(PREFIX):])

    control_packets = [decoded(message) for message in control_tools]
    treatment_packets = [decoded(message) for message in treatment_tools]
    assert _all_values(control_packets, "receipt_id") <= _all_values(treatment_packets, "receipt_id")
    assert _all_values(control_packets, "handle") <= _all_values(treatment_packets, "handle")
    assert all("linked_history" not in packet for packet in treatment_packets[:-1])
    assert treatment_packets[-1]["linked_history"] == {"live_processes": ["process-4"]}
    assert all("latest_primary_result" in packet for packet in treatment_packets)


def test_observation_history_keeps_assistant_reasoning_and_tool_pairing() -> None:
    third = _run("observation_history_v1").requests[2]
    messages = third["messages"]
    for index, message in enumerate(messages):
        if message["role"] == "tool":
            assert messages[index - 1]["role"] == "assistant"
            assert messages[index - 1]["tool_calls"][0]["id"] == message["tool_call_id"]
    assistants = [m for m in messages if m["role"] == "assistant"]
    assert [m["reasoning_content"] for m in assistants] == ["reasoning for call-0", "reasoning for call-1"]


def test_latest_exchange_keeps_one_assistant_and_latest_tool_result() -> None:
    third = _run("latest_exchange_v1").requests[2]
    assert len([m for m in third["messages"] if m["role"] == "assistant"]) == 1
    tools = _tool_messages(third)
    assert len(tools) == 1
    assert json.loads(tools[0]["content"][len(PREFIX):])["linked_history"] == {"live_processes": ["process-2"]}


def test_transport_mode_is_scoped_and_reported() -> None:
    transport = FakeTransport(*[_tool_response(f"call-{i}") for i in range(6)])
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="solver", native_persistent_tools=True,
    )
    model.set_reality_transport_mode("observation_history_v1", run_id="r1", task_id="t1")
    for run_id, task_id in (("r1", "t1"), ("r2", "t2")):
        for step in range(3):
            model.call_with_telemetry_scope(
                [{"role": "system", "content": "task"}, _system_packet(_packet(step))],
                max_output_tokens=64, run_id=run_id, task_id=task_id,
            )
            model.commit_pending_response(run_id=run_id, task_id=task_id)

    projected = _tool_messages(transport.requests[2])
    control = _tool_messages(transport.requests[5])
    assert json.loads(projected[0]["content"][len(PREFIX):])["packet_history_projection"] == "observation_only_v1"
    assert "linked_history" not in json.loads(projected[0]["content"][len(PREFIX):])
    assert "linked_history" in json.loads(control[0]["content"][len(PREFIX):])
    telemetry = model.drain_telemetry()
    assert [event["chat_reality_transport_mode"] for event in telemetry] == [
        "observation_history_v1" if event["task_id"] == "t1" else "full_snapshot_control"
        for event in telemetry
    ]


def test_pt_ra_keeps_all_reasoning_and_actions_but_stubs_old_results() -> None:
    fifth = _run("reasoning_actions_no_results_v1").requests[4]
    messages = fifth["messages"]
    assistants = [m for m in messages if m["role"] == "assistant"]
    tools = _tool_messages(fifth)
    assert [m["reasoning_content"] for m in assistants] == [
        "reasoning for call-0", "reasoning for call-1", "reasoning for call-2", "reasoning for call-3",
    ]
    assert [m["tool_calls"][0]["id"] for m in assistants] == [
        "call-0", "call-1", "call-2", "call-3",
    ]
    assert len(tools) == 4
    for index, message in enumerate(tools[:-1]):
        assert message["content"].startswith("[historical_result_omitted]\n")
        payload = json.loads(message["content"].split("\n", 1)[1])
        assert payload["historical_results_are_current_state"] is False
        assert payload["retrieval_actions"] == ["query_history", "read_output"]
        assert payload["retrieval_handles"]
        assert messages[messages.index(message) - 1]["tool_calls"][0]["id"] == message["tool_call_id"]
    assert tools[-1]["content"].startswith(PREFIX)
    assert messages[messages.index(tools[-1]) - 1]["tool_calls"][0]["id"] == tools[-1]["tool_call_id"]


def test_pt_r1_keeps_all_reasoning_and_only_latest_action_result_pair() -> None:
    fifth = _run("reasoning_latest_action_no_results_v1").requests[4]
    messages = fifth["messages"]
    assistants = [m for m in messages if m["role"] == "assistant"]
    assert [m["reasoning_content"] for m in assistants] == [
        "reasoning for call-0", "reasoning for call-1", "reasoning for call-2", "reasoning for call-3",
    ]
    assert all("tool_calls" not in m for m in assistants[:-1])
    assert assistants[-1]["tool_calls"][0]["id"] == "call-3"
    tools = _tool_messages(fifth)
    assert len(tools) == 1
    assert tools[0]["tool_call_id"] == "call-3"
    assert tools[0]["content"].startswith(PREFIX)


def test_pt_r1_preserves_interleaved_user_feedback_order() -> None:
    transport = FakeTransport(*[_tool_response(f"call-{i}") for i in range(3)])
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", role="solver", native_persistent_tools=True,
    )
    model.set_reality_transport_mode(
        "reasoning_latest_action_no_results_v1", run_id="run", task_id="task",
    )

    model.call_with_telemetry_scope(
        [{"role": "system", "content": "[raw_user_task]\nT"}, _system_packet(_packet(0))],
        max_output_tokens=64, run_id="run", task_id="task",
    )
    model.commit_pending_response(run_id="run", task_id="task")

    model.call_with_telemetry_scope(
        [
            {"role": "system", "content": "[raw_user_task]\nT"},
            _system_packet(_packet(1)),
            {"role": "user", "content": "[protocol_correction]\nfix the arguments"},
        ],
        max_output_tokens=64, run_id="run", task_id="task",
    )
    model.commit_pending_response(run_id="run", task_id="task")

    model.call_with_telemetry_scope(
        [{"role": "system", "content": "[raw_user_task]\nT"}, _system_packet(_packet(2))],
        max_output_tokens=64, run_id="run", task_id="task",
    )
    third = transport.requests[2]["messages"]
    suffix = [m for m in third if m["role"] in {"assistant", "user", "tool"}]
    assert [m["role"] for m in suffix] == ["assistant", "user", "assistant", "tool"]
    assert suffix[0]["reasoning_content"] == "reasoning for call-0"
    assert suffix[1]["content"] == "[protocol_correction]\nfix the arguments"
    assert suffix[2]["reasoning_content"] == "reasoning for call-1"
    assert suffix[2]["tool_calls"][0]["id"] == "call-1"
    assert suffix[3]["tool_call_id"] == "call-1"


def test_pt_modes_are_reported_in_telemetry() -> None:
    for mode in ("reasoning_actions_no_results_v1", "reasoning_latest_action_no_results_v1"):
        transport = _run(mode, turns=3)
        assert len(transport.requests) == 3


def test_pt_modes_reduce_history_payload_without_dropping_reasoning() -> None:
    observation = _run("observation_history_v1").requests[4]
    pt_ra = _run("reasoning_actions_no_results_v1").requests[4]
    pt_r1 = _run("reasoning_latest_action_no_results_v1").requests[4]
    def history_bytes(request: dict[str, Any]) -> int:
        return len(json.dumps(request["messages"], sort_keys=True, separators=(",", ":")).encode())
    assert history_bytes(pt_ra) < history_bytes(observation)
    assert history_bytes(pt_r1) < history_bytes(pt_ra)
    for request in (pt_ra, pt_r1):
        assistants = [m for m in request["messages"] if m["role"] == "assistant"]
        assert [m["reasoning_content"] for m in assistants] == [
            "reasoning for call-0", "reasoning for call-1", "reasoning for call-2", "reasoning for call-3",
        ]

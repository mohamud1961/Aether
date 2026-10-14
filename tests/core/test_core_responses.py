"""Responses API provider: request shape, stream assembly, and reasoning replay through the real loop."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import IncompleteStream, Turn
from aether.core.responses import ResponsesProvider, input_items, tool_spec
from tests.core.core_fakes import LocalEnv

TOOL = {
    "type": "function",
    "function": {
        "name": "terminal",
        "description": "run",
        "parameters": {"type": "object", "properties": {"input": {"type": "string"}}},
    },
}


def ev(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


def item(**kw):
    return SimpleNamespace(model_dump=lambda exclude_none=True: dict(kw))


def turn_events(n, call=None, text="", status="completed", reason=None):
    """One scripted response: a reasoning item, then text and/or one function call, then the final event."""
    out = [
        ev(
            "response.created",
            response=SimpleNamespace(id=f"resp{n}", model="gpt-6-luna-x"),
        )
    ]
    out.append(ev("response.reasoning_summary_text.delta", delta=f"summary {n}"))
    out.append(
        ev(
            "response.output_item.done",
            item=item(
                type="reasoning", id=f"rs{n}", encrypted_content=f"enc{n}", summary=[]
            ),
        )
    )
    if text:
        out.append(ev("response.output_text.delta", delta=text))
    if call:
        name, args, cid = call
        out.append(
            ev(
                "response.output_item.done",
                item=item(
                    type="function_call",
                    call_id=cid,
                    name=name,
                    arguments=json.dumps(args),
                ),
            )
        )
    final = SimpleNamespace(
        id=f"resp{n}",
        model="gpt-6-luna-x",
        status=status,
        incomplete_details=SimpleNamespace(reason=reason) if reason else None,
        usage=SimpleNamespace(
            model_dump=lambda: {
                "input_tokens": 1000,
                "output_tokens": 60,
                "input_tokens_details": {"cached_tokens": 400},
                "output_tokens_details": {"reasoning_tokens": 40},
            }
        ),
    )
    out.append(
        ev(
            "response.completed" if status == "completed" else "response.incomplete",
            response=final,
        )
    )
    return out


class _Stream:
    def __init__(self, events):
        self._events = list(events)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


class ResponsesClient:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        return _Stream(self.script.pop(0))


def provider(client, tmp_path, params=None):
    tmp_path.mkdir(exist_ok=True)
    return ResponsesProvider(
        client,
        model="GPT-6-Luna",
        params=params
        or {
            "reasoning_effort": "high",
            "tool_choice": "required",
            "parallel_tool_calls": False,
        },
        log=CallLog(tmp_path / "calls"),
    )


def test_tool_definitions_and_history_convert_to_responses_items():
    assert tool_spec(TOOL) == {
        "type": "function",
        "name": "terminal",
        "description": "run",
        "parameters": TOOL["function"]["parameters"],
    }
    enc = [{"type": "reasoning", "id": "rs1", "encrypted_content": "e", "summary": []}]
    history = [
        {"role": "system", "content": "sys"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "look"},
                {"type": "image_url", "image_url": {"url": "data:x"}},
            ],
        },
        {
            "role": "assistant",
            "content": "plan",
            "reasoning_content": enc,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "terminal", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "out"},
        {
            "role": "assistant",
            "content": None,
            "reasoning_content": "glm text is not replayable here",
            "tool_calls": [
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "terminal", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "assistant",
            "content": None,
            "reasoning_content": enc,
        },  # nothing follows it: not replayed
    ]
    assert input_items(history) == [
        {"role": "system", "content": "sys"},
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "look"},
                {"type": "input_image", "image_url": "data:x"},
            ],
        },
        enc[0],
        {"role": "assistant", "content": "plan"},
        {
            "type": "function_call",
            "call_id": "c1",
            "name": "terminal",
            "arguments": "{}",
        },
        {"type": "function_call_output", "call_id": "c1", "output": "out"},
        {
            "type": "function_call",
            "call_id": "c2",
            "name": "terminal",
            "arguments": "{}",
        },
    ]


def test_request_is_stateless_with_encrypted_reasoning_and_per_call_effort(tmp_path):
    p = provider(ResponsesClient([]), tmp_path)
    req = p._request([{"role": "user", "content": "hi"}], [TOOL], 500, None)
    assert req["max_output_tokens"] == 500 and "max_tokens" not in req
    assert req["params"]["store"] is False and req["params"]["include"] == [
        "reasoning.encrypted_content"
    ]
    assert req["params"]["reasoning"] == {"effort": "high", "summary": "auto"}
    assert "reasoning_effort" not in req["params"] and req["tools"] == [tool_spec(TOOL)]
    assert req["params"]["tool_choice"] == "required"
    plain = p._request(
        [{"role": "user", "content": "hi"}], None, 500, {"reasoning_effort": "low"}
    )
    assert "tools" not in plain and "tool_choice" not in plain["params"]
    assert plain["params"]["reasoning"]["effort"] == "low"


def test_stream_assembles_text_calls_usage_and_replayable_reasoning(tmp_path):
    client = ResponsesClient(
        [turn_events(1, call=("terminal", {"input": "ls"}, "c1"), text="ok")]
    )
    turn = asyncio.run(
        provider(client, tmp_path).complete(
            [{"role": "user", "content": "hi"}],
            [TOOL],
            max_tokens=100,
            remaining_s=lambda: 60,
        )
    )
    assert (
        turn.content == "ok"
        and turn.reasoning == "summary 1"
        and turn.finish_reason == "tool_calls"
    )
    assert turn.tool_calls[0]["id"] == "c1" and json.loads(
        turn.tool_calls[0]["function"]["arguments"]
    ) == {"input": "ls"}
    assert turn.usage == {"input": 1000, "output": 60, "cached": 400, "reasoning": 40}
    assert turn.response_model == "gpt-6-luna-x"
    msg = turn.assistant_message()
    assert msg["reasoning_content"] == [
        {"type": "reasoning", "id": "rs1", "encrypted_content": "enc1", "summary": []}
    ]


def test_truncated_and_cut_streams_are_reported_honestly(tmp_path):
    client = ResponsesClient(
        [
            turn_events(
                1, text="partial", status="incomplete", reason="max_output_tokens"
            )
        ]
    )
    turn = asyncio.run(
        provider(client, tmp_path).complete(
            [{"role": "user", "content": "hi"}],
            [TOOL],
            max_tokens=100,
            remaining_s=lambda: 60,
        )
    )
    assert turn.finish_reason == "length"
    cut = provider(ResponsesClient([turn_events(1, text="x")[:-1]]), tmp_path / "cut")
    with pytest.raises(IncompleteStream):
        asyncio.run(
            cut._stream_once(
                cut._request([{"role": "user", "content": "hi"}], None, 10, None),
                Turn(),
            )
        )


def test_chat_turns_keep_text_reasoning_in_the_replay_slot():
    assert (
        Turn(reasoning="glm thought").assistant_message()["reasoning_content"]
        == "glm thought"
    )


def test_the_loop_replays_the_previous_turns_encrypted_reasoning(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    client = ResponsesClient(
        [
            turn_events(1, call=("terminal", {"input": "echo hi > f.txt"}, "c1")),
            turn_events(2, call=("finish", {"summary": "wrote f.txt"}, "c2")),
        ]
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="write f.txt",
            workdir=str(work),
            provider=provider(client, tmp_path),
            timeout_s=60,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl")),
        )
    )
    assert result.status == "finished" and (work / "f.txt").read_text().strip() == "hi"
    second = client.requests[1]["input"]
    kinds = [
        (i.get("type"), i.get("id") or i.get("call_id")) for i in second if "type" in i
    ]
    assert kinds[:3] == [
        ("reasoning", "rs1"),
        ("function_call", "c1"),
        ("function_call_output", "c1"),
    ]
    assert client.requests[1]["store"] is False and "tools" in client.requests[1]


def _three_turn_inputs(tmp_path, replay):
    from aether.core.clm import ClmSettings

    work = tmp_path / f"w-{replay}"
    work.mkdir()
    client = ResponsesClient(
        [
            turn_events(1, call=("terminal", {"input": "echo a > a.txt"}, "c1")),
            turn_events(2, call=("terminal", {"input": "echo b > b.txt"}, "c2")),
            turn_events(3, call=("finish", {"summary": "wrote a and b"}, "c3")),
        ]
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="write a.txt and b.txt",
            workdir=str(work),
            provider=provider(client, tmp_path / f"p-{replay}"),
            timeout_s=60,
            trace=Trace(tmp_path / f"trace-{replay}.jsonl"),
            config=CoreConfig(
                context="clm",
                clm=ClmSettings(replay_reasoning=replay),
                control_dir=str(tmp_path / f"ctl-{replay}"),
            ),
        )
    )
    assert result.status == "finished"
    return [r["input"] for r in client.requests]


def _strip_volatile(items):
    """Drop the per-turn clock and context notes the loop appends to tool output, so only history order is compared."""
    return [
        (i.get("type") or i.get("role"), i.get("id") or i.get("call_id")) for i in items
    ]


def test_replaying_every_turns_reasoning_makes_each_request_extend_the_last(tmp_path):
    for replay, extends in (("all", True), ("newest", False)):
        inputs = [_strip_volatile(x) for x in _three_turn_inputs(tmp_path, replay)]
        second, third = inputs[1], inputs[2]
        assert (third[: len(second)] == second) is extends, replay
        reasoning = [k for k in third if k[0] == "reasoning"]
        assert reasoning == (
            [("reasoning", "rs1"), ("reasoning", "rs2")]
            if replay == "all"
            else [("reasoning", "rs2")]
        )

"""Real OpenAI SDK Responses SSE through Core's provider, loop, and tool effect."""

import asyncio
import json
import re

from openai import AsyncOpenAI

from aether.core.calls import CallLog, requests
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.responses import ResponsesProvider
from tests.core_fakes import LocalEnv
from tests.test_core_http import server


def _response(response_id: str, *, status: str, output: list[dict], usage: bool) -> dict:
    value = {
        "id": response_id,
        "object": "response",
        "created_at": 1,
        "model": "scripted-responses",
        "status": status,
        "output": output,
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }
    if usage:
        value["usage"] = {
            "input_tokens": 12,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens": 4,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 16,
        }
    return value


def responses_sse(response_id: str, item: dict, *, complete: bool) -> tuple:
    in_progress_item = {**item, "status": "in_progress", "arguments": ""}
    events = [
        {
            "type": "response.created",
            "sequence_number": 0,
            "response": _response(response_id, status="in_progress", output=[], usage=False),
        },
        {
            "type": "response.output_item.added",
            "sequence_number": 1,
            "output_index": 0,
            "item": in_progress_item,
        },
        {
            "type": "response.function_call_arguments.delta",
            "sequence_number": 2,
            "output_index": 0,
            "item_id": item["id"],
            "delta": item["arguments"],
        },
        {
            "type": "response.function_call_arguments.done",
            "sequence_number": 3,
            "output_index": 0,
            "item_id": item["id"],
            "name": item["name"],
            "arguments": item["arguments"],
        },
        {
            "type": "response.output_item.done",
            "sequence_number": 4,
            "output_index": 0,
            "item": item,
        },
    ]
    if complete:
        events.append(
            {
                "type": "response.completed",
                "sequence_number": 5,
                "response": _response(
                    response_id, status="completed", output=[item], usage=True
                ),
            }
        )
    body = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
    if complete:
        body += "data: [DONE]\n\n"
    return 200, {"Content-Type": "text/event-stream"}, body.encode()


def _function_call(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "id": f"fc_{call_id}",
        "type": "function_call",
        "status": "completed",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments),
    }


def test_real_sdk_responses_sse_runs_core_tool_pairs_output_and_retries_incomplete(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    effect_path = work / "artifact.txt"
    calls_path = tmp_path / "calls.jsonl"
    trace_path = tmp_path / "trace.jsonl"
    content = "Responses SSE effect\n"
    write_item = _function_call(
        "call_write",
        "write_file",
        {"path": "artifact.txt", "content": content},
    )
    finish_item = _function_call("call_finish", "finish", {"summary": "complete"})
    # The first response exposes a full-looking function call item and then ends without
    # response.completed. Core must retry the provider turn before dispatching the file write.
    with server(
        [
            responses_sse("resp_cut", write_item, complete=False),
            responses_sse("resp_write", write_item, complete=True),
            responses_sse("resp_finish", finish_item, complete=True),
        ]
    ) as (url, seen):

        async def execute():
            async with AsyncOpenAI(
                api_key="offline-responses-fixture-key",
                base_url=url + "/v1/",
                max_retries=0,
            ) as client:
                provider = ResponsesProvider(
                    client,
                    model="scripted-responses",
                    params={},
                    log=CallLog(calls_path),
                    sleep=lambda _delay: asyncio.sleep(0),
                )
                return await run_agent(
                    env=LocalEnv(work),
                    task="Write the supplied fixture content to artifact.txt, then finish.",
                    workdir=str(work),
                    provider=provider,
                    timeout_s=90,
                    trace=Trace(trace_path),
                    config=CoreConfig(control_dir=str(tmp_path / "control")),
                )

        result = asyncio.run(execute())

    assert result.status == "finished"
    assert effect_path.read_bytes() == content.encode()
    assert len(seen) == 3
    # All three HTTP request bodies use native Responses `input`, not Chat `messages`.
    assert all("input" in request and "messages" not in request for request in seen)
    # The incomplete attempt and retry sent the same pre-action request; no tool effect occurred between them.
    assert seen[0]["input"] == seen[1]["input"]
    rows = list(requests(calls_path))
    assert [(row["attempt"], row["ok"]) for row in rows] == [
        (1, False),
        (2, True),
        (1, True),
    ]
    assert rows[1]["response_id"] == "resp_write"
    assert rows[2]["response_id"] == "resp_finish"
    assert "offline-responses-fixture-key" not in calls_path.read_text()

    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    writes = [row for row in trace if row.get("event") == "tool" and row.get("name") == "write_file"]
    finishes = [row for row in trace if row.get("event") == "tool" and row.get("name") == "finish"]
    models = [row for row in trace if row.get("event") == "model"]
    assert len(writes) == 1
    assert len(finishes) == 1
    assert len(models) == 2 and models[0]["attempts"] == 2

    # The next Responses request must preserve the assistant function call immediately followed
    # by its exact matching function_call_output; the output is the Core-observed write receipt.
    next_input = seen[2]["input"]
    call_index = next(
        index
        for index, item in enumerate(next_input)
        if item.get("type") == "function_call" and item.get("call_id") == "call_write"
    )
    output_index = next(
        index
        for index, item in enumerate(next_input)
        if item.get("type") == "function_call_output" and item.get("call_id") == "call_write"
    )
    output_item = next_input[output_index]
    assert call_index < output_index
    assert output_index == call_index + 1
    assert output_item["output"].startswith(writes[0]["result"])
    assert f"wrote {len(content.encode())} bytes" in output_item["output"]
    assert str(effect_path) in output_item["output"]
    assert re.search(r"\n\[t=\d+s of 90s\]$", output_item["output"])


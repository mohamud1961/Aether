"""Real SDK and loopback Responses transport for the opt-in multi-call experiment."""

import asyncio
import json
from dataclasses import replace

import pytest

from aether.core.harbor_agent import build_config, build_provider
from aether.core.loop import Trace, run_agent
from tests.test_core_http import server
from tests.test_core_multi_call_comparison_e2e import TimedReads
from tests.test_core_responses_http import _function_call, _response, responses_sse


def multi_response(items):
    response_id = "resp_multiple"
    events = [{
        "type": "response.created", "sequence_number": 0,
        "response": _response(response_id, status="in_progress", output=[], usage=False),
    }]
    for i, item in enumerate(items):
        events.append({
            "type": "response.output_item.done", "sequence_number": i + 1,
            "output_index": i, "item": item,
        })
    events.append({
        "type": "response.completed", "sequence_number": len(items) + 1,
        "response": _response(response_id, status="completed", output=items, usage=True),
    })
    body = "".join("data: " + json.dumps(event) + "\n\n" for event in events) + "data: [DONE]\n\n"
    return 200, {"Content-Type": "text/event-stream"}, body.encode()


@pytest.mark.parametrize("grouped,peak", [(False, 1), (True, 2)])
def test_real_responses_stream_preserves_multiple_calls_and_results(tmp_path, grouped, peak):
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("alpha\n")
    (work / "b.txt").write_text("beta\n")
    items = [_function_call("a", "read_file", {"path": "a.txt"}),
             _function_call("b", "read_file", {"path": "b.txt"})]
    combine = _function_call("combine", "terminal", {"input": "cat a.txt b.txt > combined.txt"})
    finish = _function_call("finish", "finish", {"summary": "done"})
    replies = [multi_response(items), responses_sse("resp_combine", combine, complete=True),
               responses_sse("resp_finish", finish, complete=True)]
    with server(replies) as (url, requests):
        environ = {
            "AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "project", "AETHER_CORE_REPL": "off",
            "AETHER_CORE_IMAGES": "off", "AETHER_CORE_REQUEST": "responses", "AETHER_CORE_API": "openai",
            "AETHER_CORE_CALLS": "many", "AETHER_CORE_PARALLEL_READS": "on" if grouped else "off",
            "AETHER_FW_GLM_53_FLASH_ENDPOINT": url + "/v1/",
            "AETHER_FW_GLM_53_FLASH_KEY": "offline", "AETHER_FW_GLM_53_FLASH_DEPLOYMENT": "scripted",
        }
        env = TimedReads(work)

        async def execute():
            provider = build_provider(environ=environ)
            try:
                return await run_agent(
                    env=env, task="Combine the supplied files.", workdir=str(work),
                    provider=provider, timeout_s=60, trace=Trace(tmp_path / "trace"),
                    config=replace(build_config(environ=environ), control_dir=str(tmp_path / "control")),
                )
            finally:
                await provider._client.close()

        result = asyncio.run(execute())

    assert result.status == "finished"
    assert (work / "combined.txt").read_text() == "alpha\nbeta\n"
    assert env.peak == peak
    assert all(request["parallel_tool_calls"] is True for request in requests)
    calls = [item["call_id"] for item in requests[1]["input"] if item.get("type") == "function_call"]
    outputs = [item for item in requests[1]["input"] if item.get("type") == "function_call_output"]
    assert calls == ["a", "b"] and [item["call_id"] for item in outputs] == ["a", "b"]
    assert "alpha" in outputs[0]["output"] and "beta" in outputs[1]["output"]

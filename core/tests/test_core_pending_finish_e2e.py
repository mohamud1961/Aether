"""A finish held for a real terminal result must allow a fresh decision."""

import asyncio
import json

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk, tool_chunk


def test_held_finish_defers_all_queued_actions_until_a_new_turn(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "staged").write_bytes(b"old\n")
    client = ScriptedClient([
        call("terminal", {
            "input": "sleep 1.2; printf 'ready\\n' > prerequisite",
            "name": "build", "wait_s": 0.1,
        }, "start"),
        [
            tool_chunk("finish", {"summary": "Ready."}, index=0, call_id="held"),
            tool_chunk("terminal", {"input": "cat staged >> published"}, index=1, call_id="early"),
            tool_chunk("finish", {"summary": "Published."}, index=2, call_id="early-finish"),
            chunk(finish="tool_calls"),
        ],
        call("write_file", {"path": "staged", "content": "new\n"}, "prepare"),
        call("terminal", {"input": "test -f prerequisite && cat staged >> published"}, "publish"),
        call("finish", {"summary": "Published."}, "done"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Publish the new release exactly once when the prerequisite is ready.",
        workdir=str(work), provider=ChatProvider(client, model="offline", params={}),
        trace=Trace(trace), timeout_s=45,
        config=CoreConfig(terminal_events=True, control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    assert result.status == "finished"
    assert (work / "prerequisite").read_bytes() == b"ready\n"
    assert (work / "published").read_bytes() == b"new\n"
    tools = [msg for msg in client.requests[2]["messages"] if msg["role"] == "tool"]
    assert [msg["tool_call_id"] for msg in tools[-3:]] == ["held", "early", "early-finish"]
    observed, _ = json.JSONDecoder().raw_decode(tools[-3]["content"].split("\n", 1)[1])
    assert [event["name"] for event in observed["completed"]] == ["build"]
    assert not observed["pending"] and not observed["unknown"]
    assert all("not dispatched" in msg["content"] for msg in tools[-2:])
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    skipped = [row["call_id"] for row in rows if row["event"] == "action_skipped"]
    assert skipped == ["early", "early-finish"]

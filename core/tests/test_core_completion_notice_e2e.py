"""A background command finishes while the model works elsewhere (real Linux shell, real Core loop)."""

import asyncio
import json
import os

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call, tool_chunk

pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="native Linux shell qualification"
)


def run(tmp_path, notices):
    work = tmp_path / "work"
    work.mkdir()
    (work / "schema.txt").write_text("id,name\n")
    client = ScriptedClient([
        call("terminal", {"name": "export", "input": "sleep 0.6; echo exported > data.csv; (exit 5)",
                          "wait_s": 0.1}, "start"),
        call("terminal", {"name": "main", "input": "sleep 1.2; cat schema.txt", "wait_s": 5}, "schema"),
        call("read_file", {"path": "schema.txt"}, "again"),
        call("terminal", {"name": "export", "input": "", "wait_s": 1}, "collect"),
        call("read_file", {"path": "data.csv"}, "data"),
        call("finish", {"summary": "exported."}, "done"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Export data.csv.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(trace), timeout_s=60,
        config=CoreConfig(completion_notices=notices, control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    tools = [m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    return result, tools, rows


def test_finished_background_command_is_noticed_once_and_its_output_still_delivered(tmp_path):
    result, tools, rows = run(tmp_path, notices=True)
    assert result.status == "finished"
    start, schema, again, collect, data = tools
    assert "finished with exit" not in start
    assert "[terminal export: command #1 finished with exit 5" in schema  # noticed beside an unrelated result
    assert "id,name" in schema
    assert "finished with exit" not in again and "finished with exit" not in collect  # once
    assert "exported" in collect or "exit 5" in collect  # the output itself is delivered by the next use
    assert "exported" in data
    (notice,) = [r for r in rows if r["event"] == "completion_notice"]
    assert (notice["name"], notice["sequence"], notice["exit"]) == ("export", 1, 5)
    assert result.extras["completion_notices_seen"][0]["name"] == "export"


def test_switch_off_adds_no_notice(tmp_path):
    result, tools, rows = run(tmp_path, notices=False)
    assert result.status == "finished"
    assert not any("finished with exit" in t for t in tools)
    assert not [r for r in rows if r["event"].startswith("completion_notice")]



def test_completion_is_owned_by_terminal_generation_and_batched_at_packet_boundary(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "input").write_text("schema")
    parallel_packet = call("terminal", {"name": "main", "input": "sleep 0.9", "wait_s": 5}, "overlap2")
    parallel_packet.insert(2, tool_chunk("read_file", {"path": "input"}, index=1, call_id="boundary"))
    client = ScriptedClient([
        call("terminal", {"name": "export", "input": "sleep 0.4; echo one > one; (exit 4)", "wait_s": 0}, "start1"),
        call("terminal", {"name": "main", "input": "sleep 0.9", "wait_s": 5}, "overlap1"),
        call("terminal", {"name": "export", "input": "", "wait_s": 1}, "collect1"),
        call("terminal", {"name": "export", "input": "exit", "wait_s": 1}, "close1"),
        call("terminal", {"name": "export", "input": "sleep 0.4; echo two > two; (exit 7)", "wait_s": 0}, "start2"),
        parallel_packet,
        call("terminal", {"name": "export", "input": "", "wait_s": 1}, "collect2"),
        call("finish", {"summary": "exported both."}, "done"),
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Export both artifacts.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=30, config=CoreConfig(completion_notices=True, control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    assert result.status == "finished"
    assert len(client.requests) == 8
    assert [(row["sequence"], row["exit"]) for row in result.extras["completion_notices_seen"]] == [(1, 4), (1, 7)]
    messages = {m["tool_call_id"]: m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"}
    assert "finished with exit" not in messages["overlap2"]
    assert "[terminal export: command #1 finished with exit 7" in messages["boundary"]
    assert (work / "one").read_text() == "one\n" and (work / "two").read_text() == "two\n"



@pytest.mark.parametrize("delivery", [False, True])
def test_delivered_output_advances_the_task_without_a_collection_turn(tmp_path, delivery):
    work = tmp_path / "work"
    work.mkdir()
    (work / "input").write_text("value=417")
    (work / "schema").write_text("code")

    class DecisionClient(ScriptedClient):
        async def _create(self, **kwargs):
            if len(self.requests) in (2, 3) and not (work / "delivery").exists():
                last = next(m for m in reversed(kwargs["messages"]) if m["role"] == "tool")
                value = next((line.removeprefix("READY-") for line in last["content"].splitlines()
                              if line.startswith("READY-")), None)
                if value is None:
                    self.script.insert(0, call("terminal", {"name": "export", "input": "", "wait_s": 1}, "collect"))
                else:
                    self.script.insert(0, call("write_file", {"path": "delivery", "content": value}, "deliver"))
            return await super()._create(**kwargs)

    client = DecisionClient([
        call("terminal", {"name": "export", "input":
                         "while [ ! -f allow ]; do sleep 0.05; done; sed 's/^value=/READY-/' input; (exit 5)",
                         "wait_s": 0}, "start"),
        call("terminal", {"name": "schema", "input": "touch allow; sleep 0.6; cat schema", "wait_s": 3}, "schema"),
        call("terminal", {"name": "export", "input": "", "wait_s": 0}, "confirm-consumed"),
        call("finish", {"summary": "Delivered."}, "done"),
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Write the result of the export to delivery.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=30, config=CoreConfig(terminal_result_delivery=delivery, control_dir=str(tmp_path / "control"),
                                       end_processes="stop"),
    ))
    assert result.status == "finished"
    packets = {m["tool_call_id"]: m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"}
    assert ("Core will deliver" in packets["start"]) is delivery
    assert ("READY-417" in packets["schema"]) is delivery
    assert "READY-417" not in packets["confirm-consumed"] and "finished with exit" not in packets["deliver"]
    assert (work / "delivery").read_text() == "417"
    if delivery:
        assert "finished with exit 5" in packets["schema"]
        assert result.extras["completion_notices_seen"][0]["delivered"] is True
        assert len(client.requests) == 5 and "collect" not in packets
    else:
        assert "READY-417" in packets["collect"] and "[exit 5" in packets["collect"]
        assert len(client.requests) == 6

"""A background command finishes while the model works elsewhere (real Linux shell, real Core loop)."""

import asyncio
import json
import os

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

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

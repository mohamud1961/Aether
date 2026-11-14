"""A background writer still changing delivered files at finish (real shell, real Core loop)."""

import asyncio
import json

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

WRITER = ("printf 'checked\\n' > result.txt; "
          "nohup sh -c 'sleep 1; for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do echo late-$i >> result.txt; "
          "sleep 0.4; done' > /dev/null 2>&1 &")


def run(tmp_path, command, settle):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([
        call("terminal", {"input": command, "wait_s": 0.5}, "write"),
        call("finish", {"summary": "result.txt is written and checked."}, "first"),
        call("finish", {"summary": "Finishing as it is."}, "second"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Write result.txt.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(trace), timeout_s=60,
        config=CoreConfig(finish_settle=settle, control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    return result, client, rows


def test_changing_delivered_file_holds_the_first_finish_once(tmp_path):
    result, client, rows = run(tmp_path, WRITER, settle=True)
    assert result.status == "finished"
    assert len(client.requests) == 3  # the first finish came back to the model, the second ended the work
    tools = [m for m in client.requests[2]["messages"] if m["role"] == "tool"]
    held = tools[-1]["content"]
    assert "still changing" in held and "result.txt" in held
    assert "sleep" in held or "sh -c" in held  # the writer is named among running processes
    (settle,) = [r for r in rows if r["event"] == "finish_settle"]
    assert settle["status"] == "changing" and settle["changed"][0]["path"].endswith("/result.txt")
    assert result.extras["finish_settle"]["status"] == "changing"  # the run record keeps the measurement
    assert result.extras["switches"]["finish_settle"] is True


def test_switch_off_finishes_at_the_first_request(tmp_path):
    result, client, rows = run(tmp_path, WRITER, settle=False)
    assert result.status == "finished" and len(client.requests) == 2
    assert not [r for r in rows if r["event"] == "finish_settle"]


def test_settled_delivery_is_not_held(tmp_path):
    result, client, rows = run(tmp_path, "printf 'done\\n' > result.txt", settle=True)
    assert result.status == "finished" and len(client.requests) == 2
    (settle,) = [r for r in rows if r["event"] == "finish_settle"]
    assert settle["status"] == "settled" and settle["files"] == 1

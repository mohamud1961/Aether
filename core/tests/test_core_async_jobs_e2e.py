"""Background jobs in named terminals and selected completion waits (real Linux shells, real Core loop).

Each completion is delivered once, with its own exit and output; a wait returns as soon as its selection is
satisfied; a timeout names what is still running; other terminals keep running.
"""

import asyncio
import json
import os
import time

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv, ScriptedClient, call

pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="native Linux shell qualification"
)


def controller(tmp_path):
    return Terminals(LocalEnv(tmp_path), str(tmp_path), lambda: 1000.0,
                     control_dir=str(tmp_path / "ctl"), preserve_existing=True)


def test_any_returns_the_first_finisher_and_all_collects_the_rest_once(tmp_path):
    async def go():
        t = controller(tmp_path)
        try:
            assert "still running" in await t.use(name="slow", input="sleep 1.5; echo slow-out", wait_s=0.1)
            assert "still running" in await t.use(name="fast", input="sleep 0.3; echo fast-out; (exit 2)",
                                                  wait_s=0.1)
            started = time.monotonic()
            first = await t.wait_events(["slow", "fast"], mode="any", wait_s=10)
            assert time.monotonic() - started < 1.2  # did not wait for the slow job
            assert [(c["name"], c["exit"]) for c in first["completed"]] == [("fast", 2)]
            assert "fast-out" in first["completed"][0]["observation"] and first["pending"] == ["slow"]
            rest = await t.wait_events(["slow", "fast"], mode="all", wait_s=10)
            assert [(c["name"], c["exit"]) for c in rest["completed"]] == [("slow", 0)]
            assert "slow-out" in rest["completed"][0]["observation"]
            assert [u["name"] for u in rest["unknown"]] == ["fast"]  # already delivered, never twice
            again = await t.wait_events(["slow"], mode="all", wait_s=0)
            assert not again["completed"] and again["unknown"][0]["reason"] == "no outstanding terminal command"
        finally:
            await t.close()

    asyncio.run(go())


def test_timeout_names_the_running_command_and_leaves_it_running(tmp_path):
    async def go():
        t = controller(tmp_path)
        try:
            await t.use(name="job", input="sleep 1; printf done > out", wait_s=0.1)
            timed = await t.wait_events(["job"], mode="all", wait_s=0.3)
            assert timed["pending"] == ["job"] and not timed["completed"] and not timed["unknown"]
            done = await t.wait_events(["job"], mode="all", wait_s=10)
            assert [(c["name"], c["exit"]) for c in done["completed"]] == [("job", 0)]
            assert (tmp_path / "out").read_text() == "done"
        finally:
            await t.close()

    asyncio.run(go())


def test_one_model_turn_waits_where_polling_would_take_several(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([
        call("terminal", {"name": "build", "input": "sleep 1.2; echo built > artifact; (exit 0)", "wait_s": 0.1},
             "start"),
        call("terminal_wait", {"names": ["build"], "mode": "all", "wait_s": 30}, "wait"),
        call("finish", {"summary": "artifact built."}, "done"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Build artifact.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(trace), timeout_s=60,
        config=CoreConfig(terminal_events=True, control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    assert result.status == "finished" and len(client.requests) == 3
    waited = [m for m in client.requests[2]["messages"] if m["role"] == "tool"][-1]["content"]
    body = json.loads(waited[: waited.rindex("}") + 1])
    assert [(c["name"], c["exit"]) for c in body["completed"]] == [("build", 0)]
    assert (work / "artifact").read_text() == "built\n"
    names = [t["function"]["name"] for t in client.requests[0]["tools"]]
    assert "terminal_wait" in names


def test_wait_tool_is_absent_in_stock(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([call("finish", {"summary": "nothing to do."}, "done")])
    asyncio.run(run_agent(
        env=LocalEnv(work), task="Nothing.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "t"), timeout_s=30,
        config=CoreConfig(control_dir=str(tmp_path / "control"), terminal_events=False),
    ))
    assert "terminal_wait" not in [t["function"]["name"] for t in client.requests[0]["tools"]]

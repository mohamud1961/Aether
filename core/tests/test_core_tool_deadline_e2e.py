"""One deadline: a hanging host-side tool call cannot outlive the task's time limit (real Core loop, stock).

The browser sidecar's start is a host ``docker run`` with its own 300 s limit, outside the sandbox deadline. Here it
hangs for 60 s in a run whose work time is 5 s (20 s limit minus the 15 s stop margin). The run-wide timeout around
the loop (loop.py, ``asyncio.timeout(s.remaining())``) already cuts it: no switch is needed. Checked here so that a
change dropping that bound fails.
"""

import asyncio
import time

from aether.core import browser
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


def test_a_hanging_host_call_stops_at_the_task_deadline(tmp_path, monkeypatch):
    entered = []

    async def hang(self, life_s):
        entered.append(time.monotonic())
        await asyncio.sleep(60)

    async def factory(env):
        return "c" * 64

    monkeypatch.setattr(browser.Sidecar, "start", hang)
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([
        call("browser", {"code": "print(1)"}, "slow"),
        call("finish", {"summary": "Done."}, "finish"),
    ])
    started = time.monotonic()
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Use the browser.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=20, config=CoreConfig(browser=factory, control_dir=str(tmp_path / "control")),
    ))
    elapsed = time.monotonic() - started
    assert entered, "the browser call never reached the hanging start: the test proves nothing"
    assert 3 <= elapsed < 15
    assert result.status == "timeout"

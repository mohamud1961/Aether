"""Real-file integration checks for background handles and ordered read batches."""

import asyncio
import json

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core.core_fakes import LocalEnv, ScriptedClient, call, chunk, tool_chunk


def test_background_terminal_handle_is_polled_without_repeating_the_command(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient(
        [
            call(
                "terminal",
                {
                    "name": "build",
                    "input": "sleep 1; echo completed >> count.txt",
                    "wait_s": 0,
                },
                "c1",
            ),
            call("terminal", {"name": "other", "input": "echo independent"}, "c2"),
            call("terminal", {"name": "build", "input": "", "wait_s": 5}, "c3"),
            call("finish", {"summary": "done"}, "c4"),
        ]
    )
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="run two jobs",
            workdir=str(work),
            provider=ChatProvider(client, model="scripted", params={}),
            timeout_s=30,
            trace=Trace(trace),
            config=CoreConfig(control_dir=str(tmp_path / "ctl")),
        )
    )
    tools = [
        r
        for r in map(json.loads, trace.read_text().splitlines())
        if r["event"] == "tool"
    ]
    assert "still running" in tools[0]["result"] and "build" in tools[0]["result"]
    assert "independent" in tools[1]["result"] and "exit 0" in tools[2]["result"]
    assert (
        result.status == "finished"
        and (work / "count.txt").read_text() == "completed\n"
    )


def test_parallel_reads_keep_call_ids_and_cannot_cross_a_write(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("before-a")
    (work / "b.txt").write_text("before-b")

    class RendezvousEnv(LocalEnv):
        """Two independent reads must be in flight; the real filesystem still supplies the values."""

        def __init__(self, root):
            super().__init__(root)
            self.reads = 0
            self.both = asyncio.Event()

        async def exec(self, command, **kwargs):
            if "awk 'END" in command and self.reads < 2:
                self.reads += 1
                if self.reads == 2:
                    self.both.set()
                await asyncio.wait_for(self.both.wait(), timeout=2)
            return await super().exec(command, **kwargs)

    batch = [
        tool_chunk("read_file", {"path": "a.txt"}, 0, "a"),
        tool_chunk("read_file", {"path": "b.txt"}, 1, "b"),
        tool_chunk("write_file", {"path": "a.txt", "content": "after-a"}, 2, "write"),
        tool_chunk("read_file", {"path": "a.txt"}, 3, "after"),
        chunk(finish="tool_calls"),
    ]
    client = ScriptedClient([batch, call("finish", {"summary": "done"})])
    result = asyncio.run(
        run_agent(
            env=RendezvousEnv(work),
            task="read then change",
            workdir=str(work),
            provider=ChatProvider(client, model="scripted", params={}),
            timeout_s=30,
            trace=Trace(tmp_path / "trace"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), parallel_reads=True),
        )
    )
    replies = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in replies] == ["a", "b", "write", "after"]
    assert "before-a" in replies[0]["content"] and "before-b" in replies[1]["content"]
    assert "after-a" in replies[3]["content"] and result.status == "finished"
    assert CoreConfig().parallel_reads is False

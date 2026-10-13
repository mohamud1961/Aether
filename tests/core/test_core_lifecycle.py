"""Fault controls at the complete run interface: no provider calls."""

import asyncio

import pytest

from aether.core import loop
from aether.core.calls import CallLog
from aether.core.provider import ChatProvider, ProviderError
from aether.core.repl import Repl
from aether.core.terminal import Terminals
from tests.core.core_fakes import LocalEnv, ScriptedClient, call, tool_chunk


def test_startup_failure_after_repl_launch_still_closes_the_process(
    tmp_path, monkeypatch
):
    original = Repl.start
    instances = []

    async def start(self):
        await original(self)
        instances.append(self)
        assert self.pid
        raise RuntimeError("startup fault after process launch")

    monkeypatch.setattr(Repl, "start", start)
    work = tmp_path / "work"
    work.mkdir()
    try:
        result = asyncio.run(
            loop.run_agent(
                env=LocalEnv(work),
                task="task",
                workdir=str(work),
                provider=ChatProvider(ScriptedClient([]), model="scripted", params={}),
                timeout_s=60,
                trace=loop.Trace(tmp_path / "trace"),
                config=loop.CoreConfig(
                    repl=True, control_dir=str(tmp_path / "control path")
                ),
            )
        )
        assert result.status == "environment_error" and "startup fault" in result.error
        assert instances[0].pid == 0
    finally:  # baseline failure must not leave the real diagnostic process behind
        for instance in instances:
            asyncio.run(instance.close())


def test_cleanup_continues_when_another_closer_fails(tmp_path, monkeypatch):
    closed = []

    async def terminal_close(self):
        raise OSError("terminal cleanup failure")

    async def repl_close(self):
        closed.append("repl")

    monkeypatch.setattr(Terminals, "close", terminal_close)
    monkeypatch.setattr(Repl, "close", repl_close)
    work = tmp_path / "work"
    work.mkdir()
    result = asyncio.run(
        loop.run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=ChatProvider(
                ScriptedClient([call("finish", {"summary": "done"})]),
                model="scripted",
                params={},
            ),
            timeout_s=60,
            trace=loop.Trace(tmp_path / "trace"),
            config=loop.CoreConfig(control_dir=str(tmp_path / "control")),
        )
    )
    assert closed == ["repl"] and result.extras["cleanup_errors"]


def test_transfer_cannot_outlive_total_work_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "STOP_MARGIN_S", 0.05)

    class BlockUpload(LocalEnv):
        async def upload_file(self, source_path, target_path):
            await asyncio.Event().wait()

    work = tmp_path / "work"
    work.mkdir()

    async def run():
        return await asyncio.wait_for(
            loop.run_agent(
                env=BlockUpload(work),
                task="task",
                workdir=str(work),
                provider=ChatProvider(
                    ScriptedClient(
                        [call("write_file", {"path": "out", "content": "x" * 60000})]
                    ),
                    model="scripted",
                    params={},
                ),
                timeout_s=0.25,
                trace=loop.Trace(tmp_path / "trace"),
                config=loop.CoreConfig(control_dir=str(tmp_path / "control")),
            ),
            timeout=1.0,
        )

    result = asyncio.run(run())
    assert result.status == "timeout" and not (work / "out").exists()


def test_early_stream_eof_is_not_a_successful_executable_call(tmp_path):
    provider = ChatProvider(
        ScriptedClient([[tool_chunk("write_file", {"path": "x", "content": "wrong"})]]),
        model="scripted",
        params={},
        log=CallLog(tmp_path / "calls"),
    )
    with pytest.raises(ProviderError, match="finish"):
        asyncio.run(provider.complete([], [], max_tokens=10, remaining_s=lambda: 10))
    assert provider.log.totals()["all"]["failed"] == 1

"""Separate provider multi-call exposure from Core's execution of independent reads."""

import asyncio
from dataclasses import replace

import pytest

from aether.core.harbor_agent import build_config, build_provider
from aether.core.harbor_config import ConfigError
from aether.core.loop import Trace, run_agent
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk, tool_chunk


class TimedReads(LocalEnv):
    def __init__(self, work):
        super().__init__(work)
        self.in_flight = 0
        self.peak = 0

    async def exec(self, command, **kwargs):
        if "awk -v total_file" not in command:
            return await super().exec(command, **kwargs)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(0.2)
            return await super().exec(command, **kwargs)
        finally:
            self.in_flight -= 1


def test_many_calls_does_not_hide_invalid_parallel_read_configuration():
    with pytest.raises(ConfigError, match="AETHER_CORE_PARALLEL_READS"):
        build_provider(environ={
            "AETHER_FW_GLM_53_FLASH_ENDPOINT": "http://127.0.0.1:1",
            "AETHER_FW_GLM_53_FLASH_KEY": "unused",
            "AETHER_FW_GLM_53_FLASH_DEPLOYMENT": "scripted",
            "AETHER_CORE_CALLS": "many",
            "AETHER_CORE_PARALLEL_READS": "invalid",
        })


@pytest.mark.parametrize("grouped,expected_peak", [(False, 1), (True, 2)])
def test_identical_multi_call_request_produces_the_same_artifact(grouped, expected_peak, tmp_path, monkeypatch):
    import openai

    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("alpha\n")
    (work / "b.txt").write_text("beta\n")
    batch = [
        tool_chunk("read_file", {"path": "a.txt"}, 0, "a"),
        tool_chunk("read_file", {"path": "b.txt"}, 1, "b"),
        chunk(finish="tool_calls"),
    ]
    client = ScriptedClient([
        batch, call("terminal", {"input": "cat a.txt b.txt > combined.txt"}, "combine"),
        call("finish", {"summary": "done"}, "finish"),
    ])
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: client)
    environ = {
        "AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "project", "AETHER_CORE_REPL": "off",
        "AETHER_CORE_IMAGES": "off", "AETHER_CORE_CALLS": "many",
        "AETHER_CORE_PARALLEL_READS": "on" if grouped else "off",
        "AETHER_FW_GLM_53_FLASH_ENDPOINT": "http://127.0.0.1:1",
        "AETHER_FW_GLM_53_FLASH_KEY": "unused", "AETHER_FW_GLM_53_FLASH_DEPLOYMENT": "scripted",
    }
    config = replace(build_config(environ=environ), control_dir=str(tmp_path / "control"))
    env = TimedReads(work)
    result = asyncio.run(run_agent(
        env=env, task="Combine a.txt and b.txt.", workdir=str(work),
        provider=build_provider(environ=environ), timeout_s=60, trace=Trace(tmp_path / "trace"),
        config=config,
    ))
    assert client.requests[0]["parallel_tool_calls"] is True
    replies = [item for item in client.requests[1]["messages"] if item["role"] == "tool"]
    assert [item["tool_call_id"] for item in replies] == ["a", "b"]
    assert "alpha" in replies[0]["content"] and "beta" in replies[1]["content"]
    assert env.peak == expected_peak
    assert result.status == "finished" and (work / "combined.txt").read_text() == "alpha\nbeta\n"

"""Fast MCP waits keep real effects, error reporting and retry ownership truthful."""

import asyncio
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import sys
import time

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.harbor_config import build_config
from aether.core.mcp import Mcp
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="MCP daemon requires Linux /proc")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))


def restricted_path(tmp_path, monkeypatch, mode):
    bindir = tmp_path / "commands"
    bindir.mkdir()
    for directory in (Path("/usr/local/bin"), Path("/usr/bin"), Path("/bin")):
        if not directory.is_dir():
            continue
        for executable in directory.iterdir():
            if (executable.name.startswith("python") or (mode == "no_timeout" and executable.name == "timeout")
                    or not os.access(executable, os.X_OK)):
                continue
            link = bindir / executable.name
            if not link.exists():
                link.symlink_to(executable)
    if mode in ("broken", "empty"):
        (bindir / "python3").symlink_to("/bin/false" if mode == "broken" else "/bin/true")
    elif mode == "no_timeout":
        (bindir / "python3").symlink_to(sys.executable)
    elif mode in ("partial", "malformed", "hanging", "premature", "stubborn", "wrong_id"):
        python = bindir / "python3"
        if mode == "hanging":
            python.write_text("#!/bin/sh\nexec sleep 30\n")
        elif mode == "stubborn":
            python.write_text("#!/bin/sh\necho $$ >> " + shlex.quote(str(bindir / "stubborn-pids")) +
                              "\ntrap '' TERM\nexec sleep 30\n")
        else:
            output = {"partial": "not a complete response", "malformed": "not-json\\n__AETHER_MCP_WAIT_COMPLETE__",
                      "premature": "\\n__AETHER_MCP_WAIT_COMPLETE__",
                      "wrong_id": '{"id":999}\\n__AETHER_MCP_WAIT_COMPLETE__'}[mode]
            python.write_text("#!/bin/sh\nprintf '" + output + "'\n")
        python.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))


@pytest.mark.parametrize("mode", ["healthy", "missing", "no_timeout", "broken", "empty", "partial", "malformed",
                                  "premature", "hanging", "stubborn", "wrong_id"])
def test_fast_wait_or_fallback_delivers_each_real_effect_once(tmp_path, monkeypatch, mode):
    if mode in ("hanging", "stubborn") and not shutil.which("timeout"):
        pytest.skip("the bounded-interpreter failure case requires timeout")
    effect = tmp_path / "effect"
    spec = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}
    base = {"server": "fx", "action": "call"}
    original_path = os.environ["PATH"]

    async def scenario():
        client = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [spec], adopt=True, fast_wait=True)
        try:
            assert (await client.use({**base, "tool": "count"}, 60)).startswith("count=1")
            if mode != "healthy":
                restricted_path(tmp_path, monkeypatch, mode)
            args = {**base, "tool": "effect", "arguments": {"path": str(effect), "delay": 0}}
            assert "effect-done" in await client.use(args, 60)
            assert "effect-done" in await client.use(args, 60)
            assert effect.read_bytes() == b"xx"  # a deliberate second call is a new effect
            assert "[the tool reported an error]" in await client.use({**base, "tool": "fail"}, 60)
            records = [row for row in client.calls if row["tool"] == "effect"]
            assert all(row["fast_wait"] for row in records)
            assert all((row["wait_fallbacks"] == 0) == (mode == "healthy") for row in records)
            session = Path(client.started["fx"])
            assert len(list(session.glob("req_*.json"))) == 4
            if mode == "stubborn":
                for pid in (tmp_path / "commands/stubborn-pids").read_text().splitlines():
                    proc = Path("/proc") / pid / "stat"
                    if proc.exists():
                        assert proc.read_text().rsplit(")", 1)[1].split()[0] in ("Z", "X")
        finally:
            # The fault targets the wait observer, not the separate process-tree cleanup observer.
            monkeypatch.setenv("PATH", original_path)
            await client.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("lost_after_execution", [False, True])
def test_lost_observer_reply_falls_back_without_a_second_effect(tmp_path, lost_after_execution):
    class LostObserver(LocalEnv):
        armed = False

        async def exec(self, command, **kwargs):
            if self.armed and '__AETHER_MCP_WAIT_COMPLETE__' in command:
                self.armed = False
                if lost_after_execution:
                    await super().exec(command, **kwargs)
                raise ConnectionError('observer reply lost')
            return await super().exec(command, **kwargs)

    effect = tmp_path / 'effect'
    spec = {'name': 'fx', 'transport': 'stdio', 'command': sys.executable, 'args': [FIXTURE, 'stdio']}

    async def scenario():
        env = LostObserver(tmp_path)
        client = Mcp(env, str(tmp_path / 'control'), [spec], adopt=True, fast_wait=True)
        try:
            await client.use({'server': 'fx', 'action': 'call', 'tool': 'count'}, 60)
            env.armed = True
            output = await client.use({'server': 'fx', 'action': 'call', 'tool': 'effect',
                                       'arguments': {'path': str(effect), 'delay': 0}}, 60)
            assert output.count('effect-done') == 1 and effect.read_bytes() == b'x'
            assert client.calls[-1]['wait_fallbacks'] >= 1
            assert len(list(Path(client.started['fx']).glob('req_*.json'))) == 2
        finally:
            await client.close()

    asyncio.run(scenario())


def test_broken_observer_does_not_extend_request_deadline(tmp_path, monkeypatch):
    if not shutil.which("timeout"):
        pytest.skip("the bounded-interpreter failure case requires timeout")
    effect = tmp_path / "effect"
    spec = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}
    original_path = os.environ["PATH"]

    async def scenario():
        client = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [spec], adopt=True, fast_wait=True)
        try:
            await client.use({"server": "fx", "action": "call", "tool": "count"}, 60)
            restricted_path(tmp_path, monkeypatch, "stubborn")
            started = time.monotonic()
            result = await client.use({"server": "fx", "action": "call", "tool": "effect", "timeout_s": 1,
                                       "arguments": {"path": str(effect), "delay": 3}}, 60)
            assert "effect is unknown" in result and time.monotonic() - started < 2
            assert effect.read_bytes() == b"x"
        finally:
            monkeypatch.setenv("PATH", original_path)
            await client.close()

    asyncio.run(scenario())


def test_existing_cleanup_reports_unverified_if_python_is_broken(tmp_path, monkeypatch):
    spec = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}
    original_path = os.environ["PATH"]

    async def scenario():
        client = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [spec], adopt=True, fast_wait=True)
        try:
            await client.use({"server": "fx", "action": "call", "tool": "count"}, 60)
            restricted_path(tmp_path, monkeypatch, "broken")
            with pytest.raises(RuntimeError, match="cleanup unverified"):
                await client.close()
        finally:
            monkeypatch.setenv("PATH", original_path)
            await client.close()

    asyncio.run(scenario())


def test_fast_wait_preserves_unknown_effect_and_attaches_retry(tmp_path):
    effect = tmp_path / "effect"
    spec = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}
    args = {"server": "fx", "action": "call", "tool": "effect", "timeout_s": 1,
            "arguments": {"path": str(effect), "delay": 1.6}}

    async def scenario():
        client = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [spec], adopt=True, fast_wait=True)
        try:
            started = time.monotonic()
            first = await client.use(args, 60)
            assert "effect is unknown" in first and time.monotonic() - started < 4
            second = await client.use({**args, "timeout_s": 5}, 60)
            assert "matches MCP request #1" in second and "effect-done" in second
            assert effect.read_bytes() == b"x"
            assert len(list(Path(client.started["fx"]).glob("req_*.json"))) == 1
        finally:
            await client.close()

    asyncio.run(scenario())


def test_fast_wait_reports_unknown_if_client_dies_during_real_effect(tmp_path):
    effect = tmp_path / "effect"
    spec = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}

    async def scenario():
        client = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [spec], adopt=True, fast_wait=True)
        try:
            await client.use({"server": "fx", "action": "call", "tool": "count"}, 60)
            owner = int((Path(client.started["fx"]) / "owner").read_text().split()[0])
            pending = asyncio.create_task(client.use({"server": "fx", "action": "call", "tool": "effect",
                "arguments": {"path": str(effect), "delay": 2}}, 60))
            for _ in range(100):
                if effect.exists():
                    break
                await asyncio.sleep(0.02)
            assert effect.read_bytes() == b"x"
            os.kill(owner, signal.SIGKILL)
            result = await asyncio.wait_for(pending, timeout=8)
            assert "effect is unknown" in result
            assert len(list(Path(client.launched[0]).glob("req_*.json"))) == 2
        finally:
            await client.close()

    asyncio.run(scenario())


def test_fast_wait_is_wired_through_the_real_core_loop(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    effect = work / "effect"
    spec = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}
    client = ScriptedClient([
        call("mcp", {"server": "fx", "action": "call", "tool": "effect",
                     "arguments": {"path": str(effect), "delay": 0}}, "effect"),
        call("finish", {"summary": "done"}, "finish"),
    ])
    trace = tmp_path / "trace.jsonl"
    settings = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "project", "AETHER_CORE_REPL": "off",
                "AETHER_CORE_IMAGES": "off", "AETHER_CORE_START_COPY": "off"}
    assert not build_config(environ=settings).fast_mcp_wait
    assert build_config(environ={**settings, "AETHER_CORE_FAST_MCP_WAIT": "on"}).fast_mcp_wait
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Run the declared operation once.", workdir=str(work),
        provider=ChatProvider(client, model="scripted", params={}), trace=Trace(trace), timeout_s=60,
        config=CoreConfig(mcp_servers=(spec,), terminal_events=True, fast_mcp_wait=True,
                          control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    assert result.status == "finished" and effect.read_bytes() == b"x"
    assert result.extras["mcp_calls"][0]["fast_wait"] is True
    assert next(json.loads(line) for line in trace.read_text().splitlines()
                if json.loads(line)["event"] == "start")["fast_mcp_wait"] is True
    seen = next(message["content"] for message in client.requests[-1]["messages"]
                if message.get("tool_call_id") == "effect")
    assert "effect-done" in seen

"""Task-declared MCP servers through the mcp tool (real MCP server process, real sandbox client, real Core loop)."""

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.mcp import Mcp
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(kind):
    port = free_port()
    proc = subprocess.Popen([sys.executable, FIXTURE, kind, str(port)])
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    return proc, port


def run(tmp_path, servers, calls):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([*calls, call("finish", {"summary": "done."}, "done")])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Use the browser server.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=90, config=CoreConfig(mcp_servers=tuple(servers), control_dir=str(tmp_path / "control"),
                                        end_processes="stop"),
    ))
    tools = [m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
    return result, client, tools


STEPS = [
    call("mcp", {"server": "fx", "action": "list"}, "list"),
    call("mcp", {"server": "fx", "action": "call", "tool": "count"}, "c1"),
    call("mcp", {"server": "fx", "action": "call", "tool": "count"}, "c2"),
    call("mcp", {"server": "fx", "action": "call", "tool": "shot"}, "img"),
    call("mcp", {"server": "fx", "action": "call", "tool": "fail"}, "bad"),
    call("mcp", {"server": "fx", "action": "call", "tool": "nope"}, "unknown"),
]


@pytest.mark.parametrize("transport", ["sse", "streamable-http", "stdio"])
def test_declared_server_tools_listed_and_called_with_one_persistent_session(tmp_path, transport):
    proc = None
    if transport == "stdio":
        spec = {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable, "args": [FIXTURE, "stdio"]}
    else:
        proc, port = serve("sse" if transport == "sse" else "http")
        path = "/sse" if transport == "sse" else "/mcp"
        spec = {"name": "fx", "transport": transport, "url": f"http://127.0.0.1:{port}{path}", "command": None, "args": []}
    try:
        result, client, (listed, c1, c2, img, bad, unknown) = run(tmp_path, [spec], STEPS)
    finally:
        if proc:
            proc.kill()
    assert result.status == "finished"
    assert not result.extras["cleanup_errors"]
    assert "mcp" in [t["function"]["name"] for t in client.requests[0]["tools"]]
    assert listed.startswith("5 tools:") and "- count: Increment" in listed
    assert c1.startswith("count=1") and c2.startswith("count=2")  # the same server session across calls
    assert "here" in img and "[image returned by the server, saved at " in img
    image = img.split("saved at ")[1].split("]")[0]
    assert Path(image).read_bytes().startswith(b"\x89PNG")
    assert bad.startswith("[the tool reported an error]") and "it broke" in bad
    assert unknown.startswith("error: MCP") and "unknown tool nope" in unknown
    assert [c["tool"] for c in result.extras["mcp_calls"]] == [None, "count", "count", "shot", "fail", "nope"]


def test_unreachable_server_is_a_reported_error_not_a_hang(tmp_path):
    spec = {"name": "fx", "transport": "sse", "url": f"http://127.0.0.1:{free_port()}/sse", "command": None, "args": []}
    started = time.monotonic()
    result, _, (listed, *_rest) = run(tmp_path, [spec], STEPS[:1])
    assert result.status == "finished" and time.monotonic() - started < 30
    assert listed.startswith("error:") and "fx" in listed


def test_declared_tool_receives_its_arguments_through_the_core_loop(tmp_path):
    artifact = tmp_path / "effect"
    spec = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}
    args = {"server": "fx", "action": "call", "tool": "effect"}
    result, _, (bad, good) = run(tmp_path, [spec], [
        call("mcp", {**args, "arguments": [], "timeout_s": 5}, "bad-object"),
        call("mcp", {**args, "arguments": {"path": str(artifact), "delay": 0}, "timeout_s": 5}, "effect"),
    ])
    assert result.status == "finished"
    assert "expected object" in bad
    assert good.startswith("effect-done")
    assert artifact.read_bytes() == b"x"
    assert [record["tool"] for record in result.extras["mcp_calls"]] == ["effect"]


def test_no_declared_servers_no_tool(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([call("finish", {"summary": "done."}, "done")])
    asyncio.run(run_agent(env=LocalEnv(work), task="x", workdir=str(work),
                          provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "t"),
                          timeout_s=30, config=CoreConfig(control_dir=str(tmp_path / "control"))))
    assert "mcp" not in [t["function"]["name"] for t in client.requests[0]["tools"]]



def test_two_controller_sessions_do_not_share_reply_or_cleanup_ownership(tmp_path):
    first = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}
    second = {**first, "args": ["-c", "raise SystemExit(7)"]}
    args = {"server": "fx", "action": "call", "tool": "count"}

    async def scenario():
        prior = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [first], adopt=False)
        later = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [second], adopt=False)
        try:
            assert (await prior.use(args, 60)).startswith("count=1")
            with pytest.raises(RuntimeError, match="client initialization failed"):
                await later.use(args, 60)
            await later.close()
            assert (await prior.use(args, 60)).startswith("count=2")
        finally:
            await prior.close()

    asyncio.run(scenario())


def test_a_lost_image_materialization_reuses_the_mcp_response(tmp_path):
    class LostImage(LocalEnv):
        dropped = False

        async def exec(self, command, **kwargs):
            result = await super().exec(command, **kwargs)
            if not self.dropped and "image_1_1.png" in command:
                self.dropped = True
                raise ConnectionError("image staging reply lost")
            return result

    async def scenario():
        spec = {"name": "fx", "transport": "stdio", "command": sys.executable, "args": [FIXTURE, "stdio"]}
        client = Mcp(LostImage(tmp_path), str(tmp_path / "control"), [spec], adopt=True)
        shot = {"server": "fx", "action": "call", "tool": "shot"}
        try:
            with pytest.raises(ConnectionError, match="image staging reply lost"):
                await client.use(shot, 60)
            recovered = await client.use(shot, 60)
            assert "matches MCP request #1" in recovered
            assert "image_1_1.png" in recovered
            assert sorted(p.name for p in Path(client.started["fx"]).glob("req_*.json")) == ["req_1.json"]
        finally:
            await client.close()

    asyncio.run(scenario())

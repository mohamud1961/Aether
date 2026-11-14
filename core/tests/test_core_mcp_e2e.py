"""Task-declared MCP servers through the mcp tool (real MCP server process, real sandbox client, real Core loop)."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
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
    assert "mcp" in [t["function"]["name"] for t in client.requests[0]["tools"]]
    assert listed.startswith("3 tools:") and "- count: Increment" in listed
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


def test_no_declared_servers_no_tool(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([call("finish", {"summary": "done."}, "done")])
    asyncio.run(run_agent(env=LocalEnv(work), task="x", workdir=str(work),
                          provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "t"),
                          timeout_s=30, config=CoreConfig(control_dir=str(tmp_path / "control"))))
    assert "mcp" not in [t["function"]["name"] for t in client.requests[0]["tools"]]

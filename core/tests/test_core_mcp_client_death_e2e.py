"""A3 + A14: the MCP client daemon dies mid-run (real stdio MCP server and client, SIGKILL to the daemon).

A3 (always on): the death is noticed while the request waits, not at the wait's deadline. A request the dead client
never took is cancelled for certain and sent once on a new client; one it took without answering is stated as effect
unknown, and the server is served by a new client afterwards. Known-bad: without the liveness check the call waits
out its whole timeout and reports only "no result".

A14 (switch, off by default): the identical retry after an unknown effect carries the first call's idempotency key,
and a server that honours keys (the fixture keeps them durably) applies the effect once. Known-bad: with the switch
off the same retry applies it a second time.
"""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from aether.core import mcp as mcp_mod
from aether.core.mcp import Mcp
from tests.core_fault_sweep import CutExecs

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))


def spec():
    return {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable, "args": [FIXTURE, "stdio"]}


def kill_client(mcp):
    owner = Path(mcp.started["fx"], "owner").read_text().split()
    os.kill(int(owner[0]), signal.SIGKILL)


async def effects_after(path, at_least=1, within=10.0):
    end = time.monotonic() + within
    while time.monotonic() < end:
        if path.exists() and len(path.read_text()) >= at_least:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("the effect never happened")


def intent(tmp_path, delay, timeout_s=30):
    return {"server": "fx", "action": "call", "tool": "effect",
            "arguments": {"path": str(tmp_path / "effects"), "delay": delay}, "timeout_s": timeout_s}


async def died_before_taking(tmp_path):
    mcp = Mcp(CutExecs(tmp_path, None, None), str(tmp_path / "control"), [spec()])
    try:
        assert (await mcp.use({"server": "fx", "action": "list"}, 120)).startswith("4 tools:")
        kill_client(mcp)
        await asyncio.sleep(0.3)
        began = time.monotonic()
        out = await mcp.use(intent(tmp_path, 0, timeout_s=8), 120)
        return out, time.monotonic() - began, (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
    finally:
        await mcp.close()


async def died_after_sending(tmp_path, idempotency):
    mcp = Mcp(CutExecs(tmp_path, None, None), str(tmp_path / "control"), [spec()], idempotency=idempotency)
    try:
        assert (await mcp.use({"server": "fx", "action": "list"}, 120)).startswith("4 tools:")
        call = asyncio.ensure_future(mcp.use(intent(tmp_path, 6), 120))
        await effects_after(tmp_path / "effects")
        kill_client(mcp)
        began = time.monotonic()
        first = await call
        waited = time.monotonic() - began
        # Idempotency applies to an identical intent, including its arguments.
        retry = await mcp.use(intent(tmp_path, 6), 120)
        return first, waited, retry, len((tmp_path / "effects").read_text())
    finally:
        await mcp.close()


def test_a_request_the_dead_client_never_took_is_sent_once_on_a_new_client(tmp_path):
    out, seconds, effects = asyncio.run(died_before_taking(tmp_path))
    assert "was never sent" in out and "effect-done" in out, out
    assert effects == "x" and seconds < 6, (effects, seconds)


def test_known_bad_without_the_liveness_check_the_call_waits_out_its_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_mod, "LIVENESS_EVERY_S", 1e9)
    out, seconds, effects = asyncio.run(died_before_taking(tmp_path))
    assert "no result after" in out and effects == "" and seconds >= 8, (out, seconds)


def test_a_request_taken_before_the_death_is_stated_as_unknown_and_the_server_keeps_working(tmp_path):
    first, waited, retry, effects = asyncio.run(died_after_sending(tmp_path, idempotency=False))
    assert "effect is unknown" in first and "effect-done" not in first and waited < 4, (first, waited)
    assert "effect-done" in retry  # a new client serves the server
    assert effects == 2  # known-bad for A14: without a key the retry applies the effect again


def test_with_idempotency_keys_the_retry_after_an_unknown_effect_applies_it_once(tmp_path):
    first, waited, retry, effects = asyncio.run(died_after_sending(tmp_path, idempotency=True))
    assert "effect is unknown" in first and waited < 4, first
    assert "idempotency key of MCP request #2" in retry and "effect-done" in retry, retry
    assert effects == 1

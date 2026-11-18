"""A11/A14: a restarted controller finds the earlier MCP client dead and reads its session back (real server and client).

The first controller is dropped without close() and its client daemon is killed, so neither can report anything.
Before 15 Nov the new controller saw a dead owner, started a fresh client and said nothing: an answer nobody saw was
lost, an effect that may have happened was never stated, and an identical retry ran the tool again without the earlier
call's idempotency key.
"""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from aether.core import mcp_adopt
from aether.core.mcp import Mcp
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))
SPEC = {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable, "args": [FIXTURE, "stdio"]}


def controller(tmp_path, idempotency=True):
    mcp = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [SPEC], adopt=True, idempotency=idempotency)
    mcp.conversation = set()
    mcp.delivery_tag = lambda: "call_x"
    return mcp


def kill_client(session: str) -> None:
    pid = int(Path(session, "owner").read_text().split()[0])
    os.kill(pid, signal.SIGKILL)
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)


def effect(effects, delay):
    return {"server": "fx", "action": "call", "tool": "effect", "arguments": {"path": str(effects), "delay": delay}}


def taken_then_dead(tmp_path):
    """The client takes a slow effect call and dies before answering; a new controller retries the identical call."""
    effects = tmp_path / "effects"

    async def go():
        first = controller(tmp_path)
        assert "no result after" in await first.use({**effect(effects, 3.0), "timeout_s": 0.5}, 60)
        kill_client(first.started["fx"])
        del first
        second = controller(tmp_path)
        try:
            retried = await second.use({**effect(effects, 3.0), "timeout_s": 10.0}, 60)  # identical call
            await asyncio.sleep(3.5)  # an orphaned server run of the first call could still land
            return retried, len(effects.read_text()) if effects.exists() else 0
        finally:
            await second.close()

    return asyncio.run(go())


def test_an_effect_taken_by_the_dead_client_is_stated_unknown_and_the_retry_reuses_its_key(tmp_path):
    retried, effects = taken_then_dead(tmp_path)
    assert effects == 1  # the server honoured the reused key: one effect
    assert "of an earlier controller was taken by its client" in retried and "effect is unknown" in retried, retried
    assert "idempotency key of MCP request #1" in retried, retried


def test_known_bad_without_read_back_the_restart_says_nothing(tmp_path, monkeypatch):
    async def nothing(*args, **kwargs):
        return None
    monkeypatch.setattr(mcp_adopt, "_read_back", nothing)
    retried, effects = taken_then_dead(tmp_path)
    assert effects == 2  # a fresh key: the tool ran again
    assert "earlier controller" not in retried and "idempotency key of MCP request" not in retried, retried


def test_an_answer_the_dead_client_wrote_is_shown_once(tmp_path):
    effects = tmp_path / "effects"

    async def go():
        first = controller(tmp_path)
        assert "no result after" in await first.use({**effect(effects, 2.0), "timeout_s": 1.0}, 60)  # 1 s is the floor
        session = first.started["fx"]
        for _ in range(200):
            if Path(session, "resp_1.json").exists():
                break
            await asyncio.sleep(0.05)
        kill_client(session)
        del first
        second = controller(tmp_path)
        try:
            shown = await second.use({"server": "fx", "action": "call", "tool": "count"}, 60)
        finally:
            await second.close()
        third = controller(tmp_path)
        third.conversation = {"call_x"}  # the continued conversation contains what the second controller showed
        try:
            again = await third.use({"server": "fx", "action": "call", "tool": "count"}, 60)
        finally:
            await third.close()
        return shown, again

    shown, again = asyncio.run(go())
    assert "answered before its client ended" in shown and "effect-done" in shown, shown
    assert "earlier controller" not in again, again  # delivered once, not restated by a later controller


def test_a_request_the_dead_client_never_took_is_cancelled_for_certain(tmp_path):
    async def go():
        first = controller(tmp_path)
        assert (await first.use({"server": "fx", "action": "call", "tool": "count"}, 60)).startswith("count=1")
        session = first.started["fx"]
        kill_client(session)
        # A published request the client never took (as when it dies between publication and pickup).
        body = {"id": 7, "method": "tools/call", "params": {"name": "count", "arguments": {}}}
        Path(session, "req_7.json").write_text(json.dumps(body))
        del first
        second = controller(tmp_path)
        try:
            shown = await second.use({"server": "fx", "action": "call", "tool": "count"}, 60)
        finally:
            await second.close()
        return shown, os.readlink(Path(session, "start_7"))

    shown, token = asyncio.run(go())
    assert "#7 (count) of an earlier controller was never sent" in shown, shown
    assert token == "revoked"

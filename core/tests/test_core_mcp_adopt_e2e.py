"""A restarted controller adopts the MCP client session the earlier one left running (real MCP server and client).

The first controller is dropped without close(), as a killed process leaves it: its client daemon and the server
session stay up. Its last request is still waiting for an answer.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from aether.core.mcp import Mcp
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))
SPEC = {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable, "args": [FIXTURE, "stdio"]}


def controller(tmp_path, adopt=True):
    mcp = Mcp(LocalEnv(tmp_path), str(tmp_path / "control"), [SPEC], adopt=adopt)
    mcp.conversation = set()
    return mcp


def scenario(tmp_path, adopt):
    effects = tmp_path / "effects"
    slow = {"server": "fx", "action": "call", "tool": "effect",
            "arguments": {"path": str(effects), "delay": 3.0}, "timeout_s": 1.0}

    async def go():
        first = controller(tmp_path, adopt)
        first.delivery_tag = lambda: "call_1"
        assert (await first.use({"server": "fx", "action": "call", "tool": "count"}, 60)).startswith("count=1")
        assert "no result after" in await first.use(slow, 60)
        del first  # the controller dies; its client and the server session do not

        second = controller(tmp_path, adopt)
        try:
            retried = await second.use({**slow, "timeout_s": 10.0}, 60)
            counted = await second.use({"server": "fx", "action": "call", "tool": "count"}, 60)
            await asyncio.sleep(3.5)  # let any second send finish
            return retried, counted, len(effects.read_text()) if effects.exists() else 0
        finally:
            await second.close()

    return asyncio.run(go())


def test_session_is_kept_and_an_unanswered_request_is_attached_not_resent(tmp_path):
    retried, counted, effects = scenario(tmp_path, adopt=True)
    assert "adopted from an earlier controller" in retried
    assert "not sent again" in retried and "effect-done" in retried
    assert counted.startswith("count=2")  # the same server session as the first controller
    assert effects == 1


def test_without_adoption_the_session_is_lost_and_the_request_runs_twice(tmp_path):
    """Known-bad: a fresh client per controller (the earlier behaviour)."""
    retried, counted, effects = scenario(tmp_path, adopt=False)
    assert counted.startswith("count=1")
    assert effects == 2

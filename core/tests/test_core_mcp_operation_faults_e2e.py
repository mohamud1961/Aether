"""Kill an MCP tool call at every exec and every step, and check the operation contract (real MCP server and client).

An MCP tool call has an effect outside the sandbox. The contract is the terminal one: at every kill point the tool
runs on the server at most once, at least once within a few turns, and its result reaches the model exactly once. The
simulated model is the most naive one: after any failure or unclear reply it sends the identical call again, until it
sees the tool's result.

``core_fault_sweep`` numbers every exec of the call (staging, publishing, each response poll) and cuts each before
each of its simple commands, or loses its reply. This sweep covers a surviving controller; a restarted controller
adopting the client session is covered in ``test_core_mcp_adopt_e2e.py``.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from aether.core.mcp import Mcp
from tests.core_fault_sweep import CutExecs, kill_points

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))
TURNS = 8


def spec():
    return {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable, "args": [FIXTURE, "stdio"]}


class Forgetful(Mcp):
    """Known-bad: forgets tracked requests before every use, as the untracked client did."""

    async def use(self, args, remaining):
        self.ops.clear()
        return await super().use(args, remaining)


async def scenario(tmp_path, target=None, cut=None, delay=1.0, timeout_s=60.0, client=Mcp):
    env = CutExecs(tmp_path, target, cut)
    effects = tmp_path / "effects"
    intent = {"server": "fx", "action": "call", "tool": "effect",
              "arguments": {"path": str(effects), "delay": delay}, "timeout_s": timeout_s}
    mcp = client(env, str(tmp_path / "control"), [spec()])
    shown: list[str] = []
    try:
        assert (await mcp.use({"server": "fx", "action": "list"}, 120)).startswith("4 tools:")
        env.armed = True
        try:
            shown.append(await mcp.use(intent, 120))
        except (ConnectionError, OSError, RuntimeError):  # the model sees a tool error and tries again
            pass
        env.fired = True
        for _ in range(TURNS):
            if any("effect-done" in out for out in shown):
                break
            shown.append(await mcp.use({**intent, "timeout_s": max(timeout_s, 3.0)}, 120))
        return {"effects": len(effects.read_text()) if effects.exists() else 0,
                "delivered": sum(out.count("effect-done") for out in shown), "shown": shown, "counts": env.counts}
    finally:
        await mcp.close()


def sweep(tmp_path, client=Mcp):
    (tmp_path / "discover").mkdir()
    found = asyncio.run(scenario(tmp_path / "discover", client=client))
    assert (found["effects"], found["delivered"]) == (1, 1)
    points = kill_points(found["counts"])
    assert len(found["counts"]) >= 3 and len(points) >= 8
    failures = []
    for n, (target, cut) in enumerate(points):
        case = tmp_path / f"p{n}"
        case.mkdir()
        got = asyncio.run(scenario(case, target, cut, client=client))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, cut, got["effects"], got["delivered"], got["shown"][-1][-200:] if got["shown"] else ""))
    return points, failures


def test_every_mcp_call_kill_point_runs_the_tool_once_and_delivers_it_once(tmp_path):
    points, failures = sweep(tmp_path)
    assert not failures, f"{len(failures)}/{len(points)} kill points broke the contract: {failures}"


def test_without_request_tracking_the_sweep_finds_a_second_tool_execution(tmp_path):
    _, failures = sweep(tmp_path, client=Forgetful)
    assert any(f[2] > 1 for f in failures), "no kill point repeated the external effect without tracking"


def test_a_call_that_outlives_its_wait_is_never_sent_twice_and_its_result_arrives_once(tmp_path):
    """The tool answers after 3 s; Core waits 1 s. Every identical retry must attach to the outstanding call."""
    got = asyncio.run(scenario(tmp_path, delay=3.0, timeout_s=1.0))
    assert "no result after" in got["shown"][0]
    assert (got["effects"], got["delivered"]) == (1, 1), got["shown"]

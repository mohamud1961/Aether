"""H7 portability for MCP: the operation-fault sweep and the dead-client readback through plain ``docker exec``.

The same contracts as ``test_core_mcp_operation_faults_e2e.py`` (every kill point of a tool call: the tool runs once and
its result reaches the model once) and ``test_core_mcp_dead_readback_e2e.py`` (a new controller reads back what a
killed client left: an answer shown once, an unknown effect stated, the idempotency key reused), with the client, the
fixture server and every file inside a container reached only through ``DockerExecEnv``.

Runs where a Docker daemon is reachable: AETHER_TEST_DOCKER_CONTEXT and AETHER_TEST_DOCKER_IMAGE (sh, bash, python3).
"""

import asyncio
import shlex
from pathlib import Path

import pytest

from aether.core import mcp_adopt
from aether.core.docker_env import DockerExecEnv
from aether.core.mcp import Mcp
from tests.core_fault_sweep import kill_points
from tests import test_core_docker_env_e2e as _env
from tests.test_core_docker_env_e2e import CTX, DOCKER, IMAGE, DockerCut

box = _env.box  # the shared container fixture

pytestmark = pytest.mark.skipif(not (CTX and IMAGE), reason="needs AETHER_TEST_DOCKER_CONTEXT and _IMAGE")
FIXTURE = Path(__file__).with_name("mcp_fixture_server.py")
TURNS = 8


async def _sh(env, command):
    return (await DockerExecEnv.exec(env, command)).stdout


async def _prepare(env, root):
    await DockerExecEnv.exec(env, f"mkdir -p {shlex.quote(root)}")
    await DockerExecEnv.upload_file(env, FIXTURE, f"{root}/fx.py")
    return {"name": "fx", "transport": "stdio", "url": None, "command": "python3", "args": [f"{root}/fx.py", "stdio"]}


async def _effects(env, root):
    return int((await _sh(env, f"cat {root}/effects 2>/dev/null | wc -c")).strip() or 0)


class Forgetful(Mcp):
    """Known-bad: forgets tracked requests before every use, as the untracked client did."""

    async def use(self, args, remaining):
        self.ops.clear()
        return await super().use(args, remaining)


async def scenario(box, root, target=None, cut=None, delay=1.0, timeout_s=60.0, client=Mcp):
    env = DockerCut(box, root, target, cut)
    spec = await _prepare(env, root)
    intent = {"server": "fx", "action": "call", "tool": "effect",
              "arguments": {"path": f"{root}/effects", "delay": delay}, "timeout_s": timeout_s}
    mcp = client(env, f"{root}/control", [spec])
    shown: list[str] = []
    try:
        assert (await mcp.use({"server": "fx", "action": "list"}, 120)).startswith("5 tools:")
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
        return {"effects": await _effects(env, root), "delivered": sum(o.count("effect-done") for o in shown),
                "shown": shown, "counts": env.counts}
    finally:
        env.armed = False
        await mcp.close()


def sweep(box, prefix, client=Mcp):
    found = asyncio.run(scenario(box, f"{prefix}/discover", client=client))
    assert (found["effects"], found["delivered"]) == (1, 1), found
    points = kill_points(found["counts"])
    assert len(found["counts"]) >= 3 and len(points) >= 8, found["counts"]
    failures = []
    for n, (target, cut) in enumerate(points):
        got = asyncio.run(scenario(box, f"{prefix}/p{n}", target, cut, client=client))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, cut, got["effects"], got["delivered"], got["shown"][-1][-200:] if got["shown"] else ""))
    return points, failures


def test_every_mcp_call_kill_point_through_docker_runs_the_tool_once_and_delivers_it_once(box):  # noqa: F811
    points, failures = sweep(box, "/m/tracked")
    print("H7-MCP-SWEEP", len(points), failures)
    assert not failures, f"{len(failures)}/{len(points)} kill points broke the contract: {failures}"


def test_through_docker_without_request_tracking_the_sweep_finds_a_second_tool_execution(box):  # noqa: F811
    _, failures = sweep(box, "/m/forgetful", client=Forgetful)
    assert any(f[2] > 1 for f in failures), "no kill point repeated the external effect without tracking"


def _controller(env, root, spec):
    mcp = Mcp(env, f"{root}/control", [spec], adopt=True, idempotency=True)
    mcp.conversation = set()
    mcp.delivery_tag = lambda: "call_x"
    return mcp


async def _kill_client(env, session):
    owner = (await _sh(env, f"cat {shlex.quote(session)}/owner")).split()[0]
    await DockerExecEnv.exec(env, f"kill -9 {int(owner)}; while kill -0 {int(owner)} 2>/dev/null; do sleep 0.05; done")


def _taken_then_dead(box, root):  # noqa: F811
    async def go():
        env = DockerExecEnv(box, docker=DOCKER)
        spec = await _prepare(env, root)
        call = {"server": "fx", "action": "call", "tool": "effect", "arguments": {"path": f"{root}/effects", "delay": 3.0}}
        first = _controller(env, root, spec)
        assert "no result after" in await first.use({**call, "timeout_s": 0.5}, 60)
        await _kill_client(env, first.started["fx"])
        del first
        second = _controller(env, root, spec)
        try:
            retried = await second.use({**call, "timeout_s": 10.0}, 60)  # identical call
            await asyncio.sleep(3.5)  # an orphaned server run of the first call could still land
            return retried, await _effects(env, root)
        finally:
            await second.close()

    return asyncio.run(go())


def test_through_docker_a_dead_clients_taken_effect_is_stated_unknown_and_its_key_reused(box):  # noqa: F811
    retried, effects = _taken_then_dead(box, "/m/dead")
    assert effects == 1, retried
    assert "of an earlier controller was taken by its client" in retried and "effect is unknown" in retried, retried
    assert "idempotency key of MCP request #1" in retried, retried


def test_through_docker_known_bad_without_read_back_runs_the_tool_twice(box, monkeypatch):  # noqa: F811
    async def nothing(*args, **kwargs):
        return None
    monkeypatch.setattr(mcp_adopt, "_read_back", nothing)
    retried, effects = _taken_then_dead(box, "/m/dead-bad")
    assert effects == 2, retried
    assert "earlier controller" not in retried, retried

"""H7 portability for the Python REPL: the every-exec fault sweep and controller adoption through plain ``docker exec``.

Same contracts as ``test_core_repl_operation_faults_e2e.py`` (any exec of a cell cut at every simple command or its
reply lost: the cell runs once and its output reaches the model once; the untracked stock protocol breaks it) and
``test_core_repl_adopt_e2e.py`` (a restarted controller adopts the running interpreter: variables kept, the unseen
cell shown once), with the interpreter and every file inside a container reached only through ``DockerExecEnv``.

Runs where a Docker daemon is reachable: AETHER_TEST_DOCKER_CONTEXT and AETHER_TEST_DOCKER_IMAGE (sh, bash, python3).
"""

import asyncio

import pytest

from aether.core.docker_env import DockerExecEnv
from aether.core.repl import Repl
from tests.core_fault_sweep import kill_points
from tests import test_core_docker_env_e2e as _env
from tests.test_core_docker_env_e2e import CTX, DOCKER, IMAGE, DockerCut

box = _env.box  # the shared container fixture

pytestmark = pytest.mark.skipif(not (CTX and IMAGE), reason="needs AETHER_TEST_DOCKER_CONTEXT and _IMAGE")
INTENT = "open('effects', 'a').write('x')\nimport time\ntime.sleep(1)\nprint('OPSM-' + 'RAN')"
TURNS = 8


async def scenario(box, root, target=None, cut=None, track=True):
    env = DockerCut(box, root, target, cut)
    await DockerExecEnv.exec(env, f"mkdir -p {root}")
    repl = Repl(env, root, lambda: 600.0, None, base=f"{root}/repl", track_operations=track)
    shown: list[str] = []
    assert await repl.start()
    try:
        assert "[python cell 1: ok" in await repl.run("pass", wait_s=10)
        env.armed, send = True, True
        for _ in range(TURNS + 1):
            try:
                out = await repl.run(INTENT if send else "", wait_s=2)
            except ConnectionError:
                send = True
                continue
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = "never started" in out
        env.armed = False
        effects = (await DockerExecEnv.exec(env, f"cat {root}/effects 2>/dev/null | wc -c")).stdout.strip()
        return {"effects": int(effects or 0), "delivered": sum(o.count("OPSM-RAN") for o in shown),
                "counts": env.counts, "last": shown[-1][-160:] if shown else ""}
    finally:
        env.armed = False
        await repl.close()


def sweep(box, prefix, track=True):
    found = asyncio.run(scenario(box, f"{prefix}/discover", track=track))
    points = kill_points(found["counts"])
    failures = []
    for n, (target, cut) in enumerate(points):
        got = asyncio.run(scenario(box, f"{prefix}/p{n}", target, cut, track))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, cut, got["effects"], got["delivered"], got["last"]))
    return points, failures


def test_every_exec_kill_point_of_a_cell_through_docker_runs_it_once_and_delivers_it_once(box):  # noqa: F811
    points, failures = sweep(box, "/r/tracked")
    print("H7-REPL-SWEEP", len(points), failures)
    assert len(points) >= 8, points
    assert not failures, f"{len(failures)}/{len(points)} kill points broke the contract: {failures}"


def test_through_docker_known_bad_untracked_cells_break_the_sweep(box):  # noqa: F811
    _, failures = sweep(box, "/r/stock", track=False)
    assert failures, "the untracked REPL passed every exec kill point through docker"


def test_through_docker_a_restarted_controller_adopts_the_interpreter(box):  # noqa: F811
    root = "/r/adopt"

    def controller(conversation):
        repl = Repl(DockerExecEnv(box, docker=DOCKER), root, lambda: 600.0, None, base=f"{root}/repl",
                    track_operations=True)
        repl.conversation = conversation
        return repl

    async def go():
        await DockerExecEnv(box, docker=DOCKER).exec(f"mkdir -p {root}")
        first = controller(set())
        first.delivery_tag = lambda: "call_1"
        assert await first.start()
        assert "[python cell 1: ok" in await first.run("x = 41", wait_s=10)
        assert "still running" in await first.run("import time\ntime.sleep(3)\nx += 1\nprint('cell-done', x)", wait_s=0)
        server = first.pid
        del first  # the controller dies; its interpreter does not

        second = controller({"call_1"})
        try:
            assert await second.start()
            assert second.pid == server  # adopted, not relaunched
            shown = await second.run("print('fresh-output')", wait_s=10)
            assert "adopted from an earlier controller" in shown and "[code not run" in shown, shown
            waited = await second.run("", wait_s=10)
            assert (shown + waited).count("cell-done 42") == 1, shown + waited
            again = await second.run("print('x is', x)", wait_s=10)
            assert "x is 42" in again and "cell-done" not in again, again
        finally:
            await second.close()

    asyncio.run(go())

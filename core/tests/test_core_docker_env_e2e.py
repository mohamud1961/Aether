"""H7 portability: the same Core through a plain ``docker exec`` orchestrator (no Harbor).

1. The environment keeps the local-shell semantics Core is qualified on (status, output, cwd, env, timeout, binary
   file transfer, missing file).
2. A whole scripted Core session (terminal, write_file, terminal, finish) runs through it.
3. The T2 terminal sweep: every exec of a command, misreported (run fully, then "failed, no output"), still runs the
   command once and shows its result once.

Runs where a Docker daemon is reachable: set AETHER_TEST_DOCKER_CONTEXT (and AETHER_TEST_DOCKER_IMAGE, an image
with sh, bash and python3). Everything is asserted through ``docker exec``; nothing is shared with the host.
"""

import asyncio
import os
import shlex
import subprocess
import uuid
from types import SimpleNamespace

import pytest

from aether.core.docker_env import DockerExecEnv
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.terminal import Terminals
from tests.core_fakes import ScriptedClient, call
from tests.core_fault_sweep import _under_trap, misreport_points

CTX, IMAGE = os.environ.get("AETHER_TEST_DOCKER_CONTEXT"), os.environ.get("AETHER_TEST_DOCKER_IMAGE")
pytestmark = pytest.mark.skipif(not (CTX and IMAGE), reason="needs AETHER_TEST_DOCKER_CONTEXT and _IMAGE")
DOCKER = ("docker", "--context", CTX or "")
HOLD = ("still running", "may have", "unknown", "not known")
INTENT = "printf x >> effects; sleep 1; echo OPSM-RAN"


@pytest.fixture(scope="module")
def box():
    name = f"aether-h7-{uuid.uuid4().hex[:8]}"
    subprocess.run([*DOCKER, "run", "-d", "--rm", "--pull", "never", "--network", "none", "--init", "--name", name,
                    IMAGE, "sleep", "3600"], check=True, capture_output=True)
    try:
        yield name
    finally:
        subprocess.run([*DOCKER, "rm", "-f", name], capture_output=True)


def sh(env, command):
    return asyncio.run(env.exec(command)).stdout


def test_the_environment_keeps_local_shell_semantics(box, tmp_path):
    env = DockerExecEnv(box, docker=DOCKER)
    r = asyncio.run(env.exec("mkdir -p /w && cd /w && printf out; printf err >&2; exit 3"))
    assert (r.return_code, r.stdout, r.stderr) == (3, "out", "err")
    assert asyncio.run(env.exec("pwd", cwd="/w")).stdout.strip() == "/w"
    assert asyncio.run(env.exec('printf %s "$K"', env={"K": "v w"})).stdout == "v w"
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(env.exec("sleep 5", timeout_sec=1))
    blob = bytes(range(256)) * 4
    (tmp_path / "in.bin").write_bytes(blob)
    asyncio.run(env.upload_file(tmp_path / "in.bin", "/w/in.bin"))
    asyncio.run(env.download_file("/w/in.bin", tmp_path / "out.bin"))
    assert (tmp_path / "out.bin").read_bytes() == blob
    with pytest.raises(FileNotFoundError):
        asyncio.run(env.download_file("/w/none", tmp_path / "none"))


def test_a_whole_core_session_runs_without_harbor(box, tmp_path):
    env = DockerExecEnv(box, docker=DOCKER)
    sh(env, "mkdir -p /s")
    script = [
        call("terminal", {"input": "echo one > /s/a.txt"}, "c1"),
        call("write_file", {"path": "/s/b.txt", "content": "two\n"}, "c2"),
        call("terminal", {"input": "cat /s/a.txt /s/b.txt"}, "c3"),
        call("finish", {"summary": "done"}, "c4"),
    ]
    result = asyncio.run(run_agent(
        env=env, task="write two files", workdir="/s", provider=ChatProvider(ScriptedClient(script), model="scripted", params={}),
        timeout_s=120, trace=Trace(tmp_path / "trace.jsonl"), config=CoreConfig(control_dir="/tmp/.aether-h7")))
    assert result.status == "finished", result.error
    assert sh(env, "cat /s/a.txt /s/b.txt") == "one\ntwo\n"
    assert "one\ntwo" in (tmp_path / "trace.jsonl").read_text().replace("\\n", "\n")


class DockerCut(DockerExecEnv):
    """CutExecs's discovery and misreport modes, with the counter read back through docker exec."""

    def __init__(self, box, root, target=None):
        super().__init__(box, docker=DOCKER)
        self.root, self.target, self.armed, self.fired, self.index, self.counts = root, target, False, False, 0, []

    async def exec(self, command, **kwargs):
        if not self.armed or self.fired:
            return await super().exec(command, **kwargs)
        i, self.index = self.index, self.index + 1
        if self.target is None:
            counter = f"{self.root}/.exec-{i}.n"
            result = await super().exec(_under_trap(command, counter, None), **kwargs)
            self.counts.append(int((await super().exec(f"cat {shlex.quote(counter)}")).stdout))
            return result
        if i != self.target:
            return await super().exec(command, **kwargs)
        self.fired = True
        await super().exec(command, **kwargs)
        return SimpleNamespace(return_code=1, stdout="", stderr="")


async def terminal_case(box, root, target=None):
    env = DockerCut(box, root, target)
    await DockerExecEnv.exec(env, f"mkdir -p {root}")
    ctrl = Terminals(env, root, lambda: 1000.0, control_dir=f"{root}/ctl", preserve_existing=True)
    shown = []
    try:
        assert "[exit 0" in await ctrl.use(name="job", input="true", wait_s=5)
        env.armed, send = True, True
        for _ in range(8):
            try:
                out = await ctrl.use(name="job", input=INTENT if send else "", wait_s=2)
            except Exception as exc:  # as the loop shows it
                out = f"error: {type(exc).__name__}: {exc}"
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = not any(k in out for k in HOLD)
        env.armed = False
        effects = (await DockerExecEnv.exec(env, f"cat {root}/effects 2>/dev/null")).stdout
        return {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown), "counts": env.counts,
                "shown": [o[-160:] for o in shown]}
    finally:
        env.armed = False
        await ctrl.close()


def test_terminal_misreport_sweep_through_docker(box):
    found = asyncio.run(terminal_case(box, "/t/discover"))
    assert (found["effects"], found["delivered"]) == (1, 1), found
    points = misreport_points(found["counts"])
    failures = []
    for n, (target, _) in enumerate(points):
        got = asyncio.run(terminal_case(box, f"/t/p{n}", target))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, got["effects"], got["delivered"], got["shown"]))
    print("H7-T2-TERMINAL", len(points), failures)
    assert points and not failures, failures

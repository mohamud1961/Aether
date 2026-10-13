"""Fault suite on real Linux containers: the tools the model uses, driven the way Harbor drives them (every
command a ``docker exec``), under the failures that matter: interrupts, floods, binary output, dying shells,
deadlines, interpreter crashes, compose routing, mounts, and cleanup.

Needs Linux and a docker daemon (the VM). ``AETHER_FAULT_IMAGE`` picks the image (it needs bash, python3 and
util-linux ``script``); otherwise the first local image that has them is used.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from types import SimpleNamespace
import uuid

import pytest

from aether.core import clone as C
from aether.core.files import Files
from aether.core.repl import Repl
from aether.core.terminal import Terminals


def _docker_ok() -> bool:
    return (os.path.exists("/proc/self/stat") and shutil.which("docker") is not None
            and subprocess.run(["docker", "info"], capture_output=True).returncode == 0)


pytestmark = pytest.mark.skipif(not _docker_ok(), reason="needs Linux and a docker daemon")
NEEDS = "command -v bash && command -v python3 && script -qfc true /dev/null"


def _image() -> str:
    if os.environ.get("AETHER_FAULT_IMAGE"):
        return os.environ["AETHER_FAULT_IMAGE"]
    listed = subprocess.run(["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True,
                            text=True).stdout.split()
    for image in (i for i in listed if "<none>" not in i and not i.startswith("aether-clone")):
        probe = subprocess.run(["docker", "run", "--rm", "--entrypoint", "sh", image, "-c", NEEDS],
                               capture_output=True, timeout=120)
        if probe.returncode == 0:
            return image
    pytest.skip("no local image with bash, python3 and script")


class DockerEnv:
    """The Harbor environment interface over ``docker exec`` (Harbor runs ``docker compose exec``)."""

    def __init__(self, container: str) -> None:
        self.container = container

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        argv = ["docker", "exec", *(["-w", cwd] if cwd else []), self.container, "bash", "-c", command]
        code, out, err = await C.host_run(argv, float(timeout_sec or 60))
        return SimpleNamespace(return_code=code, stdout=out, stderr=err)

    async def upload_file(self, source_path, target_path):
        await C.host_run(["docker", "cp", str(source_path), f"{self.container}:{target_path}"], 120)

    async def download_file(self, source_path, target_path):
        code, _, err = await C.host_run(["docker", "cp", f"{self.container}:{source_path}", str(target_path)], 120)
        if code != 0:
            raise FileNotFoundError(err)


@pytest.fixture(scope="module")
def image() -> str:
    return _image()


@pytest.fixture
def box(image, tmp_path):
    name = f"aether-fault-{uuid.uuid4().hex[:8]}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-v", f"{tmp_path}:/mnt/host",
                    "--entrypoint", "sh", image, "-c", "mkdir -p /app; while :; do sleep 3600; done"],
                   check=True, capture_output=True)
    yield DockerEnv(name)
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def _terms(env, clock=lambda: 1000.0):
    return Terminals(env, "/app", clock, control_dir="/tmp/.aether")


def _go(coro):
    return asyncio.run(coro)


def _procs(env, pattern: str) -> list[str]:
    out = _go(env.exec(f"for d in /proc/[0-9]*; do tr '\\0' ' ' < $d/cmdline 2>/dev/null; echo; done")).stdout
    return [line for line in out.splitlines() if pattern in line and "for d in" not in line]


# ----- terminals ---------------------------------------------------------------------------------------------

def test_exit_statuses_are_exact_including_signals(box):
    t = _terms(box)
    assert "[exit 0 " in _go(t.use(input="true"))
    assert "[exit 1 " in _go(t.use(input="false"))
    assert "[exit 7 " in _go(t.use(input="(exit 7)"))
    assert "[exit 143 " in _go(t.use(input="sh -c 'kill -TERM $$'"))
    _go(t.close())


def test_shell_state_persists_and_a_pty_is_present(box):
    t = _terms(box)
    first = _go(t.use(input="cd /tmp && export AETHER_X=42"))
    assert "without a pty" not in first
    out = _go(t.use(input="pwd; echo $AETHER_X; tty"))
    assert "/tmp" in out and "42" in out and "/dev/pts/" in out and "cwd /tmp" in out
    _go(t.close())


def test_an_interactive_program_reads_keys(box):
    t = _terms(box)
    out = _go(t.use(input="read -r line; echo got:$line", wait_s=2))
    assert "still running" in out
    out = _go(t.use(input="abc\n", mode="keys", wait_s=5))
    assert "got:abc" in out
    out = _go(t.use(input="python3 -i -q", wait_s=3))
    out = _go(t.use(input="print(6*7)\n", mode="keys", wait_s=3))
    assert "42" in out
    _go(t.use(input="exit()\n", mode="keys", wait_s=3))
    assert "[exit 0 " in _go(t.use(input="echo back"))
    _go(t.close())


def test_ctrl_c_stops_the_command_and_the_shell_stays_usable(box):
    t = _terms(box)
    assert "still running" in _go(t.use(input="sleep 300", wait_s=1))
    started = time.monotonic()
    out = _go(t.use(interrupt=True, wait_s=10))
    assert time.monotonic() - started < 8 and "still running" not in out
    assert not _procs(box, "sleep 300")
    assert "alive" in _go(t.use(input="echo alive"))
    _go(t.close())


def test_an_output_flood_is_clipped_for_the_model_and_kept_whole_in_the_log(box):
    t = _terms(box)
    started = time.monotonic()
    out = _go(t.use(input="yes 0123456789 | head -c 20000000; echo END", wait_s=120))
    assert time.monotonic() - started < 60
    assert "bytes omitted; full output is in /tmp/.aether/term/main/out.log" in out and "END" in out
    assert len(out) < 20_000
    size = int(_go(box.exec("wc -c < /tmp/.aether/term/main/out.log")).stdout)
    assert size >= 20_000_000
    _go(t.close())


def test_binary_and_unterminated_output_do_not_break_the_terminal(box):
    t = _terms(box)
    _go(t.use(input="head -c 4000 /dev/urandom"))
    assert "abc" in _go(t.use(input="printf abc"))
    assert "[exit 0 " in _go(t.use(input="echo fine"))
    _go(t.close())


def test_a_shell_that_exits_says_so_and_restarts_fresh(box):
    t = _terms(box)
    _go(t.use(input="export GONE=1"))
    assert "exited; it restarts on next use" in _go(t.use(input="exit 3"))
    out = _go(t.use(input="echo [$GONE]"))
    assert "started" in out and "[]" in out
    _go(t.close())


def test_a_wait_never_outlives_the_run_deadline(box):
    t = _terms(box, clock=lambda: 6.0)  # 6 s left: at most 1 s of waiting
    started = time.monotonic()
    out = _go(t.use(input="sleep 20", wait_s=60))
    assert time.monotonic() - started < 6 and "still running" in out
    _go(t.close())


def test_close_stops_the_terminals_and_their_background_jobs(box):
    t = _terms(box)
    _go(t.use(input="sleep 1001 & nohup sleep 1002 >/dev/null 2>&1 &"))
    _go(t.use(name="other", input="sleep 1004", wait_s=1))
    assert _procs(box, "sleep 1001") and _procs(box, "sleep 1002") and _procs(box, "sleep 1004")
    _go(t.close())
    time.sleep(1.0)
    assert not _procs(box, "sleep 100"), _procs(box, "sleep 100")


# ----- files and the REPL ------------------------------------------------------------------------------------

def test_files_read_large_binary_and_unterminated_and_keep_permissions(box):
    f = Files(box, "/app")
    _go(box.exec("seq 1 5000 > /app/big.txt; head -c 3000 /dev/urandom > /app/blob.bin; printf 'x' > /app/nonl; "
                 "printf '#!/bin/sh\\necho hi\\n' > /app/run.sh; chmod 755 /app/run.sh"))
    page = _go(f.read("big.txt", 4990, 20))
    assert "5000" in page and "4989" not in page
    assert "not text" in _go(f.read("blob.bin")).lower() or "binary" in _go(f.read("blob.bin")).lower()
    assert "x" in _go(f.read("nonl"))
    _go(f.edit("run.sh", "echo hi", "echo bye"))
    assert _go(box.exec("stat -c %a /app/run.sh; /app/run.sh")).stdout.split() == ["755", "bye"]


def test_the_repl_keeps_state_reports_a_crash_and_restarts(box):
    async def go():
        repl = Repl(box, "/app", lambda: 1000.0, None, base="/tmp/.aether/repl")
        version = await repl.start()
        assert version.startswith("3")
        await repl.run("x = 41")
        kept = await repl.run("print(x + 1)")
        crash = await repl.run("import os; os._exit(9)")
        after = await repl.run("print('x' in globals())")
        await repl.close()
        return kept, crash, after
    kept, crash, after = _go(go())
    assert "42" in kept
    assert "restart" in crash.lower() or "exited" in crash.lower() or "died" in crash.lower(), crash
    assert "False" in after  # a fresh interpreter, and the model is told it is fresh


# ----- clones ------------------------------------------------------------------------------------------------

def test_a_clone_is_proven_isolated_from_the_original(box):
    async def go():
        await box.exec("echo original > /app/a")
        clone = await C.Clone.create(box)
        try:
            await clone.exec("echo changed > /app/a")
            seen = (await clone.exec("cat /app/a")).stdout
        finally:
            await clone.close()
        return seen, (await box.exec("cat /app/a")).stdout, clone.image
    seen, original, image = _go(go())
    assert seen.strip() == "changed" and original.strip() == "original"
    assert subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode != 0


def test_a_bind_mounted_path_is_not_in_the_clone(box, tmp_path):
    (tmp_path / "data.txt").write_text("mounted")

    async def go():
        clone = await C.Clone.create(box)
        try:
            return (await clone.exec("cat /mnt/host/data.txt 2>&1; echo [$?]")).stdout
        finally:
            await clone.close()
    seen = _go(go())
    assert "mounted" not in seen  # a known limit, stated in clone.py: checks cannot see volume contents


def test_compose_never_routes_the_live_container_s_commands_into_a_clone(image, tmp_path):
    """The V3 bug: a clone that kept the compose labels received `docker compose exec main` commands."""
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0:
        pytest.skip("no docker compose")
    project = f"aetherfault{uuid.uuid4().hex[:6]}"
    (tmp_path / "compose.yaml").write_text(json.dumps({"services": {"main": {
        "image": image, "entrypoint": ["sh", "-c", "echo live > /marker; while :; do sleep 3600; done"]}}}))
    base = ["docker", "compose", "-p", project, "-f", str(tmp_path / "compose.yaml")]
    subprocess.run([*base, "up", "-d"], check=True, capture_output=True)
    try:
        class Compose:
            async def exec(self, command, cwd=None, env=None, timeout_sec=None):
                code, out, err = await C.host_run([*base, "exec", "-T", "main", "sh", "-c", command],
                                                  float(timeout_sec or 60))
                return SimpleNamespace(return_code=code, stdout=out, stderr=err)

        async def go():
            clone = await C.Clone.create(Compose())
            try:
                await clone.exec("echo clone > /marker")
                return [(await Compose().exec("cat /marker")).stdout.strip() for _ in range(5)]
            finally:
                await clone.close()
        assert _go(go()) == ["live"] * 5
    finally:
        subprocess.run([*base, "down", "-t", "1"], capture_output=True)


def test_a_clone_cancelled_at_any_point_leaves_no_container_or_image_behind(box):
    before = set(subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True).stdout.split())
    cancelled = 0

    async def go(delay):
        task = asyncio.create_task(C.Clone.create(box))
        await asyncio.sleep(delay)  # identify, docker commit or docker run, depending on the delay
        task.cancel()
        (out,) = await asyncio.gather(task, return_exceptions=True)
        if isinstance(out, C.Clone):  # it finished first: the caller owns it
            await out.close()
        return isinstance(out, asyncio.CancelledError)
    for delay in (0.05, 0.2, 0.4, 0.7, 1.0):
        cancelled += _go(go(delay))
    after = set(subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True).stdout.split())
    images = subprocess.run(["docker", "image", "ls", "-q", "--filter", "reference=aether-clone"],
                            capture_output=True, text=True).stdout.split()
    assert cancelled >= 2  # the cancellations really landed mid-creation
    assert after <= before and not images, (after - before, images)


def test_zombie_liveness_is_not_reported_as_alive(box):
    from aether.core.env import alive_test

    async def go():
        # The parent deliberately leaves its exited child unreaped, independently of the image's PID 1.
        await box.exec("python3 -c 'import os,time; child=os.fork(); "
                       "open(\"/tmp/zombie-child\",\"w\").write(str(child)) if child else os._exit(0); "
                       "time.sleep(20)' >/tmp/zombie-parent.log 2>&1 &")
        try:
            await asyncio.sleep(0.3)
            pid = int((await box.exec("cat /tmp/zombie-child")).stdout)
            probe = await box.exec(f"kill -0 {pid}; echo kill_code:$?; "
                                   f"{alive_test(pid)}; echo alive_code:$?")
            return probe.stdout
        finally:
            await box.exec("pkill -f 'time.sleep\\(20\\)' || true")
    output = _go(go())
    assert "kill_code:0" in output and "alive_code:1" in output


def test_terminal_restarts_after_its_wrapper_dies_between_calls(box):
    async def go():
        t = _terms(box)
        try:
            await t.use(input="export OLD_STATE=yes")
            await box.exec(f"kill -9 {t._sessions['main'].pid}")
            await asyncio.sleep(0.2)
            return await t.use(input="echo restarted-${OLD_STATE:-fresh}", wait_s=3)
        finally:
            await t.close()
    out = _go(go())
    assert "fresh terminal" in out and "restarted-fresh" in out and "exit 0" in out

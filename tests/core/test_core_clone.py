"""The clone substrate: a commit of the task container started with no network and resource limits, never
selected by compose, and (Linux + docker) isolated from the original."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import uuid

import pytest

from aether.core import clone as V


def test_the_clone_has_no_network_and_resource_limits():
    calls = []

    async def host(argv, timeout):
        calls.append(argv)
        return 0, "", ""

    class Env:
        async def exec(self, command, cwd=None, env=None, timeout_sec=None):
            from types import SimpleNamespace
            return SimpleNamespace(return_code=0, stdout="a" * 64 + "\nhost\n", stderr="")
    clone = asyncio.run(V.Clone.create(Env(), host))
    commit, start = calls[0], calls[1]
    assert commit[:2] == ["docker", "commit"] and commit[-2] == "a" * 64
    # compose selects containers by these labels; a clone that kept them could receive the live run's commands
    assert "LABEL com.docker.compose.project=" in commit and "LABEL com.docker.compose.service=" in commit
    assert ["--network", "none"] == start[start.index("--network"):start.index("--network") + 2]
    assert "no-new-privileges" in start and "--memory" in start and "--pids-limit" in start
    asyncio.run(clone.close())
    assert calls[-2][:3] == ["docker", "rm", "-f"] and calls[-1][:3] == ["docker", "rmi", "-f"]


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _docker_ok(), reason="needs a docker daemon")
def test_a_real_clone_is_isolated_from_the_original_container():
    local = subprocess.run(["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True,
                           text=True).stdout.split()
    image = next((i for i in local if "<none>" not in i and not i.startswith("aether-clone")), None)
    if image is None:
        pytest.skip("no small base image available locally")
    name = f"aether-clone-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, image, "sh", "-c",
                    "mkdir -p /data && echo original > /data/a && sleep 600"], check=True, capture_output=True)

    class Live:
        async def exec(self, command, cwd=None, env=None, timeout_sec=None):
            p = subprocess.run(["docker", "exec", name, "sh", "-c", command], capture_output=True, text=True)
            from types import SimpleNamespace
            return SimpleNamespace(return_code=p.returncode, stdout=p.stdout, stderr=p.stderr)

    async def go():
        clone = await V.Clone.create(Live())
        try:
            seen = (await clone.exec("cat /data/a")).stdout
            await clone.exec("echo changed-in-clone > /data/a")
            changed = (await clone.exec("cat /data/a")).stdout
        finally:
            await clone.close()
        original = (await Live().exec("cat /data/a")).stdout
        gone = subprocess.run(["docker", "image", "inspect", clone.image], capture_output=True).returncode != 0
        return seen, changed, original, gone
    try:
        seen, changed, original, gone = asyncio.run(go())
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    assert seen.strip() == "original" and changed.strip() == "changed-in-clone"
    assert original.strip() == "original"  # the clone's writes never reach the original
    assert gone  # the clone image is removed afterwards

"""The clone substrate: a commit of the task container started with no network and resource limits, never
selected by compose, and (Linux + docker) isolated from the original."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import uuid

import pytest

from aether.core import clone as V


class _Host:
    """A fake docker host with two containers: the task's (its files are ``files``) and another one."""

    def __init__(self, files: dict[str, str], real: str = "a" * 64, other: str = "b" * 64) -> None:
        self.files, self.real, self.other, self.calls = files, real, other, []

    async def __call__(self, argv, timeout):
        self.calls.append(argv)
        if argv[:2] == ["docker", "inspect"]:
            return (0, argv[-1] + "\n", "") if argv[-1] in (self.real, self.other) else (1, "", "No such object")
        if argv[:2] == ["docker", "exec"]:
            cid, path = argv[2], argv[-1]
            return (0, self.files.get(path, ""), "") if cid == self.real else (1, "", "No such file")
        return 0, "", ""


class _TaskEnv:
    """The task container as the worker may have left it: it reports ``claims`` as its own id."""

    def __init__(self, host: _Host, claims: str) -> None:
        self.host, self.claims = host, claims

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        from types import SimpleNamespace
        if command.startswith("printf %s "):
            token, path = command.split()[2], command.split()[-1]
            self.host.files[path] = token
        if command.startswith("rm -f "):
            self.host.files.pop(command.split()[-1], None)
        return SimpleNamespace(return_code=0, stdout=self.claims + "\nhost\n", stderr="")


def test_the_clone_has_no_network_and_resource_limits():
    host = _Host({})
    clone = asyncio.run(V.Clone.create(_TaskEnv(host, host.real), host))
    commit = next(c for c in host.calls if c[:2] == ["docker", "commit"])
    start = next(c for c in host.calls if c[:2] == ["docker", "run"])
    assert commit[-2] == "a" * 64
    # compose selects containers by these labels; a clone that kept them could receive the live run's commands
    assert "LABEL com.docker.compose.project=" in commit and "LABEL com.docker.compose.service=" in commit
    assert ["--network", "none"] == start[start.index("--network"):start.index("--network") + 2]
    assert "no-new-privileges" in start and "--memory" in start and "--pids-limit" in start
    assert host.files == {}  # the identity token is gone before the commit
    asyncio.run(clone.close())
    assert host.calls[-2][:3] == ["docker", "rm", "-f"] and host.calls[-1][:3] == ["docker", "rmi", "-f"]


def test_a_container_that_names_another_container_as_itself_is_refused_before_any_commit():
    host = _Host({})
    with pytest.raises(V.CloneError, match="not the one it runs in"):
        asyncio.run(V.Clone.create(_TaskEnv(host, host.other), host))
    assert not any(c[:2] == ["docker", "commit"] for c in host.calls)
    with pytest.raises(V.CloneError, match="no container"):
        asyncio.run(V.Clone.create(_TaskEnv(host, "made-up-name"), host))


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

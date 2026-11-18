"""The python REPL on a task image with no python3 (AETHER_CORE_REPL_PYTHON, box_python.install).

Why (16 Nov board P): toolset=python refused to start on 2 of 8 screen tasks whose images ship no python3, and the
stock REPL is silently absent there. With the host tarball set, the REPL runs on a harness CPython kept off PATH and
the first python result states that fact; with it unset, behaviour is unchanged (no REPL).

Runs where a Docker daemon is reachable: AETHER_TEST_DOCKER_CONTEXT, AETHER_TEST_DOCKER_NOPY_IMAGE (a glibc image
with sh and no python3) and AETHER_TEST_REPL_PYTHON (a python-build-standalone install_only tarball on this host).
"""

import asyncio
import os
import subprocess
import uuid

import pytest

from aether.core import box_python
from aether.core.docker_env import DockerExecEnv
from aether.core.repl import Repl

CTX = os.environ.get("AETHER_TEST_DOCKER_CONTEXT")
IMAGE = os.environ.get("AETHER_TEST_DOCKER_NOPY_IMAGE")
TARBALL = os.environ.get("AETHER_TEST_REPL_PYTHON", "")
pytestmark = pytest.mark.skipif(not (CTX and IMAGE and TARBALL),
                                reason="needs AETHER_TEST_DOCKER_CONTEXT, _NOPY_IMAGE and AETHER_TEST_REPL_PYTHON")
DOCKER = ("docker", "--context", CTX or "")


@pytest.fixture()
def nopy():
    name = f"aether-nopy-{uuid.uuid4().hex[:8]}"
    subprocess.run([*DOCKER, "run", "-d", "--rm", "--pull", "never", "--network", "none", "--init", "--name", name,
                    IMAGE, "sleep", "600"], check=True, capture_output=True)
    try:
        yield name
    finally:
        subprocess.run([*DOCKER, "rm", "-f", name], capture_output=True)


class Counting(DockerExecEnv):
    uploads = 0

    async def upload_file(self, source_path, target_path):
        type(self).uploads += 1
        return await super().upload_file(source_path, target_path)


def env(name):
    return Counting(name, docker=DOCKER)


async def session(e, bundled):
    repl = Repl(e, "/tmp", lambda: 600.0, None, base="/tmp/.aether/repl", bundled_python=bundled)
    version = await repl.start()
    try:
        first = await repl.run("import sys\nprint('SUM', 1 + 1, sys.executable)", wait_s=20) if version else ""
        path = (await DockerExecEnv.exec(e, "command -v python3 || echo NONE")).stdout.strip()
        return version, first, path
    finally:
        await repl.close()


def test_known_bad_no_tarball_means_no_repl(nopy):
    version, first, path = asyncio.run(session(env(nopy), ""))
    assert (version, first, path) == ("", "", "NONE")


def test_bundled_python_runs_the_repl_off_path_and_says_so(nopy):
    Counting.uploads = 0
    version, first, path = asyncio.run(session(env(nopy), TARBALL))
    assert version.count(".") == 1 and int(version.split(".")[0]) == 3
    assert "SUM 2 " + box_python.REPL_ROOT in first
    assert "has no python3" in first and "not on PATH" in first
    assert path == "NONE"  # the task's own shell still finds no python3
    assert Counting.uploads == 1
    again = asyncio.run(session(env(nopy), TARBALL))  # a later controller reuses the install
    assert Counting.uploads == 1 and "SUM 2" in again[1]


def test_missing_tarball_is_no_repl_not_a_crash(nopy):
    version, first, _ = asyncio.run(session(env(nopy), "/nonexistent/python.tar.gz"))
    assert (version, first) == ("", "")

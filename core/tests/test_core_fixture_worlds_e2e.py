"""D14: fixture worlds on a real task image with seeded navigation hazards (the negative controls of
ENVIRONMENT_NAVIGATION.md, "Falsifiers and measures").

Two fresh containers from one image get the same apparent paths with different versions of ``data/config.json``,
plus repeated file names, an outside-root symlink to /etc, an unserved FIFO, a 3,000-entry flat directory and a
52,000-entry directory beyond the search walk's entry limit. Core's navigation surfaces must not equate the worlds,
claim absence from a partial scan, read beyond the workspace, block on the FIFO, or report a measured zero where they
could not measure.

Needs Docker and a task image with a system Python: AETHER_TEST_DOCKER_IMAGE (and AETHER_TEST_DOCKER_CONTEXT for a
non-default context). AETHER_TEST_DOCKER_IMAGE_NO_PYTHON (a task image without one) adds the check that search then
says it is unavailable instead of reporting no match.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import uuid

import pytest

from aether.core import start_copy, state_service, workspace_search
from aether.core.docker_env import DockerExecEnv

IMAGE = os.environ.get("AETHER_TEST_DOCKER_IMAGE", "")
NO_PYTHON = os.environ.get("AETHER_TEST_DOCKER_IMAGE_NO_PYTHON", "")
CONTEXT = os.environ.get("AETHER_TEST_DOCKER_CONTEXT", "")
DOCKER = ("docker", "--context", CONTEXT) if CONTEXT else ("docker",)
W, CTL = "/fixture", "/tmp/.aether-d14"
pytestmark = pytest.mark.skipif(not IMAGE, reason="needs AETHER_TEST_DOCKER_IMAGE (a task image)")

SEED = """set -e
W={w}; mkdir -p $W/data $W/a $W/b $W/flat $W/huge
printf '{{"version": "{version}"}}\\n' > $W/data/config.json
echo alpha > $W/a/notes.txt; echo beta > $W/b/notes.txt
ln -s /etc $W/outside
mkfifo $W/pipe
cd $W/flat && seq 1 3000 | sed 's/^/f/' | xargs touch
cd $W/huge && seq 1 52000 | sed 's/^/h/' | xargs touch
"""


def _world(image, version):
    name = f"aether-d14-{version}-{uuid.uuid4().hex[:8]}"
    subprocess.run([*DOCKER, "run", "-d", "--rm", "--network", "none", "--name", name, "--entrypoint", "sleep",
                    image, "infinity"], check=True, capture_output=True)
    env = DockerExecEnv(name, docker=DOCKER)
    seeded = asyncio.run(env.exec(SEED.format(w=W, version=version), timeout_sec=300))
    assert seeded.return_code == 0, seeded.stderr
    return env


def _remove(env):
    subprocess.run([*DOCKER, "rm", "-f", env.container], capture_output=True)


@pytest.fixture(scope="module")
def worlds():
    made = {}
    try:
        for version in ("2", "1"):
            made[version] = _world(IMAGE, version)
        yield made
    finally:
        for env in made.values():
            _remove(env)


def _search(env, **args):
    return json.loads(asyncio.run(workspace_search.search(env, W, CTL, args)))


def test_search_tells_the_worlds_apart_by_version_and_content(worlds):
    found = {v: _search(env, mode="text", query="version", subdir="data") for v, env in worlds.items()}
    for version, result in found.items():
        assert result["status"] == "searched" and len(result["matches"]) == 1, result
        assert result["matches"][0]["text"] == f'{{"version": "{version}"}}', result
    assert found["2"]["matches"][0] != found["1"]["matches"][0]  # same path, different version: never equated


def test_search_keeps_repeated_names_apart_and_never_follows_the_outside_link(worlds):
    env = worlds["2"]
    names = _search(env, mode="filename", query="notes.txt")
    paths = sorted(m.get("path") for m in names["matches"])
    assert paths == ["a/notes.txt", "b/notes.txt"], names
    outside = _search(env, mode="text", query="root:")  # /etc/passwd content, reachable only through the link
    assert outside["matches"] == [], outside


def test_known_bad_a_scan_that_hit_its_limits_is_partial_not_absent(worlds):
    env = worlds["2"]
    deep = _search(env, mode="filename", query="h51999", subdir="huge")  # beyond the 50,000-entry walk
    assert deep["status"] == "partial" and deep["skipped_or_limited"] > 0, deep
    whole = _search(env, mode="text", query="version")  # the FIFO is skipped, never opened: the scan says so
    assert whole["status"] == "partial" and len(whole["matches"]) == 1, whole


def test_start_copy_and_state_never_hang_never_leave_scope_and_never_report_an_unmeasured_zero(worlds):
    env = worlds["1"]
    _, row = asyncio.run(asyncio.wait_for(start_copy.take(env, W, CTL), 240))  # the FIFO must not block the copy
    assert row["copied"], row
    copy = row["path"]
    probe = asyncio.run(env.exec(f"readlink {copy}/outside; find {copy} -path '*/ssl' | wc -l; test -p {copy}/pipe && "
                                 "echo fifo", timeout_sec=30))
    # the copy keeps the link as a link and the FIFO as a FIFO: nothing of /etc was copied, the pipe was never read
    assert probe.stdout.split() == ["/etc", "0", "fifo"], probe.stdout
    rows = []
    svc = state_service.StateService(env, W, lambda: 300.0, lambda event, **row: rows.append(row), control_dir=CTL)
    asyncio.run(svc.start())
    line = asyncio.run(svc.after_action(1, "terminal", {"input": "true"}, ""))
    assert "unmeasured" in line and "0 changed" not in line, line  # 55,000 files: over the account's limit


@pytest.mark.skipif(not NO_PYTHON, reason="needs AETHER_TEST_DOCKER_IMAGE_NO_PYTHON")
def test_known_bad_without_a_system_python_search_is_unavailable_never_an_empty_result():
    env = _world(NO_PYTHON, "2")
    try:
        result = _search(env, mode="text", query="version", subdir="data")
        assert result["status"] == "search_unavailable" and "matches" not in result, result
    finally:
        _remove(env)

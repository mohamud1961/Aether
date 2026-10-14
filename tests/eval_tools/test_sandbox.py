from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from harness_evals.sandbox import (
    TIMEOUT_EXIT_CODE,
    DockerSandbox,
    LocalSandbox,
    SandboxUnavailable,
    open_sandbox,
)
from harness_evals.task import load_task


@pytest.fixture
def task(make_task):
    return load_task(make_task(workspace={"state.txt": "initial\n", "sub/keep.txt": "x\n"}))


def test_workspace_is_copied_and_writes_stay_in_the_copy(task):
    sandbox = LocalSandbox(task)
    try:
        assert (sandbox.root / "state.txt").read_text() == "initial\n"
        assert (sandbox.root / "sub" / "keep.txt").is_file()
        result = sandbox.exec("printf changed > state.txt", timeout_s=10)
        assert result.code == 0
        assert (sandbox.root / "state.txt").read_text() == "changed"
        assert (task.workspace_dir / "state.txt").read_text() == "initial\n"
    finally:
        sandbox.close()


def test_exec_captures_stdout_stderr_and_exit_code(task):
    sandbox = LocalSandbox(task)
    try:
        result = sandbox.exec("echo out; echo err >&2; exit 7", timeout_s=10)
    finally:
        sandbox.close()
    assert result.code == 7
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
    assert result.timed_out is False
    assert result.wall_s >= 0


def test_environment_is_minimal_and_task_root_is_exported(task, monkeypatch):
    monkeypatch.setenv("SECRET_FROM_HOST", "leak")
    sandbox = LocalSandbox(task, trusted=True)
    try:
        result = sandbox.exec('echo "$TASK_ROOT|$HOME|$PATH|${SECRET_FROM_HOST:-unset}"', timeout_s=10)
        extra = sandbox.exec('echo "$EXTRA"', timeout_s=10, env={"EXTRA": "present"})
    finally:
        sandbox.close()
    task_root, _home, path, secret = result.stdout.strip().split("|")
    assert task_root == str(task.root)
    assert path.endswith(os.environ.get("PATH", ""))
    assert secret == "unset"
    assert extra.stdout.strip() == "present"


def test_home_is_the_sandbox_root(task):
    sandbox = LocalSandbox(task)
    try:
        result = sandbox.exec('echo "$HOME"', timeout_s=10)
        assert result.stdout.strip() == str(sandbox.root)
    finally:
        sandbox.close()


def test_timeout_kills_the_command_and_reports_it(task):
    sandbox = LocalSandbox(task)
    try:
        started = time.monotonic()
        result = sandbox.exec("sleep 30", timeout_s=0.5)
        elapsed = time.monotonic() - started
    finally:
        sandbox.close()
    assert result.timed_out is True
    assert result.code == TIMEOUT_EXIT_CODE
    assert elapsed < 10


def test_timeout_kills_background_children_in_the_process_group(task):
    sandbox = LocalSandbox(task)
    try:
        result = sandbox.exec("sleep 60 & echo $! > child.pid; wait", timeout_s=1)
        child_pid = int((sandbox.root / "child.pid").read_text().strip())
    finally:
        sandbox.close()
    assert result.timed_out is True
    deadline = time.monotonic() + 5
    while True:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        if time.monotonic() > deadline:
            pytest.fail(f"background child {child_pid} survived the timeout")
        time.sleep(0.05)


def test_close_removes_the_sandbox_and_is_idempotent(task):
    sandbox = LocalSandbox(task)
    root = sandbox.root
    sandbox.close()
    sandbox.close()
    assert not root.exists()
    with pytest.raises(RuntimeError, match="closed"):
        sandbox.exec("true", timeout_s=5)


def test_open_sandbox_dispatches_by_kind(task):
    sandbox = open_sandbox(task, kind="local")
    try:
        assert isinstance(sandbox, LocalSandbox)
    finally:
        sandbox.close()
    with pytest.raises(ValueError, match="unknown sandbox kind"):
        open_sandbox(task, kind="remote")
    with pytest.raises(TypeError):
        open_sandbox(task, kind="local", memory="1g")


def test_docker_sandbox_reports_missing_cli(task, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(SandboxUnavailable, match="docker CLI not found"):
        DockerSandbox(task)


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_docker_sandbox_runs_with_no_network(task):
    sandbox = DockerSandbox(task, image="python:3.11-slim", trusted=True)
    try:
        result = sandbox.exec("cat state.txt && echo $TASK_ROOT", timeout_s=120)
    finally:
        sandbox.close()
    assert result.code == 0
    assert "initial" in result.stdout
    assert "/task" in result.stdout
    assert not Path(sandbox.root).exists()

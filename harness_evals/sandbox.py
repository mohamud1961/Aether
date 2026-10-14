"""Sandboxes: a fresh copy of a task workspace in which an agent or a reference script runs.

LocalSandbox runs bash on the host inside a temporary directory with a minimal environment.
It isolates the workspace (a copy) and the environment. It does not isolate the network or
the rest of the filesystem.

Only trusted=True exposes reference/known-bad assets. LocalSandbox remains host-accessible
and debug-only even with trusted=False. Docker candidate execution mounts workspace only.

DockerSandbox runs each command in a container with no network, a memory limit and a CPU
limit. The task directory is mounted read-only at /task, and TASK_ROOT points there.
"""

from __future__ import annotations

import os
import shutil
import signal
import sys
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from harness_evals.task import Task

TIMEOUT_EXIT_CODE = 124
DEFAULT_DOCKER_IMAGE = "python:3.11-slim"


class SandboxUnavailable(RuntimeError):
    """The sandbox substrate cannot be used on this host."""


@dataclass(frozen=True)
class ExecResult:
    code: int
    stdout: str
    stderr: str
    wall_s: float
    timed_out: bool


class Sandbox(Protocol):
    root: Path

    def exec(
        self, cmd: str, timeout_s: float, env: dict[str, str] | None = None
    ) -> ExecResult: ...

    def close(self) -> None: ...


class LocalSandbox:
    def __init__(self, task: Task, trusted: bool = False) -> None:
        self._task = task
        self.trusted = trusted
        self.root = Path(tempfile.mkdtemp(prefix="harness-evals-"))
        shutil.copytree(task.workspace_dir, self.root, dirs_exist_ok=True)
        self._closed = False
        self._tools = Path(tempfile.mkdtemp(prefix="harness-evals-tools-"))
        (self._tools / "python3").symlink_to(sys.executable)

    def exec(
        self, cmd: str, timeout_s: float, env: dict[str, str] | None = None
    ) -> ExecResult:
        _require_open(self._closed)
        full_env = {
            "PATH": str(self._tools) + os.pathsep + os.environ.get("PATH", ""),
            "HOME": str(self.root),
        }
        if self.trusted:
            full_env["TASK_ROOT"] = str(self._task.root)
        if env:
            full_env.update(env)
        return _run_in_new_group(
            ["bash", "-c", cmd], cwd=self.root, env=full_env, timeout_s=timeout_s
        )

    def close(self) -> None:
        if not self._closed:
            shutil.rmtree(self.root, ignore_errors=True)
            shutil.rmtree(self._tools, ignore_errors=True)
            self._closed = True


class DockerSandbox:
    def __init__(
        self,
        task: Task,
        image: str = DEFAULT_DOCKER_IMAGE,
        memory: str = "1g",
        cpus: str = "1",
        trusted: bool = False,
    ) -> None:
        if shutil.which("docker") is None:
            raise SandboxUnavailable("docker CLI not found on PATH")
        _probe_docker_daemon()
        self._task = task
        self.trusted = trusted
        self._image = image
        self._memory = memory
        self._cpus = cpus
        self.root = Path(tempfile.mkdtemp(prefix="harness-evals-docker-"))
        shutil.copytree(task.workspace_dir, self.root, dirs_exist_ok=True)
        self._closed = False

    def exec(
        self, cmd: str, timeout_s: float, env: dict[str, str] | None = None
    ) -> ExecResult:
        _require_open(self._closed)
        name = f"harness-evals-{uuid.uuid4().hex[:12]}"
        container_env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/work"}
        if self.trusted:
            container_env["TASK_ROOT"] = "/task"
        if env:
            container_env.update(env)
        argv = [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            self._memory,
            "--cpus",
            self._cpus,
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--workdir",
            "/work",
            "-v",
            f"{self.root}:/work",
        ]
        if self.trusted:
            argv += ["-v", f"{self._task.root}:/task:ro"]
        for key, value in container_env.items():
            argv += ["-e", f"{key}={value}"]
        argv += [self._image, "bash", "-c", cmd]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                argv, capture_output=True, timeout=timeout_s, check=False
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run(
                ["docker", "kill", name], capture_output=True, timeout=60, check=False
            )
            return ExecResult(
                code=TIMEOUT_EXIT_CODE,
                stdout=_decode(exc.stdout),
                stderr=_decode(exc.stderr),
                wall_s=time.monotonic() - start,
                timed_out=True,
            )
        return ExecResult(
            code=proc.returncode,
            stdout=_decode(proc.stdout),
            stderr=_decode(proc.stderr),
            wall_s=time.monotonic() - start,
            timed_out=False,
        )

    def close(self) -> None:
        if not self._closed:
            shutil.rmtree(self.root, ignore_errors=True)
            self._closed = True


def open_sandbox(task: Task, kind: str = "local", **opts: object) -> Sandbox:
    if kind == "local":
        return LocalSandbox(task, **opts)  # type: ignore[arg-type]
    if kind == "docker":
        return DockerSandbox(task, **opts)  # type: ignore[arg-type]
    raise ValueError(f"unknown sandbox kind {kind!r}; expected 'local' or 'docker'")


def _run_in_new_group(
    argv: list[str], cwd: Path, env: dict[str, str], timeout_s: float
) -> ExecResult:
    start = time.monotonic()
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(proc.pid)
        out, err = proc.communicate()
    return ExecResult(
        code=TIMEOUT_EXIT_CODE if timed_out else proc.returncode,
        stdout=_decode(out),
        stderr=_decode(err),
        wall_s=time.monotonic() - start,
        timed_out=timed_out,
    )


def _kill_group(pgid: int) -> None:
    """Kill the whole process group, so background children of a timed-out command die too."""
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _probe_docker_daemon() -> None:
    try:
        probe = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxUnavailable("docker daemon did not answer within 30 s") from exc
    if probe.returncode != 0:
        raise SandboxUnavailable(f"docker daemon not reachable: {probe.stderr.strip()}")


def _require_open(closed: bool) -> None:
    if closed:
        raise RuntimeError("sandbox is closed")


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")

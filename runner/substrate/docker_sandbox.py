"""Container lifecycle management for baseline command execution."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DockerSandbox:
    """Minimal sandbox wrapper for Packet 02 baseline runs.

    Default mode executes commands locally in `cwd`. Docker mode is optional and
    intentionally narrow for the first baseline substrate.
    """

    cwd: str | Path
    timeout_sec: int = 600
    sandbox_type: str = "none"
    sandbox_image: str | None = None
    _active: bool = field(default=False, init=False, repr=False)
    _container_id: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.cwd = Path(self.cwd).resolve()
        self.timeout_sec = max(self.timeout_sec, 600)

    def __enter__(self) -> "DockerSandbox":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        return False

    def start(self) -> None:
        self.cwd.mkdir(parents=True, exist_ok=True)
        if self._active:
            return
        if self.sandbox_type == "docker":
            self._container_id = _start_container(self.sandbox_image, self.cwd)
        self._active = True

    def exec(self, command: str, timeout_sec: int | None = None) -> dict[str, Any]:
        if not self._active:
            raise RuntimeError("sandbox must be started before exec")
        timeout = int(timeout_sec if timeout_sec is not None else self.timeout_sec)
        if self.sandbox_type == "docker":
            if not self._container_id:
                raise RuntimeError("docker container is not available")
            cmd = ["docker", "exec", self._container_id, "bash", "-lc", command]
            return _run_command(cmd, timeout=timeout)
        return _run_command(["bash", "-lc", command], cwd=self.cwd, timeout=timeout)

    def workspace_state(self) -> dict[str, Any]:
        return {
            "sandbox_type": self.sandbox_type,
            "sandbox_image": self.sandbox_image,
            "cwd": str(self.cwd),
            "active": self._active,
            "container_id": self._container_id,
        }

    def stop(self) -> None:
        if not self._active:
            return
        if self._container_id:
            _stop_container(self._container_id)
        self._container_id = None
        self._active = False


def _run_command(
    cmd: list[str],
    *,
    timeout: int,
    cwd: Path | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": " ".join(cmd),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as err:
        return {
            "command": " ".join(cmd),
            "exit_code": 124,
            "stdout": err.stdout or "",
            "stderr": err.stderr or "",
            "timed_out": True,
        }


def _start_container(image: str | None, cwd: Path) -> str:
    if not image:
        raise ValueError("sandbox_image is required when sandbox_type=docker")
    cmd = [
        "docker",
        "run",
        "-d",
        "-w",
        str(cwd),
        "-v",
        f"{cwd}:{cwd}",
        image,
        "sleep",
        "infinity",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"failed to start docker sandbox: {completed.stderr.strip()}")
    container_id = completed.stdout.strip()
    if not container_id:
        raise RuntimeError("docker sandbox returned empty container id")
    return container_id


def _stop_container(container_id: str) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container_id],
        capture_output=True,
        text=True,
        check=False,
    )

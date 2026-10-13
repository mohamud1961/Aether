"""Disposable clones of the task container: a commit of its filesystem, started without network.

Used to run acceptance checks on a copy of a state, so nothing a check writes reaches the graded container.
A commit copies files, not processes: servers running in the task container are absent from a clone, and
volume-mounted paths are not part of the commit.
"""
from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any, Awaitable, Callable
import uuid

from .env import Environment, run

CLONE_MEMORY = "8g"
CLONE_CPUS = "2"

HostRun = Callable[[list[str], float], Awaitable[tuple[int, str, str]]]


async def host_run(argv: list[str], timeout_s: float) -> tuple[int, str, str]:
    """Run a host command (the docker CLI) without a shell."""
    proc = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.DEVNULL,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", f"timed out after {timeout_s:.0f}s"
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


class CloneError(RuntimeError):
    pass


# docker commit copies the container's labels into the image, so a clone of a compose service carries the same
# project and service labels, and `docker compose exec main` (how Harbor runs every command) may pick the clone:
# in V3 the worker's terminal and file writes went into the contract writer's clone and were lost with it. The
# commit blanks the labels compose selects by, so the clone is never a candidate.
_COMPOSE_LABELS = ("com.docker.compose.project", "com.docker.compose.service", "com.docker.compose.container-number",
                   "com.docker.compose.oneoff", "com.docker.compose.config-hash")
_UNLABEL = [arg for label in _COMPOSE_LABELS for arg in ("--change", f"LABEL {label}=")]


class Clone:
    """A throwaway container started from a commit of the task container (Harbor-environment interface)."""

    def __init__(self, name: str, image: str, host: HostRun, owns_image: bool = True) -> None:
        self.name, self.image, self._host, self._owns_image = name, image, host, owns_image

    @staticmethod
    def _run_args(name: str, image: str) -> list[str]:
        # No network: the clone must not escape the task's egress policy.
        return ["docker", "run", "-d", "--rm", "--name", name, "--network", "none", "--security-opt",
                "no-new-privileges", "--pids-limit", "4096", "--memory", CLONE_MEMORY, "--cpus", CLONE_CPUS,
                "--entrypoint", "sh", image, "-c", "while :; do sleep 3600; done"]

    @classmethod
    async def create(cls, env: Environment, host: HostRun = host_run) -> "Clone":
        # The container's own hostname file is bind-mounted from /var/lib/docker/containers/<id>/, which names it
        # even when a compose file sets a custom hostname; the hostname itself is the fallback.
        res = await run(env, "grep -o 'containers/[0-9a-f]\\{64\\}' /proc/self/mountinfo 2>/dev/null | head -n 1 "
                             "| cut -d/ -f2; cat /etc/hostname 2>/dev/null || hostname")
        cid = (res.stdout.split() or [""])[0]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", cid):
            raise CloneError(f"cannot identify the task container (hostname {cid!r})")
        tag = f"aether-clone:{uuid.uuid4().hex[:12]}"
        code, _, err = await host(["docker", "commit", *_UNLABEL, cid, tag], 900)
        if code != 0:
            raise CloneError(f"docker commit failed: {err.strip()[:300]}")
        name = tag.replace(":", "-")
        code, _, err = await host(cls._run_args(name, tag), 180)
        if code != 0:
            await host(["docker", "rmi", "-f", tag], 120)
            raise CloneError(f"docker run of the clone failed: {err.strip()[:300]}")
        return cls(name, tag, host)

    async def exec(self, command: str, cwd: str | None = None, env: dict | None = None,
                   timeout_sec: int | None = None) -> Any:
        argv = ["docker", "exec", *(["-w", cwd] if cwd else []), self.name, "sh", "-c", command]
        code, out, err = await self._host(argv, float(timeout_sec or 60))
        return SimpleNamespace(return_code=code, stdout=out, stderr=err)

    async def upload_file(self, source_path: Any, target_path: str) -> None:
        code, _, err = await self._host(["docker", "cp", str(source_path), f"{self.name}:{target_path}"], 120)
        if code != 0:
            raise OSError(f"docker cp into the clone failed: {err.strip()[:200]}")

    async def download_file(self, source_path: str, target_path: Any) -> None:
        code, _, err = await self._host(["docker", "cp", f"{self.name}:{source_path}", str(target_path)], 120)
        if code != 0:
            raise OSError(f"docker cp from the clone failed: {err.strip()[:200]}")

    async def sibling(self) -> "Clone":
        """Another throwaway container from the same commit (the image stays owned by this clone)."""
        name = f"{self.name}-{uuid.uuid4().hex[:6]}"
        code, _, err = await self._host(self._run_args(name, self.image), 180)
        if code != 0:
            raise CloneError(f"docker run of a sibling clone failed: {err.strip()[:300]}")
        return Clone(name, self.image, self._host, owns_image=False)

    async def close(self) -> None:
        await self._host(["docker", "rm", "-f", self.name], 120)
        if self._owns_image:
            await self._host(["docker", "rmi", "-f", self.image], 300)

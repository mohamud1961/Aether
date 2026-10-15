"""Disposable clones of the task container: a commit of its filesystem, started without network.

Used to run acceptance checks on a copy of a state, so nothing a check writes reaches the graded container.
A commit copies files, not processes: servers running in the task container are absent from a clone, and
volume-mounted paths are not part of the commit. Which container is committed is proven from the host
(``identify``), never taken from what the task container says about itself.
"""

from __future__ import annotations

import asyncio
import re
import time
from types import SimpleNamespace
from typing import Any, Awaitable, Callable
import uuid

from .env import Environment, run

CLONE_MEMORY = "8g"
CLONE_CPUS = "2"

HostRun = Callable[[list[str], float], Awaitable[tuple[int, str, str]]]


async def host_run(argv: list[str], timeout_s: float) -> tuple[int, str, str]:
    """Run a host command (the docker CLI) without a shell."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        if isinstance(exc, asyncio.CancelledError):
            raise
        return 124, "", f"timed out after {timeout_s:.0f}s"
    return (
        proc.returncode or 0,
        out.decode(errors="replace"),
        err.decode(errors="replace"),
    )


async def compose_clone(
    env: Environment, project: str, *, timeout_s: float | None = None
) -> "Clone":
    """Clone a compose service's main container. With ``timeout_s`` the lookup and the clone share that time."""
    if timeout_s is None:
        return await Clone.create(env, known=await compose_container(project))
    end = time.monotonic() + timeout_s

    async def bounded(argv: list[str], seconds: float) -> tuple[int, str, str]:
        return await host_run(argv, max(0.1, min(seconds, end - time.monotonic())))

    known = await compose_container(project, host=bounded)
    return await Clone.create(
        env, known=known, timeout_s=max(0.1, end - time.monotonic())
    )


class CloneError(RuntimeError):
    pass


# docker commit copies the container's labels into the image, so a clone of a compose service carries the same
# project and service labels, and `docker compose exec main` (how Harbor runs every command) may pick the clone:
# in V3 the worker's terminal and file writes went into the contract writer's clone and were lost with it. The
# commit blanks the labels compose selects by, so the clone is never a candidate.
_COMPOSE_LABELS = (
    "com.docker.compose.project",
    "com.docker.compose.service",
    "com.docker.compose.container-number",
    "com.docker.compose.oneoff",
    "com.docker.compose.config-hash",
)
_UNLABEL = [arg for label in _COMPOSE_LABELS for arg in ("--change", f"LABEL {label}=")]


async def compose_container(
    project: str, service: str = "main", host: HostRun = host_run
) -> str:
    """The container of a compose service, looked up on the host by its labels (clones have them blanked)."""
    code, out, err = await host(
        [
            "docker",
            "ps",
            "-q",
            "--no-trunc",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--filter",
            f"label=com.docker.compose.service={service}",
        ],
        60,
    )
    ids = out.split()
    if code != 0 or len(ids) != 1:
        raise CloneError(
            f"compose project {project!r} service {service!r}: expected one container, found "
            f"{len(ids)} {err.strip()[:200]}"
        )
    return ids[0]


async def identify(
    env: Environment, host: HostRun = host_run, known: str | None = None
) -> str:
    """The full id of the container ``env`` runs commands in, proven from the host.

    ``known`` is the id the environment's owner found on the host (Harbor: its compose project's ``main``
    service); without it, the container's own report (mountinfo, else its hostname) is only a candidate, since
    the worker controls that container and could make it name another one. Either way a random token is written
    through ``env`` and must be read back from that id with ``docker exec`` before anything is committed, and the
    token is removed. Without ``known``, a container that shares the token path with ``env`` (a shared volume)
    could still pass, so production runs pass ``known``."""
    candidate = known
    if candidate is None:
        # The hostname file is bind-mounted from /var/lib/docker/containers/<id>/, which names the container even
        # when a compose file sets a custom hostname; the hostname itself is the fallback.
        res = await run(
            env,
            "grep -o 'containers/[0-9a-f]\\{64\\}' /proc/self/mountinfo 2>/dev/null | head -n 1 "
            "| cut -d/ -f2; cat /etc/hostname 2>/dev/null || hostname",
        )
        candidate = (res.stdout.split() or [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", candidate):
        raise CloneError(f"cannot identify the task container (reported {candidate!r})")
    code, out, err = await host(
        ["docker", "inspect", "--format", "{{.Id}}", candidate], 60
    )
    cid = out.strip()
    if code != 0 or not re.fullmatch(r"[0-9a-f]{64}", cid):
        raise CloneError(
            f"no container {candidate!r} on this host: {err.strip()[:200]}"
        )
    token = uuid.uuid4().hex
    proof = f"/tmp/.aether-identity-{token}"
    wrote = await run(env, f"printf %s {token} > {proof}")
    try:
        code, out, _ = await host(["docker", "exec", cid, "cat", proof], 60)
    finally:
        await run(env, f"rm -f {proof}")
    if wrote.code != 0 or code != 0 or out.strip() != token:
        raise CloneError(
            f"container {candidate!r} reported by the environment is not the one it runs in"
        )
    return cid


class Clone:
    """A throwaway container started from a commit of the task container (Harbor-environment interface)."""

    def __init__(
        self, name: str, image: str, host: HostRun, owns_image: bool = True
    ) -> None:
        self.name, self.image, self._host, self._owns_image = (
            name,
            image,
            host,
            owns_image,
        )

    @staticmethod
    def _run_args(name: str, image: str) -> list[str]:
        # No network: the clone must not escape the task's egress policy.
        return [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "4096",
            "--memory",
            CLONE_MEMORY,
            "--cpus",
            CLONE_CPUS,
            "--entrypoint",
            "sh",
            image,
            "-c",
            "while :; do sleep 3600; done",
        ]

    @classmethod
    async def create(
        cls,
        env: Environment,
        host: HostRun = host_run,
        known: str | None = None,
        *,
        timeout_s: float | None = None,
    ) -> "Clone":
        """Commit and start a clone. Cancelled midway, it lets the docker commands it started finish and removes
        what they made before re-raising: a docker CLI killed mid-commit can still leave the image behind."""
        clock = getattr(env, "remaining_s", None)
        budget = (
            timeout_s
            if timeout_s is not None
            else max(0, clock())
            if callable(clock)
            else 1200.0
        )
        deadline = time.monotonic() + budget

        async def bounded(argv, seconds):
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("clone creation deadline exceeded")
            return await host(argv, min(seconds, left))

        making = asyncio.ensure_future(
            cls._create(env, bounded, known, cleanup_host=host)
        )
        try:
            return await asyncio.shield(making)
        except asyncio.CancelledError:
            try:
                clone = await making
            except (
                BaseException
            ):  # it failed on its own; _create cleans up what it made
                clone = None
            if clone is not None:
                await clone.close()
            raise

    @classmethod
    async def _create(
        cls,
        env: Environment,
        host: HostRun,
        known: str | None,
        *,
        cleanup_host: HostRun,
    ) -> "Clone":
        cid = await identify(env, host, known)
        tag = f"aether-clone:{uuid.uuid4().hex[:12]}"
        name = tag.replace(":", "-")
        try:
            code, _, err = await host(["docker", "commit", *_UNLABEL, cid, tag], 900)
            if code != 0:
                raise CloneError(f"docker commit failed: {err.strip()[:300]}")
            code, _, err = await host(cls._run_args(name, tag), 180)
            if code != 0:
                raise CloneError(f"docker run of the clone failed: {err.strip()[:300]}")
            return cls(name, tag, cleanup_host)
        except BaseException as exc:
            for argv in (["docker", "rm", "-f", name], ["docker", "rmi", "-f", tag]):
                try:
                    code, _, err = await cleanup_host(argv, 10)
                    if code and "no such" not in err.lower():
                        exc.add_note(f"clone cleanup failed ({code}): {err[:200]}")
                except Exception as cleanup_error:
                    exc.add_note(
                        f"clone cleanup failed: {type(cleanup_error).__name__}: {cleanup_error}"
                    )
            raise

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        argv = [
            "docker",
            "exec",
            *(["-w", cwd] if cwd else []),
            self.name,
            "sh",
            "-c",
            command,
        ]
        code, out, err = await self._host(argv, float(timeout_sec or 60))
        return SimpleNamespace(return_code=code, stdout=out, stderr=err)

    async def upload_file(self, source_path: Any, target_path: str) -> None:
        code, _, err = await self._host(
            ["docker", "cp", str(source_path), f"{self.name}:{target_path}"], 120
        )
        if code != 0:
            raise OSError(f"docker cp into the clone failed: {err.strip()[:200]}")

    async def download_file(self, source_path: str, target_path: Any) -> None:
        code, _, err = await self._host(
            ["docker", "cp", f"{self.name}:{source_path}", str(target_path)], 120
        )
        if code != 0:
            raise OSError(f"docker cp from the clone failed: {err.strip()[:200]}")

    async def sibling(self) -> "Clone":
        """Another throwaway container from the same commit (the image stays owned by this clone)."""
        name = f"{self.name}-{uuid.uuid4().hex[:6]}"
        code, _, err = await self._host(self._run_args(name, self.image), 180)
        if code != 0:
            raise CloneError(
                f"docker run of a sibling clone failed: {err.strip()[:300]}"
            )
        return Clone(name, self.image, self._host, owns_image=False)

    async def close(self) -> None:
        failures = []
        commands = [["docker", "rm", "-f", self.name]]
        if self._owns_image:
            commands.append(["docker", "rmi", "-f", self.image])
        for command in commands:
            try:
                code, _, error = await self._host(command, 10)
                if code and "no such" not in error.lower():
                    failures.append(f"{command[1]} ({code}): {error[:200]}")
            except Exception as exc:
                failures.append(f"{command[1]}: {type(exc).__name__}: {exc}")
        if failures:
            raise CloneError("clone cleanup incomplete: " + "; ".join(failures))

"""A plain ``docker exec`` environment: Core without Harbor (master checklist H7, portability).

It implements the three calls Core needs from an orchestrator (``exec``, ``upload_file``, ``download_file``) with the
Docker CLI against an already running container. Commands run under ``sh -c``, as the local-shell test environment
runs them, so the fault suites' semantics carry over. A command that outlives ``timeout_sec`` has its ``docker exec``
client killed and the timeout is raised; whatever it started inside the container may still be running, which is the
same truth Core already handles for any orchestrator.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Sequence


class DockerExecEnv:
    def __init__(self, container: str, *, docker: Sequence[str] = ("docker",)) -> None:
        self.container = container
        self.docker = tuple(docker)

    async def _cli(self, *args: str, timeout_s: float | None) -> tuple[int, bytes, bytes]:
        proc = await asyncio.create_subprocess_exec(
            *self.docker, *args, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except BaseException:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise
        return proc.returncode, out, err

    async def exec(self, command: str, cwd: str | None = None, env: dict | None = None,
                   timeout_sec: float | None = None) -> Any:
        args = ["exec"]
        if cwd:
            args += ["-w", cwd]
        for key, value in (env or {}).items():
            args += ["-e", f"{key}={value}"]
        code, out, err = await self._cli(*args, self.container, "sh", "-c", command, timeout_s=timeout_sec or 30)
        return SimpleNamespace(return_code=code, stdout=out.decode(errors="replace"), stderr=err.decode(errors="replace"))

    async def upload_file(self, source_path: Any, target_path: str) -> None:
        code, _, err = await self._cli("cp", str(source_path), f"{self.container}:{target_path}", timeout_s=120)
        if code != 0:
            raise OSError(f"upload to {target_path} failed: {err.decode(errors='replace').strip()}")

    async def download_file(self, source_path: str, target_path: Any) -> None:
        code, _, err = await self._cli("cp", f"{self.container}:{source_path}", str(target_path), timeout_s=120)
        if code != 0:
            text = err.decode(errors="replace").strip()
            if "No such" in text or "Could not find" in text:
                raise FileNotFoundError(source_path)
            raise OSError(f"download of {source_path} failed: {text}")

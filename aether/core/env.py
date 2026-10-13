"""Thin async helpers over a Harbor-style environment (exec / upload_file / download_file)."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import tempfile
from typing import Any, Protocol

CONTROL_DIR = "/tmp/.aether"
# Linux caps a single argv string at 128 KiB; stay well below it.
INLINE_BYTES = 48_000


class Environment(Protocol):
    async def exec(self, command: str, cwd: str | None = None, env: dict | None = None,
                   timeout_sec: int | None = None) -> Any: ...
    async def upload_file(self, source_path: Any, target_path: str) -> Any: ...
    async def download_file(self, source_path: str, target_path: Any) -> Any: ...


@dataclass(frozen=True)
class ExecResult:
    code: int | None  # None: the environment reported no exit status (never read as success)
    stdout: str
    stderr: str


def exit_code(result: Any) -> int | None:
    """The exit status an environment reported, or None when it reported none."""
    for name in ("return_code", "exit_code"):
        value = getattr(result, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


async def run(env: Environment, command: str, *, timeout_s: int = 30, cwd: str | None = None) -> ExecResult:
    result = await env.exec(command=command, cwd=cwd, env=None, timeout_sec=max(1, int(timeout_s)))
    return ExecResult(exit_code(result), str(getattr(result, "stdout", "") or ""),
                      str(getattr(result, "stderr", "") or ""))


async def put_bytes(env: Environment, data: bytes, remote: str) -> None:
    """Write bytes to a remote path, creating parents. Small payloads go inline."""
    parent = shlex.quote(os.path.dirname(remote) or "/")
    if len(data) <= INLINE_BYTES:
        payload = base64.b64encode(data).decode()
        res = await run(env, f"mkdir -p {parent} && printf %s {payload} | base64 -d > {shlex.quote(remote)}")
        if res.code != 0:
            raise OSError(f"write {remote} failed: {(res.stderr or res.stdout).strip()[:300]}")
        return
    res = await run(env, f"mkdir -p {parent}")
    if res.code != 0:
        raise OSError(f"mkdir for {remote} failed: {res.stderr.strip()[:300]}")
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "payload"
        local.write_bytes(data)
        await env.upload_file(local, remote)


async def get_bytes(env: Environment, remote: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "payload"
        await env.download_file(remote, local)
        return local.read_bytes()

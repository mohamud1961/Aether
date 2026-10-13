"""Thin async helpers over a Harbor-style environment (exec / upload_file / download_file)."""

from __future__ import annotations

import base64
import asyncio
import math
from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import tempfile
import uuid
from typing import Any, Protocol

CONTROL_DIR = "/tmp/.aether"
# Linux caps a single argv string at 128 KiB; stay well below it.
INLINE_BYTES = 48_000


class Environment(Protocol):
    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict | None = None,
        timeout_sec: int | None = None,
    ) -> Any: ...
    async def upload_file(self, source_path: Any, target_path: str) -> Any: ...
    async def download_file(self, source_path: str, target_path: Any) -> Any: ...


class DeadlineEnvironment:
    """All sandbox operations share the run's work deadline, including file transfers.

    Cleanup switches to its own short reserve; a failing closer cannot grant unlimited time.
    """

    def __init__(self, env: Environment, remaining) -> None:
        self._env, self.remaining_s = env, remaining

    def cleanup_until(self, deadline: float) -> None:
        import time

        self.remaining_s = lambda: deadline - time.monotonic()

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        left = self.remaining_s()
        if left <= 0:
            raise TimeoutError("sandbox work deadline exceeded")
        async with asyncio.timeout(left):
            return await self._env.exec(
                command=command,
                cwd=cwd,
                env=env,
                timeout_sec=max(1, math.ceil(min(left, timeout_sec or left))),
            )

    async def upload_file(self, source_path, target_path):
        async with asyncio.timeout(max(0, self.remaining_s())):
            return await self._env.upload_file(source_path, target_path)

    async def download_file(self, source_path, target_path):
        async with asyncio.timeout(max(0, self.remaining_s())):
            return await self._env.download_file(source_path, target_path)


@dataclass(frozen=True)
class ExecResult:
    code: (
        int | None
    )  # None: the environment reported no exit status (never read as success)
    stdout: str
    stderr: str


def exit_code(result: Any) -> int | None:
    """The exit status an environment reported, or None when it reported none."""
    for name in ("return_code", "exit_code"):
        value = getattr(result, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def alive_test(pid: int) -> str:
    """A shell test that a process exists and is not a zombie. ``kill -0`` alone succeeds on a zombie, and in a
    container whose PID 1 does not reap (``sleep infinity``) a dead terminal or REPL stays one and looked alive."""
    return (
        f"{{ kill -0 {int(pid)} 2>/dev/null && ! {{ [ -r /proc/{int(pid)}/stat ] && "
        f"sed 's/.*) //' /proc/{int(pid)}/stat | grep -q '^Z'; }}; }}"
    )


_KILL_TREE = (
    "if [ ! -d /proc/1 ]; then for r in {roots}; do kill -TERM -$r 2>/dev/null; pkill -TERM -P $r "
    "2>/dev/null; kill -TERM $r 2>/dev/null; done; exit 0; fi; "
    "all='{roots}'; frontier='{roots}'; while [ -n \"$frontier\" ]; do next=''; "
    "for d in /proc/[0-9]*; do p=${{d#/proc/}}; "
    "pp=$(sed 's/.*) //' $d/stat 2>/dev/null | cut -d' ' -f2) || continue; "
    'for f in $frontier; do [ "$pp" = "$f" ] && next="$next $p"; done; done; '
    'all="$all $next"; frontier=$next; done; for r in {roots}; do kill -TERM -$r 2>/dev/null; done; kill -TERM $all 2>/dev/null; sleep 0.5; '
    "for r in {roots}; do kill -KILL -$r 2>/dev/null; done; kill -KILL $all 2>/dev/null; true"
)


async def stop_process_tree(env: Environment, pids: list[int]) -> None:
    """Stop only the owned roots and their descendants; never allow PID 0 or PID 1."""
    if any(type(pid) is not int or pid <= 1 for pid in pids):
        raise ValueError("cleanup roots must be owned process IDs above 1")
    if not pids:
        return
    roots = " ".join(map(str, pids))
    result = await run(env, _KILL_TREE.format(roots=roots), timeout_s=30)
    if result.code != 0:
        raise OSError(f"process cleanup did not report success: {result.stderr[:300]}")


async def run(
    env: Environment, command: str, *, timeout_s: int = 30, cwd: str | None = None
) -> ExecResult:
    result = await env.exec(
        command=command, cwd=cwd, env=None, timeout_sec=max(1, int(timeout_s))
    )
    return ExecResult(
        exit_code(result),
        str(getattr(result, "stdout", "") or ""),
        str(getattr(result, "stderr", "") or ""),
    )


async def put_bytes(
    env: Environment, data: bytes, remote: str, *, mode: str | None = None
) -> None:
    """Replace bytes atomically within the target directory. Interrupted transfers preserve the old file.

    Existing symlinks are followed; atomic replacement must not silently replace the link itself.
    """
    q = shlex.quote
    resolved = await run(
        env,
        f"if [ -L {q(remote)} ]; then readlink -f {q(remote)} 2>/dev/null || "
        f"realpath {q(remote)}; else printf '%s\\n' {q(remote)}; fi",
    )
    if resolved.code != 0:
        raise OSError(f"cannot resolve write target {remote}")
    target = resolved.stdout.removesuffix("\n")
    checked = await run(
        env,
        f"if [ -d {q(target)} ]; then echo 'write target is a directory' >&2; exit 2; fi",
    )
    if checked.code != 0:
        raise OSError(
            f"cannot write {remote}: {(checked.stderr or checked.stdout).strip()[:300]}"
        )
    parent = q(os.path.dirname(target) or ".")
    temporary = target + ".aether-" + uuid.uuid4().hex + ".tmp"
    committed = False
    try:
        res = await run(env, f"mkdir -p {parent}")
        if res.code != 0:
            raise OSError(f"mkdir for {remote} failed: {res.stderr.strip()[:300]}")
        if len(data) <= INLINE_BYTES:
            payload = base64.b64encode(data).decode()
            res = await run(env, f"printf %s {q(payload)} | base64 -d > {q(temporary)}")
            if res.code != 0:
                raise OSError(
                    f"write {remote} failed: {(res.stderr or res.stdout).strip()[:300]}"
                )
        else:
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / "payload"
                local.write_bytes(data)
                await env.upload_file(local, temporary)
        if mode:
            res = await run(env, f"chmod {q(mode)} {q(temporary)}")
            if res.code != 0:
                raise OSError(f"preserving permissions of {remote} failed")
        # Rename the target pathname, never move a payload *inside* a directory.
        # Linux mv -T also rejects a directory that appeared after the preflight.
        # The non-Linux path supports local development with the same semantics.
        rename = q("import os,sys; os.replace(sys.argv[1],sys.argv[2])")
        res = await run(
            env,
            f'if [ "$(uname -s)" = Linux ]; then mv -fT {q(temporary)} {q(target)}; '
            f"else python3 -c {rename} {q(temporary)} {q(target)}; fi",
        )
        if res.code != 0:
            raise OSError(
                f"committing write to {remote} failed: {res.stderr.strip()[:300]}"
            )
        committed = True
    finally:
        if not committed:
            try:
                await run(env, f"rm -f {q(temporary)}")
            except Exception:
                pass  # the original error remains authoritative; run cleanup owns expired environments


async def get_bytes(env: Environment, remote: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "payload"
        await env.download_file(remote, local)
        return local.read_bytes()

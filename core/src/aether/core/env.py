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
# Exit codes of the one-shot write scripts below: each maps to the message its own step produced when the steps
# were separate execs (see docs/EXEC_COLLAPSE.md).
_RESOLVE, _DIRECTORY, _MKDIR, _WRITE, _CHMOD, _RENAME = 10, 11, 12, 13, 14, 15


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


def _b64(data: bytes) -> str:
    return shlex.quote(base64.b64encode(data).decode())


def _rename(src: str, dst: str) -> str:
    """A shell compound command that renames ``src`` over ``dst`` atomically, never moving a payload *inside* a
    directory. ``src`` and ``dst`` are already-quoted shell words."""
    replace = shlex.quote("import os,sys; os.replace(sys.argv[1],sys.argv[2])")
    return (
        f'if [ "$(uname -s)" = Linux ]; then mv -fT {src} {dst}; '
        f"else python3 -c {replace} {src} {dst}; fi"
    )


def atomic_write(path: str, data: bytes, code: int) -> str:
    """One shell statement that replaces ``path`` with ``data`` atomically: temp file beside the target, then the
    same rename as :func:`put_bytes`. The parent directory is created if missing; the temp file is removed and
    ``code`` is the exit status on any failure."""
    q = shlex.quote
    temporary = path + ".aether-" + uuid.uuid4().hex + ".tmp"
    return (
        f"mkdir -p {q(os.path.dirname(path) or '.')} && "
        f"printf %s {_b64(data)} | base64 -d > {q(temporary)} && {_rename(q(temporary), q(path))} "
        f"|| {{ rm -f {q(temporary)}; exit {code}; }}"
    )


def _write_failure(result: ExecResult, remote: str) -> OSError:
    """The error the failed step raised when the steps were separate execs."""
    detail = (result.stderr or result.stdout).strip()[:300]
    return OSError(
        {
            _RESOLVE: f"cannot resolve write target {remote}",
            _DIRECTORY: f"cannot write {remote}: {detail}",
            _MKDIR: f"mkdir for {remote} failed: {detail}",
            _WRITE: f"write {remote} failed: {detail}",
            _CHMOD: f"preserving permissions of {remote} failed",
            _RENAME: f"committing write to {remote} failed: {detail}",
        }.get(result.code, f"write {remote} failed: {detail}")
    )


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


# The same /proc walk as _KILL_TREE, printing "pid<TAB>cmdline" per descendant instead of signalling it.
_LIST_TREE = (
    "if [ ! -d /proc/1 ]; then ps -A -o pid= -o ppid= -o command= 2>/dev/null | awk -v roots='{roots}' "
    "'BEGIN{{n=split(roots,r,\" \"); for(i=1;i<=n;i++) keep[r[i]]=1}} {{pid[NR]=$1; pp[NR]=$2; "
    "c=$0; sub(/^ *[0-9]+ +[0-9]+ +/,\"\",c); cmd[NR]=c}} END{{do {{ch=0; for(i=1;i<=NR;i++) "
    "if(!(pid[i] in keep) && (pp[i] in keep)) {{keep[pid[i]]=1; out[pid[i]]=cmd[i]; ch=1}}}} while(ch); "
    "for(p in out) printf \"%s\\t%s\\n\", p, substr(out[p],1,160)}}'; exit 0; fi; frontier='{roots}'; all=''; while [ -n \"$frontier\" ]; do next=''; "
    "for d in /proc/[0-9]*; do p=${{d#/proc/}}; "
    "pp=$(sed 's/.*) //' $d/stat 2>/dev/null | cut -d' ' -f2) || continue; "
    'for f in $frontier; do [ "$pp" = "$f" ] && next="$next $p"; done; done; '
    'all="$all $next"; frontier=$next; done; '
    "for p in $all; do c=$(tr '\\0' ' ' < /proc/$p/cmdline 2>/dev/null | cut -c1-160); "
    '[ -n "$c" ] && printf "%s\\t%s\\n" "$p" "$c"; done; true'
)
_WRAPPER_CMDS = ("script -qfc", "bash --noprofile --norc", "/run.sh")


async def list_process_tree(env: Environment, pids: list[int]) -> list[str]:
    """The live descendants of the owned roots ("pid cmdline"), terminal wrapper shells excluded. Kills nothing."""
    if any(type(pid) is not int or pid <= 1 for pid in pids):
        raise ValueError("process roots must be owned process IDs above 1")
    if not pids:
        return []
    result = await run(env, _LIST_TREE.format(roots=" ".join(map(str, pids))), timeout_s=30)
    if result.code != 0:
        raise OSError(f"process listing did not report success: {result.stderr[:300]}")
    out = []
    for line in result.stdout.splitlines():
        pid, _, cmd = line.partition("\t")
        if pid.isdigit() and cmd and not any(w in cmd for w in _WRAPPER_CMDS):
            out.append(f"{pid} {cmd.strip()}")
    return out


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

    Existing symlinks are followed; atomic replacement must not silently replace the link itself. A payload that
    fits inline costs one environment call: resolve, refuse a directory, mkdir, write, chmod and rename are one
    shell script. A larger one costs three: that script without the payload, the upload, and chmod with the rename.
    """
    q = shlex.quote
    # Rename the target pathname, never move a payload *inside* a directory.
    # Linux mv -T also rejects a directory that appeared after the preflight.
    # The non-Linux path supports local development with the same semantics.
    preflight = (
        f"if [ -L {q(remote)} ]; then t=$(readlink -f {q(remote)} 2>/dev/null || realpath {q(remote)}) "
        f"|| exit {_RESOLVE}; else t={q(remote)}; fi; "
    )
    refuse_directory = (
        f"if [ -d \"$t\" ]; then echo 'write target is a directory' >&2; exit {_DIRECTORY}; fi; "
    )
    if len(data) <= INLINE_BYTES:
        rename = _rename('"$tmp"', '"$t"')
        res = await run(
            env,
            'tmp=""; trap \'[ -z "$tmp" ] || rm -f "$tmp"\' 0; '
            + preflight
            + refuse_directory
            + f'mkdir -p "$(dirname "$t")" || exit {_MKDIR}; '
            + f'tmp="$t.aether-{uuid.uuid4().hex}.tmp"; '
            + f'printf %s {_b64(data)} | base64 -d > "$tmp" || exit {_WRITE}; '
            + (f'chmod {q(mode)} "$tmp" || exit {_CHMOD}; ' if mode else "")
            + f"{rename} || exit {_RENAME}; tmp=''",
        )
        if res.code != 0:
            raise _write_failure(res, remote)
        return
    resolved = await run(
        env,
        preflight
        + "printf '%s\\n' \"$t\"; "
        + refuse_directory
        + f'mkdir -p "$(dirname "$t")" || exit {_MKDIR}',
    )
    if resolved.code != 0:
        raise _write_failure(resolved, remote)
    target = resolved.stdout.removesuffix("\n")
    temporary = target + ".aether-" + uuid.uuid4().hex + ".tmp"
    committed = False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "payload"
            local.write_bytes(data)
            await env.upload_file(local, temporary)
        res = await run(
            env,
            (f"chmod {q(mode)} {q(temporary)} || exit {_CHMOD}; " if mode else "")
            + f"{_rename(q(temporary), q(target))} || exit {_RENAME}",
        )
        if res.code != 0:
            raise _write_failure(res, remote)
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

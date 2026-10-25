"""Thin async helpers over a Harbor-style environment (exec / upload_file / download_file)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import math
import os
import shlex
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
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


_CLEANUP_OBSERVER = r"""
# Runs inside the task environment, never in the host's PID namespace by proxy.
import json, os, signal, subprocess, sys, time
roots = json.loads(sys.argv[1]); nonce = sys.argv[2]
action = sys.argv[3]; bindings = json.loads(sys.argv[4])
missing_roots = []
owned = {}; errors = []; reused = []; survivors = []; status = 'unverified'
precision = 'proc_start_ticks' if os.path.isdir('/proc/1') else 'ps_start_time_seconds'

def snapshot():
    table = {}
    if os.path.isdir('/proc/1'):
        for name in os.listdir('/proc'):
            if not name.isdigit(): continue
            try:
                with open('/proc/'+name+'/stat') as f: fields = f.read().rsplit(')',1)[1].split()
                table[int(name)] = (int(fields[1]),int(fields[2]),fields[0],fields[19])
            except FileNotFoundError:
                continue  # a process that exited during enumeration
            except (OSError, ValueError, IndexError) as exc:
                raise RuntimeError('process enumeration incomplete: '+type(exc).__name__)
    else:
        p = subprocess.run(['ps','-axo','pid=,ppid=,pgid=,stat=,lstart='],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=3)
        if p.returncode: raise RuntimeError('process enumeration failed: '+p.stderr[:200])
        for line in p.stdout.splitlines():
            fields = line.split(None,4)
            if len(fields)!=5: raise RuntimeError('process enumeration malformed')
            pid,ppid,pgid = map(int,fields[:3]); table[pid]=(ppid,pgid,fields[3],' '.join(fields[4].split()))
    if os.getpid() not in table: raise RuntimeError('process observer absent from enumeration')
    return table

def live(row):
    return row is not None and not row[2].startswith(('Z','X'))

def discover(table):
    # Retain original birth identities after parents exit; never adopt a recycled PID.
    for pid,birth in list(owned.items()):
        row=table.get(pid)
        if row and row[3]!=birth and pid not in reused: reused.append(pid)
    connected={p for p,b in owned.items() if p in table and table[p][3]==b}
    connected.update(p for p in roots if p in table and p not in owned)
    changed=True
    while changed:
        changed=False
        groups={table[p][1] for p in connected if p in table and table[p][1] in roots}
        for pid,row in table.items():
            if pid in connected or pid in owned: continue
            if row[0] in connected or row[1] in groups:
                connected.add(pid);changed=True
    for pid in connected:
        if pid not in owned: owned[pid]=table[pid][3]

try:
    table=snapshot()
    ancestors={os.getpid()}; p=os.getpid()
    while p in table and table[p][0]>1 and table[p][0] not in ancestors:
        p=table[p][0];ancestors.add(p)
    if any(r in ancestors or r<=1 for r in roots): raise RuntimeError('cleanup root is observer or ancestor')
    missing_roots = [r for r in roots if r not in table]
    if missing_roots: raise RuntimeError('root absent before observation; descendant ownership unverified')
    if bindings is not None:
        for root in roots:
            if str(root) not in bindings or table[root][3] != bindings[str(root)]:
                raise RuntimeError('launch-time process identity unavailable or changed; no signals sent')
    discover(table)
    if action in ('observe','list'):
        processes=[]
        if action == 'list':
            for pid in sorted(owned):
                if not live(table.get(pid)):continue
                cmd=subprocess.run(['ps','-p',str(pid),'-o','command='],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=3)
                if cmd.returncode or not cmd.stdout.strip():
                    current=snapshot().get(pid)
                    if not live(current) or current[3]!=owned[pid]:continue
                    raise RuntimeError('live owned process command observation failed; retention unverified')
                processes.append({'pid':pid,'command':cmd.stdout.strip()[:200]})
        status = 'observed'
        print('AETHER_CLEANUP_V1 '+json.dumps({'nonce':nonce,'roots':roots,'status':status,'processes':processes,'identities':{str(r):table[r][3] for r in roots},'identity_precision':precision}))
        sys.exit(0)
    for sig in (signal.SIGTERM,signal.SIGKILL):
        table=snapshot();discover(table)
        # Every signal has a fresh identity observation; captured identities survive parent exit.
        for pid,birth in reversed(list(owned.items())):
            if precision == 'proc_start_ticks':
                try:
                    with open('/proc/'+str(pid)+'/stat') as f: fields=f.read().rsplit(')',1)[1].split()
                    row=(int(fields[1]),int(fields[2]),fields[0],fields[19])
                except FileNotFoundError:row=None
            else:
                one=subprocess.run(['ps','-p',str(pid),'-o','pid=,ppid=,pgid=,stat=,lstart='],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=3)
                fields=one.stdout.split(None,4)
                if one.returncode not in (0,1):raise RuntimeError('identity observation failed')
                row=(int(fields[1]),int(fields[2]),fields[3],' '.join(fields[4].split())) if len(fields)==5 else None
            if not live(row): continue
            if row[3]!=birth:
                if pid not in reused:reused.append(pid)
                continue
            try:os.kill(pid,sig)
            except ProcessLookupError:pass
            except OSError as exc:errors.append({'pid':pid,'signal':int(sig),'error':type(exc).__name__})
        time.sleep(.15)
    deadline=time.monotonic()+1.5
    while True:
        table=snapshot();discover(table)
        survivors=[p for p,b in owned.items() if live(table.get(p)) and table[p][3]==b]
        if not survivors or time.monotonic()>=deadline:break
        time.sleep(.05)
    status='still_running' if survivors else ('unverified' if reused else 'confirmed_stopped')
except Exception as exc:
    errors.append({'error':type(exc).__name__,'detail':str(exc)[:300]})
print('AETHER_CLEANUP_V1 '+json.dumps({'nonce':nonce,'roots':roots,'status':status,'missing_roots':missing_roots,'observed':sorted(owned),'still_running':survivors,'identity_changed':reused,'signal_errors':errors,'identity_precision':precision,'coverage':'observed roots, descendants and anchored owned process groups; pre-observation detached/orphan processes are not proven owned'}))
sys.exit(0 if status=='confirmed_stopped' else 1)
"""

_WRAPPER_CMDS = ("script -qfc ", "bash --noprofile --norc")


async def list_process_tree(
    env: Environment, pids: list[int], *, identities=None
) -> list[str]:
    """Observed live owned processes; unavailable enumeration is never an empty list."""
    if not pids:
        return []
    receipt = await _process_observation(env, pids, "list", identities)
    return [
        f"{row['pid']} {row['command']}"
        for row in receipt["processes"]
        if row["pid"] not in pids
        and row.get("command")
        and not row["command"].startswith(_WRAPPER_CMDS)
    ]


class ProcessCleanupError(OSError):
    """Cleanup evidence, including partial effects, remains attached to the error."""

    def __init__(self, message: str, receipt: dict[str, Any] | None = None):
        super().__init__(message)
        self.receipt = receipt or {}


async def _process_observation(
    env: Environment, pids: list[int], action: str, identities=None
) -> dict[str, Any]:
    import json

    if any(type(pid) is not int or pid <= 1 for pid in pids):
        raise ValueError("cleanup roots must be owned process IDs above 1")
    roots = sorted(set(pids))
    nonce = uuid.uuid4().hex
    command = (
        "python3 -c "
        + shlex.quote(_CLEANUP_OBSERVER)
        + " "
        + shlex.quote(json.dumps(roots))
        + " "
        + nonce
        + " "
        + action
        + " "
        + shlex.quote(json.dumps(identities))
    )
    try:
        result = await run(env, command, timeout_s=15)
    except Exception as exc:
        raise ProcessCleanupError(
            "process cleanup attempted but outcome unverified: " + str(exc)[:300]
        ) from exc
    receipt = {}
    try:
        lines = [
            line
            for line in result.stdout.splitlines()
            if line.startswith("AETHER_CLEANUP_V1 ")
        ]
        if len(lines) != 1:
            raise ValueError(
                "missing unique observer receipt (python3/process enumeration may be unavailable)"
            )
        receipt = json.loads(lines[0].partition(" ")[2])
        if receipt.get("nonce") != nonce or receipt.get("roots") != roots:
            raise ValueError("cleanup receipt identity mismatch")
        expected = "confirmed_stopped" if action == "stop" else "observed"
        if receipt.get("status") != expected or result.code != 0:
            raise ProcessCleanupError("process cleanup " + str(receipt), receipt)
        if receipt.get("still_running") or receipt.get("identity_changed"):
            raise ValueError("cleanup postcondition contradicts observer status")
    except (ValueError, TypeError, KeyError) as exc:
        raise ProcessCleanupError(
            "process cleanup postcondition unverified: "
            + str(exc)
            + "; "
            + result.stderr[:200],
            receipt,
        ) from exc
    return receipt


async def process_identities(env: Environment, pids: list[int]) -> dict[str, str]:
    """Capture launch-time birth tokens before any task work; failure is not proof."""
    return (await _process_observation(env, pids, "observe"))["identities"]


async def stop_process_tree(
    env: Environment, pids: list[int], *, identities=None
) -> dict[str, Any]:
    """Stop observed identities and verify postconditions. Pass launch-time tokens.

    Receipt covers observed descendants/groups, not ownership lost before the
    first observation. Portable ps tokens have second resolution; they are not
    an atomic PID handle. Linux birth ticks and syscall race qualification are
    a separate native gate. Missing roots/binding/enumeration fail unverified.
    """
    if not pids:
        return {
            "status": "confirmed_stopped",
            "observed": [],
            "coverage": "no owned roots",
        }
    return await _process_observation(env, pids, "stop", identities)


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
    env: Environment,
    data: bytes,
    remote: str,
    *,
    mode: str | None = None,
    expected_sha256: str | None = None,
) -> None:
    """Replace bytes atomically within the target directory. Interrupted transfers preserve the old file.

    Existing symlinks are followed; atomic replacement must not silently replace the link itself.
    """
    if expected_sha256 is not None and (
        len(expected_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in expected_sha256)
    ):
        raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")
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
        # Pin the physical parent once so later symlink pivots cannot strand
        # staging or redirect this commit into a different directory. This is
        # pathname custody, not an atomic namespace/CAS guarantee.
        pinned = await run(env, f"cd {parent} && pwd -P")
        if pinned.code != 0 or not pinned.stdout.endswith("\n"):
            raise OSError(f"physical parent for {remote} could not be established")
        physical_parent = pinned.stdout.removesuffix("\n")
        target = physical_parent.rstrip("/") + "/" + os.path.basename(target)
        temporary = target + ".aether-" + uuid.uuid4().hex + ".tmp"
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
        # Every stage, including inline base64 writes and exact text edits,
        # must have the bytes the model actually submitted before replacement.
        # Checking uploads but trusting smaller staged files made an otherwise
        # successful edit silently publish corrupt bytes after lower-layer
        # corruption. This check is part of the same remote commit command.
        expected_payload = hashlib.sha256(data).hexdigest()
        proof_label = (
            "upload integrity failure"
            if len(data) > INLINE_BYTES
            else "write integrity failure"
        )
        precondition = (
            f"if [ ! -f {q(temporary)} ]; then "
            f"echo '{proof_label}: staged file missing' >&2; exit 12; fi; "
            f"actual_payload=$( (sha256sum < {q(temporary)} 2>/dev/null || "
            f"shasum -a 256 < {q(temporary)}) | cut -c1-64 ); "
            f'if [ "$actual_payload" != {q(expected_payload)} ]; then '
            f"echo '{proof_label}: staged bytes differ from submitted payload' >&2; exit 12; fi; "
        )
        precondition += (
            f"if [ -L {q(target)} ] || {{ [ -e {q(target)} ] && [ ! -f {q(target)} ]; }}; then "
            f"echo 'write conflict: destination changed to symlink or non-regular file before commit' >&2; exit 9; fi; "
        )
        if expected_sha256 is not None:
            # The comparison and final rename run in the SAME remote shell
            # invocation. This catches stale edits as late as practical,
            # though uncooperative concurrent writers can still race between
            # the hash check and rename: filesystem CAS is not guaranteed.
            precondition += (
                f"if [ ! -f {q(target)} ]; then echo 'edit conflict: source missing' >&2; exit 9; fi; "
                f"actual=$( (sha256sum < {q(target)} 2>/dev/null || "
                f"shasum -a 256 < {q(target)}) | cut -c1-64 ); "
                f'if [ "$actual" != {q(expected_sha256)} ]; then '
                f"echo 'edit conflict: file content changed before commit' >&2; exit 9; fi; "
                + (
                    f"current_mode=$(stat -Lc %a {q(target)} 2>/dev/null || "
                    f"stat -Lf %Lp {q(target)} 2>/dev/null); "
                    f'if [ "$current_mode" != {q(mode)} ]; then '
                    f"echo 'edit conflict: file permissions changed before commit' >&2; exit 9; fi; "
                    if mode
                    else ""
                )
            )
        res = await run(
            env,
            precondition
            + f'if [ "$(uname -s)" = Linux ]; then mv -fT {q(temporary)} {q(target)}; '
            + f"else python3 -c {rename} {q(temporary)} {q(target)}; fi",
        )
        if res.code != 0:
            raise OSError(
                f"committing write to {remote} failed: {res.stderr.strip()[:300]}"
            )
        committed = True
        # A successful rename acknowledges the operation, not the destination
        # bytes. Read the requested path again through the transport before
        # reporting success; it may have changed or a symlink may have pivoted.
        # This is an observation at acknowledgement time, never durable CAS.
        try:
            requested_parent = q(os.path.dirname(remote) or ".")
            requested_identity = await run(
                env,
                f"if [ -L {q(remote)} ]; then readlink -f {q(remote)} 2>/dev/null || realpath {q(remote)}; "
                f"else cd {requested_parent} && actual_parent=$(pwd -P && printf .) && "
                "actual_parent=${actual_parent%.} && actual_parent=${actual_parent%?} && "
                f"printf '%s/%s\\n' \"$actual_parent\" {q(os.path.basename(remote))}; fi",
            )
            if (
                requested_identity.code != 0
                or requested_identity.stdout.removesuffix("\n") != target
            ):
                raise OSError("requested path changed after commit")
            proof = await run(
                env,
                f"if [ ! -f {q(remote)} ]; then echo 'destination is not a regular file' >&2; exit 13; fi; "
                f"sha256sum < {q(remote)} 2>/dev/null || shasum -a 256 < {q(remote)} 2>/dev/null",
            )
        except Exception as exc:
            raise OSError(
                f"write committed to {remote}, but destination could not be verified"
            ) from exc
        if proof.code != 0 or not proof.stdout.split():
            raise OSError(
                f"write committed to {remote}, but destination could not be verified"
            )
        if proof.stdout.split()[0] != expected_payload:
            raise OSError(
                f"write committed to {remote}, but destination bytes differ from submitted payload"
            )

    finally:
        if not committed:
            import sys

            original = sys.exc_info()[1]
            try:
                cleanup = await run(env, f"rm -f {q(temporary)}")
                if cleanup.code != 0:
                    raise OSError(
                        cleanup.stderr[:200] or "stage removal did not report success"
                    )
            except Exception as cleanup_error:
                detail = f"staging cleanup unverified at {temporary}: {cleanup_error}"
                if isinstance(original, Exception):
                    raise OSError(f"{original}; {detail}") from original
                if original is not None:
                    original.add_note(
                        detail
                    )  # preserve cancellation, with partial-effect evidence
                else:
                    raise OSError(detail) from cleanup_error


async def get_bytes(env: Environment, remote: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "payload"
        await env.download_file(remote, local)
        return local.read_bytes()

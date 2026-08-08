"""Persistent PTY sessions inside one long-lived Docker task container.

The host owns only the PTY transport and transcript.  Session lifecycle is
bound to the exact container-side process generation (PID + /proc start time)
so killing a docker CLI client is never treated as proof that the task process
was stopped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import errno
from hashlib import sha256
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Any

from ..evidence_finalization import export_content_addressed_files
from ..execution import TerminalReadResult, TerminalSessionHandle, TerminalSessionState
from .docker_terminal_lifecycle import (
    generation_live,
    group_live,
    signal_exact_group,
    signal_group_after_root_exit,
    terminate_client,
    terminate_descendants_exact,
    wait_identity,
)


@dataclass
class _ManagedDockerTerminal:
    session_id: str
    name: str
    command: str
    client: subprocess.Popen[bytes]
    master_fd: int
    transcript_path: Path
    container_pid: int
    start_time_ticks: str
    command_sha256: str
    process_generation: str
    process_group_id: int
    session_leader_id: int
    condition: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.Lock())
    )
    read_offset: int = 0
    total_bytes: int = 0
    closed: bool = False
    reader_thread: threading.Thread | None = None


def _reader_loop(state: _ManagedDockerTerminal) -> None:
    """Continuously drain the host PTY into one durable raw transcript."""
    try:
        while True:
            ready, _writable, _errors = select.select([state.master_fd], [], [], 0.10)
            saw_data = False
            if ready:
                while True:
                    try:
                        chunk = os.read(state.master_fd, 65_536)
                    except BlockingIOError:
                        break
                    except OSError as exc:
                        if exc.errno in {errno.EIO, errno.EBADF}:
                            chunk = b""
                            break
                        raise
                    if not chunk:
                        break
                    saw_data = True
                    with state.transcript_path.open("ab") as handle:
                        handle.write(chunk)
                    with state.condition:
                        state.total_bytes += len(chunk)
                        state.condition.notify_all()
            if state.client.poll() is not None and not saw_data:
                final_ready, _w, _e = select.select([state.master_fd], [], [], 0)
                if not final_ready:
                    break
    finally:
        try:
            os.close(state.master_fd)
        except OSError:
            pass
        with state.condition:
            state.closed = True
            state.condition.notify_all()


class DockerTerminalManager:
    """Own exact-generation PTY sessions for one Docker container."""

    def __init__(self, container_id: str) -> None:
        self._container_id = str(container_id)
        self._sessions: dict[str, _ManagedDockerTerminal] = {}
        self._transcript_root = Path(tempfile.mkdtemp(prefix="aether_docker_terminal_"))

    def start(self, name: str, command: str, *, cwd: str) -> TerminalSessionHandle:
        nonce = uuid.uuid4().hex[:16]
        identity_path = f"/tmp/aether-terminals/{nonce}.identity"
        command_hash = sha256(command.encode("utf-8")).hexdigest()
        wrapper = (
            "set -eu\n"
            "mkdir -p /tmp/aether-terminals\n"
            "rm -f \"$2\"\n"
            "pid=$$\n"
            "start=$(awk '{print $22}' /proc/$$/stat 2>/dev/null || true)\n"
            "pgrp=$(awk '{print $5}' /proc/$$/stat 2>/dev/null || true)\n"
            "sid=$(awk '{print $6}' /proc/$$/stat 2>/dev/null || true)\n"
            "if [ -z \"$start\" ] || [ -z \"$pgrp\" ] || [ -z \"$sid\" ]; then exit 42; fi\n"
            "printf '%s\\t%s\\t%s\\t%s\\n' \"$pid\" \"$start\" \"$pgrp\" \"$sid\" >\"$2\"\n"
            "exec bash -lc \"$1\"\n"
        )
        docker_cmd = [
            "docker", "exec", "-i", "-t", "-w", cwd,
            self._container_id,
            "bash", "-lc", wrapper, "_", command, identity_path,
        ]
        master_fd, slave_fd = pty.openpty()
        transcript = self._transcript_root / f"{nonce}.pty.raw"
        transcript.touch()
        try:
            client = subprocess.Popen(
                docker_cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                close_fds=True,
            )
        except Exception:
            os.close(master_fd)
            os.close(slave_fd)
            raise
        finally:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        os.set_blocking(master_fd, False)

        identity = wait_identity(self._container_id, identity_path, client, timeout_s=3.0)
        if identity is None:
            terminate_client(client)
            try:
                os.close(master_fd)
            except OSError:
                pass
            raise RuntimeError("terminal launch failed before container process identity was recorded")
        pid, start_ticks, pgrp, sid = identity
        if pgrp != pid:
            terminate_client(client)
            try:
                os.close(master_fd)
            except OSError:
                pass
            raise RuntimeError(
                f"terminal root is not process-group leader: pid={pid} pgrp={pgrp} sid={sid}"
            )
        generation = sha256(
            f"{self._container_id}\0{pid}\0{start_ticks}\0{pgrp}\0{sid}\0{command_hash}".encode("utf-8")
        ).hexdigest()[:24]
        session_id = f"terminal:{generation}"
        state = _ManagedDockerTerminal(
            session_id=session_id,
            name=str(name),
            command=str(command),
            client=client,
            master_fd=master_fd,
            transcript_path=transcript,
            container_pid=pid,
            start_time_ticks=start_ticks,
            command_sha256=command_hash,
            process_generation=generation,
            process_group_id=pgrp,
            session_leader_id=sid,
        )
        thread = threading.Thread(
            target=_reader_loop,
            args=(state,),
            name=f"aether-docker-pty-{generation}",
            daemon=True,
        )
        state.reader_thread = thread
        self._sessions[session_id] = state
        thread.start()
        return TerminalSessionHandle(
            session_id=session_id,
            name=str(name),
            command=str(command),
            live=True,
            pid=pid,
            start_time_ticks=start_ticks,
            command_sha256=command_hash,
            process_generation=generation,
            process_group_id=pgrp,
            session_leader_id=sid,
            transcript_path=str(transcript),
        )

    def send(self, session_id: str, data: str, *, append_newline: bool = True) -> TerminalSessionState:
        state = self._require(session_id)
        if not self._generation_is_live(state):
            raise RuntimeError("terminal session process generation is not live")
        payload = str(data) + ("\n" if append_newline else "")
        raw = payload.encode("utf-8")
        written = os.write(state.master_fd, raw)
        return self._state(state, bytes_sent=written)

    def read(self, session_id: str, *, max_bytes: int = 20_000, wait_ms: int = 1000) -> TerminalReadResult:
        state = self._require(session_id)
        cap = max(1, min(20_000, int(max_bytes)))
        wait_s = max(0.0, min(30.0, int(wait_ms) / 1000.0))
        deadline = time.monotonic() + wait_s
        with state.condition:
            while state.total_bytes <= state.read_offset and not state.closed and time.monotonic() < deadline:
                state.condition.wait(timeout=max(0.0, deadline - time.monotonic()))
            if wait_s > 0 and state.total_bytes > state.read_offset and not state.closed:
                settle_s = min(0.10, wait_s)
                observed = state.total_bytes
                quiet_deadline = min(deadline, time.monotonic() + settle_s)
                while (
                    state.total_bytes - state.read_offset < cap
                    and not state.closed
                    and time.monotonic() < deadline
                    and time.monotonic() < quiet_deadline
                ):
                    now = time.monotonic()
                    state.condition.wait(timeout=max(0.0, min(deadline, quiet_deadline) - now))
                    if state.total_bytes > observed:
                        observed = state.total_bytes
                        quiet_deadline = min(deadline, time.monotonic() + settle_s)
            start = state.read_offset
            available = max(0, state.total_bytes - start)
            length = min(cap, available)
            state.read_offset += length
            cursor = state.read_offset
            total = state.total_bytes
        raw = b""
        if length:
            with state.transcript_path.open("rb") as handle:
                handle.seek(start)
                raw = handle.read(length)
        live = self._generation_is_live(state)
        exit_code = state.client.poll()
        return TerminalReadResult(
            session_id=session_id,
            output=raw.decode("utf-8", "replace"),
            bytes_read=len(raw),
            cursor=cursor,
            total_bytes=total,
            more_available=cursor < total,
            live=live,
            exit_code=exit_code,
            process_generation=state.process_generation,
            process_group_id=state.process_group_id,
            session_leader_id=state.session_leader_id,
        )

    def wait(self, session_id: str, *, timeout_s: float = 30.0) -> TerminalSessionState:
        state = self._require(session_id)
        bounded = max(0.0, min(300.0, float(timeout_s)))
        try:
            if bounded > 0:
                state.client.wait(timeout=bounded)
        except subprocess.TimeoutExpired:
            pass
        if state.client.poll() is not None and state.reader_thread is not None:
            state.reader_thread.join(timeout=0.5)
        return self._state(state)

    def interrupt(self, session_id: str) -> TerminalSessionState:
        state = self._require(session_id)
        if self._generation_is_live(state):
            signal_exact_group(
                self._container_id, pid=state.container_pid, start_ticks=state.start_time_ticks,
                process_group_id=state.process_group_id, session_leader_id=state.session_leader_id,
                signal_name="INT",
            )
            time.sleep(0.05)
        return self._state(state, signal_name="SIGINT")

    def close(self, session_id: str) -> TerminalSessionState:
        state = self._require(session_id)
        if self._generation_is_live(state):
            # Kill descendants leaf-first while the exact root shell is still
            # alive so it can reap them. Production task containers use a
            # simple `sleep infinity` PID 1, which does not reliably reap
            # adopted zombies; killing the whole group simultaneously can
            # otherwise leave dead-but-unreaped descendants for the rest of
            # the task episode.
            terminate_descendants_exact(
                self._container_id, pid=state.container_pid, start_ticks=state.start_time_ticks,
                process_group_id=state.process_group_id, session_leader_id=state.session_leader_id,
                signal_name="TERM",
            )
            reap_deadline = time.monotonic() + 0.75
            while self._generation_is_live(state) and time.monotonic() < reap_deadline:
                time.sleep(0.05)
            if self._generation_is_live(state):
                signal_exact_group(
                    self._container_id, pid=state.container_pid, start_ticks=state.start_time_ticks,
                    process_group_id=state.process_group_id, session_leader_id=state.session_leader_id,
                    signal_name="TERM",
                )
            deadline = time.monotonic() + 1.0
            while self._group_is_live(state) and time.monotonic() < deadline:
                time.sleep(0.05)
            if self._group_is_live(state):
                signal_group_after_root_exit(
                    self._container_id, process_group_id=state.process_group_id,
                    session_leader_id=state.session_leader_id, signal_name="KILL",
                )
        try:
            state.client.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            terminate_client(state.client)
        if state.reader_thread is not None:
            state.reader_thread.join(timeout=1.0)
        return self._state(state)

    def close_all(self) -> None:
        for session_id in tuple(self._sessions):
            try:
                self.close(session_id)
            except Exception:
                state = self._sessions.get(session_id)
                if state is not None:
                    terminate_client(state.client)
                    if state.reader_thread is not None:
                        state.reader_thread.join(timeout=0.5)

    def export_to(self, destination: str) -> dict[str, Any]:
        paths = tuple(
            str(state.transcript_path)
            for state in self._sessions.values()
            if state.transcript_path.is_file()
        )
        return export_content_addressed_files(paths, destination)

    def cleanup(self) -> None:
        self.close_all()
        shutil.rmtree(self._transcript_root, ignore_errors=True)

    def _require(self, session_id: str) -> _ManagedDockerTerminal:
        state = self._sessions.get(str(session_id))
        if state is None:
            raise KeyError(f"unknown terminal session: {session_id}")
        return state

    def _generation_is_live(self, state: _ManagedDockerTerminal) -> bool:
        return generation_live(
            self._container_id, state.client, pid=state.container_pid,
            start_ticks=state.start_time_ticks, process_group_id=state.process_group_id,
            session_leader_id=state.session_leader_id,
        )

    def _group_is_live(self, state: _ManagedDockerTerminal) -> bool:
        return group_live(
            self._container_id, process_group_id=state.process_group_id,
            session_leader_id=state.session_leader_id,
        )

    def _state(
        self,
        state: _ManagedDockerTerminal,
        *,
        bytes_sent: int = 0,
        signal_name: str = "",
    ) -> TerminalSessionState:
        live = self._generation_is_live(state)
        return TerminalSessionState(
            session_id=state.session_id,
            live=live,
            exit_code=state.client.poll(),
            cursor=state.read_offset,
            total_bytes=state.total_bytes,
            more_available=state.read_offset < state.total_bytes,
            bytes_sent=bytes_sent,
            signal=signal_name,
            process_generation=state.process_generation,
        )

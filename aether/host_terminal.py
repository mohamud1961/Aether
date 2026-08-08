"""Persistent PTY sessions for the host-backed SubprocessExecutor.

The Popen handle is the lifecycle authority for the root process.  A private
session/process-group is created for every terminal so send/interrupt/close do
not target unrelated host processes.  Raw PTY bytes are drained continuously
into a durable transcript and exposed to the solver only through cursor-based
reads; host transcript paths remain evidence-internal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import errno
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid

from .evidence_finalization import export_content_addressed_files
from .execution import TerminalReadResult, TerminalSessionHandle, TerminalSessionState


@dataclass
class _ManagedHostTerminal:
    session_id: str
    name: str
    command: str
    process: subprocess.Popen[bytes]
    master_fd: int
    transcript_path: Path
    process_generation: str
    process_group_id: int
    session_leader_id: int
    start_time_ticks: str = ""
    condition: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.Lock())
    )
    read_offset: int = 0
    total_bytes: int = 0
    closed: bool = False
    reader_thread: threading.Thread | None = None


def _reader_loop(state: _ManagedHostTerminal) -> None:
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
            if state.process.poll() is not None and not saw_data:
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


def _linux_start_ticks(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[21]
    except (OSError, IndexError):
        return ""


class HostTerminalManager:
    """Own persistent PTYs for one host executor instance."""

    def __init__(self) -> None:
        self._sessions: dict[str, _ManagedHostTerminal] = {}
        self._transcript_root = Path(tempfile.mkdtemp(prefix="aether_host_terminal_"))

    def start(self, name: str, command: str, *, cwd: str) -> TerminalSessionHandle:
        master_fd, slave_fd = pty.openpty()
        command_hash = sha256(command.encode("utf-8")).hexdigest()
        nonce = uuid.uuid4().hex
        transcript = self._transcript_root / f"{nonce}.pty.raw"
        transcript.touch()
        try:
            process = subprocess.Popen(
                ["bash", "-lc", command],
                cwd=cwd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                close_fds=True,
            )
        except Exception:
            os.close(master_fd)
            raise
        finally:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        os.set_blocking(master_fd, False)
        pgid = os.getpgid(process.pid)
        sid = os.getsid(process.pid)
        if pgid != process.pid or sid != process.pid:
            self._terminate_process(process)
            try:
                os.close(master_fd)
            except OSError:
                pass
            raise RuntimeError("host terminal root is not its own process-group/session leader")
        start_ticks = _linux_start_ticks(process.pid)
        generation = sha256(
            f"host\0{process.pid}\0{start_ticks}\0{command_hash}\0{nonce}".encode("utf-8")
        ).hexdigest()[:24]
        session_id = f"terminal:{generation}"
        state = _ManagedHostTerminal(
            session_id=session_id,
            name=str(name),
            command=str(command),
            process=process,
            master_fd=master_fd,
            transcript_path=transcript,
            process_generation=generation,
            process_group_id=pgid,
            session_leader_id=sid,
            start_time_ticks=start_ticks,
        )
        thread = threading.Thread(
            target=_reader_loop,
            args=(state,),
            name=f"aether-host-pty-{generation}",
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
            pid=process.pid,
            start_time_ticks=start_ticks,
            command_sha256=command_hash,
            process_generation=generation,
            process_group_id=pgid,
            session_leader_id=sid,
            transcript_path=str(transcript),
        )

    def send(self, session_id: str, data: str, *, append_newline: bool = True) -> TerminalSessionState:
        state = self._require(session_id)
        if not self._root_live(state):
            raise RuntimeError("terminal session is not live")
        payload = (str(data) + ("\n" if append_newline else "")).encode("utf-8")
        written = os.write(state.master_fd, payload)
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
                observed = state.total_bytes
                quiet_deadline = min(deadline, time.monotonic() + min(0.10, wait_s))
                while (
                    state.total_bytes - state.read_offset < cap
                    and not state.closed
                    and time.monotonic() < quiet_deadline
                ):
                    state.condition.wait(timeout=max(0.0, quiet_deadline - time.monotonic()))
                    if state.total_bytes > observed:
                        observed = state.total_bytes
                        quiet_deadline = min(deadline, time.monotonic() + min(0.10, wait_s))
            start = state.read_offset
            length = min(cap, max(0, state.total_bytes - start))
            state.read_offset += length
            cursor = state.read_offset
            total = state.total_bytes
        raw = b""
        if length:
            with state.transcript_path.open("rb") as handle:
                handle.seek(start)
                raw = handle.read(length)
        return TerminalReadResult(
            session_id=session_id,
            output=raw.decode("utf-8", "replace"),
            bytes_read=len(raw),
            cursor=cursor,
            total_bytes=total,
            more_available=cursor < total,
            live=self._root_live(state),
            exit_code=state.process.poll(),
            process_generation=state.process_generation,
            process_group_id=state.process_group_id,
            session_leader_id=state.session_leader_id,
        )

    def wait(self, session_id: str, *, timeout_s: float = 30.0) -> TerminalSessionState:
        state = self._require(session_id)
        bounded = max(0.0, min(300.0, float(timeout_s)))
        try:
            if bounded > 0:
                state.process.wait(timeout=bounded)
        except subprocess.TimeoutExpired:
            pass
        if state.process.poll() is not None and state.reader_thread is not None:
            state.reader_thread.join(timeout=0.5)
        return self._state(state)

    def interrupt(self, session_id: str) -> TerminalSessionState:
        state = self._require(session_id)
        if self._root_live(state):
            os.killpg(state.process_group_id, signal.SIGINT)
            time.sleep(0.05)
        return self._state(state, signal_name="SIGINT")

    def close(self, session_id: str) -> TerminalSessionState:
        state = self._require(session_id)
        if self._group_exists(state.process_group_id):
            try:
                os.killpg(state.process_group_id, signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 1.0
            while self._group_exists(state.process_group_id) and time.monotonic() < deadline:
                time.sleep(0.05)
            if self._group_exists(state.process_group_id):
                try:
                    os.killpg(state.process_group_id, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        try:
            state.process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self._terminate_process(state.process)
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
                    self._terminate_process(state.process)

    def export_to(self, destination: str) -> dict[str, object]:
        return export_content_addressed_files(
            (
                str(state.transcript_path)
                for state in self._sessions.values()
                if state.transcript_path.is_file()
            ),
            destination,
        )

    def cleanup(self) -> None:
        self.close_all()
        shutil.rmtree(self._transcript_root, ignore_errors=True)

    def _require(self, session_id: str) -> _ManagedHostTerminal:
        state = self._sessions.get(str(session_id))
        if state is None:
            raise KeyError(f"unknown terminal session: {session_id}")
        return state

    @staticmethod
    def _root_live(state: _ManagedHostTerminal) -> bool:
        return state.process.poll() is None

    @staticmethod
    def _group_exists(pgid: int) -> bool:
        try:
            os.killpg(pgid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    @staticmethod
    def _terminate_process(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass

    def _state(
        self,
        state: _ManagedHostTerminal,
        *,
        bytes_sent: int = 0,
        signal_name: str = "",
    ) -> TerminalSessionState:
        return TerminalSessionState(
            session_id=state.session_id,
            live=self._root_live(state),
            exit_code=state.process.poll(),
            cursor=state.read_offset,
            total_bytes=state.total_bytes,
            more_available=state.read_offset < state.total_bytes,
            bytes_sent=bytes_sent,
            signal=signal_name,
            process_generation=state.process_generation,
            process_group_id=state.process_group_id,
            session_leader_id=state.session_leader_id,
        )

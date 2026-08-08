"""DockerExecExecutor PTY adapter kept separate for the executor LOC boundary."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from ..execution import TerminalReadResult, TerminalSessionHandle, TerminalSessionState
from ..workspace_state import capture_workspace_state, diff_workspace_states
from .docker_terminal import DockerTerminalManager


class DockerTerminalExecutorMixin:
    """Add truthful persistent terminal sessions to a Docker executor."""

    _terminal_manager: DockerTerminalManager
    _terminal_workspace_state: Any
    _host_root: str
    _container_workdir: str

    def _init_terminal_sessions(self, container_id: str) -> None:
        self._terminal_manager = DockerTerminalManager(container_id)
        self._terminal_workspace_state = None

    def _export_terminal_transcripts(self, destination: str) -> dict[str, Any]:
        return self._terminal_manager.export_to(str(Path(destination) / "terminals"))

    def close(self) -> None:
        self._terminal_manager.cleanup()

    def _terminal_delta(self) -> dict[str, Any]:
        current = capture_workspace_state(self._host_root)
        previous = self._terminal_workspace_state or current
        delta = diff_workspace_states(previous, current)
        self._terminal_workspace_state = current
        return delta

    def start_terminal_session(
        self, name: str, command: str, *, cwd: str | None = None
    ) -> TerminalSessionHandle:
        self._terminal_workspace_state = capture_workspace_state(self._host_root)
        handle = self._terminal_manager.start(
            name, command, cwd=cwd or self._container_workdir
        )
        return replace(handle, state_delta=self._terminal_delta())

    def terminal_send(
        self, session_id: str, data: str, *, append_newline: bool = True
    ) -> TerminalSessionState:
        state = self._terminal_manager.send(
            session_id, data, append_newline=append_newline
        )
        return replace(state, state_delta=self._terminal_delta())

    def terminal_read(
        self, session_id: str, *, max_bytes: int = 20_000, wait_ms: int = 1000
    ) -> TerminalReadResult:
        result = self._terminal_manager.read(
            session_id, max_bytes=max_bytes, wait_ms=wait_ms
        )
        return replace(result, state_delta=self._terminal_delta())

    def terminal_wait(
        self, session_id: str, *, timeout_s: float = 30.0
    ) -> TerminalSessionState:
        state = self._terminal_manager.wait(session_id, timeout_s=timeout_s)
        return replace(state, state_delta=self._terminal_delta())

    def terminal_interrupt(self, session_id: str) -> TerminalSessionState:
        state = self._terminal_manager.interrupt(session_id)
        return replace(state, state_delta=self._terminal_delta())

    def terminal_close(self, session_id: str) -> TerminalSessionState:
        state = self._terminal_manager.close(session_id)
        return replace(state, state_delta=self._terminal_delta())

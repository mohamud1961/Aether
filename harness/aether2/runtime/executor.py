"""Workspace scoped foreground execution helper with optional container backing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any
import errno
import os
import shlex
import subprocess
import time
import uuid

from harness.aether2.traces.envelope import ErrorInfo, FileDelta, ProcessDelta


@dataclass(frozen=True)
class RawResult:
    tool: str
    command: str
    exit_code: int | None
    duration_sec: float
    cwd: str
    stdout: str
    stderr: str
    workspace_root: str
    timed_out: bool = False
    boundary_violation: bool = False
    files_changed: list[FileDelta] = field(default_factory=list)
    process_delta: ProcessDelta = field(default_factory=ProcessDelta)
    blind_retry_blocked: bool = False
    error: ErrorInfo | None = None


@dataclass(frozen=True)
class ContainerBackend:
    """Execution backend describing the live task environment."""

    kind: str = "local"
    container_id: str | None = None
    container_workspace_root: str | None = None
    exec_shell: str = "sh"
    base_env: dict[str, str] = field(default_factory=dict)


class ContainerExecutor:
    """Run foreground shell commands with a workspace-root boundary."""

    _FOREGROUND_SCRIPT_DIR = ".aether2/foreground_commands"

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        *,
        backend: ContainerBackend | None = None,
    ) -> None:
        root = Path(workspace_root) if workspace_root is not None else Path.cwd()
        self.workspace_root = root.resolve(strict=False)
        self.backend = backend or ContainerBackend()
        container_root = self.backend.container_workspace_root or self.workspace_root.as_posix()
        self.container_workspace_root = self._normalize_container_root(container_root)

    @property
    def execution_boundary(self) -> str:
        return self.backend.kind

    def run(self, cmd: str, timeout_sec: int, cwd: str | Path | None = None) -> RawResult:
        command = str(cmd)
        started_at = perf_counter()
        cwd_path, container_cwd, cwd_error = self._resolve_cwd(cwd)
        if cwd_error is not None:
            return self._finish_error(
                command=command,
                cwd_path=cwd_path,
                started_at=started_at,
                exit_code=2,
                timed_out=False,
                boundary_violation=cwd_error.kind == "workspace_boundary_violation",
                error=cwd_error,
            )

        blocked_token = self._find_boundary_violation(command, cwd_path)
        if blocked_token is not None:
            return self._finish_error(
                command=command,
                cwd_path=cwd_path,
                started_at=started_at,
                exit_code=126,
                timed_out=False,
                boundary_violation=True,
                error=ErrorInfo(
                    kind="workspace_boundary_violation",
                    message=(
                        "workspace_boundary_violation: blocked path-like token outside the task workspace: "
                        f"{self._format_blocked_token(blocked_token)}"
                    ),
                    reason_code="workspace_boundary_violation",
                    failure_class="path_visibility",
                    details="heuristic workspace-root boundary guard",
                    tool_name="run_command",
                    command=command,
                ),
            )

        try:
            completed = self._run_subprocess(command, cwd_path=cwd_path, container_cwd=container_cwd, timeout_sec=timeout_sec)
        except subprocess.TimeoutExpired as exc:
            duration_sec = perf_counter() - started_at
            stdout, stderr = self._normalize_timeout_streams(exc)
            return RawResult(
                tool="run_command",
                command=command,
                exit_code=124,
                duration_sec=duration_sec,
                cwd=str(cwd_path),
                stdout=stdout,
                stderr=stderr,
                workspace_root=str(self.workspace_root),
                timed_out=True,
                boundary_violation=False,
                error=ErrorInfo(
                    kind="timeout",
                    message=f"command timed out after {timeout_sec}s",
                    reason_code="timeout",
                    failure_class="timeout",
                    details="foreground command exceeded the configured timeout",
                    tool_name="run_command",
                    command=command,
                    exit_code=124,
                    timed_out=True,
                ),
            )
        except OSError as exc:
            return self._finish_error(
                command=command,
                cwd_path=cwd_path,
                started_at=started_at,
                exit_code=71,
                timed_out=False,
                boundary_violation=False,
                error=ErrorInfo(
                    kind="spawn_failed",
                    message=str(exc),
                    reason_code="spawn_failed",
                    failure_class="runtime",
                    details="foreground command could not be spawned",
                    tool_name="run_command",
                    command=command,
                ),
            )

        duration_sec = perf_counter() - started_at
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = int(completed.returncode)
        error = None
        if exit_code != 0:
            error = ErrorInfo(
                kind="nonzero_exit",
                message=f"command exited with status {exit_code}",
                reason_code="nonzero_exit",
                failure_class="process_exit",
                details="foreground command completed but returned a non-zero exit code",
                tool_name="run_command",
                command=command,
                exit_code=exit_code,
                timed_out=False,
            )
        return RawResult(
            tool="run_command",
            command=command,
            exit_code=exit_code,
            duration_sec=duration_sec,
            cwd=str(cwd_path),
            stdout=stdout,
            stderr=stderr,
            workspace_root=str(self.workspace_root),
            timed_out=False,
            boundary_violation=False,
            error=error,
        )

    def resolve_workspace_path(self, path: str | Path) -> Path:
        resolved, error = self._resolve_workspace_path(path)
        if error is not None:
            raise ValueError(error.message)
        return resolved

    def to_container_path(self, path: str | Path) -> str:
        resolved = self.resolve_workspace_path(path)
        relative = resolved.relative_to(self.workspace_root).as_posix()
        if relative == ".":
            return self.container_workspace_root
        return f"{self.container_workspace_root}/{relative}"

    def _resolve_cwd(self, cwd: str | Path | None) -> tuple[Path, str, ErrorInfo | None]:
        candidate = self.workspace_root if cwd is None else cwd
        resolved, error = self._resolve_workspace_path(candidate)
        if error is not None:
            return self.workspace_root, self.container_workspace_root, error
        if not resolved.exists() or not resolved.is_dir():
            requested_cwd = "." if cwd is None else self._display_workspace_location(resolved)
            return (
                resolved,
                self._host_to_container_path(resolved),
                ErrorInfo(
                    kind="cwd_missing",
                    message=f"cwd_missing: {requested_cwd} does not exist as a directory inside the task workspace",
                    reason_code="cwd_missing",
                    failure_class="filesystem",
                    details="the resolved cwd must exist and be a directory",
                    tool_name="run_command",
                    command="",
                    timed_out=False,
                ),
            )
        return resolved, self._host_to_container_path(resolved), None

    def _find_boundary_violation(self, command: str, cwd_path: Path) -> str | None:
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return None
        for index, token in enumerate(tokens):
            if index == 0:
                continue
            candidate = self._candidate_path_from_token(token, cwd_path)
            if candidate is None:
                continue
            if not self._is_within_workspace(candidate):
                return token
        return None

    def _format_blocked_token(self, token: str) -> str:
        stripped = token.strip()
        if not stripped:
            return "<path>"
        if stripped.startswith(("~", "/")):
            return "<outside-workspace-path>"
        return stripped

    def _candidate_path_from_token(self, token: str, cwd_path: Path) -> Path | None:
        if not token or token.startswith("-") or "://" in token:
            return None
        if not self._looks_like_path_token(token):
            return None
        resolved, error = self._resolve_workspace_path(token, cwd_path=cwd_path)
        if error is not None:
            return self._coerce_path(token).expanduser().resolve(strict=False)
        return resolved

    def _looks_like_path_token(self, token: str) -> bool:
        if token.startswith(("/", "./", "../", "~/")):
            return True
        if "/" in token:
            return True
        return Path(token).suffix.lower() in {
            ".csv",
            ".ini",
            ".json",
            ".jsonl",
            ".log",
            ".md",
            ".py",
            ".sh",
            ".txt",
            ".toml",
            ".xml",
            ".yaml",
            ".yml",
        }

    def _is_within_workspace(self, path: Path) -> bool:
        try:
            path.relative_to(self.workspace_root)
        except ValueError:
            return False
        return True

    def _coerce_path(self, value: str | Path) -> Path:
        return value if isinstance(value, Path) else Path(value)

    def _resolve_workspace_path(
        self,
        value: str | Path,
        *,
        cwd_path: Path | None = None,
    ) -> tuple[Path, ErrorInfo | None]:
        candidate = self._coerce_path(value).expanduser()
        base_cwd = cwd_path or self.workspace_root
        if candidate.is_absolute():
            candidate_str = candidate.as_posix()
            if candidate_str == self.container_workspace_root or candidate_str.startswith(f"{self.container_workspace_root}/"):
                relative = candidate_str.removeprefix(self.container_workspace_root).lstrip("/")
                resolved = (self.workspace_root / relative).resolve(strict=False)
            else:
                resolved = candidate.resolve(strict=False)
        else:
            resolved = (base_cwd / candidate).resolve(strict=False)

        if not self._is_within_workspace(resolved):
            return (
                resolved,
                ErrorInfo(
                    kind="workspace_boundary_violation",
                    message="workspace_boundary_violation: path must stay inside the task workspace",
                    reason_code="workspace_boundary_violation",
                    failure_class="path_visibility",
                    details="all paths must stay inside the configured workspace root",
                    tool_name="filesystem",
                    command="",
                    timed_out=False,
                ),
            )
        return resolved, None

    def _host_to_container_path(self, path: Path) -> str:
        relative = path.resolve(strict=False).relative_to(self.workspace_root).as_posix()
        if relative == ".":
            return self.container_workspace_root
        return f"{self.container_workspace_root}/{relative}"

    def _normalize_container_root(self, value: str) -> str:
        root = str(value).strip() or "/app"
        if not root.startswith("/"):
            root = "/" + root
        return root.rstrip("/") or "/"

    def _display_workspace_location(self, path: Path) -> str:
        relative = path.resolve(strict=False).relative_to(self.workspace_root).as_posix()
        return "." if relative == "." else relative

    def _requires_literal_script(self, command: str) -> bool:
        return "\n" in command or "\r" in command

    def _write_literal_script(self, command: str) -> tuple[Path, str]:
        scripts_dir = self.workspace_root / self._FOREGROUND_SCRIPT_DIR
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / f"cmd-{uuid.uuid4().hex}.sh"
        with script_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(command)
        script_path.chmod(0o700)
        return script_path, self._host_to_container_path(script_path)

    _SPAWN_RETRY_MAX = 5
    _SPAWN_RETRY_BASE_SEC = 0.2

    def _run_subprocess(
        self,
        command: str,
        *,
        cwd_path: Path,
        container_cwd: str,
        timeout_sec: int,
    ) -> subprocess.CompletedProcess[str]:
        timeout = max(0.0, float(timeout_sec))
        attempt = 0
        while True:
            try:
                return self._run_subprocess_once(
                    command, cwd_path=cwd_path, container_cwd=container_cwd, timeout=timeout
                )
            except OSError as exc:
                attempt += 1
                if getattr(exc, "errno", None) != errno.EAGAIN or attempt >= self._SPAWN_RETRY_MAX:
                    raise
                time.sleep(self._SPAWN_RETRY_BASE_SEC * (2 ** (attempt - 1)))

    def _run_subprocess_once(
        self,
        command: str,
        *,
        cwd_path: Path,
        container_cwd: str,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        if self._requires_literal_script(command):
            host_script_path, container_script_path = self._write_literal_script(command)
        else:
            host_script_path, container_script_path = None, None
        if self.backend.kind == "docker":
            if not self.backend.container_id:
                raise OSError("docker backend requires a container_id")
            exec_cmd = [
                "docker",
                "exec",
                "-w",
                container_cwd,
            ]
            for key, value in sorted(self.backend.base_env.items()):
                exec_cmd.extend(["-e", f"{key}={value}"])
            exec_cmd.extend(
                [
                    self.backend.container_id,
                    self.backend.exec_shell,
                ]
            )
            if container_script_path is not None:
                exec_cmd.append(container_script_path)
            else:
                exec_cmd.extend(["-lc", command])
            return subprocess.run(
                exec_cmd,
                cwd=str(cwd_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                env=os.environ.copy(),
            )
        if host_script_path is not None:
            return subprocess.run(
                ["/bin/sh", str(host_script_path)],
                cwd=str(cwd_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                env=os.environ.copy(),
            )
        return subprocess.run(
            ["/bin/sh", "-lc", command],
            cwd=str(cwd_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )

    def _normalize_timeout_streams(self, exc: subprocess.TimeoutExpired) -> tuple[str, str]:
        return self._stream_to_text(exc.stdout), self._stream_to_text(exc.stderr)

    def _stream_to_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _finish_error(
        self,
        *,
        command: str,
        cwd_path: Path,
        started_at: float,
        exit_code: int | None,
        timed_out: bool,
        boundary_violation: bool,
        error: ErrorInfo,
    ) -> RawResult:
        return RawResult(
            tool="run_command",
            command=command,
            exit_code=exit_code,
            duration_sec=perf_counter() - started_at,
            cwd=str(cwd_path),
            stdout="",
            stderr="",
            workspace_root=str(self.workspace_root),
            timed_out=timed_out,
            boundary_violation=boundary_violation,
            error=error,
        )


__all__ = ["ContainerExecutor", "RawResult"]

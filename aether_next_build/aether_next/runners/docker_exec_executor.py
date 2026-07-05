"""Docker-exec-backed Executor (extracted from docker_runner for the 500-LOC cap).

Commands run inside the long-lived task container via ``docker exec``; file
operations act on the host bind-mounted workspace.
"""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from ..execution import (
    ArtifactInspection,
    CommandResult,
    ProcessHandle,
    ProbeResult,
)
from ..real_executor import (
    StreamSpooler,
    SubprocessExecutor,
    _decode_partial,
    _snapshot_mtimes,
)
from ..runtime_ir import EnvMap

import logging
import re


class DockerExecExecutor:
    """Executor that runs commands inside a Docker container via ``docker exec``.

    File operations (read/write/exists/glob/inspect/refresh_envmap) operate
    on the HOST ``workspace_root_host`` directory, which is bind-mounted
    into the container at ``container_workdir``.
    """

    def __init__(
        self,
        container_id: str,
        workspace_root_host: str,
        *,
        default_timeout_s: int = 120,
        container_workdir: str = "/app",
    ) -> None:
        self._container_id = container_id
        self._host_root = str(Path(workspace_root_host).resolve())
        self._default_timeout_s = max(1, default_timeout_s)
        self._container_workdir = container_workdir
        # Delegate host filesystem ops to a SubprocessExecutor on the host dir.
        self._host_exec = SubprocessExecutor(
            self._host_root, default_timeout_s=default_timeout_s,
        )
        self._spooler = StreamSpooler()

    # ---- Filesystem (host-side, bind-mounted) --------------------------------

    def read_file(self, path: str) -> str:
        return self._host_exec.read_file(path)

    def read_file_bytes(self, path: str) -> bytes:
        return self._host_exec.read_file_bytes(path)

    def write_file(self, path: str, content: str) -> None:
        self._host_exec.write_file(path, content)

    def exists(self, path: str) -> bool:
        return self._host_exec.exists(path)

    def glob(self, pattern: str) -> tuple[str, ...]:
        return self._host_exec.glob(pattern)

    def inspect_artifact(self, path: str, mode: str) -> ArtifactInspection:
        return self._host_exec.inspect_artifact(path, mode)

    def refresh_envmap(self, envmap: EnvMap) -> EnvMap:
        return self._host_exec.refresh_envmap(envmap)

    # ---- Command execution (inside Docker container) -------------------------

    def run_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout_s: int = 30,
    ) -> CommandResult:
        effective_timeout = timeout_s if timeout_s > 0 else self._default_timeout_s
        effective_cwd = cwd or self._container_workdir

        before = _snapshot_mtimes(self._host_root)

        docker_cmd = [
            "docker", "exec", "-w", effective_cwd,
            self._container_id,
            "bash", "-lc", command,
        ]
        timed_out = False
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True, errors="replace",
                timeout=effective_timeout,
            )
            exit_code = proc.returncode
            raw_stdout, raw_stderr = proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            raw_stdout = _decode_partial(exc.stdout)
            raw_stderr = _decode_partial(exc.stderr) + (
                f"\n[harness] docker exec timed out after {effective_timeout}s; "
                "partial output above is preserved"
            )

        stdout_total, stderr_total = len(raw_stdout), len(raw_stderr)
        stdout, stdout_overflow = self._spooler.finalize(raw_stdout, "stdout")
        stderr, stderr_overflow = self._spooler.finalize(raw_stderr, "stderr")

        after = _snapshot_mtimes(self._host_root)

        modified: list[str] = []
        produced: list[str] = []
        for rel, mtime in after.items():
            if rel not in before:
                produced.append(rel)
            elif before[rel] != mtime:
                modified.append(rel)

        return CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            modified_paths=tuple(sorted(modified)),
            produced_artifacts=tuple(sorted(produced)),
            metrics={},
            stdout_overflow_path=stdout_overflow,
            stderr_overflow_path=stderr_overflow,
            stdout_bytes_total=stdout_total,
            stderr_bytes_total=stderr_total,
            timed_out=timed_out,
        )

    # ---- Process management (inside Docker container) ------------------------

    def launch_process(
        self,
        name: str,
        command: str,
        *,
        interactive: bool = False,
        cwd: str | None = None,
    ) -> ProcessHandle:
        effective_cwd = cwd or self._container_workdir
        process_id = f"docker-proc-{uuid.uuid4().hex[:8]}"

        docker_cmd = [
            "docker", "exec", "-d", "-w", effective_cwd,
            self._container_id,
            "bash", "-lc", command,
        ]
        try:
            subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True, errors="replace",
                timeout=30,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            return ProcessHandle(
                process_id=process_id,
                name=name,
                command=command,
                interactive=interactive,
                live=False,
                detail=f"docker exec -d failed: {exc.stderr or exc.stdout}",
            )
        except subprocess.TimeoutExpired:
            return ProcessHandle(
                process_id=process_id,
                name=name,
                command=command,
                interactive=interactive,
                live=False,
                detail="docker exec -d timed out",
            )

        return ProcessHandle(
            process_id=process_id,
            name=name,
            command=command,
            interactive=interactive,
            live=True,
            detail=f"launched in container {self._container_id[:12]}",
        )

    def probe_process(self, target: str) -> ProbeResult:
        """Probe a live service endpoint or named process inside the container.

        ``probe_service`` is the solver-visible affordance for service liveness.
        A target shaped like ``host:port`` or ``port`` must test the TCP endpoint,
        not look for a process command line containing that literal string.
        """
        tcp_target = _parse_tcp_probe_target(target)
        if tcp_target is not None:
            return self._probe_tcp_endpoint(target, *tcp_target)
        return self._probe_process_name(target)

    def _probe_process_name(self, target: str) -> ProbeResult:
        """Probe whether a named process is running inside the container."""
        docker_cmd = [
            "docker", "exec", self._container_id,
            "pgrep", "-f", target,
        ]
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True, errors="replace",
                timeout=10,
            )
            alive = proc.returncode == 0
            return ProbeResult(
                target=target,
                live=alive,
                detail=proc.stdout.strip() if alive else "not found",
                service_name=target,
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(
                target=target,
                live=False,
                detail="probe timed out",
                service_name=target,
            )

    def _probe_tcp_endpoint(self, target: str, host: str, port: int) -> ProbeResult:
        code = (
            "import socket,sys\n"
            "s=socket.socket()\n"
            "s.settimeout(5)\n"
            f"rc=s.connect_ex(({host!r},{port}))\n"
            "s.close()\n"
            "print('open' if rc == 0 else f'closed rc={rc}')\n"
            "sys.exit(0 if rc == 0 else 1)\n"
        )
        docker_cmd = [
            "docker", "exec", self._container_id,
            "python3", "-c", code,
        ]
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True, errors="replace",
                timeout=10,
            )
            alive = proc.returncode == 0
            detail = (proc.stdout or proc.stderr).strip()
            return ProbeResult(
                target=target,
                live=alive,
                detail=detail or ("open" if alive else "closed"),
                service_name=target,
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(
                target=target,
                live=False,
                detail="tcp probe timed out",
                service_name=target,
            )

    def stop_process(self, target: str) -> bool:
        """Kill a process by name inside the container."""
        docker_cmd = [
            "docker", "exec", self._container_id,
            "pkill", "-f", target,
        ]
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True, errors="replace",
                timeout=10,
            )
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            return False



_log = logging.getLogger(__name__)


def _parse_tcp_probe_target(target: str) -> tuple[str, int] | None:
    raw = str(target or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        port = int(raw)
        if 0 < port <= 65535:
            return ("127.0.0.1", port)
        return None
    # Keep process names such as "python3 server.py" on the process-probe path.
    if any(ch.isspace() for ch in raw):
        return None
    host, sep, port_text = raw.rpartition(":")
    if not sep or not port_text.isdigit():
        return None
    # Avoid treating arbitrary labels with colons as TCP unless the endpoint is
    # plausibly host-like. This remains generic and task-agnostic.
    clean_host = host.strip() or "127.0.0.1"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", clean_host):
        return None
    port = int(port_text)
    if not 0 < port <= 65535:
        return None
    return clean_host, port

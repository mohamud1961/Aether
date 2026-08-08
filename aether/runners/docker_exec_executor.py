"""Docker-exec-backed Executor (extracted from docker_runner for the 500-LOC cap).

Commands run inside the long-lived task container via ``docker exec``; file
operations act on the host bind-mounted workspace.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from ..execution import (
    ArtifactInspection,
    CommandResult,
    ProcessHandle,
    ProbeResult,
    JobProbeResult,
)
from ..real_executor import (
    StreamSpooler,
    SubprocessExecutor,
    _decode_partial,
)
from ..runtime_ir import EnvMap
from ..workspace_state import capture_workspace_state, diff_workspace_states
from .docker_terminal_executor import DockerTerminalExecutorMixin
from .docker_exec_helpers import (
    docker_any_pid_descends_from,
    docker_process_generation_state,
    docker_stop_process_generation,
    docker_tcp_listener_owners,
    parse_tcp_probe_target,
)



class DockerExecExecutor(DockerTerminalExecutorMixin):
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
        initial_snapshot_host_root: str | None = None,
    ) -> None:
        self._container_id = container_id
        self._host_root = str(Path(workspace_root_host).resolve())
        self._default_timeout_s = max(1, default_timeout_s)
        self._container_workdir = container_workdir
        self._initial_snapshot_host_root = (
            str(Path(initial_snapshot_host_root).resolve())
            if initial_snapshot_host_root else ""
        )
        self._initial_snapshot_digest = ""
        if self._initial_snapshot_host_root:
            snapshot_state = capture_workspace_state(self._initial_snapshot_host_root)
            if snapshot_state.truncated:
                raise RuntimeError("initial workspace snapshot inventory is truncated")
            self._initial_snapshot_digest = snapshot_state.digest
        self._host_exec = SubprocessExecutor(
            self._host_root, default_timeout_s=default_timeout_s,
        )
        self._spooler = StreamSpooler()
        self._process_registry: dict[str, ProcessHandle] = {}
        self._init_terminal_sessions(self._container_id)

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

    def for_workspace(self, workspace_root: str) -> "DockerExecExecutor":
        """Return an executor for a trusted isolated path in this container."""
        return DockerExecExecutor(
            self._container_id,
            self._host_root,
            default_timeout_s=self._default_timeout_s,
            container_workdir=workspace_root,
            initial_snapshot_host_root=self._initial_snapshot_host_root or None,
        )

    def _comparison_relative_path(self, path: str) -> str:
        raw = str(path or "").strip()
        if not raw:
            raise ValueError("initial/current comparison requires a path")
        workdir = str(self._container_workdir or "/app").rstrip("/") or "/"
        if raw == workdir:
            return "."
        if raw.startswith(workdir + "/"):
            raw = raw[len(workdir) + 1:]
        elif raw.startswith("/"):
            raise ValueError("initial/current comparison path must be inside the task workspace")
        parts = Path(raw).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("initial/current comparison path must be a normalized workspace-relative path")
        return str(Path(*parts))

    @staticmethod
    def _stable_path_identity(root: str, relative: str) -> dict[str, Any]:
        base = Path(root).resolve()
        candidate = base / relative
        if not candidate.exists() and not candidate.is_symlink():
            return {"present": False, "kind": "missing", "bytes": 0, "sha256": "", "stable": True}
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise RuntimeError("comparison target escapes its workspace root") from exc
        before = candidate.lstat()
        if candidate.is_symlink():
            first = candidate.readlink().as_posix()
            second = candidate.readlink().as_posix()
            after = candidate.lstat()
            stable = (before.st_ino, before.st_mtime_ns, before.st_size, first) == (
                after.st_ino, after.st_mtime_ns, after.st_size, second
            )
            encoded = first.encode("utf-8", "surrogateescape")
            return {
                "present": True, "kind": "symlink", "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(), "stable": stable,
            }
        if candidate.is_file():
            data = candidate.read_bytes()
            after = candidate.lstat()
            stable = (before.st_ino, before.st_mtime_ns, before.st_size) == (
                after.st_ino, after.st_mtime_ns, after.st_size
            )
            return {
                "present": True, "kind": "file", "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(), "stable": stable,
            }
        if candidate.is_dir():
            first = capture_workspace_state(candidate)
            second = capture_workspace_state(candidate)
            if first.truncated or second.truncated:
                raise RuntimeError("comparison directory inventory is truncated")
            return {
                "present": True, "kind": "directory", "bytes": 0,
                "sha256": first.digest, "stable": first.digest == second.digest,
                "entry_count": first.entry_count,
            }
        after = candidate.lstat()
        stable = (before.st_mode, before.st_ino, before.st_mtime_ns, before.st_size) == (
            after.st_mode, after.st_ino, after.st_mtime_ns, after.st_size
        )
        material = f"{before.st_mode}:{before.st_size}".encode("ascii")
        return {
            "present": True, "kind": "other", "bytes": int(before.st_size),
            "sha256": hashlib.sha256(material).hexdigest(), "stable": stable,
        }

    def compare_initial_path(self, path: str) -> dict[str, Any]:
        """Compare current workspace state with the immutable generation-0 snapshot.

        Returns only mechanical identity/relation evidence; semantic correctness
        remains owned by the Verifier/task contract.
        """
        if not self._initial_snapshot_host_root or not self._initial_snapshot_digest:
            raise RuntimeError("initial workspace snapshot is unavailable to this executor")
        relative = self._comparison_relative_path(path)
        current_before = self._stable_path_identity(self._host_root, relative)
        initial = self._stable_path_identity(self._initial_snapshot_host_root, relative)
        current_after = self._stable_path_identity(self._host_root, relative)
        current_stable = bool(
            current_before.get("stable")
            and current_after.get("stable")
            and current_before == current_after
        )
        if not current_stable:
            raise RuntimeError("current comparison target changed during final observation")
        if not bool(initial.get("stable")):
            raise RuntimeError("immutable initial comparison target was not stable")
        if not initial["present"] and not current_after["present"]:
            relation = "absent_both"
        elif not initial["present"]:
            relation = "created"
        elif not current_after["present"]:
            relation = "removed"
        elif initial["kind"] != current_after["kind"]:
            relation = "kind_changed"
        elif initial["sha256"] == current_after["sha256"]:
            relation = "equal"
        else:
            relation = "different"
        payload = {
            "path": relative,
            "initial": initial,
            "current": current_after,
            "relation": relation,
            "equal": relation == "equal",
            "current_stable": True,
            "initial_snapshot_digest": self._initial_snapshot_digest,
        }
        payload["relation_digest"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return payload

    def run_independent_verifier_command(
        self,
        command: str,
        *,
        workspace_root: str,
        timeout_s: int = 30,
    ) -> dict[str, Any]:
        """Run PERSISTENT Verifier shell in a sibling container from current rootfs.

        ``docker commit`` snapshots the live task-container root filesystem so
        runtime installs/configuration are preserved. The F78 command child is
        outside the /app bind mount and therefore enters that snapshot. A new
        container then copies that exact child to /app, runs with Docker's
        private PID/mount boundary and network=none, and is destroyed together
        with the temporary image before authority is returned.
        """
        nonce = uuid.uuid4().hex[:16]
        image_tag = f"aether-persistent-f80-{nonce}:snapshot"
        sibling_name = f"aether-persistent-f80-{nonce}"
        metadata: dict[str, Any] = {
            "execution_isolation": "docker_current_rootfs_snapshot_sibling",
            "isolation_backend": "docker_snapshot_sibling",
            "independent_isolation_verified": False,
            "isolation_cleanup_verified": False,
            "mount_namespace_private": True,
            "pid_namespace_private": True,
            "network_namespace_private": True,
            "network_scope": "docker_none",
            "parent_container_id_sha256": hashlib.sha256(self._container_id.encode("utf-8")).hexdigest(),
            "workspace_snapshot_path_sha256": hashlib.sha256(str(workspace_root).encode("utf-8")).hexdigest(),
        }
        if (
            not str(workspace_root).startswith("/app.verifier_overlay_")
            or ".command_" not in str(workspace_root)
        ):
            return {"error": "verifier_independent_isolation_invalid_docker_child", "metadata": metadata}
        result: CommandResult | None = None
        error = ""
        image_created = False
        sibling_created = False
        try:
            commit = subprocess.run(
                ["docker", "commit", "--pause=true", self._container_id, image_tag],
                capture_output=True, text=True, errors="replace", timeout=120,
            )
            if commit.returncode != 0:
                return {
                    "error": "verifier_independent_isolation_docker_commit_failed: "
                    + (commit.stderr or commit.stdout)[-1000:],
                    "metadata": metadata,
                }
            image_created = True
            snapshot_id = commit.stdout.strip()
            metadata["snapshot_image_id_sha256"] = hashlib.sha256(snapshot_id.encode("utf-8")).hexdigest()
            bootstrap = (
                'set -eu; src="$1"; cmd="$2"; '
                'rm -rf /app; mkdir -p /app; cp -a "$src"/. /app/; '
                'cd /app; exec bash -lc "$cmd"'
            )
            docker_cmd = [
                "docker", "run", "--name", sibling_name,
                "--network", "none", "--workdir", "/",
                "--entrypoint", "bash", image_tag,
                "-lc", bootstrap, "aether-f80", str(workspace_root), command,
            ]
            effective_timeout = timeout_s if timeout_s > 0 else self._default_timeout_s
            timed_out = False
            try:
                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True, text=True, errors="replace",
                    timeout=effective_timeout,
                )
                sibling_created = True
                exit_code = proc.returncode
                raw_stdout, raw_stderr = proc.stdout, proc.stderr
            except subprocess.TimeoutExpired as exc:
                sibling_created = True
                timed_out = True
                exit_code = 124
                raw_stdout = _decode_partial(exc.stdout)
                raw_stderr = _decode_partial(exc.stderr) + (
                    f"\n[harness] isolated verifier sibling timed out after {effective_timeout}s"
                )
            result = CommandResult(
                command=command,
                exit_code=exit_code,
                stdout=raw_stdout,
                stderr=raw_stderr,
                stdout_bytes_total=len(raw_stdout),
                stderr_bytes_total=len(raw_stderr),
                timed_out=timed_out,
            )
            metadata["independent_isolation_verified"] = True
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            error = f"verifier_independent_isolation_docker_setup_failed: {type(exc).__name__}: {exc}"
        finally:
            def _cleanup_run(args: list[str], *, timeout: int) -> tuple[subprocess.CompletedProcess[str] | None, str]:
                try:
                    return subprocess.run(
                        args, capture_output=True, text=True, errors="replace", timeout=timeout,
                    ), ""
                except (OSError, subprocess.SubprocessError) as exc:
                    return None, f"{type(exc).__name__}: {exc}"

            # Always attempt removal by the unguessable sibling name. This
            # covers failures where docker created the container but the client
            # call failed before local bookkeeping could mark sibling_created.
            rm, rm_error = _cleanup_run(["docker", "rm", "-f", sibling_name], timeout=30)
            inspect, inspect_error = _cleanup_run(["docker", "inspect", sibling_name], timeout=15)
            sibling_absent = inspect is not None and inspect.returncode != 0
            image_rm, image_rm_error = (
                _cleanup_run(["docker", "image", "rm", "-f", image_tag], timeout=60)
                if image_created else (None, "")
            )
            image_inspect, image_inspect_error = _cleanup_run(
                ["docker", "image", "inspect", image_tag], timeout=15,
            )
            image_absent = image_inspect is not None and image_inspect.returncode != 0
            metadata.update({
                "sibling_container_removed": sibling_absent,
                "snapshot_image_removed": image_absent,
                "isolation_cleanup_verified": bool(sibling_absent and image_absent),
                "sibling_remove_exit": None if rm is None else rm.returncode,
                "snapshot_image_remove_exit": None if image_rm is None else image_rm.returncode,
                "sibling_remove_error": rm_error,
                "sibling_inspect_error": inspect_error,
                "snapshot_image_remove_error": image_rm_error,
                "snapshot_image_inspect_error": image_inspect_error,
            })
            if not metadata["isolation_cleanup_verified"]:
                error = error or "verifier_independent_isolation_docker_cleanup_failed"
        if error or not metadata["independent_isolation_verified"] or not metadata["isolation_cleanup_verified"]:
            return {"error": error or "verifier_independent_isolation_not_verified", "metadata": metadata}
        return {"result": result, "metadata": metadata}

    def export_spools(self, destination: str) -> dict[str, Any]:
        # Preserve the established root command-spool manifest; terminal raw
        # transcripts are additive content-addressed evidence beneath it.
        command_manifest = self._spooler.export_to(destination)
        command_manifest["terminal_transcripts"] = self._export_terminal_transcripts(destination)
        return command_manifest

    def run_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout_s: int = 30,
    ) -> CommandResult:
        effective_timeout = timeout_s if timeout_s > 0 else self._default_timeout_s
        effective_cwd = cwd or self._container_workdir

        before_state = capture_workspace_state(self._host_root)

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

        after_state = capture_workspace_state(self._host_root)
        state_delta = diff_workspace_states(before_state, after_state)
        modified = sorted(
            set(state_delta["content_changed_paths"])
            | set(state_delta["metadata_changed_paths"])
        )
        produced = tuple(state_delta["created_paths"])
        removed = tuple(state_delta["removed_paths"])

        return CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            modified_paths=tuple(modified),
            produced_artifacts=produced,
            removed_paths=removed,
            state_delta=state_delta,
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
        launch_nonce = uuid.uuid4().hex[:12]
        command_sha256 = hashlib.sha256(command.encode("utf-8")).hexdigest()
        stdout_log = f"/tmp/aether-processes/{launch_nonce}.stdout.log"
        stderr_log = f"/tmp/aether-processes/{launch_nonce}.stderr.log"
        status_log = f"/tmp/aether-processes/{launch_nonce}.status"
        wrapper = (
            "set -eu\n"
            "mkdir -p /tmp/aether-processes\n"
            "rm -f \"$4\"\n"
            "nohup bash -lc 'bash -lc \"$1\"; rc=$?; printf \"%s\\n\" \"$rc\" >\"$2\"; exit \"$rc\"' "
            "_ \"$1\" \"$4\" >\"$2\" 2>\"$3\" </dev/null &\n"
            "pid=$!\n"
            "i=0\n"
            "while [ $i -lt 20 ] && [ ! -r /proc/$pid/stat ]; do i=$((i+1)); sleep 0.05; done\n"
            "start=$(awk '{print $22}' /proc/$pid/stat 2>/dev/null || true)\n"
            "if [ -z \"$start\" ]; then exit 42; fi\n"
            "printf '%s\\t%s\\n' \"$pid\" \"$start\"\n"
        )
        docker_cmd = [
            "docker", "exec", "-w", effective_cwd,
            self._container_id,
            "bash", "-lc", wrapper, "_", command, stdout_log, stderr_log, status_log,
        ]
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=30,
                check=True,
            )
            fields = proc.stdout.strip().split("\t")
            if len(fields) != 2 or not fields[0].isdigit() or not fields[1].isdigit():
                raise ValueError(f"invalid launch identity: {proc.stdout!r}")
            pid = int(fields[0])
            start_ticks = fields[1]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            detail = str(exc)
            if isinstance(exc, subprocess.CalledProcessError):
                detail = str(exc.stderr or exc.stdout or exc)
            return ProcessHandle(
                process_id=f"failed:{launch_nonce}",
                name=name,
                command=command,
                interactive=interactive,
                live=False,
                detail=f"process launch failed: {detail}",
                command_sha256=command_sha256,
                stdout_log=stdout_log,
                stderr_log=stderr_log,
                status_log=status_log,
                status="unknown",
            )

        generation = hashlib.sha256(
            f"{self._container_id}\0{pid}\0{start_ticks}\0{command_sha256}".encode("utf-8")
        ).hexdigest()[:24]
        process_id = f"process:{generation}"
        handle = ProcessHandle(
            process_id=process_id,
            name=name,
            command=command,
            interactive=interactive,
            live=True,
            detail=f"pid={pid} start_ticks={start_ticks} container={self._container_id[:12]}",
            pid=pid,
            start_time_ticks=start_ticks,
            command_sha256=command_sha256,
            process_generation=generation,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            status_log=status_log,
            status="running",
        )
        # A new launch generation supersedes earlier registered generations of
        # the same service name for proof purposes, even if the old OS process
        # remains alive until explicitly stopped.
        self._process_registry[process_id] = handle
        return handle

    def probe_process(self, target: str) -> ProbeResult:
        """Probe a live service endpoint or named process inside the container.

        ``probe_service`` is the solver-visible affordance for service liveness.
        A target shaped like ``host:port`` or ``port`` must test the TCP endpoint,
        not look for a process command line containing that literal string.
        """
        tcp_target = parse_tcp_probe_target(target)
        if tcp_target is not None:
            return self._probe_tcp_endpoint(target, *tcp_target)
        return self._probe_process_name(target)

    def _registered_process(self, target: str) -> ProcessHandle | None:
        direct = self._process_registry.get(target)
        if direct is not None:
            return direct
        matches = [item for item in self._process_registry.values() if item.name == target]
        return matches[-1] if matches else None

    def _probe_process_name(self, target: str) -> ProbeResult:
        handle = self._registered_process(target)
        if handle is None or handle.pid is None or not handle.start_time_ticks:
            return ProbeResult(
                target=target, live=False, detail="no registered process generation",
                service_name=target,
            )
        status, _current, detail = docker_process_generation_state(
            self._container_id, handle.pid, handle.start_time_ticks
        )
        alive = status == "running"
        return ProbeResult(
            target=target,
            live=alive,
            detail=detail,
            service_name=handle.name,
            process_id=handle.process_id,
            process_generation=handle.process_generation,
            process_generation_verified=alive,
            endpoint_owner_pids=((handle.pid,) if alive else ()),
        )

    def probe_job(self, target: str) -> JobProbeResult:
        handle = self._registered_process(target)
        if handle is None or handle.pid is None or not handle.start_time_ticks:
            return JobProbeResult(
                target=target, found=False, status="unknown", completed=False,
                detail="no registered job generation",
            )
        status, _current, detail = docker_process_generation_state(
            self._container_id, handle.pid, handle.start_time_ticks
        )
        terminal = status == "exited"
        verified = bool(status in {"running", "exited"} and handle.process_generation)
        return JobProbeResult(
            target=target, found=True, status=status, completed=terminal,
            succeeded=None, exit_code=None, detail=detail,
            job_id=handle.process_id, process_id=handle.process_id,
            process_generation=handle.process_generation,
            process_generation_verified=verified,
            lifecycle_authority="registered_process_generation", pid=handle.pid,
        )

    def _probe_tcp_endpoint(self, target: str, host: str, port: int) -> ProbeResult:
        del host  # Listener ownership is resolved from the container network namespace.
        live, owner_pids, inodes, detail = docker_tcp_listener_owners(
            self._container_id, port
        )
        registered: list[ProcessHandle] = []
        if live and owner_pids:
            for item in self._process_registry.values():
                if not item.live or item.pid is None:
                    continue
                if not self._probe_process_name(item.process_id).live:
                    continue
                if item.pid in owner_pids or docker_any_pid_descends_from(
                    self._container_id, owner_pids, item.pid
                ):
                    registered.append(item)
        owner = registered[-1] if registered else None
        payload = {
            "live": live,
            "owner_pids": list(owner_pids),
            "inodes": list(inodes),
            "detail": detail,
        }
        return ProbeResult(
            target=target,
            live=live,
            detail=json.dumps(payload, sort_keys=True),
            service_name=(owner.name if owner is not None else target),
            process_id=(owner.process_id if owner is not None else ""),
            process_generation=(owner.process_generation if owner is not None else ""),
            process_generation_verified=bool(owner is not None and live),
            endpoint_owner_pids=owner_pids,
        )

    def stop_process(self, target: str) -> bool:
        handle = self._registered_process(target)
        if handle is None or handle.pid is None or not handle.start_time_ticks:
            return False
        probe = self._probe_process_name(handle.process_id)
        if not probe.live:
            self._process_registry[handle.process_id] = ProcessHandle(
                **{**handle.__dict__, "live": False, "detail": "already not live"}
            )
            return False
        stopped = docker_stop_process_generation(
            self._container_id, handle.pid, handle.start_time_ticks
        )
        if stopped:
            self._process_registry[handle.process_id] = ProcessHandle(
                **{**handle.__dict__, "live": False, "detail": "stopped"}
            )
        return stopped

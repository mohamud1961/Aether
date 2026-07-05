"""Docker-backed runner for Terminal-Bench tasks against the Aether-Next kernel."""
from __future__ import annotations

import json as _json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
import logging
from typing import Any, Iterator

from ..classifier import HarnessLimiterClassifier, reconcile_grader_alignment
from ..envmap_builder import build_envmap_from_task
from ..environment_probe import probe_environment
from ..execution import (
    ArtifactInspection,
    CommandResult,
    ProcessHandle,
    ProbeResult,
)
from ..kernel import AetherNextKernel, KernelResult
from ..model_hooks import ModelCallable, ModelHooks
from ..real_executor import (
    StreamSpooler,
    SubprocessExecutor,
    _decode_partial,
    _resolve_safe,
    _snapshot_mtimes,
    _SKIP_DIRS,
    _MAX_SCAN_ENTRIES,
)
from ..run_adapter import ensure_certified_architect_mode, workbench_architect_for
from ..runtime_ir import EnvMap, normalize_relpath
from ..task_metadata_loader import load_task_instruction, load_task_metadata
from .docker_helpers import detect_grader_command, ensure_image_available, seed_workspace_from_image

# Prevent git "dubious ownership" on bind-mounted workspaces (uid mismatch).
_GIT_SAFE_DIR_CMD = "git config --global --add safe.directory '*' || true"


def _load_task_toml(task_dir: str) -> dict[str, Any]:
    return load_task_metadata(task_dir)


class KernelRunTimeout(TimeoutError):
    """Raised when the per-task kernel loop exceeds the wall-clock budget."""


_MAX_RUN_TIMEOUT_S = 14_400


def _effective_run_timeout_s(run_timeout_s: int, task_toml: dict[str, Any]) -> tuple[int, str]:
    """Honor the task's own declared agent budget; never let a generic runner
    default silently starve a long task.  ``run_timeout_s`` remains the floor;
    the declared budget raises it up to a hard safety cap."""
    agent = task_toml.get("agent") if isinstance(task_toml.get("agent"), dict) else {}
    raw = agent.get("timeout_sec")
    try:
        declared = int(float(raw)) if raw is not None else 0
    except (TypeError, ValueError):
        declared = 0
    if declared <= 0:
        return run_timeout_s, f"runner_default={run_timeout_s}"
    effective = max(run_timeout_s, min(declared, _MAX_RUN_TIMEOUT_S))
    return effective, (
        f"task_declared={declared}; runner_floor={run_timeout_s}; "
        f"cap={_MAX_RUN_TIMEOUT_S}; effective={effective}"
    )


def _resolve_grader_reward(
    *,
    container_id: str,
    task_dir: str,
    grader_exit: int,
    grader_error: str | None,
) -> tuple[float, str | None, str]:
    """Resolve the official grader reward for supported task layouts.

    Mirrored ``task.toml`` tasks may write ``/logs/verifier/reward.txt``.
    Official YAML tasks commonly expose pass/fail through ``run-tests.sh``'s
    exit code and do not write a reward file.  Treating that missing file as a
    grader failure turns genuine passes into invalid rows, so the fallback is
    layout-specific rather than global.
    """
    if grader_error is not None:
        return 0.0, grader_error, "grader_error"

    try:
        rp = subprocess.run(
            ["docker", "exec", container_id, "cat", "/logs/verifier/reward.txt"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
        )
    except Exception:
        rp = None

    if rp is not None and rp.returncode == 0 and rp.stdout.strip():
        return (1.0 if rp.stdout.strip() == "1" else 0.0), None, "reward_txt"

    if (Path(task_dir) / "run-tests.sh").exists():
        return (1.0 if grader_exit == 0 else 0.0), None, "official_run_tests_exit_code"

    if rp is None:
        return 0.0, "reward.txt unreadable", "reward_txt_error"
    return 0.0, "reward.txt missing or empty", "reward_txt_missing"


# ---------------------------------------------------------------------------
# DockerExecExecutor
# ---------------------------------------------------------------------------

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


def _receipt_summary(result: KernelResult) -> list[dict[str, Any]]:
    """Compact receipt list (mirrors run_adapter._receipt_summary)."""
    return [{"receipt_id": r.receipt_id, "kind": r.kind, "success": r.success,
             "failure_class": r.failure_class, "summary": r.summary}
            for r in result.receipts]


def _latest_model_verifier_verdict(result: KernelResult) -> str:
    for receipt in reversed(result.receipts):
        if receipt.kind != "model_verifier_result":
            continue
        payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        verdict = str(payload.get("verdict", "") or "").strip()
        if verdict:
            return verdict
        if receipt.success:
            return "completed"
        if receipt.failure_class:
            return str(receipt.failure_class)
        return ""
    return ""


def _classification_fields_for_record(
    *,
    classification: Any,
    result: KernelResult,
    reward: float,
    grader_error: str | None,
    kernel_timed_out: bool,
) -> tuple[str, str, str, str]:
    record_status = result.status
    classifier_label = classification.label
    classifier_confidence = classification.confidence
    classifier_detail = classification.detail
    if grader_error is not None:
        record_status = "grader_error"
        classifier_label = "timeout_resource_failure" if "timeout" in grader_error else "grader_failure"
        classifier_confidence = "high"
        classifier_detail = grader_error
    elif kernel_timed_out and reward >= 1.0:
        classifier_label = "none"
        classifier_confidence = "high"
        classifier_detail = (
            "official grader passed after kernel timeout; task state was solved, "
            "but the agent loop remained step/time inefficient"
        )
    return record_status, classifier_label, classifier_confidence, classifier_detail


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


def _docker_snapshot(container_id: str, dest: str) -> None:
    """Best-effort ``docker cp`` of /app to *dest*."""
    os.makedirs(dest, exist_ok=True)
    try:
        subprocess.run(["docker", "cp", f"{container_id}:/app/.", dest],
                       capture_output=True, text=True, errors="replace", timeout=60)
    except Exception as exc:
        _log.warning("snapshot to %s failed: %s", dest, exc)


def run_tbench_task(
    *,
    task_dir: str,
    image: str,
    architect_model: ModelCallable,
    solver_model: ModelCallable,
    max_steps: int = 30,
    run_timeout_s: int = 1800,
    trace_dir: str | None = None,
    architect_mode: str = "workbench",
    snapshot_dir: str | None = None,
    snapshot_steps: tuple[int, ...] = (),
    run_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one Terminal-Bench task end-to-end.  Never raises -- errors are
    captured into the record so that a pilot loop can continue.
    """
    task_name = Path(task_dir).name
    container_id: str | None = None
    workspace_dir: str | None = None
    run_trace: Any = None

    try:
        ensure_certified_architect_mode(architect_mode)
    except ValueError as exc:
        return _error_record(
            task_name,
            image,
            "invalid_architect_mode",
            str(exc),
            architect_mode=architect_mode,
        )

    task_toml = _load_task_toml(task_dir)
    run_timeout_s, run_timeout_policy = _effective_run_timeout_s(run_timeout_s, task_toml)

    try:  # outer try: catch ALL exceptions so the pilot never gets a raise
        # -- 1. Temp workspace + seed ----------------------------------------
        workspace_dir = tempfile.mkdtemp(prefix=f"tbench_{task_name}_")
        workspace_path = Path(workspace_dir)

        image_error = ensure_image_available(image, pull_timeout_s=max(300, run_timeout_s))
        if image_error is not None:
            return _error_record(task_name, image, "image_pull_failed", image_error, architect_mode=architect_mode)

        seed_error = seed_workspace_from_image(
            image,
            workspace_path,
            create_timeout_s=max(300, run_timeout_s),
            copy_timeout_s=max(300, run_timeout_s),
        )
        if seed_error is not None:
            return _error_record(task_name, image, "workspace_seed_failed", seed_error, architect_mode=architect_mode)

        # -- 2. Start long-lived container ------------------------------------
        task_dir_abs = str(Path(task_dir).resolve())
        tests_mount = os.path.join(task_dir_abs, "tests")

        docker_run_cmd = [
            "docker", "run", "-d",
            "-v", f"{workspace_dir}:/app",
            "-w", "/app",
            image,
            "sleep", "infinity",
        ]
        start = subprocess.run(
            docker_run_cmd,
            capture_output=True,
            text=True, errors="replace",
            timeout=60,
        )
        if start.returncode != 0:
            return _error_record(
                task_name, image, "container_start_failed",
                (start.stdout + start.stderr).strip(),
                architect_mode=architect_mode,
            )
        container_id = start.stdout.strip()

        # Best-effort: fix git "dubious ownership" (host uid != container root).
        # Harmlessly returns non-zero when git is not installed in the image.
        subprocess.run(
            ["docker", "exec", container_id, "sh", "-lc", _GIT_SAFE_DIR_CMD],
            capture_output=True,
            text=True, errors="replace",
            timeout=30,
        )

        # -- 3. Build kernel inputs and run -----------------------------------
        instruction_text = load_task_instruction(task_dir)

        envmap = build_envmap_from_task(
            workspace_dir,
            instruction_text,
            workspace_root="/app",
            task_toml=task_toml,
        )

        executor = DockerExecExecutor(
            container_id,
            workspace_dir,
            default_timeout_s=min(run_timeout_s, 300),
            container_workdir="/app",
        )
        static_hints = envmap.task_metadata.get("static_task_hints", {})
        required_tool_hints = envmap.task_metadata.get("required_tool_hints", ())
        extra_command_names = (
            tuple(required_tool_hints)
            if isinstance(required_tool_hints, (list, tuple))
            else tuple(static_hints.get("tool_hints", ())) if isinstance(static_hints, dict) else ()
        )
        env_probe = probe_environment(
            executor,
            workspace_root="/app",
            extra_command_names=tuple(extra_command_names) if isinstance(extra_command_names, (list, tuple)) else (),
        )
        envmap = build_envmap_from_task(
            workspace_dir,
            instruction_text,
            workspace_root="/app",
            task_metadata={"environment_probe": env_probe},
            task_toml=task_toml,
        )
        hooks = ModelHooks(architect_model, solver_model)

        # Build snapshot callback: captures container_id + snapshot_dir from closure.
        snap_cb = None
        if snapshot_dir and container_id:
            _base = os.path.join(snapshot_dir, task_name)
            snap_cb = lambda step: _docker_snapshot(container_id, os.path.join(_base, f"step_{step}"))  # noqa: E731

        kernel = AetherNextKernel(
            max_steps=max_steps,
            workbench_architect=workbench_architect_for(architect_model),
            snapshot_callback=snap_cb, snapshot_steps=snapshot_steps,
        )

        if trace_dir is not None:
            from ..tracing import RunTrace
            run_trace = RunTrace()
        kernel_timed_out = False
        kernel_timeout_detail = ""

        try:
            with _scoped_verifier_evidence_dir(task_name), _kernel_wall_timeout(run_timeout_s):
                result = kernel.run(envmap, executor, hooks, trace=run_trace)
        except KernelRunTimeout as exc:
            # The agent phase has TERMINATED (by wall clock).  The official
            # grader runs after termination regardless of the reason -- a
            # timeout must never discard real completed state as reward 0.0
            # without scoring it (observed live: headless-terminal and
            # kv-store-grpc timed out with gate-ready workspaces and were
            # recorded as failures without ever being graded).
            timeout_steps = len(run_trace.steps) if run_trace is not None and hasattr(run_trace, "steps") else 0
            result = KernelResult(
                status="timeout",
                step=timeout_steps,
                reconfigurations=0,
                blockers=(f"kernel_timeout_after_{run_timeout_s}s",),
                receipts=(),
            )
            kernel_timed_out = True
            kernel_timeout_detail = str(exc)

        # Capture final workspace snapshot if requested.
        if snapshot_dir and container_id:
            _docker_snapshot(container_id, os.path.join(snapshot_dir, task_name, "final"))

        # -- 4. Score with official grader ------------------------------------
        # Ensure the verifier output directory exists inside the container.
        # Introduce official task/test surfaces only after the agent has
        # reached a terminal state.  The solver container is started without
        # /task or /tests mounts, so pre-terminal code cannot inspect grader
        # or solution material.
        subprocess.run(
            ["docker", "exec", container_id, "bash", "-lc", "rm -rf /task /tests && mkdir -p /task /tests"],
            capture_output=True, text=True, errors="replace", timeout=30,
        )
        subprocess.run(
            ["docker", "cp", f"{task_dir_abs}/.", f"{container_id}:/task"],
            capture_output=True, text=True, errors="replace", timeout=60,
        )
        if os.path.isdir(tests_mount):
            subprocess.run(
                ["docker", "cp", f"{tests_mount}/.", f"{container_id}:/tests"],
                capture_output=True, text=True, errors="replace", timeout=60,
            )

        grader_cmd = detect_grader_command(task_dir_abs)
        grader_error = None
        try:
            grader_proc = subprocess.run(
                ["docker", "exec", "-w", "/app", container_id, "bash", "-lc", grader_cmd],
                capture_output=True, text=True, errors="replace", timeout=run_timeout_s,
            )
            grader_exit = grader_proc.returncode
            grader_stdout = grader_proc.stdout[-4000:]
            grader_stderr = grader_proc.stderr[-4000:]
        except subprocess.TimeoutExpired as exc:
            grader_exit = -1
            grader_stdout = str(exc.stdout or "")[-4000:]
            grader_stderr = str(exc.stderr or "")[-4000:]
            grader_error = f"grader_timeout_after_{run_timeout_s}s"

        reward, grader_error, reward_source = _resolve_grader_reward(
            container_id=container_id,
            task_dir=task_dir_abs,
            grader_exit=grader_exit,
            grader_error=grader_error,
        )

        # Capture CTRF detail if present (optional).
        grader_detail: dict[str, Any] | None = None
        try:
            cp = subprocess.run(
                ["docker", "exec", container_id, "cat", "/logs/verifier/ctrf.json"],
                capture_output=True, text=True, errors="replace", timeout=10)
            if cp.returncode == 0 and cp.stdout.strip():
                ctrf = _json.loads(cp.stdout)
                tests = ctrf.get("results", {}).get("tests", [])
                p = [t.get("name", "?") for t in tests if t.get("status") == "passed"]
                f = [t.get("name", "?") for t in tests if t.get("status") == "failed"]
                grader_detail = {"passed_count": len(p), "failed_count": len(f),
                                 "passed_names": p[:20], "failed_names": f[:20]}
        except Exception:
            pass  # CTRF is optional

        # -- 5. Classify -------------------------------------------------------
        classifier = HarnessLimiterClassifier()
        classification = classifier.classify(result)
        (
            record_status,
            classifier_label,
            classifier_confidence,
            classifier_detail,
        ) = _classification_fields_for_record(
            classification=classification,
            result=result,
            reward=reward,
            grader_error=grader_error,
            kernel_timed_out=kernel_timed_out,
        )
        verifier_verdict = _latest_model_verifier_verdict(result)

        record: dict[str, Any] = {
            "task": task_name,
            "image": image,
            "architect_mode": architect_mode,
            "reward": reward,
            "status": record_status,
            "kernel_status": result.status,
            "model_verifier_final_verdict": verifier_verdict,
            "step": result.step,
            "reconfigurations": result.reconfigurations,
            "architect_defect": result.architect_defect,
            "architect_defect_reasons": list(result.architect_defect_reasons),
            "classifier_label": classifier_label,
            "classifier_confidence": classifier_confidence,
            "classifier_detail": classifier_detail,
            "model_parse_errors": list(hooks.last_parse_errors),
            "grader_exit": grader_exit,
            "reward_source": reward_source,
            "grader_stdout_tail": grader_stdout, "grader_stderr_tail": grader_stderr,
            "receipt_summary": _receipt_summary(result),
            "run_provenance": dict(run_provenance or {}),
            "run_timeout_s_effective": run_timeout_s,
            "run_timeout_policy": run_timeout_policy,
            **reconcile_grader_alignment(
                reward=reward,
                grader_error=grader_error,
                kernel_status=result.status,
                verifier_verdict=verifier_verdict,
            ),
        }
        if grader_error is not None:
            record["grader_error"] = grader_error
        if grader_detail is not None:
            record["grader_detail"] = grader_detail
        if kernel_timed_out:
            record["error"] = f"kernel_timeout_after_{run_timeout_s}s"
            record["error_detail"] = kernel_timeout_detail
            record["graded_after_timeout"] = True

        # Write trace file when trace capture is enabled.
        if trace_dir is not None and run_trace is not None:
            _write_trace_file_to_record(
                record,
                trace_dir,
                task_name,
                image,
                reward=reward,
                status=result.status,
                run_trace=run_trace,
            )

        return record

    except Exception as exc:
        record = _error_record(task_name, image, type(exc).__name__, str(exc), architect_mode=architect_mode)
        if trace_dir is not None and run_trace is not None:
            _write_trace_file_to_record(
                record,
                trace_dir,
                task_name,
                image,
                reward=0.0,
                status="error",
                run_trace=run_trace,
            )
        return record
    finally:
        # -- 6. Teardown -------------------------------------------------------
        if container_id:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True, text=True, errors="replace", timeout=30,
            )
        if workspace_dir and os.path.isdir(workspace_dir):
            shutil.rmtree(workspace_dir, ignore_errors=True)


def _error_record(
    task: str,
    image: str,
    error_kind: str,
    detail: str,
    *,
    architect_mode: str = "workbench",
) -> dict[str, Any]:
    """Build a minimal error record that keeps the pilot loop going."""
    return {
        "task": task,
        "image": image,
        "architect_mode": architect_mode,
        "reward": 0.0,
        "status": "error",
        "step": 0,
        "reconfigurations": 0,
        "classifier_label": "environment_runner_failure",
        "classifier_confidence": "high",
        "classifier_detail": f"{error_kind}: {detail[:2000]}",
        "model_parse_errors": [],
        "grader_exit": -1,
        "grader_stdout_tail": "",
        "grader_stderr_tail": "",
        "receipt_summary": [],
        "error": error_kind,
        "error_detail": detail[:4000],
        **reconcile_grader_alignment(reward=None, grader_error=error_kind, kernel_status="error"),
    }


def _timeout_record(
    task: str,
    image: str,
    error_kind: str,
    detail: str,
    *,
    trace_dir: str | None = None,
) -> dict[str, Any]:
    """Build a timeout record that distinguishes kernel budget exhaustion."""
    trace_path = None
    if trace_dir is not None:
        trace_path = str(Path(trace_dir) / f"{task}.trace.json")
    record = {
        "task": task,
        "image": image,
        "reward": 0.0,
        "status": "timeout",
        "kernel_status": "timeout",
        "step": 0,
        "reconfigurations": 0,
        "classifier_label": "timeout_resource_failure",
        "classifier_confidence": "high",
        "classifier_detail": f"{error_kind}: {detail[:2000]}",
        "model_parse_errors": [],
        "grader_exit": -1,
        "grader_stdout_tail": "",
        "grader_stderr_tail": "",
        "receipt_summary": [],
        "error": error_kind,
        "error_detail": detail[:4000],
        **reconcile_grader_alignment(reward=None, grader_error=error_kind, kernel_status="timeout"),
    }
    if trace_path is not None:
        record["trace_path"] = trace_path
    return record


def _write_trace_file(
    trace_dir: str,
    task: str,
    image: str,
    *,
    reward: float,
    status: str,
    run_trace: Any,
) -> None:
    Path(trace_dir).mkdir(parents=True, exist_ok=True)
    trace_path = Path(_trace_path_for(trace_dir, task))
    trace_path.write_text(
        _json.dumps(run_trace.to_dict(task=task, image=image, reward=reward, status=status), indent=2),
        encoding="utf-8",
    )


def _trace_path_for(trace_dir: str, task: str) -> str:
    return str(Path(trace_dir) / f"{task}.trace.json")


def _write_trace_file_to_record(
    record: dict[str, Any],
    trace_dir: str,
    task: str,
    image: str,
    *,
    reward: float,
    status: str,
    run_trace: Any,
) -> None:
    record["trace_path"] = _trace_path_for(trace_dir, task)
    try:
        _write_trace_file(
            trace_dir,
            task,
            image,
            reward=reward,
            status=status,
            run_trace=run_trace,
        )
    except Exception as exc:
        record["trace_write_error"] = "failed_to_write_trace_file"
        record["trace_write_error_type"] = type(exc).__name__
        record["trace_write_error_detail"] = str(exc)[:2000]


_VERIFIER_EVIDENCE_DIR_ENV = "AETHER_VERIFIER_EVIDENCE_DIR"


@contextmanager
def _scoped_verifier_evidence_dir(task_name: str) -> Iterator[None]:
    """Namespace verifier evidence output by task for this process's duration.

    A pilot run drives several tasks sequentially in one process, each
    restarting the kernel's step counter at 0. If the operator sets
    ``AETHER_VERIFIER_EVIDENCE_DIR`` once for the whole run (the documented
    usage), later tasks silently overwrite earlier tasks' ``step_NNNN``
    verifier evidence directories. Scope it here so evidence never collides
    regardless of how the caller launched the run.
    """
    previous = os.environ.get(_VERIFIER_EVIDENCE_DIR_ENV)
    if previous:
        os.environ[_VERIFIER_EVIDENCE_DIR_ENV] = str(Path(previous) / task_name)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(_VERIFIER_EVIDENCE_DIR_ENV, None)
        else:
            os.environ[_VERIFIER_EVIDENCE_DIR_ENV] = previous


@contextmanager
def _kernel_wall_timeout(timeout_s: float) -> Iterator[None]:
    """Bound the model/kernel loop itself, not just docker exec calls."""
    if timeout_s <= 0:
        yield
        return

    def _raise_timeout(signum: int, frame: Any) -> None:
        raise KernelRunTimeout(f"kernel loop exceeded {timeout_s:g}s")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])

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
from typing import Any, Callable, Iterator

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
from ..result_metrics import run_metrics_for_row
from ..runtime_ir import EnvMap, normalize_relpath
from ..task_metadata_loader import load_task_instruction, load_task_metadata
from .docker_exec_executor import DockerExecExecutor
from .docker_helpers import detect_grader_command, ensure_image_available, seed_workspace_from_image

# Prevent git "dubious ownership" on bind-mounted workspaces (uid mismatch).
_GIT_SAFE_DIR_CMD = "git config --global --add safe.directory '*' || true"
_log = logging.getLogger(__name__)


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


def _expected_steps_from(result: KernelResult) -> int:
    for receipt in result.receipts:
        if receipt.kind == "config_realization":
            payload = (receipt.payload or {}).get("config_realization", {})
            if isinstance(payload, dict):
                try:
                    return int(payload.get("expected_steps", 0) or 0)
                except (TypeError, ValueError):
                    return 0
    return 0


def _step_efficiency(result: KernelResult) -> float | None:
    """Advisory metric: actual steps / architect expectation (>1 = over budget)."""
    expected = _expected_steps_from(result)
    if expected <= 0:
        return None
    return round(result.step / expected, 2)


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
    vision_model: Any | None = None,
    max_steps: int = 30,
    run_timeout_s: int = 1800,
    trace_dir: str | None = None,
    architect_mode: str = "workbench",
    snapshot_dir: str | None = None,
    snapshot_steps: tuple[int, ...] = (),
    run_provenance: dict[str, Any] | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
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
        _progress(progress_callback, task_name, "workspace_create", "creating temporary workspace")
        workspace_dir = tempfile.mkdtemp(prefix=f"tbench_{task_name}_")
        workspace_path = Path(workspace_dir)

        _progress(progress_callback, task_name, "image_available", f"ensuring docker image {image}")
        image_error = ensure_image_available(image, pull_timeout_s=max(300, run_timeout_s))
        if image_error is not None:
            return _error_record(task_name, image, "image_pull_failed", image_error, architect_mode=architect_mode)

        _progress(progress_callback, task_name, "workspace_seed", "copying task workspace from image")
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

        _progress(progress_callback, task_name, "container_start", "starting solver container")
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
        _progress(progress_callback, task_name, "envmap_build", "building task environment map")
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
        _progress(progress_callback, task_name, "environment_probe", "probing task runtime capabilities")
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
        hooks = ModelHooks(architect_model, solver_model, vision_model=vision_model)

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
            _progress(progress_callback, task_name, "kernel_run", f"running agent kernel with timeout {run_timeout_s}s")
            with _scoped_verifier_evidence_dir(task_name, trace_dir), _kernel_wall_timeout(run_timeout_s):
                result = kernel.run(envmap, executor, hooks, trace=run_trace, run_timeout_s=run_timeout_s)
            _progress(progress_callback, task_name, "kernel_done", f"kernel status={result.status} step={result.step}")
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
            _progress(progress_callback, task_name, "kernel_timeout", kernel_timeout_detail)

        # Capture final workspace snapshot if requested.
        if snapshot_dir and container_id:
            _progress(progress_callback, task_name, "snapshot_final", "copying final workspace snapshot")
            _docker_snapshot(container_id, os.path.join(snapshot_dir, task_name, "final"))

        # -- 4. Score with official grader ------------------------------------
        # Ensure the verifier output directory exists inside the container.
        # Introduce official task/test surfaces only after the agent has
        # reached a terminal state.  The solver container is started without
        # /task or /tests mounts, so pre-terminal code cannot inspect grader
        # or solution material.
        _progress(progress_callback, task_name, "grader_prepare", "mounting official task/test surfaces after agent termination")
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
            _progress(progress_callback, task_name, "grader_run", grader_cmd)
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
        _progress(progress_callback, task_name, "grader_done", f"reward={reward} source={reward_source} error={grader_error}")

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
        run_metrics = run_metrics_for_row(result, hooks.last_parse_errors)

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
            "model_parse_errors": run_metrics.pop("model_parse_errors"),
            "run_metrics": run_metrics,
            "grader_exit": grader_exit,
            "reward_source": reward_source,
            "grader_stdout_tail": grader_stdout, "grader_stderr_tail": grader_stderr,
            "receipt_summary": _receipt_summary(result),
            "run_provenance": dict(run_provenance or {}),
            "expected_steps": _expected_steps_from(result),
            "step_efficiency": _step_efficiency(result),
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


def _progress(
    callback: Callable[[str, str], None] | None,
    task_name: str,
    stage: str,
    detail: str,
) -> None:
    message = f"[{task_name}] {stage}: {detail}"
    print(message, flush=True)
    if callback is not None:
        try:
            callback(stage, detail)
        except Exception:
            _log.debug("progress callback failed", exc_info=True)


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
def _scoped_verifier_evidence_dir(task_name: str, trace_dir: str | None = None) -> Iterator[None]:
    """Namespace verifier evidence output by task for this process's duration.

    A pilot run drives several tasks sequentially in one process, each
    restarting the kernel's step counter at 0. If the operator sets
    ``AETHER_VERIFIER_EVIDENCE_DIR`` once for the whole run (the documented
    usage), later tasks silently overwrite earlier tasks' ``step_NNNN``
    verifier evidence directories. Scope it here so evidence never collides
    regardless of how the caller launched the run.

    When the operator did NOT set the env var but the run is traced, default
    the evidence root under the trace dir: two live batches already lost every
    verifier packet/raw-output bundle to a forgotten export, and per-round
    verifier evidence is not optional provenance.
    """
    previous = os.environ.get(_VERIFIER_EVIDENCE_DIR_ENV)
    if previous:
        os.environ[_VERIFIER_EVIDENCE_DIR_ENV] = str(Path(previous) / task_name)
    elif trace_dir:
        os.environ[_VERIFIER_EVIDENCE_DIR_ENV] = str(Path(trace_dir) / "verifier_evidence" / task_name)
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

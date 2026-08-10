"""Docker-backed runner for Terminal-Bench tasks against the Aether-Next kernel."""
from __future__ import annotations

import json as _json
import os
from decimal import Decimal, InvalidOperation
import re
import shutil
import signal
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
import logging
from typing import Any, Callable, Iterator, Mapping

from ..classifier import HarnessLimiterClassifier, reconcile_grader_alignment
from ..envmap_builder import build_envmap_from_task
from ..evidence_finalization import (
    copy_snapshot, directory_manifest, executing_source_identity,
    finalize_evidence_directory, sha256_file, write_manifest,
)
from ..environment_probe import probe_environment
from ..execution import (
    ArtifactInspection,
    CommandResult,
    ProcessHandle,
    ProbeResult,
)
from ..kernel import AetherNextKernel, KernelResult
from ..model_hooks import ModelCallable, ModelHooks
from ..model_interface import (
    compact_model_interface_manifests,
    write_model_interface_captures,
)
from ..network_policy import LOOPBACK_ONLY, resolve_network_policy
from ..persistent_reanchor import CURRENT_FULL, REFINED_M, SUPPORTED_REANCHOR_MODES
from ..model_request_contract import (
    ExpectedModelRequest,
    ModelRequestRealizationError,
    preflight_model_requests,
)
from ..real_executor import (
    StreamSpooler,
    SubprocessExecutor,
    _decode_partial,
    _resolve_safe,
    _snapshot_mtimes,
    _SKIP_DIRS,
    _MAX_SCAN_ENTRIES,
)
from ..run_adapter import _build_runtime_identity, architect_v3_for, ensure_certified_architect_mode
from ..result_metrics import run_metrics_for_row
from ..runtime_ir import EnvMap, normalize_relpath
from ..task_metadata_loader import load_task_instruction, load_task_metadata
from ..task_contract import TaskClause, TaskContract
from ..world import WorldState
from ..workspace_state import (
    capture_workspace_state,
    create_immutable_workspace_snapshot,
)
from ..verify_inspection_requests import _verifier_max_output_tokens
from .docker_exec_executor import DockerExecExecutor
from .grader_results import build_grader_detail
from .result_admission import evaluate_run_admission
from .docker_helpers import detect_grader_command, ensure_image_available, seed_workspace_from_image

# Prevent git "dubious ownership" on bind-mounted workspaces (uid mismatch).
_GIT_SAFE_DIR_CMD = "git config --global --add safe.directory '*' || true"
_GRADER_PREPARE_DIRS_CMD = "rm -rf /task /tests && mkdir -p /task /tests /logs/verifier"
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


_CONTAINER_ARTIFACT_NOT_FOUND_MARKERS = (
    "No such file or directory", "Could not find", "not found",
)


def _read_container_text_artifact(
    container_id: str,
    path: str,
    *,
    timeout_s: int = 30,
) -> tuple[str | None, str | None]:
    """Read a completed grader artifact without spawning a container process.

    Graders can leave Chromium, compilers, or other process-heavy state behind.
    A post-grader ``docker exec cat`` therefore makes reward custody depend on
    the container still being able to spawn one more process. ``docker cp``
    reads the stopped/running container filesystem through the Docker daemon
    instead, which is the correct boundary for immutable grader artifacts.

    Returns ``(text, None)`` on success, ``(None, "missing")`` only when
    Docker proves the path is absent, and a distinct transport/read error for
    every other failure.
    """
    with tempfile.TemporaryDirectory(prefix="aether_grader_artifact_") as tmp:
        destination = Path(tmp) / "artifact.txt"
        try:
            proc = subprocess.run(
                ["docker", "cp", f"{container_id}:{path}", str(destination)],
                capture_output=True, text=True, errors="replace", timeout=timeout_s,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"docker_cp_{type(exc).__name__}: {exc}"
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            if any(marker.lower() in detail.lower() for marker in _CONTAINER_ARTIFACT_NOT_FOUND_MARKERS):
                return None, "missing"
            return None, f"docker_cp_exit_{proc.returncode}: {detail[:2000]}"
        try:
            return destination.read_text(encoding="utf-8", errors="replace"), None
        except OSError as exc:
            return None, f"host_artifact_read_{type(exc).__name__}: {exc}"


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

    reward_text, reward_read_error = _read_container_text_artifact(
        container_id, "/logs/verifier/reward.txt", timeout_s=30,
    )

    if reward_text is not None and reward_text.strip():
        raw_reward = reward_text.strip()
        try:
            parsed_reward = Decimal(raw_reward)
        except InvalidOperation:
            parsed_reward = None
        if (
            parsed_reward is None
            or not parsed_reward.is_finite()
            or parsed_reward not in {Decimal("0"), Decimal("1")}
        ):
            preview = raw_reward[:128].replace("\n", "\\n")
            return (
                0.0,
                f"reward.txt invalid value: {preview!r}",
                "reward_txt_invalid",
            )
        return float(parsed_reward), None, "reward_txt"

    if (Path(task_dir) / "run-tests.sh").exists():
        return (1.0 if grader_exit == 0 else 0.0), None, "official_run_tests_exit_code"

    if reward_read_error not in {None, "missing"}:
        return (
            0.0,
            f"reward.txt artifact read failed: {reward_read_error}",
            "reward_txt_error",
        )
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

def _build_task_container_command(
    *,
    image: str,
    workspace_dir: str,
    network_policy: Any,
) -> list[str]:
    """Build the exact certified task-container launch command."""
    return [
        "docker", "run", "-d", "--init",
        *network_policy.docker_args,
        "-v", f"{workspace_dir}:/app",
        "-w", "/app",
        image,
        "sleep", "infinity",
    ]


def _checked_process(
    args: list[str],
    *,
    label: str,
    timeout: int,
) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
    """Run one infrastructure command and preserve an exact failure."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{label}: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return proc, f"{label}: exit={proc.returncode}: {detail[:2000]}"
    return proc, None


def _evidence_directory(task_name: str, trace_dir: str | None) -> Path:
    if trace_dir:
        root = Path(trace_dir) / "run_evidence" / task_name
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(tempfile.mkdtemp(prefix=f"aether_run_evidence_{task_name}_"))



def _normalise_docker_sha256(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith("sha256:"):
        raw = raw[7:]
    return raw if re.fullmatch(r"[0-9a-f]{64}", raw) else ""


def _docker_image_identity(image: str) -> str:
    proc, error = _checked_process(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        label="docker_image_identity",
        timeout=30,
    )
    if error or proc is None:
        return ""
    return _normalise_docker_sha256(proc.stdout)


def _container_image_identity(container_id: str) -> str:
    proc, error = _checked_process(
        ["docker", "inspect", "--format", "{{.Image}}", container_id],
        label="container_image_identity",
        timeout=30,
    )
    if error or proc is None:
        return ""
    return _normalise_docker_sha256(proc.stdout)


def _prepare_grader_network(container_id: str, network_policy: Any) -> dict[str, Any]:
    """Grant grader-only bridge access after the agent loop has terminated.

    Certified agent isolation remains unchanged: loopback-only task containers
    start with Docker network ``none``. Some official graders install their own
    test dependencies, so after the final agent-visible state has been sealed we
    may attach the already-running container to Docker's default bridge solely
    for grading. No model turn occurs after this transition.
    """
    scope = str(getattr(network_policy, "scope", "") or "")
    transition: dict[str, Any] = {
        "agent_network_scope": scope,
        "grader_network": "existing_external" if scope != LOOPBACK_ONLY else "docker_bridge",
        "transition_required": scope == LOOPBACK_ONLY,
        "transition_succeeded": True,
        "error": "",
    }
    if scope != LOOPBACK_ONLY:
        return transition
    disconnect, disconnect_error = _checked_process(
        ["docker", "network", "disconnect", "none", container_id],
        label="grader_network_disconnect_none",
        timeout=30,
    )
    transition["disconnect_exit"] = None if disconnect is None else disconnect.returncode
    transition["disconnect_stdout_tail"] = "" if disconnect is None else disconnect.stdout[-1000:]
    transition["disconnect_stderr_tail"] = "" if disconnect is None else disconnect.stderr[-1000:]
    if disconnect_error:
        transition["transition_succeeded"] = False
        transition["error"] = disconnect_error
        return transition
    proc, error = _checked_process(
        ["docker", "network", "connect", "bridge", container_id],
        label="grader_network_connect",
        timeout=30,
    )
    transition["connect_exit"] = None if proc is None else proc.returncode
    transition["connect_stdout_tail"] = "" if proc is None else proc.stdout[-1000:]
    transition["connect_stderr_tail"] = "" if proc is None else proc.stderr[-1000:]
    if error:
        transition["transition_succeeded"] = False
        transition["error"] = error
    return transition


def _probe_agent_hidden_surfaces(container_id: str) -> dict[str, Any]:
    paths = ("/tests", "/solution", "/solutions", "/task")
    command = 'for p in "$@"; do [ ! -e "$p" ] || printf "%s\n" "$p"; done'
    proc, error = _checked_process(
        ["docker", "exec", container_id, "sh", "-c", command, "hidden-surface", *paths],
        label="agent_hidden_surface_probe",
        timeout=30,
    )
    visible = [] if proc is None else [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return {
        "checked_paths": list(paths),
        "visible_paths": visible,
        "probe_error": error or "",
        "clean": error is None and not visible,
    }


def _remove_container_with_evidence(container_id: str) -> dict[str, Any]:
    remove_proc, remove_error = _checked_process(
        ["docker", "rm", "-f", container_id],
        label="container_remove",
        timeout=30,
    )
    try:
        inspect = subprocess.run(
            ["docker", "inspect", container_id],
            capture_output=True, text=True, errors="replace", timeout=15,
        )
        inspect_error = ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        inspect = None
        inspect_error = f"{type(exc).__name__}: {exc}"
    verified_absent = inspect is not None and inspect.returncode != 0
    return {
        "container_id": container_id,
        "remove_exit": None if remove_proc is None else remove_proc.returncode,
        "remove_stdout_tail": "" if remove_proc is None else remove_proc.stdout[-2000:],
        "remove_stderr_tail": "" if remove_proc is None else remove_proc.stderr[-2000:],
        "remove_error": remove_error or "",
        "inspect_exit": None if inspect is None else inspect.returncode,
        "inspect_stdout_tail": "" if inspect is None else inspect.stdout[-2000:],
        "inspect_stderr_tail": "" if inspect is None else inspect.stderr[-2000:],
        "inspect_error": inspect_error,
        "verified_absent": verified_absent,
    }


def _build_kernel_for_architect_mode(
    *,
    architect_mode: str,
    architect_model: ModelCallable,
    hooks: ModelHooks,
    max_steps: int,
    snapshot_callback: Callable[[int], None] | None,
    snapshot_steps: tuple[int, ...],
    runtime_identity: dict[str, Any] | None,
    solver_reanchor_mode: str = CURRENT_FULL,
) -> AetherNextKernel:
    """Build the exact certified kernel path selected by the public runner mode."""
    persistent_primary = architect_mode == "persistent_v0"
    return AetherNextKernel(
        max_steps=max_steps,
        architect_v3_architect=(
            None
            if persistent_primary
            else architect_v3_for(architect_model, hooks=hooks)
        ),
        persistent_primary=persistent_primary,
        runtime_identity=runtime_identity if persistent_primary else None,
        solver_reanchor_mode=solver_reanchor_mode,
        snapshot_callback=snapshot_callback,
        snapshot_steps=snapshot_steps,
        certified_production=True,
    )


def _provider_protocol_validity(
    *, record_error: str, classifier_label: str, model_parse_errors: list[Any],
) -> tuple[bool, bool]:
    provider_errors = {
        "multiple_distinct_assistant_outputs",
        "provider_output_incomplete",
        "provider_structured_output_invalid_json",
        "mixed_assistant_output_types",
    }
    # These codes originate at the Responses item/cardinality boundary rather
    # than from the model placing several future turns inside one assistant
    # message. They can arrive wrapped inside a solver_parse_error receipt, so
    # row admission must inspect the preserved parse evidence as well as the
    # terminal result.error field.
    provider_parse_error_codes = {
        "provider_persistent_v0_multiple_distinct_semantic_payloads",
        "multiple_distinct_assistant_outputs",
        "provider_no_assistant_message",
        "provider_mixed_message_and_tool_output",
        "provider_output_incomplete",
        "provider_empty_assistant_message",
        "provider_content_filter",
        "provider_refusal",
    }
    parse_error_text = "\n".join(
        _json.dumps(item, sort_keys=True, default=str)
        if isinstance(item, (dict, list, tuple))
        else str(item)
        for item in model_parse_errors
    )
    provider_parse_invalid = any(
        code in parse_error_text for code in provider_parse_error_codes
    )
    provider_valid = (
        record_error not in provider_errors
        and classifier_label not in {"provider_protocol_failure", "provider_failure"}
        and not provider_parse_invalid
    )
    protocol_valid = (
        not model_parse_errors
        and classifier_label != "solver_protocol_failure"
        and provider_valid
    )
    return provider_valid, protocol_valid


_SOURCE_40_RE = re.compile(r"^[0-9a-f]{40}$")
_SOURCE_64_RE = re.compile(r"^[0-9a-f]{64}$")
_CERTIFIED_SOURCE_HASH_FIELDS = (
    "current_runtime_manifest_sha256",
    "current_runtime_aggregate_sha256",
    "execution_body_manifest_sha256",
    "execution_body_aggregate_sha256",
    "source_manifest_aggregate_sha256",
)


def _resolve_certified_source_identity(
    observed: Mapping[str, Any],
    certified: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolve source custody without letting supplied metadata hide local Git truth."""
    observed_row = dict(observed)
    if certified is None:
        return observed_row
    row = dict(certified)
    commit = str(row.get("commit", "") or "").lower()
    tree = str(row.get("tree", "") or "").lower()
    if not _SOURCE_40_RE.fullmatch(commit) or not _SOURCE_40_RE.fullmatch(tree):
        raise ValueError("certified source commit/tree must be exact 40-hex identities")
    if row.get("clean") is not True:
        raise ValueError("certified source identity must assert clean=true")
    custody_mode = str(row.get("custody_mode", "") or "").strip()
    if not custody_mode or "manifest" not in custody_mode:
        raise ValueError("certified source identity requires explicit manifest custody mode")
    for key in _CERTIFIED_SOURCE_HASH_FIELDS:
        value = str(row.get(key, "") or "").lower()
        if not _SOURCE_64_RE.fullmatch(value):
            raise ValueError(f"certified source identity missing exact {key}")
    try:
        certified_file_count = int(row.get("source_manifest_file_count", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("certified source manifest file count invalid") from exc
    if certified_file_count <= 0:
        raise ValueError("certified source manifest file count must be positive")

    observed_manifest = observed_row.get("source_manifest")
    if not isinstance(observed_manifest, Mapping):
        raise ValueError("executing source manifest is unavailable")
    if (
        str(observed_manifest.get("aggregate_sha256", "") or "").lower()
        != str(row["source_manifest_aggregate_sha256"]).lower()
        or int(observed_manifest.get("file_count", -1) or -1) != certified_file_count
    ):
        raise ValueError("certified source manifest does not match executing aether bytes")

    if observed_row.get("git_available") is True:
        if observed_row.get("clean") is not True:
            raise ValueError("dirty local Git checkout cannot be overridden by certified source identity")
        if (
            str(observed_row.get("commit", "") or "").lower() != commit
            or str(observed_row.get("tree", "") or "").lower() != tree
        ):
            raise ValueError("certified source commit/tree does not match local Git truth")
        resolved = dict(observed_row)
        resolved.update({
            key: value for key, value in row.items()
            if key not in {"clean", "git_available", "git_top", "status", "source_manifest"}
        })
        resolved["clean"] = True
        resolved["identity_authority"] = "clean_git_plus_certified_manifest_binding"
        resolved["certified_source_identity"] = row
        return resolved

    resolved = dict(row)
    resolved.update({
        "git_available": False,
        "clean": True,
        "identity_authority": "certified_external_binding_after_manifest_match",
        "source_manifest": dict(observed_manifest),
        "observed_source_identity": observed_row,
    })
    if observed_row.get("git_error"):
        resolved["git_error"] = observed_row.get("git_error")
    return resolved


def run_tbench_task(
    *,
    task_dir: str,
    image: str,
    architect_model: ModelCallable,
    solver_model: ModelCallable,
    verifier_model: ModelCallable | None = None,
    architect_reviewer_model: ModelCallable | None = None,
    vision_model: Any | None = None,
    max_steps: int = 30,
    run_timeout_s: int = 1800,
    trace_dir: str | None = None,
    architect_mode: str = "architect_v3",
    snapshot_dir: str | None = None,
    snapshot_steps: tuple[int, ...] = (),
    run_provenance: dict[str, Any] | None = None,
    certified_source_identity: Mapping[str, Any] | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
    network_scope: str | None = None,
    solver_continuity_mode: str = "explicit",
    solver_reanchor_mode: str = CURRENT_FULL,
) -> dict[str, Any]:
    """Run one Terminal-Bench task end-to-end.  Never raises -- errors are
    captured into the record so that a pilot loop can continue.
    """
    task_name = Path(task_dir).name
    container_id: str | None = None
    workspace_dir: str | None = None
    initial_snapshot_dir: str | None = None
    initial_workspace_state: dict[str, Any] | None = None
    initial_workspace_manifest_path: str | None = None
    run_trace: Any = None
    hooks: ModelHooks | None = None
    executor: DockerExecExecutor | None = None
    run_evidence_dir: Path | None = None
    source_identity: dict[str, Any] = {}
    observed_source_identity: dict[str, Any] = {}
    evidence_paths: dict[str, Any] = {}
    task_package_sha256_start = ""
    task_package_sha256_grader = ""
    runtime_image_sha256_expected = ""
    runtime_image_sha256_container = ""
    hidden_surface_probe: dict[str, Any] = {"clean": False, "probe_error": "not_run"}
    container_teardown: dict[str, Any] = {"verified_absent": False}
    runtime_identity: dict[str, Any] | None = None

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
    if solver_reanchor_mode not in SUPPORTED_REANCHOR_MODES:
        return _error_record(
            task_name, image, "invalid_solver_reanchor_mode",
            f"unsupported PERSISTENT Solver re-anchor mode: {solver_reanchor_mode}",
            architect_mode=architect_mode,
        )
    if solver_reanchor_mode == REFINED_M and (
        architect_mode != "persistent_v0" or solver_continuity_mode != "previous_response_compaction"
    ):
        return _error_record(
            task_name, image, "invalid_solver_reanchor_route",
            "refined_m requires PERSISTENT V0 with previous_response_compaction",
            architect_mode=architect_mode,
        )
    if architect_reviewer_model is not None:
        return _error_record(
            task_name, image, "architect_v3_reviewer_forbidden",
            "Architect V3 certified production permits one Architect call and no reviewer",
            architect_mode=architect_mode,
        )
    if verifier_model is None:
        return _error_record(
            task_name, image, "verifier_model_required",
            "Architect V3 production requires a dedicated Verifier callable",
            architect_mode=architect_mode,
        )

    try:
        model_requests = [
            (solver_model, ExpectedModelRequest("solver", 16000)),
            (verifier_model, ExpectedModelRequest("verifier", _verifier_max_output_tokens())),
        ]
        if architect_mode != "persistent_v0":
            model_requests.insert(
                0, (architect_model, ExpectedModelRequest("architect", 5000))
            )
        model_request_preflight = preflight_model_requests(model_requests)
    except ModelRequestRealizationError as exc:
        return _error_record(
            task_name, image, exc.code, exc.detail,
            architect_mode=architect_mode,
        )

    task_toml = _load_task_toml(task_dir)
    try:
        network_policy = resolve_network_policy(task_toml, explicit_scope=network_scope)
    except ValueError as exc:
        return _error_record(task_name, image, "invalid_network_scope", str(exc), architect_mode=architect_mode)
    run_timeout_s, run_timeout_policy = _effective_run_timeout_s(run_timeout_s, task_toml)

    try:  # outer try: catch ALL exceptions so the pilot never gets a raise
        run_evidence_dir = _evidence_directory(task_name, trace_dir)
        observed_source_identity = executing_source_identity(Path(__file__).resolve().parents[2])
        source_identity = _resolve_certified_source_identity(
            observed_source_identity, certified_source_identity
        )
        observed_source_identity_path = run_evidence_dir / "observed_source_identity.json"
        observed_source_identity_path.write_text(
            _json.dumps(observed_source_identity, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        evidence_paths["observed_source_identity"] = str(observed_source_identity_path)
        source_identity_path = run_evidence_dir / "executing_source_identity.json"
        source_identity_path.write_text(
            _json.dumps(source_identity, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        evidence_paths["executing_source_identity"] = str(source_identity_path)
        task_package_manifest_path = run_evidence_dir / "task_package.start.manifest.json"
        task_package_manifest = write_manifest(task_dir, task_package_manifest_path)
        task_package_sha256_start = str(task_package_manifest["aggregate_sha256"])
        evidence_paths["task_package_start_manifest"] = str(task_package_manifest_path)
        evidence_paths["task_package_sha256_start"] = task_package_sha256_start
        # -- 1. Temp workspace + seed ----------------------------------------
        _progress(progress_callback, task_name, "workspace_create", "creating temporary workspace")
        workspace_dir = tempfile.mkdtemp(prefix=f"tbench_{task_name}_")
        workspace_path = Path(workspace_dir)

        _progress(progress_callback, task_name, "image_available", f"ensuring docker image {image}")
        image_error = ensure_image_available(image, pull_timeout_s=max(300, run_timeout_s))
        if image_error is not None:
            return _error_record(task_name, image, "image_pull_failed", image_error, architect_mode=architect_mode)
        runtime_image_sha256_expected = _docker_image_identity(image)
        evidence_paths["runtime_image_sha256_expected"] = runtime_image_sha256_expected

        _progress(progress_callback, task_name, "workspace_seed", "copying task workspace from image")
        seed_error = seed_workspace_from_image(
            image,
            workspace_path,
            create_timeout_s=max(300, run_timeout_s),
            copy_timeout_s=max(300, run_timeout_s),
        )
        if seed_error is not None:
            return _error_record(task_name, image, "workspace_seed_failed", seed_error, architect_mode=architect_mode)

        # Capture pristine grader-visible task state before any model or
        # container command. The immutable copy lives outside the mutable bind
        # mount and is removed only after result evidence has been written.
        pristine_state = capture_workspace_state(workspace_path)
        initial_snapshot_dir = tempfile.mkdtemp(prefix=f"tbench_initial_{task_name}_")
        shutil.rmtree(initial_snapshot_dir)
        create_immutable_workspace_snapshot(workspace_path, initial_snapshot_dir)
        initial_workspace_state = pristine_state.to_dict()
        assert run_evidence_dir is not None
        initial_manifest = copy_snapshot(
            initial_snapshot_dir,
            run_evidence_dir / "initial_workspace",
        )
        initial_workspace_manifest_path = str(
            run_evidence_dir / "initial_workspace.manifest.json"
        )
        evidence_paths["initial_workspace"] = str(run_evidence_dir / "initial_workspace")
        evidence_paths["initial_workspace_manifest"] = initial_workspace_manifest_path
        evidence_paths["initial_workspace_aggregate_sha256"] = initial_manifest["aggregate_sha256"]
        if trace_dir is not None:
            manifest_dir = Path(trace_dir) / "initial_workspace"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = manifest_dir / f"{task_name}.json"
            manifest_path.write_text(
                _json.dumps(initial_workspace_state, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            evidence_paths["initial_workspace_state_manifest"] = str(manifest_path)

        # -- 2. Start long-lived container ------------------------------------
        task_dir_abs = str(Path(task_dir).resolve())
        tests_mount = os.path.join(task_dir_abs, "tests")

        _progress(progress_callback, task_name, "container_start", "starting solver container")
        docker_run_cmd = _build_task_container_command(
            image=image,
            workspace_dir=workspace_dir,
            network_policy=network_policy,
        )
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
        runtime_image_sha256_container = _container_image_identity(container_id)
        hidden_surface_probe = _probe_agent_hidden_surfaces(container_id)
        evidence_paths["runtime_image_sha256_container"] = runtime_image_sha256_container
        evidence_paths["agent_hidden_surface_probe"] = hidden_surface_probe

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
            network_scope=network_policy.scope,
            task_metadata={"network_policy": network_policy.as_dict()},
            task_toml=task_toml,
        )

        executor = DockerExecExecutor(
            container_id,
            workspace_dir,
            default_timeout_s=min(run_timeout_s, 300),
            container_workdir="/app",
            initial_snapshot_host_root=initial_snapshot_dir,
        )
        # Probe a stable generic command/package inventory.  Task semantics do
        # not select or prioritise tools in trusted code.
        extra_command_names: tuple[str, ...] = ()
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
            network_scope=network_policy.scope,
            task_metadata={"environment_probe": env_probe, "network_policy": network_policy.as_dict()},
            task_toml=task_toml,
        )
        persistent_primary = architect_mode == "persistent_v0"
        runtime_identity = None
        if persistent_primary:
            supplied_identity = {
                "task_id": task_name,
                "runtime_path": "persistent_primary",
                "source_commit": str(source_identity.get("commit", "") or ""),
                "source_tree": str(source_identity.get("tree", "") or ""),
                "source_clean": source_identity.get("clean") is True,
            }
            provenance = dict(run_provenance or {})
            for key in ("run_id", "primary_agent_id", "runtime_manifest_sha256"):
                value = provenance.get(key)
                if value:
                    supplied_identity[key] = value
            runtime_identity = _build_runtime_identity(
                task_dir=task_dir_abs,
                instruction_text=instruction_text,
                workspace_root="/app",
                environment_id=envmap.digest(),
                max_steps=max_steps,
                supplied=supplied_identity,
            )
        hooks = ModelHooks(
            architect_model,
            solver_model,
            verifier_model=verifier_model,
            architect_reviewer_model=None,
            vision_model=vision_model,
            run_id=(
                str(runtime_identity["run_id"])
                if runtime_identity is not None else None
            ),
            task_id=task_name,
        )

        # Build snapshot callback: captures container_id + snapshot_dir from closure.
        snap_cb = None
        if snapshot_dir and container_id:
            _base = os.path.join(snapshot_dir, task_name)
            snap_cb = lambda step: _docker_snapshot(container_id, os.path.join(_base, f"step_{step}"))  # noqa: E731

        kernel = _build_kernel_for_architect_mode(
            architect_mode=architect_mode,
            architect_model=architect_model,
            hooks=hooks,
            max_steps=max_steps,
            snapshot_callback=snap_cb,
            snapshot_steps=snapshot_steps,
            runtime_identity=runtime_identity,
            solver_reanchor_mode=solver_reanchor_mode,
        )
        world_state = WorldState(
            task_contract=TaskContract.create(
                instruction_text,
                (TaskClause("task:prompt", instruction_text),),
            ),
            env_facts={
                "workspace_root": "/app",
                "network_scope": envmap.network_scope,
                "visible_file_count": len(envmap.visible_files),
                "visible_dir_count": len(envmap.visible_dirs),
                "container_id": container_id,
            },
        )

        if trace_dir is not None:
            from ..tracing import RunTrace
            run_trace = RunTrace()
        kernel_timed_out = False
        kernel_timeout_detail = ""

        try:
            _progress(progress_callback, task_name, "kernel_run", f"running agent kernel with timeout {run_timeout_s}s")
            with _scoped_verifier_evidence_dir(task_name, trace_dir), _kernel_wall_timeout(run_timeout_s):
                result = kernel.run(
                    envmap, executor, hooks, world_state=world_state,
                    trace=run_trace, run_timeout_s=run_timeout_s,
                )
            _progress(progress_callback, task_name, "kernel_done", f"kernel status={result.status} step={result.step}")
        except KernelRunTimeout as exc:
            # The agent phase has TERMINATED (by wall clock).  The official
            # grader runs after termination regardless of the reason -- a
            # timeout must never discard real completed state as reward 0.0
            # without scoring it (observed live: terminal-emulator-check and
            # rpc-key-value timed out with gate-ready workspaces and were
            # recorded as failures without ever being graded).
            result = kernel.interrupted_result(
                status="timeout",
                blockers=(f"kernel_timeout_after_{run_timeout_s}s",),
            )
            kernel_timed_out = True
            kernel_timeout_detail = str(exc)
            _progress(progress_callback, task_name, "kernel_timeout", kernel_timeout_detail)

        # Capture final workspace snapshot if requested.
        if snapshot_dir and container_id:
            _progress(progress_callback, task_name, "snapshot_final", "copying final workspace snapshot")
            _docker_snapshot(container_id, os.path.join(snapshot_dir, task_name, "final"))

        # Preserve the exact agent-visible terminal state before official
        # surfaces or grader code can mutate /app.
        assert run_evidence_dir is not None
        agent_final_manifest = copy_snapshot(
            workspace_path,
            run_evidence_dir / "agent_final_workspace",
        )
        evidence_paths["agent_final_workspace"] = str(run_evidence_dir / "agent_final_workspace")
        evidence_paths["agent_final_workspace_manifest"] = str(
            run_evidence_dir / "agent_final_workspace.manifest.json"
        )
        evidence_paths["agent_final_workspace_aggregate_sha256"] = agent_final_manifest["aggregate_sha256"]
        if executor is not None:
            spool_manifest = executor.export_spools(str(run_evidence_dir / "command_spools"))
            evidence_paths["command_spools"] = spool_manifest
            terminal_manifest = spool_manifest.get("terminal_transcripts", {})
            if isinstance(terminal_manifest, dict) and terminal_manifest.get("manifest_path"):
                evidence_paths["terminal_transcripts"] = terminal_manifest

        # -- 4. Score with official grader ------------------------------------
        # Ensure the verifier output directory exists inside the container.
        # Introduce official task/test surfaces only after the agent has
        # reached a terminal state.  The solver container is started without
        # /task or /tests mounts, so pre-terminal code cannot inspect grader
        # or solution material.
        _progress(progress_callback, task_name, "grader_prepare", "mounting official task/test surfaces after agent termination")
        grader_network_transition = _prepare_grader_network(container_id, network_policy)
        evidence_paths["grader_network_transition"] = grader_network_transition
        task_package_grader_manifest_path = run_evidence_dir / "task_package.grader.manifest.json"
        task_package_grader_manifest = directory_manifest(task_dir_abs)
        task_package_grader_manifest_path.write_text(
            _json.dumps(task_package_grader_manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        task_package_sha256_grader = str(task_package_grader_manifest["aggregate_sha256"])
        evidence_paths["task_package_grader_manifest"] = str(task_package_grader_manifest_path)
        evidence_paths["task_package_sha256_grader"] = task_package_sha256_grader
        surface_errors: list[str] = []
        if not bool(grader_network_transition.get("transition_succeeded", False)):
            surface_errors.append(str(grader_network_transition.get("error", "grader network transition failed")))
        _proc, error = _checked_process(
            ["docker", "exec", container_id, "bash", "-lc", _GRADER_PREPARE_DIRS_CMD],
            label="grader_prepare_directories",
            timeout=30,
        )
        if error:
            surface_errors.append(error)
        _proc, error = _checked_process(
            ["docker", "cp", f"{task_dir_abs}/.", f"{container_id}:/task"],
            label="grader_copy_task_surface",
            timeout=60,
        )
        if error:
            surface_errors.append(error)
        if os.path.isdir(tests_mount):
            _proc, error = _checked_process(
                ["docker", "cp", f"{tests_mount}/.", f"{container_id}:/tests"],
                label="grader_copy_tests_surface",
                timeout=60,
            )
            if error:
                surface_errors.append(error)

        grader_cmd = detect_grader_command(task_dir_abs)
        grader_error = None
        if surface_errors:
            grader_exit = -1
            grader_stdout_full = ""
            grader_stderr_full = "\n".join(surface_errors)
            grader_stdout = ""
            grader_stderr = grader_stderr_full[-4000:]
            grader_error = "grader_surface_prepare_failed: " + "; ".join(surface_errors)
        else:
            try:
                _progress(progress_callback, task_name, "grader_run", grader_cmd)
                grader_proc = subprocess.run(
                    ["docker", "exec", "-w", "/app", container_id, "bash", "-lc", grader_cmd],
                    capture_output=True, text=True, errors="replace", timeout=run_timeout_s,
                )
                grader_exit = grader_proc.returncode
                grader_stdout_full = grader_proc.stdout
                grader_stderr_full = grader_proc.stderr
                grader_stdout = grader_stdout_full[-4000:]
                grader_stderr = grader_stderr_full[-4000:]
            except subprocess.TimeoutExpired as exc:
                grader_exit = -1
                grader_stdout_full = str(exc.stdout or "")
                grader_stderr_full = str(exc.stderr or "")
                grader_stdout = grader_stdout_full[-4000:]
                grader_stderr = grader_stderr_full[-4000:]
                grader_error = f"grader_timeout_after_{run_timeout_s}s"

        reward, grader_error, reward_source = _resolve_grader_reward(
            container_id=container_id,
            task_dir=task_dir_abs,
            grader_exit=grader_exit,
            grader_error=grader_error,
        )
        _progress(progress_callback, task_name, "grader_done", f"reward={reward} source={reward_source} error={grader_error}")

        # Capture optional CTRF without letting its final phase overwrite
        # earlier visible grader failures. The official reward remains
        # authoritative and contradictions are retained explicitly.
        ctrf_text: str | None = None
        try:
            cp = subprocess.run(
                ["docker", "exec", container_id, "cat", "/logs/verifier/ctrf.json"],
                capture_output=True, text=True, errors="replace", timeout=10)
            if cp.returncode == 0 and cp.stdout.strip():
                ctrf_text = cp.stdout
        except Exception:
            pass
        grader_detail = build_grader_detail(
            reward=reward, grader_exit=grader_exit,
            stdout=grader_stdout_full, stderr=grader_stderr_full,
            ctrf_text=ctrf_text,
        )

        post_grader_manifest = copy_snapshot(
            workspace_path,
            run_evidence_dir / "post_grader_workspace",
        )
        evidence_paths["post_grader_workspace"] = str(run_evidence_dir / "post_grader_workspace")
        evidence_paths["post_grader_workspace_manifest"] = str(
            run_evidence_dir / "post_grader_workspace.manifest.json"
        )
        evidence_paths["post_grader_workspace_aggregate_sha256"] = post_grader_manifest["aggregate_sha256"]

        # Grade-required services may remain live until this point. Remove and
        # verify the complete container boundary before sealing performance.
        container_teardown = _remove_container_with_evidence(container_id)
        evidence_paths["container_teardown"] = container_teardown
        if container_teardown.get("verified_absent") is True:
            container_id = None

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
        model_parse_errors = list(run_metrics.pop("model_parse_errors"))
        provider_valid, protocol_valid = _provider_protocol_validity(
            record_error=str(getattr(result, "error", "") or ""),
            classifier_label=classifier_label,
            model_parse_errors=model_parse_errors,
        )
        admission = evaluate_run_admission(
            source_identity=source_identity,
            provider_valid=provider_valid,
            protocol_valid=protocol_valid,
            grader_error=grader_error,
            reward_source=reward_source,
            task_package_sha256_start=task_package_sha256_start,
            task_package_sha256_grader=task_package_sha256_grader,
            runtime_image_sha256_expected=runtime_image_sha256_expected,
            runtime_image_sha256_container=runtime_image_sha256_container,
            teardown_verified_absent=bool(container_teardown.get("verified_absent", False)),
            evidence_surfaces_clean=bool(hidden_surface_probe.get("clean", False)),
        )
        model_call_telemetry = hooks.drain_model_telemetry()
        quarantined_model_call_telemetry = hooks.drain_quarantined_model_telemetry()
        model_interface_captures = hooks.drain_model_interface_captures()
        model_interface_index = write_model_interface_captures(
            model_interface_captures,
            run_evidence_dir / "model_interfaces",
        )
        evidence_paths["model_interfaces"] = model_interface_index

        record: dict[str, Any] = {
            "task": task_name,
            "image": image,
            "architect_mode": architect_mode,
            "runtime_identity": dict(runtime_identity or {}),
            "solver_continuity_mode": solver_continuity_mode,
            "solver_reanchor_mode": solver_reanchor_mode,
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
            "model_parse_errors": model_parse_errors,
            "run_metrics": run_metrics,
            "provider_valid": provider_valid,
            "protocol_valid": protocol_valid,
            "grader_status": admission.grader_status,
            "run_valid": admission.run_valid,
            "performance_row_admitted": admission.performance_row_admitted,
            "process_leak": admission.process_leak,
            "run_admission_reasons": list(admission.reasons),
            "task_package_sha256": task_package_sha256_start,
            "task_package_sha256_at_grader": task_package_sha256_grader,
            "task_edited_after_start": task_package_sha256_start != task_package_sha256_grader,
            "runtime_image_sha256": runtime_image_sha256_expected,
            "runtime_image_sha256_container": runtime_image_sha256_container,
            "agent_hidden_surface_probe": hidden_surface_probe,
            "container_teardown": container_teardown,
            "model_call_telemetry": list(model_call_telemetry),
            "quarantined_late_model_telemetry": list(quarantined_model_call_telemetry),
            "model_interface_manifests": compact_model_interface_manifests(model_interface_captures),
            "model_interface_index": model_interface_index,
            "grader_exit": grader_exit,
            "reward_source": reward_source,
            "official_grader_status": grader_detail["official_status"],
            "grader_stdout_tail": grader_stdout, "grader_stderr_tail": grader_stderr,
            "receipt_summary": _receipt_summary(result),
            "world_state_snapshot": world_state.dynamic_snapshot(),
            "run_provenance": dict(run_provenance or {}),
            "executing_source_identity": source_identity,
            "run_evidence_dir": str(run_evidence_dir),
            "run_evidence": dict(evidence_paths),
            "model_request_preflight": list(model_request_preflight),
            "initial_workspace_state": {
                "digest": (initial_workspace_state or {}).get("digest", ""),
                "entry_count": (initial_workspace_state or {}).get("entry_count", 0),
                "truncated": bool((initial_workspace_state or {}).get("truncated", False)),
            },
            "initial_workspace_manifest_path": initial_workspace_manifest_path,
            "expected_steps": _expected_steps_from(result),
            "step_efficiency": _step_efficiency(result),
            "run_timeout_s_effective": run_timeout_s,
            "run_timeout_policy": run_timeout_policy,
            "network_policy": network_policy.as_dict(),
            **reconcile_grader_alignment(
                reward=reward,
                grader_error=grader_error,
                kernel_status=result.status,
                verifier_verdict=verifier_verdict,
            ),
        }
        if grader_error is not None:
            record["grader_error"] = grader_error
        record["grader_detail"] = grader_detail
        record["grader_detail_conflict"] = not grader_detail["consistent_with_official_reward"]
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

        result_record_path = run_evidence_dir / "result_record.json"
        result_record_path.write_text(
            _json.dumps(record, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        evidence_paths["result_record"] = str(result_record_path)
        required_paths: list[str] = [
            str(run_evidence_dir / "observed_source_identity.json"),
            str(run_evidence_dir / "executing_source_identity.json"),
            str(run_evidence_dir / "task_package.start.manifest.json"),
            str(run_evidence_dir / "task_package.grader.manifest.json"),
            str(run_evidence_dir / "initial_workspace"),
            str(run_evidence_dir / "agent_final_workspace"),
            str(run_evidence_dir / "post_grader_workspace"),
            str(run_evidence_dir / "command_spools" / "manifest.json"),
            str(run_evidence_dir / "command_spools" / "terminals" / "manifest.json"),
            str(run_evidence_dir / "model_interfaces"),
            str(result_record_path),
        ]
        if record.get("trace_path") and Path(str(record["trace_path"])).exists():
            required_paths.append(str(record["trace_path"]))
        marker = finalize_evidence_directory(
            run_evidence_dir,
            required_paths=required_paths,
            metadata={
                "task": task_name,
                "image": image,
                "kernel_status": result.status,
                "reward": reward,
                "source_commit": source_identity.get("commit", ""),
                "source_tree": source_identity.get("tree", ""),
                "source_clean": source_identity.get("clean", False),
                "task_package_sha256": task_package_sha256_start,
                "runtime_image_sha256": runtime_image_sha256_expected,
                "performance_row_admitted": admission.performance_row_admitted,
                "run_admission_reasons": list(admission.reasons),
                "container_teardown_verified_absent": bool(container_teardown.get("verified_absent", False)),
                "solver_continuity_mode": solver_continuity_mode,
                "solver_reanchor_mode": solver_reanchor_mode,
            },
        )
        record["evidence_finalization"] = marker
        # FINALIZED.json is deliberately the last evidence write.  The returned
        # in-memory record includes its pointer; the durable pre-finalisation
        # result record is one of the checksummed inputs to the marker.
        return record

    except Exception as exc:
        record = _error_record(task_name, image, type(exc).__name__, str(exc), architect_mode=architect_mode)
        if hooks is not None:
            # A provider failure can abort the runner before the normal result
            # record is built. Do not lose telemetry or the exact interface.
            record["model_call_telemetry"] = list(hooks.drain_model_telemetry())
            record["quarantined_late_model_telemetry"] = list(
                hooks.drain_quarantined_model_telemetry()
            )
            failed_interface_captures = hooks.drain_model_interface_captures()
            record["model_interface_manifests"] = compact_model_interface_manifests(
                failed_interface_captures
            )
            if run_evidence_dir is not None:
                record["model_interface_index"] = write_model_interface_captures(
                    failed_interface_captures,
                    run_evidence_dir / "model_interfaces",
                )
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
        if hooks is not None:
            try:
                hooks.release_model_scope()
            except Exception:
                _log.warning("model continuity scope cleanup failed", exc_info=True)
        if executor is not None:
            try:
                executor.close()
            except Exception:
                _log.warning("executor terminal cleanup failed", exc_info=True)
        if container_id:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True, text=True, errors="replace", timeout=30,
            )
        if workspace_dir and os.path.isdir(workspace_dir):
            shutil.rmtree(workspace_dir, ignore_errors=True)
        if initial_snapshot_dir and os.path.isdir(initial_snapshot_dir):
            # Snapshot contents are read-only by design; restore owner write
            # permission only for teardown, never during the episode.
            for dirpath, dirnames, filenames in os.walk(initial_snapshot_dir):
                for name in filenames:
                    try:
                        (Path(dirpath) / name).chmod(0o600)
                    except OSError:
                        pass
                for name in dirnames:
                    try:
                        (Path(dirpath) / name).chmod(0o700)
                    except OSError:
                        pass
            try:
                Path(initial_snapshot_dir).chmod(0o700)
            except OSError:
                pass
            shutil.rmtree(initial_snapshot_dir, ignore_errors=True)


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
    architect_mode: str = "architect_v3",
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
        "model_call_telemetry": [],
        "quarantined_late_model_telemetry": [],
        "model_interface_manifests": [],
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
        "model_call_telemetry": [],
        "quarantined_late_model_telemetry": [],
        "model_interface_manifests": [],
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

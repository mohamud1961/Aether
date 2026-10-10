"""Fail-closed Harbor Docker execution for private P1/V5 live experiments.

The host is allowed to prepare task inputs and run the hidden grader. Solver
commands, terminals, and managed processes are owned by a fresh Harbor Docker
environment with no host bind mounts, inherited task credentials, or custom
compose overlays. This module intentionally requires the pinned Harbor runtime;
it does not substitute a fake executor when the Docker route is unavailable.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Mapping
import uuid


ISOLATION_QUALIFICATION_SCHEMA = "aether.solver_isolation_qualification.v1"
ISOLATION_ADMISSION_SCHEMA = "aether.solver_isolation_admission.v1"
ISOLATION_QUALIFICATION_ENV = "AETHER_SOLVER_ISOLATION_QUALIFICATION"
ISOLATION_QUALIFICATION_SHA_ENV = "AETHER_SOLVER_ISOLATION_QUALIFICATION_SHA256"
ISOLATION_ADMISSION_ENV = "AETHER_SOLVER_ISOLATION_ADMISSION"
ISOLATION_ADMISSION_SHA_ENV = "AETHER_SOLVER_ISOLATION_ADMISSION_SHA256"
REQUIRED_ISOLATION_CHECKS = frozenset({
    "ordinary_command_hidden_sentinel_rejected",
    "persistent_terminal_hidden_sentinel_rejected",
    "managed_process_hidden_sentinel_rejected",
    "task_file_edit_and_read_succeeded",
    "service_lifecycle_succeeded",
    "external_network_egress_rejected",
    "container_cleanup_independently_verified",
    "host_repo_and_grader_not_mounted",
    "provider_environment_not_inherited",
    "docker_socket_not_mounted",
    "host_process_namespace_not_visible",
    "v5_manifest_and_answer_metadata_not_mounted",
    "verifier_independent_snapshot_and_cleanup_succeeded",
    "spool_evidence_export_succeeded",
})
_HARBOR_VERSION = "0.20.0"
_PRIVATE_LOOPBACK_SERVICE = "aether-private-loopback-service"
_PROVIDER_ENV_KEYS = frozenset({
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_GPT56_FRONTIER_KEY",
    "AZURE_OPENAI_GPT56_FRONTIER_ENDPOINT",
    "AZURE_OPENAI_GPT56_FRONTIER_DEPLOYMENT",
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
    "AETHER_PROVIDER_CALLS_ALLOWED",
    "AETHER_PROVIDER_PROFILE_SHA256",
    "AETHER_PROVIDER_BUDGET_PATH",
    "AETHER_PROVIDER_BUDGET_SHA256",
    "AETHER_PROVIDER_BUDGET_JOURNAL",
    "AETHER_ISOLATION_TEST_CREDENTIAL_SENTINEL",
})


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_identities(repo_root: str | Path) -> dict[str, str]:
    """Hash the live P1/V5 dispatch seams and their shared Harbor adapter."""
    root = Path(repo_root).resolve()
    paths = {
        "p1_runner_sha256": "tools/p1_checkpoint_live_runner_v1.py",
        "p1_replay_sha256": "tools/p1_checkpoint_causal_replay_v1.py",
        "p1_custody_sha256": "tools/p1_checkpoint_campaign_custody.py",
        "v5_runner_sha256": "evals/performance/context_interface_experiment.py",
        "executor_module_sha256": "aether/harbor_executor.py",
        "task_environment_module_sha256": "aether/harbor_task_environment.py",
        "envmap_builder_sha256": "aether/envmap_builder.py",
        "environment_probe_sha256": "aether/environment_probe.py",
        "run_adapter_sha256": "aether/run_adapter.py",
        "qualification_script_sha256": "tools/qualify_solver_isolation_v1.py",
    }
    result: dict[str, str] = {}
    for identity, relpath in paths.items():
        file_path = root / relpath
        if not file_path.is_file() or file_path.is_symlink():
            raise RuntimeError(f"solver isolation source identity is missing or unsafe: {relpath}")
        result[identity] = _sha256(file_path.read_bytes())
    return result


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root,
            text=True, capture_output=True, timeout=10, check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"cannot establish current source commit: {type(exc).__name__}") from exc
    commit = result.stdout.strip()
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit.lower()):
        raise RuntimeError("current source commit is not a full Git object ID")
    return commit


def _git_tree(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=repo_root,
            text=True, capture_output=True, timeout=10, check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"cannot establish current source tree: {type(exc).__name__}") from exc
    return result.stdout.strip()


def validate_solver_isolation_qualification(
    path: str | Path,
    *,
    expected_sha256: str,
    source_commit: str,
    repo_root: str | Path,
) -> dict[str, Any]:
    """Accept only a real-runtime, provider-free receipt bound to this source."""
    qualification_path = Path(path).expanduser().resolve(strict=True)
    if qualification_path.is_symlink() or not qualification_path.is_file():
        raise RuntimeError("solver isolation qualification path is not a regular file")
    raw = qualification_path.read_bytes()
    observed_sha = _sha256(raw)
    if observed_sha != str(expected_sha256).strip().lower():
        raise RuntimeError("solver isolation qualification SHA256 mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("solver isolation qualification is not valid JSON") from exc
    if not isinstance(value, dict) or value.get("schema_version") != ISOLATION_QUALIFICATION_SCHEMA:
        raise RuntimeError("solver isolation qualification schema mismatch")
    if value.get("status") != "PASS":
        raise RuntimeError("solver isolation qualification status is not PASS")
    if int(value.get("provider_calls", -1)) != 0 or int(value.get("provider_creates", -1)) != 0:
        raise RuntimeError("solver isolation qualification must be provider-free")
    expected_commit = str(source_commit).strip().lower()
    root = Path(repo_root).resolve()
    current_commit = _git_commit(root)
    if expected_commit != current_commit or str(value.get("source_commit", "")).lower() != expected_commit:
        raise RuntimeError("solver isolation qualification source commit mismatch")
    current_tree = _git_tree(root)
    if str(value.get("source_tree", "")).lower() != current_tree.lower():
        raise RuntimeError("solver isolation qualification source tree mismatch")
    expected_identities = source_identities(root)
    observed_identities = value.get("identities")
    if not isinstance(observed_identities, Mapping):
        raise RuntimeError("solver isolation qualification source identities are missing")
    for key, expected in expected_identities.items():
        if str(observed_identities.get(key, "")) != expected:
            raise RuntimeError(f"solver isolation qualification identity mismatch: {key}")
    checks = value.get("checks")
    if not isinstance(checks, Mapping):
        raise RuntimeError("solver isolation qualification checks are missing")
    for check in sorted(REQUIRED_ISOLATION_CHECKS):
        if checks.get(check) is not True:
            raise RuntimeError(f"solver isolation qualification check failed: {check}")
    routes = value.get("route_receipts")
    if not isinstance(routes, Mapping) or set(routes) != {"p1", "v5"}:
        raise RuntimeError("qualification must contain real P1 and V5 route receipts")
    for route_name in ("p1", "v5"):
        route = routes.get(route_name)
        if not isinstance(route, Mapping) or route.get("status") != "PASS":
            raise RuntimeError(f"qualification route did not pass: {route_name}")
        if route.get("executor") != "aether.harbor_executor.HarborEnvironmentExecutor":
            raise RuntimeError(f"qualification route used the wrong executor: {route_name}")
        execution = route.get("execution_receipt")
        if not isinstance(execution, Mapping):
            raise RuntimeError(f"qualification route receipt is missing: {route_name}")
        if execution.get("backend") != "harbor.docker":
            raise RuntimeError(f"qualification route is not Harbor Docker: {route_name}")
        if execution.get("container_cleanup_independently_verified") is not True:
            raise RuntimeError(f"qualification route cleanup is unverified: {route_name}")
        if execution.get("host_mount_count") != 0 or not execution.get("network_policy_enforced"):
            raise RuntimeError(f"qualification route isolation receipt is incomplete: {route_name}")
        container_hash = str(execution.get("container_id_sha256", ""))
        if len(container_hash) != 64 or any(ch not in "0123456789abcdef" for ch in container_hash.lower()):
            raise RuntimeError(f"qualification route lacks an inspected container identity: {route_name}")
        route_checks = route.get("checks")
        if not isinstance(route_checks, Mapping):
            raise RuntimeError(f"qualification route checks are missing: {route_name}")
        for check in REQUIRED_ISOLATION_CHECKS:
            if check == "v5_manifest_and_answer_metadata_not_mounted" and route_name == "p1":
                continue
            if check == "container_cleanup_independently_verified":
                if execution.get("container_cleanup_independently_verified") is not True:
                    raise RuntimeError(f"qualification route check failed: {route_name}:{check}")
            elif route_checks.get(check) is not True:
                raise RuntimeError(f"qualification route check failed: {route_name}:{check}")
    runtime = value.get("runtime")
    if not isinstance(runtime, Mapping) or runtime.get("harbor_version") != _HARBOR_VERSION:
        raise RuntimeError("solver isolation qualification Harbor version mismatch")
    return {
        "status": "PASS",
        "sha256": observed_sha,
        "source_commit": expected_commit,
        "source_tree": current_tree,
        "identities": expected_identities,
        "checks": {name: True for name in sorted(REQUIRED_ISOLATION_CHECKS)},
    }


def require_solver_isolation_qualification(
    *, expected_sha256: str, source_commit: str, repo_root: str | Path,
) -> dict[str, Any]:
    """Read the qualification receipt path from the orchestrator's host env."""
    raw_path = str(os.environ.get(ISOLATION_QUALIFICATION_ENV, "") or "").strip()
    if not raw_path:
        raise RuntimeError(
            "official P1/V5 execution is fail-closed: set "
            f"{ISOLATION_QUALIFICATION_ENV} to the exact real-Harbor qualification artifact"
        )
    if not str(expected_sha256).strip():
        raise RuntimeError("official P1/V5 execution is fail-closed: preregistration lacks qualification SHA256")
    return validate_solver_isolation_qualification(
        raw_path,
        expected_sha256=expected_sha256,
        source_commit=source_commit,
        repo_root=repo_root,
    )


def validate_solver_isolation_admission(
    admission_path: str | Path,
    *,
    expected_sha256: str,
    qualification_path: str | Path,
    qualification_sha256: str,
    source_commit: str,
    repo_root: str | Path,
    frozen_artifact_name: str,
    frozen_artifact_sha256: str,
) -> dict[str, Any]:
    """Validate a separately pinned addendum that leaves frozen bytes untouched."""
    path = Path(admission_path).expanduser().resolve(strict=True)
    if Path(admission_path).is_symlink() or not path.is_file():
        raise RuntimeError("solver isolation admission path is not a regular file")
    raw = path.read_bytes()
    observed_sha = _sha256(raw)
    if observed_sha != str(expected_sha256).strip().lower():
        raise RuntimeError("solver isolation admission SHA256 mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("solver isolation admission is not valid JSON") from exc
    if not isinstance(value, dict) or value.get("schema_version") != ISOLATION_ADMISSION_SCHEMA:
        raise RuntimeError("solver isolation admission schema mismatch")
    if value.get("status") != "PASS":
        raise RuntimeError("solver isolation admission status is not PASS")
    expected_commit = str(source_commit).strip().lower()
    root = Path(repo_root).resolve()
    current_commit = _git_commit(root)
    if expected_commit != current_commit or str(value.get("source_commit", "")).lower() != expected_commit:
        raise RuntimeError("solver isolation admission source commit mismatch")
    current_tree = _git_tree(root)
    if str(value.get("source_tree", "")).lower() != current_tree.lower():
        raise RuntimeError("solver isolation admission source tree mismatch")
    expected_identities = source_identities(root)
    identities = value.get("identities")
    if not isinstance(identities, Mapping):
        raise RuntimeError("solver isolation admission source identities are missing")
    for key, expected in expected_identities.items():
        if str(identities.get(key, "")) != expected:
            raise RuntimeError(f"solver isolation admission identity mismatch: {key}")
    frozen_hashes = value.get("frozen_artifact_hashes")
    if not isinstance(frozen_hashes, Mapping):
        raise RuntimeError("solver isolation admission frozen artifact hashes are missing")
    if str(frozen_hashes.get(frozen_artifact_name, "")) != str(frozen_artifact_sha256).lower():
        raise RuntimeError(f"frozen artifact identity mismatch: {frozen_artifact_name}")
    if frozen_artifact_name == "p1_preregistration_sha256":
        if str(value.get("p1_successor_preregistration_sha256", "")).lower() != str(frozen_artifact_sha256).lower():
            raise RuntimeError("P1 successor preregistration identity mismatch")
        if not str(value.get("p1_successor_campaign_id", "")).strip():
            raise RuntimeError("P1 successor campaign identity is missing")
    if frozen_artifact_name in {"v5_manifest_sha256", "v6_manifest_sha256"}:
        version = frozen_artifact_name.split("_", 1)[0]
        manifest_field = f"{version}_manifest_sha256"
        launch_field = f"{version}_launch_id"
        if str(value.get(manifest_field, "")).lower() != str(frozen_artifact_sha256).lower():
            raise RuntimeError(f"{version.upper()} frozen manifest identity mismatch")
        if not str(value.get(launch_field, "")).strip():
            raise RuntimeError(f"{version.upper()} successor launch identity is missing")
    expected_qualification_sha = str(qualification_sha256).strip().lower()
    if str(value.get("qualification_sha256", "")).lower() != expected_qualification_sha:
        raise RuntimeError("solver isolation admission qualification hash mismatch")
    qualification = validate_solver_isolation_qualification(
        qualification_path,
        expected_sha256=expected_qualification_sha,
        source_commit=expected_commit,
        repo_root=root,
    )
    if str(value.get("qualification_source_commit", "")).lower() != expected_commit:
        raise RuntimeError("solver isolation admission qualification source mismatch")
    return {
        **{
            key: value[key]
            for key in (
                "p1_successor_preregistration_sha256",
                "p1_successor_campaign_id",
                "p1_predecessor_preregistration_sha256",
                "p1_predecessor_campaign_id",
                "p1_successor_identities",
                "v5_manifest_sha256",
                "v5_predecessor_experiment_id",
                "v5_launch_id",
                "v6_manifest_sha256",
                "v6_predecessor_experiment_id",
                "v6_launch_id",
            )
            if key in value
        },
        "status": "PASS",
        "sha256": observed_sha,
        "source_commit": expected_commit,
        "source_tree": current_tree,
        "identities": expected_identities,
        "frozen_artifact_name": frozen_artifact_name,
        "frozen_artifact_sha256": str(frozen_artifact_sha256).lower(),
        "qualification": qualification,
    }


def require_solver_isolation_admission(
    *,
    source_commit: str,
    repo_root: str | Path,
    frozen_artifact_name: str,
    frozen_artifact_sha256: str,
) -> dict[str, Any]:
    """Read explicitly hash-pinned qualification and addendum paths from the host env."""
    admission_path = str(os.environ.get(ISOLATION_ADMISSION_ENV, "") or "").strip()
    admission_sha = str(os.environ.get(ISOLATION_ADMISSION_SHA_ENV, "") or "").strip()
    qualification_path = str(os.environ.get(ISOLATION_QUALIFICATION_ENV, "") or "").strip()
    qualification_sha = str(os.environ.get(ISOLATION_QUALIFICATION_SHA_ENV, "") or "").strip()
    if not all((admission_path, admission_sha, qualification_path, qualification_sha)):
        raise RuntimeError(
            "official P1/V5 execution is fail-closed: set the exact isolation admission and "
            "qualification paths plus their pinned SHA256 values"
        )
    return validate_solver_isolation_admission(
        admission_path,
        expected_sha256=admission_sha,
        qualification_path=qualification_path,
        qualification_sha256=qualification_sha,
        source_commit=source_commit,
        repo_root=repo_root,
        frozen_artifact_name=frozen_artifact_name,
        frozen_artifact_sha256=frozen_artifact_sha256,
    )


def write_solver_isolation_admission(
    *,
    path: str | Path,
    qualification_path: str | Path,
    p1_preregistration_path: str | Path,
    v5_manifest_path: str | Path,
    repo_root: str | Path,
) -> dict[str, Any]:
    """Create the successor addendum after a real qualification has passed."""
    root = Path(repo_root).resolve()
    commit = _git_commit(root)
    identities = source_identities(root)
    qualification_file = Path(qualification_path).resolve(strict=True)
    qualification_sha = _sha256(qualification_file.read_bytes())
    qualification = validate_solver_isolation_qualification(
        qualification_file,
        expected_sha256=qualification_sha,
        source_commit=commit,
        repo_root=root,
    )
    prereg_path = Path(p1_preregistration_path).resolve(strict=True)
    manifest_file = Path(v5_manifest_path).resolve(strict=True)
    try:
        p1_prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
        v5_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("successor launch inputs are not valid JSON") from exc
    if not isinstance(p1_prereg, dict) or p1_prereg.get("schema") != "aether.p1_checkpoint_live_preregistration.v1":
        raise RuntimeError("P1 successor preregistration schema mismatch")
    if str(p1_prereg.get("source_commit", "")).lower() != commit.lower():
        raise RuntimeError("P1 successor preregistration must name the current source commit")
    successor_of = p1_prereg.get("successor_of")
    if not isinstance(successor_of, Mapping):
        raise RuntimeError("P1 launch must use an explicit successor preregistration, not the frozen predecessor")
    predecessor_hash = str(successor_of.get("predecessor_preregistration_sha256", "")).lower()
    predecessor_campaign = str(successor_of.get("predecessor_campaign_id", ""))
    p1_campaign = str(p1_prereg.get("campaign_id", ""))
    if len(predecessor_hash) != 64 or not predecessor_campaign or not p1_campaign or predecessor_campaign == p1_campaign:
        raise RuntimeError("P1 successor preregistration lacks a distinct, hash-bound predecessor/campaign identity")
    context_schema = str(v5_manifest.get("schema_version") or "")
    if context_schema not in {
        "aether.phase_c_context_interface.v5",
        "aether.phase_c_context_interface.v6",
    }:
        raise RuntimeError("expected a frozen V5/V6 context manifest for successor launch identity")
    context_version = "v6" if context_schema.endswith(".v6") else "v5"
    context_manifest_key = f"{context_version}_manifest_sha256"
    context_predecessor_key = f"{context_version}_predecessor_experiment_id"
    context_launch_key = f"{context_version}_launch_id"
    from aether.launch import package_closure, production_tool_schema_sha256
    from aether.model_profile import PRODUCTION_PROFILE
    from tools import p1_checkpoint_live_runner_v1 as p1_live
    p1_successor_identities = {
        "live_runner_sha256": _sha256(p1_live.RUNNER.read_bytes()),
        "checkpoint_replay_sha256": _sha256(p1_live.REPLAY.read_bytes()),
        "campaign_custody_sha256": _sha256(p1_live.CUSTODY.read_bytes()),
        "budget_candidate_audit_sha256": _sha256(p1_live.BUDGET_AUDIT.read_bytes()),
        "package_closure_sha256": package_closure().sha256,
        "profile_sha256": PRODUCTION_PROFILE.sha256(),
        "tool_schema_sha256": production_tool_schema_sha256(),
    }
    if dict(p1_prereg.get("identities") or {}) != p1_successor_identities:
        raise RuntimeError("P1 successor preregistration identities do not match the committed live source")
    frozen_hashes = {
        "p1_preregistration_sha256": _sha256(prereg_path.read_bytes()),
        context_manifest_key: _sha256(manifest_file.read_bytes()),
        "p1_predecessor_preregistration_sha256": predecessor_hash,
    }
    context_launch_id = (
        str(v5_manifest.get("experiment_id", f"phase-c-{context_version}"))
        + "-solver-isolation-" + commit[:12]
    )
    value = {
        "schema_version": ISOLATION_ADMISSION_SCHEMA,
        "status": "PASS",
        "source_commit": commit,
        "source_tree": _git_tree(root),
        "identities": identities,
        "frozen_artifact_hashes": frozen_hashes,
        "p1_successor_preregistration_sha256": frozen_hashes["p1_preregistration_sha256"],
        "p1_successor_campaign_id": p1_campaign,
        "p1_predecessor_preregistration_sha256": predecessor_hash,
        "p1_predecessor_campaign_id": predecessor_campaign,
        "p1_successor_identities": p1_successor_identities,
        context_manifest_key: frozen_hashes[context_manifest_key],
        context_predecessor_key: str(v5_manifest.get("experiment_id", "")),
        context_launch_key: context_launch_id,
        "qualification_sha256": qualification_sha,
        "qualification_source_commit": qualification["source_commit"],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with target.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"refusing to overwrite solver isolation admission: {target}") from exc
    return {**value, "sha256": _sha256(encoded)}


def require_harbor_docker_runtime() -> dict[str, str]:
    """Require the pinned Harbor package and a live Linux Docker daemon."""
    if platform.system() != "Linux":
        raise RuntimeError("Solver isolation requires a Linux host; macOS/Windows fallback is prohibited")
    try:
        version = importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("Harbor 0.20.0 is not installed; install the pinned project extra") from exc
    if version != _HARBOR_VERSION:
        raise RuntimeError(f"Harbor version mismatch: expected {_HARBOR_VERSION}, observed {version}")
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable; Solver execution remains fail-closed")
    for command in ([docker, "compose", "version"], [docker, "info", "--format", "{{.OSType}}"]):
        try:
            result = subprocess.run(
                command, text=True, capture_output=True, timeout=15, check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Docker runtime preflight failed: {type(exc).__name__}") from exc
        if command[-1] == "{{.OSType}}" and result.stdout.strip().lower() != "linux":
            raise RuntimeError("Docker daemon is not running Linux containers")
    return {"harbor_version": version, "docker_cli": docker, "daemon_os": "linux"}


def validate_contained_relative_symlink(path: str | Path, root: str | Path) -> Path:
    """Accept only a relative symlink whose resolved target remains inside root.

    Task fixtures may legitimately use relative in-workspace links. The Solver
    boundary may preserve those semantics, but it must never let a task link
    escape into host/control material. Broken and absolute links fail closed.
    """
    root_path = Path(root).resolve(strict=True)
    link = Path(path)
    if not link.is_symlink():
        raise RuntimeError(f"expected a symlink for containment validation: {link}")
    try:
        link_parent = link.parent.resolve(strict=True)
        link_parent.relative_to(root_path)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise RuntimeError(f"Solver build context symlink location escapes root: {link}") from exc
    raw_target = os.readlink(link)
    target = Path(raw_target)
    if target.is_absolute():
        raise RuntimeError(f"Solver build context symlink target must be relative: {link}")
    try:
        resolved = (link.parent / target).resolve(strict=True)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        raise RuntimeError(f"Solver build context contains a broken symlink: {link}") from exc
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise RuntimeError(f"Solver build context symlink escapes root: {link}") from exc
    return resolved


def validate_solver_build_context(path: str | Path) -> Path:
    """Reject host-control/grader material; allow only contained relative links."""
    root = Path(path).resolve(strict=True)
    if not root.is_dir() or Path(path).is_symlink():
        raise RuntimeError("Solver build context must be a real directory")
    denied_parts = {
        ".git", ".ssh", ".aws", ".azure", ".config", "tests",
        "solution", "solutions", "grader", "graders", "ceiling", "known_bad",
        "answer", "answers", "private",
    }
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in [*dirs, *files]:
            item = current_path / name
            rel = item.relative_to(root)
            lower = name.lower()
            if item.is_symlink():
                validate_contained_relative_symlink(item, root)
            if any(part.lower() in denied_parts for part in rel.parts):
                raise RuntimeError(f"Solver build context contains denied material: {rel.as_posix()}")
            if lower == ".env" or lower.startswith(".env."):
                raise RuntimeError(f"Solver build context contains an environment file: {rel.as_posix()}")
            if lower.startswith("docker-compose") and Path(lower).suffix in {".yml", ".yaml"}:
                raise RuntimeError(f"Solver build context contains a Compose overlay: {rel.as_posix()}")
            if lower in {"compose.yml", "compose.yaml", "docker.sock", "grade.py", "grader.py"}:
                raise RuntimeError(f"Solver build context contains denied control/grader material: {rel.as_posix()}")
        # Never traverse through a symlinked directory here. Its resolved
        # target must already live elsewhere under root and will be scanned by
        # its canonical path during the ordinary walk.
        dirs[:] = sorted(
            name for name in dirs if not (current_path / name).is_symlink()
        )
    return root


def make_v5_solver_build_context(workspace: str | Path, destination: str | Path) -> Path:
    """Create a V5 context from task-world files only; never copy its manifest."""
    source = Path(workspace).resolve(strict=True)
    target = Path(destination).resolve()
    if target.exists():
        raise RuntimeError(f"V5 solver build context already exists: {target}")
    if source.is_symlink() or not source.is_dir():
        raise RuntimeError("V5 fixture workspace must be a real directory")
    allowed_top = {"instruction.md", "data", "bin", "py"}
    actual_top = {entry.name for entry in source.iterdir()}
    if actual_top != allowed_top:
        raise RuntimeError("V5 fixture workspace does not match its task-world allowlist")
    for current, dirs, files in os.walk(source, followlinks=False):
        for name in [*dirs, *files]:
            if (Path(current) / name).is_symlink():
                raise RuntimeError("V5 fixture workspace contains a symlink")
    target.mkdir(parents=True)
    try:
        for name in sorted(allowed_top):
            src = source / name
            if src.is_symlink():
                raise RuntimeError(f"V5 task-world input is a symlink: {name}")
            if name == "instruction.md":
                if not src.is_file():
                    raise RuntimeError("V5 instruction file is missing")
                shutil.copy2(src, target / name)
            else:
                if not src.is_dir():
                    raise RuntimeError(f"V5 task-world directory is missing: {name}")
                shutil.copytree(src, target / name, symlinks=False)
        (target / "Dockerfile").write_text(
            "FROM python:3.13-slim-bookworm\n"
            "WORKDIR /app\n"
            "COPY instruction.md /app/instruction.md\n"
            "COPY data/ /app/data/\n"
            "COPY bin/ /app/bin/\n"
            "COPY py/ /app/py/\n",
            encoding="utf-8",
        )
        (target / ".dockerignore").write_text(".dockerignore\n", encoding="utf-8")
        validate_solver_build_context(target)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return target


def task_environment_config_from_toml(path: str | Path) -> Any:
    """Parse only the declared public network policy and resource limits."""
    try:
        from harbor.models.task.config import TaskConfig
    except ImportError as exc:
        raise RuntimeError("pinned Harbor task config models are unavailable") from exc
    task_config = TaskConfig.model_validate_toml(Path(path).read_text(encoding="utf-8"))
    source = task_config.environment
    if source.env or source.mcp_servers:
        raise RuntimeError("Solver isolation refuses task-provided environment credentials or MCP servers")
    baseline = source.resolve_baseline()
    return _task_environment_config(
        network_mode=str(baseline.network_mode.value),
        allowed_hosts=list(baseline.allowed_hosts),
        cpus=source.cpus,
        memory_mb=source.memory_mb,
        storage_mb=source.storage_mb,
        # Host/VM accelerators are infrastructure resources; never expose a
        # GPU device to the Solver task container through Harbor.
        gpus=0,
    )


def _task_environment_config(
    *, network_mode: str, allowed_hosts: list[str] | None = None,
    cpus: int | None = None, memory_mb: int | None = None,
    storage_mb: int | None = None, gpus: int | None = None,
) -> Any:
    try:
        from harbor.models.task.config import EnvironmentConfig, NetworkMode
    except ImportError as exc:
        raise RuntimeError("pinned Harbor environment config models are unavailable") from exc
    try:
        mode = NetworkMode(str(network_mode))
    except ValueError as exc:
        raise RuntimeError(f"unsupported task network policy: {network_mode}") from exc
    if mode.value != "no-network":
        raise RuntimeError("P1/V5 Solver containers must use no-network policy")
    return EnvironmentConfig(
        network_mode=mode,
        allowed_hosts=allowed_hosts,
        cpus=cpus,
        memory_mb=memory_mb,
        storage_mb=storage_mb,
        gpus=gpus or 0,
        env={},
        mcp_servers=[],
    )


def v5_task_environment_config() -> Any:
    return _task_environment_config(network_mode="no-network")


def _validate_private_loopback_build_context(path: str | Path) -> Path:
    """Validate one private sidecar build context that is never model-mounted."""
    root = Path(path).resolve(strict=True)
    if not root.is_dir() or Path(path).is_symlink():
        raise RuntimeError("private loopback sidecar context must be a real directory")
    dockerfile = root / "Dockerfile"
    if not dockerfile.is_file() or dockerfile.is_symlink():
        raise RuntimeError("private loopback sidecar context requires a regular Dockerfile")
    denied_names = {".env", "docker.sock"}
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in [*dirs, *files]:
            item = Path(current) / name
            rel = item.relative_to(root)
            lower = name.lower()
            if item.is_symlink():
                raise RuntimeError(f"private loopback sidecar context contains a symlink: {rel.as_posix()}")
            if ".git" in {part.lower() for part in rel.parts}:
                raise RuntimeError(f"private loopback sidecar context contains Git metadata: {rel.as_posix()}")
            if lower in denied_names or lower.startswith(".env."):
                raise RuntimeError(f"private loopback sidecar context contains denied host material: {rel.as_posix()}")
        dirs[:] = sorted(dirs)
    return root


def _write_solver_loopback_sidecar_override(root: Path, private_context: str | Path) -> Path:
    """Write the only supported Solver-private-service topology.

    ``main`` owns a Docker ``none`` network namespace. The private service joins
    exactly that namespace, so localhost protocols work but neither container has
    an external network interface. Filesystem/PID namespaces remain separate.
    """
    context = _validate_private_loopback_build_context(private_context)
    path = root / "aether-solver-private-loopback.json"
    payload = {
        "services": {
            "main": {"network_mode": "none"},
            _PRIVATE_LOOPBACK_SERVICE: {
                "build": {"context": str(context)},
                "network_mode": "service:main",
                "depends_on": {"main": {"condition": "service_started"}},
                "restart": "no",
            },
        }
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _inspect_private_loopback_sidecar(executor: Any, runtime: Mapping[str, str]) -> dict[str, Any]:
    """Fail closed unless the private service shares only main's network namespace."""
    main_id, error = executor._harbor_docker_main_container_id()
    if error or not main_id:
        raise RuntimeError("cannot identify Solver main container for private loopback sidecar: " + (error or "missing"))
    compose = getattr(executor.environment, "_run_docker_compose_command", None)
    if not callable(compose):
        raise RuntimeError("Harbor private loopback sidecar compose seam unavailable")
    result = executor._await(
        compose(["ps", "-q", _PRIVATE_LOOPBACK_SERVICE], check=False, timeout_sec=30),
        timeout_s=35,
    )
    code, stdout, stderr = executor._result_fields(result)
    rows = [line.strip() for line in stdout.splitlines() if line.strip()]
    if code != 0 or len(rows) != 1:
        raise RuntimeError("private loopback sidecar lookup failed: " + (stderr or stdout)[-1000:])
    sidecar_id = rows[0].lower()
    inspected = subprocess.run(
        [runtime["docker_cli"], "inspect", sidecar_id],
        text=True, capture_output=True, timeout=15, check=True,
    )
    payload = json.loads(inspected.stdout)
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], Mapping):
        raise RuntimeError("private loopback sidecar Docker inspect shape invalid")
    container = payload[0]
    mounts = container.get("Mounts") or []
    host = container.get("HostConfig") or {}
    config = container.get("Config") or {}
    network_mode = str(host.get("NetworkMode") or "")
    pid_mode = str(host.get("PidMode") or "")
    privileged = host.get("Privileged") is True
    cap_add = [str(value) for value in (host.get("CapAdd") or [])]
    env_names = {str(row).split("=", 1)[0].upper() for row in (config.get("Env") or [])}
    inherited_provider_env = any(
        name in _PROVIDER_ENV_KEYS
        or name.startswith(("AZURE_OPENAI_", "OPENAI_", "AETHER_"))
        or any(secret in name for secret in ("API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "CREDENTIAL"))
        for name in env_names
    )
    checks = {
        "shares_exact_main_network_namespace": network_mode == f"container:{main_id}",
        "zero_mounts": len(mounts) == 0,
        "pid_namespace_not_host": pid_mode.lower() != "host",
        "not_privileged": not privileged,
        "no_added_capabilities": not cap_add,
        "provider_environment_not_inherited": not inherited_provider_env,
        "docker_socket_not_mounted": all(
            str(row.get("Destination") or "") not in {"/var/run/docker.sock", "/run/docker.sock"}
            for row in mounts if isinstance(row, Mapping)
        ),
    }
    if not all(checks.values()):
        failed = [name for name, value in checks.items() if not value]
        raise RuntimeError("private loopback sidecar isolation failed: " + ", ".join(failed))
    return {
        "service_name": _PRIVATE_LOOPBACK_SERVICE,
        "container_id_sha256": _sha256(sidecar_id.encode("utf-8")),
        "network_mode": "service:main",
        "checks": checks,
    }


def _write_solver_no_network_override(root: Path) -> Path:
    """Write an Aether-owned Compose override that gives ``main`` no network stack.

    Aether binds the no-network invariant to Docker's primitive directly rather
    than relying on transparent-proxy handshake semantics. Harbor's egress proxy
    may accept a local TCP handshake even when upstream payload forwarding is
    denied, so socket-connect success alone is not a trustworthy isolation
    observable. The override lives outside the task build context and carries no
    task/grader data.
    """
    path = root / "aether-solver-network-none.json"
    path.write_text(
        json.dumps({"services": {"main": {"network_mode": "none"}}}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


_POSTRUN_WORKSPACE_DOWNLOAD_TIMEOUT_S = 180.0
_POSTRUN_ENVIRONMENT_STOP_TIMEOUT_S = 120.0


async def _bounded_harbor_await(awaitable, *, timeout_s: float, label: str):
    try:
        return await asyncio.wait_for(awaitable, timeout=max(1.0, float(timeout_s)))
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"{label} timed out after {float(timeout_s):g}s") from exc


def run_in_fresh_harbor_container(
    *,
    build_context: str | Path,
    local_workspace: str | Path,
    task_environment_config: Any,
    environment_name: str,
    callback: Callable[[Any], Any],
    local_state_dir: str | Path,
    startup_timeout_s: float = 180.0,
    private_loopback_build_context: str | Path | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Run a synchronous Aether callback on Harbor's live loop in a fresh Docker task world."""
    runtime = require_harbor_docker_runtime()
    context = validate_solver_build_context(build_context)
    workspace = Path(local_workspace).resolve()
    if not workspace.is_dir() or workspace.is_symlink():
        raise RuntimeError("local task workspace must be a real directory")
    try:
        from harbor.environments.factory import EnvironmentFactory
        from harbor.models.environment_type import EnvironmentType
        from harbor.models.task.config import NetworkPolicy
        from harbor.models.trial.config import EnvironmentConfig as TrialEnvironmentConfig
        from harbor.models.trial.paths import TrialPaths
        from .harbor_executor import HarborEnvironmentExecutor
    except ImportError as exc:
        raise RuntimeError("pinned Harbor Docker environment API is unavailable") from exc

    session_id = f"aether-{environment_name}-{uuid.uuid4().hex[:12]}"
    trial_root = Path(tempfile.mkdtemp(prefix="aether-harbor-trial-"))
    download_root = trial_root / "workspace-download"
    task_network_mode = str(getattr(task_environment_config.network_mode, "value", task_environment_config.network_mode))
    if task_network_mode != "no-network":
        raise RuntimeError(
            "Aether Harbor Solver execution is fail-closed: only no-network task worlds are supported"
        )
    network_override = (
        _write_solver_loopback_sidecar_override(trial_root, private_loopback_build_context)
        if private_loopback_build_context is not None
        else _write_solver_no_network_override(trial_root)
    )
    trial_environment = TrialEnvironmentConfig(
        type=EnvironmentType.DOCKER,
        force_build=True,
        delete=True,
        mounts=[],
        extra_docker_compose=[network_override],
        env={},
        kwargs={},
    )
    environment = EnvironmentFactory.create_environment_from_config(
        trial_environment,
        environment_dir=context,
        environment_name=environment_name,
        session_id=session_id,
        trial_paths=TrialPaths(trial_dir=trial_root / "trial"),
        task_env_config=task_environment_config,
        mounts=[],
        persistent_env={},
        extra_docker_compose=[network_override],
        # Harbor's trial configuration does not infer the task network policy
        # from ``task_env_config``. Pass the resolved policy explicitly so the
        # Docker environment selects its no-network compose overlay instead of
        # silently starting on the default bridge network.
        network_policy=NetworkPolicy(
            network_mode=task_environment_config.network_mode,
            allowed_hosts=list(task_environment_config.allowed_hosts or []),
        ),
    )
    executor: Any = None
    record: Any = None
    failure: BaseException | None = None
    cleanup_verified = False
    cleanup_fallback: dict[str, Any] = {}
    inspection: dict[str, Any] = {}
    private_sidecar_inspection: dict[str, Any] = {}

    async def _run() -> None:
        nonlocal executor, record, failure, cleanup_verified, cleanup_fallback, inspection, private_sidecar_inspection
        loop = asyncio.get_running_loop()
        try:
            try:
                await asyncio.wait_for(
                    environment.start(force_build=True),
                    timeout=max(1.0, float(startup_timeout_s)),
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError("Harbor task environment startup timed out") from exc
            executor = HarborEnvironmentExecutor(
                environment,
                event_loop=loop,
                workspace_root="/app",
                local_state_dir=local_state_dir,
            )
            inspection = await asyncio.to_thread(_inspect_live_container, executor, runtime)
            if private_loopback_build_context is not None:
                private_sidecar_inspection = await asyncio.to_thread(
                    _inspect_private_loopback_sidecar, executor, runtime
                )
            record = await asyncio.to_thread(callback, executor)
            await _bounded_harbor_await(
                environment.download_dir("/app", download_root),
                timeout_s=_POSTRUN_WORKSPACE_DOWNLOAD_TIMEOUT_S,
                label="Harbor task workspace download",
            )
            _replace_workspace(workspace, download_root)
        except BaseException as exc:  # preserve callback/runtime failure through teardown
            failure = exc
        finally:
            if executor is not None:
                try:
                    await asyncio.to_thread(executor.close)
                except BaseException as exc:
                    failure = failure or RuntimeError(f"Harbor executor cleanup failed: {type(exc).__name__}")
            try:
                await _bounded_harbor_await(
                    environment.stop(delete=True),
                    timeout_s=_POSTRUN_ENVIRONMENT_STOP_TIMEOUT_S,
                    label="Harbor environment teardown",
                )
            except BaseException as exc:
                failure = failure or RuntimeError(
                    f"Harbor environment teardown failed: {type(exc).__name__}: {exc}"
                )
            try:
                cleanup_fallback = await asyncio.to_thread(
                    _cleanup_compose_project, session_id, runtime["docker_cli"]
                )
                cleanup_verified = bool(cleanup_fallback.get("verified_clean"))
            except BaseException as exc:
                cleanup_fallback = {
                    "project": session_id,
                    "verified_clean": False,
                    "failures": [f"{type(exc).__name__}: {exc}"],
                }
                cleanup_verified = False
                failure = failure or RuntimeError(
                    f"Harbor exact-project cleanup failed: {type(exc).__name__}: {exc}"
                )

    try:
        asyncio.run(_run())
    finally:
        shutil.rmtree(trial_root, ignore_errors=True)
    receipt = {
        "backend": "harbor.docker",
        "executor": "aether.harbor_executor.HarborEnvironmentExecutor",
        "harbor_version": runtime["harbor_version"],
        "workspace_root": "/app",
        "session_id": session_id,
        "network_mode": "no-network",
        "docker_network_mode": str(inspection.get("network_mode", "")),
        "network_policy_enforced": bool(inspection.get("network_policy_enforced")),
        "network_policy_transport": str(inspection.get("network_policy_transport", "")),
        "egress_sidecar_id_sha256": str(inspection.get("egress_sidecar_id_sha256", "")),
        "container_id_sha256": str(inspection.get("container_id_sha256", "")),
        "host_mount_count": int(inspection.get("mount_count", -1)),
        "host_mount_targets": list(inspection.get("mount_targets", ())),
        "pid_mode": str(inspection.get("pid_mode", "")),
        "privileged": bool(inspection.get("privileged")),
        "provider_environment_not_inherited": bool(inspection.get("provider_environment_not_inherited")),
        "docker_socket_not_mounted": bool(inspection.get("docker_socket_not_mounted")),
        "host_process_namespace_not_visible": bool(inspection.get("host_process_namespace_not_visible")),
        "host_repo_and_grader_not_mounted": int(inspection.get("mount_count", -1)) == 0,
        "container_cleanup_independently_verified": bool(cleanup_verified),
        "compose_project_cleanup": cleanup_fallback or None,
        "private_loopback_sidecar": private_sidecar_inspection or None,
    }
    if not cleanup_verified:
        failure = failure or RuntimeError("Harbor Docker containers or networks remain after cleanup")
    if failure is not None:
        raise failure
    if isinstance(record, dict):
        record["solver_execution_isolation"] = receipt
    return record, receipt


def _replace_workspace(workspace: Path, downloaded: Path) -> None:
    if not downloaded.is_dir() or downloaded.is_symlink():
        raise RuntimeError("Harbor did not return a real /app workspace")
    replacement = workspace.with_name(workspace.name + ".harbor-result")
    shutil.rmtree(replacement, ignore_errors=True)
    # Harbor's supervision directories can contain named pipes (for example,
    # an interactive terminal's input.fifo). Exclude them before copytree tries
    # to copy those control files as ordinary artifacts. Their useful output is
    # already captured in execution receipts and the executor's spool archive.
    harbor_control_root = (downloaded / ".aether").resolve()

    def ignore_harbor_control_dirs(source: str, names: list[str]) -> list[str]:
        if Path(source).resolve() != harbor_control_root:
            return []
        return [name for name in names if name in {"harbor_jobs", "harbor_terminals"}]

    shutil.copytree(
        downloaded,
        replacement,
        symlinks=False,
        ignore=ignore_harbor_control_dirs,
    )
    # Retain the post-copy cleanup as a defense against runtime layouts that
    # materialize these names as files rather than traversable directories.
    for relpath in (".aether/harbor_jobs", ".aether/harbor_terminals"):
        shutil.rmtree(replacement / relpath, ignore_errors=True)
    try:
        (replacement / ".aether").rmdir()
    except OSError:
        pass
    shutil.rmtree(workspace)
    replacement.rename(workspace)


def _solver_network_policy_identity(network_mode: str) -> dict[str, Any]:
    """Accept only Docker's primitive network-none isolation for Solver main.

    Harbor's transparent egress-control sidecar can make a local TCP handshake
    succeed even when upstream payload forwarding is denied. Current Aether
    execution always installs an explicit ``network_mode: none`` override, so
    any other observed network mode is source/runtime drift and must fail closed.
    """
    value = str(network_mode or "").strip()
    if value != "none":
        raise RuntimeError(
            f"Solver container network policy is not Docker none: {value or '<empty>'}"
        )
    return {
        "network_policy_enforced": True,
        "network_policy_transport": "docker-none",
        "egress_sidecar_id_sha256": "",
    }


def _inspect_live_container(executor: Any, runtime: Mapping[str, str]) -> dict[str, Any]:
    container_id, detail = executor._harbor_docker_main_container_id()
    if not container_id:
        raise RuntimeError(f"cannot identify exact Harbor Solver container: {detail}")
    result = subprocess.run(
        [runtime["docker_cli"], "inspect", container_id],
        text=True, capture_output=True, timeout=15, check=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise RuntimeError("Docker inspect did not return exactly one Solver container")
    container = payload[0]
    mounts = container.get("Mounts") or []
    host_config = container.get("HostConfig") or {}
    config = container.get("Config") or {}
    pid_mode = str(host_config.get("PidMode") or "")
    network_mode = str(host_config.get("NetworkMode") or "")
    privileged = host_config.get("Privileged") is True
    mount_targets = {str(row.get("Destination") or "") for row in mounts if isinstance(row, Mapping)}
    if mounts:
        raise RuntimeError("Solver container has host/container mounts; only ephemeral task image layers are allowed")
    if pid_mode.lower() == "host":
        raise RuntimeError("Solver container shares the host PID namespace")
    if privileged:
        raise RuntimeError("Solver container is privileged")
    if "/var/run/docker.sock" in mount_targets or "/run/docker.sock" in mount_targets:
        raise RuntimeError("Docker socket is mounted into the Solver container")
    network_identity = _solver_network_policy_identity(network_mode)
    network_policy_enforced = bool(network_identity["network_policy_enforced"])
    network_policy_transport = str(network_identity["network_policy_transport"])
    env_rows = config.get("Env") or []
    env_names = {str(row).split("=", 1)[0].upper() for row in env_rows}
    inherited_provider_env = any(
        name in _PROVIDER_ENV_KEYS
        or name.startswith(("AZURE_OPENAI_", "OPENAI_", "AETHER_"))
        or any(secret in name for secret in ("API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "CREDENTIAL"))
        for name in env_names
    )
    if inherited_provider_env:
        raise RuntimeError("Solver container inherited a forbidden provider/test environment variable")
    return {
        "container_id_sha256": _sha256(container_id.encode("utf-8")),
        "mount_count": len(mounts),
        "mount_targets": sorted(mount_targets),
        "pid_mode": pid_mode,
        "network_mode": network_mode,
        "network_policy_enforced": network_policy_enforced,
        "network_policy_transport": network_policy_transport,
        "egress_sidecar_id_sha256": str(network_identity["egress_sidecar_id_sha256"]),
        "privileged": privileged,
        "provider_environment_not_inherited": not inherited_provider_env,
        "docker_socket_not_mounted": True,
        "host_process_namespace_not_visible": pid_mode.lower() != "host" and not privileged,
    }


def _compose_project_resource_ids(session_id: str, docker_cli: str) -> tuple[list[str], list[str]]:
    containers = subprocess.run(
        [docker_cli, "ps", "-aq", "--filter", f"label=com.docker.compose.project={session_id}"],
        text=True, capture_output=True, timeout=15, check=True,
    ).stdout.split()
    networks = subprocess.run(
        [docker_cli, "network", "ls", "-q", "--filter", f"label=com.docker.compose.project={session_id}"],
        text=True, capture_output=True, timeout=15, check=True,
    ).stdout.split()
    return containers, networks


def _cleanup_compose_project(session_id: str, docker_cli: str) -> dict[str, Any]:
    """Best-effort exact-project fallback cleanup after Harbor teardown.

    Harbor normally owns lifecycle cleanup. This fallback exists for timeout,
    cancellation and exception paths where Harbor can leave its Compose project
    behind. Only resources carrying this exact row's project label are touched.
    """
    before_containers, before_networks = _compose_project_resource_ids(session_id, docker_cli)
    removed_containers: list[str] = []
    removed_networks: list[str] = []
    failures: list[str] = []

    for container_id in before_containers:
        result = subprocess.run(
            [docker_cli, "rm", "-f", container_id],
            text=True, capture_output=True, timeout=30, check=False,
        )
        if result.returncode == 0:
            removed_containers.append(container_id)
        else:
            failures.append(
                f"container:{container_id}:rc={result.returncode}:{(result.stderr or '')[-500:]}"
            )

    # Re-list after containers are gone because Compose networks can remain even
    # when Harbor partially completed its own teardown.
    _, network_ids = _compose_project_resource_ids(session_id, docker_cli)
    for network_id in network_ids:
        result = subprocess.run(
            [docker_cli, "network", "rm", network_id],
            text=True, capture_output=True, timeout=30, check=False,
        )
        if result.returncode == 0:
            removed_networks.append(network_id)
        else:
            failures.append(
                f"network:{network_id}:rc={result.returncode}:{(result.stderr or '')[-500:]}"
            )

    after_containers, after_networks = _compose_project_resource_ids(session_id, docker_cli)
    return {
        "project": session_id,
        "before_container_count": len(before_containers),
        "before_network_count": len(before_networks),
        "removed_container_ids": removed_containers,
        "removed_network_ids": removed_networks,
        "remaining_container_ids": after_containers,
        "remaining_network_ids": after_networks,
        "failures": failures,
        "verified_clean": not after_containers and not after_networks,
    }


def _no_compose_resources_remain(session_id: str, docker_cli: str) -> bool:
    containers, networks = _compose_project_resource_ids(session_id, docker_cli)
    return not containers and not networks


__all__ = [
    "ISOLATION_QUALIFICATION_ENV",
    "ISOLATION_QUALIFICATION_SHA_ENV",
    "ISOLATION_ADMISSION_ENV",
    "ISOLATION_ADMISSION_SHA_ENV",
    "ISOLATION_ADMISSION_SCHEMA",
    "ISOLATION_QUALIFICATION_SCHEMA",
    "REQUIRED_ISOLATION_CHECKS",
    "make_v5_solver_build_context",
    "require_harbor_docker_runtime",
    "require_solver_isolation_admission",
    "require_solver_isolation_qualification",
    "run_in_fresh_harbor_container",
    "source_identities",
    "task_environment_config_from_toml",
    "validate_contained_relative_symlink",
    "validate_solver_build_context",
    "validate_solver_isolation_qualification",
    "validate_solver_isolation_admission",
    "write_solver_isolation_admission",
    "v5_task_environment_config",
]

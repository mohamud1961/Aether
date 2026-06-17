"""Certified sandbox contract helpers for benchmark-native execution."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any
import uuid

from runner.schemas import SchemaValidationError

DEFAULT_CONTAINER_WORKSPACE_ROOT = "/app"
CERTIFIED_BACKEND_TYPES = ("docker", "linux_container", "approved_equivalent")
ALLOWED_FAILURE_LABELS = (
    "path_cwd",
    "runtime",
    "provider",
    "tool_contract",
    "sandbox",
    "verification_grading",
    "unclear",
)
REQUIRED_REPLAY_FIELDS = (
    "tool_io",
    "cwd",
    "environment_manifest_ref",
    "file_hashes_or_deltas",
    "verifier_grader_output",
    "visible_model_messages",
)
DEFAULT_ARTIFACTS_DIR = "artifacts/certified_smoke"


def _require_non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{path} must be a non-empty string")
    return value


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{path} must be a list")
    return value


def _require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(f"{path} must be a boolean")
    return value


def build_environment_manifest(
    *,
    host_workspace_path: str,
    backend_type: str,
    image_metadata: dict[str, Any],
    python_interpreter: str,
    sandbox_type: str = "docker",
    task_declared_canonical_root: str = DEFAULT_CONTAINER_WORKSPACE_ROOT,
    container_workspace_path: str = DEFAULT_CONTAINER_WORKSPACE_ROOT,
    initial_cwd: str = DEFAULT_CONTAINER_WORKSPACE_ROOT,
    network_policy: dict[str, Any] | None = None,
    workspace_root_override_reason: str | None = None,
) -> dict[str, Any]:
    """Build and validate a certified-sandbox environment manifest."""
    policy = network_policy or {
        "enabled": False,
        "rationale": "default disabled for certified reproducibility",
        "allowed_endpoints": [],
        "grading_impact": "none",
        "reproducibility_note": "network disabled by default",
    }
    manifest = {
        "host_workspace_path": str(Path(host_workspace_path).resolve()),
        "container_workspace_path": container_workspace_path,
        "initial_cwd": initial_cwd,
        "task_declared_canonical_root": task_declared_canonical_root,
        "default_workspace_root": DEFAULT_CONTAINER_WORKSPACE_ROOT,
        "workspace_root_overridden": bool(workspace_root_override_reason),
        "workspace_root_override_reason": workspace_root_override_reason,
        "backend_type": backend_type,
        "sandbox_type": sandbox_type,
        "image_metadata": deepcopy(image_metadata),
        "python_interpreter_contract": python_interpreter,
        "network_policy": deepcopy(policy),
        "certification_mode": "certified",
    }
    return validate_environment_manifest(manifest)


def validate_environment_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    data = _require_mapping(manifest, "environment_manifest")
    for key in (
        "host_workspace_path",
        "container_workspace_path",
        "initial_cwd",
        "task_declared_canonical_root",
        "default_workspace_root",
        "backend_type",
        "sandbox_type",
        "python_interpreter_contract",
        "certification_mode",
    ):
        _require_non_empty_string(data.get(key), f"environment_manifest.{key}")
    _require_mapping(data.get("image_metadata"), "environment_manifest.image_metadata")
    validate_network_policy(data.get("network_policy"))
    if data["default_workspace_root"] != DEFAULT_CONTAINER_WORKSPACE_ROOT:
        raise SchemaValidationError("environment_manifest.default_workspace_root must be /app")
    if data["certification_mode"] == "certified":
        if data["sandbox_type"] == "none":
            raise SchemaValidationError("sandbox_type=none is debug_only and cannot be certified")
        if data["backend_type"] not in CERTIFIED_BACKEND_TYPES:
            raise SchemaValidationError(
                f"certified runs require backend_type in {CERTIFIED_BACKEND_TYPES}"
            )
    if data["workspace_root_overridden"] and not data.get("workspace_root_override_reason"):
        raise SchemaValidationError(
            "environment_manifest.workspace_root_override_reason is required when overridden"
        )
    if not data["workspace_root_overridden"]:
        if data["container_workspace_path"] != DEFAULT_CONTAINER_WORKSPACE_ROOT:
            raise SchemaValidationError("container_workspace_path must normalize to /app by default")
        if data["initial_cwd"] != DEFAULT_CONTAINER_WORKSPACE_ROOT:
            raise SchemaValidationError("initial_cwd must default to /app unless explicit override")
    return data


def validate_network_policy(network_policy: dict[str, Any] | None) -> dict[str, Any]:
    policy = _require_mapping(network_policy, "network_policy")
    enabled = _require_bool(policy.get("enabled"), "network_policy.enabled")
    _require_list(policy.get("allowed_endpoints", []), "network_policy.allowed_endpoints")
    if enabled:
        for key in ("rationale", "grading_impact", "reproducibility_note"):
            _require_non_empty_string(policy.get(key), f"network_policy.{key}")
    return policy


def build_certified_docker_run_command(
    *,
    host_workspace_path: str,
    image: str,
    container_name: str,
    network_policy: dict[str, Any] | None = None,
    container_workspace_path: str = DEFAULT_CONTAINER_WORKSPACE_ROOT,
) -> list[str]:
    """Construct docker run command for certified execution."""
    _require_non_empty_string(image, "image")
    _require_non_empty_string(container_name, "container_name")
    validate_network_policy(
        network_policy
        or {
            "enabled": False,
            "rationale": "default disabled for certified reproducibility",
            "allowed_endpoints": [],
            "grading_impact": "none",
            "reproducibility_note": "network disabled by default",
        }
    )
    resolved_host = str(Path(host_workspace_path).resolve())
    command = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "-w",
        container_workspace_path,
        "-v",
        f"{resolved_host}:{container_workspace_path}",
    ]
    policy = network_policy or {"enabled": False}
    if not policy.get("enabled", False):
        command.extend(["--network", "none"])
    command.extend([image, "sleep", "infinity"])
    return command


def _compute_workspace_hashes(workspace_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(workspace_root))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[rel_path] = digest
    return hashes


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


class CertifiedSmokeRunner:
    """Minimal certified smoke execution with deterministic artifact writing."""

    def __init__(self, *, host_workspace_path: str, artifacts_dir: str = DEFAULT_ARTIFACTS_DIR) -> None:
        self.host_workspace_path = Path(host_workspace_path).resolve()
        self.artifacts_dir = Path(artifacts_dir)

    def run(
        self,
        *,
        image: str,
        smoke_command: str,
        verifier_command: str,
        image_metadata: dict[str, Any],
        python_interpreter: str = "python3",
        backend_type: str = "docker",
        sandbox_type: str = "docker",
        network_policy: dict[str, Any] | None = None,
        visible_model_messages: list[str] | None = None,
    ) -> dict[str, Any]:
        _require_non_empty_string(smoke_command, "smoke_command")
        _require_non_empty_string(verifier_command, "verifier_command")
        if sandbox_type == "none":
            raise SchemaValidationError("sandbox_type=none is debug_only and cannot be certified")
        manifest = build_environment_manifest(
            host_workspace_path=str(self.host_workspace_path),
            backend_type=backend_type,
            image_metadata=image_metadata,
            python_interpreter=python_interpreter,
            sandbox_type=sandbox_type,
            network_policy=network_policy,
        )
        container_name = f"certified-smoke-{uuid.uuid4().hex[:10]}"
        run_command = build_certified_docker_run_command(
            host_workspace_path=str(self.host_workspace_path),
            image=image,
            container_name=container_name,
            network_policy=network_policy,
        )
        before_hashes = _compute_workspace_hashes(self.host_workspace_path)
        tool_io: list[dict[str, Any]] = [{"tool": "docker_run", "input": run_command}]
        failure_labels: list[str] = []
        contamination_detected = False
        smoke_exit_code: int | None = None
        verifier_exit_code: int | None = None
        smoke_output: dict[str, str] = {"stdout": "", "stderr": ""}
        verifier_output: dict[str, str] = {"stdout": "", "stderr": ""}
        subprocess.run(run_command, capture_output=True, text=True, check=True)
        try:
            smoke_result = subprocess.run(
                ["docker", "exec", container_name, "sh", "-lc", smoke_command],
                capture_output=True,
                text=True,
            )
            smoke_exit_code = smoke_result.returncode
            smoke_output = {"stdout": smoke_result.stdout, "stderr": smoke_result.stderr}
            tool_io.append(
                {
                    "tool": "docker_exec",
                    "input": smoke_command,
                    "output": smoke_output,
                    "exit_code": smoke_exit_code,
                }
            )
            verifier_result = subprocess.run(
                ["docker", "exec", container_name, "sh", "-lc", verifier_command],
                capture_output=True,
                text=True,
            )
            verifier_exit_code = verifier_result.returncode
            verifier_output = {"stdout": verifier_result.stdout, "stderr": verifier_result.stderr}
            tool_io.append(
                {
                    "tool": "docker_exec",
                    "input": verifier_command,
                    "output": verifier_output,
                    "exit_code": verifier_exit_code,
                }
            )
        finally:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                check=False,
            )
        if smoke_exit_code and smoke_exit_code != 0:
            failure_labels.append("runtime")
        if verifier_exit_code and verifier_exit_code != 0:
            failure_labels.append("verification_grading")
        certified_pass = smoke_exit_code == 0 and verifier_exit_code == 0
        after_hashes = _compute_workspace_hashes(self.host_workspace_path)
        manifest_path = self.artifacts_dir / "environment_manifest.json"
        verifier_path = self.artifacts_dir / "verifier_output.json"
        bundle_path = self.artifacts_dir / "artifact_bundle.json"
        manifest_ref = _write_json(manifest_path, manifest)
        verifier_payload = {
            "command": verifier_command,
            "exit_code": verifier_exit_code,
            "stdout": verifier_output["stdout"],
            "stderr": verifier_output["stderr"],
        }
        verifier_output_ref = _write_json(verifier_path, verifier_payload)
        bundle = {
            "manifest_ref": manifest_ref,
            "verifier_command": verifier_command,
            "verifier_output_ref": verifier_output_ref,
            "contamination_detected": contamination_detected,
            "failure_labels": failure_labels,
            "certified_pass": certified_pass,
            "cheap_replay": {
                "tool_io": tool_io,
                "cwd": DEFAULT_CONTAINER_WORKSPACE_ROOT,
                "environment_manifest_ref": manifest_ref,
                "file_hashes_or_deltas": {"before": before_hashes, "after": after_hashes},
                "verifier_grader_output": verifier_payload,
                "visible_model_messages": visible_model_messages or [],
            },
        }
        validate_artifact_bundle(bundle)
        bundle_ref = _write_json(bundle_path, bundle)
        return {
            "certified_pass": certified_pass,
            "manifest_ref": manifest_ref,
            "verifier_output_ref": verifier_output_ref,
            "artifact_bundle_ref": bundle_ref,
            "smoke_exit_code": smoke_exit_code,
            "verifier_exit_code": verifier_exit_code,
        }


def validate_artifact_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    data = _require_mapping(bundle, "artifact_bundle")
    for key in ("manifest_ref", "verifier_command", "verifier_output_ref"):
        _require_non_empty_string(data.get(key), f"artifact_bundle.{key}")
    labels = _require_list(data.get("failure_labels"), "artifact_bundle.failure_labels")
    for index, label in enumerate(labels):
        if label not in ALLOWED_FAILURE_LABELS:
            raise SchemaValidationError(
                f"artifact_bundle.failure_labels[{index}] must be one of {ALLOWED_FAILURE_LABELS}"
            )
    _require_bool(data.get("contamination_detected"), "artifact_bundle.contamination_detected")
    replay = _require_mapping(data.get("cheap_replay"), "artifact_bundle.cheap_replay")
    for field in REQUIRED_REPLAY_FIELDS:
        if field not in replay:
            raise SchemaValidationError(f"artifact_bundle.cheap_replay.{field} is required")
    return data

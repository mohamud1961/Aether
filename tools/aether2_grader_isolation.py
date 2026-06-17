"""Generic official-test mount and grader-isolation helpers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from runner.schemas import SchemaValidationError

DEFAULT_OFFICIAL_TEST_PATH = "/tests"
DEFAULT_RUNNER_TEST_PATH = "/app/tests"
DEFAULT_GRADER_TOOLCHAIN_ROOT = "/opt/aether2-grader-toolchain"
DEFAULT_GRADER_SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
DEFAULT_ENV_SNAPSHOT_KEYS = (
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "VIRTUAL_ENV",
    "VIRTUAL_ENV_PROMPT",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "LD_LIBRARY_PATH",
)
DEFAULT_ENV_STRIP_KEYS = (
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "VIRTUAL_ENV",
    "VIRTUAL_ENV_PROMPT",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "LD_LIBRARY_PATH",
    "PIP_CONFIG_FILE",
    "UV_PROJECT_ENVIRONMENT",
)


def _contract_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{path} must be a non-empty string")
    return value


def _require_absolute_path(value: Any, path: str) -> str:
    text = _require_string(value, path)
    if not Path(text).is_absolute():
        raise SchemaValidationError(f"{path} must be an absolute path")
    return text


def _snapshot_env(env: Mapping[str, str], keys: Sequence[str]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for key in keys:
        if key in env:
            snapshot[key] = str(env[key])
    return snapshot


def _sanitize_env(
    env: Mapping[str, str] | None,
    *,
    toolchain_bin: str,
    extra_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    incoming = dict(env or {})
    sanitized: dict[str, str] = {
        "PATH": f"{toolchain_bin}{os.pathsep}{DEFAULT_GRADER_SYSTEM_PATH}",
    }
    for key in DEFAULT_ENV_STRIP_KEYS:
        if key == "PATH":
            continue
        sanitized[key] = ""
    if extra_env:
        for key, value in extra_env.items():
            sanitized[key] = str(value)
    for key in ("HOME", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR"):
        if key in incoming and key not in sanitized:
            sanitized[key] = str(incoming[key])
    return sanitized


def build_official_test_mount_manifest(
    *,
    source_ref: str,
    official_path: str = DEFAULT_OFFICIAL_TEST_PATH,
    runner_path: str = DEFAULT_RUNNER_TEST_PATH,
) -> dict[str, Any]:
    """Build a dual-path mount manifest for official tests."""
    manifest = {
        "manifest_type": "aether2_official_test_mount_manifest",
        "manifest_version": 1,
        "source_ref": _require_string(source_ref, "source_ref"),
        "official_path": _require_absolute_path(official_path, "official_path"),
        "runner_path": _require_absolute_path(runner_path, "runner_path"),
        "mount_strategy": "dual_path",
        "hidden_test_isolation": {
            "model_visible": False,
            "agent_visible": False,
            "grader_visible": True,
            "content_exposed_to_model": False,
        },
        "mounts": [
            {
                "role": "official",
                "path": _require_absolute_path(official_path, "official_path"),
                "source_ref": _require_string(source_ref, "source_ref"),
                "visible_to_model": False,
                "phase": "grader",
            },
            {
                "role": "runner",
                "path": _require_absolute_path(runner_path, "runner_path"),
                "source_ref": _require_string(source_ref, "source_ref"),
                "visible_to_model": False,
                "phase": "grader",
            },
        ],
    }
    return validate_official_test_mount_manifest(manifest)


def validate_official_test_mount_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    data = _require_mapping(manifest, "official_test_mount_manifest")
    _require_string(data.get("manifest_type"), "official_test_mount_manifest.manifest_type")
    if data["manifest_type"] != "aether2_official_test_mount_manifest":
        raise SchemaValidationError(
            "official_test_mount_manifest.manifest_type must be aether2_official_test_mount_manifest"
        )
    if int(data.get("manifest_version", 0)) != 1:
        raise SchemaValidationError("official_test_mount_manifest.manifest_version must be 1")
    source_ref = _require_string(data.get("source_ref"), "official_test_mount_manifest.source_ref")
    official_path = _require_absolute_path(
        data.get("official_path"), "official_test_mount_manifest.official_path"
    )
    runner_path = _require_absolute_path(data.get("runner_path"), "official_test_mount_manifest.runner_path")
    if official_path == runner_path:
        raise SchemaValidationError("official_test_mount_manifest paths must be distinct")

    hidden = _require_mapping(data.get("hidden_test_isolation"), "official_test_mount_manifest.hidden_test_isolation")
    if _require_bool(hidden.get("model_visible"), "official_test_mount_manifest.hidden_test_isolation.model_visible"):
        raise SchemaValidationError("official_test_mount_manifest.hidden_test_isolation.model_visible must be false")
    if _require_bool(hidden.get("agent_visible"), "official_test_mount_manifest.hidden_test_isolation.agent_visible"):
        raise SchemaValidationError("official_test_mount_manifest.hidden_test_isolation.agent_visible must be false")
    if not _require_bool(hidden.get("grader_visible"), "official_test_mount_manifest.hidden_test_isolation.grader_visible"):
        raise SchemaValidationError("official_test_mount_manifest.hidden_test_isolation.grader_visible must be true")
    if _require_bool(
        hidden.get("content_exposed_to_model"),
        "official_test_mount_manifest.hidden_test_isolation.content_exposed_to_model",
    ):
        raise SchemaValidationError(
            "official_test_mount_manifest.hidden_test_isolation.content_exposed_to_model must be false"
        )

    mounts = _require_list(data.get("mounts"), "official_test_mount_manifest.mounts")
    if len(mounts) != 2:
        raise SchemaValidationError("official_test_mount_manifest.mounts must contain official and runner entries")
    by_role: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(mounts):
        mount = _require_mapping(entry, f"official_test_mount_manifest.mounts[{index}]")
        role = _require_string(mount.get("role"), f"official_test_mount_manifest.mounts[{index}].role")
        path = _require_absolute_path(mount.get("path"), f"official_test_mount_manifest.mounts[{index}].path")
        if path not in {official_path, runner_path}:
            raise SchemaValidationError(
                f"official_test_mount_manifest.mounts[{index}].path must match the official or runner path"
            )
        if path == official_path and role != "official":
            raise SchemaValidationError(
                f"official_test_mount_manifest.mounts[{index}].role must be official for {official_path}"
            )
        if path == runner_path and role != "runner":
            raise SchemaValidationError(
                f"official_test_mount_manifest.mounts[{index}].role must be runner for {runner_path}"
            )
        if _require_bool(mount.get("visible_to_model"), f"official_test_mount_manifest.mounts[{index}].visible_to_model"):
            raise SchemaValidationError(
                f"official_test_mount_manifest.mounts[{index}].visible_to_model must be false"
            )
        _require_string(mount.get("source_ref"), f"official_test_mount_manifest.mounts[{index}].source_ref")
        _require_string(mount.get("phase"), f"official_test_mount_manifest.mounts[{index}].phase")
        by_role[role] = mount
    if set(by_role) != {"official", "runner"}:
        raise SchemaValidationError("official_test_mount_manifest.mounts must include official and runner roles")
    if by_role["official"]["path"] != official_path:
        raise SchemaValidationError("official_test_mount_manifest official mount path mismatch")
    if by_role["runner"]["path"] != runner_path:
        raise SchemaValidationError("official_test_mount_manifest runner mount path mismatch")
    if by_role["official"]["source_ref"] != source_ref or by_role["runner"]["source_ref"] != source_ref:
        raise SchemaValidationError("official_test_mount_manifest mounts must share the same source_ref")
    return data


def build_grader_environment_manifest(
    *,
    agent_env: Mapping[str, str] | None = None,
    toolchain_root: str = DEFAULT_GRADER_TOOLCHAIN_ROOT,
    primary_tool: str = "pytest",
    extra_env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a grader environment manifest that does not inherit agent PATH semantics."""
    toolchain_root_path = Path(_require_absolute_path(toolchain_root, "toolchain_root"))
    toolchain_bin = toolchain_root_path / "bin"
    primary_tool_name = _require_string(primary_tool, "primary_tool")
    toolchain_paths = {
        "pytest": str(toolchain_bin / "pytest"),
        "uv": str(toolchain_bin / "uv"),
    }
    primary_tool_path = toolchain_paths.get(primary_tool_name, str(toolchain_bin / primary_tool_name))
    manifest = {
        "manifest_type": "aether2_grader_environment_manifest",
        "manifest_version": 1,
        "toolchain_root": str(toolchain_root_path),
        "toolchain_bin": str(toolchain_bin),
        "primary_tool": primary_tool_name,
        "primary_tool_path": primary_tool_path,
        "toolchain_paths": toolchain_paths,
        "agent_env_snapshot": _snapshot_env(agent_env or {}, DEFAULT_ENV_SNAPSHOT_KEYS),
        "sanitized_env": _sanitize_env(agent_env, toolchain_bin=str(toolchain_bin), extra_env=extra_env),
        "env_policy": {
            "inherit_agent_env": False,
            "inherit_agent_path": False,
            "inherit_agent_pythonpath": False,
            "use_absolute_toolchain_paths": True,
            "visible_to_model": False,
        },
    }
    return validate_grader_environment_manifest(manifest)


def validate_grader_environment_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    data = _require_mapping(manifest, "grader_environment_manifest")
    _require_string(data.get("manifest_type"), "grader_environment_manifest.manifest_type")
    if data["manifest_type"] != "aether2_grader_environment_manifest":
        raise SchemaValidationError(
            "grader_environment_manifest.manifest_type must be aether2_grader_environment_manifest"
        )
    if int(data.get("manifest_version", 0)) != 1:
        raise SchemaValidationError("grader_environment_manifest.manifest_version must be 1")
    toolchain_root = _require_absolute_path(data.get("toolchain_root"), "grader_environment_manifest.toolchain_root")
    toolchain_bin = _require_absolute_path(data.get("toolchain_bin"), "grader_environment_manifest.toolchain_bin")
    if Path(toolchain_bin).parent != Path(toolchain_root):
        raise SchemaValidationError("grader_environment_manifest.toolchain_bin must live under toolchain_root")
    primary_tool = _require_string(data.get("primary_tool"), "grader_environment_manifest.primary_tool")
    primary_tool_path = _require_absolute_path(
        data.get("primary_tool_path"), "grader_environment_manifest.primary_tool_path"
    )
    expected_primary_tool_path = str(Path(toolchain_bin) / primary_tool)
    if primary_tool_path != expected_primary_tool_path:
        raise SchemaValidationError("grader_environment_manifest.primary_tool_path must resolve from toolchain_bin")
    toolchain_paths = _require_mapping(data.get("toolchain_paths"), "grader_environment_manifest.toolchain_paths")
    for name, path in toolchain_paths.items():
        resolved = _require_absolute_path(path, f"grader_environment_manifest.toolchain_paths.{name}")
        if resolved != str(Path(toolchain_bin) / str(name)):
            raise SchemaValidationError(
                f"grader_environment_manifest.toolchain_paths.{name} must resolve from toolchain_bin"
            )
    agent_env_snapshot = _require_mapping(
        data.get("agent_env_snapshot"), "grader_environment_manifest.agent_env_snapshot"
    )
    sanitized_env = _require_mapping(data.get("sanitized_env"), "grader_environment_manifest.sanitized_env")
    if "PATH" not in sanitized_env:
        raise SchemaValidationError("grader_environment_manifest.sanitized_env.PATH is required")
    if not str(sanitized_env["PATH"]).startswith(str(toolchain_bin)):
        raise SchemaValidationError("grader_environment_manifest.sanitized_env.PATH must start with toolchain_bin")
    env_policy = _require_mapping(data.get("env_policy"), "grader_environment_manifest.env_policy")
    if _require_bool(env_policy.get("inherit_agent_env"), "grader_environment_manifest.env_policy.inherit_agent_env"):
        raise SchemaValidationError("grader_environment_manifest.env_policy.inherit_agent_env must be false")
    if _require_bool(env_policy.get("inherit_agent_path"), "grader_environment_manifest.env_policy.inherit_agent_path"):
        raise SchemaValidationError("grader_environment_manifest.env_policy.inherit_agent_path must be false")
    if _require_bool(
        env_policy.get("inherit_agent_pythonpath"),
        "grader_environment_manifest.env_policy.inherit_agent_pythonpath",
    ):
        raise SchemaValidationError(
            "grader_environment_manifest.env_policy.inherit_agent_pythonpath must be false"
        )
    if not _require_bool(
        env_policy.get("use_absolute_toolchain_paths"),
        "grader_environment_manifest.env_policy.use_absolute_toolchain_paths",
    ):
        raise SchemaValidationError(
            "grader_environment_manifest.env_policy.use_absolute_toolchain_paths must be true"
        )
    if _require_bool(env_policy.get("visible_to_model"), "grader_environment_manifest.env_policy.visible_to_model"):
        raise SchemaValidationError("grader_environment_manifest.env_policy.visible_to_model must be false")

    # Keep the agent snapshot present only as provenance. We intentionally do not
    # reuse it while resolving the grader command or PATH.
    if "PATH" in agent_env_snapshot and str(agent_env_snapshot["PATH"]) == str(sanitized_env["PATH"]):
        raise SchemaValidationError("grader_environment_manifest must distinguish agent PATH from grader PATH")
    return data


def build_grader_isolation_contract(
    *,
    official_tests_source_ref: str,
    agent_env: Mapping[str, str] | None = None,
    toolchain_root: str = DEFAULT_GRADER_TOOLCHAIN_ROOT,
    primary_tool: str = "pytest",
    extra_env: Mapping[str, str] | None = None,
    official_path: str = DEFAULT_OFFICIAL_TEST_PATH,
    runner_path: str = DEFAULT_RUNNER_TEST_PATH,
) -> dict[str, Any]:
    """Build a complete grader isolation contract with mount and environment manifests."""
    contract = {
        "contract_type": "aether2_grader_isolation_contract",
        "contract_version": 1,
        "mount_manifest": build_official_test_mount_manifest(
            source_ref=official_tests_source_ref,
            official_path=official_path,
            runner_path=runner_path,
        ),
        "grader_environment_manifest": build_grader_environment_manifest(
            agent_env=agent_env,
            toolchain_root=toolchain_root,
            primary_tool=primary_tool,
            extra_env=extra_env,
        ),
    }
    contract["contract_digest"] = _contract_digest(contract)
    return validate_grader_isolation_contract(contract)


def validate_grader_isolation_contract(contract: dict[str, Any]) -> dict[str, Any]:
    data = _require_mapping(contract, "grader_isolation_contract")
    _require_string(data.get("contract_type"), "grader_isolation_contract.contract_type")
    if data["contract_type"] != "aether2_grader_isolation_contract":
        raise SchemaValidationError(
            "grader_isolation_contract.contract_type must be aether2_grader_isolation_contract"
        )
    if int(data.get("contract_version", 0)) != 1:
        raise SchemaValidationError("grader_isolation_contract.contract_version must be 1")
    digest = data.get("contract_digest")
    if digest is not None:
        expected_digest = _contract_digest(
            {
                "contract_type": data["contract_type"],
                "contract_version": data["contract_version"],
                "mount_manifest": data.get("mount_manifest"),
                "grader_environment_manifest": data.get("grader_environment_manifest"),
            }
        )
        if digest != expected_digest:
            raise SchemaValidationError("grader_isolation_contract.contract_digest mismatch")
    mount_manifest = validate_official_test_mount_manifest(
        _require_mapping(data.get("mount_manifest"), "grader_isolation_contract.mount_manifest")
    )
    env_manifest = validate_grader_environment_manifest(
        _require_mapping(data.get("grader_environment_manifest"), "grader_isolation_contract.grader_environment_manifest")
    )
    if mount_manifest["hidden_test_isolation"]["model_visible"]:
        raise SchemaValidationError("grader_isolation_contract must preserve hidden-test isolation")
    if env_manifest["env_policy"]["inherit_agent_env"]:
        raise SchemaValidationError("grader_isolation_contract must keep grader environment hermetic")
    return data

from __future__ import annotations

import pytest

from runner.schemas import SchemaValidationError
from tools.aether2_grader_isolation import (
    DEFAULT_OFFICIAL_TEST_PATH,
    DEFAULT_RUNNER_TEST_PATH,
    build_grader_environment_manifest,
    build_grader_isolation_contract,
    build_official_test_mount_manifest,
    validate_grader_environment_manifest,
    validate_grader_isolation_contract,
    validate_official_test_mount_manifest,
)


def test_grader_isolation_contract_builds_mount_and_environment_manifests() -> None:
    contract = build_grader_isolation_contract(
        official_tests_source_ref="task-pack://official-tests",
        agent_env={"PATH": "/tmp/agent/bin", "PYTHONPATH": "/tmp/agent/site"},
    )

    assert contract["contract_type"] == "aether2_grader_isolation_contract"
    assert contract["contract_version"] == 1
    assert isinstance(contract["contract_digest"], str)
    assert len(contract["contract_digest"]) == 64
    assert validate_grader_isolation_contract(contract)["contract_version"] == 1

    mount = contract["mount_manifest"]
    env = contract["grader_environment_manifest"]
    assert validate_official_test_mount_manifest(mount)["mount_strategy"] == "dual_path"
    assert validate_grader_environment_manifest(env)["env_policy"]["use_absolute_toolchain_paths"] is True


def test_helper_distinguishes_agent_path_from_grader_toolchain_path() -> None:
    agent_env = {
        "PATH": "/tmp/agent/bin",
        "PYTHONPATH": "/tmp/agent/site",
        "HOME": "/home/agent",
    }
    env = build_grader_environment_manifest(
        agent_env=agent_env,
        toolchain_root="/opt/grader-toolchain",
    )

    assert env["agent_env_snapshot"]["PATH"] == "/tmp/agent/bin"
    assert env["sanitized_env"]["PATH"].startswith("/opt/grader-toolchain/bin")
    assert env["primary_tool_path"] == "/opt/grader-toolchain/bin/pytest"
    assert env["primary_tool_path"] != env["agent_env_snapshot"]["PATH"]
    assert "agent/site" not in env["primary_tool_path"]
    assert validate_grader_environment_manifest(env)["toolchain_root"] == "/opt/grader-toolchain"


def test_official_test_mount_manifest_represents_both_paths() -> None:
    mount = build_official_test_mount_manifest(source_ref="task-pack://official-tests")

    assert mount["official_path"] == DEFAULT_OFFICIAL_TEST_PATH
    assert mount["runner_path"] == DEFAULT_RUNNER_TEST_PATH
    assert {entry["role"] for entry in mount["mounts"]} == {"official", "runner"}
    assert {entry["path"] for entry in mount["mounts"]} == {
        DEFAULT_OFFICIAL_TEST_PATH,
        DEFAULT_RUNNER_TEST_PATH,
    }
    assert mount["hidden_test_isolation"] == {
        "model_visible": False,
        "agent_visible": False,
        "grader_visible": True,
        "content_exposed_to_model": False,
    }


def test_validation_rejects_hidden_test_exposure_and_missing_runner_path() -> None:
    bad = build_official_test_mount_manifest(source_ref="task-pack://official-tests")
    bad["hidden_test_isolation"]["model_visible"] = True

    with pytest.raises(SchemaValidationError, match="model_visible must be false"):
        validate_official_test_mount_manifest(bad)

    incomplete = build_official_test_mount_manifest(source_ref="task-pack://official-tests")
    incomplete["mounts"] = [mount for mount in incomplete["mounts"] if mount["role"] == "official"]

    with pytest.raises(SchemaValidationError, match="official and runner entries"):
        validate_official_test_mount_manifest(incomplete)

from __future__ import annotations

import json
import subprocess

import pytest

from runner.certified_sandbox import (
    CertifiedSmokeRunner,
    DEFAULT_CONTAINER_WORKSPACE_ROOT,
    build_certified_docker_run_command,
    build_environment_manifest,
    validate_artifact_bundle,
    validate_environment_manifest,
    validate_network_policy,
)
from runner.schemas import SchemaValidationError


def test_certified_manifest_smoke_passes_with_default_app_contract(tmp_path):
    manifest = build_environment_manifest(
        host_workspace_path=str(tmp_path),
        backend_type="docker",
        image_metadata={"image": "python:3.12-slim", "digest": "sha256:abc"},
        python_interpreter="python3",
    )

    assert manifest["container_workspace_path"] == DEFAULT_CONTAINER_WORKSPACE_ROOT
    assert manifest["initial_cwd"] == DEFAULT_CONTAINER_WORKSPACE_ROOT
    assert manifest["default_workspace_root"] == DEFAULT_CONTAINER_WORKSPACE_ROOT
    assert manifest["network_policy"]["enabled"] is False


def test_known_bad_manifest_fails_when_certified_uses_local_none(tmp_path):
    bad = {
        "host_workspace_path": str(tmp_path),
        "container_workspace_path": "/app",
        "initial_cwd": "/app",
        "task_declared_canonical_root": "/workspace",
        "default_workspace_root": "/app",
        "workspace_root_overridden": False,
        "workspace_root_override_reason": None,
        "backend_type": "local",
        "sandbox_type": "none",
        "image_metadata": {"image": "n/a"},
        "python_interpreter_contract": "python3",
        "network_policy": {
            "enabled": False,
            "rationale": "debug run",
            "allowed_endpoints": [],
            "grading_impact": "none",
            "reproducibility_note": "local-only",
        },
        "certification_mode": "certified",
    }
    with pytest.raises(SchemaValidationError, match="sandbox_type=none is debug_only"):
        validate_environment_manifest(bad)


def test_network_enabled_requires_rationale_fields():
    with pytest.raises(SchemaValidationError, match="network_policy.rationale"):
        validate_network_policy(
            {
                "enabled": True,
                "allowed_endpoints": ["https://example.com"],
                "grading_impact": "possible nondeterminism",
                "reproducibility_note": "pinned endpoint set",
            }
        )


def test_artifact_bundle_requires_cheap_replay_fields():
    with pytest.raises(SchemaValidationError, match="cheap_replay.visible_model_messages"):
        validate_artifact_bundle(
            {
                "manifest_ref": "artifacts/environment_manifest.json",
                "verifier_command": "python3 verifier.py",
                "verifier_output_ref": "artifacts/verifier_output.json",
                "failure_labels": ["runtime"],
                "contamination_detected": False,
                "cheap_replay": {
                    "tool_io": [],
                    "cwd": "/app",
                    "environment_manifest_ref": "artifacts/environment_manifest.json",
                    "file_hashes_or_deltas": [],
                    "verifier_grader_output": {"exit_code": 1},
                },
            }
        )


def test_docker_command_defaults_to_app_mount_and_no_network(tmp_path):
    command = build_certified_docker_run_command(
        host_workspace_path=str(tmp_path),
        image="python:3.12-slim",
        container_name="certified-smoke-test",
    )

    assert command[:3] == ["docker", "run", "-d"]
    assert ["--name", "certified-smoke-test"] == command[
        command.index("--name") : command.index("--name") + 2
    ]
    assert "-v" in command
    assert f"{tmp_path.resolve()}:/app" in command
    assert ["--network", "none"] == command[command.index("--network") : command.index("--network") + 2]


def test_certified_smoke_runner_writes_expected_artifacts_and_cleanup(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool = False):
        calls.append(cmd)
        if cmd[:3] == ["docker", "run", "-d"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="containerid", stderr="")
        if cmd[:2] == ["docker", "exec"] and cmd[-2:] == ["-lc", "echo smoke_ok"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="smoke_ok\n", stderr="")
        if cmd[:2] == ["docker", "exec"] and cmd[-2:] == ["-lc", "python3 verifier.py"]:
            return subprocess.CompletedProcess(cmd, 0, stdout='{"passed": true}\n', stderr="")
        if cmd[:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("runner.certified_sandbox.subprocess.run", fake_run)
    runner = CertifiedSmokeRunner(
        host_workspace_path=str(tmp_path),
        artifacts_dir=str(tmp_path / "artifacts"),
    )
    result = runner.run(
        image="python:3.12-slim",
        smoke_command="echo smoke_ok",
        verifier_command="python3 verifier.py",
        image_metadata={"image": "python:3.12-slim", "digest": "sha256:abc"},
    )

    docker_run = calls[0]
    assert docker_run[:3] == ["docker", "run", "-d"]
    assert ["-w", "/app"] == docker_run[docker_run.index("-w") : docker_run.index("-w") + 2]
    assert f"{tmp_path.resolve()}:/app" in docker_run
    assert ["--network", "none"] == docker_run[
        docker_run.index("--network") : docker_run.index("--network") + 2
    ]
    assert any(cmd[:2] == ["docker", "exec"] for cmd in calls)
    assert any(cmd[:3] == ["docker", "rm", "-f"] for cmd in calls)

    manifest = json.loads((tmp_path / "artifacts" / "environment_manifest.json").read_text())
    verifier = json.loads((tmp_path / "artifacts" / "verifier_output.json").read_text())
    bundle = json.loads((tmp_path / "artifacts" / "artifact_bundle.json").read_text())
    assert manifest["container_workspace_path"] == "/app"
    assert verifier["exit_code"] == 0
    assert bundle["certified_pass"] is True
    assert bundle["contamination_detected"] is False
    assert bundle["failure_labels"] == []
    assert bundle["cheap_replay"]["visible_model_messages"] == []
    assert result["certified_pass"] is True


def test_certified_smoke_known_bad_verifier_failure_labels_metadata(tmp_path, monkeypatch):
    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool = False):
        if cmd[:3] == ["docker", "run", "-d"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="containerid", stderr="")
        if cmd[:2] == ["docker", "exec"] and cmd[-2:] == ["-lc", "echo smoke_ok"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="smoke_ok\n", stderr="")
        if cmd[:2] == ["docker", "exec"] and cmd[-2:] == ["-lc", "python3 verifier.py"]:
            return subprocess.CompletedProcess(cmd, 2, stdout='{"passed": false}\n', stderr="bad")
        if cmd[:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("runner.certified_sandbox.subprocess.run", fake_run)
    runner = CertifiedSmokeRunner(
        host_workspace_path=str(tmp_path),
        artifacts_dir=str(tmp_path / "artifacts"),
    )
    result = runner.run(
        image="python:3.12-slim",
        smoke_command="echo smoke_ok",
        verifier_command="python3 verifier.py",
        image_metadata={"image": "python:3.12-slim", "digest": "sha256:abc"},
    )
    bundle = json.loads((tmp_path / "artifacts" / "artifact_bundle.json").read_text())

    assert result["certified_pass"] is False
    assert bundle["certified_pass"] is False
    assert "verification_grading" in bundle["failure_labels"]
    assert bundle["verifier_output_ref"].endswith("verifier_output.json")
    assert bundle["contamination_detected"] is False


def test_certified_smoke_rejects_debug_only_sandbox_none(tmp_path):
    runner = CertifiedSmokeRunner(
        host_workspace_path=str(tmp_path),
        artifacts_dir=str(tmp_path / "artifacts"),
    )
    with pytest.raises(SchemaValidationError, match="sandbox_type=none is debug_only"):
        runner.run(
            image="python:3.12-slim",
            smoke_command="echo smoke_ok",
            verifier_command="python3 verifier.py",
            image_metadata={"image": "python:3.12-slim"},
            sandbox_type="none",
        )

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from conftest import spawn_with_retry


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "run_aether2_g3_official.py"
    spec = importlib.util.spec_from_file_location("run_aether2_g3_official_test_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_entrypoint_help_works_from_foreign_cwd_without_pythonpath() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = spawn_with_retry(
            subprocess.run,
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "tools" / "run_aether2_g3_official.py"),
                "--help",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=tmpdir,
            env=env,
        )
    assert proc.returncode == 0
    assert "usage:" in proc.stdout.lower()
    assert "module named 'runner'" not in (proc.stdout + proc.stderr).lower()


def test_build_agent_instruction_mentions_task_and_contract() -> None:
    mod = _load_module()
    instruction = mod.build_agent_instruction("task-123", "Do the thing.")
    assert "task-123" in instruction
    assert "official verifier" in instruction.lower()
    assert "solution.sh" in instruction


def test_copy_official_tests_mirrors_compat_official_and_runner_paths(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    task_dir = tmp_path / "task"
    tests_dir = task_dir / "tests"
    tests_dir.mkdir(parents=True)
    (task_dir / "run-tests.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    logs = tmp_path / "logs"
    calls: list[list[str]] = []

    def fake_run(args, *, timeout, cwd):  # noqa: ANN001
        calls.append(list(args))
        return {"cmd": list(args), "returncode": 0, "stdout": "ok", "stderr": "", "timed_out": False, "duration_sec": 0.01}

    monkeypatch.setattr(mod, "run", fake_run)
    result = mod.copy_official_tests_into_container(container_id="cid123", task_dir=task_dir, logs=logs)

    assert result["returncode"] == 0
    assert calls[0][-1] == "cid123:/tmp/aether2-tests"
    assert calls[1][-1] == "cid123:/tests"
    assert calls[2][-1] == "cid123:/app/tests"
    assert calls[3][-1] == "cid123:/tmp/aether2-run-tests.sh"
    assert (logs / "copy_compat_tests.json").exists()
    assert (logs / "copy_official_tests.json").exists()
    assert (logs / "copy_runner_tests.json").exists()
    assert (logs / "copy_run_tests.json").exists()


def test_failure_rows_classify_environment_provider_and_launch(tmp_path: Path) -> None:
    mod = _load_module()
    env_row = mod.row_from_failure(
        task_id="task-1",
        run_dir=tmp_path / "run1",
        reason="docker_build_failed",
        started_at=0.0,
        details={"stderr": "docker build failed"},
    )
    provider_row = mod.row_from_failure(
        task_id="task-2",
        run_dir=tmp_path / "run2",
        reason="runner_exception",
        started_at=0.0,
        details={"status_code": 400, "message": "bad request"},
    )
    launch_row = mod.row_from_failure(
        task_id="task-3",
        run_dir=tmp_path / "run3",
        reason="missing official task assets",
        started_at=0.0,
        details={"missing": ["Dockerfile"]},
    )

    assert env_row["row_status"] == "invalid_environment"
    assert provider_row["row_status"] == "invalid_provider"
    assert launch_row["row_status"] == "invalid_launch"
    assert env_row["scoreable"] is False
    assert provider_row["scoreable"] is False
    assert launch_row["scoreable"] is False


def test_environment_contract_and_service_evidence_helpers_preserve_opaque_data(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    grader_contract = {
        "contract_type": "aether2_grader_isolation_contract",
        "contract_version": 1,
        "contract_digest": "f" * 64,
        "mount_manifest": {
            "manifest_type": "aether2_official_test_mount_manifest",
            "manifest_version": 1,
            "source_ref": str(tmp_path / "tests"),
            "official_path": "/tests",
            "runner_path": "/app/tests",
            "hidden_test_isolation": {
                "model_visible": False,
                "agent_visible": False,
                "grader_visible": True,
                "content_exposed_to_model": False,
            },
            "mounts": [
                {"role": "official", "path": "/tests", "source_ref": str(tmp_path / "tests"), "visible_to_model": False, "phase": "grader"},
                {"role": "runner", "path": "/app/tests", "source_ref": str(tmp_path / "tests"), "visible_to_model": False, "phase": "grader"},
            ],
        },
        "grader_environment_manifest": {
            "manifest_type": "aether2_grader_environment_manifest",
            "manifest_version": 1,
            "toolchain_root": "/opt/aether2-grader-toolchain",
            "toolchain_bin": "/opt/aether2-grader-toolchain/bin",
            "primary_tool": "pytest",
            "primary_tool_path": "/opt/aether2-grader-toolchain/bin/pytest",
            "toolchain_paths": {"pytest": "/opt/aether2-grader-toolchain/bin/pytest", "uv": "/opt/aether2-grader-toolchain/bin/uv"},
            "agent_env_snapshot": {"PATH": "/usr/bin"},
            "sanitized_env": {"PATH": "/opt/aether2-grader-toolchain/bin:/usr/bin"},
            "env_policy": {
                "inherit_agent_env": False,
                "inherit_agent_path": False,
                "inherit_agent_pythonpath": False,
                "use_absolute_toolchain_paths": True,
                "visible_to_model": False,
            },
        },
    }
    env_contract = mod._build_environment_contract(  # noqa: SLF001
        task_id="task-x",
        task_dir=tmp_path / "task",
        workspace=tmp_path / "run" / "workspace",
        artifacts=tmp_path / "run" / "artifacts",
        container_name="container-123",
        grader_isolation_contract=grader_contract,
    )
    assert env_contract["contract_digest"] == env_contract["environment_contract_digest"]
    assert env_contract["environment_contract_version"] == "aether2_env_contract_v2"
    assert env_contract["contract_version"] == "aether2_env_contract_v2"
    assert env_contract["environment_contract_ref"] == "environment_contract.json"
    assert env_contract["grader_isolation"]["contract_digest"] == grader_contract["contract_digest"]
    assert env_contract["unknowns"]["service_ports"] == []
    assert env_contract["model_start_contract"] == {
        "canonical_cwd": "/app",
        "workspace_root": "/app",
        "visible_tests": [],
        "hidden_tests_available_to_model": False,
        "completion_requires_independent_evidence": True,
    }
    assert env_contract["artifact_expectations"]["workspace_must_sync_back"] is True
    assert env_contract["artifact_expectations"]["empty_artifact_is_not_success"] is True
    assert env_contract["service_expectations"]["fresh_client_probe_required_when_task_requests_service"] is True
    assert env_contract["service_expectations"]["open_port_only_is_weak_evidence"] is True
    assert env_contract["finalization_expectations"]["task_done_requires_successful_replayed_check"] is True
    assert env_contract["finalization_expectations"]["self_authored_readback_is_weak_evidence"] is True
    assert env_contract["finalization_expectations"]["official_grader_is_final_authority"] is True

    fake_stdout = json.dumps([{"State": {"Running": True}, "NetworkSettings": {"Ports": {"8080/tcp": [{"HostPort": "8080"}]}}, "Config": {"Image": "img"}}])

    def fake_run(args, *, timeout, cwd):  # noqa: ANN001
        if args[:2] == ["docker", "port"]:
            return {"cmd": list(args), "returncode": 0, "stdout": "8080/tcp -> 0.0.0.0:8080\n", "stderr": "", "timed_out": False, "duration_sec": 0.01}
        if args[:2] == ["docker", "inspect"]:
            return {"cmd": list(args), "returncode": 0, "stdout": fake_stdout, "stderr": "", "timed_out": False, "duration_sec": 0.01}
        if args[:3] == ["docker", "exec", "cid123"]:
            if "ps -ef" in args[-1]:
                return {"cmd": list(args), "returncode": 0, "stdout": "root 1 0 0", "stderr": "", "timed_out": False, "duration_sec": 0.01}
            return {"cmd": list(args), "returncode": 0, "stdout": "LISTEN", "stderr": "", "timed_out": False, "duration_sec": 0.01}
        raise AssertionError(f"unexpected docker command: {args}")

    monkeypatch.setattr(mod, "run", fake_run)
    evidence = mod._collect_service_evidence(  # noqa: SLF001
        container_id="cid123",
        loop_result=SimpleNamespace(job_survival=True, session_survival=False),
        verification_exit_code=0,
        verification_stdout="ok",
        verification_stderr="",
        observation_window_started_at=0.0,
    )
    assert evidence["job_survival"] is True
    assert evidence["session_survival"] is False
    assert evidence["port_binding_report"]["stdout"].startswith("8080/tcp")
    assert evidence["container_inspect"]["state"] == {"Running": True}

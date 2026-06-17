from __future__ import annotations

import json
from pathlib import Path

import runner.certified_sandbox_backend_probe as probe


def test_docker_base_cmd_includes_context():
    assert probe._docker_base_cmd(None) == ["docker"]
    assert probe._docker_base_cmd("azure-dev") == ["docker", "--context", "azure-dev"]


def test_run_probe_emits_result_row_without_real_docker(monkeypatch, tmp_path):
    def fake_run(cmd, *, timeout_sec=60, cwd=None):  # type: ignore[no-untyped-def]
        if cmd[-2:] == ["context", "show"]:
            return {"cmd": cmd, "returncode": 0, "stdout": "azure-dev\n", "stderr": ""}
        if "context" in cmd:
            return {"cmd": cmd, "returncode": 0, "stdout": '{"Name":"azure-dev","Endpoints":{"docker":{"Host":"ssh://azure-vm"}}}', "stderr": ""}
        if "version" in cmd:
            return {"cmd": cmd, "returncode": 0, "stdout": '{"Client":{"Version":"25.0.0"},"Server":{"Version":"25.0.0"}}', "stderr": ""}
        if "info" in cmd:
            return {"cmd": cmd, "returncode": 0, "stdout": '{"ServerVersion":"25.0.0","OSType":"linux","Architecture":"x86_64"}', "stderr": ""}
        if "pull" in cmd:
            return {"cmd": cmd, "returncode": 0, "stdout": "pulled\n", "stderr": ""}
        if cmd[:4] == ["docker", "--context", "azure-dev", "image"]:
            return {"cmd": cmd, "returncode": 0, "stdout": '{"Id":"sha256:abc","Os":"linux","Architecture":"amd64"}', "stderr": ""}
        if "create" in cmd:
            return {"cmd": cmd, "returncode": 0, "stdout": "container123\n", "stderr": ""}
        if "start" in cmd:
            return {"cmd": cmd, "returncode": 0, "stdout": "container123\n", "stderr": ""}
        if "mkdir" in cmd:
            assert "/workspace/task" in cmd
            return {"cmd": cmd, "returncode": 0, "stdout": "", "stderr": ""}
        if "cp" in cmd and str(cmd[-1]).endswith("/probe_input.txt"):
            assert "container123:/workspace/task/probe_input.txt" in cmd
            return {"cmd": cmd, "returncode": 0, "stdout": "", "stderr": ""}
        if "python3" in cmd:
            token_arg = next(part for part in cmd if str(part).startswith("PROBE_RUN_TOKEN="))
            token = token_arg.split("=", 1)[1]
            report = {
                "cwd": "/workspace/task",
                "python3_available": True,
                "python3_path": "/usr/local/bin/python3",
                "python_version": "3.11.9",
                "bare_python_path": "/usr/local/bin/python",
                "bare_python_version": "Python 3.11.9",
                "platform": "Linux",
                "run_token": token,
                "input_exists": True,
            }
            return {"cmd": cmd, "returncode": 0, "stdout": json.dumps(report), "stderr": ""}
        if "sh" in cmd:
            token_arg = next(part for part in cmd if str(part).startswith("PROBE_RUN_TOKEN="))
            token = token_arg.split("=", 1)[1]
            return {"cmd": cmd, "returncode": 0, "stdout": f"verifier_probe_ok {token}\n", "stderr": ""}
        if "cp" in cmd and cmd[-2] == "container123:/workspace/task/.":
            workspace = Path(cmd[-1])
            token = next(
                part.split("=", 1)[1]
                for prior in calls
                for part in prior
                if str(part).startswith("PROBE_RUN_TOKEN=")
            )
            (workspace / "probe_container_report.json").write_text(json.dumps({"run_token": token}), encoding="utf-8")
            (workspace / "artifact_sync_check.txt").write_text(token + "\n", encoding="utf-8")
            (workspace / "verifier_visible.log").write_text(f"verifier_probe_ok {token}\n", encoding="utf-8")
            return {"cmd": cmd, "returncode": 0, "stdout": "", "stderr": ""}
        if "rm" in cmd:
            return {"cmd": cmd, "returncode": 0, "stdout": "", "stderr": ""}
        raise AssertionError(f"unexpected command: {cmd}")

    calls = []
    def recording_run(cmd, *, timeout_sec=60, cwd=None):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        return fake_run(cmd, timeout_sec=timeout_sec, cwd=cwd)

    monkeypatch.setattr(probe, "_run", recording_run)

    result = probe.run_probe(
        output_dir=tmp_path,
        docker_context="azure-dev",
        image="python:3.11-slim",
        require_backend="remote_docker",
        require_context="azure-dev",
        require_endpoint_regex="azure-vm",
    )
    result_path = tmp_path / probe.RESULT_ROW_NAME
    on_disk = json.loads(result_path.read_text(encoding="utf-8"))

    assert result["status"] == "pass"
    assert result["certified_eligible"] is True
    assert result["certification_claimed"] is False
    assert result["backend_type"] == "remote_docker"
    assert result["environment_manifest_hash"]
    assert result["environment_manifest"]["workspace"]["transfer_mode"] == "docker_cp"
    assert result["checks"]["required_backend"] is True
    assert result["checks"]["required_context"] is True
    assert result["checks"]["required_endpoint"] is True
    assert result["invalid_reason_codes"] == []
    assert result["workspace"]["canonical_path"] == "/workspace/task"
    assert result["workspace"]["cwd_matches"] is True
    assert result["python"]["python3_path"] == "/usr/local/bin/python3"
    assert result["python"]["bare_python_path"] == "/usr/local/bin/python"
    assert result["artifact"]["sha256"]
    assert result["checks"]["cwd_mapping"] is True
    assert result["checks"]["python3_available"] is True
    assert result["checks"]["artifact_sync_back"] is True
    assert on_disk["docker_context"] == "azure-dev"
    assert on_disk["status"] == "pass"
    flattened = [" ".join(command) for command in calls]
    assert not any(" -v " in command for command in flattened)
    assert any(" cp " in command for command in flattened)


def test_backend_type_infers_local_and_remote():
    assert probe._backend_type({"Endpoints": {"docker": {"Host": "unix:///var/run/docker.sock"}}}) == "local_docker"
    assert probe._backend_type({"Endpoints": {"docker": {"Host": "npipe:////./pipe/docker_engine"}}}) == "local_docker"
    assert probe._backend_type({"Endpoints": {"docker": {"Host": "ssh://azure-vm"}}}) == "remote_docker"
    assert probe._backend_type({"Endpoints": {"docker": {"Host": "tcp://example:2376"}}}) == "remote_docker"


def test_failed_linux_and_token_checks_emit_reason_codes(tmp_path):
    workspace = tmp_path
    (workspace / "artifact_sync_check.txt").write_text("old-token\n", encoding="utf-8")
    (workspace / "verifier_visible.log").write_text("verifier_probe_ok old-token\n", encoding="utf-8")
    steps = {
        "docker_context_show": {"returncode": 0, "stdout": "", "stderr": ""},
        "docker_context": {"returncode": 0, "stdout": "", "stderr": ""},
        "docker_version": {"returncode": 0, "stdout": "", "stderr": ""},
        "docker_info": {"returncode": 0, "stdout": "", "stderr": ""},
        "image_metadata": {"returncode": 0, "stdout": "", "stderr": ""},
        "image_pull": {"returncode": 0, "stdout": "", "stderr": ""},
        "container_start": {"returncode": 0, "stdout": "", "stderr": ""},
        "workspace_create": {"returncode": 0, "stdout": "", "stderr": ""},
        "input_sync_in": {"returncode": 0, "stdout": "", "stderr": ""},
        "container_probe": {
            "returncode": 0,
            "stdout": json.dumps({"cwd": "/workspace/task", "python3_available": True, "run_token": "new-token"}),
            "stderr": "",
        },
        "verifier_probe": {"returncode": 0, "stdout": "verifier_probe_ok old-token\n", "stderr": ""},
        "artifact_sync_back": {"returncode": 0, "stdout": "", "stderr": ""},
    }
    checks = probe._evaluate_checks(
        steps,
        workspace,
        run_token="new-token",
        backend_type="remote_docker",
        docker_info={"OSType": "darwin"},
        image_metadata={"Os": "linux"},
        required_checks={},
    )
    reasons = probe._reason_codes(checks)

    assert checks["linux_docker_server"] is False
    assert checks["run_token_fresh"] is False
    assert "linux_docker_server_failed" in reasons
    assert "run_token_fresh_failed" in reasons


def test_unknown_backend_type_is_not_eligible(tmp_path):
    steps = {
        "docker_context_show": {"returncode": 0, "stdout": "", "stderr": ""},
        "docker_context": {"returncode": 0, "stdout": "", "stderr": ""},
        "docker_version": {"returncode": 0, "stdout": "", "stderr": ""},
        "docker_info": {"returncode": 0, "stdout": "", "stderr": ""},
        "image_metadata": {"returncode": 0, "stdout": "", "stderr": ""},
        "image_pull": {"returncode": 0, "stdout": "", "stderr": ""},
        "container_start": {"returncode": 0, "stdout": "", "stderr": ""},
        "workspace_create": {"returncode": 0, "stdout": "", "stderr": ""},
        "input_sync_in": {"returncode": 0, "stdout": "", "stderr": ""},
        "container_probe": {
            "returncode": 0,
            "stdout": json.dumps({"cwd": "/workspace/task", "python3_available": True, "run_token": "token"}),
            "stderr": "",
        },
        "verifier_probe": {"returncode": 0, "stdout": "verifier_probe_ok token\n", "stderr": ""},
        "artifact_sync_back": {"returncode": 0, "stdout": "", "stderr": ""},
    }
    (tmp_path / "artifact_sync_check.txt").write_text("token\n", encoding="utf-8")
    (tmp_path / "verifier_visible.log").write_text("verifier_probe_ok token\n", encoding="utf-8")

    checks = probe._evaluate_checks(
        steps,
        tmp_path,
        run_token="token",
        backend_type="unknown_docker",
        docker_info={"OSType": "linux"},
        image_metadata={"Os": "linux"},
        required_checks={},
    )

    assert checks["backend_identified"] is False
    assert "backend_identified_failed" in probe._reason_codes(checks)


def test_required_remote_backend_gates_make_local_pass_ineligible(tmp_path):
    checks = probe._required_gate_checks(
        backend_type="local_docker",
        context_name="desktop-linux",
        docker_endpoint="unix:///var/run/docker.sock",
        require_backend="remote_docker",
        require_context="azure-dev",
        require_endpoint_regex="azure",
    )

    assert checks == {
        "required_backend": False,
        "required_context": False,
        "required_endpoint": False,
    }
    reasons = probe._reason_codes(checks)
    assert "required_backend_failed" in reasons
    assert "required_context_failed" in reasons
    assert "required_endpoint_failed" in reasons

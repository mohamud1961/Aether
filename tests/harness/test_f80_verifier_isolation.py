from __future__ import annotations

import subprocess

from aether.runners import docker_exec_executor as docker_mod
from aether.runners.docker_exec_executor import DockerExecExecutor


def _executor() -> DockerExecExecutor:
    executor = object.__new__(DockerExecExecutor)
    executor._container_id = "parent-container-123"
    executor._default_timeout_s = 30
    return executor


def _completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


class _DockerScript:
    def __init__(self, *, command_returncode: int = 0, timeout: bool = False, cleanup_inspect_error: bool = False):
        self.command_returncode = command_returncode
        self.timeout = timeout
        self.cleanup_inspect_error = cleanup_inspect_error
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args, **kwargs):
        row = tuple(str(x) for x in args)
        self.calls.append(row)
        if row[:2] == ("docker", "commit"):
            return _completed(args, 0, "sha256:current-rootfs-snapshot\n", "")
        if row[:2] == ("docker", "run"):
            if self.timeout:
                raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 1), output=b"partial-out", stderr=b"partial-err")
            return _completed(args, self.command_returncode, "command-out", "command-err")
        if row[:3] == ("docker", "rm", "-f"):
            return _completed(args, 0, "removed", "")
        if row[:2] == ("docker", "inspect"):
            if self.cleanup_inspect_error:
                raise OSError("inspect transport failed")
            return _completed(args, 1, "", "not found")
        if row[:3] == ("docker", "image", "rm"):
            return _completed(args, 0, "removed image", "")
        if row[:3] == ("docker", "image", "inspect"):
            return _completed(args, 1, "", "not found")
        raise AssertionError(f"unexpected docker call: {row}")


def _run(monkeypatch, script: _DockerScript):
    monkeypatch.setattr(docker_mod.subprocess, "run", script)
    result = _executor().run_independent_verifier_command(
        "python3 verify.py",
        workspace_root="/app.verifier_overlay_test.command_one",
        timeout_s=12,
    )
    return result, script.calls


def test_f80_docker_sibling_success_uses_current_snapshot_network_none_and_cleans(monkeypatch) -> None:
    result, calls = _run(monkeypatch, _DockerScript())
    assert not result.get("error"), result
    assert result["result"].exit_code == 0
    metadata = result["metadata"]
    assert metadata["independent_isolation_verified"] is True
    assert metadata["isolation_cleanup_verified"] is True
    assert metadata["sibling_container_removed"] is True
    assert metadata["snapshot_image_removed"] is True
    commit = next(row for row in calls if row[:2] == ("docker", "commit"))
    assert commit[2:4] == ("--pause=true", "parent-container-123")
    run = next(row for row in calls if row[:2] == ("docker", "run"))
    assert "--network" in run and run[run.index("--network") + 1] == "none"
    assert "/app.verifier_overlay_test.command_one" in run
    assert not any(row[:2] == ("docker", "exec") for row in calls)


def test_f80_docker_sibling_nonzero_is_valid_observed_outcome_and_still_cleans(monkeypatch) -> None:
    result, _calls = _run(monkeypatch, _DockerScript(command_returncode=7))
    assert not result.get("error"), result
    assert result["result"].exit_code == 7
    assert result["result"].success is False
    assert result["metadata"]["independent_isolation_verified"] is True
    assert result["metadata"]["isolation_cleanup_verified"] is True


def test_f80_docker_sibling_timeout_is_observed_and_still_cleans(monkeypatch) -> None:
    result, _calls = _run(monkeypatch, _DockerScript(timeout=True))
    assert not result.get("error"), result
    assert result["result"].exit_code == 124
    assert result["result"].timed_out is True
    assert "partial-out" in result["result"].stdout
    assert result["metadata"]["independent_isolation_verified"] is True
    assert result["metadata"]["isolation_cleanup_verified"] is True


def test_f80_docker_cleanup_transport_failure_fails_closed(monkeypatch) -> None:
    result, _calls = _run(monkeypatch, _DockerScript(cleanup_inspect_error=True))
    assert result["error"] == "verifier_independent_isolation_docker_cleanup_failed"
    assert result["metadata"]["independent_isolation_verified"] is True
    assert result["metadata"]["isolation_cleanup_verified"] is False
    assert result["metadata"]["sibling_container_removed"] is False
    assert "inspect transport failed" in result["metadata"]["sibling_inspect_error"]

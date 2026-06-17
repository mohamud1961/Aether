from __future__ import annotations

import errno
from subprocess import CompletedProcess, TimeoutExpired
import sys

from runner.aether2.envelope import build_envelope
from runner.aether2 import executor as executor_module
from runner.aether2.executor import ContainerBackend, ContainerExecutor, RawResult


def test_run_returns_raw_result_and_consumes_into_envelope(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    subdir = workspace_root / "sub"
    subdir.mkdir()

    def fake_run(args, *, cwd, capture_output, text, encoding, errors, timeout, check, env):
        assert args == ["/bin/sh", "-lc", "pwd"]
        assert cwd == str(subdir.resolve())
        assert capture_output is True
        assert text is True
        assert timeout == 5.0
        return CompletedProcess(args=args, returncode=0, stdout=f"{subdir.resolve()}\n", stderr="")

    monkeypatch.setattr(executor_module.subprocess, "run", fake_run)
    executor = ContainerExecutor(workspace_root=workspace_root)
    result = executor.run("pwd", timeout_sec=5, cwd="sub")

    assert isinstance(result, RawResult)
    assert result.tool == "run_command"
    assert result.exit_code == 0
    assert result.cwd == str(subdir.resolve())
    assert result.stdout == f"{subdir.resolve()}\n"
    assert result.stderr == ""
    assert result.timed_out is False
    assert result.boundary_violation is False

    envelope = build_envelope(result, raw_log_dir=tmp_path / "logs")
    assert envelope.tool == "run_command"
    assert envelope.cwd == result.cwd
    assert envelope.stdout_head == result.stdout
    assert envelope.stderr_head == ""
    assert envelope.raw_log_path


def test_run_enforces_timeout_explicitly(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    def fake_run(args, *, cwd, capture_output, text, encoding, errors, timeout, check, env):
        raise TimeoutExpired(cmd=args, timeout=timeout)

    monkeypatch.setattr(executor_module.subprocess, "run", fake_run)
    executor = ContainerExecutor(workspace_root=workspace_root)
    result = executor.run(
        f"{sys.executable} -c \"import time; time.sleep(5)\"",
        timeout_sec=1,
        cwd=workspace_root,
    )

    assert result.timed_out is True
    assert result.exit_code == 124
    assert result.error is not None
    assert result.error.kind == "timeout"
    assert result.duration_sec >= 0.0
    assert result.stdout == ""
    assert result.stderr == ""


def test_run_retries_eagain_spawn_failure_then_succeeds(tmp_path, monkeypatch):
    """V2: the production executor must retry BlockingIOError/OSError EAGAIN
    spawn failures (bounded, exponential backoff) before reporting a truthful
    spawn_failed error -- never fake success, but don't surface transient
    host-load EAGAINs as command failures either."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    calls = {"count": 0}
    sleeps: list[float] = []

    def fake_run(args, *, cwd, capture_output, text, encoding, errors, timeout, check, env):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")
        return CompletedProcess(args=args, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(executor_module.subprocess, "run", fake_run)
    monkeypatch.setattr(executor_module.time, "sleep", lambda secs: sleeps.append(secs))

    executor = ContainerExecutor(workspace_root=workspace_root)
    result = executor.run("echo ok", timeout_sec=5, cwd=None)

    assert result.exit_code == 0
    assert result.stdout == "ok\n"
    assert result.error is None
    assert calls["count"] == 3
    assert len(sleeps) == 2


def test_run_reports_truthful_spawn_failed_after_exhausting_eagain_retries(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    def fake_run(args, *, cwd, capture_output, text, encoding, errors, timeout, check, env):
        raise BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")

    monkeypatch.setattr(executor_module.subprocess, "run", fake_run)
    monkeypatch.setattr(executor_module.time, "sleep", lambda secs: None)

    executor = ContainerExecutor(workspace_root=workspace_root)
    result = executor.run("echo ok", timeout_sec=5, cwd=None)

    assert result.exit_code == 71
    assert result.error is not None
    assert result.error.kind == "spawn_failed"


def test_run_blocks_host_only_path_outside_workspace_root(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    host_secret = tmp_path / "host_secret.txt"
    host_secret.write_text("secret\n", encoding="utf-8")

    executor = ContainerExecutor(workspace_root=workspace_root)
    result = executor.run(f"cat {host_secret}", timeout_sec=5, cwd=workspace_root)

    assert result.exit_code == 126
    assert result.boundary_violation is True
    assert result.timed_out is False
    assert result.error is not None
    assert result.error.kind == "workspace_boundary_violation"
    assert result.error.reason_code == "workspace_boundary_violation"
    assert "secret" not in result.stdout
    assert "secret" not in result.stderr
    assert str(host_secret) not in result.error.message
    assert result.stdout == ""
    assert result.stderr == ""


def test_multiline_run_command_uses_literal_script_and_preserves_exit_status(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    executor = ContainerExecutor(workspace_root=workspace_root)
    command = "\n".join(
        [
            "printf 'alpha beta\\n'",
            "printf '%s\\n' 'line two'",
            "exit 7",
        ]
    )

    result = executor.run(command, timeout_sec=5, cwd=workspace_root)

    assert result.exit_code == 7
    assert result.stdout == "alpha beta\nline two\n"
    assert result.error is not None
    assert result.error.reason_code == "nonzero_exit"
    scripts = sorted((workspace_root / ".aether2" / "foreground_commands").glob("cmd-*.sh"))
    assert scripts
    assert any(path.read_text(encoding="utf-8") == command for path in scripts)


def test_multiline_run_command_uses_container_script_path_for_docker_backend(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    nested = workspace_root / "nested"
    nested.mkdir()
    calls = []

    def fake_run(args, *, cwd, capture_output, text, encoding, errors, timeout, check, env):
        calls.append(list(args))
        return CompletedProcess(args=args, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(executor_module.subprocess, "run", fake_run)
    executor = ContainerExecutor(
        workspace_root=workspace_root,
        backend=ContainerBackend(kind="docker", container_id="cid-123", container_workspace_root="/app"),
    )

    result = executor.run("printf 'one\\n'\nprintf 'two\\n'\n", timeout_sec=5, cwd="nested")

    assert result.exit_code == 0
    assert result.stdout == "ok\n"
    assert calls
    assert calls[0][:6] == ["docker", "exec", "-w", "/app/nested", "cid-123", "sh"]
    assert "-lc" not in calls[0]
    assert calls[0][-1].startswith("/app/.aether2/foreground_commands/cmd-")
    host_scripts = sorted((workspace_root / ".aether2" / "foreground_commands").glob("cmd-*.sh"))
    assert host_scripts
    assert any(path.read_text(encoding="utf-8") == "printf 'one\\n'\nprintf 'two\\n'\n" for path in host_scripts)


def test_executor_maps_container_workspace_paths_back_to_host_workspace(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    nested = workspace_root / "nested"
    nested.mkdir()

    executor = ContainerExecutor(
        workspace_root=workspace_root,
        backend=ContainerBackend(kind="docker", container_workspace_root="/app"),
    )

    assert executor.resolve_workspace_path("/app/nested") == nested.resolve()
    assert executor.to_container_path(nested) == "/app/nested"

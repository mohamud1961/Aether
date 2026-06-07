import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from runner.aether2 import jobs as jobs_module
from runner.aether2.jobs import JobRegistry

from conftest import spawn_with_retry


def test_job_registry_persists_and_reports_real_exit_code(tmp_path: Path, retrying_subprocess) -> None:
    retrying_subprocess(jobs_module)
    registry = JobRegistry(tmp_path / ".aether2" / "state")
    job_id = registry.start("printf 'hello\\n'; exit 7", job_id="job-exit", cwd=tmp_path)

    status = _wait_for_job(registry, job_id)

    assert status.job_id == "job-exit"
    assert status.alive is False
    assert status.exit_code == 7
    assert "hello" in status.tail
    reread = JobRegistry(tmp_path / ".aether2" / "state").status(job_id)
    assert reread.exit_code == 7
    assert reread.registry_path.endswith("meta.json")


def test_job_registry_missing_job_fails_explicitly(tmp_path: Path) -> None:
    registry = JobRegistry(tmp_path / ".aether2" / "state")
    with pytest.raises(KeyError, match="unknown job"):
        registry.status("missing")


def test_job_tail_is_bounded(tmp_path: Path, retrying_subprocess) -> None:
    retrying_subprocess(jobs_module)
    registry = JobRegistry(tmp_path / ".aether2" / "state")
    payload = "x" * 5000
    job_id = registry.start(f"python3 - <<'PY'\nprint({payload!r})\nPY", job_id="job-tail", cwd=tmp_path)

    status = _wait_for_job(registry, job_id)

    assert len(status.tail) <= 2048
    assert status.log_path.endswith("job.log")


def test_multiline_job_uses_literal_command_script_and_preserves_exit_status(tmp_path: Path, retrying_subprocess) -> None:
    retrying_subprocess(jobs_module)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry = JobRegistry(workspace / ".aether2" / "state")
    command = "\n".join(
        [
            "printf 'hello world\\n'",
            "printf '%s\\n' 'line two'",
            "exit 9",
        ]
    )

    job_id = registry.start(command, job_id="job-multiline", cwd=workspace)
    status = _wait_for_job(registry, job_id)
    job_dir = workspace / ".aether2" / "state" / "jobs" / job_id
    wrapper = (job_dir / "run.sh").read_text(encoding="utf-8")

    assert status.exit_code == 9
    assert "hello world" in status.tail
    assert "line two" in status.tail
    assert (job_dir / "command.sh").read_text(encoding="utf-8") == command
    assert "eval " not in wrapper
    assert str(job_dir / "command.sh") in wrapper


def test_job_survives_launcher_process_exit(tmp_path: Path, retrying_subprocess) -> None:
    retrying_subprocess(jobs_module)
    state_dir = tmp_path / ".aether2" / "state"
    helper = tmp_path / "launch_job.py"
    helper.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "from runner.aether2.jobs import JobRegistry",
                f"state_dir = Path({str(state_dir)!r})",
                f"workspace = Path({str(tmp_path)!r})",
                "registry = JobRegistry(state_dir)",
                "job_id = registry.start('python3 -c \"import time; time.sleep(2)\"', job_id='survivor', cwd=workspace)",
                "print(job_id)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env = dict(**{"PYTHONPATH": str(Path.cwd())}, **dict())
    proc = spawn_with_retry(
        subprocess.run,
        [sys.executable, str(helper)],
        check=True,
        text=True,
        capture_output=True,
        cwd=str(Path.cwd()),
        env=env,
    )
    job_id = proc.stdout.strip()
    registry = JobRegistry(state_dir)
    status = registry.status(job_id)
    assert status.alive is True
    os_kill(status.pid)
    finished = _wait_for_job(registry, job_id)
    assert finished.exit_code is not None


def _wait_for_job(registry: JobRegistry, job_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    latest = registry.status(job_id)
    while time.time() < deadline:
        latest = registry.status(job_id)
        if not latest.alive and latest.exit_code is not None:
            return latest
        time.sleep(0.05)
    raise AssertionError(json.dumps(latest.__dict__, indent=2, sort_keys=True))


def test_job_registry_routes_through_docker_backend_not_host_subprocess(tmp_path: Path, monkeypatch) -> None:
    """C1: when backend.kind == 'docker', jobs are launched via docker exec into
    the container, not via host subprocess.Popen."""
    from runner.aether2.executor import ContainerBackend

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        assert cmd[:3] == ["docker", "exec", "fake-container-id"]
        return subprocess.CompletedProcess(cmd, 0, stdout="4242\n", stderr="")

    def fake_popen(*args, **kwargs):
        raise AssertionError("host subprocess.Popen must not be used for the docker backend")

    monkeypatch.setattr(jobs_module.subprocess, "run", fake_run)
    monkeypatch.setattr(jobs_module.subprocess, "Popen", fake_popen)

    backend = ContainerBackend(kind="docker", container_id="fake-container-id", container_workspace_root="/app")
    state_dir = tmp_path / ".aether2" / "state"

    def container_path_fn(path):
        return f"/app/.aether2/state/jobs/{Path(path).parent.name}/run.sh"

    registry = JobRegistry(state_dir, backend=backend, container_path_fn=container_path_fn)
    job_id = registry.start("echo hi", job_id="job-docker", cwd=tmp_path)

    assert job_id == "job-docker"
    assert calls, "expected at least one docker exec call"
    assert calls[0][:3] == ["docker", "exec", "fake-container-id"]
    assert "/app/.aether2/state/jobs/job-docker/run.sh" in calls[0][-1]

    status = registry.status(job_id)
    assert status.pid == 4242
    # status() liveness check must also go through docker exec, not os.kill
    assert any(call[:4] == ["docker", "exec", "fake-container-id", "kill"] for call in calls)


def os_kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_job_registry_defaults_cwd_to_workspace_root_not_aether2(tmp_path):
    from runner.aether2.jobs import JobRegistry

    workspace = tmp_path / "workspace"
    state_dir = workspace / ".aether2" / "state"
    state_dir.mkdir(parents=True)

    registry = JobRegistry(state_dir)
    job_id = registry.start("pwd > default_cwd.txt", job_id="cwd-default")
    status = _wait_for_job(registry, job_id)

    assert status.cwd == str(workspace.resolve())
    assert status.exit_code == 0
    assert (workspace / "default_cwd.txt").exists()
    assert not (workspace / ".aether2" / "default_cwd.txt").exists()


def test_docker_job_wrapper_uses_container_namespace_paths(tmp_path, monkeypatch):
    from subprocess import CompletedProcess
    from runner.aether2.executor import ContainerBackend
    from runner.aether2.jobs import JobRegistry

    workspace = tmp_path / "workspace"
    state_dir = workspace / ".aether2" / "state"
    state_dir.mkdir(parents=True)

    def to_container_path(path):
        resolved = path.resolve()
        rel = resolved.relative_to(workspace.resolve()).as_posix()
        return "/app" if rel == "." else f"/app/{rel}"

    calls = []

    def fake_run(cmd, capture_output, text, check=False):
        calls.append(list(cmd))
        return CompletedProcess(cmd, 0, stdout="4321\n", stderr="")

    monkeypatch.setattr("runner.aether2.jobs.subprocess.run", fake_run)

    registry = JobRegistry(
        state_dir,
        backend=ContainerBackend(kind="docker", container_id="cid-123", container_workspace_root="/app"),
        container_path_fn=to_container_path,
    )

    job_id = registry.start("printf ok", job_id="docker-cwd", cwd="/app")
    job_dir = state_dir / "jobs" / job_id
    wrapper = (job_dir / "run.sh").read_text(encoding="utf-8")
    command_script = (job_dir / "command.sh").read_text(encoding="utf-8")
    meta = __import__("json").loads((job_dir / "meta.json").read_text(encoding="utf-8"))

    assert 'cd "/app"' in wrapper
    assert '"/app/.aether2/state/jobs/docker-cwd/command.sh"' in wrapper
    assert '"/app/.aether2/state/jobs/docker-cwd/job.log"' in wrapper
    assert '"/app/.aether2/state/jobs/docker-cwd/exit_code"' in wrapper
    assert str(workspace / ".aether2") not in wrapper
    assert "eval " not in wrapper
    assert command_script == "printf ok"
    assert meta["cwd"] == str(workspace.resolve())
    assert calls
    assert calls[0][:4] == ["docker", "exec", "cid-123", "sh"]
    assert "/app/.aether2/state/jobs/docker-cwd/run.sh" in calls[0][-1]

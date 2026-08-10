"""Tests for DockerExecExecutor against a real Docker container.

Requires Docker to be available.  Tests are skipped cleanly if
``docker info`` fails.

Also includes lightweight unit tests (no Docker required) for
module-level constants and bootstrap behavior.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

# Skip the entire module if Docker is not available.
_docker_available = False
try:
    _check = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    _docker_available = _check.returncode == 0
except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
    pass

pytestmark = pytest.mark.skipif(
    not _docker_available,
    reason="Docker daemon not available",
)

from aether.runners.docker_runner import DockerExecExecutor, run_tbench_task


@pytest.fixture()
def docker_env():
    """Start an Alpine container with a bind-mounted temp workspace.

    Yields ``(container_id, workspace_dir)`` and tears down on exit.
    """
    # Docker Desktop does not always share the platform tempdir on macOS
    # (often /var/folders/...), while /tmp is part of the benchmark-native
    # workspace contract exercised by the isolation smoke.
    workspace = tempfile.mkdtemp(prefix="test_docker_runner_", dir="/tmp")
    container_id: str | None = None
    try:
        start = subprocess.run(
            [
                "docker", "run", "-d", "--init",
                "-v", f"{workspace}:/app",
                "-w", "/app",
                "debian:stable-slim",
                "sleep", "infinity",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert start.returncode == 0, f"docker run failed: {start.stderr}"
        container_id = start.stdout.strip()
        yield container_id, workspace
    finally:
        if container_id:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True, text=True, timeout=30,
            )
        if os.path.isdir(workspace):
            import shutil
            shutil.rmtree(workspace, ignore_errors=True)


class TestDockerExecExecutor:
    """Integration tests for DockerExecExecutor with a real Alpine container."""

    def test_write_and_read_file(self, docker_env: tuple[str, str]) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)

        executor.write_file("hello.txt", "hello world\n")
        content = executor.read_file("hello.txt")
        assert content == "hello world\n"

    def test_exists(self, docker_env: tuple[str, str]) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)

        assert not executor.exists("nope.txt")
        executor.write_file("yep.txt", "yes")
        assert executor.exists("yep.txt")

    def test_run_command_echo(self, docker_env: tuple[str, str]) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)

        result = executor.run_command("echo hi", timeout_s=10)
        assert result.exit_code == 0
        assert "hi" in result.stdout

    def test_run_command_failing(self, docker_env: tuple[str, str]) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)

        result = executor.run_command("exit 42", timeout_s=10)
        assert result.exit_code == 42

    def test_run_command_produces_artifacts(self, docker_env: tuple[str, str]) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)

        result = executor.run_command("echo artifact > /app/new_file.txt", timeout_s=10)
        assert result.exit_code == 0
        assert "new_file.txt" in result.produced_artifacts

        # Verify the file is visible on the host.
        host_file = Path(workspace) / "new_file.txt"
        assert host_file.exists()
        assert "artifact" in host_file.read_text()

    def test_glob(self, docker_env: tuple[str, str]) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)

        executor.write_file("a.py", "# a")
        executor.write_file("b.py", "# b")
        executor.write_file("c.txt", "c")

        matches = executor.glob("*.py")
        assert "a.py" in matches
        assert "b.py" in matches
        assert "c.txt" not in matches

    def test_persistent_terminal_is_real_tty_and_cursor_exact(self, docker_env: tuple[str, str], tmp_path: Path) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)
        command = (
            "if [ -t 0 ] && [ -t 1 ]; then echo TTY=1; else echo TTY=0; fi; "
            "echo QUESTION; read answer; echo ANSWER=$answer; "
            "printf 'artifact=%s\\n' \"$answer\" > /app/terminal-result.txt"
        )
        handle = executor.start_terminal_session("challenge", command, cwd="/app")
        assert handle.live
        assert handle.session_id.startswith("terminal:")
        assert handle.pid is not None
        assert handle.start_time_ticks.isdigit()
        assert len(handle.process_generation) == 24

        first = executor.terminal_read(handle.session_id, max_bytes=4096, wait_ms=1500)
        assert first.process_generation == handle.process_generation
        assert "TTY=1" in first.output
        assert "QUESTION" in first.output
        assert first.cursor == first.bytes_read
        assert first.live

        sent = executor.terminal_send(handle.session_id, "hello", append_newline=True)
        assert sent.bytes_sent == 6
        assert sent.process_generation == handle.process_generation

        second = executor.terminal_read(handle.session_id, max_bytes=4096, wait_ms=1500)
        assert second.process_generation == handle.process_generation
        assert "ANSWER=hello" in second.output
        # The child may create the artifact before terminal_send's immediate
        # post-action snapshot or during terminal_read's wait. The mutation
        # must be observed once across those consecutive terminal receipts; it
        # is intentionally not assigned by timing heuristics to one of them.
        created = set(sent.state_delta.get("created_paths", ())) | set(
            second.state_delta.get("created_paths", ())
        )
        assert "terminal-result.txt" in created

        waited = executor.terminal_wait(handle.session_id, timeout_s=3)
        assert not waited.live
        assert waited.process_generation == handle.process_generation

        empty = executor.terminal_read(handle.session_id, max_bytes=4096, wait_ms=0)
        assert empty.bytes_read == 0
        assert empty.output == ""
        assert empty.cursor == second.cursor

        assert Path(workspace, "terminal-result.txt").read_text() == "artifact=hello\n"
        exported = executor.export_spools(str(tmp_path / "spools"))
        terminal_manifest = exported["terminal_transcripts"]
        assert terminal_manifest["file_count"] == 1
        stored = Path(terminal_manifest["files"][0]["stored_path"])
        raw = stored.read_bytes().decode("utf-8", "replace")
        assert "QUESTION" in raw and "ANSWER=hello" in raw
        executor.close()

    def test_terminal_interrupt_and_close_bind_exact_generation(self, docker_env: tuple[str, str]) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)
        handle = executor.start_terminal_session(
            "interruptible",
            "trap 'echo INTERRUPTED; exit 130' INT; echo READY; while :; do read line; done",
            cwd="/app",
        )
        ready = executor.terminal_read(handle.session_id, wait_ms=1500)
        assert "READY" in ready.output
        interrupted = executor.terminal_interrupt(handle.session_id)
        assert interrupted.process_generation == handle.process_generation
        result = executor.terminal_read(handle.session_id, wait_ms=1500)
        assert "INTERRUPTED" in result.output
        final = executor.terminal_wait(handle.session_id, timeout_s=2)
        assert not final.live

        second = executor.start_terminal_session(
            "closable",
            "echo STARTED; sleep 300 & child=$!; echo CHILD=$child; wait $child",
            cwd="/app",
        )
        observed = executor.terminal_read(second.session_id, wait_ms=1500)
        assert "STARTED" in observed.output
        child_line = next(line for line in observed.output.replace('\r', '').splitlines() if line.startswith("CHILD="))
        child_pid = int(child_line.split("=", 1)[1])
        child_identity = subprocess.run(
            ["docker", "exec", cid, "bash", "-lc", f"awk '{{print $22}}' /proc/{child_pid}/stat"],
            capture_output=True, text=True, timeout=5,
        )
        assert child_identity.returncode == 0
        child_start = child_identity.stdout.strip()
        assert child_start.isdigit()
        closed = executor.terminal_close(second.session_id)
        assert not closed.live
        assert closed.process_generation == second.process_generation
        # Closing owns the exact descendant generation, not a numeric PID. A
        # later docker exec may legitimately reuse child_pid immediately.
        child_probe = subprocess.run(
            ["docker", "exec", cid, "bash", "-lc",
             f"current=$(awk '{{print $22}}' /proc/{child_pid}/stat 2>/dev/null || true); test \"$current\" != {child_start!r}"],
            capture_output=True, text=True, timeout=5,
        )
        if child_probe.returncode != 0:
            state_probe = subprocess.run(
                ["docker", "exec", cid, "bash", "-lc",
                 f"awk '{{print \"state=\"$3,\"ppid=\"$4,\"pgrp=\"$5,\"sid=\"$6,\"start=\"$22}}' /proc/{child_pid}/stat 2>/dev/null || true"],
                capture_output=True, text=True, timeout=5,
            )
            raise AssertionError(
                f"terminal child generation leaked: pid={child_pid} start={child_start} {state_probe.stdout.strip()}"
            )
        with pytest.raises(RuntimeError, match="not live"):
            executor.terminal_send(second.session_id, "should-not-send")
        executor.close()

    def test_registered_service_descendant_listener_binds_generation(
        self, docker_env: tuple[str, str]
    ) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)
        executor.write_file(
            "/app/listener.pl",
            "use IO::Socket::INET; my $s=IO::Socket::INET->new(LocalAddr=>'127.0.0.1',LocalPort=>8765,Listen=>5,Reuse=>1,Proto=>'tcp') or die $!; sleep 300;\n",
        )
        handle = executor.launch_process("web", "perl listener.pl", cwd="/app")
        try:
            probe = None
            for _ in range(100):
                probe = executor.probe_process("127.0.0.1:8765")
                if probe.live and probe.process_generation_verified:
                    break
                time.sleep(0.05)
            assert probe is not None and probe.live
            assert probe.process_generation_verified is True
            assert probe.process_id == handle.process_id
            assert probe.process_generation == handle.process_generation
            assert probe.endpoint_owner_pids
            assert handle.pid not in probe.endpoint_owner_pids
            assert executor.stop_process(handle.process_id) is True
            post_stop = None
            for _ in range(40):
                post_stop = executor.probe_process("127.0.0.1:8765")
                if not post_stop.live:
                    break
                time.sleep(0.05)
            assert post_stop is not None and post_stop.live is False
        finally:
            executor.stop_process(handle.process_id)
            executor.close()

    def test_f80_independent_verifier_uses_current_rootfs_sibling_with_no_parent_world(
        self, docker_env: tuple[str, str]
    ) -> None:
        cid, workspace = docker_env
        executor = DockerExecExecutor(cid, workspace)
        Path(workspace, "authoritative.txt").write_text("SOURCE")
        marker = "F80_PARENT_PROCESS_9d6b7e21"
        # Runtime-only rootfs state proves the sibling comes from CURRENT
        # container state rather than the configured base image.
        prep = subprocess.run(
            ["docker", "exec", cid, "bash", "-lc",
             f"printf '%s' {marker!r} >/f80_process_marker; printf runtime >/f80_runtime_marker; "
             "perl -MIO::Socket::INET -e '$s=IO::Socket::INET->new(LocalAddr=>\"127.0.0.1\",LocalPort=>18765,Listen=>5,Reuse=>1,Proto=>\"tcp\") or die $!; sleep 300' >/tmp/f80-listener.out 2>&1 & "
             "bash -c 'exec -a \"$1\" sleep 300' _ \"$(cat /f80_process_marker)\" &"],
            capture_output=True, text=True, timeout=30,
        )
        assert prep.returncode == 0, prep.stderr
        child_root = "/app.verifier_overlay_f80test.command_one"
        copied = subprocess.run(
            ["docker", "exec", cid, "bash", "-lc", f"rm -rf {child_root}; cp -a /app {child_root}"],
            capture_output=True, text=True, timeout=30,
        )
        assert copied.returncode == 0, copied.stderr
        try:
            command = (
                "test \"$(cat /f80_runtime_marker)\" = runtime; "
                "test \"$(cat /app/authoritative.txt)\" = SOURCE; "
                "m=$(cat /f80_process_marker); ! grep -a -l \"$m\" /proc/[0-9]*/cmdline >/dev/null 2>&1; "
                "perl -MIO::Socket::INET -e '$s=IO::Socket::INET->new(PeerAddr=>\"127.0.0.1\",PeerPort=>18765,Proto=>\"tcp\",Timeout=>1); exit($s?9:0)'; "
                "printf isolated >/app/sibling-only.txt"
            )
            isolated = executor.run_independent_verifier_command(
                command, workspace_root=child_root, timeout_s=30,
            )
            assert not isolated.get("error"), isolated
            result = isolated["result"]
            metadata = isolated["metadata"]
            assert result.exit_code == 0, (result.stdout, result.stderr, metadata)
            assert metadata["independent_isolation_verified"] is True
            assert metadata["isolation_cleanup_verified"] is True
            assert metadata["network_scope"] == "docker_none"
            assert metadata["mount_namespace_private"] is True
            assert metadata["pid_namespace_private"] is True
            assert metadata["network_namespace_private"] is True
            assert metadata["sibling_container_removed"] is True
            assert metadata["snapshot_image_removed"] is True
            assert metadata["execution_isolation"] == "docker_current_rootfs_snapshot_sibling"
            # Sibling writes cannot flow back into the Solver bind mount.
            assert not Path(workspace, "sibling-only.txt").exists()
        finally:
            subprocess.run(
                ["docker", "exec", cid, "bash", "-lc", f"rm -rf {child_root}"],
                capture_output=True, text=True, timeout=30,
            )
            executor.close()

    def test_teardown_removes_container(self) -> None:
        """Verify that container removal works (manual lifecycle)."""
        workspace = tempfile.mkdtemp(prefix="test_teardown_")
        try:
            start = subprocess.run(
                ["docker", "run", "-d", "debian:stable-slim", "sleep", "infinity"],
                capture_output=True, text=True, timeout=60,
            )
            assert start.returncode == 0
            cid = start.stdout.strip()

            # Remove.
            rm = subprocess.run(
                ["docker", "rm", "-f", cid],
                capture_output=True, text=True, timeout=30,
            )
            assert rm.returncode == 0

            # Verify gone.
            inspect = subprocess.run(
                ["docker", "inspect", cid],
                capture_output=True, text=True, timeout=10,
            )
            assert inspect.returncode != 0
        finally:
            import shutil
            shutil.rmtree(workspace, ignore_errors=True)


# ---------------------------------------------------------------------------
# Unit tests (no Docker required)
# ---------------------------------------------------------------------------

class TestGitSafeDirConstant:
    """Verify the _GIT_SAFE_DIR_CMD module constant is well-formed."""

    def test_constant_contains_safe_directory(self) -> None:
        from aether.runners.docker_runner import _GIT_SAFE_DIR_CMD

        assert "safe.directory" in _GIT_SAFE_DIR_CMD
        assert "'*'" in _GIT_SAFE_DIR_CMD
        # The trailing `|| true` ensures non-zero exit is swallowed.
        assert "|| true" in _GIT_SAFE_DIR_CMD


class TestCertifiedArchitectModeQuarantine:
    def test_reference_modes_are_rejected_before_docker_work(self) -> None:
        with tempfile.TemporaryDirectory() as task_dir:
            record = run_tbench_task(
                task_dir=task_dir,
                image="debian:stable-slim",
                architect_model=lambda *_args, **_kwargs: "{}",
                solver_model=lambda *_args, **_kwargs: "{}",
                architect_mode="ir",
            )

        assert record["status"] == "error"
        assert record["error"] == "invalid_architect_mode"
        assert record["architect_mode"] == "ir"
        assert "quarantined in reference_legacy" in record["error_detail"]


class TestEffectiveRunTimeout:
    def test_task_declared_budget_raises_runner_floor(self) -> None:
        from aether.runners.docker_runner import _effective_run_timeout_s

        effective, policy = _effective_run_timeout_s(1800, {"agent": {"timeout_sec": 3600}})
        assert effective == 3600
        assert "task_declared=3600" in policy

    def test_missing_budget_keeps_runner_default(self) -> None:
        from aether.runners.docker_runner import _effective_run_timeout_s

        effective, policy = _effective_run_timeout_s(1800, {})
        assert effective == 1800
        assert "runner_default" in policy

    def test_declared_budget_is_capped_and_never_lowers_floor(self) -> None:
        from aether.runners.docker_runner import (
            _MAX_RUN_TIMEOUT_S,
            _effective_run_timeout_s,
        )

        effective, _ = _effective_run_timeout_s(1800, {"agent": {"timeout_sec": 999999}})
        assert effective == _MAX_RUN_TIMEOUT_S
        effective, _ = _effective_run_timeout_s(1800, {"agent": {"timeout_sec": 60}})
        assert effective == 1800

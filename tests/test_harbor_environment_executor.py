from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import pytest

from aether.execution import BootstrapEngine, CommandResult, PerceptionLane
from aether.harbor_executor import HarborEnvironmentExecutor
from aether.perception_vision import needs_vision
from aether.runtime_ir import ActionRequest, EnvMap


@dataclass
class _Completed:
    return_code: int
    stdout: str = ""
    stderr: str = ""


class _LocalAsyncEnvironment:
    """Real local shell/file implementation of Harbor's small environment surface.

    This is a contract test double, not evidence that Harbor itself is installed
    or production-qualified. Commands/processes/files are real OS operations.
    """

    async def exec(
        self,
        *,
        command: str,
        cwd: str | None,
        env: dict[str, str] | None,
        timeout_sec: int,
    ) -> _Completed:
        def _run() -> _Completed:
            completed = subprocess.run(
                ["/bin/sh", "-lc", command],
                cwd=cwd,
                env=None if env is None else {**dict(__import__("os").environ), **env},
                text=True,
                capture_output=True,
                timeout=timeout_sec,
            )
            return _Completed(completed.returncode, completed.stdout, completed.stderr)

        return await asyncio.to_thread(_run)

    async def upload_file(self, source: Path, destination: str) -> None:
        def _copy() -> None:
            target = Path(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

        await asyncio.to_thread(_copy)

    async def download_file(self, source: str, destination: Path) -> None:
        await asyncio.to_thread(shutil.copyfile, source, destination)


def _run_scenario(callback):
    async def _main():
        with tempfile.TemporaryDirectory(prefix="aether-harbor-executor-test-") as tmp:
            root = Path(tmp) / "workspace"
            state = Path(tmp) / "state"
            root.mkdir()
            loop = asyncio.get_running_loop()
            executor = HarborEnvironmentExecutor(
                _LocalAsyncEnvironment(),
                event_loop=loop,
                workspace_root=str(root),
                local_state_dir=state,
            )
            try:
                return await asyncio.to_thread(callback, executor, root)
            finally:
                await asyncio.to_thread(executor.close)

    return asyncio.run(_main())




def test_packaged_harbor_subreaper_identity_is_frozen() -> None:
    import hashlib
    import aether.harbor_executor as module

    helper = Path(module.__file__).with_name("harbor_subreaper_linux_x86_64")
    source = Path(module.__file__).with_name("harbor_subreaper.c")
    assert helper.is_file()
    assert source.is_file()
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == (
        "b5c68b3f11f357ba14fed69d82a192d7a2853e05f059af32a0415da0301dc2f4"
    )
    text = source.read_text(encoding="utf-8")
    assert "PR_SET_CHILD_SUBREAPER" in text
    assert "signal_descendants(self, SIGKILL)" in text
    assert "cleanup_status" not in text  # path is supplied by the Python authority

def test_harbor_executor_real_foreground_file_and_artifact_contract() -> None:
    def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
        executor.write_file("nested/value.txt", "hello\n")
        assert executor.read_file("nested/value.txt") == "hello\n"
        result = executor.run_command("printf 'world\\n' >> nested/value.txt && wc -l < nested/value.txt")
        assert result.success
        assert result.stdout.strip() == "2"
        assert result.provenance == ("harbor:supervised_process_group",)
        bash = executor.run_command("items=(zero one); printf '%s\n' \"${items[1]}\"")
        assert bash.success is True
        assert bash.stdout == "one\n"
        assert executor.exists("nested/value.txt") is True
        assert executor.glob("nested/*.txt") == (str(root / "nested" / "value.txt"),)
        inspection = executor.inspect_artifact("nested/value.txt", "text")
        assert inspection.success
        assert inspection.extracted_text == "hello\nworld\n"
        assert inspection.metadata["bytes"] == len(b"hello\nworld\n")
        assert len(inspection.metadata["sha256"]) == 64

    _run_scenario(scenario)


def test_harbor_executor_rejects_file_api_workspace_escape() -> None:
    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        with pytest.raises(ValueError, match="workspace path escape"):
            executor.read_file("../outside.txt")
        with pytest.raises(ValueError, match="workspace path escape"):
            executor.write_file("/tmp/outside.txt", "x")

    _run_scenario(scenario)


def test_harbor_executor_normalizes_missing_harbor_download_to_file_not_found() -> None:
    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        async def missing_download(source: str, destination: Path) -> None:
            del source, destination
            raise RuntimeError("docker compose cp source missing")

        executor.environment.download_file = missing_download
        with pytest.raises(FileNotFoundError):
            executor.read_file("never-created.txt")
        with pytest.raises(FileNotFoundError):
            executor.read_file_bytes("never-created.bin")

    _run_scenario(scenario)


def test_harbor_executor_preserves_download_transport_error_when_source_exists() -> None:
    def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
        (root / "exists.txt").write_text("present\n", encoding="utf-8")

        async def broken_download(source: str, destination: Path) -> None:
            del source, destination
            raise RuntimeError("docker compose transport failed")

        executor.environment.download_file = broken_download
        with pytest.raises(RuntimeError, match="docker compose transport failed"):
            executor.read_file("exists.txt")

    _run_scenario(scenario)


def test_harbor_executor_timeout_terminates_supervised_process_group_before_return() -> None:
    def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
        pid_path = root / "timed-child.pid"
        late_path = root / "late-write.txt"
        command = (
            "python3 -c "
            + __import__("shlex").quote(
                "import os,pathlib,signal,time; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                f"pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid())); "
                "time.sleep(30); "
                f"pathlib.Path({str(late_path)!r}).write_text('late')"
            )
        )
        result = executor.run_command(command, timeout_s=1)
        assert result.exit_code == 124
        assert result.timed_out is True
        assert result.success is False
        assert "remote process group terminated" in result.stderr
        assert result.metrics["remote_process_group_terminated"] is True
        assert result.provenance == ("harbor:supervised_process_group",)
        if pid_path.exists():
            child_pid = int(pid_path.read_text(encoding="utf-8"))
            with pytest.raises(ProcessLookupError):
                __import__("os").kill(child_pid, 0)
        # An invocation-start deadline may terminate before the child reaches
        # its PID marker; either way, no delayed mutation may survive return.
        time.sleep(0.2)
        assert late_path.exists() is False

    _run_scenario(scenario)


def test_harbor_executor_timeout_deadline_is_anchored_before_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A slow launch acknowledgement must not grant a fresh action timeout."""
    import aether.harbor_executor as harbor_module
    from types import SimpleNamespace

    # The first monotonic value is run_command entry. By the first status
    # observation the declared one-second authority is already exhausted.
    ticks = iter((100.0, 101.25, 101.25))
    monkeypatch.setattr(harbor_module.time, "monotonic", lambda: next(ticks, 101.25))
    monkeypatch.setattr(harbor_module.time, "sleep", lambda _seconds: None)

    class DummyEnv:
        pass

    loop = asyncio.new_event_loop()
    executor = HarborEnvironmentExecutor(
        DummyEnv(), event_loop=loop, workspace_root="/tmp/aether-deadline-unit",
        local_state_dir=Path(tempfile.mkdtemp(prefix="aether-deadline-state-")),
    )
    record = SimpleNamespace(container_id="")
    terminated = []
    monkeypatch.setattr(executor, "_launch_supervised_foreground_command", lambda command, cwd=None: record)
    monkeypatch.setattr(executor, "_remote_status", lambda _record: (True, None, "running"))
    monkeypatch.setattr(executor, "_terminate_supervised_foreground", lambda _record: (terminated.append(True) or (True, "terminated")))
    monkeypatch.setattr(executor, "_download_remote_process_streams", lambda _record: ("", ""))
    monkeypatch.setattr(executor, "_cleanup_supervised_foreground", lambda _record: None)
    monkeypatch.setattr(executor, "_docker_environment_type", lambda: False)
    try:
        result = executor.run_command("ignored", timeout_s=1)
    finally:
        loop.close()
    assert result.timed_out is True
    assert result.exit_code == 124
    assert terminated == [True]


def test_harbor_executor_does_not_relabel_unrelated_runtime_error_as_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raising_launch(self, command: str, *, cwd: str | None = None):
        del self, command, cwd
        raise RuntimeError("docker compose transport failed")

    monkeypatch.setattr(HarborEnvironmentExecutor, "_launch_supervised_foreground_command", raising_launch)

    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        with pytest.raises(RuntimeError, match="docker compose transport failed"):
            executor.run_command("broken")

    _run_scenario(scenario)


def test_bootstrap_acquisition_has_metadata_poor_fallback_budget() -> None:
    class _Recorder:
        def __init__(self) -> None:
            self.timeout_s = None

        def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30):
            self.timeout_s = timeout_s
            return CommandResult(
                command=command, exit_code=124, timed_out=True, stderr="timeout"
            )

    recorder = _Recorder()
    action = ActionRequest(
        action_id="bootstrap-test",
        kind="bootstrap_acquire",
        capability_id="shell",
        arguments={"manager": "apt", "target": "gcc make"},
        intent="acquire build tools",
        expected_observation="tools available",
        if_fail_next="report failure",
    )
    receipt, refreshed = BootstrapEngine().execute(
        action, 1, recorder, EnvMap(task_prompt="bootstrap test", workspace_root="/app", capabilities={})
    )
    assert recorder.timeout_s == 120
    assert receipt.success is False
    assert receipt.failure_class == "bootstrap_required"
    assert receipt.payload["command"] == "apt-get update && apt-get install -y gcc make"
    assert refreshed is None


def test_bootstrap_acquisition_honors_explicit_task_timeout_authority() -> None:
    class _Recorder:
        def __init__(self) -> None:
            self.timeout_s = None
        def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30):
            self.timeout_s = timeout_s
            return CommandResult(command=command, exit_code=0, stdout="installed\n")
        def refresh_envmap(self, envmap):
            return envmap
    recorder = _Recorder()
    action = ActionRequest(
        action_id="bootstrap-authority", kind="bootstrap_acquire", capability_id="shell",
        arguments={"manager":"cargo","target":"some-tool"}, intent="install",
        expected_observation="installed", if_fail_next="report failure",
    )
    envmap = EnvMap(
        task_prompt="bootstrap authority", workspace_root="/app", capabilities={},
        task_metadata={"resource_budget":{"agent_timeout_sec":3600}},
    )
    receipt, _ = BootstrapEngine().execute(action, 1, recorder, envmap)
    assert recorder.timeout_s == 3600
    assert receipt.payload["timeout_s"] == 3600
    assert receipt.payload["timeout_policy"] == "task_declared:agent_timeout_sec=3600"



def test_harbor_executor_real_background_job_lifecycle() -> None:
    def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
        handle = executor.launch_process(
            "worker",
            "sleep 0.2; printf 'done\\n' > job-result.txt",
        )
        assert handle.live is True
        assert handle.process_generation
        deadline = time.monotonic() + 5.0
        probe = executor.probe_job(handle.process_id)
        while not probe.completed and time.monotonic() < deadline:
            time.sleep(0.05)
            probe = executor.probe_job(handle.process_id)
        assert probe.completed is True
        assert probe.succeeded is True
        assert probe.exit_code == 0
        assert (root / "job-result.txt").read_text() == "done\n"
        process_probe = executor.probe_process("worker")
        assert process_probe.live is False
        assert process_probe.process_generation_verified is True

    _run_scenario(scenario)


def test_harbor_executor_failed_background_job_preserves_bounded_child_streams() -> None:
    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        handle = executor.launch_process(
            "failing-worker",
            "printf 'child standard output\\n'; printf 'child assertion detail\\n' >&2; exit 7",
        )
        deadline = time.monotonic() + 5.0
        probe = executor.probe_job(handle.process_id)
        while not probe.completed and time.monotonic() < deadline:
            time.sleep(0.05)
            probe = executor.probe_job(handle.process_id)
        assert probe.completed is True
        assert probe.succeeded is False
        assert probe.exit_code == 7
        assert "child_stdout:\nchild standard output" in probe.detail
        assert "child_stderr:\nchild assertion detail" in probe.detail

    _run_scenario(scenario)


def test_harbor_executor_real_line_oriented_terminal_round_trip() -> None:
    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        session = executor.start_terminal_session(
            "echo-loop",
            "while IFS= read -r line; do printf 'got:%s\\n' \"$line\"; [ \"$line\" = quit ] && exit 0; done",
        )
        assert session.live
        executor.terminal_send(session.session_id, "hello")
        deadline = time.monotonic() + 5.0
        observed = ""
        while "got:hello" not in observed and time.monotonic() < deadline:
            chunk = executor.terminal_read(session.session_id, max_bytes=4096, wait_ms=50)
            observed += chunk.output
        assert "got:hello" in observed
        executor.terminal_send(session.session_id, "quit")
        state = executor.terminal_wait(session.session_id, timeout_s=5)
        assert state.live is False
        assert state.exit_code == 0

    _run_scenario(scenario)


def test_harbor_executor_image_inspection_exposes_exact_identity_and_requests_semantic_perception() -> None:
    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        raw = b"\x89PNG\r\n\x1a\nsynthetic-image-bytes"
        local = executor.local_state_dir / "picture-source.png"
        local.write_bytes(raw)
        executor._await(
            executor.environment.upload_file(local, executor._remote_path("picture.png")),
            timeout_s=60,
        )
        local.unlink(missing_ok=True)
        action = ActionRequest(
            "img", "inspect_artifact", "artifact_inspection",
            {"path": "picture.png", "mode": "image"},
            "inspect", "semantic pixels", "derive a view",
        )
        receipt = PerceptionLane().inspect(
            action, 1, executor, workspace_root=executor.workspace_root,
        )
        assert receipt.success is False
        assert needs_vision(receipt) is True
        identity = receipt.payload["metadata"]["artifact_identity"]
        assert identity["media_type"] == "image/png"
        assert identity["bytes"] == len(raw)
        assert receipt.payload["metadata"]["semantic_content_available"] is False

    _run_scenario(scenario)


class _LocalDockerAsyncEnvironment(_LocalAsyncEnvironment):
    @staticmethod
    def type() -> str:
        return "docker"

    async def _run_docker_compose_command(
        self,
        command: list[str],
        check: bool = True,
        timeout_sec: int | None = None,
        **_kwargs,
    ) -> _Completed:
        del check, timeout_sec
        if command == ["ps", "-q", "main"]:
            return _Completed(0, "a" * 64 + "\n", "")
        return _Completed(2, "", "unexpected compose command")


def _run_docker_scenario(callback):
    async def _main():
        with tempfile.TemporaryDirectory(prefix="aether-harbor-docker-executor-test-") as tmp:
            root = Path(tmp) / "workspace"
            state = Path(tmp) / "state"
            root.mkdir()
            loop = asyncio.get_running_loop()
            executor = HarborEnvironmentExecutor(
                _LocalDockerAsyncEnvironment(),
                event_loop=loop,
                workspace_root=str(root),
                local_state_dir=state,
            )
            try:
                return await asyncio.to_thread(callback, executor, root)
            finally:
                await asyncio.to_thread(executor.close)
    return asyncio.run(_main())


def test_harbor_executor_for_workspace_rebinds_path_authority_without_new_world() -> None:
    def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
        child_root = str(root) + ".verifier_overlay_deadbeef"
        Path(child_root).mkdir()
        clone = executor.for_workspace(child_root)
        assert clone.environment is executor.environment
        assert clone.event_loop is executor.event_loop
        assert clone.workspace_root == child_root
        assert clone.local_state_dir != executor.local_state_dir
        clone.write_file("proof.txt", "ok\n")
        assert Path(child_root, "proof.txt").read_text() == "ok\n"
        with pytest.raises(ValueError, match="workspace path escape"):
            clone.read_file(str(root / "outside.txt"))
    _run_scenario(scenario)


def test_harbor_docker_independent_verifier_uses_owned_pause_snapshot_sibling_and_verifies_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    paused = False

    def fake_host_call(args: list[str], *, timeout_s: int):
        nonlocal paused
        del timeout_s
        calls.append(list(args))
        if args[:3] == ["docker", "inspect", "--format"]:
            return subprocess.CompletedProcess(
                args, 0, stdout=f"true {'true' if paused else 'false'}\n", stderr=""
            ), ""
        if args[:2] == ["docker", "pause"]:
            assert paused is False
            paused = True
            return subprocess.CompletedProcess(args, 0, stdout="parent\n", stderr=""), ""
        if args[:2] == ["docker", "unpause"]:
            assert paused is True
            paused = False
            return subprocess.CompletedProcess(args, 0, stdout="parent\n", stderr=""), ""
        if args[:3] == ["docker", "commit", "--pause=false"]:
            assert paused is True
            return subprocess.CompletedProcess(args, 0, stdout="sha256:snapshot\n", stderr=""), ""
        if args[:2] == ["docker", "run"]:
            assert paused is False, "parent must be runnable before sibling work starts"
            assert "--detach" in args
            assert "--network" in args
            assert args[args.index("--network") + 1] == "none"
            assert "/app.verifier_overlay_deadbeef.command_cafebabe" in args
            return subprocess.CompletedProcess(args, 0, stdout="container-id\n", stderr=""), ""
        if args[:2] == ["docker", "exec"]:
            if "test" in args and "-f" in args:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
            assert args[args.index("--workdir") + 1] == "/app"
            assert args[-1] == "printf verified"
            return subprocess.CompletedProcess(args, 0, stdout="verified\n", stderr=""), ""
        if args[:3] == ["docker", "rm", "-f"] or args[:3] == ["docker", "image", "rm"]:
            return subprocess.CompletedProcess(args, 0, stdout="removed\n", stderr=""), ""
        if args[:2] == ["docker", "inspect"] or args[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="not found"), ""
        raise AssertionError(args)

    monkeypatch.setattr(HarborEnvironmentExecutor, "_docker_host_call", staticmethod(fake_host_call))

    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        result = executor.run_independent_verifier_command(
            "printf verified",
            workspace_root="/app.verifier_overlay_deadbeef.command_cafebabe",
            timeout_s=10,
        )
        assert result.get("error") in (None, "")
        assert result["result"].stdout == "verified\n"
        metadata = result["metadata"]
        assert metadata["independent_isolation_verified"] is True
        assert metadata["isolation_cleanup_verified"] is True
        assert metadata["parent_runnable_before_snapshot"] is True
        assert metadata["parent_pause_owned"] is True
        assert metadata["parent_unpause_attempted"] is True
        assert metadata["parent_unpause_succeeded"] is True
        assert metadata["parent_runnable_after_snapshot"] is True
        assert paused is False
        pause_i = next(i for i,row in enumerate(calls) if row[:2] == ["docker", "pause"])
        commit_i = next(i for i,row in enumerate(calls) if row[:3] == ["docker", "commit", "--pause=false"])
        unpause_i = next(i for i,row in enumerate(calls) if row[:2] == ["docker", "unpause"])
        run_i = next(i for i,row in enumerate(calls) if row[:2] == ["docker", "run"])
        assert pause_i < commit_i < unpause_i < run_i
        assert calls[commit_i][3] == "a" * 64
    _run_docker_scenario(scenario)


def test_harbor_docker_independent_verifier_fails_closed_when_cleanup_cannot_be_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paused = False
    def fake_host_call(args: list[str], *, timeout_s: int):
        nonlocal paused
        del timeout_s
        if args[:3] == ["docker", "inspect", "--format"]:
            return subprocess.CompletedProcess(args,0,stdout=f"true {'true' if paused else 'false'}\n",stderr=""),""
        if args[:2] == ["docker", "pause"]:
            paused=True; return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
        if args[:2] == ["docker", "unpause"]:
            paused=False; return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
        if args[:3] == ["docker", "commit", "--pause=false"]:
            return subprocess.CompletedProcess(args,0,stdout="sha256:snapshot\n",stderr=""),""
        if args[:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(args,0,stdout="container-id\n",stderr=""),""
        if args[:2] == ["docker", "exec"]:
            if "test" in args and "-f" in args: return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
            return subprocess.CompletedProcess(args,0,stdout="ok\n",stderr=""),""
        if args[:3] == ["docker", "rm", "-f"] or args[:3] == ["docker", "image", "rm"]:
            return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
        if args[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(args,0,stdout="still exists",stderr=""),""
        if args[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args,1,stdout="",stderr="not found"),""
        raise AssertionError(args)
    monkeypatch.setattr(HarborEnvironmentExecutor,"_docker_host_call",staticmethod(fake_host_call))
    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        result=executor.run_independent_verifier_command("true",workspace_root="/app.verifier_overlay_deadbeef.command_cafebabe")
        assert result["error"] == "verifier_independent_isolation_docker_cleanup_failed"
        assert result["metadata"]["independent_isolation_verified"] is True
        assert result["metadata"]["isolation_cleanup_verified"] is False
        assert result["metadata"]["parent_runnable_after_snapshot"] is True
        assert paused is False
    _run_docker_scenario(scenario)


def test_harbor_snapshot_unpauses_parent_even_when_commit_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls=[]; paused=False
    def fake_host_call(args: list[str], *, timeout_s: int):
        nonlocal paused
        del timeout_s; calls.append(list(args))
        if args[:3]==["docker","inspect","--format"]:
            return subprocess.CompletedProcess(args,0,stdout=f"true {'true' if paused else 'false'}\n",stderr=""),""
        if args[:2]==["docker","pause"]:
            paused=True; return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
        if args[:3]==["docker","commit","--pause=false"]:
            return subprocess.CompletedProcess(args,1,stdout="",stderr="commit failed"),""
        if args[:2]==["docker","unpause"]:
            paused=False; return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
        if args[:3]==["docker","rm","-f"]: return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
        if args[:2]==["docker","inspect"] or args[:3]==["docker","image","inspect"]:
            return subprocess.CompletedProcess(args,1,stdout="",stderr="not found"),""
        raise AssertionError(args)
    monkeypatch.setattr(HarborEnvironmentExecutor,"_docker_host_call",staticmethod(fake_host_call))
    def scenario(executor: HarborEnvironmentExecutor, _root: Path):
        result=executor.run_independent_verifier_command("true",workspace_root="/app.verifier_overlay_deadbeef.command_cafebabe")
        assert "docker_commit_failed" in result["error"]
        assert result["metadata"]["parent_unpause_attempted"] is True
        assert result["metadata"]["parent_unpause_succeeded"] is True
        assert result["metadata"]["parent_runnable_after_snapshot"] is True
        assert paused is False
        assert any(row[:2]==["docker","unpause"] for row in calls)
    _run_docker_scenario(scenario)


def test_harbor_independent_verifier_rejects_non_docker_provider_without_fallback() -> None:
    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        result = executor.run_independent_verifier_command(
            "true",
            workspace_root="/app.verifier_overlay_deadbeef.command_cafebabe",
        )
        assert "unsupported_harbor_provider" in result["error"]
        assert result["metadata"]["independent_isolation_verified"] is False
    _run_scenario(scenario)



def test_harbor_terminal_observes_workspace_mutation_across_interactions() -> None:
    def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
        session = executor.start_terminal_session(
            "stateful-terminal",
            "read line; printf '%s\\n' \"$line\" > terminal-mutated.txt; echo done",
        )
        sent = executor.terminal_send(session.session_id, "value")
        deadline = time.monotonic() + 5.0
        observed: set[str] = set(sent.state_delta.get("created_paths", ()))
        observed.update(sent.state_delta.get("metadata_changed_paths", ()))
        while "terminal-mutated.txt" not in observed and time.monotonic() < deadline:
            chunk = executor.terminal_read(session.session_id, max_bytes=4096, wait_ms=50)
            delta = chunk.state_delta
            observed.update(delta.get("created_paths", ()))
            observed.update(delta.get("metadata_changed_paths", ()))
        assert "terminal-mutated.txt" in observed
        assert (root / "terminal-mutated.txt").read_text() == "value\n"
        assert not any(path.startswith(".aether/harbor_terminals/") for path in observed)

    _run_scenario(scenario)



def test_harbor_managed_process_observer_captures_async_workspace_write() -> None:
    def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
        handle = executor.launch_process(
            "async-writer", "sleep 0.05; printf done > async-harbor-process.txt"
        )
        deadline = time.monotonic() + 5.0
        observed: set[str] = set()
        while "async-harbor-process.txt" not in observed and time.monotonic() < deadline:
            time.sleep(0.05)
            delta = executor.observe_process_state(handle.process_id)
            observed.update(delta.get("created_paths", ()))
            observed.update(delta.get("metadata_changed_paths", ()))
        assert "async-harbor-process.txt" in observed
        assert (root / "async-harbor-process.txt").read_text() == "done"
        assert not any(path.startswith(".aether/harbor_jobs/") for path in observed)

    _run_scenario(scenario)



def test_harbor_executor_verifier_world_read_is_read_only_and_realpath_guarded() -> None:
    def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
        outside = root.parent / "external-world.txt"
        outside.write_text("external state\n", encoding="utf-8")

        # Ordinary Solver file APIs stay workspace-confined.
        with pytest.raises(ValueError, match="workspace path escape"):
            executor.read_file(str(outside))

        # Independent Verifier direct observation may read only a task-public
        # absolute root configured from the raw task surface.
        executor.set_verifier_world_roots((str(outside),))
        assert executor.resolve_verifier_read_path(str(outside)) == str(outside.resolve())
        assert executor.read_verifier_file(str(outside)) == "external state\n"
        assert executor.read_verifier_file_bytes(str(outside)) == b"external state\n"

        unrelated = root.parent / "unmentioned-world.txt"
        unrelated.write_text("not task public\n", encoding="utf-8")
        with pytest.raises(ValueError, match="task-public absolute root"):
            executor.read_verifier_file(str(unrelated))

        # Resolve first, then deny: a workspace symlink cannot tunnel into a
        # pseudo-filesystem/secret root.
        denied_link = root / "denied-link"
        denied_link.symlink_to("/dev/null")
        with pytest.raises(ValueError, match="privacy boundary"):
            executor.read_verifier_file(str(denied_link))

        with pytest.raises(ValueError, match="absolute path"):
            executor.read_verifier_file("relative.txt")

    _run_scenario(scenario)


def test_foreground_command_waits_for_delayed_exit_status_visibility(monkeypatch) -> None:
    """Process death one probe before exit-file visibility is not a false failure."""
    from types import SimpleNamespace

    statuses = iter([
        (False, None, "status file not visible yet"),
        (False, 0, ""),
    ])

    monkeypatch.setattr(
        HarborEnvironmentExecutor,
        "_launch_supervised_foreground_command",
        lambda self, command, cwd=None: SimpleNamespace(generation="grace"),
    )
    monkeypatch.setattr(
        HarborEnvironmentExecutor,
        "_remote_status",
        lambda self, record: next(statuses),
    )
    monkeypatch.setattr(
        HarborEnvironmentExecutor,
        "_download_remote_process_streams",
        lambda self, record: ("ok\n", ""),
    )
    monkeypatch.setattr(
        HarborEnvironmentExecutor,
        "_cleanup_supervised_foreground",
        lambda self, record: None,
    )

    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        result = executor.run_command("true", timeout_s=2)
        assert result.exit_code == 0
        assert result.stdout == "ok\n"
        assert result.timed_out is False

    _run_scenario(scenario)


def test_harbor_snapshot_fails_closed_when_owned_pause_cannot_be_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    paused=False
    def fake_host_call(args: list[str], *, timeout_s: int):
        nonlocal paused
        del timeout_s
        if args[:3]==["docker","inspect","--format"]:
            return subprocess.CompletedProcess(args,0,stdout=f"true {'true' if paused else 'false'}\n",stderr=""),""
        if args[:2]==["docker","pause"]:
            paused=True; return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
        if args[:3]==["docker","commit","--pause=false"]:
            return subprocess.CompletedProcess(args,0,stdout="sha256:snapshot\n",stderr=""),""
        if args[:2]==["docker","unpause"]:
            return subprocess.CompletedProcess(args,1,stdout="",stderr="unpause failed"),""
        if args[:3]==["docker","rm","-f"] or args[:3]==["docker","image","rm"]:
            return subprocess.CompletedProcess(args,0,stdout="",stderr=""),""
        if args[:2]==["docker","inspect"] or args[:3]==["docker","image","inspect"]:
            return subprocess.CompletedProcess(args,1,stdout="",stderr="not found"),""
        raise AssertionError(args)
    monkeypatch.setattr(HarborEnvironmentExecutor,"_docker_host_call",staticmethod(fake_host_call))
    monkeypatch.setattr(HarborEnvironmentExecutor,"_wait_for_docker_container_runnable",lambda self,cid,timeout_s=10.0:(False,"state=true true",1))
    def scenario(executor: HarborEnvironmentExecutor, _root: Path):
        result=executor.run_independent_verifier_command("true",workspace_root="/app.verifier_overlay_deadbeef.command_cafebabe")
        assert "parent_unpause_failed" in result["error"]
        assert result["metadata"]["parent_pause_owned"] is True
        assert result["metadata"]["parent_unpause_attempted"] is True
        assert result["metadata"]["parent_unpause_succeeded"] is False
        assert result["metadata"]["parent_runnable_after_snapshot"] is False
    _run_docker_scenario(scenario)


def test_harbor_verifier_snapshot_timeout_scales_with_generation_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paused = False
    commit_timeouts: list[int] = []

    def fake_host_call(args: list[str], *, timeout_s: int):
        nonlocal paused
        if args[:3] == ["docker", "inspect", "--format"]:
            return subprocess.CompletedProcess(
                args, 0, stdout=f"true {'true' if paused else 'false'}\n", stderr=""
            ), ""
        if args[:2] == ["docker", "pause"]:
            paused = True
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:3] == ["docker", "commit", "--pause=false"]:
            commit_timeouts.append(timeout_s)
            return subprocess.CompletedProcess(args, 0, stdout="sha256:snapshot\n", stderr=""), ""
        if args[:2] == ["docker", "unpause"]:
            paused = False
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(args, 0, stdout="container-id\n", stderr=""), ""
        if args[:2] == ["docker", "exec"]:
            if "test" in args and "-f" in args:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
            return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr=""), ""
        if args[:3] == ["docker", "rm", "-f"] or args[:3] == ["docker", "image", "rm"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:2] == ["docker", "inspect"] or args[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="not found"), ""
        raise AssertionError(args)

    monkeypatch.setattr(HarborEnvironmentExecutor, "_docker_host_call", staticmethod(fake_host_call))
    monkeypatch.setattr("aether.harbor_executor.remaining_verifier_generation_s", lambda: 7200.0)

    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        result = executor.run_independent_verifier_command(
            "true",
            workspace_root="/app.verifier_overlay_deadbeef.command_cafebabe",
            timeout_s=30,
        )
        assert result.get("error") in (None, "")
        assert result["metadata"]["snapshot_timeout_s"] == 600
        assert result["metadata"]["snapshot_elapsed_s"] >= 0
        assert paused is False

    _run_docker_scenario(scenario)
    assert commit_timeouts == [600]


def test_harbor_verifier_snapshot_timeout_preserves_short_deadline_headroom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("aether.harbor_executor.remaining_verifier_generation_s", lambda: 100.0)
    from aether.harbor_executor import _verifier_snapshot_timeout_s
    assert _verifier_snapshot_timeout_s() == 70


def test_docker_foreground_process_streams_remain_bound_to_exact_parent_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = "a" * 64
    calls: list[list[str]] = []
    environment_download_calls: list[str] = []

    def fake_host_call(args: list[str], *, timeout_s: int):
        del timeout_s
        calls.append(list(args))
        if args[:2] == ["docker", "exec"]:
            command = args[-1]
            if command == "uname -m":
                return subprocess.CompletedProcess(args, 0, stdout="x86_64\n", stderr=""), ""
            if "__ALIVE__" in command:
                stdout = "\n".join([
                    "__ALIVE__false",
                    "__EXIT__0",
                    "__AETHER_CHILD_STDOUT_BEGIN__",
                    "",
                    "__AETHER_CHILD_STDERR_BEGIN__",
                    "",
                ])
                return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=""), ""
            if "nohup setsid" in command:
                return subprocess.CompletedProcess(args, 0, stdout="4321\n", stderr=""), ""
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:2] == ["docker", "cp"]:
            source, target = args[2], args[3]
            if source.startswith(owner + ":"):
                destination = Path(target)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text("ok\n" if source.endswith("/stdout.log") else "", encoding="utf-8")
            else:
                assert target.startswith(owner + ":"), target
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        raise AssertionError(args)

    monkeypatch.setattr(HarborEnvironmentExecutor, "_docker_host_call", staticmethod(fake_host_call))

    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        async def wrong_owner_download(source: str, destination: Path) -> None:
            del destination
            environment_download_calls.append(source)
            raise RuntimeError("compose alias resolved to verifier helper")

        executor.environment.download_file = wrong_owner_download
        result = executor.run_command("printf ok", timeout_s=2)
        assert result.exit_code == 0
        assert result.stdout == "ok\n"
        assert result.provenance == ("harbor:subreaper_descendant_tree",)

    _run_docker_scenario(scenario)
    assert environment_download_calls == []
    stream_copies = [
        row for row in calls
        if row[:2] == ["docker", "cp"] and row[2].startswith(owner + ":")
    ]
    assert len(stream_copies) == 2
    assert all(row[2].startswith(owner + ":") for row in stream_copies)
    exact_execs = [row for row in calls if row[:2] == ["docker", "exec"]]
    assert exact_execs
    assert all(owner in row for row in exact_execs)


def test_verifier_cleanup_inspect_backend_failure_does_not_prove_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paused = False

    def fake_host_call(args: list[str], *, timeout_s: int):
        nonlocal paused
        del timeout_s
        if args[:3] == ["docker", "inspect", "--format"]:
            return subprocess.CompletedProcess(
                args, 0, stdout=f"true {'true' if paused else 'false'}\n", stderr=""
            ), ""
        if args[:2] == ["docker", "pause"]:
            paused = True
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:3] == ["docker", "commit", "--pause=false"]:
            return subprocess.CompletedProcess(args, 0, stdout="sha256:snapshot\n", stderr=""), ""
        if args[:2] == ["docker", "unpause"]:
            paused = False
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:3] == ["docker", "run", "--detach"]:
            return subprocess.CompletedProcess(args, 0, stdout="cid\n", stderr=""), ""
        if args[:2] == ["docker", "exec"]:
            return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr=""), ""
        if args[:3] == ["docker", "rm", "-f"] or args[:3] == ["docker", "image", "rm"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:2] == ["docker", "inspect"]:
            # Daemon/permission failure is not evidence that the sibling is gone.
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="permission denied"), ""
        if args[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="No such image"), ""
        raise AssertionError(args)

    monkeypatch.setattr(HarborEnvironmentExecutor, "_docker_host_call", staticmethod(fake_host_call))
    monkeypatch.setattr(
        HarborEnvironmentExecutor,
        "_harbor_docker_main_container_id",
        lambda self: ("a" * 64, ""),
    )
    monkeypatch.setattr(
        HarborEnvironmentExecutor,
        "_wait_for_docker_container_runnable",
        lambda self, cid, timeout_s=10.0: (True, "", 1),
    )

    def scenario(executor: HarborEnvironmentExecutor, _root: Path) -> None:
        result = executor.run_independent_verifier_command(
            "true", workspace_root="/app.verifier_overlay_deadbeef.command_cafebabe"
        )
        assert result["metadata"]["sibling_container_removed"] is False
        assert result["metadata"]["snapshot_image_removed"] is True
        assert result["metadata"]["isolation_cleanup_verified"] is False
        assert "docker_cleanup_failed" in result["error"]
        assert "permission denied" in result["metadata"]["sibling_inspect_error"]

    _run_docker_scenario(scenario)

"""Generation-bound process and service obligation tests."""
from __future__ import annotations

import hashlib
import json
import platform
import socket
import subprocess
import time
from types import SimpleNamespace
from typing import Any

import pytest

from aether.execution import MemoryExecutor, ProcessHandle, ProcessOrchestratorV2
from aether.ledger import ExecutionLedger, Receipt
from aether.runners.docker_exec_executor import DockerExecExecutor
from aether.runtime_ir import ActionRequest, ObjectiveGraph, ProofObligation


def _action(kind: str, arguments: dict[str, Any], action_id: str) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id="managed_process",
        arguments=arguments,
        intent="manage one service generation",
        expected_observation="exact process identity",
        if_fail_next="report blocker",
    )


def _ledger() -> ExecutionLedger:
    ledger = ExecutionLedger()
    ledger.ensure_objective(ObjectiveGraph(obligations=(
        ProofObligation("service:web", "service", "web service is current and live", "web"),
    )))
    return ledger


def test_memory_launch_receipt_contains_real_generation_identity() -> None:
    executor = MemoryExecutor(workspace_root="/app")
    receipt = ProcessOrchestratorV2().launch(
        _action("launch_process", {"service_name": "web", "command": "serve"}, "launch"),
        0,
        executor,
        workspace_root="/app",
        interactive=False,
    )
    assert receipt.success is True
    assert receipt.payload["pid"] is not None
    assert receipt.payload["start_time_ticks"]
    assert receipt.payload["command_sha256"] == hashlib.sha256(b"serve").hexdigest()
    assert receipt.payload["process_generation"]
    assert receipt.payload["process_id"] == f"process:{receipt.payload['process_generation']}"


def test_unowned_listener_cannot_satisfy_service_obligation() -> None:
    ledger = _ledger()
    ledger.record(Receipt(
        receipt_id="probe:unowned",
        step=1,
        kind="service_probe",
        success=True,
        summary="port is open but owner is unknown",
        payload={
            "service_name": "web",
            "target": "8080",
            "live": True,
            "process_generation_verified": False,
            "endpoint_owner_pids": [999],
        },
    ))
    assert ledger.obligations["service:web"].status == "open"


def test_verified_probe_satisfies_only_current_process_generation() -> None:
    executor = MemoryExecutor(workspace_root="/app")
    orchestrator = ProcessOrchestratorV2()
    ledger = _ledger()

    launch1 = orchestrator.launch(
        _action("launch_process", {"service_name": "web", "command": "serve-v1"}, "launch-1"),
        0, executor, workspace_root="/app", interactive=False,
    )
    ledger.record(launch1)
    probe1 = orchestrator.probe(
        _action("probe_service", {"target": "web"}, "probe-1"), 1, executor,
    )
    ledger.record(probe1)
    assert ledger.obligations["service:web"].status == "satisfied"
    generation1 = launch1.payload["process_generation"]

    launch2 = orchestrator.launch(
        _action("launch_process", {"service_name": "web", "command": "serve-v2"}, "launch-2"),
        2, executor, workspace_root="/app", interactive=False,
    )
    ledger.record(launch2)
    assert launch2.payload["process_generation"] != generation1
    assert ledger.obligations["service:web"].status == "open"

    # A late probe receipt from the old generation cannot re-satisfy it.
    ledger.record(Receipt(
        receipt_id="probe:old-late",
        step=3,
        kind="service_probe",
        success=True,
        summary="old generation reported live",
        payload={
            "service_name": "web",
            "process_id": launch1.payload["process_id"],
            "process_generation": generation1,
            "process_generation_verified": True,
            "live": True,
        },
    ))
    assert ledger.obligations["service:web"].status == "open"

    probe2 = orchestrator.probe(
        _action("probe_service", {"target": "web"}, "probe-2"), 4, executor,
    )
    ledger.record(probe2)
    assert probe2.payload["process_generation"] == launch2.payload["process_generation"]
    assert ledger.obligations["service:web"].status == "satisfied"


def test_stop_reopens_service_obligation_and_marks_current_generation_dead() -> None:
    executor = MemoryExecutor(workspace_root="/app")
    orchestrator = ProcessOrchestratorV2()
    ledger = _ledger()
    launch = orchestrator.launch(
        _action("launch_process", {"service_name": "web", "command": "serve"}, "launch"),
        0, executor, workspace_root="/app", interactive=False,
    )
    ledger.record(launch)
    ledger.record(orchestrator.probe(
        _action("probe_service", {"target": "web"}, "probe"), 1, executor,
    ))
    assert ledger.obligations["service:web"].status == "satisfied"

    stop = orchestrator.stop(
        _action("stop_process", {"target": "web"}, "stop"), 2, executor,
    )
    ledger.record(stop)
    assert ledger.obligations["service:web"].status == "open"
    assert ledger.live_processes() == {}


def test_docker_launch_uses_real_pid_start_and_command_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, stdout="321\t9988\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    executor = DockerExecExecutor("container-abcdef", str(tmp_path))
    handle = executor.launch_process("web", "python3 server.py")

    assert handle.live is True
    assert handle.pid == 321
    assert handle.start_time_ticks == "9988"
    assert handle.command_sha256 == hashlib.sha256(b"python3 server.py").hexdigest()
    assert handle.process_generation
    assert handle.process_id == f"process:{handle.process_generation}"
    assert "docker" in calls[0][0]
    assert "-d" not in calls[0], "launch must return the actual child identity, not detached-exec fiction"


def test_docker_endpoint_probe_reports_live_but_unverified_for_unregistered_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="AETHER_TCP\t1\t777\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    probe = DockerExecExecutor("container", str(tmp_path)).probe_process("127.0.0.1:5328")
    assert probe.live is True
    assert probe.endpoint_owner_pids == (777,)
    assert probe.process_generation_verified is False
    assert probe.process_generation == ""


def test_docker_endpoint_probe_binds_registered_owner_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    executor = DockerExecExecutor("container", str(tmp_path))
    handle = ProcessHandle(
        process_id="process:gen1",
        name="web",
        command="serve",
        live=True,
        pid=777,
        start_time_ticks="99",
        command_sha256="cmd",
        process_generation="gen1",
    )
    executor._process_registry[handle.process_id] = handle
    responses = iter((
        subprocess.CompletedProcess([], 0, stdout="AETHER_TCP\t1\t777\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout="AETHER_GEN\t99\n", stderr=""),
    ))
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: next(responses))

    probe = executor.probe_process("127.0.0.1:5328")
    assert probe.live is True
    assert probe.service_name == "web"
    assert probe.process_id == "process:gen1"
    assert probe.process_generation == "gen1"
    assert probe.process_generation_verified is True


def test_docker_endpoint_probe_binds_registered_descendant_owner_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    executor = DockerExecExecutor("container", str(tmp_path))
    handle = ProcessHandle(
        process_id="process:gen1", name="web", command="serve", live=True,
        pid=777, start_time_ticks="99", command_sha256="cmd",
        process_generation="gen1",
    )
    executor._process_registry[handle.process_id] = handle
    responses = iter((
        subprocess.CompletedProcess([], 0, stdout="AETHER_TCP\t1\t888\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout="AETHER_GEN\t99\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    ))
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: next(responses))

    probe = executor.probe_process("127.0.0.1:5328")
    assert probe.live is True
    assert probe.endpoint_owner_pids == (888,)
    assert probe.service_name == "web"
    assert probe.process_id == "process:gen1"
    assert probe.process_generation == "gen1"
    assert probe.process_generation_verified is True


def test_docker_launch_registers_nonce_owned_status_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, stdout="321\t9988\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    executor = DockerExecExecutor("container-abcdef", str(tmp_path))
    handle = executor.launch_process("finite", "sleep 1; exit 0")

    assert handle.status_log.startswith("/tmp/aether-processes/")
    assert handle.status_log.endswith(".status")
    assert handle.status == "running"
    command = calls[0]
    assert handle.status_log in command
    wrapper = command[command.index("-lc") + 1]
    assert 'rm -f "$4"' in wrapper
    assert 'printf "%s\\n" "$rc"' in wrapper


def test_docker_probe_job_uses_registered_generation_not_task_writable_status_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    executor = DockerExecExecutor("container", str(tmp_path))
    handle = ProcessHandle(
        process_id="process:gen1", name="finite", command="work", live=True,
        pid=777, start_time_ticks="99", command_sha256="cmd",
        process_generation="gen1", status_log="/tmp/aether-processes/a.status",
        status="running",
    )
    executor._process_registry[handle.process_id] = handle
    calls: list[list[str]] = []
    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(
            [], 0, stdout="AETHER_GEN\t\n", stderr="",
        )
    monkeypatch.setattr(subprocess, "run", fake_run)

    probe = executor.probe_job(handle.process_id)
    assert probe.found is True
    assert probe.status == "exited"
    assert probe.completed is True
    assert probe.succeeded is None
    assert probe.exit_code is None
    assert probe.process_generation == "gen1"
    assert probe.process_generation_verified is True
    assert probe.lifecycle_authority == "registered_process_generation"
    probe_code = calls[0][calls[0].index("-lc") + 1]
    assert "status_path" not in probe_code
    assert handle.status_log not in probe_code
    assert "python3" not in calls[0]


def _free_tcp_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_subprocess_endpoint_probe_observes_and_binds_registered_listener(tmp_path) -> None:
    from aether.real_executor import SubprocessExecutor

    port = _free_tcp_port()
    executor = SubprocessExecutor(str(tmp_path))
    command = (
        "exec python3 -c \"import socket,time; "
        f"s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); "
        f"s.bind(('127.0.0.1',{port})); s.listen(); time.sleep(30)\""
    )
    handle = executor.launch_process("web", command)
    try:
        probe = None
        for _ in range(100):
            probe = executor.probe_process(f"127.0.0.1:{port}")
            if probe.live:
                break
            time.sleep(0.02)
        assert probe is not None and probe.live is True
        if platform.system() == "Linux":
            assert probe.service_name == "web"
            assert probe.process_id == handle.process_id
            assert probe.process_generation == handle.process_generation
            assert probe.process_generation_verified is True
            assert handle.pid in probe.endpoint_owner_pids
        else:
            assert probe.process_generation_verified is False
    finally:
        executor.stop_process(handle.process_id)


def test_subprocess_endpoint_probe_reports_unowned_listener_without_generation(tmp_path) -> None:
    from aether.real_executor import SubprocessExecutor

    port = _free_tcp_port()
    process = subprocess.Popen([
        "python3", "-c",
        (
            "import socket,time; "
            f"s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); "
            f"s.bind(('127.0.0.1',{port})); s.listen(); time.sleep(30)"
        ),
    ])
    try:
        executor = SubprocessExecutor(str(tmp_path))
        probe = None
        for _ in range(100):
            probe = executor.probe_process(str(port))
            if probe.live:
                break
            time.sleep(0.02)
        assert probe is not None and probe.live is True
        assert probe.process_generation_verified is False
        assert probe.process_generation == ""
        assert probe.process_id == ""
    finally:
        process.terminate()
        process.wait(timeout=5)

from __future__ import annotations

from types import SimpleNamespace

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.execution import (
    CommandResult, TerminalReadResult, TerminalSessionHandle, TerminalSessionState,
)
from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger, Receipt
from aether.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    EnvMap,
    RuntimeConfigIR,
)


class FakeExecutor:
    def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30):
        del cwd, timeout_s
        return CommandResult(
            command=command,
            exit_code=0,
            stdout="done",
            removed_paths=("critical.asset",),
            state_delta={
                "before_digest": "before",
                "after_digest": "after",
                "removed_paths": ["critical.asset"],
                "created_paths": [],
                "content_changed_paths": [],
                "metadata_changed_paths": [],
                "mutation_actor_status": "mutation_actor_unknown",
            },
        )


class IntegrityGuard:
    def __init__(self) -> None:
        self.seen: tuple[str, ...] = ()

    def validate_modified_paths(self, objective, paths):
        del objective
        self.seen = tuple(paths)
        return "protected path removed" if "critical.asset" in self.seen else None


def _compiled():
    env = EnvMap(
        task_prompt="preserve state",
        workspace_root="/app",
        capabilities={
            "shell": CapabilityDescriptor("shell", "commands", tool_names=("run_command",)),
            "filesystem": CapabilityDescriptor("filesystem", "files", tool_names=("read_file", "write_file")),
        },
    )
    ir = RuntimeConfigIR(
        architect_summary="run command",
        solver_identity_prompt="work carefully",
        selected_capabilities=("shell", "filesystem"),
        inspection_plan=("inspect",),
        proof_plan=("check",),
    )
    return ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(ir, env), env


def test_run_command_receipt_retains_removed_paths_and_state_delta() -> None:
    compiled, env = _compiled()
    guard = IntegrityGuard()
    kernel = SimpleNamespace(
        failure_parser=SimpleNamespace(classify=lambda *args, **kwargs: ""),
        integrity_guards=guard,
    )
    action = ActionRequest(
        action_id="cmd",
        kind="run_command",
        capability_id="shell",
        arguments={"command": "mutate"},
        intent="exercise command",
        expected_observation="state delta",
        if_fail_next="inspect",
    )
    receipt = dispatch_action(
        kernel, action, 1, compiled, FakeExecutor(), env, ExecutionLedger()
    )[0]
    assert receipt.state_change is True
    assert receipt.payload["removed_paths"] == ("critical.asset",)
    assert receipt.payload["state_delta"]["before_digest"] == "before"
    assert receipt.payload["state_delta"]["mutation_actor_status"] == "mutation_actor_unknown"
    assert guard.seen == ("critical.asset",)
    assert receipt.payload["integrity_violation"] == "protected path removed"



class FakeTerminalExecutor(FakeExecutor):
    def start_terminal_session(self, name: str, command: str, *, cwd: str | None = None):
        del cwd
        return TerminalSessionHandle(
            session_id="terminal:abc",
            name=name,
            command=command,
            live=True,
            pid=77,
            start_time_ticks="123",
            command_sha256="deadbeef",
            process_generation="gen-1",
            transcript_path="/tmp/raw.pty",
            state_delta={"created_paths": [], "removed_paths": [], "content_changed_paths": [], "metadata_changed_paths": []},
        )

    def terminal_read(self, session_id: str, *, max_bytes: int = 20_000, wait_ms: int = 1000):
        del max_bytes, wait_ms
        return TerminalReadResult(
            session_id=session_id,
            output="READY\n",
            bytes_read=6,
            cursor=6,
            total_bytes=6,
            more_available=False,
            live=True,
            process_generation="gen-1",
            state_delta={"created_paths": ["result.txt"], "removed_paths": [], "content_changed_paths": [], "metadata_changed_paths": []},
        )

    def terminal_send(self, session_id: str, data: str, *, append_newline: bool = True):
        del data, append_newline
        return TerminalSessionState(
            session_id=session_id,
            live=True,
            bytes_sent=4,
            process_generation="gen-1",
            state_delta={"created_paths": [], "removed_paths": [], "content_changed_paths": [], "metadata_changed_paths": []},
        )

    def terminal_wait(self, session_id: str, *, timeout_s: float = 30.0):
        del timeout_s
        return TerminalSessionState(session_id=session_id, live=False, exit_code=0, process_generation="gen-1")

    def terminal_interrupt(self, session_id: str):
        return TerminalSessionState(session_id=session_id, live=True, signal="SIGINT", process_generation="gen-1")

    def terminal_close(self, session_id: str):
        return TerminalSessionState(session_id=session_id, live=False, exit_code=143, process_generation="gen-1")


def _terminal_action(kind: str, arguments: dict[str, object]) -> ActionRequest:
    return ActionRequest(
        action_id=f"a-{kind}",
        kind=kind,
        capability_id="shell",
        arguments=arguments,
        intent="exercise generic terminal primitive",
        expected_observation="mechanical terminal state",
        if_fail_next="report observed failure",
    )


def test_terminal_dispatch_preserves_generation_and_mechanical_delta() -> None:
    compiled, env = _compiled()
    executor = FakeTerminalExecutor()
    kernel = SimpleNamespace()
    started = dispatch_action(
        kernel,
        _terminal_action("start_terminal_session", {"session_name": "x", "command": "echo hi"}),
        1,
        compiled,
        executor,
        env,
        ExecutionLedger(),
    )[0]
    assert started.success is True
    assert started.payload["session_id"] == "terminal:abc"
    assert started.payload["process_generation"] == "gen-1"
    assert started.state_change is False

    read = dispatch_action(
        kernel,
        _terminal_action("terminal_read", {"session_id": "terminal:abc"}),
        2,
        compiled,
        executor,
        env,
        ExecutionLedger(),
    )[0]
    assert read.success is True
    assert read.payload["output"] == "READY\n"
    assert read.payload["cursor"] == 6
    assert read.payload["process_generation"] == "gen-1"
    assert read.state_change is True
    assert read.payload["state_delta"]["created_paths"] == ["result.txt"]


def test_terminal_dispatch_fails_closed_without_crashing_loop() -> None:
    compiled, env = _compiled()

    class MissingTerminal(FakeTerminalExecutor):
        def terminal_send(self, session_id: str, data: str, *, append_newline: bool = True):
            raise KeyError(session_id)

    receipt = dispatch_action(
        SimpleNamespace(),
        _terminal_action("terminal_send", {"session_id": "missing", "data": "x"}),
        3,
        compiled,
        MissingTerminal(),
        env,
        ExecutionLedger(),
    )[0]
    assert receipt.success is False
    assert receipt.failure_class == "service_not_ready"
    assert receipt.payload["error_type"] == "KeyError"



def test_terminal_session_remains_first_class_live_state_until_close() -> None:
    compiled, env = _compiled()
    executor = FakeTerminalExecutor()
    ledger = ExecutionLedger()
    started = dispatch_action(
        SimpleNamespace(),
        _terminal_action("start_terminal_session", {"session_name": "x", "command": "echo hi"}),
        1, compiled, executor, env, ledger,
    )[0]
    ledger.record(started)
    ledger.record(Receipt(
        receipt_id="unrelated", step=2, kind="read_file", success=True,
        summary="unrelated observation", payload={"path": "other.txt"},
    ))
    live = ledger.live_processes()
    assert "terminal:abc" in live
    assert live["terminal:abc"]["kind"] == "terminal_session"
    assert live["terminal:abc"]["process_generation"] == "gen-1"

    read = dispatch_action(
        SimpleNamespace(),
        _terminal_action("terminal_read", {"session_id": "terminal:abc"}),
        3, compiled, executor, env, ledger,
    )[0]
    ledger.record(read)
    assert ledger.live_processes()["terminal:abc"]["cursor"] == 6

    closed = dispatch_action(
        SimpleNamespace(),
        _terminal_action("terminal_close", {"session_id": "terminal:abc"}),
        4, compiled, executor, env, ledger,
    )[0]
    ledger.record(closed)
    assert "terminal:abc" not in ledger.live_processes()

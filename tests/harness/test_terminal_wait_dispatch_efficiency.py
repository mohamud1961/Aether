from __future__ import annotations

from types import SimpleNamespace

from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger
from aether.runtime_ir import ActionRequest, EnvMap


def _action(kind: str, arguments: dict[str, object]) -> ActionRequest:
    return ActionRequest(
        action_id=f"test-{kind}",
        kind=kind,
        capability_id="persistent_terminal",
        arguments=arguments,
        intent="test dispatch semantics",
        expected_observation="bounded terminal state",
        if_fail_next="stop",
    )


class _TerminalExecutor:
    def __init__(self) -> None:
        self.read_wait_ms: int | None = None
        self.wait_timeout_s: float | None = None

    def terminal_read(self, session_id: str, *, max_bytes: int, wait_ms: int):
        self.read_wait_ms = wait_ms
        return SimpleNamespace(
            session_id=session_id,
            output="",
            bytes_read=0,
            cursor=0,
            total_bytes=0,
            more_available=False,
            live=True,
            exit_code=None,
            process_generation="gen-1",
            state_delta={},
        )

    def terminal_wait(self, session_id: str, *, timeout_s: float):
        self.wait_timeout_s = timeout_s
        return SimpleNamespace(
            session_id=session_id,
            live=True,
            exit_code=None,
            cursor=0,
            total_bytes=0,
            more_available=False,
            process_generation="gen-1",
            state_delta={},
        )


def _dispatch(executor: _TerminalExecutor, kind: str, arguments: dict[str, object]):
    return dispatch_action(
        SimpleNamespace(),
        _action(kind, arguments),
        0,
        SimpleNamespace(),
        executor,
        EnvMap(task_prompt="test", workspace_root="/app", capabilities={}),
        ExecutionLedger(),
    )


def test_terminal_read_preserves_explicit_zero_wait() -> None:
    executor = _TerminalExecutor()
    receipts = _dispatch(
        executor,
        "terminal_read",
        {"session_id": "session-1", "max_bytes": 1024, "wait_ms": 0},
    )
    assert receipts[0].success is True
    assert executor.read_wait_ms == 0


def test_terminal_wait_preserves_explicit_zero_timeout() -> None:
    executor = _TerminalExecutor()
    receipts = _dispatch(
        executor,
        "terminal_wait",
        {"session_id": "session-1", "timeout_s": 0},
    )
    assert receipts[0].success is True
    assert executor.wait_timeout_s == 0.0


def test_terminal_defaults_still_apply_when_fields_are_omitted() -> None:
    executor = _TerminalExecutor()
    _dispatch(executor, "terminal_read", {"session_id": "session-1"})
    _dispatch(executor, "terminal_wait", {"session_id": "session-1"})
    assert executor.read_wait_ms == 1000
    assert executor.wait_timeout_s == 30.0

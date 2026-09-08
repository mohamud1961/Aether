"""PCR V0 task-local helper-tool creation, smoke testing, and provenance."""
from __future__ import annotations

from aether.execution import CommandResult, MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.pcr_provider_protocol import validate_pcr_inner_turn
from aether.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    EnvMap,
    SolverTurn,
)
from aether.tracing import RunTrace


HELPER_PATH = ".aether/tools/helper.py"
SMOKE_COMMAND = f"python {HELPER_PATH} --self-test"
EXECUTE_COMMAND = f"python {HELPER_PATH} input.txt"


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Use a task-local helper, then independently verify output.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files",
                tool_names=("read_file", "write_file"),
            ),
            "shell": CapabilityDescriptor(
                "shell", "local commands",
                tool_names=("run_command",),
            ),
        },
    )


def _action(
    kind: str,
    arguments: dict[str, object],
    *,
    action_id: str,
    capability_id: str,
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id=capability_id,
        arguments=arguments,
        intent="",
        expected_observation="",
        if_fail_next="",
    )


class _Hooks:
    verify = None

    def __init__(self, turns: list[SolverTurn]) -> None:
        self.turns = list(turns)

    def solve(self, messages, compiled):
        del messages, compiled
        return self.turns.pop(0)


def _write_turn(content: str, action_id: str = "write-helper") -> SolverTurn:
    return SolverTurn(
        kind="act",
        summary="write helper",
        actions=(_action(
            "write_file", {"path": HELPER_PATH, "content": content},
            action_id=action_id, capability_id="filesystem",
        ),),
    )


def _helper_command_turn(
    command: str,
    mode: str,
    action_id: str,
    *,
    path: str = HELPER_PATH,
) -> SolverTurn:
    return SolverTurn(
        kind="act",
        summary=f"helper {mode}",
        actions=(_action(
            "run_command",
            {
                "command": command,
                "helper_path": path,
                "helper_mode": mode,
            },
            action_id=action_id,
            capability_id="shell",
        ),),
    )


def _observation_turn(action_id: str = "observe") -> SolverTurn:
    return SolverTurn(
        kind="act",
        summary="observe helper state through an ordinary file read",
        actions=(_action(
            "read_file", {"path": "input.txt"},
            action_id=action_id, capability_id="filesystem",
        ),),
    )


def _executor() -> MemoryExecutor:
    executor = MemoryExecutor(
        workspace_root="/app",
        files={"input.txt": "input"},
    )
    executor.register_command(
        SMOKE_COMMAND,
        lambda _executor, command: CommandResult(
            command, 0, stdout="self-test: ok"
        ),
    )
    executor.register_command(
        EXECUTE_COMMAND,
        lambda _executor, command: CommandResult(
            command, 0, stdout="helper result"
        ),
    )
    return executor


def test_provider_contract_has_explicit_helper_smoke_and_execute_modes() -> None:
    for mode in ("smoke_test", "execute"):
        turn = validate_pcr_inner_turn({
            "kind": "act",
            "action": {
                "kind": "run_command",
                "arguments": {
                    "command": SMOKE_COMMAND if mode == "smoke_test" else EXECUTE_COMMAND,
                    "helper_path": HELPER_PATH,
                    "helper_mode": mode,
                },
            },
        })
        assert turn["action"]["arguments"]["helper_mode"] == mode


def test_helper_requires_smoke_test_then_executes_exact_generation() -> None:
    executor = _executor()
    trace = RunTrace()
    turns = [
        _write_turn("print('v1')"),
        _helper_command_turn(EXECUTE_COMMAND, "execute", "execute-too-early"),
        _helper_command_turn(SMOKE_COMMAND, "smoke_test", "smoke"),
        _helper_command_turn(EXECUTE_COMMAND, "execute", "execute"),
        _observation_turn(),
    ]

    result = AetherNextKernel(max_steps=5).run(
        _env(), executor, _Hooks(turns), trace=trace,
    )

    assert executor.command_history == [SMOKE_COMMAND, EXECUTE_COMMAND]
    creations = [
        receipt for receipt in result.receipts
        if receipt.kind == "pcr_helper_tool_created"
    ]
    assert len(creations) == 1
    generation = creations[0].payload["helper_generation"]
    blocked = [
        receipt for receipt in result.receipts
        if receipt.failure_class == "helper_smoke_test_required"
    ]
    assert len(blocked) == 1
    smoke = next(
        receipt for receipt in result.receipts
        if receipt.kind == "pcr_helper_smoke_test"
    )
    execution = next(
        receipt for receipt in result.receipts
        if receipt.kind == "pcr_helper_execution"
    )
    assert smoke.success is True
    assert smoke.payload["helper_generation"] == generation
    assert execution.success is True
    assert execution.payload["helper_generation"] == generation
    assert execution.payload["smoke_test_receipt_id"] == smoke.receipt_id
    assert execution.payload["helper_output_trust_for_completion"] is False

    context = trace.steps[4]["context_seen"]
    helper = context["self_extension"]["current_helpers"][0]
    assert helper["path"] == HELPER_PATH
    assert helper["helper_generation"] == generation
    assert helper["smoke_test_status"] == "passed"
    assert helper["latest_execution_receipt_id"] == execution.receipt_id
    assert context["self_extension"]["trust_for_completion"] is False

    # Helper source and helper command output are visible as causal results but
    # never enter the completion evidence alias set.
    evidence_receipts = {
        row["receipt_id"] for row in context["evidence_index"]
    }
    helper_command_receipts = {
        receipt.receipt_id for receipt in result.receipts
        if receipt.kind == "run_command"
        and receipt.payload.get("helper_mode")
    }
    helper_write = next(
        receipt for receipt in result.receipts
        if receipt.kind == "write_file"
        and receipt.payload.get("helper_tool_artifact")
    )
    assert helper_write.receipt_id not in evidence_receipts
    assert helper_command_receipts.isdisjoint(evidence_receipts)


def test_rewriting_helper_invalidates_old_smoke_test() -> None:
    executor = _executor()
    turns = [
        _write_turn("print('v1')", "write-v1"),
        _helper_command_turn(SMOKE_COMMAND, "smoke_test", "smoke-v1"),
        _write_turn("print('v2')", "write-v2"),
        _helper_command_turn(EXECUTE_COMMAND, "execute", "execute-v2"),
    ]

    result = AetherNextKernel(max_steps=4).run(
        _env(), executor, _Hooks(turns),
    )

    assert executor.command_history == [SMOKE_COMMAND]
    creations = [
        receipt for receipt in result.receipts
        if receipt.kind == "pcr_helper_tool_created"
    ]
    assert len(creations) == 2
    assert (
        creations[0].payload["helper_generation"]
        != creations[1].payload["helper_generation"]
    )
    blocked = next(
        receipt for receipt in result.receipts
        if receipt.failure_class == "helper_smoke_test_required"
    )
    assert (
        blocked.payload["helper_generation"]
        == creations[1].payload["helper_generation"]
    )


def test_registered_helper_cannot_silently_bypass_lifecycle_metadata() -> None:
    executor = _executor()
    turns = [
        _write_turn("print('v1')"),
        SolverTurn(
            kind="act",
            summary="attempt undeclared helper execution",
            actions=(_action(
                "run_command", {"command": EXECUTE_COMMAND},
                action_id="silent-bypass", capability_id="shell",
            ),),
        ),
    ]

    result = AetherNextKernel(max_steps=2).run(
        _env(), executor, _Hooks(turns),
    )

    assert executor.command_history == []
    refusal = next(
        receipt for receipt in result.receipts
        if receipt.failure_class == "helper_lifecycle_required"
    )
    assert refusal.kind == "action_validation"
    assert refusal.payload["referenced_helper_paths"] == [HELPER_PATH]


def test_declared_helper_path_outside_task_local_directory_is_refused() -> None:
    executor = _executor()
    outside = "helper.py"
    command = "python helper.py --self-test"
    executor.write_file(outside, "print('ok')")
    executor.register_command(
        command,
        lambda _executor, value: CommandResult(value, 0, stdout="ok"),
    )
    turn = _helper_command_turn(
        command, "smoke_test", "outside", path=outside,
    )

    result = AetherNextKernel(max_steps=1).run(
        _env(), executor, _Hooks([turn]),
    )

    assert executor.command_history == []
    refusal = next(
        receipt for receipt in result.receipts
        if receipt.failure_class == "helper_path_invalid"
    )
    assert "outside task-local helper directory" in refusal.summary

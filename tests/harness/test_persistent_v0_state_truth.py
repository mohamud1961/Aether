"""PERSISTENT V0 truthful progress, context-boundary, and deletion-state regressions."""
from __future__ import annotations

from aether.execution import CommandResult, MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_context import _factual_persistent_linked_history
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    DeliverableSpec,
    EnvMap,
    ObjectiveGraph,
    ProofObligation,
    SolverTurn,
)
from aether.task_contract import TaskClause, TaskContract
from aether.tracing import RunTrace
from aether.world import WorldState


def _env(task: str = "Maintain truthful workspace state.") -> EnvMap:
    return EnvMap(
        task_prompt=task,
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


def test_real_executor_reports_deleted_file_and_state_delta(tmp_path) -> None:
    executor = SubprocessExecutor(str(tmp_path))
    executor.write_file("artifact.txt", "present")

    result = executor.run_command("rm artifact.txt")

    assert result.success is True
    assert result.removed_paths == ("artifact.txt",)
    assert result.produced_artifacts == ()
    assert result.modified_paths == ()
    assert result.state_delta == {
        "modified_paths": [],
        "created_paths": [],
        "removed_paths": ["artifact.txt"],
    }
    assert executor.exists("artifact.txt") is False


def test_ledger_removes_deleted_artifact_and_reopens_obligation() -> None:
    ledger = ExecutionLedger()
    objective = ObjectiveGraph(
        deliverables=(DeliverableSpec("artifact.txt"),),
        obligations=(
            ProofObligation(
                "artifact:artifact.txt",
                "artifact",
                "artifact.txt remains present",
                target="artifact.txt",
            ),
        ),
    )
    ledger.ensure_objective(objective)
    ledger.record(Receipt(
        receipt_id="write",
        step=0,
        kind="write_file",
        success=True,
        summary="wrote artifact",
        state_change=True,
        payload={
            "artifact_paths": ("artifact.txt",),
            "modified_paths": ("artifact.txt",),
        },
    ))
    assert ledger.current_artifacts() == {"artifact.txt"}
    assert ledger.open_obligations() == []

    ledger.record(Receipt(
        receipt_id="delete",
        step=1,
        kind="run_command",
        success=True,
        summary="removed artifact",
        state_change=True,
        payload={"removed_paths": ("artifact.txt",)},
    ))

    assert ledger.current_artifacts() == set()
    assert ledger.removed_paths() == ("artifact.txt",)
    assert [item.obligation_id for item in ledger.open_obligations()] == [
        "artifact:artifact.txt"
    ]


def test_kernel_projects_command_deletion_into_world_tombstones() -> None:
    delete_command = "rm artifact.txt"
    executor = MemoryExecutor(workspace_root="/app")

    def delete(executor_: MemoryExecutor, command: str) -> CommandResult:
        executor_.files.pop("artifact.txt", None)
        return CommandResult(
            command,
            0,
            removed_paths=("artifact.txt",),
            state_delta={"removed_paths": ["artifact.txt"]},
        )

    executor.register_command(delete_command, delete)
    hooks = _Hooks([
        SolverTurn(
            kind="act",
            summary="create artifact",
            actions=(_action(
                "write_file",
                {"path": "artifact.txt", "content": "present"},
                action_id="create", capability_id="filesystem",
            ),),
        ),
        SolverTurn(
            kind="act",
            summary="remove artifact",
            actions=(_action(
                "run_command",
                {"command": delete_command},
                action_id="delete", capability_id="shell",
            ),),
        ),
    ])
    world = WorldState(
        task_contract=TaskContract.create(
            "Maintain truthful workspace state.",
            (TaskClause("task:raw", "Maintain truthful workspace state."),),
        )
    )

    AetherNextKernel(max_steps=2, persistent_primary=True).run(
        _env(), executor, hooks, world_state=world,
    )

    snapshot = world.dynamic_snapshot()
    assert "artifact.txt" not in snapshot["files"]
    assert "artifact.txt" not in snapshot["artifacts"]
    assert snapshot["removed_files"] == ["artifact.txt"]
    assert snapshot["removed_artifacts"] == ["artifact.txt"]
    assert snapshot["latest_result"]["status"] == "passed"


def test_persistent_obligation_projection_fails_open_when_views_disagree() -> None:
    linked = {
        "open_obligations": [
            {"obligation_id": "task:a", "status": "open", "description": "A"},
            {"obligation_id": "task:unexpected", "status": "open", "description": "unexpected"},
        ],
        "obligation_status": [
            {"obligation_id": "task:a", "status": "open", "description": "A"},
            {"obligation_id": "task:b", "status": "satisfied", "description": "B"},
        ],
    }
    projected = _factual_persistent_linked_history(linked)
    assert projected["open_obligations"] == linked["open_obligations"]
    assert projected["obligation_status"] == linked["obligation_status"]


def test_persistent_context_does_not_expose_false_stuck_or_legacy_strategy_guidance() -> None:
    command = "printf hello"
    executor = MemoryExecutor(workspace_root="/app")
    executor.register_command(
        command,
        lambda _executor, cmd: CommandResult(cmd, 0, stdout="hello"),
    )
    hooks = _Hooks([
        SolverTurn(
            kind="act",
            summary="observe command output",
            actions=(_action(
                "run_command", {"command": command},
                action_id="observe", capability_id="shell",
            ),),
        ),
        SolverTurn(
            kind="act",
            summary="record second boundary",
            actions=(_action(
                "record_observation", {"observation": "continue from observed output"},
                action_id="continue", capability_id="kernel",
            ),),
        ),
    ])
    trace = RunTrace()

    AetherNextKernel(max_steps=2, persistent_primary=True).run(
        _env(), executor, hooks, trace=trace,
    )

    context = trace.steps[1]["context_seen"]
    linked = context["linked_history"]
    for forbidden in (
        "stuck",
        "automatic_memory_available",
        "automatic_memory_guidance",
        "automatic_memory_findings",
        "memory_loop_feedback",
        "repeat_efficiency_guidance",
        "no_progress_controls",
        "action_constraints",
        "submission_recovery_directive",
        "latest_solver_transition",
    ):
        assert forbidden not in linked
    assert linked["persistent_context_boundary"] == {
        "linked_history_is_factual_projection": True,
        "kernel_strategy_guidance_exposed": False,
        "legacy_automatic_memory_exposed": False,
        "generic_stuck_judgment_exposed": False,
    }
    assert context["latest_primary_result"]["action_kind"] == "run_command"
    assert context["latest_primary_result"]["outcome_receipts"][0]["success"] is True
    assert context["available_capabilities"]["action_owners"]["run_command"] == ["shell"]
    assert set(context["available_capabilities"]) == {"action_owners"}
    # Full obligation status exactly carries open/satisfied state; PERSISTENT does not
    # repeat the open subset as a second model-visible copy.
    assert "open_obligations" not in linked
    assert linked["obligation_status"]

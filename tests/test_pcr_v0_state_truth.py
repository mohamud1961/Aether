"""PCR V0 truthful progress, context-boundary, and deletion-state regressions."""
from __future__ import annotations

from aether.execution import CommandResult, MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.kernel_turns import _observed_changed_paths_projection
from aether.ledger import ExecutionLedger, Receipt
from aether.pcr_context import (
    _factual_pcr_linked_history,
    _mechanically_unresolved_failures,
)
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
    assert result.state_delta["created_paths"] == []
    assert result.state_delta["removed_paths"] == ["artifact.txt"]
    assert result.state_delta["mutation_detection_status"] == "complete"
    assert result.state_delta["path_set_delta_status"] == "complete"
    assert result.state_delta["before_truncated"] is False
    assert result.state_delta["after_truncated"] is False
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

    AetherNextKernel(max_steps=2).run(
        _env(), executor, hooks, world_state=world,
    )

    snapshot = world.dynamic_snapshot()
    assert "artifact.txt" not in snapshot["files"]
    assert "artifact.txt" not in snapshot["artifacts"]
    assert snapshot["removed_files"] == ["artifact.txt"]
    assert snapshot["removed_artifacts"] == ["artifact.txt"]
    assert snapshot["latest_result"]["status"] == "passed"


def test_kernel_projects_observed_mutations_without_claiming_complete_external_state() -> None:
    command = "mutate several workspace paths"
    executor = MemoryExecutor(workspace_root="/app")
    executor.register_command(
        command,
        lambda _executor, cmd: CommandResult(
            cmd,
            0,
            modified_paths=("existing.txt",),
            produced_artifacts=("output.txt", "rmain"),
            removed_paths=("old.txt",),
            state_delta={
                "mutation_detection_status": "coarse",
                "generated_residue_paths": ["rmain"],
            },
        ),
    )
    hooks = _Hooks([
        SolverTurn(
            kind="act",
            summary="make observed changes",
            actions=(_action(
                "run_command", {"command": command},
                action_id="mutate", capability_id="shell",
            ),),
        ),
    ])
    world = WorldState(task_contract=TaskContract.create(
        "Maintain truthful workspace state.",
        (TaskClause("task:raw", "Maintain truthful workspace state."),),
    ))

    AetherNextKernel(max_steps=1).run(
        _env(), executor, hooks, world_state=world,
    )

    observed = world.dynamic_snapshot()["named_sections"]["observed_changed_paths"]
    assert observed["created"] == ["output.txt", "rmain"]
    assert observed["modified"] == ["existing.txt"]
    assert observed["removed"] == ["old.txt"]
    assert observed["generated_residue"] == ["rmain"]
    assert observed["read"] == []
    assert observed["external_state_unknown"] is True
    assert observed["content_hash_availability"] == "unknown_without_captured_bytes"


def test_observed_path_projection_names_receipt_backed_reads_without_inferring_them() -> None:
    world = WorldState(task_contract=TaskContract.create(
        "Keep state factual.", (TaskClause("task:raw", "Keep state factual."),),
    ))
    ledger = ExecutionLedger()
    receipt = Receipt(
        receipt_id="step-1:read:read",
        step=1,
        kind="read_file",
        success=True,
        summary="read source",
        payload={"path": "src/main.py"},
    )

    projected = _observed_changed_paths_projection(world, receipt, receipt.payload, ledger)

    assert projected is not None
    assert projected["read"] == ["src/main.py"]
    assert projected["generated_residue"] == []
    assert projected["created"] == []


def test_pcr_context_excludes_legacy_semantic_obligation_views() -> None:
    linked = {
        "open_obligations": [{"obligation_id": "task:a", "status": "open"}],
        "obligation_status": [{"obligation_id": "task:a", "status": "open"}],
        "artifacts_present": ["out.txt"],
    }
    projected = _factual_pcr_linked_history(linked)
    assert "open_obligations" not in projected
    assert "obligation_status" not in projected
    assert projected["artifacts_present"] == ["out.txt"]
    assert projected["pcr_context_boundary"]["kernel_strategy_guidance_exposed"] is False


def test_kernel_refuses_workspace_escape_before_dispatch() -> None:
    executor = MemoryExecutor(workspace_root="/app")
    hooks = _Hooks([
        SolverTurn(
            kind="act",
            summary="attempt an invalid workspace write",
            actions=(_action(
                "write_file", {"path": "../outside.txt", "content": "must not write"},
                action_id="escape", capability_id="filesystem",
            ),),
        ),
    ])

    result = AetherNextKernel(max_steps=1).run(
        _env(), executor, hooks,
    )

    refusal = next(
        receipt for receipt in result.receipts
        if receipt.receipt_id == "step-0:escape:workspace_path"
    )
    assert refusal.failure_class == "workspace_path_escape"
    assert executor.exists("outside.txt") is False


def test_pcr_context_does_not_expose_false_stuck_or_legacy_strategy_guidance() -> None:
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
            summary="observe a second ordinary boundary",
            actions=(_action(
                "read_file", {"path": "missing-second-boundary.txt"},
                action_id="continue", capability_id="filesystem",
            ),),
        ),
    ])
    trace = RunTrace()

    AetherNextKernel(max_steps=2).run(
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
    assert linked["pcr_context_boundary"] == {
        "linked_history_is_factual_projection": True,
        "kernel_strategy_guidance_exposed": False,
        "legacy_automatic_memory_exposed": False,
        "generic_stuck_judgment_exposed": False,
    }
    assert context["latest_primary_result"]["action_kind"] == "run_command"
    assert context["latest_primary_result"]["outcome_receipts"][0]["success"] is True
    assert "run_command" in context["available_capabilities"]["action_kinds"]
    assert set(context["available_capabilities"]) == {"action_kinds"}
    assert "action_owners" not in context["available_capabilities"]
    # Production PCR does not synthesize a semantic ObjectiveGraph from the raw
    # task. The task itself remains the sole semantic authority.
    assert "open_obligations" not in linked
    assert "obligation_status" not in linked


def test_kernel_supersedes_failed_task_result_only_after_same_action_state_change() -> None:
    command = "compile candidate"
    executor = MemoryExecutor(workspace_root="/app")
    attempts = {"count": 0}

    def compile_candidate(_executor: MemoryExecutor, cmd: str) -> CommandResult:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return CommandResult(cmd, 1, stderr="candidate missing")
        return CommandResult(cmd, 0, stdout="candidate compiled")

    executor.register_command(command, compile_candidate)
    hooks = _Hooks([
        SolverTurn(
            kind="act",
            summary="observe the initial compilation result",
            actions=(_action(
                "run_command", {"command": command},
                action_id="compile-first", capability_id="shell",
            ),),
        ),
        SolverTurn(
            kind="act",
            summary="change the candidate source",
            actions=(_action(
                "write_file", {"path": "candidate.txt", "content": "fixed"},
                action_id="repair", capability_id="filesystem",
            ),),
        ),
        SolverTurn(
            kind="act",
            summary="observe compilation after the source change",
            actions=(_action(
                "run_command", {"command": command},
                action_id="compile-second", capability_id="shell",
            ),),
        ),
    ])

    result = AetherNextKernel(max_steps=3).run(
        _env(), executor, hooks,
    )

    first_failure = next(
        receipt for receipt in result.receipts
        if receipt.receipt_id == "step-0:compile-first:cmd"
    )
    second_success = next(
        receipt for receipt in result.receipts
        if receipt.receipt_id == "step-2:compile-second:cmd"
    )
    supersession = next(
        receipt for receipt in result.receipts
        if receipt.kind == "pcr_task_failure_supersession"
    )
    assert first_failure.success is False
    assert second_success.success is True
    assert supersession.payload["source_failure_receipt_id"] == first_failure.receipt_id
    assert supersession.payload["successor_receipt_id"] == second_success.receipt_id
    assert (
        supersession.payload["source_relevant_state_fingerprint"]
        != supersession.payload["successor_relevant_state_fingerprint"]
    )
    unresolved = _mechanically_unresolved_failures(
        result.receipts,
        identity={
            "source_commit": "sealed",
            "runtime_manifest_sha256": "sealed",
        },
        latest_result={},
    )
    assert first_failure.receipt_id not in {
        row.get("receipt_id") for row in unresolved
    }


def test_control_success_and_forged_supersession_do_not_clear_task_failure() -> None:
    failure = Receipt(
        receipt_id="failed-compile",
        step=0,
        kind="run_command",
        success=False,
        summary="compiler rejected candidate",
        failure_class="command_failed",
    )
    control = Receipt(
        receipt_id="accounting-success",
        step=1,
        kind="accounting",
        success=True,
        summary="accounted for the attempted action",
    )
    forged = Receipt(
        receipt_id="forged-link",
        step=1,
        kind="pcr_task_failure_supersession",
        success=True,
        summary="untrusted resolution claim",
        payload={
            "source_failure_receipt_id": failure.receipt_id,
            "successor_receipt_id": control.receipt_id,
            "action_signature": "run_command:compile",
            "source_relevant_state_fingerprint": "before",
            "successor_relevant_state_fingerprint": "after",
            "authority": "kernel_observed_same_action_after_changed_state",
        },
    )

    unresolved = _mechanically_unresolved_failures(
        (failure, control, forged),
        identity={
            "source_commit": "sealed",
            "runtime_manifest_sha256": "sealed",
        },
        latest_result={},
    )

    assert {row.get("receipt_id") for row in unresolved} == {failure.receipt_id}

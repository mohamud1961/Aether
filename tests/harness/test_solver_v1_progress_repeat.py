from __future__ import annotations

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.execution import CommandResult, MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.ledger import ExecutionLedger, Receipt
from aether.no_progress import NoProgressController
from aether.runtime_ir import (
    ActionRequest,
    AutomaticMemoryPolicy,
    CapabilityDescriptor,
    CompletionPolicy,
    EnvMap,
    RuntimeConfigIR,
    SolverTurn,
)
from aether.solver_progress import build_progress_receipt


def _action(kind: str, arguments: dict, *, action_id: str = "a", capability: str = "filesystem") -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id=capability,
        arguments=arguments,
        intent="resolve the current evidence gap",
        expected_observation="one objective result",
        if_fail_next="change strategy or report the blocker",
    )


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Inspect current state.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file", "inspect_artifact")
            ),
            "shell": CapabilityDescriptor(
                "shell", "commands", tool_names=("run_command",)
            ),
            "service_probe": CapabilityDescriptor(
                "service_probe", "service probes", tool_names=("probe_service",)
            ),
        },
    )


def _runtime(*, memory_mode: str = "advisory") -> RuntimeConfigIR:
    return RuntimeConfigIR(
        architect_summary="solver v1 progress test",
        solver_identity_prompt="Choose one causal action.",
        selected_capabilities=("filesystem", "shell", "service_probe"),
        automatic_memory_policy=AutomaticMemoryPolicy(mode=memory_mode),
        completion_policy=CompletionPolicy(
            require_authoritative_check=False,
            require_all_obligations=False,
            require_recent_progress=False,
        ),
    )


class _Hooks:
    def __init__(self, turns: list[SolverTurn], *, memory_mode: str = "advisory") -> None:
        self.turns = list(turns)
        self.runtime = _runtime(memory_mode=memory_mode)

    def architect(self, request):
        return self.runtime

    def solve(self, messages, compiled):
        return self.turns.pop(0)


def _turn(action: ActionRequest, summary: str = "act") -> SolverTurn:
    return SolverTurn(
        kind="act",
        summary=summary,
        evidence_gap="The current objective evidence is unresolved.",
        actions=(action,),
    )


def test_repeated_artifact_inspection_soft_blocks_without_budget_charge() -> None:
    action = _action(
        "inspect_artifact",
        {"path": "report.txt", "mode": "text"},
        action_id="inspect",
    )
    turns = [_turn(action), _turn(action), _turn(action)]
    result = AetherNextKernel(max_steps=3).run(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"report.txt": "done"}),
        _Hooks(turns),
    )
    inspections = [r for r in result.receipts if r.kind == "artifact_inspection"]
    controls = [r for r in result.receipts if r.kind == "no_progress_control"]
    assert len(inspections) == 2
    assert len(controls) == 1
    assert controls[0].payload["consequence"] == "soft_block"
    assert result.accounting["solver_accepted_task_actions"] == 2
    assert result.accounting["solver_refused_actions"] == 1


def test_repeated_failed_service_probe_soft_blocks_third_probe() -> None:
    action = _action(
        "probe_service",
        {"target": "http://127.0.0.1:9999/"},
        action_id="probe",
        capability="service_probe",
    )
    turns = [_turn(action), _turn(action), _turn(action)]
    executor = MemoryExecutor(workspace_root="/app")
    result = AetherNextKernel(max_steps=3).run(_env(), executor, _Hooks(turns))
    probes = [r for r in result.receipts if r.kind == "service_probe"]
    controls = [r for r in result.receipts if r.kind == "no_progress_control"]
    assert len(probes) == 2
    assert all(not row.success for row in probes)
    assert len(controls) == 1
    assert controls[0].failure_class == "repeated_service_probe_no_state_change"
    progress = [r for r in result.receipts if r.kind == "solver_progress_assessment"]
    assert progress[-1].payload["progress_signals"] == [
        "equivalent_repeat", "protocol_or_policy_failure"
    ]


def test_progress_signals_cover_state_evidence_verification_failure_and_policy() -> None:
    ledger = ExecutionLedger()
    action = _action("read_file", {"path": "x.txt"})

    state = build_progress_receipt(
        action,
        step=1,
        step_receipts=(Receipt("write", 1, "write_file", True, "wrote", state_change=True),),
        ledger=ledger,
    )
    assert state.payload["classification"] == "state_changed"
    assert state.payload["progress_signals"] == ["state_change"]

    evidence = build_progress_receipt(
        action,
        step=2,
        step_receipts=(Receipt("read", 2, "read_file", True, "read", payload={"path": "x.txt"}),),
        ledger=ledger,
    )
    assert evidence.payload["progress_signals"] == ["new_evidence"]

    verification = build_progress_receipt(
        action,
        step=3,
        step_receipts=(Receipt("check", 3, "check_result", True, "passed"),),
        ledger=ledger,
    )
    assert verification.payload["progress_signals"] == [
        "new_evidence", "verification", "requirement_evidence"
    ]

    failure = build_progress_receipt(
        action,
        step=4,
        step_receipts=(Receipt("failed", 4, "run_command", False, "failed"),),
        ledger=ledger,
    )
    assert failure.payload["progress_signals"] == ["failure_observed"]

    policy = build_progress_receipt(
        action,
        step=5,
        step_receipts=(Receipt(
            "repeat", 5, "automatic_memory_block", False, "blocked",
            failure_class="equivalent_repeat_blocked",
            payload={"consequence": "soft_block"},
        ),),
        ledger=ledger,
    )
    assert policy.payload["classification"] == "equivalent_repeat_blocked"
    assert policy.payload["progress_signals"] == [
        "equivalent_repeat", "protocol_or_policy_failure"
    ]
    assert policy.payload["dispatch_performed"] is False


def test_progress_no_direct_result_is_no_relevant_progress() -> None:
    receipt = build_progress_receipt(
        _action("read_file", {"path": "x.txt"}),
        step=1,
        step_receipts=(),
        ledger=ExecutionLedger(),
    )
    assert receipt.payload["classification"] == "no_direct_result"
    assert receipt.payload["progress_signals"] == ["no_relevant_progress"]
    assert receipt.payload["no_relevant_progress"] is True

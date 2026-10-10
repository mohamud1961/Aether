from __future__ import annotations

from aether.execution import MemoryExecutor
from aether.model_hooks import ModelOutputError
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Read input.txt.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file"),
            )
        },
    )


def _read_turn() -> SolverTurn:
    return SolverTurn(
        kind="act",
        summary="read current input",
        actions=(ActionRequest(
            action_id="read",
            kind="read_file",
            capability_id="filesystem",
            arguments={"path": "input.txt"},
            intent="observe bytes",
            expected_observation="file contents",
            if_fail_next="report read failure",
        ),),
    )


def test_second_protocol_correction_can_recover_without_consuming_task_step() -> None:
    class Hooks:
        def __init__(self) -> None:
            self.calls = 0

        def solve(self, messages, compiled):
            del messages, compiled
            self.calls += 1
            if self.calls <= 2:
                raise ModelOutputError(f"invalid envelope {self.calls}")
            return _read_turn()

    hooks = Hooks()
    result = run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "ok"}),
        hooks,
        config=ThinLoopConfig(max_steps=1, max_solver_turns=3),
    )

    assert result.status == "step_budget_exhausted"
    assert hooks.calls == 3
    assert result.accounting["solver_provider_turns"] == 3
    assert result.accounting["solver_protocol_correction_calls"] == 2
    corrections = [
        row for row in result.receipts
        if row.kind == "thin_protocol_correction_result"
    ]
    assert len(corrections) == 1
    assert corrections[0].payload["correction_attempts_used"] == 2
    assert any(row.kind == "read_file" and row.success for row in result.receipts)


def test_protocol_correction_cannot_exceed_global_solver_turn_ceiling() -> None:
    class Hooks:
        def __init__(self) -> None:
            self.calls = 0

        def solve(self, messages, compiled):
            del messages, compiled
            self.calls += 1
            raise ModelOutputError(f"invalid envelope {self.calls}")

    hooks = Hooks()
    result = run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "ok"}),
        hooks,
        config=ThinLoopConfig(max_steps=1, max_solver_turns=2),
    )

    assert result.status == "solver_turn_budget_exhausted"
    assert hooks.calls == 2
    assert result.accounting["solver_provider_turns"] == 2
    assert result.accounting["solver_protocol_correction_calls"] == 1
    budget = next(
        row for row in result.receipts
        if row.kind == "solver_turn_budget_exhausted"
    )
    assert budget.payload["phase"] == "protocol_correction"
    assert budget.payload["correction_attempt"] == 2
    assert not any(row.state_change for row in result.receipts)

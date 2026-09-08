from __future__ import annotations

from typing import Any

from aether.execution import CommandResult, MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Produce the required output.",
        workspace_root="/app",
        capabilities={
            "shell": CapabilityDescriptor("shell", "commands", tool_names=("run_command",)),
            "filesystem": CapabilityDescriptor("filesystem", "files", tool_names=("read_file", "write_file")),
        },
    )


class _Hooks:
    def __init__(self, turns: list[SolverTurn]) -> None:
        self.turns = list(turns)
        self.solve_calls = 0

    def solve(self, messages: list[dict[str, str]], compiled: Any) -> SolverTurn:
        del messages, compiled
        self.solve_calls += 1
        return self.turns.pop(0) if self.turns else SolverTurn(kind="submit_outcome", summary="submit")


class _ParityExecutor:
    def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30) -> CommandResult:
        del cwd, timeout_s
        if command.startswith("command -v python3"):
            return CommandResult(command, 127, "", "not found")
        return CommandResult(command, 0, "", "")

    def exists(self, path: str) -> bool:
        return True

    def read_file(self, path: str) -> str:
        return ""

    def probe_process(self, target: str):
        return None



def test_solver_turns_and_accepted_actions_are_separate_receipted_counters() -> None:
    actions = tuple(
        ActionRequest(
            action_id=f"read-{index}", kind="read_file", capability_id="filesystem",
            arguments={"path": f"input-{index}.txt"}, intent="observe",
            expected_observation="file bytes", if_fail_next="stop",
        )
        for index in (1, 2)
    )
    hooks = _Hooks([
        SolverTurn(kind="act", summary="first observation", actions=(actions[0],), evidence_gap="The next action must resolve the current evidence gap"),
        SolverTurn(kind="act", summary="second observation", actions=(actions[1],), evidence_gap="The next action must resolve the current evidence gap"),
    ])
    result = AetherNextKernel(
        max_steps=3, max_solver_turns=2, max_accepted_task_actions=1,
    ).run(_env(), MemoryExecutor(workspace_root="/app", files={"input-1.txt":"1","input-2.txt":"2"}), hooks)

    assert result.status == "solver_turn_budget_exhausted"
    assert result.accounting == {
        "solver_accepted_task_actions": 1,
        "solver_provider_turns": 2,
        "solver_refused_actions": 1,
    }
    events = [receipt.payload["event"] for receipt in result.receipts if receipt.kind == "runtime_accounting"]
    assert "accepted_for_dispatch" in events
    assert "accepted_action_budget_exhausted" in events


def test_kernel_none_step_budget_does_not_impose_solver_turn_ceiling() -> None:
    kernel = AetherNextKernel(max_steps=None)
    assert kernel.max_steps is None
    assert kernel.max_solver_turns is None


def test_kernel_explicit_step_budget_remains_available_for_tests_and_research() -> None:
    kernel = AetherNextKernel(max_steps=7)
    assert kernel.max_steps == 7
    assert kernel.max_solver_turns == 7


def test_context_advisory_excess_does_not_terminate_before_solver_call(monkeypatch) -> None:
    import aether.kernel as kernel_module
    from aether.kernel import AetherNextKernel
    from aether.envmap_builder import build_envmap_from_task
    from aether.execution import MemoryExecutor
    from aether.model_hooks import ModelOutputError
    import tempfile
    from pathlib import Path

    calls = {"solver": 0}
    class Hooks:
        def solve(self, messages, compiled):
            calls["solver"] += 1
            raise ModelOutputError("stop after proving provider boundary was reached")

    original = kernel_module.build_pcr_context
    def oversized(*args, **kwargs):
        packet = dict(original(*args, **kwargs))
        packet["context_budget"] = {
            "within_budget": False,
            "hard_limit_enforced": False,
            "provider_context_authority": True,
        }
        return packet
    monkeypatch.setattr(kernel_module, "build_pcr_context", oversized)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); (root / "instruction.md").write_text("inspect", encoding="utf-8")
        env = build_envmap_from_task(str(root), "inspect", workspace_root="/app", projection_mode="factual_only")
        # One iteration is enough: the assertion is that context size no longer
        # returns context_budget_exceeded before invoking the Solver.
        AetherNextKernel(max_steps=1).run(env, MemoryExecutor(workspace_root="/app"), Hooks())
    assert calls["solver"] >= 1

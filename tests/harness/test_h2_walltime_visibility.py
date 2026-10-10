from __future__ import annotations

from copy import deepcopy

import pytest

from aether.execution import MemoryExecutor
from aether.harbor_runtime import (
    H2_CONTROL_ARM,
    H2_WALLTIME_ARM,
    H2_WALLTIME_ARM_ENV,
    build_selected_frontier_models,
    selected_h2_walltime_arm,
    selected_solver_reanchor_mode,
)
from aether.kernel import AetherNextKernel
from aether.model_profile import PRODUCTION_PROFILE
from aether.persistent_reanchor import (
    CONTINUITY_FRESH_DELTA_V1,
    CONTINUITY_FRESH_DELTA_WALLTIME_V1,
    project_persistent_context_for_model,
)
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn


def _packet(remaining_run_sec: float | None = 17.25) -> dict[str, object]:
    return {
        "latest_primary_result": {},
        "runtime_identity": {"task_id": "h2", "run_id": "r"},
        "available_capabilities": {},
        "budgets": {
            "max_kernel_steps": 20,
            "used_solver_provider_turns": 2,
            "remaining_kernel_steps": 18,
            "run_timeout_sec": 30.0,
            "elapsed_run_sec": 12.75,
            "remaining_run_sec": remaining_run_sec,
            "wall_clock_authority": "runtime_supplied_timeout",
        },
        "evidence_index": [],
        "linked_history": {},
    }


def test_h2_treatment_adds_only_truthful_remaining_run_sec() -> None:
    packet = _packet()
    before = deepcopy(packet)
    control = project_persistent_context_for_model(packet, mode=CONTINUITY_FRESH_DELTA_V1)
    treatment = project_persistent_context_for_model(
        packet, mode=CONTINUITY_FRESH_DELTA_WALLTIME_V1,
    )
    assert packet == before
    assert "remaining_run_sec" not in control["budgets"]
    assert treatment["budgets"]["remaining_run_sec"] == 17.25
    treatment_without_clock = deepcopy(treatment)
    treatment_without_clock["budgets"].pop("remaining_run_sec")
    assert treatment_without_clock == control


def test_h2_treatment_preserves_canonical_null_when_no_deadline() -> None:
    packet = _packet(None)
    treatment = project_persistent_context_for_model(
        packet, mode=CONTINUITY_FRESH_DELTA_WALLTIME_V1,
    )
    assert "remaining_run_sec" in treatment["budgets"]
    assert treatment["budgets"]["remaining_run_sec"] is None


def test_h2_arm_selector_is_default_off_and_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(H2_WALLTIME_ARM_ENV, raising=False)
    assert selected_h2_walltime_arm() == H2_CONTROL_ARM
    assert selected_solver_reanchor_mode(build_selected_frontier_models) == PRODUCTION_PROFILE.solver_reanchor_mode
    monkeypatch.setenv(H2_WALLTIME_ARM_ENV, H2_WALLTIME_ARM)
    assert selected_h2_walltime_arm() == H2_WALLTIME_ARM
    assert selected_solver_reanchor_mode(build_selected_frontier_models) == CONTINUITY_FRESH_DELTA_WALLTIME_V1
    monkeypatch.setenv(H2_WALLTIME_ARM_ENV, "invent-strategy")
    with pytest.raises(RuntimeError, match=H2_WALLTIME_ARM_ENV):
        selected_h2_walltime_arm()


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Observe files.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files", tool_names=("read_file",),
            ),
        },
    )


class _ClockHooks:
    verify = None

    def __init__(self) -> None:
        self.calls = 0
        self.seen_remaining: list[float] = []

    def solve(self, messages, compiled):
        del compiled
        import json
        marker = "[context_packet]\n"
        for message in messages:
            content = str(message.get("content", ""))
            if content.startswith(marker):
                context = json.loads(content[len(marker):])
                value = context.get("budgets", {}).get("remaining_run_sec")
                assert isinstance(value, (int, float))
                self.seen_remaining.append(float(value))
                break
        self.calls += 1
        return SolverTurn(
            kind="act",
            summary="observe",
            actions=(ActionRequest(
                action_id=f"read-{self.calls}",
                kind="read_file",
                capability_id="filesystem",
                arguments={"path": "input.txt"},
                intent="",
                expected_observation="",
                if_fail_next="",
            ),),
        )


def test_h2_model_visible_remaining_time_decreases_under_controlled_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks = iter((101.0, 103.25, 106.5, 109.0, 109.5, 109.75))
    monkeypatch.setattr("aether.kernel.time.monotonic", lambda: next(ticks))
    hooks = _ClockHooks()
    kernel = AetherNextKernel(
        max_steps=3,
        solver_reanchor_mode=CONTINUITY_FRESH_DELTA_WALLTIME_V1,
    )
    kernel.run(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "x"}),
        hooks,
        run_timeout_s=20.0,
        run_started_monotonic=100.0,
    )
    assert len(hooks.seen_remaining) == 3
    assert hooks.seen_remaining == sorted(hooks.seen_remaining, reverse=True)
    assert hooks.seen_remaining[0] <= 19.0
    assert hooks.seen_remaining[-1] < hooks.seen_remaining[0]
    assert [row["step"] for row in kernel.runtime_budget_history] == [0, 1, 2]
    canonical_remaining = [row["remaining_run_sec"] for row in kernel.runtime_budget_history]
    assert canonical_remaining == sorted(canonical_remaining, reverse=True)
    assert canonical_remaining == hooks.seen_remaining

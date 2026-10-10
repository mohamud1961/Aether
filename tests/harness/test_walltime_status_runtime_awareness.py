from __future__ import annotations

from dataclasses import replace
import json

import pytest

from aether.execution import MemoryExecutor
from aether.harbor_runtime import (
    H2_CONTROL_ARM,
    H2_WALLTIME_ARM,
    H2_WALLTIME_ARM_ENV,
    H2_WALLTIME_STATUS_ARM,
    build_selected_frontier_models,
    selected_h2_walltime_arm,
    selected_runtime_operation_status_refresh,
    selected_solver_reanchor_mode,
)
from aether.kernel import AetherNextKernel
from aether.persistent_reanchor import CONTINUITY_FRESH_DELTA_WALLTIME_V1
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Run one finite job and inspect a file.",
        workspace_root="/app",
        capabilities={
            "managed_process": CapabilityDescriptor(
                "managed_process", "managed finite jobs", tool_names=("start_job", "probe_job"),
            ),
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files", tool_names=("read_file",),
            ),
        },
    )


def _context(messages) -> dict:
    marker = "[context_packet]\n"
    for message in messages:
        content = str(message.get("content", ""))
        if content.startswith(marker):
            return json.loads(content[len(marker):])
    raise AssertionError("context packet missing")


class _Hooks:
    verify = None

    def __init__(self) -> None:
        self.calls = 0
        self.contexts: list[dict] = []

    def solve(self, messages, compiled):
        del compiled
        self.contexts.append(_context(messages))
        self.calls += 1
        if self.calls == 1:
            action = ActionRequest(
                action_id="job",
                kind="start_job",
                capability_id="managed_process",
                arguments={"service_name": "finite", "command": "do-work"},
                intent="",
                expected_observation="",
                if_fail_next="",
            )
        else:
            action = ActionRequest(
                action_id="read",
                kind="read_file",
                capability_id="filesystem",
                arguments={"path": "input.txt"},
                intent="",
                expected_observation="",
                if_fail_next="",
            )
        return SolverTurn(kind="act", summary="act", actions=(action,))


class _CompletingExecutor(MemoryExecutor):
    def __init__(self, clock: list[float]) -> None:
        super().__init__(workspace_root="/app", files={"input.txt": "ok"})
        self.clock = clock
        self.probe_calls = 0

    def probe_job(self, target: str):
        self.probe_calls += 1
        self.clock[0] += 5.0
        handle = self.processes[target]
        self.processes[target] = replace(
            handle, live=False, status="completed", exit_code=0, detail="exited 0",
        )
        return super().probe_job(target)


class _UnknownExecutor(MemoryExecutor):
    def probe_job(self, target: str):
        raise RuntimeError(f"probe unavailable for {target}")


def test_walltime_status_arm_is_explicit_default_off_and_preserves_old_walltime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(H2_WALLTIME_ARM_ENV, raising=False)
    assert selected_h2_walltime_arm() == H2_CONTROL_ARM
    assert selected_runtime_operation_status_refresh(build_selected_frontier_models) is False

    monkeypatch.setenv(H2_WALLTIME_ARM_ENV, H2_WALLTIME_ARM)
    assert selected_solver_reanchor_mode(build_selected_frontier_models) == CONTINUITY_FRESH_DELTA_WALLTIME_V1
    assert selected_runtime_operation_status_refresh(build_selected_frontier_models) is False

    monkeypatch.setenv(H2_WALLTIME_ARM_ENV, H2_WALLTIME_STATUS_ARM)
    assert selected_solver_reanchor_mode(build_selected_frontier_models) == CONTINUITY_FRESH_DELTA_WALLTIME_V1
    assert selected_runtime_operation_status_refresh(build_selected_frontier_models) is True


def test_walltime_status_refreshes_terminal_job_before_clock_and_next_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("aether.kernel.time.monotonic", lambda: clock[0])
    hooks = _Hooks()
    executor = _CompletingExecutor(clock)
    kernel = AetherNextKernel(
        max_steps=2,
        solver_reanchor_mode=CONTINUITY_FRESH_DELTA_WALLTIME_V1,
        refresh_runtime_operation_status=True,
    )
    result = kernel.run(
        _env(), executor, hooks,
        run_timeout_s=20.0,
        run_started_monotonic=100.0,
    )
    assert result.step == 2
    assert executor.probe_calls == 1
    assert len(hooks.contexts) == 2
    assert hooks.contexts[0]["budgets"]["remaining_run_sec"] == 20.0
    # The automatic status probe consumed five seconds before the clock was sampled.
    assert hooks.contexts[1]["budgets"]["remaining_run_sec"] == 15.0
    operations = hooks.contexts[1]["runtime_operations"]
    assert len(operations) == 1
    assert operations[0]["status"] == "completed"
    assert operations[0]["status_current"] is True
    assert operations[0]["status_authority"] == "mechanical_generation_verified_probe"
    assert operations[0]["completed"] is True
    assert operations[0]["job_succeeded"] is True
    assert operations[0]["exit_code"] == 0
    assert "live_processes" not in hooks.contexts[1].get("linked_history", {})
    refreshes = [r for r in result.receipts if r.kind == "runtime_operation_status_refresh"]
    assert len(refreshes) == 1 and refreshes[0].success is True


def test_walltime_status_reports_unknown_instead_of_stale_running_when_probe_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [200.0]
    monkeypatch.setattr("aether.kernel.time.monotonic", lambda: clock[0])
    hooks = _Hooks()
    executor = _UnknownExecutor(workspace_root="/app", files={"input.txt": "ok"})
    kernel = AetherNextKernel(
        max_steps=2,
        solver_reanchor_mode=CONTINUITY_FRESH_DELTA_WALLTIME_V1,
        refresh_runtime_operation_status=True,
    )
    result = kernel.run(
        _env(), executor, hooks,
        run_timeout_s=30.0,
        run_started_monotonic=200.0,
    )
    operations = hooks.contexts[1]["runtime_operations"]
    assert len(operations) == 1
    assert operations[0]["status"] == "unknown"
    assert operations[0]["status_current"] is False
    assert operations[0]["status_authority"] == "not_currently_verified"
    assert "live_processes" not in hooks.contexts[1].get("linked_history", {})
    refreshes = [r for r in result.receipts if r.kind == "runtime_operation_status_refresh"]
    assert len(refreshes) == 1
    assert refreshes[0].success is False
    assert refreshes[0].failure_class == "runtime_operation_status_unavailable"

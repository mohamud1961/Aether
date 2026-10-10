"""R7 completion interaction: verify -> stop -> disposition -> Thin submission.

Provider-free regression for the exact Thin integration boundary.  A complete,
unchanged process-stop observation is lifecycle housekeeping; uncertain or
mutating stops still advance task-world freshness and stale earlier evidence.
"""
from __future__ import annotations

import json
import time
from hashlib import sha256
from typing import Any

from aether.envmap_builder import build_envmap_from_task
from aether.execution import (
    CommandResult,
    MemoryExecutor,
    ProcessHandle,
    ProcessOrchestratorV2,
)
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import ActionRequest, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop

TASK_TEXT = (
    "Create /app/report.txt containing the final report. Validate it with a "
    "temporary verification service, stop that temporary service after it validates "
    "the report, then finish with the report served in place."
)


def _action(action_id: str, kind: str, capability_id: str, arguments: dict[str, Any]) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id=capability_id,
        arguments=arguments,
        intent="address the current evidence gap",
        expected_observation="one exact result",
        if_fail_next="inspect the failure before continuing",
    )


def _context(messages: list[dict[str, str]]) -> dict[str, Any]:
    marker = "[context_packet]\n"
    for message in messages:
        content = str(message.get("content", ""))
        if content.startswith(marker):
            return json.loads(content[len(marker):])
    raise AssertionError("context packet missing from Solver messages")


class _NoMutationMemoryExecutor(MemoryExecutor):
    def observe_process_state(self, _target: str) -> dict[str, Any]:
        return {
            "created_paths": [],
            "removed_paths": [],
            "content_changed_paths": [],
            "metadata_changed_paths": [],
            "before_truncated": False,
            "after_truncated": False,
            "mutation_detection_status": "complete",
            "path_set_delta_status": "complete",
            "mutation_detection_scope": "managed_process_async_workspace_effects",
        }


class _UnknownMutationMemoryExecutor(_NoMutationMemoryExecutor):
    def observe_process_state(self, _target: str) -> dict[str, Any]:
        return {
            "mutation_detection_status": "unavailable",
            "mutation_detection_scope": "managed_process_async_workspace_effects",
        }


class _MutatingStopMemoryExecutor(_NoMutationMemoryExecutor):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._observations = 0

    def observe_process_state(self, _target: str) -> dict[str, Any]:
        self._observations += 1
        row = super().observe_process_state(_target)
        # Launch is first observation.  The stop observation proves a file changed.
        if self._observations >= 2:
            row["content_changed_paths"] = ["report.txt"]
        return row


class _VerifyStopFinishHooks:
    def __init__(self, *, disposition: str = "optional") -> None:
        self.solve_calls = 0
        self.messages_seen: list[list[dict[str, str]]] = []
        self.disposition = disposition

    def _latest_verification_ref(self, messages: list[dict[str, str]]) -> str:
        packet = _context(messages)
        rows = [
            row for row in packet.get("evidence_index", [])
            if isinstance(row, dict)
            and row.get("evidence_type") == "run_command"
            and row.get("evidence_ref")
            and row.get("completion_evidence_eligible", True)
        ]
        assert rows, "verification evidence missing"
        return str(rows[-1]["evidence_ref"])

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        self.messages_seen.append(messages)
        step = self.solve_calls
        if step == 1:
            return SolverTurn(
                kind="act", summary="write report", evidence_gap="report missing",
                actions=(_action("write-report", "write_file", "filesystem",
                                 {"path": "report.txt", "content": "final report\n"}),),
            )
        if step == 2:
            return SolverTurn(
                kind="act", summary="start temporary verifier", evidence_gap="validation not running",
                actions=(_action("start-verify", "launch_process", "managed_process",
                                 {"service_name": "report-verify", "command": "python verify_report.py"}),),
            )
        if step == 3:
            return SolverTurn(
                kind="act", summary="validate report", evidence_gap="report unverified",
                actions=(_action("verify-report", "run_command", "shell",
                                 {"command": "python verify_report.py"}),),
            )
        if step == 4:
            return SolverTurn(
                kind="act", summary="stop temporary verifier", evidence_gap="temporary service still live",
                actions=(_action("stop-verify", "stop_process", "managed_process",
                                 {"target": "report-verify"}),),
            )
        if step == 5:
            return SolverTurn(
                kind="act", summary="reconcile verifier lifecycle", evidence_gap="stopped job unclassified",
                actions=(_action("disposition-verify", "set_job_disposition", "kernel", {
                    "job_id": "report-verify",
                    "relevance": self.disposition,
                    "reason": "temporary verification finished and was intentionally stopped",
                }),),
            )
        return SolverTurn(
            kind="finish_intent",
            summary="submit externally",
            claim="report.txt is complete and was validated before temporary-service cleanup",
            evidence_refs=(self._latest_verification_ref(messages),),
        )


def _executor(cls=_NoMutationMemoryExecutor) -> MemoryExecutor:
    executor = cls(workspace_root="/app")

    def verify_report(_executor: MemoryExecutor, command: str) -> CommandResult:
        return CommandResult(
            command, 0, stdout="report ok",
            state_delta={
                "created_paths": [], "removed_paths": [],
                "content_changed_paths": [], "metadata_changed_paths": [],
                "before_truncated": False, "after_truncated": False,
                "mutation_detection_status": "complete",
                "path_set_delta_status": "complete",
            },
        )

    def launch_verify(_executor: MemoryExecutor, name: str, command: str, interactive: bool) -> ProcessHandle:
        del interactive
        generation = sha256(f"{name}\0{command}".encode()).hexdigest()[:24]
        return ProcessHandle(
            process_id=f"process:{generation}", name=name, command=command,
            interactive=False, live=True, endpoint=f"local://{name}", detail="started",
            pid=20001, start_time_ticks="1", command_sha256=sha256(command.encode()).hexdigest(),
            process_generation=generation, status="running",
        )

    executor.register_command("python verify_report.py", verify_report)
    executor.register_launch("python verify_report.py", launch_verify)
    return executor


def _run(
    executor: MemoryExecutor,
    hooks: _VerifyStopFinishHooks,
    *,
    max_steps: int = 8,
    semantic_assistance=None,
    completion_signal_mode: str = "control",
    terminal_verifier_mode: str = "control",
):
    envmap = build_envmap_from_task(
        "/tmp/aether-empty-task-dir", TASK_TEXT, workspace_root="/app",
        projection_mode="factual_only",
    )
    return run_thin_loop(
        envmap, executor, hooks,
        config=ThinLoopConfig(
            max_steps=max_steps,
            max_solver_turns=10,
            max_accepted_task_actions=6,
            runtime_identity={
                "task_id": "v2-verify-stop-finish",
                "run_id": "v2-verify-stop-finish-run",
                "primary_agent_id": "primary",
                "budgets": {
                    "max_kernel_steps": max_steps,
                    "max_solver_turns": 10,
                    "max_accepted_task_actions": 6,
                },
            },
            completion_record_mode="off",
            solver_completion_signal_mode=completion_signal_mode,
            semantic_assistance=semantic_assistance,
            terminal_verifier_mode=terminal_verifier_mode,
        ),
    )


def test_completion_signal_is_fresh_only_immediately_after_clean_verification() -> None:
    hooks = _VerifyStopFinishHooks()
    result = _run(_executor(), hooks, completion_signal_mode="verification_v1")
    assert result.status == "submitted"

    packets = [_context(messages) for messages in hooks.messages_seen]
    visible = [index for index, packet in enumerate(packets) if "completion_signal" in packet]
    # Zero-based Solver call 3 is the call immediately after the step-3
    # verification command. Later lifecycle actions make the signal stale.
    assert visible == [3]
    signal = packets[3]["completion_signal"]
    assert signal["basis"] == "latest_primary_result"
    assert signal["semantic_completion_authority"] == "solver_against_raw_task_and_observed_reality"
    assert "call finish" in signal["instruction"]
    assert "completion_signal" not in packets[4]
    assert "completion_signal" not in packets[-1]


def test_advice_is_visible_but_cannot_veto_real_thin_submission() -> None:
    calls = []
    def advice(**kwargs):
        calls.append(kwargs["step"])
        return {"authority": "advisory_only", "suggestion": "inspect more", "completed": False}
    hooks = _VerifyStopFinishHooks()
    result = _run(_executor(), hooks, semantic_assistance=advice)
    assert result.status == "submitted"
    assert len(calls) == hooks.solve_calls
    for messages in hooks.messages_seen:
        packet = _context(messages)
        assert packet["semantic_advice"]["completed"] is False
        assert "budgets" in packet and "evidence_index" in packet
        assert any(TASK_TEXT in m["content"] for m in messages)


def test_verified_stop_disposition_submits_through_real_thin_boundary() -> None:
    hooks = _VerifyStopFinishHooks()
    result = _run(_executor(), hooks)

    assert result.status == "submitted"
    assert result.external_grade == "not_run"
    assert sum(r.kind == "primary_submission_claim" for r in result.receipts) == 1
    assert sum(r.kind == "thin_submitted" for r in result.receipts) == 1
    assert not [r for r in result.receipts if r.kind == "thin_submission_blocked"]
    stop = next(r for r in result.receipts if r.kind == "process_stop" and r.success)
    assert stop.state_change is False
    assert stop.payload["state_delta"]["mutation_detection_status"] == "complete"

    # Completion-record OFF must be truthful on the model-facing capability surface.
    for messages in hooks.messages_seen:
        actions = _context(messages)["available_capabilities"]["action_kinds"]
        assert "update_completion_record" not in actions

    # The three independent limits are projected independently.
    first = _context(hooks.messages_seen[0])["budgets"]
    second = _context(hooks.messages_seen[1])["budgets"]
    assert first["used_kernel_steps"] == 0
    assert first["remaining_kernel_steps"] == 8
    assert first["used_solver_provider_turns"] == 0
    assert first["remaining_solver_provider_turns"] == 10
    assert first["remaining_accepted_task_actions"] == 6
    assert second["used_kernel_steps"] == 1
    assert second["remaining_kernel_steps"] == 7
    assert second["used_solver_provider_turns"] == 1
    assert second["remaining_solver_provider_turns"] == 9
    assert second["remaining_accepted_task_actions"] == 5


def test_unknown_stop_observation_keeps_earlier_verification_stale() -> None:
    hooks = _VerifyStopFinishHooks()
    result = _run(_executor(_UnknownMutationMemoryExecutor), hooks)
    assert result.status != "submitted"
    stops = [r for r in result.receipts if r.kind == "process_stop" and r.success]
    assert stops
    # Uncertain state is an epistemic freshness boundary, not a fabricated
    # concrete mutation.  The receipt stays state_change=False but dispatch
    # marks its state_delta coarse, which advances evidence generation.
    assert stops[-1].state_change is False
    assert stops[-1].payload["state_delta"]["mutation_detection_status"] == "coarse"
    assert [r for r in result.receipts if r.kind == "thin_submission_blocked"]


def test_mutating_stop_observation_keeps_earlier_verification_stale() -> None:
    hooks = _VerifyStopFinishHooks()
    result = _run(_executor(_MutatingStopMemoryExecutor), hooks)
    assert result.status != "submitted"
    stop = next(r for r in result.receipts if r.kind == "process_stop" and r.success)
    assert stop.state_change is True
    assert "report.txt" in stop.payload["state_delta"]["content_changed_paths"]
    assert [r for r in result.receipts if r.kind == "thin_submission_blocked"]


def test_real_subprocess_stop_observation_is_lifecycle_only_when_workspace_unchanged(tmp_path) -> None:
    executor = SubprocessExecutor(str(tmp_path))
    orchestrator = ProcessOrchestratorV2()
    launch = orchestrator.launch(
        _action("start-real", "launch_process", "managed_process", {
            "service_name": "real-temp",
            "command": "python3 -c \"import time; time.sleep(30)\"",
        }),
        1, executor, workspace_root=str(tmp_path), interactive=False,
    )
    assert launch.success
    stop = orchestrator.stop(
        _action("stop-real", "stop_process", "managed_process",
                {"target": launch.payload["process_id"]}),
        2, executor,
    )
    assert stop.success
    assert stop.state_change is False
    delta = stop.payload["state_delta"]
    assert delta["mutation_detection_status"] == "complete"
    assert delta["path_set_delta_status"] == "complete"
    assert delta["before_truncated"] is False and delta["after_truncated"] is False
    # Ensure process really terminates; no leaked local worker.
    deadline = time.monotonic() + 2.0
    while executor.probe_process(launch.payload["process_id"]).live and time.monotonic() < deadline:
        time.sleep(0.02)
    assert executor.probe_process(launch.payload["process_id"]).live is False


def test_vf1_terminal_finish_hook_is_live_and_control_stays_inert(monkeypatch) -> None:
    from aether.verifier import ModelVerifierResult
    import aether.thin_loop as thin

    control_calls = []
    def must_not_review(*args, **kwargs):
        control_calls.append((args, kwargs))
        raise AssertionError("control must not activate terminal verifier")

    monkeypatch.setattr(thin, "run_model_verifier_if_available", must_not_review)
    control_hooks = _VerifyStopFinishHooks()
    control = _run(_executor(), control_hooks)
    assert control.status == "submitted"
    assert control_calls == []
    assert not any(r.kind == "thin_terminal_verifier_hook" for r in control.receipts)

    review_calls = []
    def completed(*args, **kwargs):
        review_calls.append({
            "reason": kwargs.get("reason"),
            "step": kwargs.get("step"),
        })
        return ModelVerifierResult(
            verdict="completed", confidence="high", summary="provider-free fixture complete"
        )

    monkeypatch.setattr(thin, "run_model_verifier_if_available", completed)
    treated_hooks = _VerifyStopFinishHooks()
    treated = _run(
        _executor(), treated_hooks,
        terminal_verifier_mode="terminal_verifier_v1",
    )
    assert treated.status == "submitted"
    assert treated_hooks.solve_calls == control_hooks.solve_calls
    assert review_calls == [{"reason": "solver_submit", "step": 5}]
    assert len([r for r in treated.receipts if r.kind == "thin_terminal_verifier_hook"]) == 1
    assert len([r for r in treated.receipts if r.kind == "thin_terminal_verifier_result" and r.success]) == 1
    assert len([r for r in treated.receipts if r.kind == "thin_submitted"]) == 1


def test_vf1_missing_terminal_verifier_fails_closed(monkeypatch) -> None:
    import aether.thin_loop as thin

    calls = []
    def missing(*args, **kwargs):
        calls.append(1)
        return None

    monkeypatch.setattr(thin, "run_model_verifier_if_available", missing)
    result = _run(
        _executor(), _VerifyStopFinishHooks(),
        terminal_verifier_mode="terminal_verifier_v1",
    )
    assert calls == [1]
    assert result.status == "verifier_missing"
    assert result.blockers == ("verifier_missing",)
    assert not any(r.kind == "thin_submitted" for r in result.receipts)




def test_vf1_cycle_counter_caps_at_three() -> None:
    from aether.thin_loop import (
        THIN_TERMINAL_VERIFIER_MAX_CYCLES,
        _next_terminal_verifier_cycle,
    )
    assert THIN_TERMINAL_VERIFIER_MAX_CYCLES == 3
    assert _next_terminal_verifier_cycle(0) == 1
    assert _next_terminal_verifier_cycle(1) == 2
    assert _next_terminal_verifier_cycle(2) == 3
    assert _next_terminal_verifier_cycle(3) is None

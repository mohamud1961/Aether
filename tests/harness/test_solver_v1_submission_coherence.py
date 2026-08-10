from __future__ import annotations

import json

from aether.execution import CommandResult, MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.ledger import ExecutionLedger, Receipt
from aether.runtime_ir import (
    ActionRequest,
    AutomaticMemoryPolicy,
    CapabilityDescriptor,
    CompletionPolicy,
    EnvMap,
    RuntimeConfigIR,
    SolverTurn,
)
from aether.submission_coherence import (
    evaluate_submission_coherence,
    submission_recovery_directive,
)
from aether.tracing import RunTrace


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Create and verify out.txt.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file")
            ),
            "shell": CapabilityDescriptor(
                "shell", "commands", tool_names=("run_command",)
            ),
        },
    )


def _runtime(*, memory_mode: str = "advisory") -> RuntimeConfigIR:
    return RuntimeConfigIR(
        architect_summary="submission coherence test",
        solver_identity_prompt="Submit only after observed evidence.",
        selected_capabilities=("filesystem", "shell"),
        automatic_memory_policy=AutomaticMemoryPolicy(mode=memory_mode),
        completion_policy=CompletionPolicy(
            require_authoritative_check=False,
            require_all_obligations=False,
            require_recent_progress=False,
        ),
    )


def _action(kind: str, arguments: dict, *, action_id: str) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id="shell" if kind == "run_command" else "filesystem",
        arguments=arguments,
        intent="resolve the current evidence gap",
        expected_observation="one objective result",
        if_fail_next="change strategy or report the blocker",
    )


def _act(action: ActionRequest, gap: str) -> SolverTurn:
    return SolverTurn(
        kind="act",
        summary=action.action_id,
        evidence_gap=gap,
        actions=(action,),
    )


def _submit() -> SolverTurn:
    return SolverTurn(kind="submit_outcome", summary="submit observed result")


class _Hooks:
    def __init__(
        self,
        turns: list[SolverTurn],
        *,
        memory_mode: str = "advisory",
        verdict: str = "completed",
    ) -> None:
        self.turns = list(turns)
        self.runtime = _runtime(memory_mode=memory_mode)
        self.verdict = verdict
        self.verify_calls = 0

    def architect(self, request):
        return self.runtime

    def solve(self, messages, compiled):
        return self.turns.pop(0)

    def verify(self, packet, compiled, ledger):
        self.verify_calls += 1
        return json.dumps({
            "verdict": self.verdict,
            "summary": f"verifier returned {self.verdict}",
        })


def _blocked(result) -> list[Receipt]:
    return [r for r in result.receipts if r.kind == "submission_coherence_blocked"]


def test_initial_submission_without_prior_solver_action_is_allowed() -> None:
    hooks = _Hooks([_submit()])
    result = AetherNextKernel(max_steps=1).run(_env(), MemoryExecutor(), hooks)
    assert hooks.verify_calls == 1
    assert not _blocked(result)


def test_unobserved_write_blocks_checks_and_verifier() -> None:
    turns = [
        _act(_action("write_file", {"path": "out.txt", "content": "done"}, action_id="write"), "out.txt is absent"),
        _submit(),
    ]
    hooks = _Hooks(turns)
    result = AetherNextKernel(max_steps=2).run(_env(), MemoryExecutor(), hooks)
    assert hooks.verify_calls == 0
    assert _blocked(result)[0].failure_class == "unobserved_state_change"
    assert not any(r.kind == "completion_gate" for r in result.receipts if r.step == 1)
    assert any(
        r.kind == "model_verifier_skipped"
        and r.payload.get("reason") == "submission_coherence_blocked"
        for r in result.receipts
    )


def test_submission_block_is_forced_into_next_solver_context() -> None:
    turns = [
        _act(_action("write_file", {"path": "out.txt", "content": "done"}, action_id="write"), "out.txt is absent"),
        _submit(),
        _act(_action("read_file", {"path": "out.txt"}, action_id="read"), "the blocked submission requires observed evidence"),
    ]
    hooks = _Hooks(turns)
    trace = RunTrace()
    AetherNextKernel(max_steps=3).run(
        _env(), MemoryExecutor(), hooks, trace=trace,
    )
    context = trace.steps[2]["context_seen"]
    denied = context["blocked_denied_receipts"]
    row = next(item for item in denied if item["kind"] == "submission_coherence_blocked")
    assert row["failure_class"] == "unobserved_state_change"
    assert row["reason_code"] == "unobserved_state_change"
    assert row["latest_progress_classification"] == "state_changed"
    assert row["blocked_round"] == 1
    directive = context["submission_recovery_directive"]
    assert directive["reason_code"] == "unobserved_state_change"
    assert directive["submission_allowed"] is False
    assert directive["required_next_turn_kind"] == "act"
    assert directive["forbidden_next_turn_kind"] == "submit_outcome"
    assert "observation-producing action" in directive["message"]


def test_submission_recovery_directive_never_chooses_task_action() -> None:
    row = submission_recovery_directive(
        "unchanged_resubmission",
        "No evidence changed after the previous submission.",
    )
    assert row["task_action_owner"] == "solver"
    assert row["required_next_turn_kind"] == "act"
    assert row["forbidden_next_turn_kind"] == "submit_outcome"
    rendered = json.dumps(row, sort_keys=True)
    for forbidden in ("read_file", "write_file", "run_command", "probe_service"):
        assert forbidden not in rendered


def test_successful_observation_after_write_rearms_submission() -> None:
    turns = [
        _act(_action("write_file", {"path": "out.txt", "content": "done"}, action_id="write"), "out.txt is absent"),
        _act(_action("read_file", {"path": "out.txt"}, action_id="read"), "the written bytes are unobserved"),
        _submit(),
    ]
    hooks = _Hooks(turns)
    result = AetherNextKernel(max_steps=3).run(_env(), MemoryExecutor(), hooks)
    assert hooks.verify_calls == 1
    assert not _blocked(result)
    assert result.status == "completed"


def test_failed_action_blocks_submission_until_recovery() -> None:
    turns = [
        _act(_action("read_file", {"path": "missing.txt"}, action_id="read-missing"), "the file state is unknown"),
        _submit(),
    ]
    hooks = _Hooks(turns)
    result = AetherNextKernel(max_steps=2).run(_env(), MemoryExecutor(), hooks)
    assert hooks.verify_calls == 0
    assert _blocked(result)[0].failure_class == "failed_action_without_recovery"


def test_repeat_policy_block_cannot_be_followed_by_submission() -> None:
    read = _action("read_file", {"path": "out.txt"}, action_id="read")
    turns = [
        _act(read, "the file is unknown"),
        _act(read, "confirm whether the file changed"),
        _submit(),
    ]
    hooks = _Hooks(turns, memory_mode="soft_block_exact_repeat")
    result = AetherNextKernel(max_steps=3).run(
        _env(), MemoryExecutor(files={"out.txt": "done"}), hooks
    )
    assert hooks.verify_calls == 0
    assert _blocked(result)[0].failure_class == "equivalent_repeat_blocked"
    assert len([r for r in result.receipts if r.kind == "read_file"]) == 1


def test_turn_validation_failure_blocks_next_submit() -> None:
    invalid = SolverTurn(
        kind="act",
        summary="invalid empty action frontier",
        evidence_gap="the action was omitted",
        actions=(),
    )
    hooks = _Hooks([invalid, _submit()])
    result = AetherNextKernel(max_steps=2).run(_env(), MemoryExecutor(), hooks)
    assert hooks.verify_calls == 0
    assert _blocked(result)[0].failure_class == (
        "protocol_or_turn_failure_without_observation"
    )


def test_unchanged_resubmission_stalemates_without_more_verifier_calls() -> None:
    hooks = _Hooks([_submit(), _submit(), _submit(), _submit()], verdict="uncertain_missing_evidence")
    result = AetherNextKernel(max_steps=4).run(_env(), MemoryExecutor(), hooks)
    assert hooks.verify_calls == 1
    assert result.status == "solver_submit_stalemate"
    assert len(_blocked(result)) == 3
    assert all(row.failure_class == "unchanged_resubmission" for row in _blocked(result))


def test_successful_protocol_correction_clears_protocol_only_barrier() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        "step-0:solver_parse_error", 0, "solver_parse_error", False,
        "invalid output", failure_class="solver_protocol_error",
    ))
    ledger.record(Receipt(
        "step-0:solver_protocol_correction_result", 0,
        "solver_protocol_correction_result", True,
        "bounded correction returned one valid submit turn",
    ))
    decision = evaluate_submission_coherence(ledger, current_step=0)
    assert decision.allowed is True


def test_recovery_directive_is_preflighted_after_mutation_and_clears_after_observation() -> None:
    turns = [
        _act(_action("write_file", {"path": "out.txt", "content": "done"}, action_id="write"), "out.txt is absent"),
        _act(_action("read_file", {"path": "out.txt"}, action_id="read"), "observe written bytes"),
        _submit(),
    ]
    hooks = _Hooks(turns)
    trace = RunTrace()
    result = AetherNextKernel(max_steps=3).run(
        _env(), MemoryExecutor(), hooks, trace=trace,
    )
    after_write = trace.steps[1]["context_seen"]
    assert after_write["submission_recovery_directive"]["reason_code"] == "unobserved_state_change"
    assert after_write["submission_recovery_directive"]["blocked_receipt_id"] == ""
    after_read = trace.steps[2]["context_seen"]
    assert "submission_recovery_directive" not in after_read
    assert result.status == "completed"


# ---------------------------------------------------------------------------
# Post-vNext2 closure: expose existing mutating-command output as observation
# ---------------------------------------------------------------------------

def test_mutating_command_recovery_context_exposes_exact_read_output_route() -> None:
    command = "compile-and-verify"
    executor = MemoryExecutor()
    executor.register_command(
        command,
        lambda _executor, _command: CommandResult(
            command=command,
            exit_code=0,
            stdout="release_exit:0\n",
            modified_paths=("/app/release",),
        ),
    )
    turns = [
        _act(
            _action("run_command", {"command": command}, action_id="compile"),
            "the repaired program has not been exercised",
        ),
        _submit(),
    ]
    hooks = _Hooks(turns)
    trace = RunTrace()
    result = AetherNextKernel(max_steps=2).run(_env(), executor, hooks, trace=trace)
    context = trace.steps[1]["context_seen"]
    directive = context["submission_recovery_directive"]
    assert directive["reason_code"] == "unobserved_state_change"
    assert directive["record_observation_is_direct_evidence"] is False
    routes = directive["available_direct_observation_routes"]
    assert routes == [{
        "kind": "read_output",
        "arguments": {"handle": "0:compile:stdout"},
        "source_receipt_id": "step-0:compile:cmd",
        "stream": "stdout",
        "bytes": len("release_exit:0\n"),
        "authority": "existing_execution_result_handle",
    }]
    assert "record_observation does not clear" in directive["route_note"]
    assert hooks.verify_calls == 0
    assert result.status != "completed"


def test_submission_observation_routes_are_not_invented_without_output_bytes() -> None:
    from aether.context_views import submission_observation_routes

    ledger = ExecutionLedger()
    ledger.record(Receipt(
        "step-0:cmd", 0, "run_command", True, "mutated without output",
        state_change=True, payload={
            "stdout_handle": "0:cmd:stdout", "stdout_bytes": 0,
            "stderr_handle": "0:cmd:stderr", "stderr_bytes": 0,
        },
    ))
    ledger.record(Receipt(
        "step-0:progress", 0, "solver_progress_assessment", True, "state changed",
        payload={
            "classification": "state_changed",
            "result_receipt_ids": ["step-0:cmd"],
            "progress_signals": ["state_change", "new_evidence"],
        },
    ))
    assert submission_observation_routes(
        ledger, progress_receipt_id="step-0:progress",
    ) == []

"""Capability-specific mechanical repetition tests for PCR V0."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from aether.ledger import ExecutionLedger, Receipt
from aether.pcr_provider_protocol import PCR_PRIMARY_TURN_SCHEMA
from aether.pcr_repeat import (
    PCR_REPEAT_DECLARATIONS,
    action_execution_committed_receipt,
    action_execution_pending_receipt,
    action_signature,
    evaluate_pcr_repeat,
    pending_execution_commitment,
    permit_consumed_receipt,
    record_repeat_observation,
    repeat_block_receipts,
    repeat_reuse_receipt,
    relevant_state_fingerprint,
)
from aether.run_adapter import run_task
from aether.runtime_ir import ActionRequest


def _ledger(workspace_id: str = "/workspace") -> ExecutionLedger:
    ledger = ExecutionLedger()
    ledger.install_runtime_identity({
        "task_id": "task-repeat",
        "run_id": "run-repeat",
        "primary_agent_id": "primary-repeat",
        "workspace_id": workspace_id,
        "environment_id": "env-repeat",
        "budgets": {"max_kernel_steps": 12},
    })
    return ledger


def _action(kind: str, arguments: dict[str, object]) -> ActionRequest:
    return ActionRequest(
        action_id="pcr-test-action",
        kind=kind,
        capability_id="shell" if kind == "run_command" else "kernel",
        arguments=arguments,
        intent="",
        expected_observation="",
        if_fail_next="",
    )


def _observation(
    *,
    receipt_id: str,
    step: int,
    signature: str,
    state: str,
    result: str = "same-result",
) -> Receipt:
    return Receipt(
        receipt_id=receipt_id,
        step=step,
        kind="pcr_repeat_observation",
        success=True,
        summary="mechanical repeat observation",
        payload={
            "action_signature": signature,
            "relevant_state_fingerprint": state,
            "result_fingerprint": result,
            "state_changed": False,
            "outcome_receipt_ids": [f"step-{step}:result"],
        },
    )


def test_two_identical_no_change_results_block_third_and_issue_one_permit() -> None:
    ledger = _ledger()
    action = _action("run_command", {"command": "false"})
    signature = action_signature(action, ledger.runtime_identity)
    state = relevant_state_fingerprint(
        action, ledger, PCR_REPEAT_DECLARATIONS["run_command"],
    )
    ledger.record(_observation(
        receipt_id="step-1:obs", step=1, signature=signature, state=state,
    ))
    ledger.record(_observation(
        receipt_id="step-2:obs", step=2, signature=signature, state=state,
    ))

    blocked = evaluate_pcr_repeat(action, ledger, step=3)
    assert blocked.consequence == "block"
    assert blocked.issue_permit is True
    rows = repeat_block_receipts(action, blocked, step=3)
    assert [row.kind for row in rows] == ["pcr_repeat_block", "pcr_repeat_permit"]
    for row in rows:
        ledger.record(row)

    permitted = evaluate_pcr_repeat(action, ledger, step=4)
    assert permitted.consequence == "allow_with_permit"
    consumed = permit_consumed_receipt(action, permitted, step=4)
    ledger.record(consumed)

    blocked_again = evaluate_pcr_repeat(action, ledger, step=5)
    assert blocked_again.consequence == "block"
    assert blocked_again.issue_permit is False
    assert blocked_again.action_signature == signature
    assert blocked_again.relevant_state_fingerprint == state


def test_run_command_timeout_budget_does_not_change_repeat_identity() -> None:
    ledger = _ledger()
    identity = ledger.runtime_identity
    command = "python3 -m pytest -q"
    signatures = {
        action_signature(_action("run_command", arguments), identity)
        for arguments in (
            {"command": command},
            {"command": command, "timeout_s": 10},
            {"command": command, "timeout_s": 20},
            {"command": command, "timeout_s": 30},
        )
    }
    assert len(signatures) == 1


def test_run_command_timeout_drift_cannot_buy_fresh_successful_repeats() -> None:
    ledger = _ledger()
    first = _action("run_command", {"command": "printf ok", "timeout_s": 10})
    second = _action("run_command", {"command": "printf ok"})
    third = _action("run_command", {"command": "printf ok", "timeout_s": 30})
    signature = action_signature(first, ledger.runtime_identity)
    assert action_signature(second, ledger.runtime_identity) == signature
    assert action_signature(third, ledger.runtime_identity) == signature
    state = relevant_state_fingerprint(
        first, ledger, PCR_REPEAT_DECLARATIONS["run_command"],
    )
    ledger.record(_observation(
        receipt_id="step-1:obs", step=1, signature=signature, state=state,
        result="success-same",
    ))
    ledger.record(_observation(
        receipt_id="step-2:obs", step=2, signature=signature, state=state,
        result="success-same",
    ))
    decision = evaluate_pcr_repeat(third, ledger, step=3)
    assert decision.consequence == "block"
    assert decision.issue_permit is True


def test_run_command_helper_identity_remains_distinct_when_timeout_is_ignored() -> None:
    ledger = _ledger()
    identity = ledger.runtime_identity
    base = _action("run_command", {
        "command": "python .aether/tools/check.py",
        "helper_path": ".aether/tools/check.py",
        "helper_mode": "smoke_test",
        "timeout_s": 10,
    })
    timeout_only = _action("run_command", {
        "command": "python .aether/tools/check.py",
        "helper_path": ".aether/tools/check.py",
        "helper_mode": "smoke_test",
        "timeout_s": 60,
    })
    execute_mode = _action("run_command", {
        "command": "python .aether/tools/check.py",
        "helper_path": ".aether/tools/check.py",
        "helper_mode": "execute",
        "timeout_s": 10,
    })
    assert action_signature(base, identity) == action_signature(timeout_only, identity)
    assert action_signature(base, identity) != action_signature(execute_mode, identity)



def test_changed_capability_owned_state_resets_repeat_history() -> None:
    ledger = _ledger()
    action = _action("run_command", {"command": "false"})
    signature = action_signature(action, ledger.runtime_identity)
    state = relevant_state_fingerprint(
        action, ledger, PCR_REPEAT_DECLARATIONS["run_command"],
    )
    ledger.record(_observation(
        receipt_id="step-1:obs", step=1, signature=signature, state=state,
    ))
    ledger.record(_observation(
        receipt_id="step-2:obs", step=2, signature=signature, state=state,
    ))
    ledger.record(Receipt(
        receipt_id="step-3:write",
        step=3,
        kind="write_file",
        success=True,
        summary="changed workspace state",
        state_change=True,
        payload={"path": "out.txt", "after_content_hash": "a" * 64},
    ))

    decision = evaluate_pcr_repeat(action, ledger, step=4)
    assert decision.consequence == "allow"
    assert decision.relevant_state_fingerprint != state


def test_immutable_output_result_is_reused_without_dispatch_then_bounded() -> None:
    ledger = _ledger()
    ledger.record(Receipt(
        receipt_id="step-1:command",
        step=1,
        kind="run_command",
        success=True,
        summary="command output",
        payload={
            "command": "printf hello",
            "stdout": "hello",
            "stdout_handle": "output:hello",
            "stdout_hash": "b" * 64,
            "stdout_bytes": 5,
        },
    ))
    action = _action("read_output", {
        "handle": "output:hello",
        "offset": 0,
        "span": 100,
    })
    first = evaluate_pcr_repeat(action, ledger, step=1)
    assert first.consequence == "allow"
    result = Receipt(
        receipt_id="step-1:pcr-test-action:read_output",
        step=1,
        kind="read_output",
        success=True,
        summary="read immutable output",
        payload={
            "handle": "output:hello",
            "chunk": "hello",
            "offset": 0,
            "span": 100,
            "total_bytes": 5,
        },
    )
    ledger.record(result)
    observation = record_repeat_observation(
        action,
        first,
        step=1,
        step_receipts=[result],
        ledger=ledger,
    )
    ledger.record(observation)

    reuse_one = evaluate_pcr_repeat(action, ledger, step=2)
    assert reuse_one.consequence == "reuse"
    assert reuse_one.reused_outcome_receipt_ids == (result.receipt_id,)
    ledger.record(repeat_reuse_receipt(action, reuse_one, step=2))

    reuse_two = evaluate_pcr_repeat(action, ledger, step=3)
    assert reuse_two.consequence == "reuse"
    ledger.record(repeat_reuse_receipt(action, reuse_two, step=3))

    blocked = evaluate_pcr_repeat(action, ledger, step=4)
    assert blocked.consequence == "block"
    assert blocked.issue_permit is False
    assert "returned twice" in blocked.detail


def test_repeat_observation_contains_only_mechanical_fingerprints() -> None:
    ledger = _ledger()
    action = _action("run_command", {"command": "printf ok"})
    decision = evaluate_pcr_repeat(action, ledger, step=1)
    result = Receipt(
        receipt_id="step-1:pcr-test-action:run",
        step=1,
        kind="run_command",
        success=True,
        summary="command completed",
        payload={
            "command": "printf ok",
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
            "stdout_handle": "output:ok",
        },
    )
    ledger.record(result)
    observation = record_repeat_observation(
        action,
        decision,
        step=1,
        step_receipts=[result],
        ledger=ledger,
    )
    assert observation.payload["semantic_loop_judged"] is False
    assert observation.payload["strategy_judged"] is False
    assert observation.payload["relevant_state_owner"] == "task_state_generation"
    assert observation.payload["result_fingerprint"]
    assert "intent" not in observation.payload
    assert "hypothesis" not in observation.payload


def test_uncommitted_action_boundary_blocks_exact_replay_until_result_is_durable() -> None:
    ledger = _ledger()
    action = _action("run_command", {"command": "python3 mutate.py"})
    pending = action_execution_pending_receipt(action, ledger, step=1)
    ledger.record(pending)

    blocked = pending_execution_commitment(action, ledger)
    assert blocked is not None
    assert blocked.receipt_id == pending.receipt_id
    assert blocked.payload["at_most_once_boundary"] is True

    result = Receipt(
        receipt_id="step-1:pcr-test-action:run",
        step=1,
        kind="run_command",
        success=True,
        summary="command outcome was observed",
        payload={"command": "python3 mutate.py", "exit_code": 0},
    )
    ledger.record(result)
    ledger.record(action_execution_committed_receipt(
        action, pending, (result,), step=1,
    ))

    assert pending_execution_commitment(action, ledger) is None


def test_empty_or_unbound_execution_commit_cannot_clear_pending_boundary() -> None:
    ledger = _ledger()
    action = _action("run_command", {"command": "python3 mutate.py"})
    pending = action_execution_pending_receipt(action, ledger, step=1)
    ledger.record(pending)

    empty = action_execution_committed_receipt(action, pending, (), step=1)
    ledger.record(empty)
    assert empty.kind == "pcr_action_execution_uncommitted"
    assert empty.success is False
    assert pending_execution_commitment(action, ledger) is pending

    missing = Receipt(
        receipt_id="step-1:pcr-test-action:fake-commit",
        step=1,
        kind="pcr_action_execution_committed",
        success=True,
        summary="bookkeeping-only commit with no durable result",
        payload={
            "pending_receipt_id": pending.receipt_id,
            "action_signature": pending.payload["action_signature"],
            "relevant_state_fingerprint": pending.payload["relevant_state_fingerprint"],
            "outcome_receipt_ids": ["missing-result"],
            "outcome_observed": True,
        },
    )
    ledger.record(missing)
    assert pending_execution_commitment(action, ledger) is pending

    failed_result = Receipt(
        receipt_id="step-2:pcr-test-action:run",
        step=2,
        kind="run_command",
        success=False,
        summary="command outcome was observed as a failure",
        failure_class="command_failed",
        payload={"command": "python3 mutate.py", "exit_code": 1},
    )
    ledger.record(failed_result)
    ledger.record(action_execution_committed_receipt(
        action, pending, (failed_result,), step=2,
    ))
    assert pending_execution_commitment(action, ledger) is None


def test_model_authored_repeat_bypass_is_not_part_of_pcr_actions() -> None:
    # The PCR provider contract rejects unknown arguments, and the internal
    # repeat controller never reads model-authored allow/repeat justification.
    schema_text = json.dumps(PCR_PRIMARY_TURN_SCHEMA, sort_keys=True)
    for forbidden in ("allow_repeat", "repeat_justification", "why_repeat"):
        assert forbidden not in schema_text
    source_names = set(PCR_REPEAT_DECLARATIONS)
    assert "run_command" in source_names
    assert all(declaration.relevant_state for declaration in PCR_REPEAT_DECLARATIONS.values())


def test_kernel_loop_executes_twice_blocks_issues_one_permit_then_blocks() -> None:
    class ForbiddenArchitect:
        def __call__(self, messages, *, max_output_tokens=8000):
            del messages, max_output_tokens
            raise AssertionError("PCR repeat replay must not invoke Architect")

    class RepeatingPrimary:
        def __call__(self, messages, *, max_output_tokens=8000):
            del messages, max_output_tokens
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "run_command",
                    "arguments": {"command": "sh -c 'exit 7'"},
                },
            })

    class UnusedVerifier:
        def __call__(self, messages, *, max_output_tokens=8000):
            del messages, max_output_tokens
            raise AssertionError("repeat-only replay must not invoke Verifier")

    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        Path(task_dir, "README.md").write_text("repeat replay", encoding="utf-8")
        record = run_task(
            task_dir=task_dir,
            instruction_text="Diagnose the failing command without claiming completion.",
            solver_model=RepeatingPrimary(),
            verifier_model=UnusedVerifier(),
            workspace_root=workspace,
            max_steps=5,
            runtime_identity={
                "task_id": "repeat-integration",
                "run_id": "repeat-integration-run",
                "primary_agent_id": "repeat-integration-primary",
            },
        )

    kinds = [row["kind"] for row in record["receipt_summary"]]
    assert kinds.count("run_command") == 3
    assert kinds.count("pcr_action_execution_pending") == 3
    assert kinds.count("pcr_action_execution_committed") == 3
    assert kinds.count("pcr_repeat_observation") == 3
    assert kinds.count("pcr_repeat_block") == 2
    assert kinds.count("pcr_repeat_permit") == 1
    assert kinds.count("pcr_repeat_permit_consumed") == 1
    blocks = [row for row in record["receipt_summary"] if row["kind"] == "pcr_repeat_block"]
    assert all(row["failure_class"] == "equivalent_repeat_blocked" for row in blocks)


def test_path_repeat_state_ignores_observation_receipt_identity_and_blocks_third_read() -> None:
    ledger = _ledger(workspace_id="/app")
    action = ActionRequest(
        action_id="pcr-read-profile",
        kind="read_file",
        capability_id="filesystem",
        arguments={"path": "/app/profiles.json"},
        intent="",
        expected_observation="",
        if_fail_next="",
    )
    ledger.record(Receipt(
        receipt_id="step-1:write-profile",
        step=1,
        kind="write_file",
        success=True,
        summary="wrote profiles.json",
        state_change=True,
        payload={
            "path": "profiles.json",
            "after_content_hash": "d" * 16,
            "bytes": 136,
        },
    ))

    first = evaluate_pcr_repeat(action, ledger, step=2)
    assert first.consequence == "allow"
    first_result = Receipt(
        receipt_id="step-2:pcr-read-profile:read",
        step=2,
        kind="read_file",
        success=True,
        summary="read profiles.json (136 bytes)",
        payload={
            "path": "profiles.json",
            "content_hash": "d" * 16,
            "bytes": 136,
            "content": "same-current-file",
        },
    )
    ledger.record(first_result)
    first_observation = record_repeat_observation(
        action, first, step=2, step_receipts=[first_result], ledger=ledger,
    )
    ledger.record(first_observation)

    second = evaluate_pcr_repeat(action, ledger, step=3)
    assert second.consequence == "allow"
    second_result = Receipt(
        receipt_id="step-3:pcr-read-profile:read",
        step=3,
        kind="read_file",
        success=True,
        summary="read profiles.json (136 bytes)",
        payload={
            "path": "profiles.json",
            "content_hash": "d" * 16,
            "bytes": 136,
            "content": "same-current-file",
        },
    )
    ledger.record(second_result)
    second_observation = record_repeat_observation(
        action, second, step=3, step_receipts=[second_result], ledger=ledger,
    )
    ledger.record(second_observation)

    # Different observation receipts over the same mechanical file state must
    # collapse to one relevant-state identity.
    assert first_observation.payload["relevant_state_fingerprint"] == second_observation.payload[
        "relevant_state_fingerprint"
    ]
    third = evaluate_pcr_repeat(action, ledger, step=4)
    assert third.consequence == "block"
    assert third.issue_permit is True
    assert third.relevant_state_fingerprint == first_observation.payload[
        "relevant_state_fingerprint"
    ]

    # A real task mutation changes both generation/state and reopens the action.
    ledger.record(Receipt(
        receipt_id="step-4:real-mutation",
        step=4,
        kind="write_file",
        success=True,
        summary="changed profiles.json",
        state_change=True,
        payload={
            "path": "profiles.json",
            "after_content_hash": "e" * 16,
            "bytes": 137,
        },
    ))
    after_mutation = evaluate_pcr_repeat(action, ledger, step=5)
    assert after_mutation.consequence == "allow"
    assert after_mutation.relevant_state_fingerprint != third.relevant_state_fingerprint


def test_path_repeat_state_uses_declared_workspace_root_not_only_app() -> None:
    ledger = _ledger(workspace_id="/workspace")
    action = ActionRequest(
        action_id="pcr-read-generic-root",
        kind="read_file",
        capability_id="filesystem",
        arguments={"path": "/workspace/state.txt"},
        intent="",
        expected_observation="",
        if_fail_next="",
    )
    ledger.record(Receipt(
        receipt_id="step-1:read-a",
        step=1,
        kind="read_file",
        success=True,
        summary="read state A",
        payload={"path": "state.txt", "content_hash": "a" * 16, "bytes": 1},
    ))
    first = relevant_state_fingerprint(
        action, ledger, PCR_REPEAT_DECLARATIONS["read_file"],
    )
    ledger.record(Receipt(
        receipt_id="step-2:read-b",
        step=2,
        kind="read_file",
        success=True,
        summary="read state B",
        payload={"path": "state.txt", "content_hash": "b" * 16, "bytes": 1},
    ))
    second = relevant_state_fingerprint(
        action, ledger, PCR_REPEAT_DECLARATIONS["read_file"],
    )
    assert second != first


def test_report_blocker_rewording_is_one_diagnostic_per_unchanged_task_state() -> None:
    ledger = _ledger(workspace_id="/app")
    first = ActionRequest(
        action_id="block-1", kind="report_blocker", capability_id="diagnostic",
        arguments={"blocker": "speed target unmet", "evidence": "101 percent"},
        intent="", expected_observation="", if_fail_next="",
    )
    decision = evaluate_pcr_repeat(first, ledger, step=1)
    assert decision.consequence == "allow"
    outcome = Receipt(
        receipt_id="step-1:block-1:blocker", step=1, kind="report_blocker",
        success=False, summary="reported blocker", failure_class="solver_reported_blocker",
        payload={"blocker": "speed target unmet", "evidence": "101 percent"},
    )
    ledger.record(outcome)
    ledger.record(record_repeat_observation(
        first, decision, step=1, step_receipts=[outcome], ledger=ledger,
    ))
    second = ActionRequest(
        action_id="block-2", kind="report_blocker", capability_id="diagnostic",
        arguments={"blocker": "required performance remains unsatisfied", "evidence": "same state"},
        intent="", expected_observation="", if_fail_next="",
    )
    blocked = evaluate_pcr_repeat(second, ledger, step=2)
    assert blocked.consequence == "block"
    assert blocked.issue_permit is False
    assert blocked.declaration is not None
    assert blocked.declaration.mode == "one_per_state"

from __future__ import annotations

from blocks.recovery import remediation_inject, rollback


class _ErrorWithDetails(RuntimeError):
    def __init__(self, message: str, details: dict[str, object]):
        super().__init__(message)
        self.details = details


def test_remediation_inject_returns_composable_action_schema() -> None:
    history = [{"role": "user", "content": "solve task"}]
    error = _ErrorWithDetails("tool call malformed", {"status_code": 400})

    action = remediation_inject.handle_error(error, history)

    assert action["action"] == "inject_remediation"
    assert action["reason"] == "recovery_remediation_injection_prepared"
    assert action["error_type"] == "_ErrorWithDetails"
    assert action["history_length"] == 1
    assert action["cleanup_status"] == "completed"
    assert "recovery_cleanup_completed" in action["cleanup_completion_reason_codes"]
    assert "recovery_remediation_instruction_prepared" in action["cleanup_completion_reason_codes"]
    assert action["error_details"] == {"status_code": 400}

    recovery_actions = action["recovery_actions"]
    assert isinstance(recovery_actions, list)
    assert recovery_actions[0]["type"] == "context_injection"
    assert recovery_actions[0]["insertion"] == "append"
    assert recovery_actions[0]["message"]["role"] == "system"
    assert "Failure type: _ErrorWithDetails." in recovery_actions[0]["message"]["content"]
    assert recovery_actions[1] == {"type": "retry", "mode": "single_attempt"}


def test_rollback_trims_to_last_user_or_system_message() -> None:
    history = [
        {"role": "user", "content": "run command"},
        {"role": "assistant", "content": "calling tool"},
        {"role": "tool", "name": "raw_bash", "content": "exit=1"},
    ]
    error = RuntimeError("tool failed")

    action = rollback.handle_error(error, history)

    assert action["action"] == "rollback_history"
    assert action["reason"] == "recovery_rollback_plan_prepared"
    assert action["history_length"] == 3
    assert action["rollback_to_history_length"] == 1
    assert action["messages_to_drop"] == 2
    assert action["cleanup_status"] == "completed"
    assert "recovery_cleanup_completed" in action["cleanup_completion_reason_codes"]
    assert "recovery_rollback_trim_applied" in action["cleanup_completion_reason_codes"]

    rollback_step = action["recovery_actions"][0]
    assert rollback_step["type"] == "history_rollback"
    assert rollback_step["strategy"] == "trim_to_last_user_or_system_turn"
    assert rollback_step["target_history_length"] == 1
    assert rollback_step["messages_to_drop"] == 2
    assert action["recovery_actions"][1] == {"type": "retry", "mode": "single_attempt"}


def test_rollback_marks_noop_boundary_when_no_trim_needed() -> None:
    history = [{"role": "system", "content": "policy reminder"}]
    error = RuntimeError("transient completion failure")

    action = rollback.handle_error(error, history)

    assert action["rollback_to_history_length"] == 1
    assert action["messages_to_drop"] == 0
    assert "recovery_rollback_noop_boundary" in action["cleanup_completion_reason_codes"]

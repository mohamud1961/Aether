"""Rollback recovery — revert to last known good state on error.

Interface: RecoveryBlock.handle_error(error, history) -> recovery_action
"""

from __future__ import annotations

from typing import Any


def handle_error(error: Exception, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a rollback plan that can compose with downstream recovery handlers."""
    from_length = len(history)
    rollback_to_length = _rollback_target_length(history)
    messages_to_drop = max(0, from_length - rollback_to_length)
    rollback_code = (
        "recovery_rollback_trim_applied"
        if messages_to_drop > 0
        else "recovery_rollback_noop_boundary"
    )

    recovery_actions = [
        {
            "type": "history_rollback",
            "strategy": "trim_to_last_user_or_system_turn",
            "from_history_length": from_length,
            "target_history_length": rollback_to_length,
            "messages_to_drop": messages_to_drop,
        },
        {
            "type": "retry",
            "mode": "single_attempt",
        },
    ]

    action: dict[str, Any] = {
        "action": "rollback_history",
        "reason": "recovery_rollback_plan_prepared",
        "error_type": type(error).__name__,
        "history_length": from_length,
        "rollback_to_history_length": rollback_to_length,
        "messages_to_drop": messages_to_drop,
        "recovery_actions": recovery_actions,
        "cleanup_status": "completed",
        "cleanup_completion_reason_codes": [
            "recovery_cleanup_completed",
            rollback_code,
        ],
    }
    error_message = str(error)
    if error_message:
        action["error_message"] = error_message
    details = getattr(error, "details", None)
    if isinstance(details, dict) and details:
        action["error_details"] = dict(details)
    return action


def _rollback_target_length(history: list[dict[str, Any]]) -> int:
    for idx in range(len(history) - 1, -1, -1):
        message = history[idx]
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role in {"user", "system"}:
            return idx + 1
    return 0

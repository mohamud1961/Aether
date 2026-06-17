"""No recovery — model handles its own errors without harness intervention.

Interface: RecoveryBlock.handle_error(error, history) -> recovery_action
"""

from __future__ import annotations

from typing import Any


def handle_error(error: Exception, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Return an explicit no-op recovery action."""
    action = {
        "action": "none",
        "reason": "baseline_no_recovery",
        "error_type": type(error).__name__,
        "history_length": len(history),
        "cleanup_status": "completed",
        "cleanup_completion_reason_codes": ["no_recovery_noop_cleanup_completed"],
    }
    error_message = str(error)
    if error_message:
        action["error_message"] = error_message
    details = getattr(error, "details", None)
    if isinstance(details, dict) and details:
        action["error_details"] = details
    return action

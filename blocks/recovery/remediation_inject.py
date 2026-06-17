"""Remediation injection — inject fix instructions into context when errors are detected.

Interface: RecoveryBlock.handle_error(error, history) -> recovery_action
"""

from __future__ import annotations

from typing import Any


def handle_error(error: Exception, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a composable remediation plan with explicit cleanup reason codes."""
    error_type = type(error).__name__
    error_message = str(error)
    history_length = len(history)

    remediation_message = {
        "role": "system",
        "content": _build_remediation_prompt(error_type=error_type, error_message=error_message),
    }
    recovery_actions = [
        {
            "type": "context_injection",
            "insertion": "append",
            "message": remediation_message,
        },
        {
            "type": "retry",
            "mode": "single_attempt",
        },
    ]
    action: dict[str, Any] = {
        "action": "inject_remediation",
        "reason": "recovery_remediation_injection_prepared",
        "error_type": error_type,
        "history_length": history_length,
        "recovery_actions": recovery_actions,
        "cleanup_status": "completed",
        "cleanup_completion_reason_codes": [
            "recovery_cleanup_completed",
            "recovery_remediation_instruction_prepared",
        ],
    }
    if error_message:
        action["error_message"] = error_message
    details = getattr(error, "details", None)
    if isinstance(details, dict) and details:
        action["error_details"] = dict(details)
    return action


def _build_remediation_prompt(*, error_type: str, error_message: str) -> str:
    prompt = (
        "Recovery directive: the previous step failed. "
        f"Failure type: {error_type}. "
        "Inspect the most recent tool call or response, correct one concrete issue, "
        "then retry with exactly one corrective action."
    )
    if error_message:
        prompt = f'{prompt} Observed error: "{error_message}".'
    return prompt

"""Lean Recovery Block: Truncates verbose compiler errors and injects diagnostic cards.

Interface: handle_error(error: Exception, history: list[dict]) -> dict
"""

from __future__ import annotations
from typing import Any

def handle_error(error: Exception, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Generates a compacted, actionable diagnostic recovery action on exception."""
    error_msg = str(error)
    error_type = type(error).__name__
    
    # 1. Truncate long error outputs/traces
    if len(error_msg) > 1000:
        lines = error_msg.splitlines()
        head = "\n".join(lines[:10])
        tail = "\n".join(lines[-15:])
        error_msg = f"{head}\n\n... [TRUNCATED HIGH-VOLUME SYSTEM ERROR DEBRIS] ...\n\n{tail}"
        
    diagnostic_card = (
        f"### [HARNESS DIAGNOSTIC EVENT]\n"
        f"An execution exception occurred during runtime:\n"
        f"- **Error Type**: {error_type}\n"
        f"- **Details**: {error_msg}\n"
        f"\n**Harness Guidance**: Please inspect CWD and paths, revise your plan, and do not repeat the failing command."
    )
    
    return {
        "action": "inject_diagnostics",
        "reason": "lean_autopsy_diagnosed",
        "error_type": error_type,
        "error_message": error_msg,
        "diagnostic_card": diagnostic_card,
        "cleanup_status": "completed",
        "cleanup_completion_reason_codes": ["autopsy_cleanup_completed"],
    }

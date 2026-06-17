"""Layered verification with explicit non-substitution reason codes.

Interface: VerificationBlock.check(task, workspace_state) -> verified: bool
"""

from __future__ import annotations

from typing import Any

from blocks.verification.layered_acceptance_guard import evaluate_layered_acceptance


def check(task: str, workspace_state: dict[str, Any]) -> bool:
    """Keep boolean output while publishing layered verification metadata."""
    _ = task
    decision = evaluate_layered_acceptance(workspace_state)
    workspace_state["verification_reason_codes"] = list(decision["reason_codes"])
    workspace_state["verification_substitution_violations"] = list(
        decision["substitution_violations"]
    )
    workspace_state["verification_layer_statuses"] = dict(decision["layer_statuses"])
    return bool(decision["verified"])

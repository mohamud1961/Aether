"""Completion gate that exposes exact layered verification telemetry.

Interface: VerificationBlock.check(task, workspace_state) -> verified: bool
"""

from __future__ import annotations

from typing import Any

from .layered_acceptance_guard import evaluate_layered_acceptance


def check(task: str, workspace_state: dict[str, Any]) -> bool:
    """Reject final claims unless the repaired layer tuple passes."""
    decision = evaluate_layered_acceptance(workspace_state)
    workspace_state["verification_reason_codes"] = decision["reason_codes"]
    workspace_state["verification_substitution_violations"] = decision[
        "substitution_violations"
    ]
    workspace_state["verification_layer_statuses"] = decision["layer_statuses"]
    workspace_state["completion_gate_decision"] = {
        "task_present": isinstance(task, str) and bool(task),
        "gate": "layered_completion_non_substitution",
        "verified": decision["verified"],
    }
    return bool(decision["verified"])

"""Authoritative completion-closure verification."""

from __future__ import annotations

from typing import Any

from .closure_truth_state import build_closure_state
from .layered_acceptance_guard import evaluate_layered_acceptance


def check(task: str, workspace_state: dict[str, Any]) -> bool:
    closure_state = build_closure_state(task, workspace_state)
    layer_statuses = {
        "L0_inline_assertion": "pass" if workspace_state.get("model_claimed_done") else "fail",
        "L1_verifier_artifact": _verifier_layer_status(
            workspace_state.get("closure_contract"),
            closure_state.get("latest_verifier_result"),
            closure_state.get("path_mismatches", []),
        ),
        "L2_replay_or_state_grader": "pass"
        if not closure_state.get("path_mismatches") and closure_state["final_answer_projection"]["artifact_paths_mentioned"]
        else "fail",
        "L4_final_acceptance": "pass" if closure_state["status"] == "solved" else "fail",
    }
    decision = evaluate_layered_acceptance(
        {
            "model_claimed_done": workspace_state.get("model_claimed_done"),
            "layer_statuses": layer_statuses,
        }
    )
    verified = bool(decision["verified"] and closure_state["status"] == "solved")
    workspace_state["authoritative_closure_state"] = closure_state
    workspace_state["verification_reason_codes"] = _dedupe(
        list(decision["reason_codes"]) + list(closure_state["reason_codes"])
    )
    workspace_state["verification_substitution_violations"] = list(decision["substitution_violations"])
    workspace_state["verification_layer_statuses"] = dict(layer_statuses)
    workspace_state["completion_gate_decision"] = {
        "task_present": isinstance(task, str) and bool(task),
        "gate": "authoritative_completion_closure_state",
        "verified": verified,
        "closure_status": closure_state["status"],
    }
    return verified


def _verifier_layer_status(
    contract: Any,
    latest_verifier: dict[str, Any] | None,
    path_mismatches: list[str],
) -> str:
    closure_contract = dict(contract) if isinstance(contract, dict) else {}
    if closure_contract.get("requires_verifier"):
        if latest_verifier is None:
            return "fail"
        return "pass" if latest_verifier["status"] == "pass" else "fail"
    return "pass" if not path_mismatches else "fail"


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered

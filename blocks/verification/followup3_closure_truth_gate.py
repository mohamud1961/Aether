"""Authoritative completion-closure verification for Phase 6.5 follow-up 3."""

from __future__ import annotations

from .followup3_closure_truth_state import build_followup3_closure_state
from .layered_acceptance_guard import evaluate_layered_acceptance


def check(task: str, workspace_state: dict[str, object]) -> bool:
    closure_state = build_followup3_closure_state(task, workspace_state)
    projection = closure_state["final_answer_projection"]
    latest = closure_state.get("latest_verifier_result")
    requires_verifier = bool(dict(workspace_state.get("closure_contract") or {}).get("requires_verifier"))
    layer_statuses = {
        "L0_inline_assertion": "pass" if workspace_state.get("model_claimed_done") else "fail",
        "L1_verifier_artifact": _verifier_layer_status(
            requires_verifier, latest, closure_state.get("path_mismatches", []), closure_state.get("wrong_target_written_paths", [])
        ),
        "L2_replay_or_state_grader": "pass"
        if not closure_state.get("path_mismatches")
        and not closure_state.get("wrong_target_written_paths")
        and projection["required_artifact_paths_mentioned"]
        and (not requires_verifier or projection["latest_truthful_verifier_state_mentioned"])
        else "fail",
        "L4_final_acceptance": "pass" if closure_state["closure_contract_status"] == "pass" else "fail",
    }
    decision = evaluate_layered_acceptance(
        {"model_claimed_done": workspace_state.get("model_claimed_done"), "layer_statuses": layer_statuses}
    )
    verified = bool(decision["verified"] and closure_state["closure_contract_status"] == "pass")
    workspace_state["authoritative_closure_state"] = closure_state
    workspace_state["verification_reason_codes"] = _dedupe(list(decision["reason_codes"]) + list(closure_state["reason_codes"]))
    workspace_state["verification_substitution_violations"] = list(decision["substitution_violations"])
    workspace_state["verification_layer_statuses"] = dict(layer_statuses)
    workspace_state["completion_gate_decision"] = {
        "task_present": isinstance(task, str) and bool(task),
        "gate": "followup3_authoritative_target_resolution_closure_state",
        "verified": verified,
        "closure_contract_status": closure_state["closure_contract_status"],
        "task_truth_status": closure_state["task_truth_status"],
    }
    return verified


def _verifier_layer_status(
    requires_verifier: bool,
    latest: dict[str, object] | None,
    mismatches: list[str],
    wrong_writes: list[str],
) -> str:
    if requires_verifier:
        if latest is None:
            return "fail"
        return "pass" if latest["status"] == "pass" else "fail"
    return "pass" if not mismatches and not wrong_writes else "fail"


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered

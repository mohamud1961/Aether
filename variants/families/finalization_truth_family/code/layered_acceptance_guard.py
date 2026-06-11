"""Deterministic layered acceptance checks for verification.

Interface helper for VerificationBlock implementations:
evaluate_layered_acceptance(workspace_state) -> decision metadata
"""

from __future__ import annotations

from typing import Any

REQUIRED_LAYERS = (
    "L0_inline_assertion",
    "L1_verifier_artifact",
    "L2_replay_or_state_grader",
    "L4_final_acceptance",
)
LOWER_REQUIRED_LAYERS = (
    "L0_inline_assertion",
    "L1_verifier_artifact",
    "L2_replay_or_state_grader",
)

MISSING_REASON_CODES = {
    "L0_inline_assertion": "required_layer_missing_l0_inline_assertion",
    "L1_verifier_artifact": "required_layer_missing_l1_verifier_artifact",
    "L2_replay_or_state_grader": "required_layer_missing_l2_replay_or_state_grader",
    "L4_final_acceptance": "required_layer_missing_l4_final_acceptance",
}
SUBSTITUTION_REASON_CODES = {
    "L0_inline_assertion": "non_substitution_violation_l4_over_l0_inline_assertion",
    "L1_verifier_artifact": "non_substitution_violation_l4_over_l1_verifier_artifact",
    "L2_replay_or_state_grader": "non_substitution_violation_l4_over_l2_replay_or_state_grader",
}


def evaluate_layered_acceptance(workspace_state: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic layered verification metadata from workspace signals."""
    layer_statuses = _resolve_layer_statuses(workspace_state)
    reason_codes: list[str] = []
    substitution_violations: list[str] = []
    model_claimed_done = bool(workspace_state.get("model_claimed_done", False))

    for layer_id in REQUIRED_LAYERS:
        if layer_statuses[layer_id] in {"unavailable", "not_applicable"}:
            reason_codes.append(MISSING_REASON_CODES[layer_id])

    if model_claimed_done:
        for layer_id in LOWER_REQUIRED_LAYERS:
            if layer_statuses[layer_id] != "pass":
                substitution_violations.append(SUBSTITUTION_REASON_CODES[layer_id])
    else:
        reason_codes.append("verification_completion_not_claimed")

    if not _has_layer_signal(workspace_state):
        reason_codes.append("verification_layer_signal_unavailable")

    verified = model_claimed_done and not substitution_violations and all(
        layer_statuses[layer_id] == "pass" for layer_id in REQUIRED_LAYERS
    )
    if not verified:
        reason_codes.append("layered_acceptance_rejected")

    return {
        "verified": verified,
        "reason_codes": _unique(reason_codes),
        "substitution_violations": _unique(substitution_violations),
        "layer_statuses": layer_statuses,
    }


def _resolve_layer_statuses(workspace_state: dict[str, Any]) -> dict[str, str]:
    score_envelope = workspace_state.get("score_envelope")
    if isinstance(score_envelope, dict):
        score_layers = score_envelope.get("layers")
        statuses = _statuses_from_layer_mapping(score_layers)
        if statuses is not None:
            return statuses

    layer_statuses = workspace_state.get("layer_statuses")
    statuses = _statuses_from_layer_mapping(layer_statuses)
    if statuses is not None:
        return statuses

    return _statuses_from_legacy_signals(workspace_state)


def _statuses_from_layer_mapping(layer_mapping: Any) -> dict[str, str] | None:
    if not isinstance(layer_mapping, dict):
        return None

    statuses: dict[str, str] = {}
    for layer_id in REQUIRED_LAYERS:
        layer_data = layer_mapping.get(layer_id)
        if isinstance(layer_data, dict):
            status = layer_data.get("status")
        else:
            status = layer_data
        statuses[layer_id] = _normalize_layer_status(status)
    return statuses


def _statuses_from_legacy_signals(workspace_state: dict[str, Any]) -> dict[str, str]:
    model_claimed_done = bool(workspace_state.get("model_claimed_done", False))
    return {
        "L0_inline_assertion": _bool_status(workspace_state.get("inline_assertion_pass")),
        "L1_verifier_artifact": _bool_status(
            workspace_state.get("verifier_artifact_present")
            or workspace_state.get("verifier_artifact_ref")
        ),
        "L2_replay_or_state_grader": _bool_status(
            workspace_state.get("replay_layer_pass")
            or workspace_state.get("replay_or_state_grader_pass")
        ),
        "L4_final_acceptance": "pass" if model_claimed_done else "fail",
    }


def _bool_status(value: Any) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "unavailable"


def _normalize_layer_status(value: Any) -> str:
    if value in {"pass", "fail", "unavailable", "not_applicable"}:
        return str(value)
    return "unavailable"


def _has_layer_signal(workspace_state: dict[str, Any]) -> bool:
    if isinstance(workspace_state.get("score_envelope"), dict):
        return True
    if isinstance(workspace_state.get("layer_statuses"), dict):
        return True
    return any(
        key in workspace_state
        for key in (
            "inline_assertion_pass",
            "verifier_artifact_present",
            "verifier_artifact_ref",
            "replay_layer_pass",
            "replay_or_state_grader_pass",
        )
    )


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered

"""Score-envelope construction and Packet 01 guard checks."""

from __future__ import annotations

from typing import Any

from runner.schemas import (
    LAYER_IDS,
    SCORE_ENVELOPE_VERSION,
    clone_score_envelope,
    make_score_envelope,
    validate_score_envelope,
)

PACKET01_REQUIRED_CONTRACT_CHECKS = (
    "record_contract_integrity",
    "layer_completeness_and_enum",
    "non_substitution_guard",
    "fallback_attribution",
    "capture_only_block",
    "provider_route_non_leakage",
    "l3_pinning_guard",
)


def build_score_envelope(
    *,
    run_id: str,
    benchmark_id: str,
    case_id: str,
    adapter: dict[str, Any] | None = None,
    layers: dict[str, dict[str, Any]] | None = None,
    final_verdict: str = "unresolved",
) -> dict[str, Any]:
    return make_score_envelope(
        run_id=run_id,
        benchmark_id=benchmark_id,
        case_id=case_id,
        scoring_contract_version=SCORE_ENVELOPE_VERSION,
        layers=layers,
        adapter=adapter,
        final_verdict=final_verdict,
    )


def apply_packet01_guards(envelope: dict[str, Any]) -> dict[str, Any]:
    guarded = clone_score_envelope(envelope)
    layers = guarded["layers"]
    aggregate = guarded["aggregate"]

    _guard_l2_not_substituted_by_l3(layers, aggregate)
    _guard_missing_verifier_artifact(layers, aggregate)
    _guard_projection_fallback(layers, aggregate)
    _guard_capture_only(layers, guarded["adapter"], aggregate)
    _guard_l3_pinning(layers, aggregate)
    _refresh_unresolved_layers(layers, aggregate)

    return validate_score_envelope(guarded)


def can_run_model_smoke(contract_results: dict[str, bool]) -> bool:
    if set(contract_results.keys()) != set(PACKET01_REQUIRED_CONTRACT_CHECKS):
        return False
    return all(contract_results[name] is True for name in PACKET01_REQUIRED_CONTRACT_CHECKS)


def _add_reason(layer: dict[str, Any], reason_code: str) -> None:
    if reason_code not in layer["reason_codes"]:
        layer["reason_codes"].append(reason_code)


def _add_violation(aggregate: dict[str, Any], violation: str) -> None:
    if violation not in aggregate["substitution_guard_violations"]:
        aggregate["substitution_guard_violations"].append(violation)


def _degrade_to_unresolved(aggregate: dict[str, Any]) -> None:
    if aggregate["final_verdict"] != "blocked_non_promotable":
        aggregate["final_verdict"] = "unresolved"


def _guard_l2_not_substituted_by_l3(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
) -> None:
    l2 = layers["L2_replay_or_state_grader"]
    l3 = layers["L3_judge_layer"]
    if l2["status"] == "unavailable" and l3["status"] == "pass":
        _add_reason(l2, "replay_data_gap")
        _add_violation(aggregate, "l2_unavailable_cannot_be_substituted_by_l3_pass")
        _degrade_to_unresolved(aggregate)


def _guard_missing_verifier_artifact(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
) -> None:
    l1 = layers["L1_verifier_artifact"]
    l4 = layers["L4_final_acceptance"]
    missing_artifact = l1["status"] == "unavailable" or not l1.get("artifact_ref")
    if missing_artifact and l4["status"] == "pass":
        _add_reason(l1, "verifier_artifact_missing")
        _add_violation(aggregate, "verifier_artifact_missing_cannot_be_hidden_by_l4_pass")
        _degrade_to_unresolved(aggregate)


def _guard_projection_fallback(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
) -> None:
    l4 = layers["L4_final_acceptance"]
    final_gate = l4.get("final_gate", {})
    is_projection = final_gate.get("gate_type") == "projection"
    if not is_projection:
        return

    _add_reason(l4, "final_projection_fallback")
    _add_violation(aggregate, "projection_fallback_non_promotable_for_packet02")
    _degrade_to_unresolved(aggregate)

    has_reason = bool(l4.get("projection_fallback_reason"))
    if not has_reason:
        _add_violation(aggregate, "projection_fallback_requires_explicit_reason")


def _guard_capture_only(
    layers: dict[str, dict[str, Any]],
    adapter: dict[str, Any],
    aggregate: dict[str, Any],
) -> None:
    benchmark_family = adapter.get("benchmark_family") or ""
    reason_present = any(
        "capture_only_non_promotable" in layers[layer_id]["reason_codes"]
        for layer_id in LAYER_IDS
    )
    if benchmark_family.startswith("capture_only") or reason_present:
        aggregate["final_verdict"] = "blocked_non_promotable"


def _guard_l3_pinning(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
) -> None:
    l3 = layers["L3_judge_layer"]
    if l3["status"] not in ("pass", "fail"):
        return
    judge_config = l3.get("judge_config", {})
    required = ("model", "prompt_fingerprint", "schema_fingerprint", "mode")
    if any(not judge_config.get(key) for key in required):
        _add_reason(l3, "judge_config_unpinned")
        _add_violation(aggregate, "active_l3_requires_pinned_judge_config")
        _degrade_to_unresolved(aggregate)


def _refresh_unresolved_layers(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
) -> None:
    unresolved = [
        layer_id
        for layer_id in LAYER_IDS
        if layers[layer_id]["status"] == "unavailable"
    ]
    aggregate["unresolved_layers"] = sorted(set(aggregate["unresolved_layers"]) | set(unresolved))

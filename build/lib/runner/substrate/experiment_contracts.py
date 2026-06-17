"""Packet 03 batch/result/recommendation contract validators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runner.schemas import (
    FINAL_VERDICTS,
    GOVERNED_TRUTH_AUTHORITY_COMPLETENESS,
    GOVERNED_TRUTH_COMPLETION_SCOPES,
    SchemaValidationError,
    SUCCESSOR_PRIMARY_COMPARATOR_VARIANT_ID,
    SUCCESSOR_RHV1_OBSERVED_MARKER_IDS,
    SUCCESSOR_RHV1_REFERENCE_VARIANT_ID,
    validate_comparability_fields,
    validate_evaluation_lane,
    validate_execution_mode,
    validate_governed_terminal_status,
    validate_lane_blocker_codes,
)

BATCH_SPEC_REQUIRED_FIELDS = (
    "batch_id",
    "packet_stage",
    "eval_family",
    "eval_ids",
    "variant_ids",
    "task_set_id",
    "task_tier",
    "rerun_count",
    "model_policy",
    "provider_route",
    "fixed_invariants",
    "budget_caps",
    "stability_budget_caps",
    "output_root",
    "evaluation_lane",
    "promotion_authority",
    "execution_mode_lock",
    "eval_card_refs",
)
PACKET04A_BATCH_REQUIRED_FIELDS = (
    "lane_blocker_policy",
    "route_contract_id",
    "ownership_bucket_map_ref",
    "variant_card_refs",
)

RESULT_RECORD_REQUIRED_FIELDS = (
    "batch_id",
    "run_id",
    "variant_id",
    "eval_id",
    "task_id",
    "rerun_index",
    "model_route",
    "score_summary",
    "reason_codes",
    "token_and_cost_summary",
    "evaluation_lane",
    "promotion_authority",
    "promotion_blocker_codes",
    "promotion_eligibility",
    "forced_probe_observed",
    "standin_observed",
    "legacy_lane_artifact_detected",
    "governed_truth_ref",
    "governed_terminal_status",
    "trace_summary_ref",
    "failure_cluster",
    "secondary_failure_tags",
    "promotion_flags",
    "run_artifact_refs",
)

TRACE_SUMMARY_REQUIRED_FIELDS = (
    "run_id",
    "raw_execution_truth",
    "governed_eval_truth",
    "error_summary",
    "loop_pattern_summary",
    "tool_error_summary",
    "workspace_integrity_summary",
    "verifier_final_contradiction_summary",
    "token_spike_summary",
    "recovery_summary",
)

RECOMMENDATION_CANDIDATE_REQUIRED_FIELDS = (
    "variant_id",
    "proposed_status",
    "rationale",
    "evidence_refs",
    "regression_risks",
    "token_cost_delta",
    "complexity_delta",
    "next_eval_or_transfer_step",
)
RECOMMENDATION_REQUIRED_FIELDS = (
    "recommendation_governance_version",
)
RECOMMENDATION_GATE_IDS = tuple(f"G{index}" for index in range(1, 16))
RECOMMENDATION_GATE_INPUT_REQUIRED_FIELDS = (
    "lane_class",
    "surface_bounded",
    "mechanism_visibility_complete",
    "schema_complete_for_promotion",
    "helper_only_evidence",
    "comparator_variant_id",
    "same_batch_comparator_run_ids",
    "primary_delta_metric",
    "corroboration_surface_ids",
    "audit_status_aa",
    "audit_status_ab",
    "audit_artifact_ref_aa",
    "audit_artifact_ref_ab",
    "forced_probe_observed",
    "standin_observed",
    "variant_card_ref",
    "route_manifest_ref",
    "route_manifest_fingerprint",
    "claimed_surface_fingerprints",
    "unchanged_surface_fingerprints",
    "governed_truth_ref",
    "governed_terminal_status",
)
RECOMMENDATION_LANE_CLASS_ALIASES = {
    "promotion": "promotion",
    "promotion_grade": "promotion",
    "guardrail_debug": "guardrail_debug",
    "guardrail_debug_only": "guardrail_debug",
    "bounded_diagnostic_only": "bounded_diagnostic",
    "mixed": "mixed",
    "missing": "missing",
}
ALLOWED_RECOMMENDATION_LANE_CLASSES = tuple(RECOMMENDATION_LANE_CLASS_ALIASES)
ALLOWED_AUDIT_STATUSES = ("pass", "fail", "missing")

ALLOWED_RECOMMENDATION_STATUSES = (
    "promote_to_atomic_eligible",
    "hold_for_more_evidence",
    "retire",
    "bound",
    "screened_no_uplift",
    "test_in_interaction",
    "test_in_transfer",
)

PROMOTION_BLOCKER_MARKERS = (
    "forced_probe",
    "standin",
    "bounded_l3",
    "schema_missing",
    "mechanism_visibility_incomplete",
    "guardrail_debug",
    "bounded_diagnostic",
    "legacy_stability_lane",
)
TOOL_FAMILY_AUTHORITY_EVAL_IDS = frozenset(
    {
        "ae_tool_call_contract_quality_v2",
        "ae_tool_result_attribution_quality_v2",
    }
)
WORKSPACE_TARGET_DECOY_GENERALIZATION_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_decoy_generalization_v2",
        "eval_workspace_target_decoy_generalization_atomic_v2",
    }
)
WORKSPACE_TARGET_MULTISTEP_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_decoy_generalization_multistep_v1",
        "eval_workspace_target_decoy_generalization_multistep_v1",
    }
)


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{path} must be an object")
    return value


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(f"{path} must be a non-empty string")
    return value


def _require_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise SchemaValidationError(f"{path} must be a non-empty list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(_require_string(item, f"{path}[{index}]"))
    return normalized


def _require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(f"{path} must be a boolean")
    return value


def _require_optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(f"{path} must be a non-empty string or null")
    return value


def _require_number_or_null(value: Any, path: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{path} must be a number or null")
    return float(value)


def _require_string_list_allow_empty(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{path} must be a list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(_require_string(item, f"{path}[{index}]"))
    return normalized


def normalize_recommendation_lane_class(value: Any, path: str = "recommendation_lane_class") -> str:
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(f"{path} must be one of {ALLOWED_RECOMMENDATION_LANE_CLASSES}")
    normalized = RECOMMENDATION_LANE_CLASS_ALIASES.get(value)
    if normalized is None:
        raise SchemaValidationError(f"{path} must be one of {ALLOWED_RECOMMENDATION_LANE_CLASSES}")
    return normalized


def validate_batch_spec(batch_spec: dict[str, Any]) -> dict[str, Any]:
    data = _require_mapping(batch_spec, "batch_spec")
    for field in BATCH_SPEC_REQUIRED_FIELDS:
        if field not in data:
            raise SchemaValidationError(f"batch_spec.{field} is required")

    for field in ("batch_id", "packet_stage", "eval_family", "task_set_id", "task_tier", "provider_route", "output_root"):
        _require_string(data.get(field), f"batch_spec.{field}")
    _require_string_list(data.get("eval_ids"), "batch_spec.eval_ids")
    _require_string_list(data.get("variant_ids"), "batch_spec.variant_ids")
    if not isinstance(data.get("rerun_count"), int) or data["rerun_count"] < 1:
        raise SchemaValidationError("batch_spec.rerun_count must be a positive int")
    for field in ("model_policy", "fixed_invariants", "budget_caps", "stability_budget_caps"):
        _require_mapping(data.get(field), f"batch_spec.{field}")

    lane = validate_evaluation_lane(data.get("evaluation_lane"), "batch_spec.evaluation_lane")
    promotion_authority = _require_bool(data.get("promotion_authority"), "batch_spec.promotion_authority")
    if promotion_authority != (lane == "promotion"):
        raise SchemaValidationError("batch_spec.promotion_authority must match batch_spec.evaluation_lane")
    if _is_packet04_batch_spec(data):
        for field in PACKET04A_BATCH_REQUIRED_FIELDS:
            if field not in data:
                raise SchemaValidationError(f"batch_spec.{field} is required for packet_04 batches")
        _require_string(data.get("lane_blocker_policy"), "batch_spec.lane_blocker_policy")
        _require_string(data.get("route_contract_id"), "batch_spec.route_contract_id")
        _require_string(data.get("ownership_bucket_map_ref"), "batch_spec.ownership_bucket_map_ref")
        variant_card_refs = _require_mapping(data.get("variant_card_refs"), "batch_spec.variant_card_refs")
        for variant_id, ref in variant_card_refs.items():
            _require_string(variant_id, "batch_spec.variant_card_refs.<variant_id>")
            _require_string(ref, f"batch_spec.variant_card_refs.{variant_id}")
        for variant_id in data["variant_ids"]:
            if variant_id not in variant_card_refs:
                raise SchemaValidationError(f"batch_spec.variant_card_refs missing entry for variant_id={variant_id}")

    execution_mode_lock = data.get("execution_mode_lock")
    lock_map = _require_mapping(execution_mode_lock, "batch_spec.execution_mode_lock")
    for eval_id, mode in lock_map.items():
        _require_string(eval_id, "batch_spec.execution_mode_lock.<eval_id>")
        validate_execution_mode(mode, f"batch_spec.execution_mode_lock.{eval_id}")
    eval_card_refs = data.get("eval_card_refs")
    refs_map = _require_mapping(eval_card_refs, "batch_spec.eval_card_refs")
    for eval_id, ref in refs_map.items():
        _require_string(eval_id, "batch_spec.eval_card_refs.<eval_id>")
        _require_string(ref, f"batch_spec.eval_card_refs.{eval_id}")
    if "claim_route_id" in data:
        _require_string(data.get("claim_route_id"), "batch_spec.claim_route_id")
    if "task_intent" in data:
        _require_string(data.get("task_intent"), "batch_spec.task_intent")
    if "budget_cap_usd" in data:
        _require_number_or_null(data.get("budget_cap_usd"), "batch_spec.budget_cap_usd")
    if "budget_spend_usd" in data:
        _require_number_or_null(data.get("budget_spend_usd"), "batch_spec.budget_spend_usd")
    task_cases = data.get("task_cases")
    if isinstance(task_cases, list):
        for index, task_case in enumerate(task_cases):
            if not isinstance(task_case, dict):
                continue
            if "claim_route_id" in task_case:
                _require_string(task_case.get("claim_route_id"), f"batch_spec.task_cases[{index}].claim_route_id")
            if "task_intent" in task_case:
                _require_string(task_case.get("task_intent"), f"batch_spec.task_cases[{index}].task_intent")
    return data


def validate_result_record(result_record: dict[str, Any]) -> dict[str, Any]:
    data = _require_mapping(result_record, "result_record")
    for field in RESULT_RECORD_REQUIRED_FIELDS:
        if field not in data:
            raise SchemaValidationError(f"result_record.{field} is required")

    for field in ("batch_id", "run_id", "variant_id", "eval_id", "task_id", "trace_summary_ref", "failure_cluster"):
        _require_string(data.get(field), f"result_record.{field}")
    _require_string(data.get("governed_truth_ref"), "result_record.governed_truth_ref")
    validate_governed_terminal_status(
        data.get("governed_terminal_status"),
        "result_record.governed_terminal_status",
    )
    if not isinstance(data.get("rerun_index"), int) or data["rerun_index"] < 0:
        raise SchemaValidationError("result_record.rerun_index must be a non-negative int")

    _require_mapping(data.get("model_route"), "result_record.model_route")
    score_summary = _require_mapping(data.get("score_summary"), "result_record.score_summary")
    final_verdict = _require_string(score_summary.get("final_verdict"), "result_record.score_summary.final_verdict")
    if final_verdict not in FINAL_VERDICTS:
        raise SchemaValidationError(
            f"result_record.score_summary.final_verdict must be one of {FINAL_VERDICTS}"
        )
    _require_mapping(data.get("token_and_cost_summary"), "result_record.token_and_cost_summary")
    _require_mapping(data.get("promotion_flags"), "result_record.promotion_flags")
    if "contender_id" in data:
        _require_string(data.get("contender_id"), "result_record.contender_id")
    if "claim_route_id" in data:
        _require_string(data.get("claim_route_id"), "result_record.claim_route_id")
    if "task_intent" in data:
        _require_string(data.get("task_intent"), "result_record.task_intent")
    if "budget_cap_usd" in data:
        _require_number_or_null(data.get("budget_cap_usd"), "result_record.budget_cap_usd")
    if "budget_spend_usd" in data:
        _require_number_or_null(data.get("budget_spend_usd"), "result_record.budget_spend_usd")
    token_summary = data.get("token_and_cost_summary")
    if isinstance(token_summary, dict) and "usd_estimate" in token_summary:
        _require_number_or_null(token_summary.get("usd_estimate"), "result_record.token_and_cost_summary.usd_estimate")

    if not isinstance(data.get("reason_codes"), list):
        raise SchemaValidationError("result_record.reason_codes must be a list")
    if not isinstance(data.get("secondary_failure_tags"), list):
        raise SchemaValidationError("result_record.secondary_failure_tags must be a list")
    for index, reason in enumerate(data["reason_codes"]):
        _require_string(reason, f"result_record.reason_codes[{index}]")
    for index, tag in enumerate(data["secondary_failure_tags"]):
        _require_string(tag, f"result_record.secondary_failure_tags[{index}]")

    validate_comparability_fields(data, "result_record")
    lane = validate_evaluation_lane(data.get("evaluation_lane"), "result_record.evaluation_lane")
    promotion_authority = _require_bool(data.get("promotion_authority"), "result_record.promotion_authority")
    if promotion_authority != (lane == "promotion"):
        raise SchemaValidationError("result_record.promotion_authority must match result_record.evaluation_lane")
    blocker_codes = validate_lane_blocker_codes(
        data.get("promotion_blocker_codes"),
        "result_record.promotion_blocker_codes",
    )
    promotion_eligibility = _require_string(data.get("promotion_eligibility"), "result_record.promotion_eligibility")
    forced_probe_observed = _require_bool(data.get("forced_probe_observed"), "result_record.forced_probe_observed")
    standin_observed = _require_bool(data.get("standin_observed"), "result_record.standin_observed")
    legacy_lane_artifact_detected = _require_bool(
        data.get("legacy_lane_artifact_detected"),
        "result_record.legacy_lane_artifact_detected",
    )
    if forced_probe_observed and "forced_probe_dependency" not in blocker_codes:
        raise SchemaValidationError(
            "result_record.forced_probe_observed=true requires forced_probe_dependency in promotion_blocker_codes"
        )
    if standin_observed and "standin_dependency" not in blocker_codes:
        raise SchemaValidationError(
            "result_record.standin_observed=true requires standin_dependency in promotion_blocker_codes"
        )
    if legacy_lane_artifact_detected and "legacy_stability_lane_artifact" not in blocker_codes:
        raise SchemaValidationError(
            "result_record.legacy_lane_artifact_detected=true requires legacy_stability_lane_artifact blocker"
        )
    if lane == "promotion":
        if final_verdict != "pass":
            if "lane_policy_restriction" not in blocker_codes:
                raise SchemaValidationError(
                    "failing promotion-lane records must include lane_policy_restriction in promotion_blocker_codes"
                )
        if promotion_eligibility == "eligible":
            if final_verdict != "pass":
                raise SchemaValidationError(
                    "result_record.evaluation_lane=promotion cannot be promotion_eligibility=eligible when final_verdict is not pass"
                )
            if blocker_codes:
                raise SchemaValidationError(
                    "result_record.evaluation_lane=promotion cannot include promotion_blocker_codes when promotion_eligibility=eligible"
                )
        else:
            if not promotion_eligibility.startswith("blocked_"):
                raise SchemaValidationError(
                    "result_record.evaluation_lane=promotion must use promotion_eligibility=eligible or a blocked_* status"
                )
            if not blocker_codes:
                raise SchemaValidationError(
                    "result_record.evaluation_lane=promotion with blocked promotion_eligibility must include promotion_blocker_codes"
                )
    else:
        if promotion_eligibility == "eligible":
            raise SchemaValidationError(
                "result_record.evaluation_lane must not report promotion_eligibility=eligible outside promotion lane"
            )
        if not blocker_codes:
            raise SchemaValidationError(
                "non-promotion lane records must include promotion_blocker_codes to prevent accidental promotion use"
            )
    run_artifact_refs = _require_mapping(data.get("run_artifact_refs"), "result_record.run_artifact_refs")
    for field in ("run_header_ref", "run_events_ref", "score_envelope_ref"):
        _require_string(run_artifact_refs.get(field), f"result_record.run_artifact_refs.{field}")
    eval_id = data.get("eval_id")
    if eval_id in TOOL_FAMILY_AUTHORITY_EVAL_IDS:
        if "#event_type=governed_eval_truth_finalized" not in data["governed_truth_ref"]:
            raise SchemaValidationError(
                "tool-family result records must reference governed_eval_truth_finalized in governed_truth_ref"
            )
        governed_terminal_status = data.get("governed_terminal_status")
        if governed_terminal_status not in {"tool_eval_completed", "tool_eval_incomplete", "tool_eval_execution_error"}:
            raise SchemaValidationError(
                "tool-family result records must emit governed_terminal_status as tool_eval_*"
            )
    _validate_lane_misuse(
        lane=lane,
        promotion_eligibility=promotion_eligibility,
        reason_codes=data["reason_codes"],
        secondary_failure_tags=data["secondary_failure_tags"],
        path="result_record",
    )
    return data


def validate_trace_summary(trace_summary: dict[str, Any]) -> dict[str, Any]:
    data = _require_mapping(trace_summary, "trace_summary")
    for field in TRACE_SUMMARY_REQUIRED_FIELDS:
        if field not in data:
            raise SchemaValidationError(f"trace_summary.{field} is required")
    _require_string(data.get("run_id"), "trace_summary.run_id")
    for field in TRACE_SUMMARY_REQUIRED_FIELDS[1:]:
        _require_mapping(data.get(field), f"trace_summary.{field}")
    raw_execution_truth = _require_mapping(data.get("raw_execution_truth"), "trace_summary.raw_execution_truth")
    _require_string(raw_execution_truth.get("execution_status"), "trace_summary.raw_execution_truth.execution_status")
    governed_eval_truth = _require_mapping(data.get("governed_eval_truth"), "trace_summary.governed_eval_truth")
    _require_string(governed_eval_truth.get("truth_source"), "trace_summary.governed_eval_truth.truth_source")
    _require_string(governed_eval_truth.get("truth_version"), "trace_summary.governed_eval_truth.truth_version")
    _require_string(governed_eval_truth.get("final_verdict"), "trace_summary.governed_eval_truth.final_verdict")
    validate_governed_terminal_status(
        governed_eval_truth.get("governed_terminal_status"),
        "trace_summary.governed_eval_truth.governed_terminal_status",
    )
    if "execution_mode" in data:
        validate_execution_mode(data["execution_mode"], "trace_summary.execution_mode")
    if "evaluation_lane" in data:
        validate_evaluation_lane(data["evaluation_lane"], "trace_summary.evaluation_lane")
    variant_id = data.get("variant_id")
    if variant_id is not None:
        _require_string(variant_id, "trace_summary.variant_id")
    eval_id = data.get("eval_id")
    if eval_id in TOOL_FAMILY_AUTHORITY_EVAL_IDS:
        _validate_tool_family_governed_truth(
            governed_eval_truth,
            path="trace_summary.governed_eval_truth",
        )
    if eval_id == "ae_tool_result_attribution_quality_v2":
        packet03_summary = _require_mapping(data.get("packet03_eval_summary"), "trace_summary.packet03_eval_summary")
        _validate_tool_result_attribution_trace(packet03_summary, "trace_summary.packet03_eval_summary")
    if eval_id == "ae_tool_call_contract_quality_v2":
        packet03_summary = _require_mapping(data.get("packet03_eval_summary"), "trace_summary.packet03_eval_summary")
        _validate_tool_call_contract_trace(packet03_summary, "trace_summary.packet03_eval_summary")
    if eval_id in WORKSPACE_TARGET_DECOY_GENERALIZATION_EVAL_IDS:
        packet03_summary = _require_mapping(data.get("packet03_eval_summary"), "trace_summary.packet03_eval_summary")
        _validate_workspace_target_decoy_trace(packet03_summary, "trace_summary.packet03_eval_summary")
    if eval_id in WORKSPACE_TARGET_MULTISTEP_EVAL_IDS:
        packet03_summary = _require_mapping(data.get("packet03_eval_summary"), "trace_summary.packet03_eval_summary")
        _validate_workspace_target_multistep_trace(packet03_summary, "trace_summary.packet03_eval_summary")
    _validate_successor_observed_mechanism_contract(data, path="trace_summary")
    return data


def _validate_successor_observed_mechanism_contract(summary: dict[str, Any], *, path: str) -> None:
    variant_id = summary.get("variant_id")
    if variant_id not in {SUCCESSOR_RHV1_REFERENCE_VARIANT_ID, SUCCESSOR_PRIMARY_COMPARATOR_VARIANT_ID}:
        return
    declared = _require_mapping(summary.get("declared_mechanisms"), f"{path}.declared_mechanisms")
    _require_string(
        declared.get("declared_mechanism_contract_version"),
        f"{path}.declared_mechanisms.declared_mechanism_contract_version",
    )
    _require_string(declared.get("variant_id"), f"{path}.declared_mechanisms.variant_id")
    _require_string_list_allow_empty(
        declared.get("claimed_runtime_keys"),
        f"{path}.declared_mechanisms.claimed_runtime_keys",
    )
    _require_string_list_allow_empty(
        declared.get("claimed_surface_ids"),
        f"{path}.declared_mechanisms.claimed_surface_ids",
    )
    observed = _require_mapping(summary.get("observed_mechanisms"), f"{path}.observed_mechanisms")
    _require_string(
        observed.get("observed_mechanism_contract_version"),
        f"{path}.observed_mechanisms.observed_mechanism_contract_version",
    )
    _require_string(observed.get("variant_id"), f"{path}.observed_mechanisms.variant_id")
    marker_family = _require_string(observed.get("marker_family"), f"{path}.observed_mechanisms.marker_family")
    markers = _require_mapping(observed.get("markers"), f"{path}.observed_mechanisms.markers")

    if variant_id == SUCCESSOR_RHV1_REFERENCE_VARIANT_ID:
        if marker_family != "rhv1_observed_markers.v1":
            raise SchemaValidationError(
                f"{path}.observed_mechanisms.marker_family must be rhv1_observed_markers.v1 for {SUCCESSOR_RHV1_REFERENCE_VARIANT_ID}"
            )
        missing = [marker_id for marker_id in SUCCESSOR_RHV1_OBSERVED_MARKER_IDS if marker_id not in markers]
        if missing:
            raise SchemaValidationError(
                f"{path}.observed_mechanisms.markers missing required RHv1 marker ids: {missing}"
            )
        for marker_id in SUCCESSOR_RHV1_OBSERVED_MARKER_IDS:
            marker_path = f"{path}.observed_mechanisms.markers.{marker_id}"
            marker_payload = _require_mapping(markers.get(marker_id), marker_path)
            _require_bool(marker_payload.get("observed"), f"{marker_path}.observed")
            _require_string_list_allow_empty(marker_payload.get("evidence_refs"), f"{marker_path}.evidence_refs")
        return

    if marker_family == "rhv1_observed_markers.v1":
        raise SchemaValidationError(
            f"{path}.observed_mechanisms.marker_family cannot be rhv1_observed_markers.v1 for {SUCCESSOR_PRIMARY_COMPARATOR_VARIANT_ID}"
        )
    if markers:
        raise SchemaValidationError(
            f"{path}.observed_mechanisms.markers must be empty for {SUCCESSOR_PRIMARY_COMPARATOR_VARIANT_ID}"
        )


def _validate_tool_result_attribution_trace(packet03_summary: dict[str, Any], path: str) -> None:
    mechanism_visible = bool(packet03_summary.get("mechanism_visibility_complete"))
    schema_complete = bool(packet03_summary.get("schema_complete_for_promotion"))
    if not mechanism_visible and not schema_complete:
        return
    case_results = packet03_summary.get("tool_result_attribution_case_results")
    if not isinstance(case_results, list) or not case_results:
        raise SchemaValidationError(f"{path}.tool_result_attribution_case_results must be populated for visible traces")
    for index, case in enumerate(case_results):
        case_path = f"{path}.tool_result_attribution_case_results[{index}]"
        row = _require_mapping(case, case_path)
        case_id = _require_string(row.get("case_id"), f"{case_path}.case_id")
        attribution_trace = _require_mapping(row.get("attribution_trace"), f"{case_path}.attribution_trace")
        permission_signal = _require_bool(
            attribution_trace.get("permission_signal_detected"),
            f"{case_path}.attribution_trace.permission_signal_detected",
        )
        runtime_signal = _require_bool(
            attribution_trace.get("runtime_signal_detected"),
            f"{case_path}.attribution_trace.runtime_signal_detected",
        )
        expected_reason = _require_string(row.get("expected_reason_code"), f"{case_path}.expected_reason_code")
        if expected_reason == "tool_runtime_mixed_permission_runtime_signals":
            if permission_signal is not True or runtime_signal is not True:
                raise SchemaValidationError(
                    f"{case_path}.attribution_trace must include both permission/runtime signals for mixed attribution case {case_id}"
                )


def _validate_tool_call_contract_trace(packet03_summary: dict[str, Any], path: str) -> None:
    mechanism_visible = bool(packet03_summary.get("mechanism_visibility_complete"))
    schema_complete = bool(packet03_summary.get("schema_complete_for_promotion"))
    if not mechanism_visible and not schema_complete:
        return
    case_results = packet03_summary.get("tool_contract_case_results")
    if not isinstance(case_results, list) or not case_results:
        raise SchemaValidationError(f"{path}.tool_contract_case_results must be populated for visible traces")
    for index, case in enumerate(case_results):
        case_path = f"{path}.tool_contract_case_results[{index}]"
        row = _require_mapping(case, case_path)
        _require_string(row.get("case_id"), f"{case_path}.case_id")
        for field in (
            "expected_contract_class",
            "observed_contract_class",
            "expected_result_class",
            "observed_result_class",
            "expected_reason_code",
            "observed_reason_code",
        ):
            _require_string(row.get(field), f"{case_path}.{field}")
        _require_bool(row.get("matched"), f"{case_path}.matched")


def _validate_workspace_target_decoy_trace(packet03_summary: dict[str, Any], path: str) -> None:
    mechanism_visible = bool(packet03_summary.get("mechanism_visibility_complete"))
    schema_complete = bool(packet03_summary.get("schema_complete_for_promotion"))
    if not mechanism_visible and not schema_complete:
        return
    _require_string(packet03_summary.get("workspace_target_target_id"), f"{path}.workspace_target_target_id")
    _require_string(packet03_summary.get("workspace_target_target_path"), f"{path}.workspace_target_target_path")
    decoy_ids = _require_string_list(packet03_summary.get("workspace_target_decoy_ids"), f"{path}.workspace_target_decoy_ids")
    decoy_paths = _require_string_list(packet03_summary.get("workspace_target_decoy_paths"), f"{path}.workspace_target_decoy_paths")
    if len(decoy_ids) != len(decoy_paths):
        raise SchemaValidationError(
            f"{path}.workspace_target_decoy_ids and {path}.workspace_target_decoy_paths must align in length"
        )
    _require_string(packet03_summary.get("workspace_target_regime_id"), f"{path}.workspace_target_regime_id")
    regime_rotation_index = packet03_summary.get("workspace_target_regime_rotation_index")
    if not isinstance(regime_rotation_index, int) or regime_rotation_index < 0:
        raise SchemaValidationError(
            f"{path}.workspace_target_regime_rotation_index must be a non-negative int"
        )
    regime_count = packet03_summary.get("workspace_target_regime_count")
    if not isinstance(regime_count, int) or regime_count < 2:
        raise SchemaValidationError(
            f"{path}.workspace_target_regime_count must be an int >= 2"
        )
    transfer_tier = _require_string(
        packet03_summary.get("workspace_target_transfer_tier"),
        f"{path}.workspace_target_transfer_tier",
    )
    if transfer_tier != "development_transfer":
        raise SchemaValidationError(
            f"{path}.workspace_target_transfer_tier must be development_transfer"
        )
    _require_bool(packet03_summary.get("workspace_target_hit"), f"{path}.workspace_target_hit")
    _require_bool(packet03_summary.get("workspace_decoy_touched"), f"{path}.workspace_decoy_touched")
    _require_bool(packet03_summary.get("workspace_target_content_ok"), f"{path}.workspace_target_content_ok")
    _require_bool(packet03_summary.get("workspace_decoys_preserved"), f"{path}.workspace_decoys_preserved")
    target_touch_evidence = packet03_summary.get("workspace_target_target_touch_evidence")
    if not isinstance(target_touch_evidence, list):
        raise SchemaValidationError(f"{path}.workspace_target_target_touch_evidence must be a list")
    decoy_touch_evidence = packet03_summary.get("workspace_target_decoy_touch_evidence")
    if not isinstance(decoy_touch_evidence, list):
        raise SchemaValidationError(f"{path}.workspace_target_decoy_touch_evidence must be a list")
    _require_bool(
        packet03_summary.get("workspace_target_trace_linkage_complete"),
        f"{path}.workspace_target_trace_linkage_complete",
    )
    forced_probe_observed = _require_bool(
        packet03_summary.get("workspace_target_forced_probe_observed"),
        f"{path}.workspace_target_forced_probe_observed",
    )
    if forced_probe_observed:
        raise SchemaValidationError(
            f"{path}.workspace_target_forced_probe_observed must be false for decoy-generalization authority traces"
        )


def _validate_workspace_target_multistep_trace(packet03_summary: dict[str, Any], path: str) -> None:
    _validate_workspace_target_decoy_trace(packet03_summary, path)
    mechanism_visible = bool(packet03_summary.get("mechanism_visibility_complete"))
    schema_complete = bool(packet03_summary.get("schema_complete_for_promotion"))
    if not mechanism_visible and not schema_complete:
        return

    min_turns_required = packet03_summary.get("workspace_target_multistep_min_turns_required")
    if not isinstance(min_turns_required, int) or min_turns_required < 2:
        raise SchemaValidationError(
            f"{path}.workspace_target_multistep_min_turns_required must be an int >= 2"
        )

    turn_count = packet03_summary.get("workspace_target_multistep_turn_count")
    if not isinstance(turn_count, int) or turn_count < min_turns_required:
        raise SchemaValidationError(
            f"{path}.workspace_target_multistep_turn_count must be an int >= {min_turns_required}"
        )

    first_tool_step_index = packet03_summary.get("workspace_target_multistep_first_tool_step_index")
    if not isinstance(first_tool_step_index, int) or first_tool_step_index != 0:
        raise SchemaValidationError(
            f"{path}.workspace_target_multistep_first_tool_step_index must be 0 for visible multistep traces"
        )

    if not _require_bool(
        packet03_summary.get("workspace_target_multistep_first_turn_observation_met"),
        f"{path}.workspace_target_multistep_first_turn_observation_met",
    ):
        raise SchemaValidationError(
            f"{path}.workspace_target_multistep_first_turn_observation_met must be true for visible multistep traces"
        )
    if not _require_bool(
        packet03_summary.get("workspace_target_multistep_post_observation_step_met"),
        f"{path}.workspace_target_multistep_post_observation_step_met",
    ):
        raise SchemaValidationError(
            f"{path}.workspace_target_multistep_post_observation_step_met must be true for visible multistep traces"
        )
    if not _require_bool(
        packet03_summary.get("workspace_target_multistep_target_touch_after_observation"),
        f"{path}.workspace_target_multistep_target_touch_after_observation",
    ):
        raise SchemaValidationError(
            f"{path}.workspace_target_multistep_target_touch_after_observation must be true for visible multistep traces"
        )
    if not _require_bool(
        packet03_summary.get("workspace_target_multistep_contract_satisfied"),
        f"{path}.workspace_target_multistep_contract_satisfied",
    ):
        raise SchemaValidationError(
            f"{path}.workspace_target_multistep_contract_satisfied must be true for visible multistep traces"
        )
    _require_string(
        packet03_summary.get("workspace_target_observation_source_path"),
        f"{path}.workspace_target_observation_source_path",
    )

    first_turn_observation_evidence = packet03_summary.get("workspace_target_first_turn_observation_evidence")
    if not isinstance(first_turn_observation_evidence, list) or not first_turn_observation_evidence:
        raise SchemaValidationError(
            f"{path}.workspace_target_first_turn_observation_evidence must be a non-empty list for visible multistep traces"
        )
    post_observation_target_touch_evidence = packet03_summary.get(
        "workspace_target_post_observation_target_touch_evidence"
    )
    if not isinstance(post_observation_target_touch_evidence, list) or not post_observation_target_touch_evidence:
        raise SchemaValidationError(
            f"{path}.workspace_target_post_observation_target_touch_evidence must be a non-empty list for visible multistep traces"
        )


def _validate_tool_family_governed_truth(governed_eval_truth: dict[str, Any], *, path: str) -> None:
    completion_scope = _require_string(
        governed_eval_truth.get("completion_scope"),
        f"{path}.completion_scope",
    )
    if completion_scope not in GOVERNED_TRUTH_COMPLETION_SCOPES:
        raise SchemaValidationError(
            f"{path}.completion_scope must be one of {GOVERNED_TRUTH_COMPLETION_SCOPES}"
        )
    if completion_scope != "case_coverage_only":
        raise SchemaValidationError(
            f"{path}.completion_scope must be case_coverage_only for tool-family governed truth"
        )

    authority_completeness = _require_string(
        governed_eval_truth.get("authority_completeness"),
        f"{path}.authority_completeness",
    )
    if authority_completeness not in GOVERNED_TRUTH_AUTHORITY_COMPLETENESS:
        raise SchemaValidationError(
            f"{path}.authority_completeness must be one of {GOVERNED_TRUTH_AUTHORITY_COMPLETENESS}"
        )
    if authority_completeness == "not_applicable":
        raise SchemaValidationError(
            f"{path}.authority_completeness cannot be not_applicable for tool-family governed truth"
        )

    reason_values = _require_string_list_allow_empty(
        governed_eval_truth.get("authority_incomplete_reasons"),
        f"{path}.authority_incomplete_reasons",
    )
    governed_terminal_status = _require_string(
        governed_eval_truth.get("governed_terminal_status"),
        f"{path}.governed_terminal_status",
    )
    final_verdict = _require_string(governed_eval_truth.get("final_verdict"), f"{path}.final_verdict")

    if authority_completeness == "complete":
        if reason_values:
            raise SchemaValidationError(
                f"{path}.authority_incomplete_reasons must be empty when authority_completeness=complete"
            )
        if governed_terminal_status != "tool_eval_completed" or final_verdict != "pass":
            raise SchemaValidationError(
                f"{path}.authority_completeness=complete requires governed_terminal_status=tool_eval_completed and final_verdict=pass"
            )
    else:
        if not reason_values:
            raise SchemaValidationError(
                f"{path}.authority_incomplete_reasons must be non-empty when authority_completeness=incomplete"
            )


def validate_recommendation_draft(
    recommendation: dict[str, Any],
    *,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    data = _require_mapping(recommendation, "recommendation")
    _require_string(data.get("batch_id"), "recommendation.batch_id")
    for field in RECOMMENDATION_REQUIRED_FIELDS:
        _require_string(data.get(field), f"recommendation.{field}")
    _require_bool(data.get("human_gate_required"), "recommendation.human_gate_required")
    if data["human_gate_required"] is not True:
        raise SchemaValidationError("recommendation.human_gate_required must be true for Packet 03/04")
    if data.get("auto_apply") is True or data.get("mutate_promotion_state") is True:
        raise SchemaValidationError("recommendation must be draft-only and cannot mutate promotion state")

    candidates = data.get("candidate_actions")
    if not isinstance(candidates, list):
        raise SchemaValidationError("recommendation.candidate_actions must be a list")
    for index, candidate in enumerate(candidates):
        path = f"recommendation.candidate_actions[{index}]"
        item = _require_mapping(candidate, path)
        for field in RECOMMENDATION_CANDIDATE_REQUIRED_FIELDS:
            if field not in item:
                raise SchemaValidationError(f"{path}.{field} is required")
        _require_string(item.get("variant_id"), f"{path}.variant_id")
        proposed_status = _require_string(item.get("proposed_status"), f"{path}.proposed_status")
        if proposed_status not in ALLOWED_RECOMMENDATION_STATUSES:
            raise SchemaValidationError(
                f"{path}.proposed_status must be one of {ALLOWED_RECOMMENDATION_STATUSES}"
            )
        _require_string(item.get("rationale"), f"{path}.rationale")
        _require_string(item.get("next_eval_or_transfer_step"), f"{path}.next_eval_or_transfer_step")
        if not isinstance(item.get("evidence_refs"), list):
            raise SchemaValidationError(f"{path}.evidence_refs must be a list")
        if not isinstance(item.get("regression_risks"), list):
            raise SchemaValidationError(f"{path}.regression_risks must be a list")
        _require_mapping(item.get("token_cost_delta"), f"{path}.token_cost_delta")
        _require_mapping(item.get("complexity_delta"), f"{path}.complexity_delta")
        failed_gate_ids = _validate_recommendation_gate_payload(
            item,
            path=path,
            output_root=output_root,
        )
        if proposed_status == "promote_to_atomic_eligible" and failed_gate_ids:
            raise SchemaValidationError(
                f"{path}.proposed_status=promote_to_atomic_eligible requires all gates pass; failed={failed_gate_ids}"
            )
        if proposed_status == "screened_no_uplift" and "G15" in failed_gate_ids:
            raise SchemaValidationError(
                f"{path}.proposed_status=screened_no_uplift requires G15 pass for mechanism/schema-complete evidence"
            )
    return data


def _validate_recommendation_gate_payload(
    item: dict[str, Any],
    *,
    path: str,
    output_root: str | Path | None,
) -> list[str]:
    gate_inputs = _require_mapping(item.get("recommendation_gate_inputs"), f"{path}.recommendation_gate_inputs")
    for field in RECOMMENDATION_GATE_INPUT_REQUIRED_FIELDS:
        if field not in gate_inputs:
            raise SchemaValidationError(f"{path}.recommendation_gate_inputs.{field} is required")

    normalize_recommendation_lane_class(
        gate_inputs.get("lane_class"),
        f"{path}.recommendation_gate_inputs.lane_class",
    )
    _require_bool(gate_inputs.get("surface_bounded"), f"{path}.recommendation_gate_inputs.surface_bounded")
    _require_bool(
        gate_inputs.get("mechanism_visibility_complete"),
        f"{path}.recommendation_gate_inputs.mechanism_visibility_complete",
    )
    _require_bool(
        gate_inputs.get("schema_complete_for_promotion"),
        f"{path}.recommendation_gate_inputs.schema_complete_for_promotion",
    )
    _require_bool(
        gate_inputs.get("helper_only_evidence"),
        f"{path}.recommendation_gate_inputs.helper_only_evidence",
    )
    _require_string(gate_inputs.get("comparator_variant_id"), f"{path}.recommendation_gate_inputs.comparator_variant_id")
    _require_string_list_allow_empty(
        gate_inputs.get("same_batch_comparator_run_ids"),
        f"{path}.recommendation_gate_inputs.same_batch_comparator_run_ids",
    )
    _require_string_list_allow_empty(
        gate_inputs.get("corroboration_surface_ids"),
        f"{path}.recommendation_gate_inputs.corroboration_surface_ids",
    )
    primary_delta_metric = _require_mapping(
        gate_inputs.get("primary_delta_metric"),
        f"{path}.recommendation_gate_inputs.primary_delta_metric",
    )
    _require_string(
        primary_delta_metric.get("metric_name"),
        f"{path}.recommendation_gate_inputs.primary_delta_metric.metric_name",
    )
    _require_number_or_null(
        primary_delta_metric.get("candidate_value"),
        f"{path}.recommendation_gate_inputs.primary_delta_metric.candidate_value",
    )
    _require_number_or_null(
        primary_delta_metric.get("comparator_value"),
        f"{path}.recommendation_gate_inputs.primary_delta_metric.comparator_value",
    )
    _require_number_or_null(
        primary_delta_metric.get("delta"),
        f"{path}.recommendation_gate_inputs.primary_delta_metric.delta",
    )
    _require_number_or_null(
        primary_delta_metric.get("threshold"),
        f"{path}.recommendation_gate_inputs.primary_delta_metric.threshold",
    )
    _require_string(
        primary_delta_metric.get("direction"),
        f"{path}.recommendation_gate_inputs.primary_delta_metric.direction",
    )
    audit_status_aa = _require_string(
        gate_inputs.get("audit_status_aa"),
        f"{path}.recommendation_gate_inputs.audit_status_aa",
    )
    audit_status_ab = _require_string(
        gate_inputs.get("audit_status_ab"),
        f"{path}.recommendation_gate_inputs.audit_status_ab",
    )
    if audit_status_aa not in ALLOWED_AUDIT_STATUSES:
        raise SchemaValidationError(
            f"{path}.recommendation_gate_inputs.audit_status_aa must be one of {ALLOWED_AUDIT_STATUSES}"
        )
    if audit_status_ab not in ALLOWED_AUDIT_STATUSES:
        raise SchemaValidationError(
            f"{path}.recommendation_gate_inputs.audit_status_ab must be one of {ALLOWED_AUDIT_STATUSES}"
        )
    audit_artifact_ref_aa = _require_optional_string(
        gate_inputs.get("audit_artifact_ref_aa"),
        f"{path}.recommendation_gate_inputs.audit_artifact_ref_aa",
    )
    audit_artifact_ref_ab = _require_optional_string(
        gate_inputs.get("audit_artifact_ref_ab"),
        f"{path}.recommendation_gate_inputs.audit_artifact_ref_ab",
    )
    if audit_status_aa != "missing" and not audit_artifact_ref_aa:
        raise SchemaValidationError(
            f"{path}.recommendation_gate_inputs.audit_status_aa={audit_status_aa} requires audit_artifact_ref_aa"
        )
    if audit_status_ab != "missing" and not audit_artifact_ref_ab:
        raise SchemaValidationError(
            f"{path}.recommendation_gate_inputs.audit_status_ab={audit_status_ab} requires audit_artifact_ref_ab"
        )
    if audit_artifact_ref_aa:
        _require_existing_file(
            audit_artifact_ref_aa,
            path=f"{path}.recommendation_gate_inputs.audit_artifact_ref_aa",
            output_root=output_root,
        )
    if audit_artifact_ref_ab:
        _require_existing_file(
            audit_artifact_ref_ab,
            path=f"{path}.recommendation_gate_inputs.audit_artifact_ref_ab",
            output_root=output_root,
        )
    _require_bool(gate_inputs.get("forced_probe_observed"), f"{path}.recommendation_gate_inputs.forced_probe_observed")
    _require_bool(gate_inputs.get("standin_observed"), f"{path}.recommendation_gate_inputs.standin_observed")
    _require_optional_string(gate_inputs.get("variant_card_ref"), f"{path}.recommendation_gate_inputs.variant_card_ref")
    _require_optional_string(
        gate_inputs.get("route_manifest_ref"),
        f"{path}.recommendation_gate_inputs.route_manifest_ref",
    )
    _require_optional_string(
        gate_inputs.get("route_manifest_fingerprint"),
        f"{path}.recommendation_gate_inputs.route_manifest_fingerprint",
    )
    _require_mapping(
        gate_inputs.get("claimed_surface_fingerprints"),
        f"{path}.recommendation_gate_inputs.claimed_surface_fingerprints",
    )
    _require_mapping(
        gate_inputs.get("unchanged_surface_fingerprints"),
        f"{path}.recommendation_gate_inputs.unchanged_surface_fingerprints",
    )
    _require_string(
        gate_inputs.get("governed_truth_ref"),
        f"{path}.recommendation_gate_inputs.governed_truth_ref",
    )
    validate_governed_terminal_status(
        gate_inputs.get("governed_terminal_status"),
        f"{path}.recommendation_gate_inputs.governed_terminal_status",
    )

    gate_results = _require_mapping(item.get("recommendation_gate_results"), f"{path}.recommendation_gate_results")
    failed_gate_ids: list[str] = []
    for gate_id in RECOMMENDATION_GATE_IDS:
        gate_path = f"{path}.recommendation_gate_results.{gate_id}"
        gate_result = _require_mapping(gate_results.get(gate_id), gate_path)
        passed = _require_bool(gate_result.get("passed"), f"{gate_path}.passed")
        _require_string(gate_result.get("reason"), f"{gate_path}.reason")
        if not passed:
            failed_gate_ids.append(gate_id)
    return failed_gate_ids


def validate_result_artifact_linkage(
    result_record: dict[str, Any],
    *,
    trace_summaries: list[dict[str, Any]] | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate result-record references to trace and run artifacts."""
    data = validate_result_record(dict(result_record))
    trace_index = _trace_summary_index(trace_summaries or [])
    _validate_trace_summary_ref(
        trace_summary_ref=data["trace_summary_ref"],
        run_id=data["run_id"],
        trace_index=trace_index,
        output_root=output_root,
    )
    run_artifact_refs = data["run_artifact_refs"]
    for field in ("run_header_ref", "run_events_ref", "score_envelope_ref"):
        _require_existing_file(
            run_artifact_refs[field],
            path=f"result_record.run_artifact_refs.{field}",
            output_root=output_root,
        )
    trace_summary = trace_index.get(data["run_id"])
    if isinstance(trace_summary, dict):
        governed_eval_truth = trace_summary.get("governed_eval_truth")
        if isinstance(governed_eval_truth, dict):
            governed_terminal_status = governed_eval_truth.get("governed_terminal_status")
            if governed_terminal_status != data.get("governed_terminal_status"):
                raise SchemaValidationError(
                    "result_record.governed_terminal_status must match trace_summary.governed_eval_truth.governed_terminal_status"
                )
    return data


def _validate_lane_misuse(
    *,
    lane: str,
    promotion_eligibility: str,
    reason_codes: list[str],
    secondary_failure_tags: list[str],
    path: str,
) -> None:
    markers = [value.lower() for value in reason_codes + secondary_failure_tags]
    if lane == "promotion" and _contains_any_marker(markers, PROMOTION_BLOCKER_MARKERS):
        raise SchemaValidationError(
            f"{path}.evaluation_lane=promotion cannot include blocker-like markers in reason_codes/secondary_failure_tags"
        )
    if lane in {"guardrail_debug", "bounded_diagnostic"} and promotion_eligibility == "eligible":
        raise SchemaValidationError(
            f"{path}.evaluation_lane={lane} cannot be promotion eligible"
        )


def _contains_any_marker(values: list[str], markers: tuple[str, ...]) -> bool:
    return any(marker in value for value in values for marker in markers)


def _is_packet04_batch_spec(batch_spec: dict[str, Any]) -> bool:
    packet_stage = batch_spec.get("packet_stage")
    if isinstance(packet_stage, str) and packet_stage == "packet_04":
        return True
    eval_family = batch_spec.get("eval_family")
    return isinstance(eval_family, str) and eval_family.startswith("packet_04")


def _trace_summary_index(trace_summaries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in trace_summaries:
        if not isinstance(item, dict):
            continue
        run_id = item.get("run_id")
        if isinstance(run_id, str) and run_id:
            index[run_id] = item
    return index


def _validate_trace_summary_ref(
    *,
    trace_summary_ref: str,
    run_id: str,
    trace_index: dict[str, dict[str, Any]],
    output_root: str | Path | None,
) -> None:
    if "#run_id=" in trace_summary_ref:
        path_part, marker_run_id = trace_summary_ref.split("#run_id=", 1)
        resolved_run_id = _require_string(marker_run_id, "result_record.trace_summary_ref#run_id")
        if resolved_run_id != run_id:
            raise SchemaValidationError(
                "result_record.trace_summary_ref#run_id must match result_record.run_id"
            )
        if resolved_run_id in trace_index:
            return
        trace_path = _resolve_path_ref(path_part, output_root)
        if not trace_path.exists():
            raise SchemaValidationError(
                "result_record.trace_summary_ref must resolve to an existing trace summary file or supplied run_id index"
            )
        if not _jsonl_contains_run_id(trace_path, resolved_run_id):
            raise SchemaValidationError(
                f"result_record.trace_summary_ref does not resolve: run_id={resolved_run_id} not found in {trace_path}"
            )
        return
    trace_path = _resolve_path_ref(trace_summary_ref, output_root)
    if trace_path.exists():
        return
    raise SchemaValidationError("result_record.trace_summary_ref must resolve to an existing trace summary artifact")


def _jsonl_contains_run_id(path: Path, run_id: str) -> bool:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("run_id") == run_id:
            return True
    return False


def _require_existing_file(ref: str, *, path: str, output_root: str | Path | None) -> Path:
    resolved = _resolve_path_ref(ref, output_root)
    if not resolved.exists() or not resolved.is_file():
        raise SchemaValidationError(f"{path} must resolve to an existing file: {resolved}")
    return resolved


def _resolve_path_ref(ref: str, output_root: str | Path | None) -> Path:
    path = Path(ref)
    if path.is_absolute():
        return path
    if output_root is None:
        return path
    return Path(output_root).resolve() / path

"""Packet 03 eval-specific grading for active atomic families."""

from __future__ import annotations

from copy import deepcopy
import importlib
import json
from pathlib import Path
from typing import Any

from runner.evaluator import apply_packet01_guards
from runner.schemas import validate_score_envelope

LAYER_EXPECTATION_MAP = {
    "l0_inline_assertion": "L0_inline_assertion",
    "l1_verifier_artifact": "L1_verifier_artifact",
    "l2_replay_or_state_grader": "L2_replay_or_state_grader",
    "l3_llm_judge": "L3_judge_layer",
    "l4_final_acceptance_reward": "L4_final_acceptance",
}
WORKSPACE_TARGET_LEGACY_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_correctness_probe",
        "eval_workspace_target_correctness_atomic_v1",
    }
)
WORKSPACE_TARGET_REPAIRED_EVAL_IDS = frozenset(
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


def apply_packet03_eval_grader(
    *,
    route: dict[str, Any],
    execution_result: dict[str, Any],
    fixture_plan: dict[str, Any],
) -> dict[str, Any]:
    score = deepcopy(execution_result["score_envelope"])
    layers = score["layers"]
    aggregate = score["aggregate"]
    eval_id = route["eval_id"]
    fixture = fixture_plan["fixture"]
    fixture_ref = fixture_plan["fixture_ref"]
    trace: dict[str, Any] = {
        "eval_id": eval_id,
        "fixture_id": fixture.get("fixture_id"),
        "grader_id": fixture.get("grader_id"),
        "mechanism_exercised": False,
    }
    issues: list[str] = []

    if eval_id == "ae_completion_layer_contract_guard":
        _grade_completion_layer_contract(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_verification_reason_code_quality_v2":
        _grade_verification_reason_code_quality_v2(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_lifecycle_adversarial_terminality_v2":
        _grade_lifecycle_adversarial_terminality_v2(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_completion_verifier_final_contradiction_probe":
        _grade_contradiction_probe(layers, aggregate, trace, fixture, fixture_ref, execution_result)
    elif eval_id == "ae_tool_call_shape_argument_contract":
        _grade_tool_call_shape_contract(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_tool_call_contract_quality_v2":
        _grade_tool_call_contract_quality_v2(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_lifecycle_terminality_contract_guard":
        _grade_lifecycle_terminality_contract(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_cwd_workdir_path_contract_guard":
        _grade_cwd_workdir_path_contract(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id in WORKSPACE_TARGET_LEGACY_EVAL_IDS:
        _grade_workspace_target_probe(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id in WORKSPACE_TARGET_REPAIRED_EVAL_IDS:
        _grade_workspace_target_decoy_generalization_v2(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id in WORKSPACE_TARGET_MULTISTEP_EVAL_IDS:
        _grade_workspace_target_decoy_multistep_v1(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_tool_result_normalization_permission_probe":
        _grade_tool_result_normalization_probe(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_tool_result_attribution_quality_v2":
        _grade_tool_result_attribution_quality_v2(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_internal_discovery_evidence_efficiency_v1":
        _grade_internal_discovery_evidence_efficiency_v1(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_internal_multifile_repair_test_verify_v1":
        _grade_internal_multifile_repair_test_verify_v1(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_internal_toolchain_dependency_pressure_v1":
        _grade_internal_toolchain_dependency_pressure_v1(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_internal_artifact_log_extraction_v1":
        _grade_internal_artifact_log_extraction_v1(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )
    elif eval_id == "ae_sync_interrupt_cleanup_probe":
        _grade_sync_interrupt_cleanup_probe(
            layers,
            aggregate,
            trace,
            fixture,
            fixture_ref,
            execution_result,
        )

    _enforce_required_layer_expectations(route["eval_card"], layers, issues)
    _enforce_execution_success(execution_result, layers, aggregate, trace)
    if issues:
        _set_unresolved(aggregate, issues)
    score = validate_score_envelope(apply_packet01_guards(score))
    execution_result["score_envelope"] = score
    execution_result["packet03_eval_trace"] = trace
    return execution_result


def _grade_completion_layer_contract(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l1 = layers["L1_verifier_artifact"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass"
    l0["score"] = {"kind": "boolean", "value": True}
    _add_evidence(l0, fixture_ref)
    tuple_complete = l1.get("status") == "pass" and l1.get("artifact_ref") and l4.get("status") in {"pass", "fail"}
    verification = _verification_summary(execution_result)
    expected = fixture.get("expected_verification", {})
    expected_reason_codes = set(_string_list(expected.get("reason_codes")))
    expected_substitution = set(_string_list(expected.get("substitution_violations")))
    observed_reason_codes = set(verification["reason_codes"])
    observed_substitution = set(verification["substitution_violations"])
    mechanism_visible = verification["summary_complete"]
    l2["status"] = "pass" if tuple_complete and mechanism_visible else "fail"
    l2["grader_id"] = fixture["grader_id"]
    l2["score"] = {"kind": "boolean", "value": bool(tuple_complete and mechanism_visible)}
    _add_evidence(l2, fixture_ref)
    if tuple_complete and mechanism_visible:
        aggregate["final_verdict"] = "pass" if l4.get("status") == "pass" else "fail"
    else:
        if not tuple_complete:
            _add_reason(l2, "completion_layer_tuple_incomplete")
            _set_unresolved(aggregate, ["completion_layer_tuple_incomplete"])
        else:
            _add_reason(l2, "verification_mechanism_evidence_missing")
            _set_unresolved(aggregate, ["verification_mechanism_evidence_missing"])
    trace["mechanism_exercised"] = True
    trace["layer_tuple_complete"] = bool(tuple_complete)
    trace["verification_reason_codes"] = verification["reason_codes"]
    trace["verification_substitution_violations"] = verification["substitution_violations"]
    trace["verification_layer_statuses"] = verification["layer_statuses"]
    if not expected_reason_codes and verification["verified"]:
        reason_code_accuracy = observed_reason_codes.issubset({"baseline_model_claim_accepted"})
    else:
        reason_code_accuracy = observed_reason_codes == expected_reason_codes
    trace["verification_reason_code_accuracy"] = reason_code_accuracy and observed_substitution == expected_substitution
    trace["verification_reason_code_specificity"] = _verification_reason_codes_specific(
        verification["reason_codes"],
        verification["substitution_violations"],
    )
    trace["verification_reason_code_coverage"] = (
        expected_reason_codes.issubset(observed_reason_codes)
        and expected_substitution.issubset(observed_substitution)
    )
    trace["verification_remediation_actionability"] = (
        bool(verification["verified"])
        or bool(verification["reason_codes"])
        or bool(verification["substitution_violations"])
    )
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = not mechanism_visible


def _grade_contradiction_probe(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l3 = layers["L3_judge_layer"]
    l1 = layers["L1_verifier_artifact"]
    l4 = layers["L4_final_acceptance"]
    contract = fixture.get("contradiction_contract", {})
    expected_contradiction = bool(contract.get("expected_contradiction", True)) if isinstance(contract, dict) else True
    verification = _verification_summary(execution_result)
    observed_statuses = verification.get("layer_statuses", {})
    if not isinstance(observed_statuses, dict):
        observed_statuses = {}
    observed_l1_status = observed_statuses.get("L1_verifier_artifact", l1.get("status"))
    observed_l4_status = observed_statuses.get("L4_final_acceptance", l4.get("status"))
    tuple_complete = (
        l1.get("status") == "pass"
        and bool(l1.get("artifact_ref"))
        and l4.get("status") in {"pass", "fail"}
        and observed_l1_status in {"pass", "fail"}
        and observed_l4_status in {"pass", "fail"}
    )
    contradiction_detected = observed_l1_status == "pass" and observed_l4_status == "fail"
    contract_match = tuple_complete and contradiction_detected == expected_contradiction
    l0["status"] = "pass"
    l0["score"] = {"kind": "boolean", "value": True}
    _add_evidence(l0, fixture_ref)
    l2["status"] = "pass" if contract_match else "fail"
    l2["grader_id"] = fixture["grader_id"]
    l2["score"] = {"kind": "boolean", "value": contract_match}
    _add_evidence(l2, fixture_ref)
    l3_contract = fixture.get("l3_judge_contract")
    l3["status"] = "pass" if contract_match else "fail"
    l3["score"] = {"kind": "boolean", "value": contract_match}
    l3["judge_config"] = dict(l3_contract) if isinstance(l3_contract, dict) else {
        "judge_type": "deterministic_local_contradiction_contract_v1",
        "model": "local_deterministic_contract",
        "prompt_fingerprint": "p15_contradiction_tuple_prompt_v1",
        "schema_fingerprint": "p15_contradiction_tuple_schema_v1",
        "mode": "phase15_measurement_repair",
    }
    l4["status"] = "pass" if contract_match else "fail"
    l4["score"] = {"kind": "boolean", "value": contract_match}
    if contract_match:
        aggregate["final_verdict"] = "pass"
    else:
        _add_reason(l2, "contradiction_contract_mismatch")
        _add_reason(l4, "contradiction_measurement_contract_failed")
        aggregate["final_verdict"] = "fail"
    trace["mechanism_exercised"] = True
    trace["degraded_without_l3"] = False
    trace["phase15_repaired_contradiction_surface"] = True
    trace["contradiction_contract_id"] = contract.get("contract_id") if isinstance(contract, dict) else None
    trace["expected_contradiction"] = expected_contradiction
    trace["contradiction_detected"] = contradiction_detected
    trace["contradiction_contract_match"] = contract_match
    trace["observed_verifier_layer_status"] = observed_l1_status
    trace["observed_final_acceptance_status"] = observed_l4_status
    trace["l3_judge_contract_configured"] = True
    trace["l3_judge_status"] = l3["status"]


def _grade_verification_reason_code_quality_v2(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    verification = _verification_summary(execution_result)
    expected = fixture.get("expected_verification", {})
    expected_verified = bool(expected.get("verified", False))
    expected_reason_codes = set(_string_list(expected.get("reason_codes")))
    expected_substitution = set(_string_list(expected.get("substitution_violations")))
    expected_layer_statuses = expected.get("layer_statuses", {})
    expected_layer_statuses = {
        str(layer_id): str(status)
        for layer_id, status in expected_layer_statuses.items()
        if isinstance(layer_id, str) and isinstance(status, str)
    } if isinstance(expected_layer_statuses, dict) else {}

    observed_reason_codes = set(verification["reason_codes"])
    observed_substitution = set(verification["substitution_violations"])
    mechanism_visible = verification["summary_complete"]
    verified_match = verification["verified"] == expected_verified
    reason_code_accuracy = observed_reason_codes == expected_reason_codes
    substitution_accuracy = observed_substitution == expected_substitution
    layer_status_match = verification["layer_statuses"] == expected_layer_statuses
    reason_code_coverage = expected_reason_codes.issubset(observed_reason_codes)
    substitution_coverage = expected_substitution.issubset(observed_substitution)
    reason_code_specificity = _verification_reason_codes_specific(
        verification["reason_codes"],
        verification["substitution_violations"],
    )
    remediation_actionability = bool(verification["reason_codes"] or verification["substitution_violations"])
    exact_match = (
        mechanism_visible
        and verified_match
        and reason_code_accuracy
        and substitution_accuracy
        and layer_status_match
        and reason_code_specificity
        and remediation_actionability
    )

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if mechanism_visible else "fail"
    l0["score"] = {"kind": "boolean", "value": mechanism_visible}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    l2["status"] = "pass" if exact_match else "fail"
    l2["score"] = {"kind": "boolean", "value": exact_match}
    l4["status"] = "pass" if exact_match else "fail"
    l4["score"] = {"kind": "boolean", "value": exact_match}
    aggregate["final_verdict"] = "pass" if exact_match else "fail"
    if not mechanism_visible:
        _add_reason(l2, "verification_mechanism_evidence_missing")
        _set_unresolved(aggregate, ["verification_mechanism_evidence_missing"])
    else:
        if not verified_match:
            _add_reason(l2, "verification_reason_code_verified_mismatch")
        if not reason_code_accuracy:
            _add_reason(l2, "verification_reason_code_set_mismatch")
        if not substitution_accuracy:
            _add_reason(l2, "verification_substitution_violation_mismatch")
        if not layer_status_match:
            _add_reason(l2, "verification_layer_status_mismatch")
        if not reason_code_specificity:
            _add_reason(l2, "verification_reason_codes_non_specific")
        if not remediation_actionability:
            _add_reason(l2, "verification_remediation_not_actionable")
        if l2["status"] == "fail":
            _add_reason(l4, "verification_reason_code_quality_failed")

    trace["mechanism_exercised"] = True
    trace["verification_reason_codes"] = verification["reason_codes"]
    trace["verification_substitution_violations"] = verification["substitution_violations"]
    trace["verification_layer_statuses"] = verification["layer_statuses"]
    trace["verification_reason_code_accuracy"] = reason_code_accuracy and substitution_accuracy
    trace["verification_reason_code_specificity"] = reason_code_specificity
    trace["verification_reason_code_coverage"] = reason_code_coverage and substitution_coverage
    trace["verification_remediation_actionability"] = remediation_actionability
    trace["verification_expected_verified"] = expected_verified
    trace["verification_observed_verified"] = verification["verified"]
    trace["verification_layer_status_match"] = layer_status_match
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = not mechanism_visible


def _grade_tool_call_shape_contract(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    cases = fixture.get("tool_call_matrix", [])
    runtime_probe = execution_result["execution"].get("runtime_probe", {})
    runtime_results = runtime_probe.get("tool_results", []) if isinstance(runtime_probe, dict) else []
    observed_by_case: dict[str, dict[str, Any]] = {}
    if isinstance(runtime_results, list):
        for item in runtime_results:
            if not isinstance(item, dict):
                continue
            case_id = item.get("case_id")
            if isinstance(case_id, str) and case_id:
                observed_by_case[case_id] = item

    classifier_source = "runtime_probe"
    case_results: list[dict[str, Any]] = []
    if observed_by_case:
        matched = 0
        for row in cases:
            case_id = row.get("case_id")
            observed = observed_by_case.get(case_id) if isinstance(case_id, str) else None
            observed_class = observed.get("tool_call_contract_class") if isinstance(observed, dict) else None
            expected_class = row.get("expected_class")
            matched_case = observed_class == expected_class
            if matched_case:
                matched += 1
            case_results.append(
                {
                    "case_id": case_id,
                    "expected_class": expected_class,
                    "observed_class": observed_class,
                    "result_class": observed.get("result_class") if isinstance(observed, dict) else None,
                    "reason_code": observed.get("reason_code") if isinstance(observed, dict) else None,
                }
            )
        matrix_ok = bool(cases) and matched == len(cases) and len(observed_by_case) >= len(cases)
    else:
        classifier, classifier_source = _resolve_tool_call_shape_classifier(execution_result)
        matched = sum(1 for row in cases if classifier(row.get("tool_call")) == row.get("expected_class"))
        matrix_ok = bool(cases) and matched == len(cases)
        for row in cases:
            observed_class = classifier(row.get("tool_call"))
            case_results.append(
                {
                    "case_id": row.get("case_id"),
                    "expected_class": row.get("expected_class"),
                    "observed_class": observed_class,
                    "result_class": None,
                    "reason_code": None,
                }
            )
        if classifier_source == "grader_fallback":
            classifier_source = "grader_fallback"
        else:
            classifier_source = f"{classifier_source}:static_matrix"
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if matrix_ok else "fail"
    l0["score"] = {"kind": "boolean", "value": matrix_ok}
    _add_evidence(l0, fixture_ref)
    l2["status"] = "pass" if matrix_ok else "fail"
    l2["grader_id"] = fixture["grader_id"]
    l2["score"] = {"kind": "boolean", "value": matrix_ok}
    _add_evidence(l2, fixture_ref)
    if not matrix_ok:
        _add_reason(l2, "tool_call_matrix_mismatch")
        _add_reason(l4, "tool_call_shape_contract_failed")
    l4["status"] = "pass" if matrix_ok else "fail"
    l4["score"] = {"kind": "boolean", "value": matrix_ok}
    aggregate["final_verdict"] = "pass" if matrix_ok else "fail"
    trace["mechanism_exercised"] = True
    trace["matrix_total"] = len(cases)
    trace["matrix_matched"] = matched
    trace["tool_contract_cases_total"] = len(cases)
    trace["tool_contract_cases_matched"] = matched
    trace["tool_contract_case_results"] = case_results
    trace["tool_call_shape_classifier_source"] = classifier_source
    trace["mechanism_visibility_complete"] = bool(observed_by_case) or classifier_source != "grader_fallback"
    trace["schema_complete_for_promotion"] = bool(observed_by_case) or classifier_source != "grader_fallback"
    trace["helper_only_evidence"] = not bool(observed_by_case) and classifier_source == "grader_fallback"


def _grade_tool_call_contract_quality_v2(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    expected_cases = fixture.get("expected_tool_call_cases", [])
    expected_by_case = {
        row.get("case_id"): row
        for row in expected_cases
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    observed_by_case: dict[str, dict[str, Any]] = {}
    for result in _tool_results(execution_result):
        case_id = result.get("case_id")
        if isinstance(case_id, str) and case_id:
            observed_by_case[case_id] = result

    case_results: list[dict[str, Any]] = []
    matched = 0
    incomplete_contract_case_ids: list[str] = []
    for case_id, expected in expected_by_case.items():
        observed = observed_by_case.get(case_id)
        observed_contract = observed.get("tool_call_contract_class") if isinstance(observed, dict) else None
        observed_result = observed.get("result_class") if isinstance(observed, dict) else None
        observed_reason = observed.get("reason_code") if isinstance(observed, dict) else None
        expected_contract = expected.get("expected_contract_class")
        expected_result = expected.get("expected_result_class")
        expected_reason = expected.get("expected_reason_code")
        matched_case = (
            observed_contract == expected_contract
            and observed_result == expected_result
            and observed_reason == expected_reason
        )
        if matched_case:
            matched += 1
        if not (
            isinstance(observed_contract, str)
            and observed_contract
            and isinstance(observed_result, str)
            and observed_result
            and isinstance(observed_reason, str)
            and observed_reason
        ):
            incomplete_contract_case_ids.append(case_id)
        case_results.append(
            {
                "case_id": case_id,
                "expected_contract_class": expected_contract,
                "observed_contract_class": observed_contract,
                "expected_result_class": expected_result,
                "observed_result_class": observed_result,
                "expected_reason_code": expected_reason,
                "observed_reason_code": observed_reason,
                "matched": matched_case,
            }
        )

    contract_trace_complete = bool(expected_by_case) and not incomplete_contract_case_ids
    mechanism_visible = bool(expected_by_case) and bool(observed_by_case) and contract_trace_complete
    all_matched = mechanism_visible and matched == len(expected_by_case)
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if mechanism_visible else "fail"
    l0["score"] = {"kind": "boolean", "value": mechanism_visible}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not mechanism_visible:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "tool_call_contract_runtime_evidence_missing")
        _set_unresolved(aggregate, ["tool_call_contract_runtime_evidence_missing"])
    elif all_matched:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "tool_call_contract_quality_mismatch")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "tool_call_contract_quality_failed")
        aggregate["final_verdict"] = "fail"

    trace["mechanism_exercised"] = True
    trace["tool_call_contract_source"] = "execution_loop"
    trace["tool_contract_cases_total"] = len(expected_by_case)
    trace["tool_contract_cases_matched"] = matched
    trace["tool_contract_case_results"] = case_results
    trace["observed_tool_contract_classes"] = sorted(
        {
            value
            for value in (
                result.get("tool_call_contract_class")
                for result in observed_by_case.values()
                if isinstance(result, dict)
            )
            if isinstance(value, str) and value
        }
    )
    trace["tool_call_contract_trace_complete"] = contract_trace_complete
    trace["tool_call_contract_incomplete_case_ids"] = sorted(incomplete_contract_case_ids)
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = False


def _grade_lifecycle_terminality_contract(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    tuple_data = fixture.get("terminality_tuple")
    tuple_complete = _lifecycle_tuple_complete(tuple_data)
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if tuple_complete else "fail"
    l0["score"] = {"kind": "boolean", "value": tuple_complete}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not tuple_complete:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "lifecycle_terminality_tuple_incomplete")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "lifecycle_terminality_tuple_incomplete")
        _set_unresolved(aggregate, ["lifecycle_terminality_tuple_incomplete"])
        trace["mechanism_exercised"] = False
        trace["terminality_tuple_complete"] = False
        return

    tuple_data = dict(tuple_data)
    tuple_coherent = _lifecycle_tuple_coherent(tuple_data)
    observed_execution = execution_result["execution"]
    execution_status = observed_execution.get("status")
    step_count = observed_execution.get("step_count")
    expected_status = tuple_data["expected_terminal_state"]
    step_bound_max = tuple_data["bounded_loop"]["step_bound_max"]
    cleanup_required = bool(tuple_data["cleanup_state"]["required"])
    cleanup_reason_codes = _string_list(observed_execution.get("cleanup_completion_reason_codes"))
    cleanup_completed = bool(observed_execution.get("cleanup_completed")) or any(
        code in {"loop_cleanup_completed", "recovery_cleanup_completed", "runtime_probe_cleanup_observed"}
        for code in cleanup_reason_codes
    )
    cleanup_ok = (not cleanup_required) or cleanup_completed
    status_match = execution_status == expected_status
    bounded = isinstance(step_count, int) and step_count <= step_bound_max
    terminal_write_count = observed_execution.get("terminal_write_count")
    single_terminal_write = terminal_write_count == 1
    unresolved_state_exit_count = observed_execution.get("unresolved_state_exit_count")
    lifecycle_sequence_fingerprint = observed_execution.get("lifecycle_sequence_fingerprint")
    lifecycle_reason_codes = _string_list(observed_execution.get("lifecycle_reason_codes"))
    post_cancel_tool_return_count = int(observed_execution.get("post_cancel_tool_return_count", 0) or 0)
    cleanup_race_detected = bool(observed_execution.get("cleanup_race_detected"))
    mechanism_visible = (
        isinstance(terminal_write_count, int)
        and isinstance(unresolved_state_exit_count, int)
        and isinstance(lifecycle_sequence_fingerprint, str)
        and bool(cleanup_reason_codes)
    )

    if not tuple_coherent:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "lifecycle_terminality_tuple_incoherent")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "lifecycle_terminality_tuple_incoherent")
        _set_unresolved(aggregate, ["lifecycle_terminality_tuple_incoherent"])
    elif not mechanism_visible:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "lifecycle_runtime_evidence_missing")
        _set_unresolved(aggregate, ["lifecycle_runtime_evidence_missing"])
    elif status_match and bounded and single_terminal_write and cleanup_ok and unresolved_state_exit_count == 0:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        if not status_match:
            _add_reason(l2, "lifecycle_terminality_status_mismatch")
        if not bounded:
            _add_reason(l2, "lifecycle_terminality_step_bound_exceeded")
        if not single_terminal_write:
            _add_reason(l2, "lifecycle_terminality_single_terminal_write_violation")
        if not cleanup_ok:
            _add_reason(l2, "lifecycle_terminality_cleanup_incomplete")
        if unresolved_state_exit_count != 0:
            _add_reason(l2, "lifecycle_terminality_unresolved_state_exit")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "lifecycle_terminality_contract_failed")
        aggregate["final_verdict"] = "fail"
    trace["mechanism_exercised"] = True
    trace["terminality_tuple_complete"] = tuple_complete
    trace["terminality_tuple_coherent"] = tuple_coherent
    trace["terminality_status_match"] = status_match
    trace["terminality_bounded"] = bounded
    trace["terminality_single_write"] = single_terminal_write
    trace["terminality_cleanup_ok"] = cleanup_ok
    trace["terminal_write_count_observed"] = terminal_write_count
    trace["cleanup_completed"] = cleanup_completed
    trace["cleanup_completion_reason_codes"] = cleanup_reason_codes
    trace["unresolved_state_exit_count"] = unresolved_state_exit_count
    trace["lifecycle_sequence_fingerprint"] = lifecycle_sequence_fingerprint
    trace["post_cancel_tool_return_count"] = post_cancel_tool_return_count
    trace["cleanup_race_detected"] = cleanup_race_detected
    trace["lifecycle_reason_codes"] = lifecycle_reason_codes
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = not mechanism_visible


def _grade_lifecycle_adversarial_terminality_v2(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    expected = fixture.get("expected_lifecycle", {})
    expected_status = expected.get("expected_final_status")
    expected_reason_codes = set(_string_list(expected.get("expected_reason_codes")))
    expected_duplicate = bool(expected.get("expected_duplicate_terminal_write"))
    expected_cleanup_race = bool(expected.get("expected_cleanup_race_detected"))
    expected_post_cancel = int(expected.get("expected_post_cancel_tool_return_count", 0) or 0)

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass"
    l0["score"] = {"kind": "boolean", "value": True}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)

    observed = execution_result["execution"]
    observed_status = observed.get("status")
    observed_reason_codes = set(_string_list(observed.get("lifecycle_reason_codes")))
    observed_cleanup_codes = _string_list(observed.get("cleanup_completion_reason_codes"))
    observed_terminal_write_count = int(observed.get("terminal_write_count_observed", observed.get("terminal_write_count", 0)) or 0)
    observed_terminal_write_attempt_count = int(observed.get("terminal_write_attempt_count", observed_terminal_write_count) or 0)
    observed_duplicate = bool(observed.get("duplicate_terminal_write_observed"))
    observed_post_cancel = int(observed.get("post_cancel_tool_return_count", 0) or 0)
    observed_cleanup_race = bool(observed.get("cleanup_race_detected"))
    observed_runtime_probe = observed.get("runtime_probe")
    mechanism_visible = (
        isinstance(observed_status, str)
        and isinstance(observed.get("lifecycle_sequence_fingerprint"), str)
        and isinstance(observed_terminal_write_attempt_count, int)
        and isinstance(observed_post_cancel, int)
        and isinstance(observed_cleanup_race, bool)
        and bool(expected_reason_codes or observed_cleanup_codes)
    )

    status_match = observed_status == expected_status
    reason_match = expected_reason_codes.issubset(observed_reason_codes)
    duplicate_match = observed_duplicate == expected_duplicate
    cleanup_race_match = observed_cleanup_race == expected_cleanup_race
    post_cancel_match = observed_post_cancel == expected_post_cancel
    duplicate_evidence_complete = (not expected_duplicate) or observed_terminal_write_attempt_count > 1

    if not mechanism_visible:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "lifecycle_adversarial_runtime_evidence_missing")
        _set_unresolved(aggregate, ["lifecycle_adversarial_runtime_evidence_missing"])
    elif all((status_match, reason_match, duplicate_match, cleanup_race_match, post_cancel_match, duplicate_evidence_complete)):
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        if not status_match:
            _add_reason(l2, "lifecycle_adversarial_status_mismatch")
        if not reason_match:
            _add_reason(l2, "lifecycle_adversarial_reason_code_mismatch")
        if not duplicate_match:
            _add_reason(l2, "lifecycle_adversarial_duplicate_terminal_write_mismatch")
        if not cleanup_race_match:
            _add_reason(l2, "lifecycle_adversarial_cleanup_race_mismatch")
        if not post_cancel_match:
            _add_reason(l2, "lifecycle_adversarial_post_cancel_return_mismatch")
        if not duplicate_evidence_complete:
            _add_reason(l2, "lifecycle_adversarial_duplicate_terminal_write_evidence_missing")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "lifecycle_adversarial_terminality_failed")
        aggregate["final_verdict"] = "fail"

    trace["mechanism_exercised"] = True
    trace["lifecycle_adversarial_case_id"] = fixture.get("adversarial_case_id", fixture.get("seed_id"))
    trace["lifecycle_adversarial_expected_status"] = expected_status
    trace["lifecycle_adversarial_status_match"] = status_match
    trace["terminal_write_count_observed"] = observed_terminal_write_count
    trace["terminal_write_attempt_count_observed"] = observed_terminal_write_attempt_count
    trace["duplicate_terminal_write_observed"] = observed_duplicate
    trace["post_cancel_tool_return_count"] = observed_post_cancel
    trace["cleanup_completed"] = bool(observed.get("cleanup_completed"))
    trace["cleanup_completion_reason_codes"] = observed_cleanup_codes
    trace["cleanup_race_detected"] = observed_cleanup_race
    trace["lifecycle_sequence_fingerprint"] = observed.get("lifecycle_sequence_fingerprint")
    trace["lifecycle_reason_codes"] = sorted(observed_reason_codes)
    trace["lifecycle_runtime_probe_defined"] = isinstance(observed_runtime_probe, dict)
    trace["lifecycle_runtime_probe_events"] = (
        _string_list(observed_runtime_probe.get("observed_event_types"))
        if isinstance(observed_runtime_probe, dict)
        else []
    )
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = not mechanism_visible


def _grade_cwd_workdir_path_contract(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    tuple_data = fixture.get("path_contract_tuple")
    tuple_complete = _cwd_tuple_complete(tuple_data)
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if tuple_complete else "fail"
    l0["score"] = {"kind": "boolean", "value": tuple_complete}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not tuple_complete:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "cwd_path_contract_tuple_incomplete")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "cwd_path_contract_tuple_incomplete")
        _set_unresolved(aggregate, ["cwd_path_contract_tuple_incomplete"])
        trace["mechanism_exercised"] = False
        trace["cwd_path_tuple_complete"] = False
        return

    tuple_data = dict(tuple_data)
    tuple_coherent = _cwd_tuple_coherent(tuple_data)
    execution_cwd = (
        execution_result.get("run_header", {})
        .get("environment", {})
        .get("cwd")
    )
    target_cwd = tuple_data["target_cwd"]
    recorded_cwd = tuple_data["recorded_cwd"]
    recorded_workdir = tuple_data["recorded_workdir"]
    resolved_target = tuple_data["resolved_target_path"]
    normalized_target = tuple_data["normalized_target_path"]
    metadata_complete = bool(tuple_data["path_metadata_complete"])
    path_contract_state = execution_result["execution"].get("path_contract_state", {})
    path_state_guard_applied = bool(path_contract_state.get("cwd_invariant_guard_applied"))
    path_state_expected_cwd = path_contract_state.get("expected_cwd")
    path_state_observed_cwd = path_contract_state.get("observed_cwd")
    path_state_cwd_match = bool(path_contract_state.get("cwd_match"))
    path_state_complete = (
        path_state_guard_applied
        and isinstance(path_state_expected_cwd, str)
        and isinstance(path_state_observed_cwd, str)
    )
    cwd_match = (
        isinstance(execution_cwd, str)
        and execution_cwd == target_cwd
        and recorded_cwd == target_cwd
        and recorded_workdir == target_cwd
    )
    normalized_match = _normalize_path(resolved_target) == _normalize_path(normalized_target)
    target_within_cwd = _path_within(base_path=target_cwd, target_path=normalized_target)
    mechanism_match = path_state_complete and path_state_expected_cwd == target_cwd and path_state_cwd_match

    if not tuple_coherent:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "cwd_path_contract_tuple_incoherent")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "cwd_path_contract_tuple_incoherent")
        _set_unresolved(aggregate, ["cwd_path_contract_tuple_incoherent"])
    elif metadata_complete and cwd_match and normalized_match and target_within_cwd:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        if not metadata_complete:
            _add_reason(l2, "cwd_path_contract_tuple_metadata_incomplete")
        if not cwd_match:
            _add_reason(l2, "cwd_path_contract_cwd_mismatch")
        if not normalized_match:
            _add_reason(l2, "cwd_path_contract_normalization_mismatch")
        if not target_within_cwd:
            _add_reason(l2, "cwd_path_contract_target_outside_cwd")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "cwd_path_contract_failed")
        aggregate["final_verdict"] = "fail"
    trace["mechanism_exercised"] = True
    trace["cwd_path_tuple_complete"] = tuple_complete
    trace["cwd_path_tuple_coherent"] = tuple_coherent
    trace["cwd_path_metadata_complete"] = metadata_complete
    trace["cwd_path_cwd_match"] = cwd_match
    trace["cwd_path_normalized_match"] = normalized_match
    trace["cwd_path_target_within_cwd"] = target_within_cwd
    trace["cwd_path_state_guard_applied"] = path_state_guard_applied
    trace["cwd_path_state_complete"] = path_state_complete
    trace["cwd_path_state_expected_cwd"] = path_state_expected_cwd
    trace["cwd_path_state_observed_cwd"] = path_state_observed_cwd
    trace["cwd_path_state_match"] = mechanism_match
    trace["mechanism_visibility_complete"] = path_state_complete
    trace["schema_complete_for_promotion"] = path_state_complete
    trace["helper_only_evidence"] = not path_state_complete


def _grade_workspace_target_probe(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    commands = _tool_commands(execution_result)
    run_dir = Path(fixture_ref).resolve().parent
    target = str(fixture.get("target_path", ""))
    decoys = [str(item) for item in fixture.get("decoy_paths", [])]
    target_expected_text = fixture.get("target_expected_text")
    decoy_expected_texts = fixture.get("decoy_expected_texts", {})
    target_hit = any(target and target in command for command in commands)
    decoy_touched = any(decoy and decoy in command for command in commands for decoy in decoys)
    target_content = _read_fixture_text(run_dir / target) if target else None
    target_content_ok = isinstance(target_expected_text, str) and target_content == target_expected_text
    decoys_preserved = True
    if isinstance(decoy_expected_texts, dict):
        for decoy in decoys:
            expected = decoy_expected_texts.get(decoy)
            if isinstance(expected, str):
                if _read_fixture_text(run_dir / decoy) != expected:
                    decoys_preserved = False
                    break

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass"
    l0["score"] = {"kind": "boolean", "value": True}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not commands:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "not_exercised"}
        _add_reason(l2, "workspace_target_probe_not_exercised_no_tool_calls")
        _set_unresolved(aggregate, ["workspace_target_probe_not_exercised_no_tool_calls"])
    elif target_hit and not decoy_touched and target_content_ok and decoys_preserved:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        reason = "workspace_target_not_hit"
        if target_hit and not target_content_ok:
            reason = "workspace_target_content_mismatch"
        elif decoy_touched:
            reason = "workspace_target_decoy_touched"
        elif not decoys_preserved:
            reason = "workspace_decoy_content_modified"
        _add_reason(l2, reason)
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        aggregate["final_verdict"] = "fail"
    trace["mechanism_exercised"] = bool(commands)
    trace["workspace_target_hit"] = target_hit
    trace["workspace_decoy_touched"] = decoy_touched
    trace["workspace_target_content_ok"] = target_content_ok
    trace["workspace_decoys_preserved"] = decoys_preserved


def _grade_workspace_target_decoy_generalization_v2(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    run_dir = Path(fixture_ref).resolve().parent
    target_descriptor = fixture.get("target_descriptor")
    decoy_descriptors = fixture.get("decoy_descriptors")
    transfer_framing = fixture.get("development_transfer_framing")
    regime_id = fixture.get("regime_id")
    rotation_index = fixture.get("regime_rotation_index")
    regime_count = fixture.get("regime_count")

    target_path, target_id = _workspace_target_descriptor_fields(target_descriptor)
    decoy_rows = _workspace_decoy_descriptor_rows(decoy_descriptors)
    decoy_paths = [row["path"] for row in decoy_rows]
    decoy_ids = [row["decoy_id"] for row in decoy_rows]
    commands = _tool_commands(execution_result)
    target_touch_evidence = [
        command for command in commands if target_path and target_path in command
    ]
    decoy_touch_evidence = [
        {
            "decoy_id": row["decoy_id"],
            "decoy_path": row["path"],
            "command": command,
        }
        for row in decoy_rows
        for command in commands
        if row["path"] in command
    ]
    decoy_touched = bool(decoy_touch_evidence)
    target_hit = bool(target_touch_evidence)

    target_expected_text = target_descriptor.get("expected_text") if isinstance(target_descriptor, dict) else None
    target_content = _read_fixture_text(run_dir / target_path) if target_path else None
    target_content_ok = isinstance(target_expected_text, str) and target_content == target_expected_text

    decoys_preserved = True
    for row in decoy_rows:
        expected_text = row.get("expected_text")
        observed_text = _read_fixture_text(run_dir / row["path"])
        if not isinstance(expected_text, str) or observed_text != expected_text:
            decoys_preserved = False
            break

    transfer_tier = None
    if isinstance(transfer_framing, dict):
        tier_value = transfer_framing.get("task_tier")
        if isinstance(tier_value, str):
            transfer_tier = tier_value
    forced_probe_observed = _workspace_forced_probe_observed(execution_result)
    metadata_complete = (
        isinstance(target_id, str)
        and bool(target_id)
        and isinstance(target_path, str)
        and bool(target_path)
        and bool(decoy_rows)
        and isinstance(regime_id, str)
        and bool(regime_id)
        and isinstance(rotation_index, int)
        and isinstance(regime_count, int)
        and regime_count >= 2
        and transfer_tier == "development_transfer"
    )
    mechanism_visible = metadata_complete and bool(commands) and not forced_probe_observed

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if metadata_complete else "fail"
    l0["score"] = {"kind": "boolean", "value": metadata_complete}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)

    if not metadata_complete:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "workspace_target_decoy_generalization_fixture_metadata_incomplete")
        _set_unresolved(aggregate, ["workspace_target_decoy_generalization_fixture_metadata_incomplete"])
    elif forced_probe_observed:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "workspace_target_decoy_generalization_forced_probe_contamination")
        _set_unresolved(aggregate, ["workspace_target_decoy_generalization_forced_probe_contamination"])
    elif not commands:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "not_exercised"}
        _add_reason(l2, "workspace_target_decoy_generalization_not_exercised_no_tool_calls")
        _set_unresolved(aggregate, ["workspace_target_decoy_generalization_not_exercised_no_tool_calls"])
    elif target_hit and not decoy_touched and target_content_ok and decoys_preserved:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        reason = "workspace_target_not_hit"
        if target_hit and not target_content_ok:
            reason = "workspace_target_content_mismatch"
        elif decoy_touched:
            reason = "workspace_target_decoy_touched"
        elif not decoys_preserved:
            reason = "workspace_decoy_content_modified"
        _add_reason(l2, reason)
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        aggregate["final_verdict"] = "fail"

    trace["mechanism_exercised"] = bool(commands)
    trace["workspace_target_target_id"] = target_id
    trace["workspace_target_target_path"] = target_path
    trace["workspace_target_decoy_ids"] = decoy_ids
    trace["workspace_target_decoy_paths"] = decoy_paths
    trace["workspace_target_regime_id"] = regime_id
    trace["workspace_target_regime_rotation_index"] = rotation_index
    trace["workspace_target_regime_count"] = regime_count
    trace["workspace_target_transfer_tier"] = transfer_tier
    trace["workspace_target_target_touch_evidence"] = target_touch_evidence
    trace["workspace_target_decoy_touch_evidence"] = decoy_touch_evidence
    trace["workspace_target_hit"] = target_hit
    trace["workspace_decoy_touched"] = decoy_touched
    trace["workspace_target_content_ok"] = target_content_ok
    trace["workspace_decoys_preserved"] = decoys_preserved
    trace["workspace_target_forced_probe_observed"] = forced_probe_observed
    trace["workspace_target_trace_linkage_complete"] = metadata_complete and bool(commands)
    trace["workspace_target_rotation_supported"] = isinstance(regime_count, int) and regime_count >= 2
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = False


def _grade_workspace_target_decoy_multistep_v1(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    run_dir = Path(fixture_ref).resolve().parent
    target_descriptor = fixture.get("target_descriptor")
    decoy_descriptors = fixture.get("decoy_descriptors")
    transfer_framing = fixture.get("development_transfer_framing")
    regime_id = fixture.get("regime_id")
    rotation_index = fixture.get("regime_rotation_index")
    regime_count = fixture.get("regime_count")
    activation_payload = fixture.get("activation_payload_descriptor")
    turn_contract = fixture.get("multistep_turn_contract")

    target_path, target_id = _workspace_target_descriptor_fields(target_descriptor)
    decoy_rows = _workspace_decoy_descriptor_rows(decoy_descriptors)
    decoy_paths = [row["path"] for row in decoy_rows]
    decoy_ids = [row["decoy_id"] for row in decoy_rows]

    source_path = ""
    if isinstance(activation_payload, dict):
        source_candidate = activation_payload.get("source_path")
        if isinstance(source_candidate, str) and source_candidate:
            source_path = source_candidate

    minimum_turn_count = 2
    if isinstance(turn_contract, dict):
        min_turn_candidate = turn_contract.get("minimum_turn_count")
        if isinstance(min_turn_candidate, int) and min_turn_candidate >= 2:
            minimum_turn_count = min_turn_candidate

    step_rows = _workspace_step_command_rows(execution_result)
    turn_count = len(step_rows)
    first_tool_step_index = next(
        (row["step_index"] for row in step_rows if row["commands"]),
        None,
    )
    first_step_commands = step_rows[0]["commands"] if step_rows else []
    first_turn_observation_evidence = [
        command
        for command in first_step_commands
        if source_path and source_path in command
    ]
    if source_path:
        first_turn_observation_met = bool(first_turn_observation_evidence)
    else:
        first_turn_observation_met = bool(first_step_commands)
    post_observation_step_met = bool(step_rows) and any(row["step_index"] > 0 for row in step_rows)
    post_observation_target_touch_evidence = [
        command
        for row in step_rows
        if row["step_index"] > 0
        for command in row["commands"]
        if target_path and target_path in command
    ]
    target_touch_after_observation = bool(post_observation_target_touch_evidence)
    commands = [command for row in step_rows for command in row["commands"]]
    target_touch_evidence = [command for command in commands if target_path and target_path in command]
    decoy_touch_evidence = [
        {
            "decoy_id": row["decoy_id"],
            "decoy_path": row["path"],
            "command": command,
        }
        for row in decoy_rows
        for command in commands
        if row["path"] in command
    ]
    decoy_touched = bool(decoy_touch_evidence)
    target_hit = bool(target_touch_evidence)

    target_expected_text = target_descriptor.get("expected_text") if isinstance(target_descriptor, dict) else None
    target_content = _read_fixture_text(run_dir / target_path) if target_path else None
    target_content_ok = isinstance(target_expected_text, str) and target_content == target_expected_text

    decoys_preserved = True
    for row in decoy_rows:
        expected_text = row.get("expected_text")
        observed_text = _read_fixture_text(run_dir / row["path"])
        if not isinstance(expected_text, str) or observed_text != expected_text:
            decoys_preserved = False
            break

    transfer_tier = None
    if isinstance(transfer_framing, dict):
        tier_value = transfer_framing.get("task_tier")
        if isinstance(tier_value, str):
            transfer_tier = tier_value
    forced_probe_observed = _workspace_forced_probe_observed(execution_result)
    metadata_complete = (
        isinstance(target_id, str)
        and bool(target_id)
        and isinstance(target_path, str)
        and bool(target_path)
        and bool(decoy_rows)
        and isinstance(regime_id, str)
        and bool(regime_id)
        and isinstance(rotation_index, int)
        and isinstance(regime_count, int)
        and regime_count >= 2
        and transfer_tier == "development_transfer"
        and bool(source_path)
    )
    turn_contract_satisfied = (
        metadata_complete
        and not forced_probe_observed
        and turn_count >= minimum_turn_count
        and first_tool_step_index == 0
        and first_turn_observation_met
        and post_observation_step_met
        and target_touch_after_observation
    )
    mechanism_visible = turn_contract_satisfied

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if metadata_complete else "fail"
    l0["score"] = {"kind": "boolean", "value": metadata_complete}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)

    if not metadata_complete:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "workspace_target_decoy_generalization_fixture_metadata_incomplete")
        _set_unresolved(aggregate, ["workspace_target_decoy_generalization_fixture_metadata_incomplete"])
    elif forced_probe_observed:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "workspace_target_decoy_generalization_forced_probe_contamination")
        _set_unresolved(aggregate, ["workspace_target_decoy_generalization_forced_probe_contamination"])
    elif not commands:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "not_exercised"}
        _add_reason(l2, "workspace_target_decoy_generalization_not_exercised_no_tool_calls")
        _set_unresolved(aggregate, ["workspace_target_decoy_generalization_not_exercised_no_tool_calls"])
    elif not turn_contract_satisfied:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "multistep_turn_contract_not_satisfied"}
        _add_reason(l2, "workspace_target_multistep_turn_contract_not_satisfied")
        _set_unresolved(aggregate, ["workspace_target_multistep_turn_contract_not_satisfied"])
    elif target_hit and not decoy_touched and target_content_ok and decoys_preserved:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        reason = "workspace_target_not_hit"
        if target_hit and not target_content_ok:
            reason = "workspace_target_content_mismatch"
        elif decoy_touched:
            reason = "workspace_target_decoy_touched"
        elif not decoys_preserved:
            reason = "workspace_decoy_content_modified"
        _add_reason(l2, reason)
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        aggregate["final_verdict"] = "fail"

    trace["mechanism_exercised"] = bool(commands)
    trace["workspace_target_target_id"] = target_id
    trace["workspace_target_target_path"] = target_path
    trace["workspace_target_decoy_ids"] = decoy_ids
    trace["workspace_target_decoy_paths"] = decoy_paths
    trace["workspace_target_regime_id"] = regime_id
    trace["workspace_target_regime_rotation_index"] = rotation_index
    trace["workspace_target_regime_count"] = regime_count
    trace["workspace_target_transfer_tier"] = transfer_tier
    trace["workspace_target_target_touch_evidence"] = target_touch_evidence
    trace["workspace_target_decoy_touch_evidence"] = decoy_touch_evidence
    trace["workspace_target_hit"] = target_hit
    trace["workspace_decoy_touched"] = decoy_touched
    trace["workspace_target_content_ok"] = target_content_ok
    trace["workspace_decoys_preserved"] = decoys_preserved
    trace["workspace_target_forced_probe_observed"] = forced_probe_observed
    trace["workspace_target_trace_linkage_complete"] = metadata_complete and bool(commands)
    trace["workspace_target_rotation_supported"] = isinstance(regime_count, int) and regime_count >= 2
    trace["workspace_target_multistep_min_turns_required"] = minimum_turn_count
    trace["workspace_target_multistep_turn_count"] = turn_count
    trace["workspace_target_multistep_first_tool_step_index"] = first_tool_step_index
    trace["workspace_target_multistep_first_turn_observation_met"] = first_turn_observation_met
    trace["workspace_target_multistep_post_observation_step_met"] = post_observation_step_met
    trace["workspace_target_multistep_target_touch_after_observation"] = target_touch_after_observation
    trace["workspace_target_multistep_contract_satisfied"] = turn_contract_satisfied
    trace["workspace_target_observation_source_path"] = source_path
    trace["workspace_target_first_turn_observation_evidence"] = first_turn_observation_evidence
    trace["workspace_target_post_observation_target_touch_evidence"] = (
        post_observation_target_touch_evidence
    )
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = False


def _grade_tool_result_normalization_probe(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    runtime_probe = execution_result["execution"].get("runtime_probe", {})
    matrix = fixture.get("classification_matrix", [])
    matrix_ok = all(
        _classify_tool_result(row.get("result_payload", {})) == row.get("expected_class")
        for row in matrix
    )
    observed = [_classify_tool_result(result) for result in _tool_results(execution_result)]
    observed_set = set(observed)
    required_categories = set(fixture.get("required_runtime_categories", []))
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if matrix_ok else "fail"
    l0["score"] = {"kind": "boolean", "value": matrix_ok}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not matrix_ok:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "tool_result_classifier_fixture_mismatch")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        aggregate["final_verdict"] = "fail"
    elif not observed:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "not_exercised"}
        _add_reason(l2, "tool_result_probe_not_exercised_no_tool_results")
        _set_unresolved(aggregate, ["tool_result_probe_not_exercised_no_tool_results"])
    elif not required_categories.issubset(observed_set):
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "tool_result_permission_runtime_not_separable")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        aggregate["final_verdict"] = "fail"
    else:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    trace["mechanism_exercised"] = bool(observed)
    trace["observed_tool_result_categories"] = sorted(observed_set)
    trace["forced_runtime_calls_executed"] = runtime_probe.get("executed_call_count", 0)


def _grade_tool_result_attribution_quality_v2(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    expected_cases = fixture.get("expected_attribution_cases", [])
    observed_results = _tool_results(execution_result)
    observed_by_case = {
        result.get("case_id"): result
        for result in observed_results
        if isinstance(result, dict) and isinstance(result.get("case_id"), str)
    }
    case_results: list[dict[str, Any]] = []
    matched = 0
    incomplete_attribution_case_ids: list[str] = []
    for case in expected_cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id")
        observed = observed_by_case.get(case_id) if isinstance(case_id, str) else None
        attribution_trace = observed.get("attribution_trace") if isinstance(observed, dict) else None
        attribution_complete = _attribution_trace_complete_for_case(
            attribution_trace=attribution_trace,
            expected_reason_code=case.get("expected_reason_code"),
        )
        result_match = (
            isinstance(observed, dict)
            and observed.get("result_class") == case.get("expected_result_class")
            and observed.get("reason_code") == case.get("expected_reason_code")
        )
        if result_match:
            matched += 1
        case_results.append(
            {
                "case_id": case_id,
                "expected_result_class": case.get("expected_result_class"),
                "expected_reason_code": case.get("expected_reason_code"),
                "observed_result_class": observed.get("result_class") if isinstance(observed, dict) else None,
                "observed_reason_code": observed.get("reason_code") if isinstance(observed, dict) else None,
                "attribution_trace": attribution_trace if isinstance(attribution_trace, dict) else None,
                "attribution_evidence_complete": attribution_complete,
            }
        )
        if not attribution_complete and isinstance(case_id, str) and case_id:
            incomplete_attribution_case_ids.append(case_id)

    matrix_ok = bool(expected_cases) and matched == len(expected_cases) and len(observed_by_case) >= len(expected_cases)
    attribution_evidence_complete = bool(expected_cases) and not incomplete_attribution_case_ids
    mechanism_visible = (
        bool(expected_cases)
        and len(observed_by_case) >= len(expected_cases)
        and attribution_evidence_complete
        and all(
            isinstance(result.get("observed_reason_code"), str) and result["observed_reason_code"]
            for result in case_results
        )
    )
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if mechanism_visible else "fail"
    l0["score"] = {"kind": "boolean", "value": mechanism_visible}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not mechanism_visible:
        if not observed_by_case:
            l2["status"] = "unavailable"
            l2["score"] = {"kind": "categorical", "value": "tool_result_attribution_runtime_evidence_missing"}
            _add_reason(l2, "tool_result_attribution_runtime_evidence_missing")
            _set_unresolved(aggregate, ["tool_result_attribution_runtime_evidence_missing"])
        elif incomplete_attribution_case_ids:
            l2["status"] = "fail"
            l2["score"] = {"kind": "boolean", "value": False}
            _add_reason(l2, "tool_result_attribution_evidence_incomplete")
            l4["status"] = "fail"
            l4["score"] = {"kind": "boolean", "value": False}
            _add_reason(l4, "tool_result_attribution_quality_failed")
            aggregate["final_verdict"] = "fail"
        else:
            l2["status"] = "unavailable"
            l2["score"] = {"kind": "categorical", "value": "tool_result_attribution_runtime_evidence_missing"}
            _add_reason(l2, "tool_result_attribution_runtime_evidence_missing")
            _set_unresolved(aggregate, ["tool_result_attribution_runtime_evidence_missing"])
    elif matrix_ok:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "tool_result_attribution_mismatch")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "tool_result_attribution_quality_failed")
        aggregate["final_verdict"] = "fail"
    observed_categories = sorted(
        {
            result.get("result_class")
            for result in observed_results
            if isinstance(result, dict) and isinstance(result.get("result_class"), str)
        }
    )
    trace["mechanism_exercised"] = bool(observed_results)
    trace["tool_result_attribution_cases_total"] = len(expected_cases)
    trace["tool_result_attribution_cases_matched"] = matched
    trace["tool_result_attribution_case_results"] = case_results
    trace["observed_tool_result_categories"] = observed_categories
    trace["tool_result_attribution_source"] = "execution_loop"
    trace["tool_result_attribution_incomplete_case_ids"] = sorted(incomplete_attribution_case_ids)
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = False


def _grade_internal_toolchain_dependency_pressure_v1(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    expected_cases = fixture.get("expected_toolchain_cases", [])
    observed_results = _tool_results(execution_result)
    observed_by_case = {
        result.get("case_id"): result
        for result in observed_results
        if isinstance(result, dict) and isinstance(result.get("case_id"), str)
    }
    case_results: list[dict[str, Any]] = []
    matched = 0
    incomplete_case_ids: list[str] = []
    for case in expected_cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id")
        observed = observed_by_case.get(case_id) if isinstance(case_id, str) else None
        observed_contract = observed.get("tool_call_contract_class") if isinstance(observed, dict) else None
        observed_result = observed.get("result_class") if isinstance(observed, dict) else None
        observed_reason = observed.get("reason_code") if isinstance(observed, dict) else None
        expected_contract = case.get("expected_contract_class")
        expected_result = case.get("expected_result_class")
        expected_reason = case.get("expected_reason_code")
        matched_case = (
            observed_contract == expected_contract
            and observed_result == expected_result
            and observed_reason == expected_reason
        )
        if matched_case:
            matched += 1
        if not (
            isinstance(observed_contract, str)
            and observed_contract
            and isinstance(observed_result, str)
            and observed_result
            and isinstance(observed_reason, str)
            and observed_reason
        ):
            if isinstance(case_id, str) and case_id:
                incomplete_case_ids.append(case_id)
        case_results.append(
            {
                "case_id": case_id,
                "expected_contract_class": expected_contract,
                "observed_contract_class": observed_contract,
                "expected_result_class": expected_result,
                "observed_result_class": observed_result,
                "expected_reason_code": expected_reason,
                "observed_reason_code": observed_reason,
                "matched": matched_case,
            }
        )

    trace_complete = bool(expected_cases) and not incomplete_case_ids
    mechanism_visible = (
        bool(expected_cases)
        and len(observed_by_case) >= len(expected_cases)
        and trace_complete
    )
    matrix_ok = mechanism_visible and matched == len(expected_cases)

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if mechanism_visible else "fail"
    l0["score"] = {"kind": "boolean", "value": mechanism_visible}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not mechanism_visible:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "toolchain_dependency_runtime_evidence_missing"}
        _add_reason(l2, "toolchain_dependency_runtime_evidence_missing")
        _set_unresolved(aggregate, ["toolchain_dependency_runtime_evidence_missing"])
    elif matrix_ok:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "toolchain_dependency_contract_mismatch")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "toolchain_dependency_pressure_failed")
        aggregate["final_verdict"] = "fail"

    trace["mechanism_exercised"] = bool(observed_results)
    trace["toolchain_pressure_source"] = "execution_loop"
    trace["toolchain_pressure_cases_total"] = len(expected_cases)
    trace["toolchain_pressure_cases_matched"] = matched
    trace["toolchain_pressure_case_results"] = case_results
    trace["toolchain_pressure_trace_complete"] = trace_complete
    trace["toolchain_pressure_incomplete_case_ids"] = sorted(incomplete_case_ids)
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = False


def _grade_internal_artifact_log_extraction_v1(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    expected_cases = fixture.get("expected_artifact_log_cases", [])
    observed_results = _tool_results(execution_result)
    observed_by_case = {
        result.get("case_id"): result
        for result in observed_results
        if isinstance(result, dict) and isinstance(result.get("case_id"), str)
    }
    case_results: list[dict[str, Any]] = []
    matched = 0
    incomplete_case_ids: list[str] = []
    for case in expected_cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id")
        observed = observed_by_case.get(case_id) if isinstance(case_id, str) else None
        attribution_trace = observed.get("attribution_trace") if isinstance(observed, dict) else None
        expected_reason = case.get("expected_reason_code")
        expected_result = case.get("expected_result_class")
        observed_result = observed.get("result_class") if isinstance(observed, dict) else None
        observed_reason = observed.get("reason_code") if isinstance(observed, dict) else None
        attribution_complete = _attribution_trace_complete_for_case(
            attribution_trace=attribution_trace,
            expected_reason_code=expected_reason,
        )
        matched_case = observed_result == expected_result and observed_reason == expected_reason
        if matched_case:
            matched += 1
        if not (
            isinstance(observed_result, str)
            and observed_result
            and isinstance(observed_reason, str)
            and observed_reason
            and attribution_complete
        ):
            if isinstance(case_id, str) and case_id:
                incomplete_case_ids.append(case_id)
        case_results.append(
            {
                "case_id": case_id,
                "expected_result_class": expected_result,
                "observed_result_class": observed_result,
                "expected_reason_code": expected_reason,
                "observed_reason_code": observed_reason,
                "attribution_trace": attribution_trace if isinstance(attribution_trace, dict) else None,
                "attribution_evidence_complete": attribution_complete,
                "matched": matched_case,
            }
        )

    trace_complete = bool(expected_cases) and not incomplete_case_ids
    mechanism_visible = (
        bool(expected_cases)
        and len(observed_by_case) >= len(expected_cases)
        and trace_complete
    )
    matrix_ok = mechanism_visible and matched == len(expected_cases)
    observed_categories = sorted(
        {
            result.get("result_class")
            for result in observed_results
            if isinstance(result, dict) and isinstance(result.get("result_class"), str)
        }
    )

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if mechanism_visible else "fail"
    l0["score"] = {"kind": "boolean", "value": mechanism_visible}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not mechanism_visible:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "artifact_log_runtime_evidence_missing"}
        _add_reason(l2, "artifact_log_runtime_evidence_missing")
        _set_unresolved(aggregate, ["artifact_log_runtime_evidence_missing"])
    elif matrix_ok:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "artifact_log_extraction_mismatch")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "artifact_log_extraction_failed")
        aggregate["final_verdict"] = "fail"

    trace["mechanism_exercised"] = bool(observed_results)
    trace["artifact_log_source"] = "execution_loop"
    trace["artifact_log_cases_total"] = len(expected_cases)
    trace["artifact_log_cases_matched"] = matched
    trace["artifact_log_case_results"] = case_results
    trace["artifact_log_trace_complete"] = trace_complete
    trace["artifact_log_incomplete_case_ids"] = sorted(incomplete_case_ids)
    trace["observed_tool_result_categories"] = observed_categories
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = False


def _grade_internal_discovery_evidence_efficiency_v1(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    run_dir = Path(fixture_ref).resolve().parent
    evidence_path = _relative_fixture_path(fixture.get("evidence_bundle_path"))
    report_path = _relative_fixture_path(fixture.get("report_path"))
    expected_report = fixture.get("expected_report")
    required_report_keys = set(_string_list(fixture.get("required_report_keys")))
    required_justification_value = fixture.get("required_justification_value")
    if not isinstance(required_justification_value, str) or not required_justification_value:
        required_justification_value = "evidence_bundle_inspected"
    probe_budget_max = int(fixture.get("probe_budget_max", 0) or 0)
    commands = _tool_commands(execution_result)
    first_write_index = _first_write_command_index(commands, report_path)
    discovery_commands = _commands_before_first_write(
        commands,
        first_write_index,
        evidence_path=evidence_path,
    )
    non_redundant_probing = len(discovery_commands) == len(set(discovery_commands))
    within_probe_budget = probe_budget_max <= 0 or len(discovery_commands) <= probe_budget_max
    report_data = _read_fixture_json(run_dir / report_path) if report_path else None
    report_matches = isinstance(expected_report, dict) and report_data == expected_report
    report_required_keys_present = (
        isinstance(report_data, dict)
        and bool(required_report_keys)
        and required_report_keys.issubset(set(report_data.keys()))
    )
    decoys_preserved = _fixture_paths_preserved(
        run_dir=run_dir,
        relative_paths=_string_list(fixture.get("decoy_paths")),
    )
    justification = report_data.get("justification") if isinstance(report_data, dict) else None
    justification_key_present = isinstance(report_data, dict) and "justification" in report_data
    final_justification_present = isinstance(justification, str) and bool(justification)
    final_justification_canonical = justification == required_justification_value
    mechanism_visible = (
        bool(evidence_path)
        and bool(report_path)
        and bool(discovery_commands)
        and non_redundant_probing
        and within_probe_budget
        and report_required_keys_present
        and report_matches
        and decoys_preserved
        and final_justification_canonical
    )

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = (
        "pass"
        if bool(
            evidence_path
            and report_path
            and isinstance(expected_report, dict)
            and required_report_keys
        )
        else "fail"
    )
    l0["score"] = {"kind": "boolean", "value": l0["status"] == "pass"}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)

    if not commands:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "not_exercised"}
        _add_reason(l2, "internal_discovery_not_exercised_no_tool_calls")
        _set_unresolved(aggregate, ["internal_discovery_not_exercised_no_tool_calls"])
    elif mechanism_visible:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        if not discovery_commands:
            _add_reason(l2, "internal_discovery_evidence_chain_missing")
        if not non_redundant_probing or not within_probe_budget:
            _add_reason(l2, "internal_discovery_probe_budget_failed")
        if not report_matches:
            _add_reason(l2, "internal_discovery_report_mismatch")
        if not report_required_keys_present:
            _add_reason(l2, "internal_discovery_report_schema_required_keys_missing")
        if not decoys_preserved:
            _add_reason(l2, "internal_discovery_decoy_modified")
        if not justification_key_present:
            _add_reason(l2, "internal_discovery_justification_absent")
        elif not final_justification_canonical:
            _add_reason(l2, "internal_discovery_justification_noncanonical")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "internal_discovery_evidence_efficiency_failed")
        aggregate["final_verdict"] = "fail"

    tool_contract_cases = {}
    tool_result_cases = {}
    if isinstance(report_data, dict):
        tool_contract_cases = report_data.get("tool_contract_cases", {})
        tool_result_cases = report_data.get("tool_result_cases", {})
    trace["mechanism_exercised"] = bool(commands)
    trace["discovery_step_evidence"] = discovery_commands
    trace["bounded_probing_markers"] = {
        "count": len(discovery_commands),
        "non_redundant": non_redundant_probing,
        "within_budget": within_probe_budget,
    }
    trace["call_class_telemetry"] = tool_contract_cases if isinstance(tool_contract_cases, dict) else {}
    trace["attribution_case_results"] = tool_result_cases if isinstance(tool_result_cases, dict) else {}
    trace["mixed_fault_traces"] = {
        "mixed_fault_live_case": (
            tool_result_cases.get("mixed_fault_live_case")
            if isinstance(tool_result_cases, dict)
            else None
        )
    }
    trace["recovery_branch_evidence"] = bool(discovery_commands) and final_justification_canonical
    trace["required_report_keys"] = sorted(required_report_keys)
    trace["report_required_keys_present"] = report_required_keys_present
    trace["final_justification_markers"] = {
        "justification": justification,
        "present": final_justification_present,
        "key_present": justification_key_present,
        "canonical": final_justification_canonical,
        "required_value": required_justification_value,
    }
    trace["assistant_completion_trace"] = _assistant_completion_trace(execution_result)
    trace["pass_quality"] = "clean_pass" if aggregate["final_verdict"] == "pass" else "needs_followup"
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = False


def _grade_internal_multifile_repair_test_verify_v1(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    run_dir = Path(fixture_ref).resolve().parent
    commands = _tool_commands(execution_result)
    target_paths = _string_list(fixture.get("target_paths"))
    expected_file_texts = fixture.get("expected_file_texts", {})
    verifier_path = _relative_fixture_path(fixture.get("verifier_path"))
    inspect_before_edit = {
        path: _path_inspected_before_edit(commands, path)
        for path in target_paths
    }
    files_match = {
        path: _read_fixture_text(run_dir / path) == expected_file_texts.get(path)
        for path in target_paths
        if isinstance(expected_file_texts, dict)
    }
    decoys_preserved = _expected_file_texts_preserved(
        run_dir=run_dir,
        expected_file_texts=expected_file_texts,
        relative_paths=_string_list(fixture.get("decoy_paths")),
    )
    verifier_command, verifier_command_index = _first_verifier_execution_command(commands, verifier_path)
    first_writes_by_target = {
        path: _first_write_command_index(commands, path)
        for path in target_paths
    }
    all_targets_written_before_verifier = bool(target_paths) and all(
        isinstance(first_writes_by_target.get(path), int)
        and isinstance(verifier_command_index, int)
        and verifier_command_index >= first_writes_by_target[path]
        for path in target_paths
    )
    verifier_after_edit = bool(verifier_command) and all_targets_written_before_verifier
    all_targets_match = bool(target_paths) and all(files_match.get(path, False) for path in target_paths)
    all_targets_inspected = bool(target_paths) and all(inspect_before_edit.values())
    mechanism_visible = (
        bool(commands)
        and all_targets_inspected
        and all_targets_match
        and decoys_preserved
        and verifier_after_edit
    )

    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l4 = layers["L4_final_acceptance"]
    l0["status"] = "pass" if bool(target_paths and verifier_path) else "fail"
    l0["score"] = {"kind": "boolean", "value": l0["status"] == "pass"}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)

    if not commands:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "not_exercised"}
        _add_reason(l2, "internal_multifile_not_exercised_no_tool_calls")
        _set_unresolved(aggregate, ["internal_multifile_not_exercised_no_tool_calls"])
    elif mechanism_visible:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        if not all_targets_inspected:
            _add_reason(l2, "internal_multifile_inspect_before_edit_missing")
        if not all_targets_match:
            _add_reason(l2, "internal_multifile_patch_mismatch")
        if not decoys_preserved:
            _add_reason(l2, "internal_multifile_decoy_modified")
        if not verifier_after_edit:
            _add_reason(l2, "internal_multifile_verify_before_completion_missing")
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "internal_multifile_repair_test_verify_failed")
        aggregate["final_verdict"] = "fail"

    trace["mechanism_exercised"] = bool(commands)
    trace["inspect_before_edit_markers"] = inspect_before_edit
    trace["verify_before_completion"] = verifier_after_edit
    trace["verifier_execution_seen"] = bool(verifier_command)
    trace["all_targets_written_before_verifier"] = all_targets_written_before_verifier
    trace["first_write_indices_by_target"] = first_writes_by_target
    trace["final_evidence_packet"] = {
        "changed_files": sorted(path for path, matched in files_match.items() if matched),
        "verifier_command": verifier_command,
    }
    trace["assistant_completion_trace"] = _assistant_completion_trace(execution_result)
    trace["ordered_lifecycle_events"] = bool(commands) and verifier_after_edit
    trace["single_terminal_write"] = execution_result.get("execution", {}).get("terminal_write_count") == 1
    trace["cleanup_before_terminal"] = bool(execution_result.get("execution", {}).get("cleanup_completed"))
    trace["pass_quality"] = "clean_pass" if aggregate["final_verdict"] == "pass" else "needs_followup"
    trace["mechanism_visibility_complete"] = mechanism_visible
    trace["schema_complete_for_promotion"] = mechanism_visible
    trace["helper_only_evidence"] = False


def _attribution_trace_complete_for_case(
    *,
    attribution_trace: Any,
    expected_reason_code: Any,
) -> bool:
    if not isinstance(attribution_trace, dict):
        return False
    permission_signal = attribution_trace.get("permission_signal_detected")
    runtime_signal = attribution_trace.get("runtime_signal_detected")
    if not isinstance(permission_signal, bool) or not isinstance(runtime_signal, bool):
        return False
    if expected_reason_code == "tool_runtime_mixed_permission_runtime_signals":
        return permission_signal is True and runtime_signal is True
    return True


def _grade_sync_interrupt_cleanup_probe(
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
    fixture: dict[str, Any],
    fixture_ref: str,
    execution_result: dict[str, Any],
) -> None:
    runtime_probe = execution_result["execution"].get("runtime_probe", {})
    forced_path = fixture.get("forced_path_probe", [])
    forced_runtime_calls = fixture.get("runtime_probe", {}).get("forced_tool_calls", [])
    recover_count = sum(1 for event in execution_result["run_events"] if event.get("phase") == "recover")
    runtime_plan_executed = int(runtime_probe.get("executed_call_count", 0)) > 0
    runtime_interrupt = bool(runtime_probe.get("interrupt_observed"))
    cleanup_observed = bool(runtime_probe.get("cleanup_observed")) or recover_count > 0
    l0 = layers["L0_inline_assertion"]
    l2 = layers["L2_replay_or_state_grader"]
    l3 = layers["L3_judge_layer"]
    l4 = layers["L4_final_acceptance"]
    forced_defined = (
        isinstance(forced_path, list)
        and bool(forced_path)
        and isinstance(forced_runtime_calls, list)
        and bool(forced_runtime_calls)
    )
    l0["status"] = "pass" if forced_defined else "fail"
    l0["score"] = {"kind": "boolean", "value": l0["status"] == "pass"}
    _add_evidence(l0, fixture_ref)
    l2["grader_id"] = fixture["grader_id"]
    _add_evidence(l2, fixture_ref)
    if not forced_defined:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "forced_path_not_defined"}
        _add_reason(l2, "sync_interrupt_forced_path_not_defined")
    elif not runtime_plan_executed:
        l2["status"] = "unavailable"
        l2["score"] = {"kind": "categorical", "value": "runtime_probe_not_executed"}
        _add_reason(l2, "sync_interrupt_runtime_probe_not_executed")
    elif not runtime_interrupt:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "sync_interrupt_boundary_not_observed")
    elif not cleanup_observed:
        l2["status"] = "fail"
        l2["score"] = {"kind": "boolean", "value": False}
        _add_reason(l2, "sync_interrupt_cleanup_not_observed")
    else:
        l2["status"] = "pass"
        l2["score"] = {"kind": "boolean", "value": True}
    l3_contract = _sync_interrupt_l3_contract(fixture)
    if l3_contract is None:
        l3["status"] = "unavailable"
        l3["score"] = {"kind": "categorical", "value": "judge_contract_missing"}
        _add_reason(l3, "sync_interrupt_l3_judge_contract_missing")
    else:
        l3["judge_config"] = l3_contract
        if l2["status"] == "pass":
            l3["status"] = "pass"
            l3["score"] = {"kind": "boolean", "value": True}
        elif l2["status"] == "fail":
            l3["status"] = "fail"
            l3["score"] = {"kind": "boolean", "value": False}
            _add_reason(l3, "sync_interrupt_bounded_l3_recovery_quality_failed")
        else:
            l3["status"] = "unavailable"
            l3["score"] = {"kind": "categorical", "value": "sync_interrupt_runtime_inputs_incomplete"}
            _add_reason(l3, "sync_interrupt_bounded_l3_inputs_incomplete")

    if l2["status"] == "unavailable":
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "sync_interrupt_runtime_probe_incomplete")
        _set_unresolved(aggregate, ["sync_interrupt_runtime_probe_incomplete"])
    elif l3["status"] == "unavailable":
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "sync_interrupt_l3_contract_unavailable")
        _set_unresolved(aggregate, ["sync_interrupt_l3_contract_unavailable"])
    elif l2["status"] == "pass" and l3["status"] == "pass":
        l4["status"] = "pass"
        l4["score"] = {"kind": "boolean", "value": True}
        aggregate["final_verdict"] = "pass"
    else:
        l4["status"] = "fail"
        l4["score"] = {"kind": "boolean", "value": False}
        _add_reason(l4, "sync_interrupt_cleanup_quality_failed")
        aggregate["final_verdict"] = "fail"

    trace["mechanism_exercised"] = runtime_plan_executed
    trace["forced_path_probe_defined"] = bool(forced_path) and bool(forced_runtime_calls)
    trace["runtime_probe_executed"] = runtime_plan_executed
    trace["interrupt_observed"] = runtime_interrupt
    trace["cleanup_observed"] = cleanup_observed
    trace["recovery_event_count"] = recover_count
    trace["l3_judge_contract_configured"] = l3_contract is not None
    trace["l3_judge_status"] = l3["status"]


def _sync_interrupt_l3_contract(fixture: dict[str, Any]) -> dict[str, str] | None:
    contract = fixture.get("l3_judge_contract")
    if not isinstance(contract, dict):
        return None
    required = ("judge_type", "model", "prompt_fingerprint", "schema_fingerprint", "mode")
    normalized: dict[str, str] = {}
    for key in required:
        value = contract.get(key)
        if not isinstance(value, str) or not value:
            return None
        normalized[key] = value
    return normalized


def _enforce_required_layer_expectations(
    eval_card: dict[str, Any],
    layers: dict[str, dict[str, Any]],
    issues: list[str],
) -> None:
    expectations = eval_card.get("score_layer_expectations", {})
    if not isinstance(expectations, dict):
        return
    for expectation_key, layer_id in LAYER_EXPECTATION_MAP.items():
        requirement = expectations.get(expectation_key)
        if not isinstance(requirement, str) or not requirement.startswith("required"):
            continue
        layer = layers[layer_id]
        if layer.get("status") in {"unavailable", "not_applicable"}:
            reason = f"required_layer_missing_{layer_id.lower()}"
            _add_reason(layer, reason)
            issues.append(reason)


def _enforce_execution_success(
    execution_result: dict[str, Any],
    layers: dict[str, dict[str, Any]],
    aggregate: dict[str, Any],
    trace: dict[str, Any],
) -> None:
    status = execution_result.get("execution", {}).get("status")
    trace["execution_status"] = status
    if (
        trace.get("eval_id") == "ae_lifecycle_adversarial_terminality_v2"
        and trace.get("lifecycle_adversarial_expected_status") == "error"
        and aggregate.get("final_verdict") == "pass"
    ):
        return
    if status != "error":
        return
    l4 = layers["L4_final_acceptance"]
    _add_reason(l4, "model_execution_error")
    details = _extract_model_error_details(execution_result.get("run_events", []))
    if details:
        detail_ref = f"model_client_error:{details}"
        _add_evidence(l4, detail_ref)
    _set_unresolved(aggregate, ["model_execution_error"])


def _extract_model_error_details(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("event_type") != "model_client_error":
            continue
        details = event.get("payload", {}).get("details", {})
        if not isinstance(details, dict):
            continue
        response_body = details.get("response_body")
        if isinstance(response_body, str) and response_body:
            return response_body
        message = details.get("message")
        if isinstance(message, str) and message:
            return message
    return None


def _classify_tool_call_shape(tool_call: Any) -> str:
    if not isinstance(tool_call, dict):
        return "malformed_call"
    name = tool_call.get("name")
    if name != "raw_bash":
        return "unsupported_tool" if isinstance(name, str) else "malformed_call"
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        command = arguments.get("command")
        return "valid_call" if isinstance(command, str) and command else "malformed_call"
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            parsed = {"command": arguments}
        if isinstance(parsed, dict) and isinstance(parsed.get("command"), str) and parsed["command"]:
            return "valid_call"
    return "malformed_call"


def _resolve_tool_call_shape_classifier(
    execution_result: dict[str, Any],
) -> tuple[callable, str]:
    run_header = execution_result.get("run_header", {})
    routed_modules = run_header.get("routed_modules")
    if isinstance(routed_modules, list):
        for entry in routed_modules:
            if not isinstance(entry, dict):
                continue
            if entry.get("runtime_key") != "tool_executor":
                continue
            module_import_path = entry.get("module_import_path")
            if not isinstance(module_import_path, str) or ":" not in module_import_path:
                continue
            module_name, _, _callable_name = module_import_path.partition(":")
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue
            classifier = getattr(module, "classify_tool_call_shape", None)
            if callable(classifier):
                return classifier, module_import_path
    return _classify_tool_call_shape, "grader_fallback"
    name = tool_call.get("name")
    if name != "raw_bash":
        return "unsupported_tool" if isinstance(name, str) else "malformed_call"
    command = _extract_command(tool_call.get("arguments"))
    return "valid_call" if command is not None else "malformed_call"


def _extract_command(arguments: Any) -> str | None:
    if isinstance(arguments, dict):
        command = arguments.get("command")
        if isinstance(command, str) and command:
            return command
        return None
    if isinstance(arguments, str) and arguments:
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            parsed = {"command": arguments}
        if isinstance(parsed, dict) and isinstance(parsed.get("command"), str) and parsed["command"]:
            return parsed["command"]
    return None


def _tool_results(execution_result: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in execution_result["execution"].get("steps", []):
        for result in step.get("results", []):
            if isinstance(result, dict):
                results.append(result)
    return results


def _tool_commands(execution_result: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for result in _tool_results(execution_result):
        command = result.get("command")
        if isinstance(command, str) and command:
            commands.append(command)
    return commands


def _workspace_target_descriptor_fields(descriptor: Any) -> tuple[str, str]:
    if not isinstance(descriptor, dict):
        return ("", "")
    target_path = descriptor.get("path")
    target_id = descriptor.get("target_id")
    if not isinstance(target_path, str) or not target_path:
        target_path = ""
    if not isinstance(target_id, str) or not target_id:
        target_id = ""
    return (target_path, target_id)


def _workspace_decoy_descriptor_rows(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        decoy_id = item.get("decoy_id")
        decoy_path = item.get("path")
        expected_text = item.get("expected_text")
        if not isinstance(decoy_id, str) or not decoy_id:
            continue
        if not isinstance(decoy_path, str) or not decoy_path:
            continue
        rows.append(
            {
                "decoy_id": decoy_id,
                "path": decoy_path,
                "expected_text": expected_text if isinstance(expected_text, str) else "",
            }
        )
    return rows


def _workspace_step_command_rows(execution_result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, step in enumerate(execution_result.get("execution", {}).get("steps", [])):
        if not isinstance(step, dict):
            continue
        raw_step_index = step.get("step")
        if isinstance(raw_step_index, int) and raw_step_index >= 0:
            step_index = raw_step_index
        else:
            step_index = index
        commands: list[str] = []
        for result in step.get("results", []):
            if not isinstance(result, dict):
                continue
            command = result.get("command")
            if isinstance(command, str) and command:
                commands.append(command)
        rows.append(
            {
                "step_index": step_index,
                "commands": commands,
            }
        )
    rows.sort(key=lambda row: row["step_index"])
    return rows


def _workspace_forced_probe_observed(execution_result: dict[str, Any]) -> bool:
    runtime_probe = execution_result.get("execution", {}).get("runtime_probe")
    if isinstance(runtime_probe, dict):
        if int(runtime_probe.get("planned_call_count", 0) or 0) > 0:
            return True
        if int(runtime_probe.get("executed_call_count", 0) or 0) > 0:
            return True
    for step in execution_result.get("execution", {}).get("steps", []):
        if isinstance(step, dict) and step.get("status") == "forced_runtime_probe":
            return True
    for event in execution_result.get("run_events", []):
        if not isinstance(event, dict):
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        details = payload.get("details")
        if isinstance(details, dict) and bool(details.get("forced_probe")):
            return True
    return False


def _classify_tool_result(result: dict[str, Any]) -> str:
    exit_code = result.get("exit_code")
    text = " ".join(str(result.get(key, "")) for key in ("stderr", "stdout", "error")).lower()
    if "permission" in text or exit_code == 126:
        return "permission_denied"
    if ("error" in result and result.get("error")) or (isinstance(exit_code, int) and exit_code != 0):
        return "runtime_error"
    return "success"


def _lifecycle_tuple_complete(tuple_data: Any) -> bool:
    if not isinstance(tuple_data, dict):
        return False
    bounded_loop = tuple_data.get("bounded_loop")
    terminal_artifact = tuple_data.get("terminal_artifact_state")
    cleanup_state = tuple_data.get("cleanup_state")
    return (
        isinstance(tuple_data.get("expected_terminal_state"), str)
        and isinstance(tuple_data.get("allowed_terminal_states"), list)
        and isinstance(tuple_data.get("terminal_state_flags"), dict)
        and isinstance(bounded_loop, dict)
        and isinstance(terminal_artifact, dict)
        and isinstance(cleanup_state, dict)
        and isinstance(bounded_loop.get("step_bound_max"), int)
        and isinstance(terminal_artifact.get("write_count"), int)
        and isinstance(cleanup_state.get("required"), bool)
        and isinstance(cleanup_state.get("status"), str)
    )


def _lifecycle_tuple_coherent(tuple_data: dict[str, Any]) -> bool:
    expected = tuple_data.get("expected_terminal_state")
    allowed = tuple_data.get("allowed_terminal_states", [])
    flags = tuple_data.get("terminal_state_flags", {})
    bounded_loop = tuple_data.get("bounded_loop", {})
    terminal_artifact = tuple_data.get("terminal_artifact_state", {})
    cleanup_state = tuple_data.get("cleanup_state", {})
    if not isinstance(expected, str) or not expected:
        return False
    if not isinstance(allowed, list) or not allowed or any(not isinstance(state, str) or not state for state in allowed):
        return False
    if expected not in allowed:
        return False
    if not isinstance(flags, dict):
        return False
    if any(state not in flags or not isinstance(flags[state], bool) for state in allowed):
        return False
    if sum(1 for state in allowed if flags.get(state) is True) != 1:
        return False
    if flags.get(expected) is not True:
        return False
    if not isinstance(bounded_loop.get("step_bound_max"), int) or bounded_loop["step_bound_max"] < 1:
        return False
    if terminal_artifact.get("status") == "single_terminal_write" and terminal_artifact.get("write_count") != 1:
        return False
    cleanup_required = cleanup_state.get("required")
    cleanup_status = cleanup_state.get("status")
    if cleanup_required and cleanup_status not in {"completed", "skipped"}:
        return False
    return True


def _cwd_tuple_complete(tuple_data: Any) -> bool:
    if not isinstance(tuple_data, dict):
        return False
    required_keys = (
        "target_cwd",
        "recorded_cwd",
        "recorded_workdir",
        "resolved_target_path",
        "normalized_target_path",
        "path_metadata_complete",
    )
    if any(key not in tuple_data for key in required_keys):
        return False
    return (
        all(isinstance(tuple_data.get(key), str) and tuple_data.get(key) for key in required_keys[:-1])
        and isinstance(tuple_data.get("path_metadata_complete"), bool)
    )


def _cwd_tuple_coherent(tuple_data: dict[str, Any]) -> bool:
    target_cwd = tuple_data.get("target_cwd")
    recorded_cwd = tuple_data.get("recorded_cwd")
    recorded_workdir = tuple_data.get("recorded_workdir")
    resolved_target = tuple_data.get("resolved_target_path")
    normalized_target = tuple_data.get("normalized_target_path")
    if not all(isinstance(value, str) and value for value in (target_cwd, recorded_cwd, recorded_workdir, resolved_target, normalized_target)):
        return False
    if not all(Path(value).is_absolute() for value in (target_cwd, recorded_cwd, recorded_workdir, resolved_target, normalized_target)):
        return False
    if recorded_cwd != recorded_workdir:
        return False
    if _normalize_path(resolved_target) != _normalize_path(normalized_target):
        return False
    return True


def _normalize_path(path_text: str) -> str:
    return str(Path(path_text).resolve())


def _path_within(*, base_path: str, target_path: str) -> bool:
    base = Path(base_path).resolve()
    target = Path(target_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return False
    return True


def _verification_summary(execution_result: dict[str, Any]) -> dict[str, Any]:
    verification = execution_result.get("verification", {})
    if not isinstance(verification, dict):
        return {
            "verified": False,
            "reason_codes": [],
            "substitution_violations": [],
            "layer_statuses": {},
            "summary_complete": False,
        }
    layer_statuses = verification.get("layer_statuses", {})
    normalized_layer_statuses = {
        str(layer_id): str(status)
        for layer_id, status in layer_statuses.items()
        if isinstance(layer_id, str) and isinstance(status, str)
    } if isinstance(layer_statuses, dict) else {}
    summary_complete = (
        isinstance(verification.get("verified"), bool)
        and len(normalized_layer_statuses) >= 4
        and isinstance(verification.get("reason_codes"), list)
        and isinstance(verification.get("substitution_violations"), list)
    )
    return {
        "verified": bool(verification.get("verified", False)),
        "reason_codes": _string_list(verification.get("reason_codes")),
        "substitution_violations": _string_list(verification.get("substitution_violations")),
        "layer_statuses": normalized_layer_statuses,
        "summary_complete": summary_complete,
    }


def _verification_reason_codes_specific(reason_codes: list[str], substitution_violations: list[str]) -> bool:
    specific_prefixes = (
        "required_layer_missing_",
        "non_substitution_violation_",
        "verification_completion_not_claimed",
        "verification_layer_signal_unavailable",
        "layered_acceptance_rejected",
    )
    values = [*reason_codes, *substitution_violations]
    return all(
        isinstance(value, str)
        and (value.startswith(specific_prefixes) or value == "baseline_model_claim_accepted")
        for value in values
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _add_reason(layer: dict[str, Any], reason: str) -> None:
    if reason not in layer["reason_codes"]:
        layer["reason_codes"].append(reason)


def _add_evidence(layer: dict[str, Any], evidence_ref: str) -> None:
    if evidence_ref not in layer["evidence_refs"]:
        layer["evidence_refs"].append(evidence_ref)


def _set_unresolved(aggregate: dict[str, Any], reasons: list[str]) -> None:
    aggregate["final_verdict"] = "unresolved"
    for reason in reasons:
        if reason not in aggregate["carry_forward_warnings"]:
            aggregate["carry_forward_warnings"].append(reason)


def _read_fixture_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _read_fixture_json(path: Path) -> dict[str, Any] | None:
    text = _read_fixture_text(path)
    if not isinstance(text, str):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _relative_fixture_path(value: Any) -> str:
    return value if isinstance(value, str) and value else ""


def _first_write_command_index(commands: list[str], relative_path: str) -> int | None:
    if not relative_path:
        return None
    for index, command in enumerate(commands):
        if _command_is_write_for_path(command, relative_path):
            return index
    return None


def _commands_before_first_write(
    commands: list[str],
    first_write_index: int | None,
    *,
    evidence_path: str,
) -> list[str]:
    if first_write_index is None:
        upper_bound = len(commands)
    else:
        upper_bound = first_write_index
    out: list[str] = []
    for command in commands[:upper_bound]:
        if evidence_path and evidence_path in command:
            out.append(command)
            continue
        if any(token in command for token in ("ls ", "find ", "cat ", "grep ", "rg ")):
            out.append(command)
    return out


def _command_is_write_for_path(command: str, relative_path: str) -> bool:
    if relative_path not in command:
        return False
    write_tokens = (
        f"> {relative_path}",
        f">> {relative_path}",
        f"tee {relative_path}",
        f"cp ",
        f"mv ",
        f"Path('{relative_path}').write_text",
        f'Path("{relative_path}").write_text',
        f"open('{relative_path}', 'w')",
        f'open("{relative_path}", "w")',
        f"open('{relative_path}','w')",
        f'open("{relative_path}","w")',
    )
    return any(token in command for token in write_tokens)


def _path_inspected_before_edit(commands: list[str], relative_path: str) -> bool:
    first_write = _first_write_command_index(commands, relative_path)
    if first_write is None:
        return False
    for command in commands[:first_write]:
        if relative_path not in command:
            continue
        if any(token in command for token in ("cat ", "sed -n", "python3 ")):
            return True
    return False


def _first_command_touching_path(commands: list[str], relative_path: str) -> str | None:
    if not relative_path:
        return None
    for command in commands:
        if relative_path in command:
            return command
    return None


def _first_verifier_execution_command(commands: list[str], relative_path: str) -> tuple[str | None, int | None]:
    if not relative_path:
        return (None, None)
    execute_tokens = (
        f"python {relative_path}",
        f"python3 {relative_path}",
        f"bash {relative_path}",
        f"sh {relative_path}",
        f"./{relative_path}",
    )
    for index, command in enumerate(commands):
        if any(token in command for token in execute_tokens):
            return (command, index)
    for index, command in enumerate(commands):
        if relative_path in command:
            return (command, index)
    return (None, None)


def _assistant_completion_trace(execution_result: dict[str, Any]) -> dict[str, Any]:
    steps = execution_result.get("execution", {}).get("steps", [])
    completion_texts: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        completion = step.get("completion")
        if not isinstance(completion, dict):
            continue
        text = completion.get("text")
        if isinstance(text, str) and text:
            completion_texts.append(text[:400])
    last_completion = execution_result.get("execution", {}).get("last_completion")
    last_text = None
    if isinstance(last_completion, dict):
        text = last_completion.get("text")
        if isinstance(text, str) and text:
            last_text = text[:400]
    return {
        "step_count": len(completion_texts),
        "step_texts": completion_texts[:4],
        "last_text": last_text,
    }


def _fixture_paths_preserved(*, run_dir: Path, relative_paths: list[str]) -> bool:
    for relative_path in relative_paths:
        if not relative_path:
            continue
        if not (run_dir / relative_path).exists():
            return False
    return True


def _expected_file_texts_preserved(
    *,
    run_dir: Path,
    expected_file_texts: Any,
    relative_paths: list[str],
) -> bool:
    if not isinstance(expected_file_texts, dict):
        return False
    for relative_path in relative_paths:
        expected_text = expected_file_texts.get(relative_path)
        if not isinstance(expected_text, str):
            return False
        if _read_fixture_text(run_dir / relative_path) != expected_text:
            return False
    return True

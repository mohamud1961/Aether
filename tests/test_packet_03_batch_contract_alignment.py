import copy
import importlib
import inspect
import json
from pathlib import Path

import pytest

PACKET03_DEFAULT_MODEL_TIER_POLICY = {
    "screening_default": "oauth:gpt-5.4-nano",
    "screening_fallback": "oauth:gpt-5.4-mini",
    "promotion_tier": "gpt-5.3-codex",
}
RECOMMENDATION_GOVERNANCE_VERSION = "packet04a_recommendation_governance.v1"


def _load_contracts_module():
    try:
        return importlib.import_module("runner.experiment_contracts")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "Packet 03 contract module is missing: expected runner.experiment_contracts "
            f"to exist for batch/result alignment tests ({exc})."
        )


def _load_batch_runner_module():
    try:
        return importlib.import_module("runner.eval_batch_runner")
    except ModuleNotFoundError:
        return None


def _resolve_callable(module, candidate_names, *, required=True):
    for name in candidate_names:
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    if required:
        pytest.fail(
            "Missing Packet 03 callable. Expected one of: " + ", ".join(candidate_names)
        )
    return None


def _invoke_single_payload_validator(validator, payload):
    signature = inspect.signature(validator)
    params = list(signature.parameters.values())
    if not params:
        return validator()

    first = params[0]
    if first.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
        if len(params) == 1:
            return validator(payload)

    kwargs = {}
    payload_param_names = {
        "batch_spec",
        "spec",
        "result_record",
        "record",
        "trace_summary",
        "summary",
        "recommendation",
        "recommendation_draft",
        "payload",
        "obj",
        "value",
    }
    for param in params:
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if param.name in payload_param_names:
            kwargs[param.name] = payload
        elif param.default is inspect._empty:
            raise TypeError(
                f"Cannot call {validator.__name__}: required parameter '{param.name}' is unsupported "
                "by this test harness."
            )
    return validator(**kwargs)


def _canonical_batch_spec():
    return {
        "batch_id": "batch-001",
        "packet_stage": "packet_03",
        "eval_family": "af_tool_gateway_argument_result_contract",
        "eval_ids": ["ae_tool_call_shape_argument_contract"],
        "variant_ids": ["sc_b_01"],
        "task_set_id": "packet03_smoke_set",
        "task_tier": "atomic",
        "rerun_count": 3,
        "model_policy": dict(PACKET03_DEFAULT_MODEL_TIER_POLICY),
        "provider_route": "codex_subscription",
        "fixed_invariants": {"grader_version": "grader.v1"},
        "budget_caps": {"tokens": 100000, "usd": 2.0},
        "stability_budget_caps": {"tokens": 50000, "usd": 1.0},
        "output_root": "/tmp/packet03/batch-001",
        "evaluation_lane": "promotion",
        "promotion_authority": True,
        "execution_mode_lock": {
            "ae_tool_call_shape_argument_contract": "one_shot_batchable",
        },
        "eval_card_refs": {
            "ae_tool_call_shape_argument_contract": "tracking/cards/eval_cards.active.jsonl#L1",
        },
    }


def _canonical_result_record():
    return {
        "batch_id": "batch-001",
        "run_id": "run-001",
        "variant_id": "sc_b_01",
        "eval_id": "ae_tool_call_shape_argument_contract",
        "task_id": "task-001",
        "rerun_index": 0,
        "model_route": {
            "model_client_id": "codex_subscription",
            "provider_route": "codex_subscription",
            "adapter_id": "codex_subscription_responses",
            "model_name": "gpt-5.4-nano",
            "auth_mode": "oauth",
            "request_settings": {"temperature": 0, "max_tokens": 256},
            "request_settings_fingerprint": "settings-route-sha-001",
        },
        "effective_settings_id": "settings-sha-001",
        "invariant_fingerprint": "invariants-sha-001",
        "grader_version": "grader.v1",
        "score_summary": {"final_verdict": "pass", "pass": True, "score": 1.0},
        "reason_codes": [],
        "token_and_cost_summary": {"input_tokens": 12, "output_tokens": 5, "usd": 0.001},
        "budget_used": {"tokens": 17, "usd": 0.001},
        "budget_cap": {"tokens": 100000, "usd": 2.0},
        "stability_metrics_summary": {"pass_rate": 1.0, "spread": 0.0},
        "trace_summary_ref": "trace_summaries/run-001.json",
        "failure_cluster": "tool_invocation_error",
        "secondary_failure_tags": [],
        "promotion_flags": {"candidate_action": "hold_for_more_evidence"},
        "execution_mode": "one_shot_batchable",
        "evaluation_lane": "promotion",
        "promotion_authority": True,
        "promotion_blocker_codes": [],
        "promotion_eligibility": "eligible",
        "forced_probe_observed": False,
        "standin_observed": False,
        "legacy_lane_artifact_detected": False,
        "governed_truth_ref": "runs/run-001/run_events.jsonl#event_type=governed_eval_truth_finalized",
        "governed_terminal_status": "not_applicable",
        "run_artifact_refs": {
            "run_header_ref": "runs/run-001/run_header.json",
            "run_events_ref": "runs/run-001/run_events.jsonl",
            "score_envelope_ref": "runs/run-001/score_envelope.json",
        },
    }


def _canonical_trace_summary():
    return {
        "run_id": "run-001",
        "raw_execution_truth": {
            "execution_status": "max_steps_exhausted",
            "step_count": 1,
            "terminal_outcome_status": "max_steps_exhausted",
        },
        "governed_eval_truth": {
            "truth_source": "post_grader",
            "truth_version": "packet05a_governed_eval_truth.v1",
            "final_verdict": "pass",
            "governed_terminal_status": "not_applicable",
        },
        "error_summary": {"status": "none"},
        "loop_pattern_summary": {"pattern": "single_shot"},
        "tool_error_summary": {"status": "none"},
        "workspace_integrity_summary": {"status": "clean"},
        "verifier_final_contradiction_summary": {"status": "none"},
        "token_spike_summary": {"status": "none"},
        "recovery_summary": {"status": "not_applicable"},
        "evaluation_lane": "promotion",
    }


def _canonical_recommendation():
    gate_inputs = {
        "lane_class": "promotion",
        "surface_bounded": False,
        "mechanism_visibility_complete": True,
        "schema_complete_for_promotion": True,
        "helper_only_evidence": False,
        "comparator_variant_id": "sc_b_01",
        "same_batch_comparator_run_ids": [],
        "primary_delta_metric": {
            "metric_name": "pass_rate_delta",
            "candidate_value": None,
            "comparator_value": None,
            "delta": None,
            "threshold": 0.0,
            "direction": "higher_is_better",
        },
        "corroboration_surface_ids": [],
        "audit_status_aa": "missing",
        "audit_status_ab": "missing",
        "audit_artifact_ref_aa": None,
        "audit_artifact_ref_ab": None,
        "forced_probe_observed": False,
        "standin_observed": False,
        "variant_card_ref": None,
        "route_manifest_ref": None,
        "route_manifest_fingerprint": None,
        "claimed_surface_fingerprints": {},
        "unchanged_surface_fingerprints": {},
        "governed_truth_ref": "runs/run-001/run_events.jsonl#event_type=governed_eval_truth_finalized",
        "governed_terminal_status": "not_applicable",
    }
    gate_results = {
        "G1": {"passed": False, "reason": "missing_same_batch_comparator_delta"},
        "G2": {"passed": True, "reason": "ok"},
        "G3": {"passed": False, "reason": "rerun_minimum_not_met"},
        "G4": {"passed": False, "reason": "missing_sibling_surface_corroboration_delta"},
        "G5": {"passed": False, "reason": "missing_corroboration_for_non_bounded_check"},
        "G6": {"passed": True, "reason": "ok"},
        "G7": {"passed": False, "reason": "audit_status_aa_missing"},
        "G8": {"passed": False, "reason": "audit_status_ab_missing"},
        "G9": {"passed": True, "reason": "ok"},
        "G10": {"passed": True, "reason": "ok"},
        "G11": {"passed": True, "reason": "ok"},
        "G12": {"passed": True, "reason": "ok"},
        "G13": {"passed": True, "reason": "ok"},
        "G14": {"passed": False, "reason": "provenance_chain_incomplete"},
        "G15": {"passed": True, "reason": "ok"},
    }
    return {
        "batch_id": "batch-001",
        "recommendation_governance_version": RECOMMENDATION_GOVERNANCE_VERSION,
        "candidate_actions": [
            {
                "variant_id": "sc_b_01",
                "proposed_status": "hold_for_more_evidence",
                "rationale": "No regression, but insufficient transfer evidence.",
                "evidence_refs": ["runs/run-001/score_envelope.json"],
                "regression_risks": ["none"],
                "token_cost_delta": {"delta_tokens": 0, "delta_usd": 0.0},
                "complexity_delta": {"delta_loc": 0, "delta_blocks": 0},
                "next_eval_or_transfer_step": "collect_more_promotion_evidence",
                "recommendation_gate_inputs": gate_inputs,
                "recommendation_gate_results": gate_results,
            }
        ],
        "human_gate_required": True,
    }


def _resolve_artifact_linkage_checker():
    contract_module = _load_contracts_module()
    batch_module = _load_batch_runner_module()
    candidate_names = (
        "validate_result_artifact_linkage",
        "validate_artifact_linkage",
        "validate_result_record_artifacts",
        "resolve_artifact_linkage",
        "check_artifact_linkage",
    )
    checker = _resolve_callable(contract_module, candidate_names, required=False)
    if checker is not None:
        return checker
    if batch_module is not None:
        checker = _resolve_callable(batch_module, candidate_names, required=False)
        if checker is not None:
            return checker
    pytest.fail(
        "Missing Packet 03 artifact-linkage checker. Expected one of: "
        + ", ".join(candidate_names)
    )


def _invoke_artifact_checker(checker, *, result_record, trace_summaries, output_root):
    signature = inspect.signature(checker)
    kwargs = {}
    for param in signature.parameters.values():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if param.name in ("result_record", "record", "result"):
            kwargs[param.name] = result_record
        elif param.name in ("result_records", "records"):
            kwargs[param.name] = [result_record]
        elif param.name in ("trace_summaries", "trace_summary_records", "summaries"):
            kwargs[param.name] = trace_summaries
        elif param.name in ("trace_summary_index", "summary_index"):
            kwargs[param.name] = {item["run_id"]: item for item in trace_summaries}
        elif param.name in ("output_root", "batch_root", "artifacts_root", "root"):
            kwargs[param.name] = str(output_root)
        elif param.default is inspect._empty:
            raise TypeError(
                f"Cannot call {checker.__name__}: required parameter '{param.name}' "
                "is unsupported by this test harness."
            )
    if kwargs:
        return checker(**kwargs)
    return checker(result_record)


def _assert_rejected_or_flagged(callable_fn, payload):
    try:
        result = _invoke_single_payload_validator(callable_fn, payload)
    except Exception:
        return
    rendered = json.dumps(result, sort_keys=True) if isinstance(result, (dict, list)) else str(result)
    lane_flag_tokens = (
        "mixed_lane",
        "lane_mismatch",
        "lane_violation",
        "mixed_lane_misuse",
        "guardrail_debug cannot be promotion eligible",
        "promotion cannot include blocker-like markers",
        "guardrail_debug_non_promotable",
        "lane_policy_restriction",
    )
    assert any(token in rendered for token in lane_flag_tokens), (
        "Mixed-lane misuse must be rejected or explicitly flagged in validator output."
    )


@pytest.mark.parametrize(
    "missing_field",
    [
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
    ],
)
def test_batch_spec_missing_required_field_is_rejected(missing_field):
    contracts = _load_contracts_module()
    validate_batch_spec = _resolve_callable(
        contracts,
        ("validate_batch_spec", "validate_experiment_batch_spec"),
    )
    broken = _canonical_batch_spec()
    broken.pop(missing_field)
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_batch_spec, broken)


@pytest.mark.parametrize(
    "missing_field",
    [
        "effective_settings_id",
        "invariant_fingerprint",
        "grader_version",
        "budget_used",
        "budget_cap",
        "stability_metrics_summary",
        "execution_mode",
    ],
)
def test_result_record_comparability_field_is_required(missing_field):
    contracts = _load_contracts_module()
    validate_result_record = _resolve_callable(
        contracts,
        ("validate_result_record", "validate_batch_result_record"),
    )
    broken = _canonical_result_record()
    broken.pop(missing_field)

    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_result_record, broken)


def test_result_record_missing_trace_or_artifact_refs_is_rejected():
    contracts = _load_contracts_module()
    validate_result_record = _resolve_callable(
        contracts,
        ("validate_result_record", "validate_batch_result_record"),
    )
    missing_trace = _canonical_result_record()
    missing_trace.pop("trace_summary_ref")
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_result_record, missing_trace)

    missing_artifact_ref = _canonical_result_record()
    missing_artifact_ref["run_artifact_refs"].pop("score_envelope_ref")
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_result_record, missing_artifact_ref)


def test_recommendation_requires_human_gate_required_true():
    contracts = _load_contracts_module()
    validate_recommendation = _resolve_callable(
        contracts,
        ("validate_recommendation_draft", "validate_recommendation"),
    )
    valid = _canonical_recommendation()
    _invoke_single_payload_validator(validate_recommendation, valid)

    invalid = copy.deepcopy(valid)
    invalid["human_gate_required"] = False
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_recommendation, invalid)


def test_recommendation_cannot_imply_promotion_state_mutation():
    contracts = _load_contracts_module()
    validate_recommendation = _resolve_callable(
        contracts,
        ("validate_recommendation_draft", "validate_recommendation"),
    )
    invalid = _canonical_recommendation()
    invalid["mutate_promotion_state"] = True

    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_recommendation, invalid)


def test_evaluation_lane_is_required_on_result_record():
    contracts = _load_contracts_module()
    validate_result_record = _resolve_callable(
        contracts,
        ("validate_result_record", "validate_batch_result_record"),
    )
    valid = _canonical_result_record()
    _invoke_single_payload_validator(validate_result_record, valid)

    missing_lane = _canonical_result_record()
    missing_lane.pop("evaluation_lane")
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_result_record, missing_lane)


def test_mixed_lane_misuse_is_rejected_or_flagged():
    contracts = _load_contracts_module()
    validate_result_record = _resolve_callable(
        contracts,
        ("validate_result_record", "validate_batch_result_record"),
    )
    mixed_lane = _canonical_result_record()
    mixed_lane["evaluation_lane"] = "guardrail_debug"
    mixed_lane["promotion_authority"] = False
    mixed_lane["promotion_eligibility"] = "eligible"
    mixed_lane["promotion_blocker_codes"] = ["guardrail_debug_non_promotable"]
    _assert_rejected_or_flagged(validate_result_record, mixed_lane)


def test_promotion_lane_schema_incomplete_record_is_allowed_only_as_blocked():
    contracts = _load_contracts_module()
    validate_result_record = _resolve_callable(
        contracts,
        ("validate_result_record", "validate_batch_result_record"),
    )
    blocked = _canonical_result_record()
    blocked["promotion_blocker_codes"] = ["schema_missing_required_fields", "mechanism_visibility_incomplete"]
    blocked["promotion_eligibility"] = "blocked_schema_missing_required_fields"
    _invoke_single_payload_validator(validate_result_record, blocked)


def test_promotion_lane_failing_verdict_cannot_be_marked_eligible():
    contracts = _load_contracts_module()
    validate_result_record = _resolve_callable(
        contracts,
        ("validate_result_record", "validate_batch_result_record"),
    )
    invalid = _canonical_result_record()
    invalid["score_summary"]["final_verdict"] = "fail"
    invalid["promotion_blocker_codes"] = []
    invalid["promotion_eligibility"] = "eligible"
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_result_record, invalid)


def test_tool_call_trace_summary_requires_case_level_schema_when_marked_visible():
    contracts = _load_contracts_module()
    validate_trace_summary = _resolve_callable(
        contracts,
        ("validate_trace_summary", "validate_batch_trace_summary"),
    )
    invalid = _canonical_trace_summary()
    invalid["eval_id"] = "ae_tool_call_contract_quality_v2"
    invalid["governed_eval_truth"] = {
        "truth_source": "post_grader",
        "truth_version": "packet05a_governed_eval_truth.v1",
        "final_verdict": "pass",
        "governed_terminal_status": "tool_eval_completed",
        "completion_scope": "case_coverage_only",
        "authority_completeness": "complete",
        "authority_incomplete_reasons": [],
    }
    invalid["packet03_eval_summary"] = {
        "mechanism_visibility_complete": True,
        "schema_complete_for_promotion": True,
    }
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_trace_summary, invalid)


def test_workspace_target_decoy_trace_requires_explicit_linkage_schema_when_marked_visible():
    contracts = _load_contracts_module()
    validate_trace_summary = _resolve_callable(
        contracts,
        ("validate_trace_summary", "validate_batch_trace_summary"),
    )
    invalid = _canonical_trace_summary()
    invalid["eval_id"] = "ae_workspace_target_decoy_generalization_v2"
    invalid["packet03_eval_summary"] = {
        "mechanism_visibility_complete": True,
        "schema_complete_for_promotion": True,
    }
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_trace_summary, invalid)


def test_workspace_target_multistep_trace_requires_turn_contract_schema_when_marked_visible():
    contracts = _load_contracts_module()
    validate_trace_summary = _resolve_callable(
        contracts,
        ("validate_trace_summary", "validate_batch_trace_summary"),
    )
    invalid = _canonical_trace_summary()
    invalid["eval_id"] = "ae_workspace_target_decoy_generalization_multistep_v1"
    invalid["packet03_eval_summary"] = {
        "mechanism_visibility_complete": True,
        "schema_complete_for_promotion": True,
        "workspace_target_target_id": "target_alpha_primary",
        "workspace_target_target_path": "workspace/dev_transfer_alpha/target/answer.txt",
        "workspace_target_decoy_ids": ["decoy_alpha_neighbor", "decoy_alpha_shadow"],
        "workspace_target_decoy_paths": [
            "workspace/dev_transfer_alpha/decoy/answer.txt",
            "workspace/dev_transfer_alpha/target/answer_shadow.txt",
        ],
        "workspace_target_regime_id": "decoy_rotation_alpha",
        "workspace_target_regime_rotation_index": 0,
        "workspace_target_regime_count": 2,
        "workspace_target_transfer_tier": "development_transfer",
        "workspace_target_hit": True,
        "workspace_decoy_touched": False,
        "workspace_target_content_ok": True,
        "workspace_decoys_preserved": True,
        "workspace_target_target_touch_evidence": ["printf 'x' > workspace/dev_transfer_alpha/target/answer.txt"],
        "workspace_target_decoy_touch_evidence": [],
        "workspace_target_trace_linkage_complete": True,
        "workspace_target_forced_probe_observed": False,
    }
    with pytest.raises(Exception):
        _invoke_single_payload_validator(validate_trace_summary, invalid)


def test_artifact_linkage_resolves_valid_refs(tmp_path):
    checker = _resolve_artifact_linkage_checker()

    run_dir = Path(tmp_path) / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_header.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "run_events.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "score_envelope.json").write_text("{}\n", encoding="utf-8")
    trace_dir = Path(tmp_path) / "trace_summaries"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_ref = trace_dir / "run-001.json"
    trace_ref.write_text("{}\n", encoding="utf-8")

    record = _canonical_result_record()
    record["run_artifact_refs"] = {
        "run_header_ref": str(run_dir / "run_header.json"),
        "run_events_ref": str(run_dir / "run_events.jsonl"),
        "score_envelope_ref": str(run_dir / "score_envelope.json"),
    }
    record["trace_summary_ref"] = str(trace_ref)
    trace_summary = _canonical_trace_summary()
    trace_summary["run_id"] = "run-001"

    _invoke_artifact_checker(
        checker,
        result_record=record,
        trace_summaries=[trace_summary],
        output_root=tmp_path,
    )


def test_artifact_linkage_rejects_missing_refs(tmp_path):
    checker = _resolve_artifact_linkage_checker()

    record = _canonical_result_record()
    record["run_artifact_refs"] = {
        "run_header_ref": str(Path(tmp_path) / "runs" / "run-001" / "run_header.json"),
        "run_events_ref": str(Path(tmp_path) / "runs" / "run-001" / "run_events.jsonl"),
        "score_envelope_ref": str(Path(tmp_path) / "runs" / "run-001" / "score_envelope.json"),
    }
    record["trace_summary_ref"] = str(Path(tmp_path) / "trace_summaries" / "run-001.json")

    trace_summary = _canonical_trace_summary()
    trace_summary["run_id"] = "run-001"

    with pytest.raises(Exception):
        _invoke_artifact_checker(
            checker,
            result_record=record,
            trace_summaries=[trace_summary],
            output_root=tmp_path,
        )


def test_artifact_linkage_rejects_trace_run_id_marker_mismatch(tmp_path):
    checker = _resolve_artifact_linkage_checker()
    run_dir = Path(tmp_path) / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_header.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "run_events.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "score_envelope.json").write_text("{}\n", encoding="utf-8")
    trace_path = Path(tmp_path) / "trace_summaries.jsonl"
    trace_path.write_text(json.dumps(_canonical_trace_summary()) + "\n", encoding="utf-8")

    record = _canonical_result_record()
    record["trace_summary_ref"] = f"{trace_path}#run_id=run-002"
    record["run_artifact_refs"] = {
        "run_header_ref": str(run_dir / "run_header.json"),
        "run_events_ref": str(run_dir / "run_events.jsonl"),
        "score_envelope_ref": str(run_dir / "score_envelope.json"),
    }

    with pytest.raises(Exception):
        _invoke_artifact_checker(
            checker,
            result_record=record,
            trace_summaries=[_canonical_trace_summary()],
            output_root=tmp_path,
        )

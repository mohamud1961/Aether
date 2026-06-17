import json
from pathlib import Path

import pytest

from runner.eval_batch_runner import (
    _build_recommendation_draft,
    _derive_lane_state,
    _resolve_packet04_route_scope,
    run_batch,
)
from runner.experiment_contracts import validate_result_artifact_linkage
from runner.model_client import LocalStubModelClient
from runner.packet03_eval_fixtures import materialize_packet03_eval_fixture
from runner.packet04_route_manifest import (
    ALLOWED_PACKET04_VARIANTS,
    BASELINE_VARIANT_ID,
    PACKET04_SLICE2_ROUTE_SCOPE,
    PACKET05A_TOOL_CALL_ALLOWED_VARIANTS,
    PACKET05A_TOOL_CALL_SCOPE,
    PACKET05A_TOOL_CALL_VARIANTS,
    PACKET05A_TOOL_RESULT_ALLOWED_VARIANTS,
    PACKET05A_SYNC_INTERRUPT_ALLOWED_VARIANTS,
    PACKET05A_SYNC_INTERRUPT_SCOPE,
    PACKET05A_SYNC_INTERRUPT_VARIANTS,
    PACKET05A_TOOL_RESULT_SCOPE,
    PACKET05A_TOOL_RESULT_VARIANTS,
    PACKET05A_WORKSPACE_TARGET_ALLOWED_VARIANTS,
    PACKET05A_WORKSPACE_TARGET_MULTISTEP_ALLOWED_VARIANTS,
    PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE,
    PACKET05A_WORKSPACE_TARGET_MULTISTEP_VARIANTS,
    PACKET05A_WORKSPACE_TARGET_SCOPE,
    PACKET05A_WORKSPACE_TARGET_VARIANTS,
    PACKET06_PD01_ALLOWED_VARIANTS,
    PACKET06_PD01_SCOPE,
    PACKET06_PD01_VARIANTS,
    RERUN_IN_SCOPE_VARIANTS,
    SLICE2_ALLOWED_PACKET04_VARIANTS,
    SLICE2_RERUN_IN_SCOPE_VARIANTS,
    build_packet04_route_manifest,
    load_runtime_callables,
)
from runner.schemas import SchemaValidationError, validate_evaluation_lane

PACKET03_ACTIVE_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)
PRIMARY_EVAL_ID = "ae_completion_layer_contract_guard"
SIBLING_EVAL_ID = "ae_tool_result_normalization_permission_probe"
PROMOTION_CANDIDATE_ID = "v04_vc_01_layered_non_substitution_reason_codes"
EXECUTION_CANDIDATE_ID = "v04_ex_01_single_terminal_outcome_cleanup_order_guard"
SLICE2_EXECUTION_CANDIDATE_ID = "v04_ex_02_cwd_workdir_invariant_propagation_guard"
SLICE2_TOOL_CANDIDATE_ID = "v04_tb_01_tool_call_contract_classifier"
TOOL_RESULT_CANDIDATE_ID = "v04_tb_02_permission_runtime_attribution_split"
SYNC_INTERRUPT_CANDIDATE_ID = "v04_rb_01_interrupt_retry_spiral_breaker"
WORKSPACE_TARGET_CANDIDATE_ID = "v04_cb_01_decoy_resistant_target_selection"
PD01_PROMPT_PLAN_ENV_CANDIDATE_ID = "prompt_plan_env"
PD01_EVIDENCE_REPORT_CANDIDATE_ID = "evidence_report_scaffold"


def _load_active_eval_cards() -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for line in PACKET03_ACTIVE_CARDS_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        cards[row["eval_id"]] = row
    return cards


def _synthetic_record(
    *,
    variant_id: str,
    eval_id: str,
    run_id: str,
    rerun_index: int,
    verdict: str,
    lane_class: str,
    surface_bounded: bool,
    audit_status: str,
    mechanism_visibility_complete: bool = True,
    schema_complete_for_promotion: bool = True,
    helper_only_evidence: bool = False,
) -> dict:
    return {
        "variant_id": variant_id,
        "eval_id": eval_id,
        "run_id": run_id,
        "rerun_index": rerun_index,
        "score_summary": {"final_verdict": verdict},
        "budget_used": {"estimated_tokens": 10, "usd": 0.01},
        "effective_settings_id": "settings-sha-001",
        "invariant_fingerprint": "invariants-sha-001",
        "grader_version": "grader.v1",
        "execution_mode": "deterministic_no_model",
        "governed_truth_ref": f"runs/{run_id}/run_events.jsonl#event_type=governed_eval_truth_finalized",
        "governed_terminal_status": "tool_eval_completed",
        "variant_card_ref": "tracking/.../variant_cards.md#variant",
        "route_manifest_ref": f"runs/{run_id}/route_manifest.json",
        "route_manifest_fingerprint": "f" * 64,
        "claimed_surface_fingerprints": {
            "surface.claimed": {"file_sha256": "a" * 64, "real_file_path": "/tmp/claimed.py"}
        },
        "unchanged_surface_fingerprints": {
            "surface.unchanged": {"file_sha256": "b" * 64, "real_file_path": "/tmp/unchanged.py"}
        },
        "recommendation_gate_inputs": {
            "lane_class": lane_class,
            "surface_bounded": surface_bounded,
            "mechanism_visibility_complete": mechanism_visibility_complete,
            "schema_complete_for_promotion": schema_complete_for_promotion,
            "helper_only_evidence": helper_only_evidence,
            "comparator_variant_id": BASELINE_VARIANT_ID,
            "same_batch_comparator_run_ids": [],
            "primary_delta_metric": None,
            "corroboration_surface_ids": [],
            "audit_status_aa": audit_status,
            "audit_status_ab": audit_status,
            "forced_probe_observed": False,
            "standin_observed": False,
            "variant_card_ref": "tracking/.../variant_cards.md#variant",
            "route_manifest_ref": f"runs/{run_id}/route_manifest.json",
            "route_manifest_fingerprint": "f" * 64,
            "claimed_surface_fingerprints": {
                "surface.claimed": {"file_sha256": "a" * 64, "real_file_path": "/tmp/claimed.py"}
            },
            "unchanged_surface_fingerprints": {
                "surface.unchanged": {"file_sha256": "b" * 64, "real_file_path": "/tmp/unchanged.py"}
            },
            "governed_truth_ref": f"runs/{run_id}/run_events.jsonl#event_type=governed_eval_truth_finalized",
            "governed_terminal_status": "tool_eval_completed",
        },
    }


def _verification_v2_eval_card() -> dict:
    return {
        "eval_id": "ae_verification_reason_code_quality_v2",
        "family_id": "af_completion_verification_layering",
        "block_family": "VerificationBlock",
        "mechanism_claim": "Require exact verification reason-code and substitution-violation quality under non-substitution pressure.",
        "target_failure": "completion_false_positive",
        "fixed_invariants": {
            "provider_route": "none",
            "settings_fingerprint": "deterministic_verification_quality_v2",
            "grader_version": "p05a_verification_reason_code_quality_grader_v2",
            "fixture_version": "p05a_verification_reason_code_quality_v2",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "deterministic_no_model",
        "batch_eligibility": True,
        "evaluation_lane": "promotion",
        "model_tier_policy": {
            "screening_default": "no_model",
            "screening_fallback": "not_applicable",
            "promotion_tier": "not_applicable",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _lifecycle_v2_eval_card() -> dict:
    return {
        "eval_id": "ae_lifecycle_adversarial_terminality_v2",
        "family_id": "af_execution_lifecycle_integrity",
        "block_family": "ExecutionBlock",
        "mechanism_claim": "Require explicit lifecycle anomaly detection under adversarial terminality and cleanup pressure.",
        "target_failure": "process_lifecycle_and_cancellation_boundary_failure",
        "fixed_invariants": {
            "provider_route": "none",
            "settings_fingerprint": "deterministic_lifecycle_adversarial_v2",
            "grader_version": "p05a_lifecycle_adversarial_terminality_grader_v2",
            "fixture_version": "p05a_lifecycle_adversarial_terminality_v2",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "deterministic_no_model",
        "batch_eligibility": True,
        "evaluation_lane": "promotion",
        "model_tier_policy": {
            "screening_default": "no_model",
            "screening_fallback": "not_applicable",
            "promotion_tier": "not_applicable",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _tool_result_v2_eval_card() -> dict:
    return {
        "eval_id": "ae_tool_result_attribution_quality_v2",
        "family_id": "af_tool_gateway_argument_result_contract",
        "block_family": "ToolBlock",
        "mechanism_claim": "Require exact permission-vs-runtime attribution on live deny/runtime/mixed signal cases.",
        "target_failure": "permission_policy_runtime_mismatch",
        "fixed_invariants": {
            "provider_route": "none",
            "settings_fingerprint": "deterministic_tool_result_attribution_v2",
            "grader_version": "p05a_tool_result_attribution_grader_v2",
            "fixture_version": "p05a_tool_result_attribution_v2",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "deterministic_no_model",
        "batch_eligibility": True,
        "evaluation_lane": "promotion",
        "model_tier_policy": {
            "screening_default": "no_model",
            "screening_fallback": "not_applicable",
            "promotion_tier": "not_applicable",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _tool_call_v2_eval_card() -> dict:
    return {
        "eval_id": "ae_tool_call_contract_quality_v2",
        "family_id": "af_tool_gateway_argument_result_contract",
        "block_family": "ToolBlock",
        "mechanism_claim": "Require exact tool-call contract classification on live valid/malformed/unsupported cases.",
        "target_failure": "tool_invocation_error",
        "fixed_invariants": {
            "provider_route": "none",
            "settings_fingerprint": "deterministic_tool_call_contract_v2",
            "grader_version": "p05a_tool_call_contract_quality_grader_v2",
            "fixture_version": "p05a_tool_call_contract_quality_v2",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "deterministic_no_model",
        "batch_eligibility": True,
        "evaluation_lane": "promotion",
        "model_tier_policy": {
            "screening_default": "no_model",
            "screening_fallback": "not_applicable",
            "promotion_tier": "not_applicable",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _workspace_target_decoy_generalization_v2_eval_card() -> dict:
    return {
        "eval_id": "ae_workspace_target_decoy_generalization_v2",
        "family_id": "af_workspace_path_target_integrity",
        "block_family": "ContextBlock",
        "mechanism_claim": "Require explicit target/decoy evidence under rotated decoy regimes with development-transfer framing.",
        "target_failure": "workspace_target_miss",
        "fixed_invariants": {
            "provider_route": "oauth",
            "model_route_for_screening": "oauth:gpt-5.4-nano",
            "settings_fingerprint": "p05a_workspace_target_decoy_generalization_v2",
            "grader_version": "p05a_workspace_target_decoy_generalization_grader_v2",
            "fixture_version": "p05a_workspace_target_decoy_generalization_v2",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "one_shot_batchable",
        "batch_eligibility": True,
        "evaluation_lane": "guardrail_debug",
        "model_tier_policy": {
            "screening_default": "oauth:gpt-5.4-nano",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def _workspace_target_decoy_multistep_v1_eval_card() -> dict:
    return {
        "eval_id": "ae_workspace_target_decoy_generalization_multistep_v1",
        "family_id": "af_workspace_path_target_integrity",
        "block_family": "ContextBlock",
        "mechanism_claim": "Require honest multistep target-vs-decoy grounding with first-turn observation and post-observation edit evidence.",
        "target_failure": "workspace_target_miss",
        "fixed_invariants": {
            "provider_route": "oauth",
            "model_route_for_screening": "oauth:gpt-5.4-nano",
            "settings_fingerprint": "p05a_workspace_target_multistep_v1",
            "grader_version": "p05a_workspace_target_multistep_grader_v1",
            "fixture_version": "p05a_workspace_target_multistep_v1",
            "comparator_variant_id": "reference_baseline_packet_02",
        },
        "execution_mode": "multistep_batchable",
        "multistep_turn_budget": 3,
        "batch_eligibility": True,
        "evaluation_lane": "guardrail_debug",
        "model_tier_policy": {
            "screening_default": "oauth:gpt-5.4-nano",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "score_layer_expectations": {
            "l0_inline_assertion": "required",
            "l1_verifier_artifact": "required",
            "l2_replay_or_state_grader": "required",
            "l3_llm_judge": "not_applicable",
            "l4_final_acceptance_reward": "required",
            "non_substitution_rule": "required",
        },
        "human_gate_required": True,
    }


def test_packet04a_first_honest_rerun_scope_is_locked():
    expected_scope = {
        BASELINE_VARIANT_ID,
        PROMOTION_CANDIDATE_ID,
        EXECUTION_CANDIDATE_ID,
    }
    assert set(ALLOWED_PACKET04_VARIANTS) == expected_scope
    assert set(RERUN_IN_SCOPE_VARIANTS) == {
        PROMOTION_CANDIDATE_ID,
        EXECUTION_CANDIDATE_ID,
    }

    for variant_id in sorted(expected_scope):
        manifest = build_packet04_route_manifest(variant_id)
        assert manifest["variant_id"] == variant_id
        assert manifest["route_manifest_fingerprint"]

    with pytest.raises(ValueError):
        build_packet04_route_manifest("v04_tb_02_permission_runtime_attribution_split")


def test_packet04_slice2_scope_is_explicit_and_separate_from_first_honest_rerun():
    assert set(SLICE2_ALLOWED_PACKET04_VARIANTS) == {
        BASELINE_VARIANT_ID,
        SLICE2_EXECUTION_CANDIDATE_ID,
        SLICE2_TOOL_CANDIDATE_ID,
    }
    assert set(SLICE2_RERUN_IN_SCOPE_VARIANTS) == {
        SLICE2_EXECUTION_CANDIDATE_ID,
        SLICE2_TOOL_CANDIDATE_ID,
    }

    ex_manifest = build_packet04_route_manifest(
        SLICE2_EXECUTION_CANDIDATE_ID,
        scope=PACKET04_SLICE2_ROUTE_SCOPE,
    )
    tb_manifest = build_packet04_route_manifest(
        SLICE2_TOOL_CANDIDATE_ID,
        scope=PACKET04_SLICE2_ROUTE_SCOPE,
    )

    assert ex_manifest["route_scope"] == PACKET04_SLICE2_ROUTE_SCOPE
    assert tb_manifest["route_scope"] == PACKET04_SLICE2_ROUTE_SCOPE
    assert any(
        entry["claimed_changed_surface"] and entry["real_file_path"].endswith("blocks/execution/cwd_invariant_loop.py")
        for entry in ex_manifest["routed_modules"]
    )
    assert any(
        entry["claimed_changed_surface"] and entry["real_file_path"].endswith("blocks/tools/contract_classifier.py")
        for entry in tb_manifest["routed_modules"]
    )

    with pytest.raises(ValueError, match="scope=packet04a_first_slice"):
        build_packet04_route_manifest(SLICE2_EXECUTION_CANDIDATE_ID)


def test_packet05a_tool_result_scope_is_explicit_and_separate():
    assert set(PACKET05A_TOOL_RESULT_ALLOWED_VARIANTS) == {
        BASELINE_VARIANT_ID,
        TOOL_RESULT_CANDIDATE_ID,
    }
    assert set(PACKET05A_TOOL_RESULT_VARIANTS) == {TOOL_RESULT_CANDIDATE_ID}

    manifest = build_packet04_route_manifest(
        TOOL_RESULT_CANDIDATE_ID,
        scope=PACKET05A_TOOL_RESULT_SCOPE,
    )
    assert manifest["route_scope"] == PACKET05A_TOOL_RESULT_SCOPE
    assert any(
        entry["claimed_changed_surface"] and entry["real_file_path"].endswith("blocks/tools/result_normalizer.py")
        for entry in manifest["routed_modules"]
    )

    with pytest.raises(ValueError, match="scope=packet04_slice2"):
        build_packet04_route_manifest(PROMOTION_CANDIDATE_ID, scope=PACKET04_SLICE2_ROUTE_SCOPE)


def test_packet05a_sync_interrupt_scope_is_explicit_and_narrow():
    assert set(PACKET05A_SYNC_INTERRUPT_ALLOWED_VARIANTS) == {
        BASELINE_VARIANT_ID,
        SYNC_INTERRUPT_CANDIDATE_ID,
    }
    assert set(PACKET05A_SYNC_INTERRUPT_VARIANTS) == {SYNC_INTERRUPT_CANDIDATE_ID}

    baseline_manifest = build_packet04_route_manifest(
        BASELINE_VARIANT_ID,
        scope=PACKET05A_SYNC_INTERRUPT_SCOPE,
    )
    candidate_manifest = build_packet04_route_manifest(
        SYNC_INTERRUPT_CANDIDATE_ID,
        scope=PACKET05A_SYNC_INTERRUPT_SCOPE,
    )
    assert candidate_manifest["route_scope"] == PACKET05A_SYNC_INTERRUPT_SCOPE

    baseline_by_key = {entry["runtime_key"]: entry for entry in baseline_manifest["routed_modules"]}
    candidate_by_key = {entry["runtime_key"]: entry for entry in candidate_manifest["routed_modules"]}

    baseline_terminal_guard = baseline_by_key["terminal_guard"]
    candidate_terminal_guard = candidate_by_key["terminal_guard"]
    assert baseline_terminal_guard["module_import_path"] == "runner.packet04_route_manifest:baseline_terminal_outcome_guard"
    assert candidate_terminal_guard["module_import_path"] == "runner.agent:_apply_terminal_outcome_cleanup_order_guard"
    assert candidate_terminal_guard["real_file_path"].endswith("runner/agent.py")
    assert candidate_terminal_guard["claimed_changed_surface"] is True
    assert candidate_terminal_guard["file_sha256"] != baseline_terminal_guard["file_sha256"]

    for runtime_key in ("orientation", "tools_getter", "tool_executor", "execution", "context", "verification", "recovery"):
        baseline_entry = baseline_by_key[runtime_key]
        candidate_entry = candidate_by_key[runtime_key]
        assert candidate_entry["claimed_changed_surface"] is False
        assert candidate_entry["module_import_path"] == baseline_entry["module_import_path"]
        assert candidate_entry["file_sha256"] == baseline_entry["file_sha256"]

    with pytest.raises(ValueError, match="scope=packet04a_first_slice"):
        build_packet04_route_manifest(SYNC_INTERRUPT_CANDIDATE_ID)
    with pytest.raises(ValueError, match=f"scope={PACKET05A_SYNC_INTERRUPT_SCOPE}"):
        build_packet04_route_manifest(EXECUTION_CANDIDATE_ID, scope=PACKET05A_SYNC_INTERRUPT_SCOPE)


def test_packet05a_sync_interrupt_comparative_batch_is_admitted_and_remains_bounded(tmp_path):
    cards = _load_active_eval_cards()
    eval_id = "ae_sync_interrupt_cleanup_probe"
    batch_spec = {
        "batch_id": "packet05a-sync-interrupt-comparative-local",
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET05A_SYNC_INTERRUPT_SCOPE,
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID, SYNC_INTERRUPT_CANDIDATE_ID],
        "task_set_id": "packet05a-sync-interrupt-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 4, "tokens": 12000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 4, "tokens": 12000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "bounded_diagnostic",
        "execution_mode_lock": {eval_id: "sync_interactive"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "sync-interrupt-001", "task_prompt": "packet05a sync interrupt bounded comparative"}],
    }

    result = run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: cards[eval_id]},
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )

    assert result["run_count"] == 4
    normalized_batch_spec = json.loads(Path(result["batch_spec_path"]).read_text(encoding="utf-8"))
    assert normalized_batch_spec["packet04_route_scope"] == PACKET05A_SYNC_INTERRUPT_SCOPE

    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 4
    assert {row["variant_id"] for row in rows} == {BASELINE_VARIANT_ID, SYNC_INTERRUPT_CANDIDATE_ID}
    assert all(row["evaluation_lane"] == "bounded_diagnostic" for row in rows)
    assert all(row["promotion_eligibility"] == "blocked_bounded_diagnostic_lane" for row in rows)
    assert all("bounded_diagnostic_non_promotable" in row["promotion_blocker_codes"] for row in rows)
    assert all("bounded_l3_dependency" in row["promotion_blocker_codes"] for row in rows)

    baseline_rows = [row for row in rows if row["variant_id"] == BASELINE_VARIANT_ID]
    candidate_rows = [row for row in rows if row["variant_id"] == SYNC_INTERRUPT_CANDIDATE_ID]
    assert len(baseline_rows) == 2
    assert len(candidate_rows) == 2
    assert all("runner.agent.terminal_outcome_guard" in row["claimed_surface_fingerprints"] for row in candidate_rows)
    assert all("runner.agent.terminal_outcome_guard" not in row["claimed_surface_fingerprints"] for row in baseline_rows)

    recommendation = json.loads(Path(result["recommendations_path"]).read_text(encoding="utf-8"))
    by_variant = {action["variant_id"]: action for action in recommendation["candidate_actions"]}
    assert recommendation["human_gate_required"] is True
    assert by_variant[BASELINE_VARIANT_ID]["proposed_status"] == "bound"
    assert by_variant[SYNC_INTERRUPT_CANDIDATE_ID]["proposed_status"] == "bound"


def test_packet05a_tool_call_scope_is_explicit_and_separate():
    assert set(PACKET05A_TOOL_CALL_ALLOWED_VARIANTS) == {
        BASELINE_VARIANT_ID,
        SLICE2_TOOL_CANDIDATE_ID,
    }
    assert set(PACKET05A_TOOL_CALL_VARIANTS) == {SLICE2_TOOL_CANDIDATE_ID}

    manifest = build_packet04_route_manifest(
        SLICE2_TOOL_CANDIDATE_ID,
        scope=PACKET05A_TOOL_CALL_SCOPE,
    )
    assert manifest["route_scope"] == PACKET05A_TOOL_CALL_SCOPE
    assert any(
        entry["claimed_changed_surface"] and entry["real_file_path"].endswith("blocks/tools/contract_classifier.py")
        for entry in manifest["routed_modules"]
    )


def test_packet05a_workspace_target_scope_is_explicit_and_routes_context_candidate_distinctly():
    assert set(PACKET05A_WORKSPACE_TARGET_ALLOWED_VARIANTS) == {
        BASELINE_VARIANT_ID,
        WORKSPACE_TARGET_CANDIDATE_ID,
    }
    assert set(PACKET05A_WORKSPACE_TARGET_VARIANTS) == {WORKSPACE_TARGET_CANDIDATE_ID}

    baseline_manifest = build_packet04_route_manifest(
        BASELINE_VARIANT_ID,
        scope=PACKET05A_WORKSPACE_TARGET_SCOPE,
    )
    candidate_manifest = build_packet04_route_manifest(
        WORKSPACE_TARGET_CANDIDATE_ID,
        scope=PACKET05A_WORKSPACE_TARGET_SCOPE,
    )
    assert candidate_manifest["route_scope"] == PACKET05A_WORKSPACE_TARGET_SCOPE

    baseline_by_key = {entry["runtime_key"]: entry for entry in baseline_manifest["routed_modules"]}
    candidate_by_key = {entry["runtime_key"]: entry for entry in candidate_manifest["routed_modules"]}

    baseline_context = baseline_by_key["context"]
    candidate_context = candidate_by_key["context"]
    assert baseline_context["module_import_path"] == "blocks.context.full_history:manage"
    assert candidate_context["module_import_path"] == "blocks.context.workspace_target_state:manage"
    assert candidate_context["real_file_path"].endswith("blocks/context/workspace_target_state.py")
    assert candidate_context["claimed_changed_surface"] is True
    assert candidate_context["file_sha256"] != baseline_context["file_sha256"]

    for runtime_key in ("orientation", "tools_getter", "tool_executor", "execution", "verification", "recovery", "terminal_guard"):
        baseline_entry = baseline_by_key[runtime_key]
        candidate_entry = candidate_by_key[runtime_key]
        assert candidate_entry["claimed_changed_surface"] is False
        assert candidate_entry["module_import_path"] == baseline_entry["module_import_path"]
        assert candidate_entry["file_sha256"] == baseline_entry["file_sha256"]

    with pytest.raises(ValueError, match="scope=packet04a_first_slice"):
        build_packet04_route_manifest(WORKSPACE_TARGET_CANDIDATE_ID)


def test_packet05a_workspace_target_multistep_scope_is_explicit_and_routes_context_candidate_distinctly():
    assert set(PACKET05A_WORKSPACE_TARGET_MULTISTEP_ALLOWED_VARIANTS) == {
        BASELINE_VARIANT_ID,
        WORKSPACE_TARGET_CANDIDATE_ID,
    }
    assert set(PACKET05A_WORKSPACE_TARGET_MULTISTEP_VARIANTS) == {WORKSPACE_TARGET_CANDIDATE_ID}

    baseline_manifest = build_packet04_route_manifest(
        BASELINE_VARIANT_ID,
        scope=PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE,
    )
    candidate_manifest = build_packet04_route_manifest(
        WORKSPACE_TARGET_CANDIDATE_ID,
        scope=PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE,
    )
    assert candidate_manifest["route_scope"] == PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE

    baseline_by_key = {entry["runtime_key"]: entry for entry in baseline_manifest["routed_modules"]}
    candidate_by_key = {entry["runtime_key"]: entry for entry in candidate_manifest["routed_modules"]}
    assert baseline_by_key["context"]["module_import_path"] == "blocks.context.full_history:manage"
    assert candidate_by_key["context"]["module_import_path"] == "blocks.context.workspace_target_state:manage"
    assert candidate_by_key["context"]["claimed_changed_surface"] is True


def test_packet06_pd01_scope_is_explicit_and_routes_only_admitted_families():
    assert set(PACKET06_PD01_ALLOWED_VARIANTS) == {
        BASELINE_VARIANT_ID,
        PD01_PROMPT_PLAN_ENV_CANDIDATE_ID,
        PD01_EVIDENCE_REPORT_CANDIDATE_ID,
    }
    assert set(PACKET06_PD01_VARIANTS) == {
        PD01_PROMPT_PLAN_ENV_CANDIDATE_ID,
        PD01_EVIDENCE_REPORT_CANDIDATE_ID,
    }

    prompt_manifest = build_packet04_route_manifest(
        PD01_PROMPT_PLAN_ENV_CANDIDATE_ID,
        scope=PACKET06_PD01_SCOPE,
    )
    scaffold_manifest = build_packet04_route_manifest(
        PD01_EVIDENCE_REPORT_CANDIDATE_ID,
        scope=PACKET06_PD01_SCOPE,
    )

    assert prompt_manifest["route_scope"] == PACKET06_PD01_SCOPE
    assert scaffold_manifest["route_scope"] == PACKET06_PD01_SCOPE
    assert any(
        entry["claimed_changed_surface"] and entry["real_file_path"].endswith("blocks/orientation/prompt_plan_env.py")
        for entry in prompt_manifest["routed_modules"]
    )
    assert any(
        entry["claimed_changed_surface"]
        and entry["real_file_path"].endswith("blocks/context/evidence_report_scaffold.py")
        for entry in scaffold_manifest["routed_modules"]
    )

    with pytest.raises(ValueError, match=f"scope={PACKET06_PD01_SCOPE}"):
        build_packet04_route_manifest(EXECUTION_CANDIDATE_ID, scope=PACKET06_PD01_SCOPE)
    with pytest.raises(ValueError, match="scope=packet04a_first_slice"):
        build_packet04_route_manifest(PD01_PROMPT_PLAN_ENV_CANDIDATE_ID)


def test_packet06_pd01_scope_loads_executable_callables():
    prompt_manifest = build_packet04_route_manifest(
        PD01_PROMPT_PLAN_ENV_CANDIDATE_ID,
        scope=PACKET06_PD01_SCOPE,
    )
    scaffold_manifest = build_packet04_route_manifest(
        PD01_EVIDENCE_REPORT_CANDIDATE_ID,
        scope=PACKET06_PD01_SCOPE,
    )
    prompt_callables = load_runtime_callables(prompt_manifest)
    scaffold_callables = load_runtime_callables(scaffold_manifest)

    assert callable(prompt_callables["orientation"])
    assert prompt_callables["orientation"].__module__ == "blocks.orientation.prompt_plan_env"
    assert callable(scaffold_callables["context"])
    assert scaffold_callables["context"].__module__ == "blocks.context.evidence_report_scaffold"


def test_workspace_target_multistep_eval_defaults_to_multistep_route_scope():
    batch_spec = {
        "eval_ids": ["ae_workspace_target_decoy_generalization_multistep_v1"],
        "fixed_invariants": {},
    }
    assert _resolve_packet04_route_scope(batch_spec) == PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE


def test_packet04a_zero_unresolved_card_path_gate_is_enforced(monkeypatch, tmp_path):
    from runner import packet04_route_manifest as route_manifest_module

    variant_cards = tmp_path / "variant_cards.md"
    variant_cards.write_text(
        "\n".join(
            [
                f"## variant_card: {EXECUTION_CANDIDATE_ID}",
                "",
                "```yaml",
                "changed_files:",
                "  - blocks/execution/flat_loop.py",
                "  - blocks/recovery/no_recovery.py",
                "  - runner/agent.py",
                "  - runner/nonexistent_packet04a_path.py",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(route_manifest_module, "PACKET04_VARIANT_CARDS_PATH", variant_cards)

    with pytest.raises(ValueError, match="zero-unresolved-card-path gate failed"):
        build_packet04_route_manifest(EXECUTION_CANDIDATE_ID)


def test_packet04a_run_batch_emits_and_validates_route_provenance_artifacts(tmp_path):
    cards = _load_active_eval_cards()
    batch_spec = {
        "batch_id": "packet04a-local-provenance",
        "packet_stage": "packet_04",
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [PRIMARY_EVAL_ID],
        "variant_ids": [BASELINE_VARIANT_ID],
        "task_set_id": "packet04a-local-task-set",
        "task_tier": "atomic",
        "rerun_count": 1,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 1, "tokens": 1000, "usd": 1.0},
        "stability_budget_caps": {"run_count": 1, "tokens": 1000, "usd": 1.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "guardrail_debug",
        "execution_mode_lock": {PRIMARY_EVAL_ID: "deterministic_no_model"},
        "eval_card_refs": {PRIMARY_EVAL_ID: f"inline:{PRIMARY_EVAL_ID}"},
        "task_cases": [{"task_id": "task-001", "task_prompt": "packet04a local verification"}],
    }

    eval_card = dict(cards[PRIMARY_EVAL_ID])
    eval_card["evaluation_lane"] = "guardrail_debug"
    result = run_batch(batch_spec=batch_spec, eval_cards={PRIMARY_EVAL_ID: eval_card})
    assert result["run_count"] == 1

    batch_dir = Path(result["batch_dir"])
    trace_rows = [
        json.loads(line)
        for line in Path(result["trace_summaries_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    record = json.loads(Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()[0])

    run_dir = batch_dir / "runs" / record["run_id"]
    run_header = json.loads((run_dir / "run_header.json").read_text(encoding="utf-8"))
    route_manifest = json.loads((run_dir / "route_manifest.json").read_text(encoding="utf-8"))

    assert run_header["routed_modules"]
    assert run_header["route_manifest_fingerprint"] == route_manifest["route_manifest_fingerprint"]
    assert record["route_manifest_fingerprint"] == route_manifest["route_manifest_fingerprint"]
    assert record["route_manifest_ref"].endswith("route_manifest.json")
    assert record["claimed_surface_fingerprints"] or record["unchanged_surface_fingerprints"]

    validate_result_artifact_linkage(
        record,
        trace_summaries=trace_rows,
        output_root=batch_dir,
    )


def test_packet04a_lane_authority_requires_explicit_lane_and_blocks_legacy_lane_artifacts():
    with pytest.raises(SchemaValidationError):
        validate_evaluation_lane("stability_lane")

    assert validate_evaluation_lane("bounded_diagnostic_only") == "bounded_diagnostic"

    lane_state = _derive_lane_state(
        batch={"fixed_invariants": {"evaluation_lane": "stability_lane"}},
        route={
            "evaluation_lane": "promotion",
            "promotion_authority": True,
            "lane_blocker_codes": [],
            "eval_card": {},
        },
        execution_result={"run_header": {"block_selection": {}}, "run_events": []},
        fixture_plan={},
    )
    assert lane_state["legacy_lane_artifact_detected"] is True
    assert "legacy_stability_lane_artifact" in lane_state["promotion_blocker_codes"]
    assert lane_state["promotion_eligibility"].startswith("blocked_")


def test_packet04a_recommendation_blocks_single_run_all_pass_no_delta_and_missing_audits():
    batch = {
        "batch_id": "packet04a-gate-check-single-run",
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "eval_ids": [PRIMARY_EVAL_ID],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "model_tier_selector": "promotion_tier",
    }
    records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]

    recommendation = _build_recommendation_draft(batch, records)
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )

    assert candidate_action["proposed_status"] == "hold_for_more_evidence"
    assert candidate_action["recommendation_gate_results"]["G3"]["passed"] is False
    assert candidate_action["recommendation_gate_results"]["G7"]["reason"] == "audit_status_aa_missing"
    assert candidate_action["recommendation_gate_results"]["G8"]["reason"] == "audit_status_ab_missing"
    assert candidate_action["recommendation_gate_results"]["G9"]["reason"] == "all_pass_no_delta"


def test_packet04a_metadata_only_audit_claims_fail_closed_without_artifacts(tmp_path):
    batch = {
        "batch_id": "packet04a-metadata-audit-spoof",
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "eval_ids": [PRIMARY_EVAL_ID, SIBLING_EVAL_ID],
        "fixed_invariants": {
            "comparator_variant_id": BASELINE_VARIANT_ID,
            "audit_status_aa": "pass",
            "audit_status_ab": "pass",
        },
        "model_tier_selector": "promotion_tier",
    }
    records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-primary-0",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-primary-1",
            rerun_index=1,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-primary-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-primary-1",
            rerun_index=1,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-baseline-sibling-0",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-baseline-sibling-1",
            rerun_index=1,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-candidate-sibling-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-candidate-sibling-1",
            rerun_index=1,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
    ]

    recommendation = _build_recommendation_draft(batch, records, output_root=tmp_path)
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )

    assert candidate_action["proposed_status"] == "hold_for_more_evidence"
    assert candidate_action["recommendation_gate_inputs"]["audit_status_aa"] == "missing"
    assert candidate_action["recommendation_gate_inputs"]["audit_status_ab"] == "missing"
    assert candidate_action["recommendation_gate_results"]["G7"]["reason"] == "audit_status_aa_missing"
    assert candidate_action["recommendation_gate_results"]["G8"]["reason"] == "audit_status_ab_missing"


def test_packet04a_recommendation_loads_sibling_corroboration_and_audit_truth(tmp_path):
    run_root = Path(tmp_path)
    current_batch_dir = run_root / "packet06-proxy-local"
    sibling_batch_dir = run_root / "packet06-corroboration-local"
    current_batch_dir.mkdir()
    sibling_batch_dir.mkdir()

    batch = {
        "batch_id": "packet06-proxy-local",
        "packet_stage": "packet_06",
        "claim_route_id": "cr_v04_tb_01",
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "eval_ids": [PRIMARY_EVAL_ID],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "model_tier_selector": "promotion_tier",
    }
    records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-primary-0",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-primary-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]

    (current_batch_dir / "audits").mkdir()
    (current_batch_dir / "audits" / "aa_pair_manifest.json").write_text(
        json.dumps({"status_by_variant": {}}),
        encoding="utf-8",
    )
    (current_batch_dir / "audits" / "ab_pair_delta_report.json").write_text(
        json.dumps({"status_by_variant": {}}),
        encoding="utf-8",
    )

    sibling_batch_spec = {
        "batch_id": "packet06-corroboration-local",
        "packet_stage": "packet_06",
        "claim_route_id": "cr_v04_tb_01",
    }
    (sibling_batch_dir / "batch_spec.json").write_text(
        json.dumps(sibling_batch_spec),
        encoding="utf-8",
    )
    sibling_records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-baseline-sibling-0",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-candidate-sibling-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]
    (sibling_batch_dir / "result_records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in sibling_records),
        encoding="utf-8",
    )
    (sibling_batch_dir / "audits").mkdir()
    (sibling_batch_dir / "audits" / "aa_pair_manifest.json").write_text(
        json.dumps(
            {
                "status_by_variant": {
                    BASELINE_VARIANT_ID: {"audit_status": "pass"},
                    PROMOTION_CANDIDATE_ID: {"audit_status": "pass"},
                }
            }
        ),
        encoding="utf-8",
    )
    (sibling_batch_dir / "audits" / "ab_pair_delta_report.json").write_text(
        json.dumps(
            {
                "status_by_variant": {
                    BASELINE_VARIANT_ID: {"audit_status": "pass"},
                    PROMOTION_CANDIDATE_ID: {"audit_status": "pass"},
                }
            }
        ),
        encoding="utf-8",
    )

    recommendation = _build_recommendation_draft(batch, records, output_root=current_batch_dir)
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )

    assert SIBLING_EVAL_ID in candidate_action["recommendation_gate_inputs"]["corroboration_surface_ids"]
    assert candidate_action["recommendation_gate_results"]["G4"] == {"passed": True, "reason": "ok"}
    assert candidate_action["recommendation_gate_results"]["G5"] == {"passed": True, "reason": "ok"}
    assert candidate_action["recommendation_gate_inputs"]["audit_status_aa"] == "pass"
    assert candidate_action["recommendation_gate_inputs"]["audit_status_ab"] == "pass"
    assert candidate_action["recommendation_gate_inputs"]["audit_artifact_ref_aa"] == "audits/aa_pair_manifest.json"
    assert candidate_action["recommendation_gate_inputs"]["audit_artifact_ref_ab"] == "audits/ab_pair_delta_report.json"


def test_packet06_authority_history_can_satisfy_rerun_minimum_and_infer_aa(tmp_path):
    run_root = Path(tmp_path)
    current_run_dir = run_root / "packet06-run-now"
    history_run_dir = run_root / "packet06-run-prev"
    current_batch_dir = current_run_dir / "p06_combo_tool_gateway_01_tool_call_api"
    history_batch_dir = history_run_dir / "p06_combo_tool_gateway_01_tool_call_api"
    current_batch_dir.mkdir(parents=True)
    history_batch_dir.mkdir(parents=True)

    batch = {
        "batch_id": "p06_combo_tool_gateway_01_tool_call_api",
        "packet_stage": "packet_06",
        "claim_route_id": "cr_v04_tb_01",
        "variant_ids": [BASELINE_VARIANT_ID, "v04_tb_01_tool_call_contract_classifier"],
        "eval_ids": ["ae_tool_call_contract_quality_v2"],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "model_tier_selector": "promotion_tier",
    }
    current_records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-baseline-now",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id="v04_tb_01_tool_call_contract_classifier",
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-candidate-now",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]
    history_records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-baseline-prev",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id="v04_tb_01_tool_call_contract_classifier",
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-candidate-prev",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]

    (current_batch_dir / "batch_spec.json").write_text(json.dumps(batch), encoding="utf-8")
    (history_batch_dir / "batch_spec.json").write_text(json.dumps(batch), encoding="utf-8")
    (current_batch_dir / "result_records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in current_records),
        encoding="utf-8",
    )
    (history_batch_dir / "result_records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in history_records),
        encoding="utf-8",
    )

    recommendation = _build_recommendation_draft(batch, current_records, output_root=current_batch_dir)
    candidate_action = next(
        action
        for action in recommendation["candidate_actions"]
        if action["variant_id"] == "v04_tb_01_tool_call_contract_classifier"
    )

    assert candidate_action["recommendation_gate_results"]["G3"] == {"passed": True, "reason": "ok"}
    assert candidate_action["recommendation_gate_results"]["G7"] == {"passed": True, "reason": "ok"}
    assert (
        candidate_action["recommendation_gate_inputs"]["audit_artifact_ref_aa"]
        == "authority_history:inferred_from_result_records"
    )


def test_packet06_authority_history_aa_inference_ignores_unresolved_runs(tmp_path):
    run_root = Path(tmp_path)
    current_run_dir = run_root / "packet06-run-now"
    history_run_dir = run_root / "packet06-run-prev"
    current_batch_dir = current_run_dir / "p06_combo_tool_gateway_01_tool_call_api"
    history_batch_dir = history_run_dir / "p06_combo_tool_gateway_01_tool_call_api"
    current_batch_dir.mkdir(parents=True)
    history_batch_dir.mkdir(parents=True)

    batch = {
        "batch_id": "p06_combo_tool_gateway_01_tool_call_api",
        "packet_stage": "packet_06",
        "claim_route_id": "cr_v04_tb_01",
        "variant_ids": [BASELINE_VARIANT_ID, "v04_tb_01_tool_call_contract_classifier"],
        "eval_ids": ["ae_tool_call_contract_quality_v2"],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "model_tier_selector": "promotion_tier",
    }
    current_records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-baseline-now",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id="v04_tb_01_tool_call_contract_classifier",
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-candidate-now",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]
    history_records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-baseline-prev",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id="v04_tb_01_tool_call_contract_classifier",
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-candidate-prev-pass",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id="v04_tb_01_tool_call_contract_classifier",
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-candidate-prev-unresolved",
            rerun_index=0,
            verdict="unresolved",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]

    (current_batch_dir / "batch_spec.json").write_text(json.dumps(batch), encoding="utf-8")
    (history_batch_dir / "batch_spec.json").write_text(json.dumps(batch), encoding="utf-8")
    (current_batch_dir / "result_records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in current_records),
        encoding="utf-8",
    )
    (history_batch_dir / "result_records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in history_records),
        encoding="utf-8",
    )

    recommendation = _build_recommendation_draft(batch, current_records, output_root=current_batch_dir)
    candidate_action = next(
        action
        for action in recommendation["candidate_actions"]
        if action["variant_id"] == "v04_tb_01_tool_call_contract_classifier"
    )

    assert candidate_action["recommendation_gate_results"]["G7"] == {"passed": True, "reason": "ok"}


def test_packet06_historical_non_proxy_sibling_corroboration_closes_g4_g5(tmp_path):
    root = Path(tmp_path)
    current_run_dir = root / "packet06-run-now"
    history_run_dir = root / "packet06-run-prev"
    current_batch_dir = current_run_dir / "p06_combo_tool_gateway_01_tool_call_api"
    historical_sibling_dir = history_run_dir / "p06_combo_tool_gateway_01_toolchain_pressure_tb01_api"
    current_batch_dir.mkdir(parents=True)
    historical_sibling_dir.mkdir(parents=True)

    batch = {
        "batch_id": "p06_combo_tool_gateway_01_tool_call_api",
        "packet_stage": "packet_06",
        "claim_route_id": "cr_v04_tb_01",
        "variant_ids": [BASELINE_VARIANT_ID, "v04_tb_01_tool_call_contract_classifier"],
        "eval_ids": ["ae_tool_call_contract_quality_v2"],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "model_tier_selector": "promotion_tier",
    }
    current_records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-baseline-primary",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id="v04_tb_01_tool_call_contract_classifier",
            eval_id="ae_tool_call_contract_quality_v2",
            run_id="run-candidate-primary",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]

    sibling_batch = {
        "batch_id": "p06_combo_tool_gateway_01_toolchain_pressure_tb01_api",
        "packet_stage": "packet_06",
        "claim_route_id": "cr_v04_tb_01",
    }
    sibling_records = [
        {
            **_synthetic_record(
                variant_id=BASELINE_VARIANT_ID,
                eval_id="ae_internal_toolchain_dependency_pressure_v1",
                run_id="run-baseline-sibling",
                rerun_index=0,
                verdict="fail",
                lane_class="promotion",
                surface_bounded=False,
                audit_status="missing",
            ),
            "task_intent": "packet06_non_proxy_corroboration",
        },
        {
            **_synthetic_record(
                variant_id="v04_tb_01_tool_call_contract_classifier",
                eval_id="ae_internal_toolchain_dependency_pressure_v1",
                run_id="run-candidate-sibling",
                rerun_index=0,
                verdict="pass",
                lane_class="promotion",
                surface_bounded=False,
                audit_status="missing",
            ),
            "task_intent": "packet06_non_proxy_corroboration",
        },
    ]

    (current_batch_dir / "batch_spec.json").write_text(json.dumps(batch), encoding="utf-8")
    (current_batch_dir / "result_records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in current_records),
        encoding="utf-8",
    )
    (historical_sibling_dir / "batch_spec.json").write_text(json.dumps(sibling_batch), encoding="utf-8")
    (historical_sibling_dir / "result_records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in sibling_records),
        encoding="utf-8",
    )

    recommendation = _build_recommendation_draft(batch, current_records, output_root=current_batch_dir)
    candidate_action = next(
        action
        for action in recommendation["candidate_actions"]
        if action["variant_id"] == "v04_tb_01_tool_call_contract_classifier"
    )

    assert "ae_internal_toolchain_dependency_pressure_v1" in candidate_action["recommendation_gate_inputs"][
        "corroboration_surface_ids"
    ]
    assert candidate_action["recommendation_gate_results"]["G4"] == {"passed": True, "reason": "ok"}
    assert candidate_action["recommendation_gate_results"]["G5"] == {"passed": True, "reason": "ok"}


def test_packet06_defaults_to_promotion_tier_when_selector_is_omitted():
    batch = {
        "batch_id": "packet06-selector-default",
        "packet_stage": "packet_06",
        "claim_route_id": "cr_v04_tb_01",
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "eval_ids": [PRIMARY_EVAL_ID],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
    }
    records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-0",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="missing",
        ),
    ]

    recommendation = _build_recommendation_draft(batch, records)
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )

    assert candidate_action["recommendation_gate_results"]["G10"] == {"passed": True, "reason": "ok"}


def test_packet04a_comparability_ignores_measurement_visibility_grader_suffix():
    batch = {
        "batch_id": "packet04a-comparability-grader-suffix-normalization",
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "eval_ids": [PRIMARY_EVAL_ID],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "model_tier_selector": "promotion_tier",
    }
    baseline = _synthetic_record(
        variant_id=BASELINE_VARIANT_ID,
        eval_id=PRIMARY_EVAL_ID,
        run_id="run-baseline-0",
        rerun_index=0,
        verdict="fail",
        lane_class="promotion",
        surface_bounded=False,
        audit_status="missing",
    )
    candidate = _synthetic_record(
        variant_id=PROMOTION_CANDIDATE_ID,
        eval_id=PRIMARY_EVAL_ID,
        run_id="run-candidate-0",
        rerun_index=0,
        verdict="pass",
        lane_class="promotion",
        surface_bounded=False,
        audit_status="missing",
    )
    baseline["grader_version"] = "score_envelope.v0+p05a_tool_result_attribution_grader_v2+packet05a_proxy_or_incomplete_v1"
    candidate["grader_version"] = "score_envelope.v0+p05a_tool_result_attribution_grader_v2+packet05a_mechanism_visible_v1"

    recommendation = _build_recommendation_draft(batch, [baseline, candidate])
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )

    assert candidate_action["recommendation_gate_results"]["G2"] == {"passed": True, "reason": "ok"}


def test_packet04a_clean_zero_delta_audited_slice_closes_as_screened_no_uplift(tmp_path):
    batch = {
        "batch_id": "packet04a-clean-zero-delta",
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "eval_ids": [PRIMARY_EVAL_ID],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "model_tier_selector": "screening_default",
        "packet_stage": "packet_04",
    }
    records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-1",
            rerun_index=1,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-1",
            rerun_index=1,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
    ]

    audits_dir = tmp_path / "audits"
    audits_dir.mkdir()
    aa_payload = {
        "status_by_variant": {
            BASELINE_VARIANT_ID: {"audit_status": "pass"},
            PROMOTION_CANDIDATE_ID: {"audit_status": "pass"},
        }
    }
    ab_payload = {
        "status_by_variant": {
            BASELINE_VARIANT_ID: {"audit_status": "pass"},
            PROMOTION_CANDIDATE_ID: {"audit_status": "pass"},
        }
    }
    (audits_dir / "aa_pair_manifest.json").write_text(json.dumps(aa_payload), encoding="utf-8")
    (audits_dir / "ab_pair_delta_report.json").write_text(json.dumps(ab_payload), encoding="utf-8")

    recommendation = _build_recommendation_draft(batch, records, output_root=tmp_path)
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )

    assert candidate_action["proposed_status"] == "screened_no_uplift"
    assert candidate_action["next_eval_or_transfer_step"] == "close_as_screened_no_uplift_and_do_not_rerun_same_surface"
    assert candidate_action["recommendation_gate_results"]["G7"] == {"passed": True, "reason": "ok"}
    assert candidate_action["recommendation_gate_results"]["G8"] == {"passed": True, "reason": "ok"}
    assert candidate_action["recommendation_gate_results"]["G9"] == {"passed": False, "reason": "all_pass_no_delta"}
    assert candidate_action["recommendation_gate_results"]["G15"] == {"passed": True, "reason": "ok"}


def test_packet04a_zero_delta_proxy_surface_fails_closed_instead_of_screened_no_uplift(tmp_path):
    batch = {
        "batch_id": "packet04a-zero-delta-proxy-surface",
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "eval_ids": [PRIMARY_EVAL_ID],
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "model_tier_selector": "screening_default",
        "packet_stage": "packet_04",
    }
    records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
            mechanism_visibility_complete=False,
            schema_complete_for_promotion=False,
            helper_only_evidence=True,
        ),
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-1",
            rerun_index=1,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
            mechanism_visibility_complete=False,
            schema_complete_for_promotion=False,
            helper_only_evidence=True,
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
            mechanism_visibility_complete=False,
            schema_complete_for_promotion=False,
            helper_only_evidence=True,
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-1",
            rerun_index=1,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
            mechanism_visibility_complete=False,
            schema_complete_for_promotion=False,
            helper_only_evidence=True,
        ),
    ]

    audits_dir = tmp_path / "audits"
    audits_dir.mkdir()
    aa_payload = {
        "status_by_variant": {
            BASELINE_VARIANT_ID: {"audit_status": "pass"},
            PROMOTION_CANDIDATE_ID: {"audit_status": "pass"},
        }
    }
    ab_payload = {
        "status_by_variant": {
            BASELINE_VARIANT_ID: {"audit_status": "pass"},
            PROMOTION_CANDIDATE_ID: {"audit_status": "pass"},
        }
    }
    (audits_dir / "aa_pair_manifest.json").write_text(json.dumps(aa_payload), encoding="utf-8")
    (audits_dir / "ab_pair_delta_report.json").write_text(json.dumps(ab_payload), encoding="utf-8")

    recommendation = _build_recommendation_draft(batch, records, output_root=tmp_path)
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )

    assert candidate_action["proposed_status"] == "hold_for_more_evidence"
    assert candidate_action["recommendation_gate_results"]["G15"] == {
        "passed": False,
        "reason": "helper_only_or_proxy_surface",
    }


def test_packet04a_bounded_or_debug_surfaces_cannot_satisfy_promotion_corroboration():
    batch = {
        "batch_id": "packet04a-corroboration-guardrail",
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "eval_ids": [PRIMARY_EVAL_ID, SIBLING_EVAL_ID],
        "fixed_invariants": {
            "comparator_variant_id": BASELINE_VARIANT_ID,
            "audit_status_aa": "pass",
            "audit_status_ab": "pass",
        },
        "model_tier_selector": "promotion_tier",
    }
    records = [
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-primary-0",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-baseline-primary-1",
            rerun_index=1,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-primary-0",
            rerun_index=0,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=PRIMARY_EVAL_ID,
            run_id="run-candidate-primary-1",
            rerun_index=1,
            verdict="pass",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-baseline-sibling-0",
            rerun_index=0,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=BASELINE_VARIANT_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-baseline-sibling-1",
            rerun_index=1,
            verdict="fail",
            lane_class="promotion",
            surface_bounded=False,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-candidate-sibling-0",
            rerun_index=0,
            verdict="pass",
            lane_class="guardrail_debug",
            surface_bounded=True,
            audit_status="pass",
        ),
        _synthetic_record(
            variant_id=PROMOTION_CANDIDATE_ID,
            eval_id=SIBLING_EVAL_ID,
            run_id="run-candidate-sibling-1",
            rerun_index=1,
            verdict="pass",
            lane_class="guardrail_debug",
            surface_bounded=True,
            audit_status="pass",
        ),
    ]

    recommendation = _build_recommendation_draft(batch, records)
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )

    assert candidate_action["proposed_status"] == "bound"
    assert candidate_action["recommendation_gate_results"]["G4"]["passed"] is True
    assert candidate_action["recommendation_gate_results"]["G5"] == {
        "passed": False,
        "reason": "bounded_or_guardrail_surface_used_for_corroboration",
    }


def test_packet04a_run_batch_emits_real_aa_ab_audit_artifacts_and_gate_reads_them(tmp_path):
    cards = _load_active_eval_cards()
    batch_spec = {
        "batch_id": "packet04a-audit-artifacts-local",
        "packet_stage": "packet_04",
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [PRIMARY_EVAL_ID],
        "variant_ids": [BASELINE_VARIANT_ID, EXECUTION_CANDIDATE_ID],
        "task_set_id": "packet04a-audit-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "guardrail_debug",
        "execution_mode_lock": {PRIMARY_EVAL_ID: "deterministic_no_model"},
        "eval_card_refs": {PRIMARY_EVAL_ID: f"inline:{PRIMARY_EVAL_ID}"},
        "task_cases": [{"task_id": "task-001", "task_prompt": "packet04a audit verification"}],
    }

    eval_card = dict(cards[PRIMARY_EVAL_ID])
    eval_card["evaluation_lane"] = "guardrail_debug"
    result = run_batch(batch_spec=batch_spec, eval_cards={PRIMARY_EVAL_ID: eval_card})
    batch_dir = Path(result["batch_dir"])
    recommendation = json.loads(Path(result["recommendations_path"]).read_text(encoding="utf-8"))
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == EXECUTION_CANDIDATE_ID
    )

    gate_inputs = candidate_action["recommendation_gate_inputs"]
    assert gate_inputs["audit_status_aa"] == "pass"
    assert gate_inputs["audit_status_ab"] == "pass"
    assert candidate_action["recommendation_gate_results"]["G7"] == {"passed": True, "reason": "ok"}
    assert candidate_action["recommendation_gate_results"]["G8"] == {"passed": True, "reason": "ok"}

    aa_path = batch_dir / gate_inputs["audit_artifact_ref_aa"]
    ab_path = batch_dir / gate_inputs["audit_artifact_ref_ab"]
    assert aa_path.exists()
    assert ab_path.exists()

    aa_payload = json.loads(aa_path.read_text(encoding="utf-8"))
    ab_payload = json.loads(ab_path.read_text(encoding="utf-8"))
    assert aa_payload["status_by_variant"][EXECUTION_CANDIDATE_ID]["audit_status"] == "pass"
    assert ab_payload["status_by_variant"][EXECUTION_CANDIDATE_ID]["audit_status"] == "pass"


def test_packet04a_route_identity_is_separate_from_comparability_invariants(tmp_path):
    cards = _load_active_eval_cards()
    batch_spec = {
        "batch_id": "packet04a-invariant-comparability-local",
        "packet_stage": "packet_04",
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [PRIMARY_EVAL_ID],
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "task_set_id": "packet04a-invariant-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "guardrail_debug",
        "execution_mode_lock": {PRIMARY_EVAL_ID: "deterministic_no_model"},
        "eval_card_refs": {PRIMARY_EVAL_ID: f"inline:{PRIMARY_EVAL_ID}"},
        "task_cases": [{"task_id": "task-001", "task_prompt": "packet04a invariant verification"}],
    }

    eval_card = dict(cards[PRIMARY_EVAL_ID])
    eval_card["evaluation_lane"] = "guardrail_debug"
    result = run_batch(batch_spec=batch_spec, eval_cards={PRIMARY_EVAL_ID: eval_card})
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline_rows = [row for row in rows if row["variant_id"] == BASELINE_VARIANT_ID]
    candidate_rows = [row for row in rows if row["variant_id"] == PROMOTION_CANDIDATE_ID]

    assert baseline_rows
    assert candidate_rows
    assert {row["invariant_fingerprint"] for row in baseline_rows} == {
        row["invariant_fingerprint"] for row in candidate_rows
    }
    assert {row["route_manifest_fingerprint"] for row in baseline_rows} != {
        row["route_manifest_fingerprint"] for row in candidate_rows
    }


def test_packet04_slice2_run_batch_accepts_explicit_scope_and_emits_route_provenance(tmp_path):
    cards = _load_active_eval_cards()
    eval_id = "ae_cwd_workdir_path_contract_guard"
    batch_spec = {
        "batch_id": "packet04-slice2-cwd-local",
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET04_SLICE2_ROUTE_SCOPE,
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID, SLICE2_EXECUTION_CANDIDATE_ID],
        "task_set_id": "packet04-slice2-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "promotion",
        "execution_mode_lock": {eval_id: "deterministic_no_model"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "task-001", "task_prompt": "packet04 slice2 cwd verification"}],
    }

    result = run_batch(batch_spec=batch_spec, eval_cards={eval_id: cards[eval_id]})
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidate_rows = [row for row in rows if row["variant_id"] == SLICE2_EXECUTION_CANDIDATE_ID]
    assert len(candidate_rows) == 2
    assert all(
        row["claimed_surface_fingerprints"]["execution.flat_loop_terminality_mechanism"]["real_file_path"].endswith(
            "blocks/execution/cwd_invariant_loop.py"
        )
        for row in candidate_rows
    )


def test_packet04_slice2_cwd_candidate_emits_mechanism_visible_gate_inputs(tmp_path):
    cards = _load_active_eval_cards()
    eval_id = "ae_cwd_workdir_path_contract_guard"
    batch_spec = {
        "batch_id": "packet04-slice2-cwd-mechanism-visible",
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET04_SLICE2_ROUTE_SCOPE,
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID, SLICE2_EXECUTION_CANDIDATE_ID],
        "task_set_id": "packet04-slice2-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "promotion",
        "execution_mode_lock": {eval_id: "deterministic_no_model"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "task-001", "task_prompt": "packet04 slice2 cwd verification"}],
    }

    result = run_batch(batch_spec=batch_spec, eval_cards={eval_id: cards[eval_id]})
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidate_rows = [row for row in rows if row["variant_id"] == SLICE2_EXECUTION_CANDIDATE_ID]
    baseline_rows = [row for row in rows if row["variant_id"] == BASELINE_VARIANT_ID]
    assert candidate_rows
    assert baseline_rows
    assert all(row["recommendation_gate_inputs"]["mechanism_visibility_complete"] is True for row in candidate_rows)
    assert all(row["recommendation_gate_inputs"]["schema_complete_for_promotion"] is True for row in candidate_rows)
    assert all(row["recommendation_gate_inputs"]["helper_only_evidence"] is False for row in candidate_rows)
    assert all(row["grader_version"].endswith("packet05a_mechanism_visible_v1") for row in candidate_rows)
    assert all(row["promotion_eligibility"] == "blocked_schema_missing_required_fields" for row in baseline_rows)
    assert all("schema_missing_required_fields" in row["promotion_blocker_codes"] for row in baseline_rows)
    assert all(row["grader_version"].endswith("packet05a_proxy_or_incomplete_v1") for row in baseline_rows)


def test_packet04_slice2_tool_candidate_emits_mechanism_visible_gate_inputs(tmp_path):
    cards = _load_active_eval_cards()
    eval_id = "ae_tool_call_shape_argument_contract"
    eval_card = dict(cards[eval_id])
    eval_card["evaluation_lane"] = "guardrail_debug"
    batch_spec = {
        "batch_id": "packet04-slice2-tool-mechanism-visible",
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET04_SLICE2_ROUTE_SCOPE,
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID, SLICE2_TOOL_CANDIDATE_ID],
        "task_set_id": "packet04-slice2-tool-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "guardrail_debug",
        "execution_mode_lock": {eval_id: "deterministic_no_model"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "task-001", "task_prompt": "packet04 slice2 tool verification"}],
    }

    result = run_batch(batch_spec=batch_spec, eval_cards={eval_id: eval_card})
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    traces = [
        json.loads(line)
        for line in Path(result["trace_summaries_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidate_rows = [row for row in rows if row["variant_id"] == SLICE2_TOOL_CANDIDATE_ID]
    assert candidate_rows
    assert all(row["recommendation_gate_inputs"]["mechanism_visibility_complete"] is True for row in candidate_rows)
    assert all(row["recommendation_gate_inputs"]["schema_complete_for_promotion"] is True for row in candidate_rows)
    assert all(row["recommendation_gate_inputs"]["helper_only_evidence"] is False for row in candidate_rows)
    assert all("forced_probe_dependency" in row["promotion_blocker_codes"] for row in candidate_rows)
    candidate_trace = next(
        row for row in traces if SLICE2_TOOL_CANDIDATE_ID in row["run_id"]
    )["packet03_eval_summary"]
    assert candidate_trace["tool_call_shape_classifier_source"] == "runtime_probe"
    assert candidate_trace["tool_contract_cases_total"] == 5
    assert candidate_trace["tool_contract_cases_matched"] == 5

    sample_run_dir = (
        Path(result["batch_dir"])
        / "runs"
        / candidate_rows[0]["run_id"]
    )
    events = [
        json.loads(line)
        for line in (sample_run_dir / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    raw_bash_results = [event for event in events if event["event_type"] == "raw_bash_result"]
    assert raw_bash_results
    raw_details = raw_bash_results[0]["payload"]["details"]
    for key in (
        "case_id",
        "tool_name",
        "raw_payload",
        "normalized_payload",
        "tool_call_contract_class",
        "result_class",
        "reason_code",
        "decision_source",
        "signal_attribution_scope",
        "mechanism_permission_signal_detected",
        "mechanism_runtime_signal_detected",
        "proxy_permission_signal_detected",
        "proxy_runtime_signal_detected",
        "permission_signal_detected",
        "runtime_signal_detected",
        "attribution_trace",
        "phase",
        "step",
        "exit_code",
        "timed_out",
        "forced_probe",
    ):
        assert key in raw_details
    assert raw_details["signal_attribution_scope"] == "proxy_only"
    assert raw_details["mechanism_permission_signal_detected"] is None
    assert raw_details["mechanism_runtime_signal_detected"] is None
    governed_events = [event for event in events if event["event_type"] == "governed_eval_truth_finalized"]
    assert governed_events
    candidate_trace_row = next(row for row in traces if SLICE2_TOOL_CANDIDATE_ID in row["run_id"])
    assert candidate_trace_row["tool_error_summary"]["tool_error_events"] == 3
    assert all(row["grader_version"].endswith("packet05a_mechanism_visible_v1") for row in candidate_rows)

    recommendation = json.loads(Path(result["recommendations_path"]).read_text(encoding="utf-8"))
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == SLICE2_TOOL_CANDIDATE_ID
    )
    assert candidate_action["proposed_status"] == "bound"


def test_packet05a_workspace_target_decoy_generalization_v2_fails_closed_without_forced_probe_blocker(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_v2"
    batch_spec = {
        "batch_id": "packet05a-workspace-target-decoy-v2-local",
        "packet_stage": "packet_04",
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID],
        "task_set_id": "packet05a-workspace-target-decoy-v2-task-set",
        "task_tier": "atomic",
        "rerun_count": 1,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 2, "tokens": 5000, "usd": 1.0},
        "stability_budget_caps": {"run_count": 2, "tokens": 5000, "usd": 1.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "guardrail_debug",
        "execution_mode_lock": {eval_id: "one_shot_batchable"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "workspace_target_regime_alpha", "task_prompt": "workspace target decoy local probe"}],
    }

    result = run_batch(
        batch_spec=batch_spec,
        eval_cards={eval_id: _workspace_target_decoy_generalization_v2_eval_card()},
        model_route_override=LocalStubModelClient.create(response_text="done").route,
    )
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    traces = [
        json.loads(line)
        for line in Path(result["trace_summaries_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    row = rows[0]
    trace_row = traces[0]
    trace = trace_row["packet03_eval_summary"]

    assert row["score_summary"]["final_verdict"] == "unresolved"
    assert row["forced_probe_observed"] is False
    assert "forced_probe_dependency" not in row["promotion_blocker_codes"]
    assert row["promotion_eligibility"] == "blocked_guardrail_debug_lane"
    assert row["recommendation_gate_inputs"]["mechanism_visibility_complete"] is False
    assert row["recommendation_gate_inputs"]["schema_complete_for_promotion"] is False
    assert trace["workspace_target_regime_count"] >= 2
    assert trace["workspace_target_transfer_tier"] == "development_transfer"
    assert trace["workspace_target_forced_probe_observed"] is False
    assert trace_row["raw_execution_truth"]["step_count"] == 2
    assert trace_row["loop_pattern_summary"]["step_count"] == 2


def test_packet05a_workspace_target_decoy_generalization_v2_fixture_sets_live_activation_contract(tmp_path):
    eval_id = "ae_workspace_target_decoy_generalization_v2"
    route = {"eval_id": eval_id, "eval_card": _workspace_target_decoy_generalization_v2_eval_card()}
    fixture_plan = materialize_packet03_eval_fixture(
        route=route,
        result_context={
            "eval_id": eval_id,
            "variant_id": BASELINE_VARIANT_ID,
            "task_id": "workspace_target_regime_alpha",
            "task_prompt": "workspace target decoy local probe",
            "rerun_index": 0,
        },
        run_dir=tmp_path / "workspace-target-decoy-activation-fixture",
    )
    fixture = fixture_plan["fixture"]
    activation_payload = fixture["activation_payload_descriptor"]
    activation_contract = fixture["exercise_activation_contract"]
    prompt = fixture_plan["task_prompt"]
    target = fixture["target_descriptor"]

    assert fixture_plan["model_client_kwargs"] is None
    assert fixture_plan["exercise_activation_contract"] == activation_contract
    assert activation_contract["require_live_tool_call"] is True
    assert activation_contract["preferred_tool_name"] == "raw_bash"
    assert activation_contract["first_turn_tool_only_response"] is True
    assert activation_contract["require_payload_copy_from_source"] is True
    assert activation_contract["forbid_forced_probe_satisfier"] is True
    assert fixture["visibility_contract"]["forbid_forced_probe_satisfier"] is True
    assert activation_payload["source_path"] in prompt
    assert target["expected_text"].strip() not in prompt


def test_packet05a_verification_quality_v2_discriminates_candidate_from_baseline(tmp_path):
    eval_id = "ae_verification_reason_code_quality_v2"
    batch_spec = {
        "batch_id": "packet05a-verification-v2-local",
        "packet_stage": "packet_04",
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID, PROMOTION_CANDIDATE_ID],
        "task_set_id": "packet05a-verification-v2-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "promotion",
        "execution_mode_lock": {eval_id: "deterministic_no_model"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [
            {
                "task_id": "verification_missing_l1_non_substitution",
                "task_prompt": "packet05a verification quality local probe",
            }
        ],
    }

    result = run_batch(batch_spec=batch_spec, eval_cards={eval_id: _verification_v2_eval_card()})
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline_rows = [row for row in rows if row["variant_id"] == BASELINE_VARIANT_ID]
    candidate_rows = [row for row in rows if row["variant_id"] == PROMOTION_CANDIDATE_ID]
    assert baseline_rows and candidate_rows
    assert all(row["score_summary"]["final_verdict"] == "fail" for row in baseline_rows)
    assert all(row["score_summary"]["final_verdict"] == "pass" for row in candidate_rows)
    assert all(row["recommendation_gate_inputs"]["mechanism_visibility_complete"] is True for row in candidate_rows)

    recommendation = json.loads(Path(result["recommendations_path"]).read_text(encoding="utf-8"))
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == PROMOTION_CANDIDATE_ID
    )
    assert candidate_action["proposed_status"] != "screened_no_uplift"
    assert candidate_action["proposed_status"] in {"hold_for_more_evidence", "promote_to_atomic_eligible"}


def test_packet05a_lifecycle_adversarial_v2_discriminates_candidate_from_baseline(tmp_path):
    eval_id = "ae_lifecycle_adversarial_terminality_v2"
    batch_spec = {
        "batch_id": "packet05a-lifecycle-v2-local",
        "packet_stage": "packet_04",
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID, EXECUTION_CANDIDATE_ID],
        "task_set_id": "packet05a-lifecycle-v2-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {"comparator_variant_id": BASELINE_VARIANT_ID},
        "budget_caps": {"run_count": 12, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 12, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "promotion",
        "execution_mode_lock": {eval_id: "deterministic_no_model"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [
            {
                "task_id": "lifecycle_duplicate_terminal_write_attempt",
                "task_prompt": "packet05a lifecycle duplicate write local probe",
            },
            {
                "task_id": "lifecycle_post_cancel_tool_return",
                "task_prompt": "packet05a lifecycle post-cancel return local probe",
            },
            {
                "task_id": "lifecycle_cleanup_race_incomplete_cleanup",
                "task_prompt": "packet05a lifecycle cleanup race local probe",
            },
        ],
    }

    result = run_batch(batch_spec=batch_spec, eval_cards={eval_id: _lifecycle_v2_eval_card()})
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline_rows = [row for row in rows if row["variant_id"] == BASELINE_VARIANT_ID]
    candidate_rows = [row for row in rows if row["variant_id"] == EXECUTION_CANDIDATE_ID]
    assert baseline_rows and candidate_rows
    assert all(row["score_summary"]["final_verdict"] == "fail" for row in baseline_rows)
    assert all(row["score_summary"]["final_verdict"] == "pass" for row in candidate_rows)
    assert all(row["recommendation_gate_inputs"]["mechanism_visibility_complete"] is True for row in candidate_rows)

    traces = [
        json.loads(line)
        for line in Path(result["trace_summaries_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidate_traces = [
        row for row in traces if EXECUTION_CANDIDATE_ID in row["run_id"]
    ]
    assert len(candidate_traces) == 6
    assert any(
        row["packet03_eval_summary"]["duplicate_terminal_write_observed"] is True
        for row in candidate_traces
    )
    assert any(
        row["packet03_eval_summary"]["post_cancel_tool_return_count"] == 1
        for row in candidate_traces
    )
    assert any(
        row["packet03_eval_summary"]["cleanup_race_detected"] is True
        for row in candidate_traces
    )

    recommendation = json.loads(Path(result["recommendations_path"]).read_text(encoding="utf-8"))
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == EXECUTION_CANDIDATE_ID
    )
    assert candidate_action["proposed_status"] != "screened_no_uplift"
    assert candidate_action["proposed_status"] in {"hold_for_more_evidence", "promote_to_atomic_eligible"}


def test_packet05a_tool_result_attribution_v2_discriminates_candidate_from_baseline(tmp_path):
    eval_id = "ae_tool_result_attribution_quality_v2"
    batch_spec = {
        "batch_id": "packet05a-tool-result-v2-local",
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET05A_TOOL_RESULT_SCOPE,
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID, TOOL_RESULT_CANDIDATE_ID],
        "task_set_id": "packet05a-tool-result-v2-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {
            "comparator_variant_id": BASELINE_VARIANT_ID,
            "packet04_route_scope": PACKET05A_TOOL_RESULT_SCOPE,
        },
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "promotion",
        "execution_mode_lock": {eval_id: "deterministic_no_model"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "tool_result_live_cases", "task_prompt": "packet05a tool result attribution local probe"}],
    }

    result = run_batch(batch_spec=batch_spec, eval_cards={eval_id: _tool_result_v2_eval_card()})
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline_rows = [row for row in rows if row["variant_id"] == BASELINE_VARIANT_ID]
    candidate_rows = [row for row in rows if row["variant_id"] == TOOL_RESULT_CANDIDATE_ID]
    assert baseline_rows and candidate_rows
    assert all(row["score_summary"]["final_verdict"] == "fail" for row in baseline_rows)
    assert all(row["score_summary"]["final_verdict"] == "pass" for row in candidate_rows)
    assert all(row["promotion_eligibility"].startswith("blocked_") for row in baseline_rows)
    assert all("lane_policy_restriction" in row["promotion_blocker_codes"] for row in baseline_rows)
    assert all(row["recommendation_gate_inputs"]["mechanism_visibility_complete"] is True for row in candidate_rows)
    assert all(row["governed_terminal_status"] == "tool_eval_completed" for row in candidate_rows)
    assert all("governed_eval_truth_finalized" in row["governed_truth_ref"] for row in candidate_rows)

    traces = [
        json.loads(line)
        for line in Path(result["trace_summaries_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidate_trace = next(row for row in traces if TOOL_RESULT_CANDIDATE_ID in row["run_id"])["packet03_eval_summary"]
    baseline_trace = next(row for row in traces if BASELINE_VARIANT_ID in row["run_id"])["packet03_eval_summary"]
    assert candidate_trace["tool_result_attribution_source"] == "execution_loop"
    assert candidate_trace["tool_result_attribution_cases_matched"] == 4
    mixed_case = next(
        case for case in candidate_trace["tool_result_attribution_case_results"] if case["case_id"] == "mixed_fault_live_case"
    )
    assert mixed_case["observed_result_class"] == "runtime_error"
    assert mixed_case["observed_reason_code"] == "tool_runtime_mixed_permission_runtime_signals"
    baseline_mixed_case = next(
        case for case in baseline_trace["tool_result_attribution_case_results"] if case["case_id"] == "mixed_fault_live_case"
    )
    assert baseline_mixed_case["observed_result_class"] == "permission_denied"
    trace_row = next(row for row in traces if TOOL_RESULT_CANDIDATE_ID in row["run_id"])
    assert trace_row["raw_execution_truth"]["execution_status"] == "max_steps_exhausted"
    assert trace_row["governed_eval_truth"]["governed_terminal_status"] == "tool_eval_completed"
    assert trace_row["governed_eval_truth"]["final_verdict"] == "pass"

    baseline_run_dir = Path(result["batch_dir"]) / "runs" / baseline_rows[0]["run_id"]
    baseline_events = [
        json.loads(line)
        for line in (baseline_run_dir / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    permission_event = next(
        event
        for event in baseline_events
        if event["event_type"] == "raw_bash_result"
        and event["payload"]["details"].get("case_id") == "permission_live_case"
    )
    permission_details = permission_event["payload"]["details"]
    assert permission_details["attribution_trace"] is None
    assert permission_details["signal_attribution_scope"] == "proxy_only"
    assert permission_details["mechanism_permission_signal_detected"] is None
    assert permission_details["mechanism_runtime_signal_detected"] is None
    assert permission_details["permission_signal_detected"] is None
    assert permission_details["runtime_signal_detected"] is None
    assert permission_details["proxy_permission_signal_detected"] is True
    assert permission_details["proxy_runtime_signal_detected"] is False

    recommendation = json.loads(Path(result["recommendations_path"]).read_text(encoding="utf-8"))
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == TOOL_RESULT_CANDIDATE_ID
    )
    assert "governed_eval_truth_finalized" in candidate_action["recommendation_gate_inputs"]["governed_truth_ref"]
    assert candidate_action["recommendation_gate_inputs"]["governed_terminal_status"] == "tool_eval_completed"
    assert candidate_action["proposed_status"] != "screened_no_uplift"
    assert candidate_action["proposed_status"] in {"hold_for_more_evidence", "promote_to_atomic_eligible"}


def test_packet05a_tool_call_contract_v2_discriminates_candidate_from_baseline(tmp_path):
    eval_id = "ae_tool_call_contract_quality_v2"
    batch_spec = {
        "batch_id": "packet05a-tool-call-v2-local",
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET05A_TOOL_CALL_SCOPE,
        "eval_family": "packet_04_first_atomic_variants",
        "eval_ids": [eval_id],
        "variant_ids": [BASELINE_VARIANT_ID, SLICE2_TOOL_CANDIDATE_ID],
        "task_set_id": "packet05a-tool-call-v2-task-set",
        "task_tier": "atomic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "oauth:gpt-5.4-mini",
            "screening_fallback": "oauth:gpt-5.4-mini",
            "promotion_tier": "gpt-5.3-codex",
        },
        "provider_route": "local_stub",
        "fixed_invariants": {
            "comparator_variant_id": BASELINE_VARIANT_ID,
            "packet04_route_scope": PACKET05A_TOOL_CALL_SCOPE,
        },
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(tmp_path),
        "evaluation_lane": "promotion",
        "execution_mode_lock": {eval_id: "deterministic_no_model"},
        "eval_card_refs": {eval_id: f"inline:{eval_id}"},
        "task_cases": [{"task_id": "tool_call_live_cases", "task_prompt": "packet05a tool call contract local probe"}],
    }

    result = run_batch(batch_spec=batch_spec, eval_cards={eval_id: _tool_call_v2_eval_card()})
    rows = [
        json.loads(line)
        for line in Path(result["result_records_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    baseline_rows = [row for row in rows if row["variant_id"] == BASELINE_VARIANT_ID]
    candidate_rows = [row for row in rows if row["variant_id"] == SLICE2_TOOL_CANDIDATE_ID]
    assert baseline_rows and candidate_rows
    assert all(row["score_summary"]["final_verdict"] == "fail" for row in baseline_rows)
    assert all(row["score_summary"]["final_verdict"] == "pass" for row in candidate_rows)
    assert all(row["recommendation_gate_inputs"]["mechanism_visibility_complete"] is True for row in candidate_rows)
    assert all(row["governed_terminal_status"] == "tool_eval_completed" for row in candidate_rows)

    traces = [
        json.loads(line)
        for line in Path(result["trace_summaries_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidate_trace = next(row for row in traces if SLICE2_TOOL_CANDIDATE_ID in row["run_id"])["packet03_eval_summary"]
    baseline_trace = next(row for row in traces if BASELINE_VARIANT_ID in row["run_id"])["packet03_eval_summary"]
    assert candidate_trace["tool_call_contract_source"] == "execution_loop"
    assert candidate_trace["tool_contract_cases_matched"] == 5
    plain_case = next(
        case for case in candidate_trace["tool_contract_case_results"] if case["case_id"] == "plain_string_arguments_case"
    )
    assert plain_case["observed_contract_class"] == "malformed_call"
    assert plain_case["observed_result_class"] == "contract_error"
    baseline_plain_case = next(
        case for case in baseline_trace["tool_contract_case_results"] if case["case_id"] == "plain_string_arguments_case"
    )
    assert baseline_plain_case["observed_contract_class"] == "valid_call"

    recommendation = json.loads(Path(result["recommendations_path"]).read_text(encoding="utf-8"))
    candidate_action = next(
        action for action in recommendation["candidate_actions"] if action["variant_id"] == SLICE2_TOOL_CANDIDATE_ID
    )
    assert candidate_action["proposed_status"] != "screened_no_uplift"
    assert candidate_action["proposed_status"] in {"hold_for_more_evidence", "promote_to_atomic_eligible"}

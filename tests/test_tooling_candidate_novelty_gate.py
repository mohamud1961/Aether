from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_PATH = (
    REPO_ROOT
    / "tracking/collab/autonomous_loop/eval_suite_v1_tournament_orchestration/tools/candidate_novelty_gate_lib.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("candidate_novelty_gate_lib", LIB_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _memory(priors: list[dict], repeat_reason: str = "no_real_tool_result_evidence", repeat_count: int = 2) -> dict:
    return {
        "repeat_failure_summary": {
            "repeat_reason_code": repeat_reason,
            "repeat_count": repeat_count,
            "escalation_recommended": repeat_count >= 2,
        },
        "attempted_mechanisms": priors,
    }


def test_novel_candidate_is_allowed() -> None:
    module = _load_module()
    candidate = {
        "candidate_id": "cand_new",
        "action": "new_variant",
        "mechanism": "fresh_path_contract_repair_01",
        "route_id_to_score": "route_fresh",
        "target_failure_class": "path_cwd",
    }
    prior = {
        "candidate_id": "cand_old",
        "failure_reason": "target_gate_not_full_pass",
        "mechanism": "tool_call_identity_patch_01",
        "route_id": "route_tooling",
        "failure_class": "tool_contract",
        "primary_reason_code": "tool_call_contract_malformed",
    }
    result = module.evaluate_candidate_novelty(candidate, _memory([prior]))
    assert result["allow_build"] is True
    assert result["decision"] == "allow_novel"
    assert result["matched_priors"] == []


def test_exact_mechanism_family_match_rejects_repeat() -> None:
    module = _load_module()
    candidate = {
        "candidate_id": "cand_new",
        "action": "new_variant",
        "mechanism_family": "schema_required_arg_planner",
        "mechanism": "schema_required_arg_planner_07",
        "route_id_to_score": "route_a",
        "target_failure_class": "tool_contract",
    }
    prior = {
        "candidate_id": "cand_old",
        "failure_reason": "target_gate_not_full_pass",
        "mechanism_family": "schema_required_arg_planner",
        "mechanism": "schema_required_arg_planner_03",
        "route_id": "route_b",
        "failure_class": "tool_contract",
        "primary_reason_code": "wrong_argument_value",
    }
    result = module.evaluate_candidate_novelty(candidate, _memory([prior], repeat_reason="wrong_argument_value"))
    assert result["allow_build"] is False
    assert result["decision"] == "reject_repeat"
    assert "exact_mechanism_family" in result["selected_prior"]["triggered_rules"]


def test_high_normalized_token_overlap_rejects_repeat() -> None:
    module = _load_module()
    candidate = {
        "candidate_id": "cand_new",
        "action": "new_variant",
        "mechanism": "result_identity_chain_final_slot_gate_beta",
        "route_id_to_score": "route_beta",
        "target_failure_class": "unclear",
    }
    prior = {
        "candidate_id": "cand_old",
        "failure_reason": "target_gate_not_full_pass",
        "mechanism": "result_identity_chain_final_slot_gate_alpha",
        "route_id": "route_old",
        "failure_class": "tool_contract",
        "primary_reason_code": "tool_result_missing_receipt",
    }
    result = module.evaluate_candidate_novelty(
        candidate,
        _memory([prior], repeat_reason="tool_result_missing_receipt"),
        token_overlap_threshold=0.45,
    )
    assert result["allow_build"] is False
    assert result["decision"] == "reject_repeat"
    assert "normalized_token_overlap" in result["selected_prior"]["triggered_rules"]


def test_shared_route_and_failure_with_repeated_reason_family_rejects_repeat() -> None:
    module = _load_module()
    candidate = {
        "candidate_id": "cand_new",
        "action": "repair_existing",
        "mechanism": "route_specific_repair_01",
        "route_id_to_score": "route_tooling_core",
        "target_failure_class": "runtime",
    }
    prior = {
        "candidate_id": "cand_old",
        "iteration": "iter_09",
        "failure_reason": "target_gate_not_full_pass",
        "mechanism": "other_shape_01",
        "route_id": "route_tooling_core",
        "failure_class": "runtime",
        "primary_reason_code": "tool_runtime_permission_denied",
        "repeat_reason_streak": 3,
    }
    result = module.evaluate_candidate_novelty(candidate, _memory([prior], repeat_reason="tool_runtime_nonzero_exit", repeat_count=3))
    assert result["allow_build"] is False
    assert result["decision"] == "reject_repeat"
    assert "shared_route_failure_repeated_reason_family" in result["selected_prior"]["triggered_rules"]


def test_parameterized_backlog_retry_requires_measurable_delta() -> None:
    module = _load_module()
    prior = {
        "candidate_id": "cand_old",
        "failure_reason": "target_gate_not_full_pass",
        "mechanism_family": "result_identity_chain_guard",
        "mechanism": "result_identity_chain_guard_01",
        "file_targets": ["runner/successor_phase65.py"],
        "max_changed_files": 4,
        "max_changed_lines": 400,
        "comparator_variant_id": "spb_01",
        "failure_card_ref": "fc_tooling_001",
        "builder_constraint_scope": ["runner/**", "tests/**"],
    }
    candidate_same = {
        "candidate_id": "cand_new",
        "action": "parameterized_backlog_retry",
        "mechanism_family": "result_identity_chain_guard",
        "mechanism": "result_identity_chain_guard_02",
        "file_targets": ["runner/successor_phase65.py"],
        "max_changed_files": 4,
        "max_changed_lines": 400,
        "comparator_variant_id": "spb_01",
        "failure_card_ref": "fc_tooling_001",
        "builder_constraint_scope": ["runner/**", "tests/**"],
    }
    result = module.evaluate_candidate_novelty(candidate_same, _memory([prior]))
    assert result["allow_build"] is False
    assert result["decision"] == "reject_retry_without_measurable_delta"
    assert result["bypass"]["requested"] is True
    assert result["bypass"]["allowed"] is False
    assert result["bypass"]["delta_fields"] == []


def test_parameterized_backlog_retry_allows_build_with_measurable_delta() -> None:
    module = _load_module()
    prior = {
        "candidate_id": "cand_old",
        "failure_reason": "target_gate_not_full_pass",
        "mechanism_family": "result_identity_chain_guard",
        "mechanism": "result_identity_chain_guard_01",
        "file_targets": ["runner/successor_phase65.py"],
        "max_changed_files": 4,
        "max_changed_lines": 400,
        "comparator_variant_id": "spb_01",
        "failure_card_ref": "fc_tooling_001",
        "builder_constraint_scope": ["runner/**", "tests/**"],
    }
    candidate_delta = {
        "candidate_id": "cand_new",
        "action": "parameterized_backlog_retry",
        "mechanism_family": "result_identity_chain_guard",
        "mechanism": "result_identity_chain_guard_02",
        "file_targets": ["runner/successor_phase65.py", "tests/test_phase65_measurement_grading.py"],
        "max_changed_files": 5,
        "max_changed_lines": 400,
        "comparator_variant_id": "spb_01",
        "failure_card_ref": "fc_tooling_001",
        "builder_constraint_scope": ["runner/**", "tests/**"],
    }
    result = module.evaluate_candidate_novelty(candidate_delta, _memory([prior]))
    assert result["allow_build"] is True
    assert result["decision"] == "allow_retry_with_delta"
    assert result["bypass"]["requested"] is True
    assert result["bypass"]["allowed"] is True
    assert set(result["bypass"]["delta_fields"]) >= {"file_targets", "mutation_budget"}

from __future__ import annotations

from aether.solver_facing_projection import solver_facing_factual_defect_projection


def _finding(**overrides):
    row = {
        "finding_id": "vf-example",
        "verdict": "needs_repair",
        "summary": "The review interprets requirement R as unmet.",
        "evidence": ["observed value was 7"],
        "applies_to": ["result.json"],
        "observed_task_state_generation": 3,
        "supporting_inspection_ids": [],
    }
    row.update(overrides)
    return row


def test_unsupported_review_interpretation_is_not_factualized_into_world_defect() -> None:
    [row] = solver_facing_factual_defect_projection(
        [_finding()], current_step=5, current_task_state_generation=3,
        witness_handles={"vf-example": "receipt:witness"},
    )
    assert row["state"] == "review_claim_needs_repair"
    assert row["epistemic_status"] == "review_interpretation_without_direct_witness"
    assert row["semantic_authority"] == "raw_user_task"
    assert row["challenged_requirement_status"] == "review_interpretation_against_raw_user_task"
    assert row["coverage_status"] == "no_explicit_support_refs"
    assert row["supporting_observation_count"] == 0
    assert row["actual_observed_result_status"] == "review_reported_observation_without_explicit_inspection_ref"
    assert row["expected_result_status"] == "not_separately_task_grounded_by_reviewer"
    assert row["currentness"] == "current_candidate"
    assert row["observations"] == ["observed value was 7"]
    assert row["finding_id"] == "cf-example"
    assert row["witness_handle"] == "receipt:witness"
    assert row["witness_access"] == "read_output"
    assert "repair_instruction" not in row


def test_inspection_linked_review_claim_exposes_support_coverage_without_strategy() -> None:
    [row] = solver_facing_factual_defect_projection(
        [_finding(supporting_inspection_ids=["inspection:4:0:read_file"])],
        current_step=5,
        current_task_state_generation=3,
    )
    assert row["epistemic_status"] == "review_claim_with_inspection_support"
    assert row["coverage_status"] == "explicit_support_refs_present"
    assert row["supporting_observation_count"] == 1
    assert row["actual_observed_result_status"] == "inspection_linked_review_observation"


def test_stale_review_claim_is_visibly_bound_to_historical_candidate_generation() -> None:
    [row] = solver_facing_factual_defect_projection(
        [_finding(observed_task_state_generation=2)],
        current_step=8,
        current_task_state_generation=4,
    )
    assert row["candidate_generation"] == 2
    assert row["currentness"] == "historical_candidate"


def test_missing_evidence_review_remains_epistemically_incomplete() -> None:
    [row] = solver_facing_factual_defect_projection(
        [_finding(verdict="uncertain_missing_evidence", evidence=[])],
        current_step=5,
        current_task_state_generation=3,
    )
    assert row["state"] == "review_evidence_incomplete"
    assert row["epistemic_status"] == "missing_or_inconclusive_evidence"
    assert row["actual_observed_result_status"] == "not_reported_by_reviewer"

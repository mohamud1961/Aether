from __future__ import annotations

import json

from aether.inspection_feedback_projection import (
    MAX_FACT_BYTES,
    solver_facing_inspection_observation,
)
from aether.solver_facing_projection import solver_facing_factual_defect_projection


def _project(result: dict, *, admissibility: str = "direct_admissible") -> dict:
    return solver_facing_inspection_observation(
        result,
        task_state_generation=7,
        admissibility=admissibility,
        observation_type="content_observation",
        target_identity="path:/app/x.txt",
        observation_valid=True,
        actual_evidence_class="exact_content",
    )


def test_file_projection_preserves_task_content_but_drops_internal_plumbing() -> None:
    result = {
        "request_id": "reviewer-private-id",
        "kind": "read_file",
        "path": "/app/x.txt",
        "excerpt": "literal verifier token belongs to task bytes\n",
        "content_hash": "abc123",
        "bytes": 44,
        "executed_in": "verifier_overlay",
        "observation_origin": "verifier_executor_surface",
        "command": "cat hidden",
    }
    fact = _project(result)
    assert fact["observation_kind"] == "file_content_observation"
    assert fact["excerpt"] == "literal verifier token belongs to task bytes\n"
    assert fact["path"] == "/app/x.txt"
    assert fact["task_state_generation"] == 7
    for forbidden in ("request_id", "executed_in", "observation_origin", "command"):
        assert forbidden not in fact


def test_internal_receipt_metadata_is_neutralized_without_rewriting_excerpt() -> None:
    result = {
        "kind": "inspect_recent_receipts",
        "rows": [{
            "kind": "model_verifier_result",
            "failure_class": "reviewer_tool_execution_failed",
            "summary": "model_verifier_result recorded reviewer_tool failure",
            "excerpt": "task file literally says model_verifier_result",
            "success": False,
        }],
        "matching_count": 1,
        "returned_count": 1,
    }
    fact = solver_facing_inspection_observation(
        result,
        task_state_generation=3,
        admissibility="direct_admissible",
        observation_type="metadata",
        target_identity="target:opaque",
        observation_valid=True,
    )
    row = fact["rows"][0]
    rendered_metadata = " ".join(str(row[key]) for key in ("kind", "failure_class", "summary"))
    assert "model_verifier" not in rendered_metadata
    assert "reviewer_tool" not in rendered_metadata
    assert row["excerpt"] == "task file literally says model_verifier_result"


def test_exploratory_or_invalid_result_is_not_solver_factual_support() -> None:
    base = {"kind": "overlay_write_fixture", "path": "fixture.json", "success": True}
    assert solver_facing_inspection_observation(
        base,
        task_state_generation=1,
        admissibility="exploratory",
        observation_type="execution_result",
        target_identity="path:fixture.json",
        observation_valid=True,
    ) == {}
    assert solver_facing_inspection_observation(
        {"kind": "read_file", "path": "x", "excerpt": "x"},
        task_state_generation=1,
        admissibility="direct_admissible",
        observation_type="content_observation",
        target_identity="path:x",
        observation_valid=False,
    ) == {}


def test_projection_stays_inside_solver_fact_budget() -> None:
    result = {
        "kind": "overlay_run_command",
        "stdout": "x" * 50000,
        "stderr": "y" * 50000,
        "exit_code": 1,
        "timed_out": False,
    }
    fact = solver_facing_inspection_observation(
        result,
        task_state_generation=2,
        admissibility="verdict_eligible",
        observation_type="execution_result",
        target_identity="target:opaque",
        observation_valid=True,
    )
    assert fact["measurement_authority"] == "independently_executed_measurement_not_task_semantics"
    assert len(json.dumps(fact, sort_keys=True, default=str).encode("utf-8")) <= MAX_FACT_BYTES
    assert "command" not in fact


def test_finding_projection_marks_support_historical_after_state_generation_changes() -> None:
    raw = [{
        "finding_id": "vf-one",
        "verdict": "needs_repair",
        "summary": "claim",
        "evidence": ["review interpretation"],
        "supporting_inspection_ids": ["inspection:1"],
        "observed_task_state_generation": 4,
    }]
    facts = {
        "vf-one": [{
            "observation_kind": "file_content_observation",
            "task_state_generation": 4,
            "excerpt": "old bytes",
        }],
    }
    row = solver_facing_factual_defect_projection(
        raw,
        current_step=10,
        current_task_state_generation=5,
        witness_facts=facts,
    )[0]
    assert row["epistemic_status"] == "review_claim_with_historical_factual_support"
    assert row["actual_observed_result_status"] == "historical_factual_inspection_only"
    assert row["supporting_factual_observations"][0]["currentness"] == "historical_candidate"
    assert row["review_claim_observations"] == ["review interpretation"]

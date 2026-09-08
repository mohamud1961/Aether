from __future__ import annotations
import json
from pathlib import Path


def _fixture(tmp_path: Path, *, wrong_previous: bool = False) -> Path:
    evidence = tmp_path / "evidence"
    run_id = "computer-continuity-fixture"
    trial = evidence / run_id / "harbor" / run_id / "task__abc"
    agent = trial / "agent"
    agent.mkdir(parents=True)
    run = {
        "status": "completed",
        "step": 3,
        "blockers": [],
        "receipt_records": [],
        "run_metrics": {},
        "runtime_identity": {"model_profile": {"solver_reasoning_effort": "high", "verifier_reasoning_effort": "low"}},
        "model_call_telemetry": [
            {
                "role": "solver", "status": "completed", "response_id": "r1",
                "pcr_continuity_request_previous_response_id": None,
                "pcr_continuity_prior_call_id_match_count": 0,
                "pcr_continuity_current_boundary_function_output_match_count": 0,
                "pcr_continuity_request_input_item_types": ["message:user"],
            },
            {
                "role": "solver", "status": "completed", "response_id": "r2",
                "pcr_continuity_request_previous_response_id": "wrong" if wrong_previous else "r1",
                "pcr_continuity_prior_call_id_match_count": 0,
                "pcr_continuity_current_boundary_function_output_match_count": 0,
                "pcr_continuity_request_input_item_types": ["computer_call_output", "message:user"],
            },
            {
                "role": "solver", "status": "completed", "response_id": "r3",
                "pcr_continuity_request_previous_response_id": "r2",
                "pcr_continuity_prior_call_id_match_count": 1,
                "pcr_continuity_current_boundary_function_output_match_count": 1,
                "pcr_continuity_request_input_item_types": ["function_call_output"],
            },
        ],
    }
    x0 = {
        "status": "OBSERVED_NO_MODEL_FACING_BEHAVIOR_CHANGE",
        "provider": {
            "attempt_count": 3, "failed_attempt_count": 0, "compaction_event_count": 0,
            "attempts": [
                {"status": "completed", "role": "solver", "response_id": "r1"},
                {"status": "completed", "role": "solver", "response_id": "r2"},
                {"status": "completed", "role": "solver", "response_id": "r3"},
            ],
        },
        "context": {"calls": []},
        "receipts": {},
    }
    result = {
        "task_name": "fixture-task",
        "started_at": "2026-09-07T00:00:00Z",
        "finished_at": "2026-09-07T00:00:03Z",
        "exception_info": None,
        "agent_result": {"n_input_tokens": 1, "n_cache_tokens": 0, "n_output_tokens": 1, "cost_usd": None},
        "verifier_result": {"rewards": {"reward": 1.0}},
    }
    (agent / "aether_run_record.json").write_text(json.dumps(run), encoding="utf-8")
    (agent / "aether_x0_observability.json").write_text(json.dumps(x0), encoding="utf-8")
    (trial / "result.json").write_text(json.dumps(result), encoding="utf-8")
    controller = {
        "status": "executed_valid", "run_id": run_id, "evidence_root": str(evidence),
        "task_id": "fixture-task", "child_custody": {"valid": True},
    }
    cp = tmp_path / "controller.json"
    cp.write_text(json.dumps(controller), encoding="utf-8")
    return cp


def test_computer_call_output_is_valid_continuation_boundary(tmp_path: Path) -> None:
    from evals.performance.collect import collect_completed_run
    row = collect_completed_run(_fixture(tmp_path))
    assert row["solver_previous_response_chain_intact"] is True


def test_computer_continuation_still_requires_exact_previous_response_identity(tmp_path: Path) -> None:
    from evals.performance.collect import collect_completed_run
    row = collect_completed_run(_fixture(tmp_path, wrong_previous=True))
    assert row["solver_previous_response_chain_intact"] is False

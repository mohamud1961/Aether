from evals.performance.phase_f_anomaly_forensics import continuity, project


def _solver(response_id, previous=None, prior=1, boundary=1, status="completed"):
    return {
        "role": "solver",
        "status": status,
        "response_id": response_id,
        "pcr_continuity_request_previous_response_id": previous,
        "pcr_continuity_prior_call_id_match_count": prior,
        "pcr_continuity_current_boundary_function_output_match_count": boundary,
        "native_tool_name": "run_command",
    }


def test_continuity_accepts_fresh_then_exact_chain():
    run = {"model_call_telemetry": [_solver("r1"), _solver("r2", "r1"), _solver("r3", "r2")]}
    out = continuity(run)
    assert out["intact"] is True
    assert out["violations"] == []


def test_continuity_fails_closed_on_missing_previous_response():
    run = {"model_call_telemetry": [_solver("r1"), _solver("r2", None)]}
    out = continuity(run)
    assert out["intact"] is False
    assert out["violations"][0]["reason"] == "missing_previous_response_id"


def test_projection_extracts_provider_and_verifier_anomalies_only_from_completed_evidence():
    run = {
        "status": "completed",
        "step": 4,
        "model_call_telemetry": [
            _solver("r1"),
            _solver("", status="failed") | {"error": "server_error", "attempt_ordinal": 1},
            {"role": "verifier", "status": "completed", "response_id": "v1", "native_tool_name": "verifier_turn"},
        ],
        "model_parse_errors": [{"role": "verifier", "error": "bad verifier shape"}],
        "run_metrics": {"verifier_parse_error_count": 1},
        "receipt_records": [{"kind": "advisory_review_unavailable", "payload": {"status": "blocked", "reason": "test"}}],
    }
    out = project(run)
    assert out["status"] == "completed"
    assert out["solver_continuity"]["intact"] is True
    assert len(out["provider_failures"]) == 1
    assert len(out["verifier_telemetry"]) == 1
    assert len(out["model_parse_errors"]) == 1
    assert out["relevant_receipts"][0]["kind"] == "advisory_review_unavailable"

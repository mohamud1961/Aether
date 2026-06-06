from __future__ import annotations

import json

from runner import successor_phase65_verification_recovery_followup as mod


def _record(
    *,
    run_id: str,
    variant_id: str,
    closure_contract_status: str,
    task_truth_status: str,
    verifier_repair_status: str,
    latest_status: str | None,
    failure_source: str,
    unresolved_blockers: list[str],
    eval_id: str = "tb_style_verifier_fail_then_repair_v1",
) -> dict[str, object]:
    latest = None if latest_status is None else {"status": latest_status}
    required = ["/app/output.txt", "/app/verify.sh"] if latest_status is not None else ["/app/invoices/summary.csv"]
    return {
        "run_id": run_id,
        "eval_id": eval_id,
        "variant_id": variant_id,
        "closure_contract_status": closure_contract_status,
        "task_truth_status": task_truth_status,
        "failure_source": failure_source,
        "closure_state": {
            "required_deliverables": required,
            "verifier_attempts": [] if latest is None else [{"status": "fail"}, {"status": latest_status}],
            "latest_verifier_result": latest,
            "verifier_repair_status": verifier_repair_status,
            "unresolved_blockers": unresolved_blockers,
        },
    }


def test_verification_recovery_followup_launch_writes_required_artifacts(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    records = [
        _record(
            run_id="ready",
            variant_id="candidate_plus_path_normalized_verifier_repair_projection_01",
            closure_contract_status="pass",
            task_truth_status="pass",
            verifier_repair_status="repaired_and_reran_to_pass",
            latest_status="pass",
            failure_source="none",
            unresolved_blockers=[],
        ),
        _record(
            run_id="partial",
            variant_id="candidate_plus_app_workspace_path_normalizer_01",
            closure_contract_status="partial",
            task_truth_status="pass",
            verifier_repair_status="repaired_and_reran_to_pass",
            latest_status="pass",
            failure_source="none",
            unresolved_blockers=["final_answer_missing_verifier_evidence"],
        ),
        _record(
            run_id="external",
            variant_id="candidate_plus_path_normalized_verifier_repair_projection_01",
            closure_contract_status="pass",
            task_truth_status="fail",
            verifier_repair_status="not_required",
            latest_status=None,
            failure_source="raw_task_capability_limit",
            unresolved_blockers=[],
            eval_id="terminalbench_public_financial-document-processor",
        ),
    ]
    (source / mod.RESULT_RECORDS).write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    (source / mod.SOURCE_SCORE).write_text(json.dumps({"selected_recommendation": "completion_followup4_sufficient_for_parallel_family_launch", "split_ready": True, "invalid_run_count": 0}), encoding="utf-8")
    (source / mod.SOURCE_REPORT).write_text(json.dumps({"comparison_set": ["a", "b"], "carry_forward_baseline_variant": "candidate_plus_path_normalized_verifier_repair_projection_01", "merged_variant": "candidate_plus_path_normalized_exact_target_projection_01"}), encoding="utf-8")
    (source / mod.SOURCE_FAILURE).write_text(json.dumps({"failure_count": 1}), encoding="utf-8")
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)

    result = mod.launch_phase65_verification_recovery_followup(output_dir=tmp_path / "out", source_dir=source)

    assert result["selected_recommendation"] == "verification_recovery_followup_partial_uplift_verification_still_open"
    required = {
        "phase65_verification_recovery_followup_score_envelope.json",
        "phase65_verification_recovery_followup_report.json",
        "phase65_verification_recovery_followup_trace_report.json",
        "phase65_verification_recovery_followup_failure_source_report.json",
        "phase65_verification_recovery_followup_deep_trace_analysis.md",
        "phase65_verification_recovery_followup_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in (tmp_path / "out").iterdir()})


def test_verification_recovery_followup_score_marks_partial_when_truthful_partial_rows_remain():
    score = mod._score(
        [
            _record(
                run_id="ready",
                variant_id="candidate_plus_path_normalized_verifier_repair_projection_01",
                closure_contract_status="pass",
                task_truth_status="pass",
                verifier_repair_status="repaired_and_reran_to_pass",
                latest_status="pass",
                failure_source="none",
                unresolved_blockers=[],
            ),
            _record(
                run_id="partial",
                variant_id="candidate_plus_path_normalized_exact_target_projection_01",
                closure_contract_status="partial",
                task_truth_status="pass",
                verifier_repair_status="repaired_and_reran_to_pass",
                latest_status="pass",
                failure_source="none",
                unresolved_blockers=["final_answer_missing_artifact_path"],
            ),
        ],
        source_score={"selected_recommendation": "completion_followup4_sufficient_for_parallel_family_launch", "split_ready": True, "invalid_run_count": 0},
    )
    assert score["repair_discipline_pass_count"] == 2
    assert score["truthful_partial_count"] == 1
    assert score["verification_partial_count"] == 1
    assert score["selected_recommendation"] == "verification_recovery_followup_partial_uplift_verification_still_open"


def test_verification_recovery_followup_score_is_ready_when_all_verifier_rows_close_cleanly():
    score = mod._score(
        [
            _record(
                run_id="ready-a",
                variant_id="candidate_plus_path_normalized_verifier_repair_projection_01",
                closure_contract_status="pass",
                task_truth_status="pass",
                verifier_repair_status="repaired_and_reran_to_pass",
                latest_status="pass",
                failure_source="none",
                unresolved_blockers=[],
            ),
            _record(
                run_id="ready-b",
                variant_id="candidate_plus_path_normalized_exact_target_projection_01",
                closure_contract_status="pass",
                task_truth_status="pass",
                verifier_repair_status="repaired_and_reran_to_pass",
                latest_status="pass",
                failure_source="none",
                unresolved_blockers=[],
            ),
        ],
        source_score={"selected_recommendation": "completion_followup4_sufficient_for_parallel_family_launch", "split_ready": True, "invalid_run_count": 0},
    )
    assert score["verification_partial_count"] == 0
    assert score["selected_recommendation"] == "verification_recovery_followup_ready_for_family_reducer"


def test_verification_recovery_followup_blocked_when_source_artifacts_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    result = mod.launch_phase65_verification_recovery_followup(output_dir=tmp_path / "out", source_dir=tmp_path / "missing", execute=False)
    assert result["blocked"] is True
    score = json.loads((tmp_path / "out" / "phase65_verification_recovery_followup_score_envelope.json").read_text(encoding="utf-8"))
    assert score["selected_recommendation"] == "verification_recovery_followup_blocked"

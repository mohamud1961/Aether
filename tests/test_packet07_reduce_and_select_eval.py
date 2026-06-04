from __future__ import annotations

import json

from runner import packet07_reduce_and_select_eval as mod


def test_prepare_mode_writes_fixture_and_artifact_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)

    result = mod.launch_reduce_and_select_eval(output_dir=tmp_path, execute=False)

    assert result["status"] == "prepared"
    fixture = tmp_path / "fixture_workspace"
    assert (fixture / "grounded_records.jsonl").exists()
    assert (fixture / "reduction_policy.json").exists()
    required = {
        "reduce_and_select_v1_run_spec.json",
        "reduce_and_select_v1_result_records.jsonl",
        "reduce_and_select_v1_score_envelope.json",
        "reduce_and_select_v1_summary.json",
        "reduce_and_select_v1_summary_table.md",
        "reduce_and_select_v1_decision_memo.md",
        "reduce_and_select_v1_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({p.name for p in tmp_path.iterdir()})

    run_spec = json.loads((tmp_path / "reduce_and_select_v1_run_spec.json").read_text(encoding="utf-8"))
    assert run_spec["eval_id"] == mod.EVAL_ID
    assert run_spec["route_id"] == mod.ROUTE_ID
    assert run_spec["models"][0] == "gpt-5.4-mini"
    assert run_spec["contract"]["task_id"] == mod.EVAL_ID


def test_deterministic_grade_and_summary_path():
    grade_ok = mod.grade_reduce_and_select_answer(final_answer="The scalar is 29.375", expected_scalar="29.375")
    grade_bad = mod.grade_reduce_and_select_answer(final_answer="29.100", expected_scalar="29.375")
    assert grade_ok["verdict"] == "pass"
    assert grade_bad["verdict"] == "fail"
    assert "scalar_mismatch" in grade_bad["reason_codes"]

    records = [mod._record_for_ceiling({"expected_scalar": "29.375", "winner_candidate_id": "c02", "eligible_count": 4})]
    score = mod._score_envelope(records=records, planned_model_runs=2, execute=False, expected_scalar="29.375")
    summary = mod._summary(records, score)
    assert score["ceiling_pass"] is True
    assert score["executed_model_runs"] == 0
    assert summary["status"] == "ready_for_model_runs"

from __future__ import annotations

import json

from runner import packet07_answer_check_eval as mod


def test_prepare_mode_writes_fixture_and_artifact_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    result = mod.launch_packet07_answer_check_eval(output_dir=tmp_path, execute=False)

    assert result["status"] == "prepared"
    fixture = tmp_path / "fixture_workspace"
    assert (fixture / "reduced_evidence.json").exists()
    assert (fixture / "candidate_answer.json").exists()
    assert (fixture / "answer_policy.json").exists()
    expected = {
        "answer_check_v1_run_spec.json",
        "answer_check_v1_result_records.jsonl",
        "answer_check_v1_score_envelope.json",
        "answer_check_v1_summary.json",
        "answer_check_v1_summary_table.md",
        "answer_check_v1_decision_memo.md",
        "answer_check_v1_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert expected.issubset({p.name for p in tmp_path.iterdir()})

    run_spec = json.loads((tmp_path / "answer_check_v1_run_spec.json").read_text(encoding="utf-8"))
    assert run_spec["eval_id"] == mod.EVAL_ID
    assert run_spec["route_id"] == mod.ROUTE_ID
    assert run_spec["models"][0] == "gpt-5.4-mini"
    assert run_spec["models"][1] == "gpt-5.3-codex"
    assert run_spec["ground_truth"]["expected_final_value"] == "37"


def test_deterministic_grade_and_summary_path(tmp_path):
    spec = mod._spec()
    workspace = tmp_path / "fixture"
    mod._seed_workspace(workspace, spec["workspace_files"])
    ceiling = mod._deterministic_ceiling(workspace)

    assert ceiling["expected_final_value"] == "37"
    assert ceiling["proposed_answer_supported"] is False

    grade_ok = mod.grade_answer_check_response(final_answer="final value: 37", expected_final_value="37")
    grade_bad = mod.grade_answer_check_response(final_answer="37.5", expected_final_value="37")
    assert grade_ok["verdict"] == "pass"
    assert grade_bad["verdict"] == "fail"
    assert "final_value_mismatch" in grade_bad["reason_codes"]

    records = [mod._record_for_ceiling(ceiling)]
    score = mod._score_envelope(records=records, planned_model_runs=2, execute=False, expected_final_value="37")
    summary = mod._summary(records, score, ceiling)
    assert score["ceiling_pass"] is True
    assert score["executed_model_runs"] == 0
    assert summary["status"] == "ready_for_model_runs"

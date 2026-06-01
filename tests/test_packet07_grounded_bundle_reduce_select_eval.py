from __future__ import annotations

import json

from runner import packet07_grounded_bundle_reduce_select_eval as mod


def test_prepare_mode_writes_fixture_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    result = mod.launch_grounded_bundle_reduce_select_eval(output_dir=tmp_path, execute=False)

    assert result["status"] == "prepared"
    fixture = tmp_path / "fixture_workspace"
    assert (fixture / "anchor_profile.json").exists()
    assert (fixture / "residents.jsonl").exists()
    assert (fixture / "bank_accounts.jsonl").exists()
    expected = {
        "grounded_bundle_reduce_select_v1_run_spec.json",
        "grounded_bundle_reduce_select_v1_result_records.jsonl",
        "grounded_bundle_reduce_select_v1_score_envelope.json",
        "grounded_bundle_reduce_select_v1_summary.json",
        "grounded_bundle_reduce_select_v1_summary_table.md",
        "grounded_bundle_reduce_select_v1_decision_memo.md",
        "grounded_bundle_reduce_select_v1_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert expected.issubset({p.name for p in tmp_path.iterdir()})

    run_spec = json.loads((tmp_path / "grounded_bundle_reduce_select_v1_run_spec.json").read_text(encoding="utf-8"))
    assert run_spec["eval_id"] == mod.EVAL_ID
    assert run_spec["route_id"] == mod.ROUTE_ID
    assert run_spec["models"][0] == "gpt-5.4-mini"
    assert run_spec["models"][1] == "gpt-5.3-codex"
    assert run_spec["ground_truth"]["final_scalar"] == "14"


def test_ceiling_and_grader_behavior(tmp_path):
    spec = mod._spec()
    workspace = tmp_path / "fixture"
    mod._seed_workspace(workspace, spec["workspace_files"])
    ceiling = mod._deterministic_ceiling(workspace)

    assert ceiling["winner_owner_id"] == "pers-0406"
    assert ceiling["target_state"] == "Indiana"
    assert ceiling["expected_scalar"] == "14"

    grade_ok = mod.grade_grounded_bundle_reduce_select_answer(final_answer="final scalar 14", expected_scalar="14")
    grade_bad = mod.grade_grounded_bundle_reduce_select_answer(final_answer="13", expected_scalar="14")
    assert grade_ok["verdict"] == "pass"
    assert grade_bad["verdict"] == "fail"
    assert "scalar_mismatch" in grade_bad["reason_codes"]

    records = [mod._record_for_ceiling(ceiling)]
    score = mod._score_envelope(records=records, planned_model_runs=2, execute=False, expected_scalar="14")
    summary = mod._summary(records, score)
    assert score["ceiling_pass"] is True
    assert score["executed_model_runs"] == 0
    assert summary["status"] == "ready_for_model_runs"

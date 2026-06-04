from __future__ import annotations

import json

from runner.successor_phase65_measurement_followup import launch_phase65_measurement_followup


def test_phase65_measurement_followup_writes_required_artifacts_and_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runner.successor_phase65_measurement_followup._record_ledger",
        lambda raw: None,
    )
    result = launch_phase65_measurement_followup(output_dir=tmp_path)

    assert result["selected_recommendation"] == "measurement_followup_completed_resume_phase65_board"
    required = {
        "phase65_measurement_followup_plan.md",
        "phase65_measurement_followup_contract_report.json",
        "phase65_measurement_followup_test_report.txt",
        "phase65_measurement_followup_proof_records.jsonl",
        "phase65_measurement_followup_score_envelope.json",
        "phase65_measurement_followup_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})
    report = json.loads((tmp_path / "phase65_measurement_followup_contract_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["contextbench"]["positive_rows_passed"] == 3
    assert report["contextbench"]["proxy_rows_rejected"] == 3
    assert report["public_terminalbench_regression_unit_tests"]["all_passed"] is True

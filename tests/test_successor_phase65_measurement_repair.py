from __future__ import annotations

import json

from runner.successor_phase65_measurement_repair import launch_phase65_measurement_repair


def test_phase65_measurement_repair_writes_required_artifacts_and_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runner.successor_phase65_measurement_repair._record_ledger",
        lambda raw: None,
    )
    result = launch_phase65_measurement_repair(output_dir=tmp_path)

    assert result["selected_recommendation"] == "measurement_repair_completed_resume_phase65_board"
    required = {
        "phase65_measurement_repair_plan.md",
        "phase65_measurement_repair_scope_report.md",
        "phase65_measurement_repair_contract_matrix.json",
        "phase65_measurement_repair_test_report.txt",
        "phase65_measurement_repair_proof_records.jsonl",
        "phase65_measurement_repair_score_envelope.json",
        "phase65_measurement_repair_trace_report.json",
        "phase65_measurement_repair_cost_report.json",
        "phase65_measurement_repair_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})
    matrix = json.loads((tmp_path / "phase65_measurement_repair_contract_matrix.json").read_text(encoding="utf-8"))
    assert matrix["status"] == "pass"
    assert all(row["status"] == "pass" for row in matrix["rows"])


def test_phase65_measurement_repair_proves_old_proxy_passes_now_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runner.successor_phase65_measurement_repair._record_ledger",
        lambda raw: None,
    )
    launch_phase65_measurement_repair(output_dir=tmp_path)
    records = [
        json.loads(line)
        for line in (tmp_path / "phase65_measurement_repair_proof_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    proxy_rows = [row for row in records if row["case_id"] == "old_proxy_pass_now_fail" or row["case_id"] == "legacy_proxy_rejected"]
    assert proxy_rows
    assert all(row["legacy_proxy_pass"] for row in proxy_rows)
    assert all(row["verdict"] == "fail" for row in proxy_rows)
    positive_rows = [row for row in records if row["case_id"] == "positive_control"]
    assert positive_rows
    assert all(row["verdict"] == "pass" for row in positive_rows)

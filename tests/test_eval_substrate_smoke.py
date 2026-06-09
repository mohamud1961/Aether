from __future__ import annotations

import json

from tools.run_eval_substrate_smoke import run_smoke


def test_eval_substrate_smoke_writes_pass_fail_rows_and_scoreboard(tmp_path):
    summary = run_smoke(tmp_path)

    pass_row = json.loads((tmp_path / "result_rows" / "pass.json").read_text(encoding="utf-8"))
    fail_row = json.loads((tmp_path / "result_rows" / "known_bad.json").read_text(encoding="utf-8"))
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["certification_claim"].startswith("none")
    assert pass_row["task_truth_status"] == "pass"
    assert pass_row["score"] == 1.0
    assert fail_row["task_truth_status"] == "fail"
    assert fail_row["failure_class"] == "verification_grading"
    assert fail_row["reason_codes"] == ["known_bad_visible_verifier_failed"]
    assert pass_row["environment_ref"]
    assert pass_row["artifact_refs"]
    assert pass_row["trace_refs"]
    assert fail_row["environment_ref"]
    assert fail_row["artifact_refs"]
    assert fail_row["trace_refs"]
    assert scoreboard["totals"] == {"pass": 1, "fail": 1, "invalid": 0, "total": 2}
    assert scoreboard["by_contamination_status"]["clean"]["total"] == 2

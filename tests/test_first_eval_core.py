from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runner.eval_substrate_contracts import FAILURE_CLASSES, validate_result_row, validate_task_pack
from tools.run_first_eval_core import CASE_IDS, FAMILIES, run_first_eval_core


def test_first_eval_core_generates_five_task_packs_and_case_rows(tmp_path):
    summary = run_first_eval_core(tmp_path, conversion_mode="diagnostic_conversion")

    assert summary["certification_claim"].startswith("none")
    assert summary["conversion_mode"] == "diagnostic_conversion"
    assert summary["diagnostic_conversion_status"] == "diagnostic_candidate_pending_certified_run"
    assert summary["row_count"] == 15
    assert set(summary["families"]) == {family["family"] for family in FAMILIES}
    assert "bfcl_tool_call_sentinel" in summary["families"]
    assert "structured_retrieval_reduction" in summary["families"]

    for path in summary["task_pack_paths"]:
        task_pack = json.loads(open(path, encoding="utf-8").read())
        validate_task_pack(task_pack)
        assert task_pack["admission_level"] == "draft"
        assert task_pack["conversion_mode"] == "diagnostic_conversion"
        assert task_pack["hidden_verifier"]["leak_hidden_checks_to_prompt"] is False
        assert task_pack["hidden_verifier"]["executed_artifacts_required_for_cases"] == list(CASE_IDS)
        assert task_pack["contamination_policy"]["public_benchmark_row"] is False
        assert task_pack["solver_reviewer_pack_contract"]["solver_pack_ref"] == "solver_pack/app"
        assert task_pack["solver_reviewer_pack_contract"]["reviewer_pack_ref"] == "reviewer_pack"
        assert "expected.json" in task_pack["solver_reviewer_pack_contract"]["solver_must_exclude"]
        assert (
            task_pack["solver_reviewer_pack_contract"]["diagnostic_status"]
            == "diagnostic_candidate_pending_certified_run"
        )

    rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "result_rows").glob("*.json"))
    ]
    assert len(rows) == 15
    assert all(validate_result_row(row) for row in rows)

    by_case = {row["run_id"].rsplit("-", 1)[1]: [] for row in rows}
    for row in rows:
        by_case[row["run_id"].rsplit("-", 1)[1]].append(row)

    assert {row["task_truth_status"] for row in by_case["ceiling"]} == {"pass"}
    assert {row["score"] for row in by_case["ceiling"]} == {1.0}
    assert {row["task_truth_status"] for row in by_case["baseline"]} == {"fail"}
    assert {row["task_truth_status"] for row in by_case["known_bad"]} == {"fail"}
    assert all(row["admission_level"] == "draft" for row in rows)
    assert all(
        row["admission_readiness"] == "diagnostic_candidate_pending_certified_run"
        for row in rows
    )
    assert all(row["certification_claim"].startswith("none") for row in rows)
    assert all(set(row["failure_class_set"]) == set(FAILURE_CLASSES) for row in rows)
    assert all(row["environment_ref"] for row in rows)
    assert all(row["artifact_refs"] for row in rows)
    assert all(row["trace_refs"] for row in rows)

    for row in rows:
        visible_output = json.loads(Path(row["verifier_ref"]).read_text(encoding="utf-8"))
        assert visible_output["visible_record"]["exit_code"] == 0
        hidden_output = json.loads(Path(row["hidden_verifier_ref"]).read_text(encoding="utf-8"))
        assert hidden_output["visible_record"]["command"].startswith("python3 hidden_verifier.py")
        run_case = row["run_id"].rsplit("-", 1)[1]
        if run_case == "ceiling":
            assert hidden_output["visible_record"]["exit_code"] == 0
        else:
            assert hidden_output["visible_record"]["exit_code"] != 0

        fixture_root = Path(row["environment_ref"]).parent.parent / "fixture_workspace"
        fixture_dirs = list(fixture_root.iterdir())
        assert len(fixture_dirs) == 1
        solver_root = fixture_dirs[0] / "solver_pack" / "app"
        reviewer_root = fixture_dirs[0] / "reviewer_pack"
        assert solver_root.exists()
        assert reviewer_root.exists()
        assert (reviewer_root / "hidden_tests" / "test_hidden_regressions.py").exists()
        assert (reviewer_root / "hidden_expected_values.json").exists()
        assert (reviewer_root / "ceiling.patch").exists()
        assert (reviewer_root / "known_bad_hardcode.patch").exists()
        assert (reviewer_root / "known_bad_test_edit.patch").exists()
        assert not (solver_root / "hidden_tests").exists()
        assert not (solver_root / "hidden_expected_values.json").exists()
        assert not (solver_root / "expected.json").exists()
        assert not (solver_root / "ceiling.patch").exists()
        assert not (solver_root / "known_bad_hardcode.patch").exists()
        assert not (solver_root / "known_bad_test_edit.patch").exists()

    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))
    assert scoreboard["row_count"] == 15
    assert scoreboard["totals"] == {"pass": 5, "fail": 10, "invalid": 0, "total": 15}
    assert set(scoreboard["by_family"]) == {family["family"] for family in FAMILIES}
    assert scoreboard["by_admission_level"]["draft"]["total"] == 15
    assert scoreboard["by_contamination_status"]["clean"]["total"] == 15


def test_first_eval_core_command_shape_only_stays_draft_debug(tmp_path):
    summary = run_first_eval_core(tmp_path, conversion_mode="command_shape_only")

    assert summary["conversion_mode"] == "command_shape_only"
    assert summary["diagnostic_conversion_status"] == "draft_command_shape_only"
    for row_path in sorted((tmp_path / "result_rows").glob("*.json")):
        row = json.loads(row_path.read_text(encoding="utf-8"))
        hidden_output = json.loads(Path(row["hidden_verifier_ref"]).read_text(encoding="utf-8"))
        assert row["admission_level"] == "draft"
        assert row["admission_readiness"] == "draft_command_shape_only"
        assert hidden_output["mode"] == "command_shape_only"
        assert hidden_output["executed"] is False

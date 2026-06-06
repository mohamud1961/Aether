from __future__ import annotations

import json
from pathlib import Path

from runner.atomic_eval_diagnostics import diagnose_atomic_row, run_atomic_eval_diagnostics
from runner.final_harness_eval_suite_adapter import load_final_suite_row_specs

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO_ROOT / "tracking/collab/final_harness_eval_suite/runs/20260529T184245Z"


def test_run_atomic_eval_diagnostics_writes_reports_for_representative_subset(tmp_path):
    output_root = tmp_path / "atomic_diag"
    summary = run_atomic_eval_diagnostics(
        repo_root=REPO_ROOT,
        row_ids=[
            "fsent_01_tool_call_bfcl_composite",
            "fhard_02_service_orchestration_flagship",
            "fhard_05_structured_retrieval_reduction",
            "fbench_acebench_normal_atom_bool_0",
            "fbench_contextbench_verified_06",
            "ftb_challenge_install_windows_3_11",
        ],
        output_root=output_root,
        result_run_root=RUN_ROOT,
    )

    assert summary["row_count"] == 6
    assert (output_root / "atomic_score_summary.json").exists()
    assert (output_root / "atomic_failure_matrix.md").exists()
    assert (output_root / "atomic_invalidity_report.md").exists()
    assert (output_root / "atomic_result_rows" / "fsent_01_tool_call_bfcl_composite.json").exists()

    score_summary = json.loads((output_root / "atomic_score_summary.json").read_text(encoding="utf-8"))
    assert score_summary["totals"] == {"pass": 4, "fail": 2, "total": 6}
    assert score_summary["by_source_kind"]["custom_task_pack"] == {"pass": 2, "fail": 1, "total": 3}
    assert score_summary["by_source_kind"]["benchmark_adapter:ACEBench"] == {"pass": 1, "fail": 0, "total": 1}
    assert score_summary["invalidity_counts"]["contamination_signal:missing contamination signal"] == 1
    assert score_summary["invalidity_counts"][
        "task_pack_load:unsupported TerminalBench task: install-windows-3.11"
    ] == 1

    custom_report = json.loads(
        (output_root / "atomic_result_rows" / "fsent_01_tool_call_bfcl_composite.json").read_text(encoding="utf-8")
    )
    terminalbench_report = json.loads(
        (output_root / "atomic_result_rows" / "ftb_challenge_install_windows_3_11.json").read_text(encoding="utf-8")
    )
    assert custom_report["status"] == "fail"
    assert "contamination_signal:missing contamination signal" in custom_report["invalidity_reasons"]
    assert terminalbench_report["status"] == "fail"
    assert "task_pack_load:unsupported TerminalBench task: install-windows-3.11" in terminalbench_report["invalidity_reasons"]


def test_atomic_eval_diagnostics_emits_level_aware_tests(tmp_path):
    output_root = tmp_path / "atomic_diag"
    run_atomic_eval_diagnostics(
        repo_root=REPO_ROOT,
        row_ids=[
            "fsent_01_tool_call_bfcl_composite",
            "fhard_02_service_orchestration_flagship",
            "fhard_05_structured_retrieval_reduction",
            "fbench_acebench_normal_atom_bool_0",
            "fbench_contextbench_verified_06",
            "ftb_challenge_install_windows_3_11",
        ],
        output_root=output_root,
        result_run_root=RUN_ROOT,
    )

    row = json.loads(
        (output_root / "atomic_result_rows" / "fhard_02_service_orchestration_flagship.json").read_text(encoding="utf-8")
    )
    summary = json.loads((output_root / "atomic_score_summary.json").read_text(encoding="utf-8"))

    assert [test["atomic_level"] for test in row["atomic_tests"]] == ["A0", "A1", "A2", "A3", "A4", "A5"]
    assert len(row["atomic_tests"]) == 6
    assert summary["atomic_level_counts"]["A1"] == {"pass": 4, "fail": 0, "invalid": 1, "blocked": 1, "total": 6}
    assert summary["atomic_level_counts"]["A2"]["blocked"] == 1
    assert summary["atomic_test_counts"]["micro_smoke"]["total"] == 6
    assert summary["promotion_blocking_counts"]["true"] > 0


def test_atomic_result_row_diagnostic_flags_missing_final_board(tmp_path):
    specs = {spec.row_id: spec for spec in load_final_suite_row_specs(REPO_ROOT)}
    spec = specs["fbench_acebench_normal_atom_bool_0"]

    result_run_root = tmp_path / "run"
    row_path = result_run_root / "result_rows" / f"{spec.row_id}.json"
    row_path.parent.mkdir(parents=True, exist_ok=True)
    row = json.loads((RUN_ROOT / "result_rows" / f"{spec.row_id}.json").read_text(encoding="utf-8"))
    row.pop("final_board")
    row_path.write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")

    diagnostic = diagnose_atomic_row(repo_root=REPO_ROOT, result_run_root=result_run_root, spec=spec)

    assert diagnostic.status == "fail"
    assert any(reason.startswith("final_board_contract:") or reason == "missing_final_board" for reason in diagnostic.invalidity_reasons)

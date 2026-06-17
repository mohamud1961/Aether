from __future__ import annotations

import csv
from pathlib import Path

from runner.phase65_measurement_contracts import load_extract_moves_contract
from runner.phase65_measurement_grading import (
    grade_bfcl_ground_truth_answer,
    grade_contextbench_verified_answer,
    grade_extract_moves_workspace,
    grade_public_terminalbench_workspace,
    grade_verifier_repair_workspace,
    grade_work_pocket_handoff_workspace,
)
from runner.successor_phase65_measurement_repair import _seed_public_terminalbench_workspace


def test_contextbench_requires_structured_answer_not_snippet_presence():
    row = next(
        csv.DictReader(
            Path("research/sources/codebases/ContextBench/data/Verified.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )
    expected_repo = row["original_inst_id"].split("__", 1)[0]
    structured = (
        "{"
        f'"original_inst_id": "{row["original_inst_id"]}", '
        f'"language": "{row["language"]}", '
        f'"status": "{row["status"]}", '
        f'"gold_context_length": "{row["gold_context_length"]}", '
        f'"commit": "{row["commit"]}", '
        f'"repo_or_file_family": "{expected_repo}"'
        "}"
    )
    proxy = f"{row['original_inst_id']} {row['language']} {row['status']} {row['commit']}"

    assert grade_contextbench_verified_answer(structured, row)["verdict"] == "pass"
    proxy_grade = grade_contextbench_verified_answer(proxy, row)
    assert proxy_grade["verdict"] == "fail"
    assert "contextbench_original_inst_id_mismatch" in proxy_grade["reason_codes"] or "contextbench_repo_or_file_family_mismatch" in proxy_grade["reason_codes"]


def test_extract_moves_requires_solution_artifact_and_similarity(tmp_path):
    contract = load_extract_moves_contract("/Users/mohamud/Downloads/terminalbench/official_tasks/extract-moves-from-video")
    passing = tmp_path / "pass"
    failing = tmp_path / "fail"
    passing.mkdir()
    failing.mkdir()
    (passing / "solution.txt").write_text(contract["expected_solution"], encoding="utf-8")
    (failing / "task_evidence_summary.md").write_text("solution.txt verifier moves", encoding="utf-8")

    assert grade_extract_moves_workspace(passing, task_id="extract-moves-from-video")["verdict"] == "pass"
    fail_grade = grade_extract_moves_workspace(failing, task_id="extract-moves-from-video")
    assert fail_grade["verdict"] == "fail"
    assert fail_grade["reason_codes"] == ["missing_solution_file"]


def test_contextbench_accepts_multiple_structured_rows():
    rows = list(
        csv.DictReader(
            Path("research/sources/codebases/ContextBench/data/Verified.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )[:3]
    for row in rows:
        expected_repo = row["original_inst_id"].split("__", 1)[0]
        answer = "\n".join(
            [
                f"original_inst_id: {row['original_inst_id']}",
                f"language: {row['language']}",
                f"status: {row['status']}",
                f"gold_context_length: {row['gold_context_length']}",
                f"commit: {row['commit']}",
                f"repo_or_file_family: {expected_repo}",
            ]
        )
        assert grade_contextbench_verified_answer(answer, row)["verdict"] == "pass"


def test_fix_git_regression_grader_direct_unit(tmp_path):
    workspace = tmp_path / "fix-git"
    _seed_public_terminalbench_workspace(workspace, "fix-git")
    assert grade_public_terminalbench_workspace(workspace, task_id="fix-git")["verdict"] == "pass"
    (workspace / "personal-site/_includes/about.md").write_text("wrong\n", encoding="utf-8")
    fail_grade = grade_public_terminalbench_workspace(workspace, task_id="fix-git")
    assert fail_grade["verdict"] == "fail"
    assert fail_grade["reason_codes"] == ["fix_git_patch_mismatch"]


def test_regex_log_regression_grader_direct_unit(tmp_path):
    workspace = tmp_path / "regex-log"
    _seed_public_terminalbench_workspace(workspace, "regex-log")
    assert grade_public_terminalbench_workspace(workspace, task_id="regex-log")["verdict"] == "pass"
    (workspace / "regex.txt").write_text("([", encoding="utf-8")
    fail_grade = grade_public_terminalbench_workspace(workspace, task_id="regex-log")
    assert fail_grade["verdict"] == "fail"
    assert fail_grade["reason_codes"] == ["regex_invalid"]


def test_financial_document_processor_regression_grader_direct_unit(tmp_path):
    workspace = tmp_path / "financial-document-processor"
    _seed_public_terminalbench_workspace(workspace, "financial-document-processor")
    assert grade_public_terminalbench_workspace(workspace, task_id="financial-document-processor")["verdict"] == "pass"
    (workspace / "documents/leak.txt").write_text("leftover\n", encoding="utf-8")
    fail_grade = grade_public_terminalbench_workspace(workspace, task_id="financial-document-processor")
    assert fail_grade["verdict"] == "fail"
    assert fail_grade["reason_codes"] == ["financial_documents_not_empty"]


def test_bfcl_strict_ground_truth_requires_complete_ordered_calls():
    ground_truth = [
        [],
        [
            "get_zipcode_based_on_city(city='Rivermist')",
            "get_zipcode_based_on_city(city='Stonebrook')",
            "estimate_distance(cityA='83214', cityB='74532')",
        ],
        ["estimate_drive_feasibility_by_mileage(distance=750.0)"],
    ]
    full_answer = "\n".join(
        [
            "1. get_zipcode_based_on_city(city='Rivermist')",
            "2. get_zipcode_based_on_city(city='Stonebrook')",
            "3. estimate_distance(cityA='83214', cityB='74532')",
            "4. estimate_drive_feasibility_by_mileage(distance=750.0)",
        ]
    )
    proxy_answer = "\n".join(
        [
            "estimate_distance(cityA='83214', cityB='74532')",
            "estimate_drive_feasibility_by_mileage(distance=750.0)",
        ]
    )

    assert grade_bfcl_ground_truth_answer(full_answer, ground_truth)["verdict"] == "pass"
    proxy_grade = grade_bfcl_ground_truth_answer(proxy_answer, ground_truth)
    assert proxy_grade["verdict"] == "fail"
    assert "bfcl_missing_required_calls" in proxy_grade["reason_codes"]


def test_work_pocket_grader_accepts_float_formatted_total(tmp_path):
    workspace = tmp_path / "work-pocket"
    workspace.mkdir()
    artifact = workspace / "artifacts/work_pocket.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"verified_total": "50.00", "verification_status": "verified", "evidence_paths": ["/app/case/a.txt"]}\n',
        encoding="utf-8",
    )

    grade = grade_work_pocket_handoff_workspace(
        workspace=workspace,
        result_text="Verified total 50 at artifacts/work_pocket.json",
        artifact_relpath="artifacts/work_pocket.json",
        expected_total=50,
        required_evidence_paths=["/app/case/a.txt"],
    )

    assert grade["verdict"] == "pass"


def test_verifier_repair_grader_normalizes_app_paths_to_workspace(tmp_path):
    workspace = tmp_path / "verify"
    workspace.mkdir()
    (workspace / "output.txt").write_text("status=complete", encoding="utf-8")
    (workspace / "verify.sh").write_text(
        "#!/bin/bash\nif [ \"$(cat /app/output.txt)\" = \"status=complete\" ]; then echo PASS; exit 0; fi\nexit 1\n",
        encoding="utf-8",
    )

    grade = grade_verifier_repair_workspace(workspace=workspace, verifier_relpath="verify.sh")

    assert grade["verdict"] == "pass"

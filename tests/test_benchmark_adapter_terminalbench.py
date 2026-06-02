from __future__ import annotations

import json

from runner.benchmark_adapter_terminalbench import (
    ADAPTER_AUTHORITY_DETAIL,
    ADAPTER_AUTHORITY_LABEL,
    ADAPTER_LABEL,
    build_hidden_truth_payload,
    build_result_row_for_grade,
    build_task_pack,
    build_verifier_provenance,
    grade_terminalbench_case_equivalent,
    hidden_truth_ref_for_task,
    load_selected_cases,
    official_solution_regex,
    smoke_control_regex,
    verifier_provenance_ref_for_task,
)
from runner.eval_substrate_contracts import validate_result_row
from tools.run_benchmark_adapter_terminalbench_smoke import run_benchmark_adapter_terminalbench_smoke


def _selected_case() -> dict:
    spec = load_selected_cases()["regex-log"]
    assert spec["probe_id"] == "terminalbench_public_regex-log"
    return spec


def test_terminalbench_equivalent_grader_pass_and_known_bad_behavior(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "regex.txt").write_text(f"{smoke_control_regex(task_id='regex-log', control_label='pass')}\n", encoding="utf-8")
    pass_grade = grade_terminalbench_case_equivalent(task_id="regex-log", workspace=workspace)

    (workspace / "regex.txt").write_text(
        f"{smoke_control_regex(task_id='regex-log', control_label='known_bad')}\n",
        encoding="utf-8",
    )
    known_bad_grade = grade_terminalbench_case_equivalent(task_id="regex-log", workspace=workspace)

    assert pass_grade["verdict"] == "pass"
    assert pass_grade["authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert pass_grade["authority_detail"] == ADAPTER_AUTHORITY_DETAIL

    assert known_bad_grade["verdict"] == "fail"
    assert known_bad_grade["reason_codes"] == ["regex_expected_dates_mismatch"]
    assert known_bad_grade["observed_file_hash"] != pass_grade["observed_file_hash"]


def test_terminalbench_result_row_matches_eval_substrate_contract(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "regex.txt").write_text(f"{official_solution_regex('regex-log')}\n", encoding="utf-8")
    grade = grade_terminalbench_case_equivalent(task_id="regex-log", workspace=workspace)
    row = build_result_row_for_grade(
        run_id="terminalbench-row-pass",
        eval_id="terminalbench-equivalent-adapter-smoke",
        task_pack_id="terminalbench-regex-log-smoke",
        task_id="regex-log",
        control_label="pass",
        environment_ref="debug://local_no_sandbox",
        artifact_refs=["artifacts/bundle.json"],
        trace_refs=["traces/trace.json"],
        verifier_ref="artifacts/verifier.json",
        grader_ref="artifacts/grader.json",
        grade=grade,
    )

    assert validate_result_row(row)["surface_type"] == "filesystem"
    assert row["task_truth_status"] == "pass"
    assert row["authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert row["authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert row["hidden_truth_ref"] == hidden_truth_ref_for_task("regex-log")
    assert row["verifier_provenance_ref"] == verifier_provenance_ref_for_task("regex-log")


def test_terminalbench_smoke_runner_emits_control_rows_and_scoreboard(tmp_path):
    summary = run_benchmark_adapter_terminalbench_smoke(tmp_path, task_id="regex-log")
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["adapter_label"] == ADAPTER_LABEL
    assert summary["output_authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert summary["output_authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert scoreboard["row_count"] == 3
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}
    assert scoreboard["by_family"]["terminalbench_equivalent_adapter"] == {
        "pass": 2,
        "fail": 1,
        "invalid": 0,
        "total": 3,
    }
    assert scoreboard["by_surface_type"]["filesystem"]["total"] == 3

    row_payloads = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "result_rows").glob("*.json"))
    }
    grader_payloads = {
        path.parts[-3]: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "runs").glob("*/artifacts/grader_output.json"))
    }
    assert set(row_payloads) == {"pass", "known_bad", "ceiling"}
    assert row_payloads["known_bad"]["task_truth_status"] == "fail"
    assert row_payloads["ceiling"]["reason_codes"] == ["ceiling_passed"]
    assert grader_payloads["pass"]["grade"]["observed_file_hash"] != grader_payloads["ceiling"]["grade"]["observed_file_hash"]
    assert grader_payloads["pass"]["grade"]["normalized_pattern_hash"] != grader_payloads["ceiling"]["grade"]["normalized_pattern_hash"]
    assert summary["hidden_truth_payload_path"].endswith("hidden_truth_payload.json")


def test_hidden_truth_separation_does_not_mix_provenance_and_truth_payloads(tmp_path):
    run_benchmark_adapter_terminalbench_smoke(tmp_path, task_id="regex-log")
    provenance_payload = json.loads((tmp_path / "verifier_provenance.json").read_text(encoding="utf-8"))
    hidden_truth_payload = json.loads((tmp_path / "hidden_truth_payload.json").read_text(encoding="utf-8"))

    output_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in list(tmp_path.rglob("result_rows/*.json"))
        + list(tmp_path.rglob("artifacts/*.json"))
        + [tmp_path / "verifier_provenance.json", tmp_path / "hidden_truth_payload.json"]
    )
    assert "2025-01-09" not in output_text
    assert "192.168.0.1" not in output_text
    assert hidden_truth_ref_for_task("regex-log") in output_text
    assert verifier_provenance_ref_for_task("regex-log") in output_text
    assert "expected_dates_hash" not in provenance_payload
    assert "sample_logs_hash" not in provenance_payload
    assert "hidden_truth_fingerprint_sha256" not in provenance_payload
    assert hidden_truth_payload["hidden_truth_ref"] == hidden_truth_ref_for_task("regex-log")
    assert hidden_truth_payload["verifier_provenance_ref"] == verifier_provenance_ref_for_task("regex-log")
    assert hidden_truth_payload["expected_dates_hash"]
    assert hidden_truth_payload["sample_logs_hash"]


def test_terminalbench_task_pack_contract_for_smoke_case():
    task_pack = build_task_pack(
        task_pack_id="terminalbench-regex-log-smoke",
        task_id="regex-log",
    )
    assert task_pack["hidden_verifier"]["leak_hidden_checks_to_prompt"] is False
    assert task_pack["surface_type"] == "filesystem"
    assert task_pack["fixture"]["request_ref"] == "/app/request.json"
    assert task_pack["visible_verifier"]["native_verifier_execution"] is False
    assert task_pack["hidden_verifier"]["native_verifier_execution"] is False
    assert "Equivalent contract replay" in task_pack["visible_verifier"]["contract_note"]


def test_verifier_provenance_and_hidden_truth_contracts_are_separate():
    provenance = build_verifier_provenance(task_id="regex-log")
    hidden_truth = build_hidden_truth_payload(task_id="regex-log")

    assert provenance["verifier_mode"] == "terminalbench_equivalent_contract_replay"
    assert "expected_dates_hash" not in provenance
    assert "sample_logs_hash" not in provenance
    assert hidden_truth["hidden_truth_ref"] == hidden_truth_ref_for_task("regex-log")
    assert hidden_truth["official_solution_regex_hash"]
    assert hidden_truth["hidden_truth_fingerprint_sha256"]

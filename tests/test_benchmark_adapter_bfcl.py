from __future__ import annotations

import json

from runner import bfcl_assets
from runner.benchmark_adapter_bfcl import (
    ADAPTER_AUTHORITY_LABEL,
    ADAPTER_AUTHORITY_DETAIL,
    build_native_tool_definitions,
    build_result_row_for_grade,
    build_task_pack,
    flatten_ground_truth_calls,
    grade_bfcl_case_equivalent,
    load_mirrored_cases,
)
from runner.eval_substrate_contracts import validate_result_row
from tools.run_benchmark_adapter_smoke import run_benchmark_adapter_smoke


def _supported_case() -> dict:
    cases = load_mirrored_cases()
    case = cases["multi_turn_composite_97"]
    assert case["id"] == "multi_turn_composite_97"
    return case


def test_bfcl_equivalent_grader_pass_and_known_bad_behavior():
    case = _supported_case()
    expected_calls = flatten_ground_truth_calls(case)
    pass_grade = grade_bfcl_case_equivalent(case, expected_calls)
    known_bad_grade = grade_bfcl_case_equivalent(case, expected_calls[:-1])

    assert pass_grade["verdict"] == "pass"
    assert pass_grade["call_match"] is True
    assert pass_grade["authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert pass_grade["authority_detail"] == ADAPTER_AUTHORITY_DETAIL

    assert known_bad_grade["verdict"] == "fail"
    assert "bfcl_missing_required_calls" in known_bad_grade["reason_codes"]
    assert "bfcl_order_or_arguments_mismatch" in known_bad_grade["reason_codes"]
    assert known_bad_grade["expected_calls_hash"] != known_bad_grade["observed_calls_hash"]


def test_bfcl_result_row_matches_eval_substrate_contract():
    case = _supported_case()
    grade = grade_bfcl_case_equivalent(case, flatten_ground_truth_calls(case))
    row = build_result_row_for_grade(
        run_id="bfcl-row-pass",
        eval_id="bfcl-equivalent-adapter-smoke",
        task_pack_id="bfcl-equivalent-v3-smoke",
        case_id=case["id"],
        control_label="pass",
        environment_ref="debug://local_no_sandbox",
        artifact_refs=["artifacts/bundle.json"],
        trace_refs=["traces/trace.json"],
        verifier_ref="artifacts/verifier.json",
        grader_ref="artifacts/grader.json",
        grade=grade,
    )

    assert validate_result_row(row)["surface_type"] == "tool_call"
    assert row["task_truth_status"] == "pass"
    assert row["authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert row["authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert row["contamination_labels"] == ["clean", "public_benchmark_row", "mirrored_resource"]
    assert row["hidden_truth_ref"].startswith("hidden://bfcl-equivalent")


def test_bfcl_smoke_runner_emits_control_rows_and_scoreboard(tmp_path):
    summary = run_benchmark_adapter_smoke(tmp_path, case_id="multi_turn_composite_97")
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["output_authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert summary["output_authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert scoreboard["row_count"] == 3
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}
    assert scoreboard["by_family"]["bfcl_equivalent_adapter"] == {
        "pass": 2,
        "fail": 1,
        "invalid": 0,
        "total": 3,
    }
    assert scoreboard["by_surface_type"]["tool_call"]["total"] == 3

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
    assert grader_payloads["pass"]["grade"]["observed_raw_calls_hash"] != grader_payloads["ceiling"]["grade"]["observed_raw_calls_hash"]
    assert grader_payloads["pass"]["grade"]["observed_calls_hash"] == grader_payloads["ceiling"]["grade"]["observed_calls_hash"]


def test_hidden_truth_separation_does_not_leak_raw_ground_truth_calls(tmp_path):
    case = _supported_case()
    expected_calls = flatten_ground_truth_calls(case)
    run_benchmark_adapter_smoke(tmp_path, case_id=case["id"])

    output_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in list(tmp_path.rglob("result_rows/*.json")) + list(tmp_path.rglob("artifacts/*.json"))
    )
    assert expected_calls
    assert expected_calls[0] not in output_text
    assert "hidden://bfcl-equivalent/mirrored-v3" in output_text


def test_bfcl_load_mirrored_cases_prefers_live_candidate_resolution(monkeypatch, tmp_path):
    fallback_sample = bfcl_assets.BFCL_SAMPLE_PATH_CANDIDATES[1]
    monkeypatch.setattr(
        bfcl_assets,
        "BFCL_SAMPLE_PATH_CANDIDATES",
        (tmp_path / "missing_bfcl.json", fallback_sample),
    )

    cases = load_mirrored_cases()

    assert cases["multi_turn_composite_97"]["id"] == "multi_turn_composite_97"


def test_bfcl_native_tool_definitions_use_live_api_dir_resolution(monkeypatch, tmp_path):
    case = _supported_case()
    fallback_api_dir = bfcl_assets.BFCL_API_DIR_CANDIDATES[1]
    monkeypatch.setattr(
        bfcl_assets,
        "BFCL_API_DIR_CANDIDATES",
        (tmp_path / "missing_apis", fallback_api_dir),
    )

    definitions = build_native_tool_definitions(case)
    names = {entry["name"] for entry in definitions}

    assert "send_message" in names
    assert "startEngine" in names


def test_bfcl_task_pack_contract_for_smoke_case():
    task_pack = build_task_pack(task_pack_id="bfcl-equivalent-v3-smoke", case_id="multi_turn_composite_97")
    assert task_pack["hidden_verifier"]["leak_hidden_checks_to_prompt"] is False
    assert task_pack["surface_type"] == "tool_call"


def test_bfcl_safe_invocation_rejects_non_literal_or_non_name_call_expressions():
    case = _supported_case()
    grade = grade_bfcl_case_equivalent(
        case,
        ["__import__('os').system('echo unsafe')"],
    )
    assert grade["verdict"] == "fail"
    assert "bfcl_observed_call_execution_error" in grade["reason_codes"]

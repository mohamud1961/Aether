from __future__ import annotations

import json

from runner import bfcl_assets
from runner.benchmark_adapter_bfcl_native import (
    ADAPTER_AUTHORITY_LABEL,
    ADAPTER_AUTHORITY_DETAIL,
    build_result_row_for_grade,
    build_task_pack,
    flatten_ground_truth_calls,
    grade_bfcl_case_native,
    load_official_curated_cases,
    native_grader_preflight,
)
from runner.benchmark_adapter_bfcl import build_native_tool_definitions
from runner.eval_substrate_contracts import validate_result_row
from tools.run_benchmark_adapter_bfcl_native_smoke import run_benchmark_adapter_bfcl_native_smoke


def _supported_case() -> dict:
    cases = load_official_curated_cases()
    case = cases["multi_turn_composite_97"]
    assert case["id"] == "multi_turn_composite_97"
    return case


def test_bfcl_native_grader_pass_and_known_bad_behavior():
    case = _supported_case()
    expected_calls = flatten_ground_truth_calls(case)
    pass_grade = grade_bfcl_case_native(case, expected_calls)
    known_bad_grade = grade_bfcl_case_native(case, [])

    assert pass_grade["verdict"] == "pass"
    assert pass_grade["authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert pass_grade["authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert pass_grade["state_mismatch_field_count"] == 0

    assert known_bad_grade["verdict"] == "fail"
    assert "bfcl_no_calls_emitted" in known_bad_grade["reason_codes"]
    assert "bfcl_state_mismatch" in known_bad_grade["reason_codes"]
    assert known_bad_grade["expected_calls_hash"] != known_bad_grade["observed_calls_hash"]


def test_bfcl_native_result_row_matches_eval_substrate_contract():
    case = _supported_case()
    grade = grade_bfcl_case_native(case, flatten_ground_truth_calls(case))
    row = build_result_row_for_grade(
        run_id="bfcl-native-row-pass",
        eval_id="bfcl-native-adapter-smoke",
        task_pack_id="bfcl-native-v3-smoke",
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
    assert row["contamination_labels"] == ["clean", "public_benchmark_row", "mirrored_resource", "official_subset"]
    assert row["hidden_truth_ref"].startswith("hidden://bfcl-native")


def test_bfcl_native_smoke_runner_emits_control_rows_and_scoreboard(tmp_path):
    summary = run_benchmark_adapter_bfcl_native_smoke(tmp_path, case_id="multi_turn_composite_97")
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["output_authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert summary["output_authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert scoreboard["row_count"] == 3
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}
    assert scoreboard["by_family"]["bfcl_native_adapter"] == {
        "pass": 2,
        "fail": 1,
        "invalid": 0,
        "total": 3,
    }
    assert scoreboard["by_surface_type"]["tool_call"]["total"] == 3


def test_hidden_truth_separation_does_not_leak_raw_ground_truth_calls(tmp_path):
    case = _supported_case()
    expected_calls = flatten_ground_truth_calls(case)
    run_benchmark_adapter_bfcl_native_smoke(tmp_path, case_id=case["id"])

    output_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in list(tmp_path.rglob("result_rows/*.json")) + list(tmp_path.rglob("artifacts/*.json"))
    )
    assert expected_calls
    assert expected_calls[0] not in output_text
    assert "hidden://bfcl-native/official-v3-curated" in output_text


def test_bfcl_native_preflight_reports_missing_mirrored_assets(monkeypatch, tmp_path):
    monkeypatch.setattr(
        bfcl_assets,
        "BFCL_SAMPLE_PATH_CANDIDATES",
        (tmp_path / "missing_bfcl.json", tmp_path / "missing_bfcl_fallback.json"),
    )
    monkeypatch.setattr(
        bfcl_assets,
        "BFCL_API_DIR_CANDIDATES",
        (tmp_path / "missing_bfcl_apis", tmp_path / "missing_bfcl_apis_fallback"),
    )

    preflight = native_grader_preflight()

    assert preflight["native_runtime_available"] is False
    assert "missing_bfcl_mirrored_assets" in preflight["blocker_codes"]
    assert len(preflight["missing_paths"]) == 4
    assert all(path.startswith(str(tmp_path)) for path in preflight["missing_paths"])


def test_bfcl_native_load_official_curated_cases_prefers_live_candidate_resolution(monkeypatch, tmp_path):
    live_sample = bfcl_assets.BFCL_SAMPLE_PATH_CANDIDATES[0]
    monkeypatch.setattr(
        bfcl_assets,
        "BFCL_SAMPLE_PATH_CANDIDATES",
        (tmp_path / "missing_bfcl.json", live_sample),
    )

    cases = load_official_curated_cases()

    assert cases["multi_turn_composite_97"]["id"] == "multi_turn_composite_97"


def test_bfcl_native_task_pack_contract_and_preflight_shape():
    task_pack = build_task_pack(task_pack_id="bfcl-native-v3-smoke", case_id="multi_turn_composite_97")
    preflight = native_grader_preflight()
    assert task_pack["hidden_verifier"]["leak_hidden_checks_to_prompt"] is False
    assert task_pack["surface_type"] == "tool_call"
    assert preflight["official_grader_source_present"] is True
    assert preflight["native_runtime_mode"] in {"official_native_runtime", "official_grader_only_no_model_runtime"}


def test_bfcl_native_tool_definitions_are_derived_from_involved_classes():
    case = _supported_case()
    definitions = build_native_tool_definitions(case)
    names = {entry["name"] for entry in definitions}

    assert "startEngine" in names
    assert "send_message" in names
    assert all(entry["name"] != "raw_bash" for entry in definitions)
    assert all(entry["input_schema"] == entry["parameters"] for entry in definitions)
    assert all(entry["input_schema"]["type"] == "object" for entry in definitions)
    assert all(entry.get("runtime_spec", {}).get("runtime_kind") == "bfcl_api_method" for entry in definitions)

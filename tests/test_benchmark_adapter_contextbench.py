from __future__ import annotations

import json

from runner.benchmark_adapter_contextbench import (
    ADAPTER_AUTHORITY_DETAIL,
    ADAPTER_AUTHORITY_LABEL,
    build_result_row_for_grade,
    build_task_pack,
    grade_contextbench_case_equivalent,
    hidden_truth_ref_for_probe,
    load_selected_cases,
    row_provenance_ref_for_probe,
)
from runner.eval_substrate_contracts import validate_result_row
from tools.run_benchmark_adapter_contextbench_smoke import run_benchmark_adapter_contextbench_smoke


def _selected_case() -> dict:
    spec = load_selected_cases()["contextbench_verified_03"]
    assert spec["task_id"].startswith("SWE-Bench-Verified__")
    return spec


def test_contextbench_equivalent_grader_pass_and_known_bad_behavior():
    spec = _selected_case()
    expected = spec["expected_answer_payload"]
    pass_answer = "\n".join(
        [
            f"original_inst_id: {expected['original_inst_id']}",
            f"language: {expected['language']}",
            f"status: {expected['status']}",
            f"gold_context_length: {expected['gold_context_length']}",
            f"commit: {expected['commit']}",
            f"repo_or_file_family: {expected['repo_or_file_family']}",
        ]
    )
    known_bad_answer = json.dumps(
        {
            **expected,
            "repo_or_file_family": "wrong_repo_family",
        },
        sort_keys=True,
    )

    pass_grade = grade_contextbench_case_equivalent(spec, pass_answer)
    known_bad_grade = grade_contextbench_case_equivalent(spec, known_bad_answer)

    assert pass_grade["verdict"] == "pass"
    assert pass_grade["authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert pass_grade["authority_detail"] == ADAPTER_AUTHORITY_DETAIL

    assert known_bad_grade["verdict"] == "fail"
    assert "contextbench_repo_or_file_family_mismatch" in known_bad_grade["reason_codes"]
    assert known_bad_grade["observed_structured_hash"] != known_bad_grade["expected_row_hash"]


def test_contextbench_result_row_matches_eval_substrate_contract():
    spec = _selected_case()
    grade = grade_contextbench_case_equivalent(
        spec,
        json.dumps(spec["expected_answer_payload"], sort_keys=True),
    )
    row = build_result_row_for_grade(
        run_id="contextbench-row-pass",
        eval_id="contextbench-equivalent-adapter-smoke",
        task_pack_id="contextbench-verified-03-smoke",
        probe_id=spec["probe_id"],
        control_label="pass",
        environment_ref="debug://local_no_sandbox",
        artifact_refs=["artifacts/bundle.json"],
        trace_refs=["traces/trace.json"],
        verifier_ref="artifacts/verifier.json",
        grader_ref="artifacts/grader.json",
        grade=grade,
    )

    assert validate_result_row(row)["surface_type"] == "retrieval"
    assert row["task_truth_status"] == "pass"
    assert row["authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert row["authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert row["contamination_labels"] == ["clean", "public_benchmark_row", "mirrored_resource"]
    assert row["hidden_truth_ref"] == hidden_truth_ref_for_probe(spec["probe_id"])
    assert row["row_provenance_ref"] == row_provenance_ref_for_probe(spec["probe_id"])


def test_contextbench_smoke_runner_emits_control_rows_and_scoreboard(tmp_path):
    summary = run_benchmark_adapter_contextbench_smoke(tmp_path, probe_id="contextbench_verified_03")
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["adapter_label"] == "ContextBench equivalent adapter"
    assert summary["output_authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert summary["output_authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert scoreboard["row_count"] == 3
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}
    assert scoreboard["by_family"]["contextbench_equivalent_adapter"] == {
        "pass": 2,
        "fail": 1,
        "invalid": 0,
        "total": 3,
    }
    assert scoreboard["by_surface_type"]["retrieval"]["total"] == 3

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
    assert grader_payloads["pass"]["grade"]["observed_answer_hash"] != grader_payloads["ceiling"]["grade"]["observed_answer_hash"]
    assert grader_payloads["pass"]["grade"]["expected_row_hash"] == grader_payloads["ceiling"]["grade"]["expected_row_hash"]


def test_hidden_truth_separation_does_not_leak_selected_row_values_in_artifacts(tmp_path):
    spec = _selected_case()
    expected = spec["expected_answer_payload"]
    run_benchmark_adapter_contextbench_smoke(tmp_path, probe_id=spec["probe_id"])

    output_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in list(tmp_path.rglob("result_rows/*.json")) + list(tmp_path.rglob("artifacts/*.json"))
    )
    assert expected["original_inst_id"] not in output_text
    assert expected["commit"] not in output_text
    assert hidden_truth_ref_for_probe(spec["probe_id"]) in output_text
    assert row_provenance_ref_for_probe(spec["probe_id"]) in output_text


def test_contextbench_task_pack_contract_for_smoke_case():
    task_pack = build_task_pack(
        task_pack_id="contextbench-verified-03-smoke",
        probe_id="contextbench_verified_03",
    )
    assert task_pack["hidden_verifier"]["leak_hidden_checks_to_prompt"] is False
    assert task_pack["surface_type"] == "retrieval"
    assert task_pack["fixture"]["request_ref"] == "/app/contextbench/request.json"

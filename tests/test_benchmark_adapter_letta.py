from __future__ import annotations

import json
from decimal import Decimal

from runner.benchmark_adapter_letta import (
    ADAPTER_AUTHORITY_DETAIL,
    ADAPTER_AUTHORITY_LABEL,
    build_result_row_for_grade,
    build_task_pack,
    grade_letta_case_equivalent,
    hidden_truth_ref_for_probe,
    load_selected_cases,
)
from runner.eval_substrate_contracts import validate_result_row
from tools.run_benchmark_adapter_letta_smoke import run_benchmark_adapter_letta_smoke


def _selected_case() -> dict:
    spec = load_selected_cases()["letta_filesystem_006_medium"]
    assert spec["difficulty"] == "medium"
    return spec


def test_letta_equivalent_grader_pass_and_known_bad_behavior():
    spec = _selected_case()
    truth_value = Decimal(str(spec["grade"]["ground_truth"]))
    pass_grade = grade_letta_case_equivalent(spec, f"The total is {truth_value}.")
    known_bad_grade = grade_letta_case_equivalent(spec, f"${truth_value + Decimal('1')}")

    assert pass_grade["verdict"] == "pass"
    assert pass_grade["authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert pass_grade["authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert pass_grade["numeric_equivalent"] is True

    assert known_bad_grade["verdict"] == "fail"
    assert known_bad_grade["reason_codes"] == ["letta_ground_truth_mismatch"]
    assert known_bad_grade["observed_answer_hash"] != known_bad_grade["ground_truth_hash"]


def test_letta_result_row_matches_eval_substrate_contract():
    spec = _selected_case()
    truth_value = Decimal(str(spec["grade"]["ground_truth"]))
    grade = grade_letta_case_equivalent(spec, f"The total is {truth_value}.")
    row = build_result_row_for_grade(
        run_id="letta-row-pass",
        eval_id="letta-equivalent-adapter-smoke",
        task_pack_id="letta-filesystem-006-medium-smoke",
        probe_id=spec["probe_id"],
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
    assert row["contamination_labels"] == ["clean", "public_benchmark_row", "mirrored_resource"]
    assert row["hidden_truth_ref"] == hidden_truth_ref_for_probe(spec["probe_id"])


def test_letta_smoke_runner_emits_control_rows_and_scoreboard(tmp_path):
    summary = run_benchmark_adapter_letta_smoke(tmp_path, probe_id="letta_filesystem_006_medium")
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["output_authority_label"] == ADAPTER_AUTHORITY_LABEL
    assert summary["output_authority_detail"] == ADAPTER_AUTHORITY_DETAIL
    assert scoreboard["row_count"] == 3
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}
    assert scoreboard["by_family"]["letta_filesystem_equivalent_adapter"] == {
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
    assert grader_payloads["pass"]["grade"]["observed_answer_hash"] != grader_payloads["ceiling"]["grade"]["observed_answer_hash"]
    assert grader_payloads["pass"]["grade"]["ground_truth_hash"] == grader_payloads["ceiling"]["grade"]["ground_truth_hash"]


def test_hidden_truth_separation_does_not_leak_raw_ground_truth(tmp_path):
    spec = _selected_case()
    run_benchmark_adapter_letta_smoke(tmp_path, probe_id=spec["probe_id"])

    output_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in list(tmp_path.rglob("result_rows/*.json")) + list(tmp_path.rglob("artifacts/*.json"))
    )
    assert spec["grade"]["ground_truth"] not in output_text
    assert hidden_truth_ref_for_probe(spec["probe_id"]) in output_text


def test_letta_task_pack_contract_for_smoke_case():
    task_pack = build_task_pack(
        task_pack_id="letta-filesystem-006-medium-smoke",
        probe_id="letta_filesystem_006_medium",
    )
    assert task_pack["hidden_verifier"]["leak_hidden_checks_to_prompt"] is False
    assert task_pack["surface_type"] == "filesystem"
    assert task_pack["fixture"]["dataset_ref"].endswith("filesystem_code.jsonl")

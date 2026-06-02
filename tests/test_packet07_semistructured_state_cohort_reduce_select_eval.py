from __future__ import annotations

import json
from pathlib import Path

from runner.packet07_semistructured_state_cohort_reduce_select_eval import (
    EVAL_ID,
    grade_semistructured_state_cohort_reduce_select_answer,
    launch_semistructured_state_cohort_reduce_select_eval,
)


def test_prepare_writes_expected_artifacts_and_fixture_files(tmp_path: Path) -> None:
    out = tmp_path / "semistructured_state_cohort_eval"
    result = launch_semistructured_state_cohort_reduce_select_eval(
        output_dir=out, execute=False, include_comparison=True
    )
    assert result["status"] == "prepared"

    expected_artifacts = [
        f"{EVAL_ID}_run_spec.json",
        f"{EVAL_ID}_result_records.jsonl",
        f"{EVAL_ID}_score_envelope.json",
        f"{EVAL_ID}_summary.json",
        f"{EVAL_ID}_summary_table.md",
        f"{EVAL_ID}_decision_memo.md",
        f"{EVAL_ID}_handoff.md",
        "RAW_LEDGER_UPDATE",
    ]
    for artifact in expected_artifacts:
        assert (out / artifact).exists(), artifact

    fixture = out / "fixture_workspace"
    expected_files = [
        "pets.txt",
        "addresses.txt",
        "bank_accounts.txt",
        "credit_cards.txt",
        "vehicles.txt",
        "insurance_policies.txt",
    ]
    for name in expected_files:
        file_path = fixture / name
        assert file_path.exists(), name
        assert file_path.read_text(encoding="utf-8").startswith("### "), name


def test_fixture_is_state_cohort_from_hard_row(tmp_path: Path) -> None:
    out = tmp_path / "semistructured_state_cohort_eval"
    launch_semistructured_state_cohort_reduce_select_eval(output_dir=out, execute=False)
    rows = [
        json.loads(line)
        for line in (out / f"{EVAL_ID}_result_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ceiling_row = next(row for row in rows if row["row_type"] == "deterministic_ceiling")
    assert ceiling_row["cohort_owner_count"] == 20


def test_deterministic_ceiling_resolves_pers_0406_and_scalar_14(tmp_path: Path) -> None:
    out = tmp_path / "semistructured_state_cohort_eval"
    launch_semistructured_state_cohort_reduce_select_eval(output_dir=out, execute=False)
    score = json.loads((out / f"{EVAL_ID}_score_envelope.json").read_text(encoding="utf-8"))
    assert score["expected_scalar"] == "14"
    rows = [
        json.loads(line)
        for line in (out / f"{EVAL_ID}_result_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ceiling_row = next(row for row in rows if row["row_type"] == "deterministic_ceiling")
    assert ceiling_row["winner_owner_id"] == "pers-0406"
    assert ceiling_row["target_state"] == "Indiana"


def test_grader_accepts_14_and_rejects_wrong_integer() -> None:
    passed = grade_semistructured_state_cohort_reduce_select_answer(
        final_answer="14", expected_scalar="14"
    )
    failed = grade_semistructured_state_cohort_reduce_select_answer(
        final_answer="12", expected_scalar="14"
    )
    assert passed["verdict"] == "pass"
    assert failed["verdict"] == "fail"
    assert "scalar_mismatch" in failed["reason_codes"]

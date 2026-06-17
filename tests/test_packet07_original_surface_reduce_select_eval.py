from __future__ import annotations

import json
from pathlib import Path

from runner.packet07_hard_row_robustness_probe import _build_hard_spec
from runner.packet07_original_surface_reduce_select_eval import (
    EVAL_ID,
    grade_original_surface_reduce_select_answer,
    launch_original_surface_reduce_select_eval,
)


def _seeded_layout_paths(root: Path) -> set[str]:
    return {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
    }


def test_fixture_preserves_original_workspace_files_and_layout(tmp_path: Path) -> None:
    out = tmp_path / "original_surface_eval"
    result = launch_original_surface_reduce_select_eval(output_dir=out, execute=False, include_comparison=True)
    assert result["status"] == "prepared"

    source_files = _build_hard_spec()["workspace_files"]
    expected_paths = {key.lstrip("/") for key in source_files}
    fixture = out / "fixture_workspace"
    observed_paths = _seeded_layout_paths(fixture)
    assert observed_paths == expected_paths
    assert (fixture / "letta" / "filesystem").is_dir()
    for key, expected_content in source_files.items():
        seeded_path = fixture / key.lstrip("/")
        assert seeded_path.read_text(encoding="utf-8") == expected_content


def test_run_spec_preserves_original_prompt_contract(tmp_path: Path) -> None:
    out = tmp_path / "original_surface_eval"
    launch_original_surface_reduce_select_eval(output_dir=out, execute=False, include_comparison=False)
    run_spec = json.loads((out / f"{EVAL_ID}_run_spec.json").read_text(encoding="utf-8"))
    expected_prompt = _build_hard_spec()["task_prompt"]
    assert run_spec["eval_id"] == EVAL_ID
    assert run_spec["contract"]["task_prompt"] == expected_prompt
    assert run_spec["models"] == ["gpt-5.4-mini"]


def test_deterministic_ceiling_and_grader_resolve_expected_scalar_14(tmp_path: Path) -> None:
    out = tmp_path / "original_surface_eval"
    launch_original_surface_reduce_select_eval(output_dir=out, execute=False, include_comparison=True)

    score = json.loads((out / f"{EVAL_ID}_score_envelope.json").read_text(encoding="utf-8"))
    assert score["expected_scalar"] == "14"
    rows = [
        json.loads(line)
        for line in (out / f"{EVAL_ID}_result_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ceiling_row = next(row for row in rows if row["row_type"] == "deterministic_ceiling")
    assert ceiling_row["final_answer"] == "14"
    assert ceiling_row["pass_fail"] is True

    passed = grade_original_surface_reduce_select_answer(final_answer="14", expected_scalar="14")
    failed = grade_original_surface_reduce_select_answer(final_answer="13", expected_scalar="14")
    assert passed["verdict"] == "pass"
    assert failed["verdict"] == "fail"
    assert "scalar_mismatch" in failed["reason_codes"]

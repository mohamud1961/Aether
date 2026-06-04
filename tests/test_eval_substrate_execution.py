from __future__ import annotations

from pathlib import Path

import pytest

from runner import eval_substrate_execution as mod
from runner.schemas import SchemaValidationError


def test_setup_fixture_workspace_rejects_fake_certified_local_staging(tmp_path):
    with pytest.raises(SchemaValidationError, match="certified fixture workspaces"):
        mod.setup_fixture_workspace(output_root=str(tmp_path), fixture_name="synthetic_row", certified=True)


def test_setup_fixture_workspace_debug_writes_local_staging_marker(tmp_path):
    out = mod.setup_fixture_workspace(output_root=str(tmp_path), fixture_name="synthetic_row", certified=False)

    assert out["debug_local_fixture_staging"] is True
    marker = tmp_path / "fixture_workspace" / "synthetic_row" / "README.debug_local_fixture.txt"
    assert marker.exists()
    assert "debug-only" in marker.read_text(encoding="utf-8")


def test_execute_verifier_records_visible_fields_and_hidden_refs_only(tmp_path):
    res = mod.execute_verifier_with_records(command="echo synthetic_ok", cwd=str(tmp_path), hidden_checks_ref="checks://row-1")

    visible = res["visible_record"]
    hidden = res["hidden_record"]
    assert set(visible) == {"command", "cwd", "stdout", "stderr", "exit_code", "timeout"}
    assert visible["exit_code"] == 0
    assert visible["timeout"] is False
    assert "synthetic_ok" in visible["stdout"]

    assert hidden["checks_ref"] == "checks://row-1"
    assert hidden["checks_materialized"] is False
    assert hidden["check_ids"] == ["hidden_check_ref_only"]


def test_execute_verifier_timeout_records_timeout_and_null_exit_code(tmp_path):
    res = mod.execute_verifier_with_records(command="sleep 1", cwd=str(tmp_path), timeout_seconds=0)

    assert res["visible_record"]["timeout"] is True
    assert res["visible_record"]["exit_code"] is None


@pytest.mark.parametrize(
    ("record", "truth", "expected"),
    [
        ({"exit_code": 0, "timeout": False}, True, "pass"),
        ({"exit_code": 0, "timeout": False}, False, "task_truth_failure"),
        ({"exit_code": 2, "timeout": False}, False, "task_truth_failure"),
        ({"exit_code": 2, "timeout": False}, True, "verifier_execution_failure"),
        ({"exit_code": None, "timeout": True}, True, "verifier_execution_failure"),
    ],
)
def test_deterministic_grade_separates_execution_failure_from_truth_failure(record, truth, expected):
    grade = mod.deterministic_grade(verifier_record=record, verifier_truth_passed=truth)

    assert grade["outcome"] == expected
    if expected == "task_truth_failure":
        assert grade["verifier_execution_failure"] is False
        assert grade["task_truth_failure"] is True
    if expected == "verifier_execution_failure":
        assert grade["verifier_execution_failure"] is True
        assert grade["task_truth_failure"] is False

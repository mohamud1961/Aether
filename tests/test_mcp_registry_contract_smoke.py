from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from runner.eval_substrate_contracts import validate_result_row, validate_task_pack
from runner.eval_substrate_scoreboard import aggregate_result_rows

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = REPO_ROOT / "eval_suite" / "custom" / "mcp_registry_contract_smoke"
TASK_PACK_PATH = PACK_ROOT / "task_pack.json"
BOARD_PATH = REPO_ROOT / "eval_suite" / "boards" / "mcp_registry_contract_smoke_v1.json"
SCOREBOARD_PATH = REPO_ROOT / "eval_suite" / "scoreboards" / "mcp_registry_contract_smoke_v1.example.scoreboard.json"
GRADER_PATH = PACK_ROOT / "grader.py"


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mcp_registry_contract_task_pack_is_valid_and_public_safe():
    task_pack = validate_task_pack(json.loads(TASK_PACK_PATH.read_text(encoding="utf-8")))

    assert task_pack["task_id"] == "mcp_registry_contract_smoke_v1"
    assert task_pack["surface_type"] == "synthetic_substrate_smoke"
    assert task_pack["contamination_policy"]["status"] == "clean"
    assert "deterministic" in task_pack["task_prompt"].lower()
    assert "mcp" in task_pack["task_prompt"].lower()


def test_mcp_registry_contract_grader_handles_pass_and_fail(tmp_path: Path):
    grader = _load_module(GRADER_PATH, "mcp_registry_contract_smoke_grader_test")
    fixture_root = PACK_ROOT / "fixture"

    pass_root = tmp_path / "pass"
    fail_root = tmp_path / "fail"
    for root in (pass_root, fail_root):
        (root / "workspace").mkdir(parents=True)
        (root / "reference").mkdir(parents=True)
        (root / "reference" / "mcp_audit.json").write_text(
            (fixture_root / "reference" / "mcp_audit.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    (pass_root / "workspace" / "mcp_audit.json").write_text(
        (fixture_root / "reference" / "mcp_audit.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fail_root / "workspace" / "mcp_audit.json").write_text(
        (fixture_root / "workspace" / "mcp_audit.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    pass_grade = grader.grade_workspace(workspace_root=pass_root / "workspace", reference_root=pass_root / "reference")
    fail_grade = grader.grade_workspace(workspace_root=fail_root / "workspace", reference_root=fail_root / "reference")

    assert pass_grade["verdict"] == "pass"
    assert pass_grade["reason_codes"] == []
    assert fail_grade["verdict"] == "fail"
    assert set(fail_grade["reason_codes"]) == {
        "mcp_discovery_not_deterministic",
        "mcp_hook_permission_evidence_missing",
        "mcp_schema_mapping_not_faithful",
        "mcp_typed_results_mismatch",
        "native_tool_regression_detected",
    }


def test_mcp_registry_contract_board_points_to_pack_and_grader():
    board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))

    assert board["board_id"] == "mcp_registry_contract_smoke_v1"
    assert (REPO_ROOT / board["task_pack_ref"]).exists()
    assert (REPO_ROOT / board["grader_ref"]).exists()
    assert (REPO_ROOT / board["fixture_root_ref"]).exists()


def test_mcp_registry_contract_example_scoreboard_matches_aggregated_rows():
    payload = json.loads(SCOREBOARD_PATH.read_text(encoding="utf-8"))
    rows = [validate_result_row(row) for row in payload["result_rows"]]

    assert payload["example_only"] is True
    assert payload["scope_label"] == "public_smoke_example_not_benchmark_evidence"
    assert aggregate_result_rows(rows) == payload["scoreboard"]

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from runner.eval_substrate_contracts import validate_result_row, validate_task_pack
from runner.eval_substrate_scoreboard import aggregate_result_rows

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = REPO_ROOT / "eval_suite" / "custom" / "subagent_handoff_contract_smoke"
TASK_PACK_PATH = PACK_ROOT / "task_pack.json"
BOARD_PATH = REPO_ROOT / "eval_suite" / "boards" / "subagent_handoff_contract_smoke_v1.json"
SCOREBOARD_PATH = REPO_ROOT / "eval_suite" / "scoreboards" / "subagent_handoff_contract_smoke_v1.example.scoreboard.json"
GRADER_PATH = PACK_ROOT / "grader.py"


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_subagent_handoff_contract_task_pack_is_valid_and_public_safe():
    task_pack = validate_task_pack(json.loads(TASK_PACK_PATH.read_text(encoding="utf-8")))

    assert task_pack["task_id"] == "subagent_handoff_contract_smoke_v1"
    assert task_pack["surface_type"] == "synthetic_substrate_smoke"
    assert task_pack["contamination_policy"]["status"] == "clean"
    assert "subagent_audit.json" in task_pack["task_prompt"]


def test_subagent_handoff_contract_grader_handles_pass_and_fail(tmp_path: Path):
    grader = _load_module(GRADER_PATH, "subagent_handoff_contract_smoke_grader_test")
    fixture_root = PACK_ROOT / "fixture"

    pass_root = tmp_path / "pass"
    fail_root = tmp_path / "fail"
    for root in (pass_root, fail_root):
        (root / "workspace").mkdir(parents=True)
        (root / "reference").mkdir(parents=True)
        (root / "reference" / "subagent_audit.json").write_text(
            (fixture_root / "reference" / "subagent_audit.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    (pass_root / "workspace" / "subagent_audit.json").write_text(
        (fixture_root / "reference" / "subagent_audit.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fail_root / "workspace" / "subagent_audit.json").write_text(
        (fixture_root / "workspace" / "subagent_audit.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    pass_grade = grader.grade_workspace(workspace_root=pass_root / "workspace", reference_root=pass_root / "reference")
    fail_grade = grader.grade_workspace(workspace_root=fail_root / "workspace", reference_root=fail_root / "reference")

    assert pass_grade["verdict"] == "pass"
    assert pass_grade["reason_codes"] == []
    assert fail_grade["verdict"] == "fail"
    assert set(fail_grade["reason_codes"]) == {
        "agent_frontmatter_parse_mismatch",
        "agent_loader_not_deterministic",
        "handoff_contract_missing",
        "silent_background_execution_assumed",
        "skill_or_mcp_refs_not_visible",
        "task_packet_contract_missing",
        "unresolved_risks_hidden",
    }


def test_subagent_handoff_contract_board_points_to_pack_and_grader():
    board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))

    assert board["board_id"] == "subagent_handoff_contract_smoke_v1"
    assert (REPO_ROOT / board["task_pack_ref"]).exists()
    assert (REPO_ROOT / board["grader_ref"]).exists()
    assert (REPO_ROOT / board["fixture_root_ref"]).exists()


def test_subagent_handoff_contract_example_scoreboard_matches_aggregated_rows():
    payload = json.loads(SCOREBOARD_PATH.read_text(encoding="utf-8"))
    rows = [validate_result_row(row) for row in payload["result_rows"]]

    assert payload["example_only"] is True
    assert payload["scope_label"] == "public_smoke_example_not_benchmark_evidence"
    assert aggregate_result_rows(rows) == payload["scoreboard"]

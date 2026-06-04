from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_eval_suite_v1_certification_baseline import (
    REGISTRY_PATH,
    run_eval_suite_v1_certification_baseline,
    _collect_rows,
    _prepare_grader_run_dir,
)


def test_collect_rows_tooling_family_admitted_seeds() -> None:
    rows = _collect_rows(
        registry_path=REGISTRY_PATH,
        family_filters={"tooling_tool_contract"},
        eval_filters=set(),
        include_homologs=False,
        include_audit_only=False,
    )
    eval_ids = {row["eval_id"] for row in rows}
    assert "esv1_tooling_001_required_args_order" in eval_ids
    assert all(row["row_kind"] == "seed" for row in rows)


def test_collect_rows_tooling_family_with_homologs() -> None:
    rows = _collect_rows(
        registry_path=REGISTRY_PATH,
        family_filters={"tooling_tool_contract"},
        eval_filters=set(),
        include_homologs=True,
        include_audit_only=False,
    )
    eval_ids = {row["eval_id"] for row in rows}
    assert "esv1_tooling_001_required_args_order_h001_workspace_band_transition" in eval_ids


def test_plan_only_accepts_candidate_route_id(tmp_path: Path) -> None:
    summary = run_eval_suite_v1_certification_baseline(
        output_root=tmp_path / "candidate",
        family_filters=["tooling_tool_contract"],
        route_id="spb_tooling_seed_plus_receipt_and_completion_01",
        plan_only=True,
    )

    assert summary["mode"] == "plan_only"
    assert summary["route_id"] == "spb_tooling_seed_plus_receipt_and_completion_01"
    assert summary["row_count"] >= 1


def test_prepare_grader_run_dir_stages_root_trace_and_answer(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "reviewer_pack").mkdir()
    (workspace / "reviewer_pack" / "hidden_truth.json").write_text(
        '{"expected_output": {"path": "/app/custom_answer.json"}}\n',
        encoding="utf-8",
    )
    (workspace / "custom_answer.json").write_text('{"ok": true}\n', encoding="utf-8")

    info = _prepare_grader_run_dir(
        run_dir=workspace / "model_run",
        task_pack={},
        workspace=workspace,
        trace_payload={"events": [{"event_type": "file_write", "path": "/app/custom_answer.json"}]},
        run_id="test-run",
    )

    assert info["candidate_rel_path"] == "/app/custom_answer.json"
    assert info["trace_rel_path"] == "/app/trace.json"
    assert (workspace / "answer.json").exists()
    assert (workspace / "trace.json").exists()
    assert (workspace / "trace" / "trace.jsonl").exists()
    assert (workspace / "model_run" / "trace.json").exists()

from __future__ import annotations

import json
import importlib
from pathlib import Path

mod = importlib.import_module("runner.packet07_closeout_scoreboard")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_closeout_scoreboard_normalizes_rows_and_writes_artifacts(tmp_path):
    golden = tmp_path / "2026-05-12_golden.jsonl"
    fair = tmp_path / "2026-05-12_fair.jsonl"
    hard_mini = tmp_path / "2026-05-12_hard_mini.jsonl"
    hard_codex = tmp_path / "2026-05-12_hard_codex.jsonl"
    bfcl = tmp_path / "2026-05-12_bfcl.jsonl"
    _write_jsonl(
        golden,
        [
            {"run_id": "g1", "eval_id": "letta_filesystem_001_easy", "variant_id": "v_inc", "model_id": "m1", "arm_id": "current_conditions", "max_steps": 4, "exact_grade": {"verdict": "pass", "ground_truth": "Tammy"}, "step_count": 2, "tool_commands": ["ls"], "trace_path": "/tmp/t1"},
            {"run_id": "g2", "eval_id": "letta_filesystem_001_easy", "variant_id": "v_inc", "model_id": "m1", "arm_id": "extended_budget_only", "max_steps": 12, "exact_grade": {"verdict": "pass", "ground_truth": "Tammy"}, "step_count": 2, "tool_commands": [], "trace_path": "/tmp/t2"},
        ],
    )
    _write_jsonl(
        fair,
        [
            {"run_id": "f1", "eval_id": "letta_filesystem_001_easy", "variant_id": "v_inc", "model_id": "m1", "arm_id": "main_12", "max_steps": 12, "exact_grade": {"verdict": "pass", "ground_truth": "Tammy"}, "step_count": 2, "tool_commands": ["cat"], "trace_path": "/tmp/t3"},
            {"run_id": "f2", "eval_id": "letta_filesystem_001_easy", "variant_id": "v_inc", "model_id": "m1", "arm_id": "rerun_7", "max_steps": 7, "exact_grade": {"verdict": "pass", "ground_truth": "Tammy"}, "step_count": 1, "tool_commands": [], "trace_path": "/tmp/t4"},
        ],
    )
    _write_jsonl(
        hard_mini,
        [
            {"run_id": "h1", "eval_id": "letta_filesystem_008_hard", "variant_id": "v_inc", "model_id": "m2", "arm_id": "main_25", "max_steps": 25, "scoreboard_verdict": "fail", "exact_grade": {"verdict": "fail", "ground_truth": "14"}, "step_count": 25, "tool_commands": ["python3"], "trace_path": "/tmp/t5"},
            {"run_id": "h2", "eval_id": "letta_filesystem_008_hard", "variant_id": "v_inc", "model_id": "m2", "arm_id": "rerun_15", "max_steps": 15, "scoreboard_verdict": "pass", "exact_grade": {"verdict": "pass", "ground_truth": "14"}, "step_count": 10, "tool_commands": ["python3"], "trace_path": "/tmp/t6"},
        ],
    )
    _write_jsonl(
        hard_codex,
        [
            {"run_id": "c1", "eval_id": "letta_filesystem_008_hard", "variant_id": "v_new", "model_id": "m3", "arm_id": "main_25", "max_steps": 25, "scoreboard_verdict": "pass", "exact_grade": {"verdict": "pass", "ground_truth": "14"}, "step_count": 12, "tool_commands": ["python3"], "trace_path": "/tmp/t7"},
            {"run_id": "c2", "eval_id": "letta_filesystem_008_hard", "variant_id": "v_new", "model_id": "m3", "arm_id": "rerun_15", "max_steps": 15, "scoreboard_verdict": "pass", "exact_grade": {"verdict": "pass", "ground_truth": "14"}, "step_count": 10, "tool_commands": [], "trace_path": "/tmp/t8"},
        ],
    )
    _write_jsonl(
        bfcl,
        [
            {"run_id": "b1", "eval_id": "bfcl_v3_strict_multi_turn_composite_97", "variant_id": "v_new", "model_id": "m3", "max_steps": 8, "scoreboard_verdict": "pass", "step_count": 3, "trace_path": "/tmp/t9"},
        ],
    )

    out = tmp_path / "out"
    mod.launch_packet07_closeout_scoreboard(
        output_dir=out,
        golden_records=golden,
        fair_records=fair,
        hard_mini_records=hard_mini,
        hard_codex_records=hard_codex,
        bfcl_records=(bfcl,),
    )

    rows = _read_jsonl(out / "packet07_minimal_scoreboard_rows.jsonl")
    assert len(rows) == 8
    for field in mod.REQUIRED_FIELDS:
        assert field in rows[0]
    groups = {row["row_group"] for row in rows}
    assert groups == {
        "current_conditions",
        "fair_runtime_main",
        "fair_runtime_confirm",
        "hard_extension_main",
        "hard_extension_confirm",
        "bfcl_sentinel_legacy",
    }
    assert all(row["run_id"] != "g2" for row in rows)
    summary = json.loads((out / "packet07_score_summary_table.json").read_text(encoding="utf-8"))
    route = json.loads((out / "packet07_route_keep_kill_defer_table.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "packet07_scoreboard_manifest.json").read_text(encoding="utf-8"))
    assert summary["row_count"] == 8
    assert route["packet_id"] == "packet_07"
    assert manifest["row_count"] == 8

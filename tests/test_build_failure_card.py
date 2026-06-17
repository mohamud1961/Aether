from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "build_failure_card.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_failure_card", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_failure_card_scored_failure(tmp_path: Path) -> None:
    module = load_module()
    candidate_dir = tmp_path / "candidate"
    tg_dir = candidate_dir / "target_gate"
    run_dir = tg_dir / "runs" / "run-1"
    artifacts = run_dir / "artifacts"
    route_trace = run_dir / "route_trace"
    artifacts.mkdir(parents=True)
    route_trace.mkdir(parents=True)

    (candidate_dir / "candidate_meta.json").write_text(
        json.dumps(
            {
                "candidate_id": "cand_1",
                "mechanism": "final_slot_gate",
                "mechanism_family": "final_required_action_slot",
                "route_id_to_score": "route_1",
                "target_cluster": ["eval_a", "eval_b"],
            }
        ),
        encoding="utf-8",
    )
    (candidate_dir / "target_gate_passes.txt").write_text("1/2\n", encoding="utf-8")
    (artifacts / "verifier_output.json").write_text(
        json.dumps({"visible_record": {"command": "python3 verifier.py", "cwd": "/app", "exit_code": 0, "stdout": "visible verifier: schema-ok\n", "stderr": ""}}),
        encoding="utf-8",
    )
    (artifacts / "grader_output.json").write_text(
        json.dumps({"failure_class": "unclear", "verdict": "fail", "score": 0.0, "reason_codes": ["no_real_tool_result_evidence"]}),
        encoding="utf-8",
    )
    (artifacts / "grader_execution.json").write_text(
        json.dumps({"selected_command": "python3 grader/grade.py", "attempts": [{"exit_code": 0, "stdout": "grader fail\n", "stderr": ""}]}),
        encoding="utf-8",
    )
    (route_trace / "run_events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "raw_bash_result",
                "payload": {"details": {"command": "cd /app && python3 verifier.py", "exit_code": 0, "reason_code": "tool_success"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tg_dir / "result_rows.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"eval_id": "eval_a", "task_pack_id": "eval_a", "verdict": "pass", "failure_class": "none", "reason_codes": ["row_passed"]}),
                json.dumps(
                    {
                        "eval_id": "eval_b",
                        "task_pack_id": "eval_b",
                        "verdict": "fail",
                        "failure_class": "unclear",
                        "reason_codes": ["no_real_tool_result_evidence"],
                        "verifier_ref": str(artifacts / "verifier_output.json"),
                        "grader_ref": str(artifacts / "grader_output.json"),
                        "grader_execution_ref": str(artifacts / "grader_execution.json"),
                        "trace_refs": [str(route_trace / "run_events.jsonl")],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    card = module.build_failure_card(tmp_path, candidate_dir)
    assert card["eval_id"] == "eval_b"
    assert card["failure_stage"] == "scored_target_gate"
    assert card["reason_codes"] == ["no_real_tool_result_evidence"]
    assert card["recommended_escalation_state"] == "needs_trace_escalation"
    assert card["route_trace_summary"]["last_command"].startswith("cd /app")


def test_build_failure_card_pre_score_validation_failure(tmp_path: Path) -> None:
    module = load_module()
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir(parents=True)
    (candidate_dir / "candidate_meta.json").write_text(json.dumps({"candidate_id": "cand_2"}), encoding="utf-8")
    (candidate_dir / "validation_summary.json").write_text(
        json.dumps({"overall_status": "fail", "checks": [{"name": "novelty_gate", "status": "fail", "reason": "duplicate"}]}),
        encoding="utf-8",
    )
    (candidate_dir / "route_plan_only_exit_code.txt").write_text("1\n", encoding="utf-8")

    card = module.build_failure_card(tmp_path, candidate_dir)
    assert card["failure_stage"] == "pre_score"
    assert card["failure_class"] == "pre_score_validation"
    assert card["recommended_escalation_state"] == "pre_score_repair_required"

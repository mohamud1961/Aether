from __future__ import annotations

import json
from pathlib import Path

import pytest


def _module():
    return pytest.importorskip("runner.packet07_hard_row_robustness_probe")


def test_normalization_and_summary_on_synthetic_rows():
    mod = _module()
    records = [
        mod._normalize_record(
            raw={
                "run_id": "r1",
                "eval_id": mod.EVAL_ID,
                "model_id": "gpt-5.4-mini",
                "route_id": mod.ROUTE_ID,
                "budget": 15,
                "run_index": 1,
                "final_answer": "14",
                "exact_grade": {"verdict": "pass", "reason_codes": []},
                "pass_fail": True,
                "step_count": 9,
                "tool_commands": ["python3 -V"],
                "exit_codes": [0],
                "trace_path": "/tmp/t1.jsonl",
                "score_row_path": "/tmp/score1.json",
                "failure_class": ["unknown", "not_allowed"],
            }
        ),
        mod._normalize_record(
            raw={
                "run_id": "r2",
                "eval_id": mod.EVAL_ID,
                "model_id": "gpt-5.4-mini",
                "route_id": mod.ROUTE_ID,
                "budget": 15,
                "run_index": 2,
                "final_answer": "",
                "exact_grade": {"verdict": "fail", "reason_codes": ["letta_ground_truth_mismatch"]},
                "pass_fail": False,
                "step_count": 15,
                "tool_commands": ["ls -1"],
                "exit_codes": [0],
                "trace_path": "/tmp/t2.jsonl",
                "score_row_path": None,
                "failure_class": ["wrong_record_selection", "dispatch_failure"],
            }
        ),
    ]
    assert records[0]["failure_class"] == ["unknown"]

    score = mod._score_envelope(
        records=records,
        preflight={"status": "pass", "checks": {}},
        metadata={"plan": [{"x": 1}, {"x": 2}]},
        blocked=False,
    )
    assert score["run_count"] == 2
    assert score["pass_count"] == 1
    assert score["fail_count"] == 1
    bucket = score["by_model_budget_cell"]["gpt-5.4-mini|15"]
    assert bucket["run_count"] == 2
    assert bucket["pass"] == 1
    assert bucket["fail"] == 1
    assert bucket["pass_rate"] == 0.5

    failure = mod._failure_report(records)
    assert failure["failed_run_count"] == 1
    assert failure["failure_class_counts"]["wrong_record_selection"] == 1
    assert failure["failure_class_counts"]["dispatch_failure"] == 1


def test_prepare_without_execution_writes_bundle(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_route_availability_check", lambda: {"status": "pass", "blockers": [], "rows": []})
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": []})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {"status": "pass", "blockers": [], "docker_available": False, "requires_docker_for_locked_board": False},
    )
    monkeypatch.setattr(
        mod,
        "prepare_probe_metadata",
        lambda repeats=mod.REPEATS: {
            "mission_id": mod.MISSION_ID,
            "phase": "phase1_only",
            "fair_runtime_only": True,
            "legacy_current_conditions_enabled": False,
            "authority": {"operator": "test"},
            "spec": {"eval_id": mod.EVAL_ID, "timeout_sec": 60},
            "plan": [
                {"eval_id": mod.EVAL_ID, "model_id": "gpt-5.4-mini", "route_id": mod.ROUTE_ID, "budget": 15, "run_index": idx}
                for idx in range(1, repeats + 1)
            ],
        },
    )

    result = mod.launch_packet07_hard_row_robustness_probe(output_dir=tmp_path, execute=False, repeats=2)

    assert result["status"] == "blocked"
    run_spec = json.loads((tmp_path / "packet07_hard_row_robustness_probe_run_spec.json").read_text(encoding="utf-8"))
    assert run_spec["fair_runtime_only"] is True
    assert run_spec["legacy_current_conditions_enabled"] is False
    assert len(run_spec["plan"]) == 2
    required = {
        "packet07_hard_row_robustness_probe_result_records.jsonl",
        "packet07_hard_row_robustness_probe_score_envelope.json",
        "packet07_hard_row_robustness_probe_trace_report.json",
        "packet07_hard_row_robustness_probe_failure_classification_report.json",
        "packet07_hard_row_robustness_probe_comparison_memo.md",
        "packet07_hard_row_robustness_probe_decision_memo.md",
        "packet07_hard_row_robustness_probe_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})
    assert Path(result["score_envelope_path"]).exists()


def test_prepare_probe_metadata_respects_repeats_override(monkeypatch):
    mod = _module()
    monkeypatch.setattr(
        mod,
        "_build_hard_spec",
        lambda: {
            "eval_id": mod.EVAL_ID,
            "benchmark_class": "letta_context_bench",
            "task_id": "filesystem_code_008",
            "task_prompt": "prompt",
            "workspace_seed": "simple_files",
            "workspace_files": {},
            "ground_truth": "14",
            "timeout_sec": 60,
        },
    )

    metadata = mod.prepare_probe_metadata(repeats=5)

    assert len(metadata["plan"]) == len(mod.MODELS) * len(mod.BUDGETS) * 5
    assert metadata["plan"][0]["run_index"] == 1
    assert metadata["plan"][-1]["run_index"] == 5

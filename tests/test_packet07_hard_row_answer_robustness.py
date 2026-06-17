from __future__ import annotations

import pytest


def _module():
    return pytest.importorskip("runner.packet07_hard_row_answer_robustness")


def test_prepare_plan_includes_primary_matrix_and_sentinels():
    mod = _module()
    spec_map = {
        mod.PROPER_EVAL_ID: {"eval_id": mod.PROPER_EVAL_ID, "max_steps": mod.PROPER_EVAL_BUDGET},
        mod.PRIMARY_EVAL_ID: {"eval_id": mod.PRIMARY_EVAL_ID, "max_steps": 25},
        "letta_filesystem_001_easy": {"eval_id": "letta_filesystem_001_easy", "max_steps": 4},
        "letta_filesystem_002_medium": {"eval_id": "letta_filesystem_002_medium", "max_steps": 4},
        "bfcl_v3_strict_multi_turn_composite_97": {"eval_id": "bfcl_v3_strict_multi_turn_composite_97", "max_steps": 4},
    }
    plan = mod._prepare_plan(spec_map=spec_map, repeats=3)

    proper_eval = [row for row in plan if row["segment"] == "proper_eval_original_surface"]
    primary = [row for row in plan if row["segment"] == "primary_hard_row"]
    sentinels = [row for row in plan if row["segment"] == "regression_sentinel"]
    assert len(proper_eval) == len(mod.ROUTE_IDS) * mod.PROPER_EVAL_REPEATS
    assert all(row["eval_id"] == mod.PROPER_EVAL_ID and row["budget"] == mod.PROPER_EVAL_BUDGET for row in proper_eval)
    assert all(row["fair_runtime"] is False for row in proper_eval)
    assert len(primary) == len(mod.ROUTE_IDS) * len(mod.PRIMARY_BUDGETS) * 3
    assert len(sentinels) == len(mod.ROUTE_IDS) * len(mod.SENTINEL_EVAL_IDS) * mod.SENTINEL_REPEATS
    assert {row["route_id"] for row in plan} == set(mod.ROUTE_IDS)
    assert any(row["fair_runtime"] is False and row["eval_id"].startswith("bfcl_") for row in sentinels)


def test_normalization_and_summary_exclude_provider_contamination():
    mod = _module()
    records = [
        mod._normalize_record(
            raw={
                "run_id": "r1",
                "eval_id": mod.PRIMARY_EVAL_ID,
                "model_id": mod.MODEL_ID,
                "route_id": mod.CONTROL_ROUTE_ID,
                "budget": 15,
                "run_index": 1,
                "segment": "primary_hard_row",
                "final_answer": "14",
                "exact_grade": {"verdict": "pass", "reason_codes": []},
                "step_count": 10,
                "tool_commands": ["python3 calc.py"],
                "exit_codes": [0],
                "trace_path": "/tmp/r1.jsonl",
                "failure_class": ["unknown"],
                "interpretation_class": "behavioral_pass",
            }
        ),
        mod._normalize_record(
            raw={
                "run_id": "r2",
                "eval_id": mod.PRIMARY_EVAL_ID,
                "model_id": mod.MODEL_ID,
                "route_id": mod.HELPER_ROUTE_ID,
                "budget": 15,
                "run_index": 1,
                "segment": "primary_hard_row",
                "final_answer": "",
                "exact_grade": {"verdict": "fail", "reason_codes": ["letta_ground_truth_mismatch"]},
                "step_count": 14,
                "tool_commands": ["cat people.txt"],
                "exit_codes": [0],
                "trace_path": "/tmp/r2.jsonl",
                "failure_class": ["reduction_error", "dispatch_failure"],
                "interpretation_class": "behavioral_fail",
            }
        ),
        mod._normalize_record(
            raw={
                "run_id": "r3",
                "eval_id": "letta_filesystem_001_easy",
                "model_id": mod.MODEL_ID,
                "route_id": mod.HELPER_ROUTE_ID,
                "budget": 15,
                "run_index": 1,
                "segment": "regression_sentinel",
                "final_answer": "",
                "exact_grade": {"verdict": "fail", "reason_codes": []},
                "step_count": 0,
                "tool_commands": [],
                "exit_codes": [],
                "trace_path": "/tmp/r3.jsonl",
                "failure_class": ["provider_contaminated"],
                "interpretation_class": "infrastructure_invalid_result",
            }
        ),
    ]

    summary = mod._score_summary(records=records, metadata={"plan": [{}, {}, {}]}, preflight={"status": "pass"}, blocked=False)
    assert summary["run_count"] == 3
    assert summary["behaviorally_admissible_run_count"] == 2
    assert summary["excluded_provider_contaminated_run_count"] == 1
    assert summary["pass_count"] == 1
    assert summary["fail_count"] == 1
    assert summary["route_summary"][mod.HELPER_ROUTE_ID]["hard_row_fail"] == 1


def test_grade_eval_row_uses_local_proper_eval_grader(monkeypatch, tmp_path):
    mod = _module()

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("grade_phase65_spec_should_not_be_used_for_proper_eval")

    monkeypatch.setattr(mod, "grade_phase65_spec", _fail_if_called)
    monkeypatch.setattr(mod, "_proper_eval_deterministic_ceiling", lambda workspace: {"expected_scalar": "7"})
    monkeypatch.setattr(
        mod,
        "grade_original_surface_reduce_select_answer",
        lambda *, final_answer, expected_scalar: {
            "verdict": "pass",
            "reason_codes": [],
            "observed_scalar": final_answer,
            "expected_scalar": expected_scalar,
        },
    )
    grade = mod._grade_eval_row(
        eval_id=mod.PROPER_EVAL_ID,
        spec={"eval_id": mod.PROPER_EVAL_ID},
        result={},
        workspace=tmp_path,
        final_answer="7",
    )
    assert grade["verdict"] == "pass"
    assert grade["expected_scalar"] == "7"


def test_run_one_seeds_proper_eval_workspace_files_without_workspace_seed(monkeypatch, tmp_path):
    mod = _module()
    spec = {
        "eval_id": mod.PROPER_EVAL_ID,
        "task_id": mod.PROPER_EVAL_ID,
        "task_prompt": "Answer the prompt",
        "benchmark_class": "packet07_original_surface",
        "workspace_files": {"inputs/value.txt": "7\n"},
        "timeout_sec": 10,
    }
    plan_row = {
        "eval_id": mod.PROPER_EVAL_ID,
        "model_id": mod.MODEL_ID,
        "route_id": mod.CONTROL_ROUTE_ID,
        "budget": mod.PROPER_EVAL_BUDGET,
        "run_index": 1,
        "segment": "proper_eval_original_surface",
        "fair_runtime": False,
    }

    monkeypatch.setattr(mod, "_build_route_manifest", lambda _route_id: {"variant_id": "test"})
    monkeypatch.setattr(mod, "_model_route", lambda _model_id: {"provider": "test"})
    monkeypatch.setattr(mod, "_tool_trace_fields", lambda _events: ([], []))
    monkeypatch.setattr(mod, "_is_infrastructure_invalid", lambda _run_dir: False)
    monkeypatch.setattr(mod, "_is_adapter_invalid", lambda _run_dir: False)
    monkeypatch.setattr(mod, "_usage", lambda _result: {})
    monkeypatch.setattr(mod, "_grade_eval_row", lambda **_kwargs: {"verdict": "pass", "reason_codes": []})

    captured_cwd = {}

    def _fake_run_reference_baseline(**kwargs):
        captured_cwd["cwd"] = kwargs["cwd"]
        return {"execution": {"last_completion": {"text": "7"}, "step_count": 1}, "run_events": []}

    monkeypatch.setattr(mod, "run_reference_baseline", _fake_run_reference_baseline)

    record = mod._run_one(out=tmp_path, spec_map={mod.PROPER_EVAL_ID: spec}, plan_row=plan_row)
    seeded_file = captured_cwd["cwd"] / "inputs/value.txt"
    assert seeded_file.read_text(encoding="utf-8") == "7\n"
    assert record["scoreboard_verdict"] == "pass"

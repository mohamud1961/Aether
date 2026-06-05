from __future__ import annotations

import json

from runner.successor_phase6_context_completion_repair_gauntlet import (
    REQUIRED_VARIANTS,
    launch_phase6,
)


def test_phase6_no_execute_writes_required_artifact_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runner.successor_phase6_context_completion_repair_gauntlet._record_ledger",
        lambda raw: None,
    )
    result = launch_phase6(output_dir=tmp_path, execute=False, rerun_count=3)
    assert result["run_count"] == 0
    assert result["selected_recommendation"] == "benchmark_adapter_still_invalid"
    required = {
        "phase6_plan.md",
        "phase6_board_manifest.json",
        "phase6_route_matrix.json",
        "phase6_variant_doctrine_matrix.json",
        "phase6_eval_design_report.md",
        "phase6_internal_tb_style_eval_spec.md",
        "phase6_execution_plan.json",
        "phase6_result_records.jsonl",
        "phase6_score_envelope.json",
        "phase6_context_report.json",
        "phase6_completion_report.json",
        "phase6_bfcl_report.json",
        "phase6_terminalbench_report.json",
        "phase6_trace_report.json",
        "phase6_cost_report.json",
        "phase6_failure_source_report.json",
        "phase6_recommendations.json",
        "phase6_handoff.md",
        "RAW_LEDGER_UPDATE.txt",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})
    route = json.loads((tmp_path / "phase6_route_matrix.json").read_text(encoding="utf-8"))
    assert {row["variant_id"] for row in route["routes"]} == set(REQUIRED_VARIANTS)


def test_phase6_board_manifest_contains_required_variant_families(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runner.successor_phase6_context_completion_repair_gauntlet._record_ledger",
        lambda raw: None,
    )
    launch_phase6(output_dir=tmp_path, execute=False, rerun_count=3)
    board = json.loads((tmp_path / "phase6_board_manifest.json").read_text(encoding="utf-8"))
    assert board["control"] == "spb_01"
    assert board["incumbent"] == "spb_tooling_seed_plus_receipt_and_completion_01"
    assert tuple(board["required_variants"]) == REQUIRED_VARIANTS


def test_phase6_fails_closed_when_route_contract_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runner.successor_phase6_context_completion_repair_gauntlet._record_ledger",
        lambda raw: None,
    )
    monkeypatch.setattr(
        "runner.successor_phase6_context_completion_repair_gauntlet._preflight",
        lambda eval_cards: {"status": "pass", "blockers": []},
    )
    monkeypatch.setattr(
        "runner.successor_phase6_context_completion_repair_gauntlet._route_matrix",
        lambda variants: {
            "mission_id": "x",
            "status": "blocked",
            "routes": [{"variant_id": variant, "route_valid": False} for variant in variants],
            "blockers": [{"variant_id": "candidate_plus_context_budget_guard_01", "error": "missing route"}],
        },
    )
    result = launch_phase6(output_dir=tmp_path, execute=True, rerun_count=2)
    assert result["run_count"] == 0
    assert result["selected_recommendation"] == "benchmark_adapter_still_invalid"
    recommendations = json.loads((tmp_path / "phase6_recommendations.json").read_text(encoding="utf-8"))
    assert recommendations["selected_recommendation"] == "benchmark_adapter_still_invalid"

from __future__ import annotations

import json

from runner.packet04_route_manifest import (
    PACKET06_PHASE5_HARD_GAUNTLET_SCOPE,
    build_packet04_route_manifest,
    get_packet04_scope_variants,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.successor_phase5_hard_gauntlet import (
    DOCTRINE_VARIANTS,
    INCUMBENT,
    REQUIRED_VARIANTS,
    launch_phase5,
)


def test_phase5_required_routes_are_admitted_with_doctrine_bindings():
    baseline = build_packet04_route_manifest("sc_b_01", scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE)
    assert tuple(REQUIRED_VARIANTS) == get_packet04_scope_variants(scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE)
    for variant_id in REQUIRED_VARIANTS:
        manifest = build_packet04_route_manifest(variant_id, scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE)
        load_runtime_callables(manifest)
        validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
        routed_text = json.dumps(manifest, sort_keys=True)
        if variant_id in DOCTRINE_VARIANTS:
            assert "blocks/orientation/workflow_doctrine.py" in routed_text


def test_phase5_no_execute_writes_required_artifact_contract(tmp_path):
    result = launch_phase5(output_dir=tmp_path, rerun_count=4, execute=False)
    assert result["run_count"] == 0
    assert result["selected_recommendation"] == "candidate_needs_long_horizon_repair"
    required = {
        "phase5_plan.md",
        "phase5_board_manifest.json",
        "phase5_route_matrix.json",
        "phase5_execution_plan.json",
        "phase5_result_records.jsonl",
        "phase5_score_envelope.json",
        "phase5_context_compaction_report.json",
        "phase5_work_episode_report.json",
        "phase5_recovery_report.json",
        "phase5_false_completion_report.json",
        "phase5_multi_agent_report.json",
        "phase5_tb_style_probe_report.json",
        "phase5_cost_report.json",
        "phase5_failure_source_report.json",
        "phase5_recommendations.json",
        "phase5_handoff.md",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})
    board = json.loads((tmp_path / "phase5_board_manifest.json").read_text())
    assert board["incumbent"] == INCUMBENT
    assert board["conditional_excluded"]["env_snapshot_v2_01"] == "excluded_no_explicit_repair_hypothesis"
    assert set(board["doctrine_bindings"]) == DOCTRINE_VARIANTS

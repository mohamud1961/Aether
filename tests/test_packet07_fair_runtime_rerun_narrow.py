from __future__ import annotations

import pytest


def _module():
    return pytest.importorskip("runner.packet07_fair_runtime_rerun_narrow")


def test_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_route_availability_check", lambda: {"status": "pass", "blockers": [], "rows": []})
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": []})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {"status": "pass", "blockers": [], "docker_available": False, "requires_docker_for_locked_board": False},
    )
    result = mod.launch_narrow_fair_runtime_rerun(output_dir=tmp_path, execute=False)
    assert result["blocked"] is True
    required = {
        "packet07_fair_runtime_rerun_narrow_result_records.jsonl",
        "packet07_fair_runtime_rerun_narrow_score_envelope.json",
        "packet07_fair_runtime_rerun_narrow_trace_report.json",
        "packet07_fair_runtime_rerun_narrow_failure_source_report.json",
        "packet07_fair_runtime_rerun_narrow_arm_comparison_report.json",
        "packet07_fair_runtime_rerun_narrow_cost_report.json",
        "packet07_fair_runtime_rerun_narrow_recommendation.md",
        "packet07_fair_runtime_rerun_narrow_deep_trace_analysis.md",
        "packet07_fair_runtime_rerun_narrow_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_rerun_plan_only_includes_main_pass_pairs():
    mod = _module()
    specs = [{"eval_id": "letta_filesystem_001_easy"}, {"eval_id": "letta_filesystem_002_medium"}]
    main_records = [
        {"eval_id": "letta_filesystem_001_easy", "variant_id": mod.BACKBONE_INCUMBENT, "scoreboard_verdict": "pass"},
        {"eval_id": "letta_filesystem_001_easy", "variant_id": mod.APP_EVIDENCE_VARIANT, "scoreboard_verdict": "fail"},
        {"eval_id": "letta_filesystem_002_medium", "variant_id": mod.APP_EVIDENCE_VARIANT, "scoreboard_verdict": "pass"},
        {"eval_id": "letta_filesystem_002_medium", "variant_id": mod.BACKBONE_INCUMBENT, "scoreboard_verdict": "invalid"},
    ]
    rerun_plan = mod._rerun_plan_from_main(specs, main_records)
    pairs = {(spec["eval_id"], variant) for _, spec, variant in rerun_plan}
    assert pairs == {
        ("letta_filesystem_001_easy", mod.BACKBONE_INCUMBENT),
        ("letta_filesystem_002_medium", mod.APP_EVIDENCE_VARIANT),
    }

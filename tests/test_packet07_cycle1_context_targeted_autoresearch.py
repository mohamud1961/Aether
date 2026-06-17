from __future__ import annotations

import json
from pathlib import Path

import pytest

EXPECTED_COMPARISON_SET = {
    "candidate_plus_path_normalized_verifier_repair_projection_01",
    "verified_work_pocket_handoff_hybrid_01",
    "candidate_plus_context_followup_merged_01",
    "candidate_plus_work_pocket_answer_projection_01",
    "candidate_plus_context_answer_closure_guard_01",
}


def _module():
    return pytest.importorskip("runner.packet07_cycle1_context_targeted_autoresearch")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_cycle1_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": [], "endpoint_host": "stub"})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {
            "status": "pass",
            "blockers": [],
            "docker_available": False,
            "requires_docker_for_locked_board": False,
            "fallback_status": "non_docker_local_supported",
        },
    )
    result = mod.launch_packet07_cycle1(output_dir=tmp_path, execute=False)

    assert result["blocked"] is True
    required = {
        "packet07_cycle1_context_result_records.jsonl",
        "packet07_cycle1_context_score_envelope.json",
        "packet07_cycle1_context_trace_report.json",
        "packet07_cycle1_context_failure_source_report.json",
        "packet07_cycle1_context_variant_delta_report.json",
        "packet07_cycle1_context_cost_report.json",
        "packet07_cycle1_context_recommendation.md",
        "packet07_cycle1_context_deep_trace_analysis.md",
        "packet07_cycle1_context_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_cycle1_board_manifest_and_route_check_pass_under_no_execute(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": [], "endpoint_host": "stub"})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {
            "status": "pass",
            "blockers": [],
            "docker_available": False,
            "requires_docker_for_locked_board": False,
            "fallback_status": "non_docker_local_supported",
        },
    )
    mod.launch_packet07_cycle1(output_dir=tmp_path, execute=False)

    manifest = _load_json(tmp_path / "packet07_cycle1_context_board_manifest.json")
    score = _load_json(tmp_path / "packet07_cycle1_context_score_envelope.json")
    route_rows = score["preflight"]["checks"]["route_availability"]["rows"]

    assert EXPECTED_COMPARISON_SET <= set(manifest["comparison_set"])
    assert manifest["max_new_variants"] == 2
    assert manifest["must_target_lane"] == "context_handoff_answer_extraction"
    assert {row["route_id"] for row in route_rows if row["status"] == "pass"} == EXPECTED_COMPARISON_SET


@pytest.mark.parametrize(
    ("route_id", "runtime_key", "module_import_path", "real_file_suffix"),
    [
        (
            "candidate_plus_context_followup_merged_01",
            "context",
            "blocks.context.phase65_context_followup_merged:manage",
            "blocks/context/phase65_context_followup_merged.py",
        ),
        (
            "candidate_plus_work_pocket_answer_projection_01",
            "context",
            "blocks.context.work_pocket_answer_projection:manage",
            "blocks/context/work_pocket_answer_projection.py",
        ),
        (
            "candidate_plus_context_answer_closure_guard_01",
            "context",
            "blocks.context.context_answer_closure_guard:manage",
            "blocks/context/context_answer_closure_guard.py",
        ),
    ],
)
def test_cycle1_local_route_manifests_use_owned_context_files(route_id, runtime_key, module_import_path, real_file_suffix):
    mod = _module()

    manifest = mod._build_route_manifest(route_id)

    assert manifest["variant_id"] == route_id
    rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == runtime_key]
    assert len(rows) == 1
    row = rows[0]
    assert row["module_import_path"] == module_import_path
    assert row["real_file_path"].endswith(real_file_suffix)


def test_cycle1_new_route_manifests_swap_orientation_and_keep_base_tools():
    mod = _module()

    manifest = mod._build_route_manifest("candidate_plus_work_pocket_answer_projection_01")
    orientation_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "orientation"]
    tools_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] in {"tools_getter", "tool_executor"}]

    assert orientation_rows[0]["module_import_path"] == (
        "blocks.orientation.packet07_context_doctrine:orient_work_pocket_answer_projection"
    )
    assert {row["module_import_path"] for row in tools_rows} == {
        "blocks.tools.spb_tooling_seed:get_tools",
        "blocks.tools.spb_tooling_seed:execute_tool_call",
    }

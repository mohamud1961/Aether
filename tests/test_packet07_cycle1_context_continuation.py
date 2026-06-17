from __future__ import annotations

import json
from pathlib import Path

import pytest


def _module():
    return pytest.importorskip("runner.packet07_cycle1_context_continuation")


def test_continuation_no_execute_writes_artifacts(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": []})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {"status": "pass", "blockers": [], "docker_available": False, "requires_docker_for_locked_board": False},
    )
    result = mod.launch_continuation(output_dir=tmp_path, execute=False)
    assert result["blocked"] is True
    required = {
        "packet07_cycle1_context_continuation_result_records.jsonl",
        "packet07_cycle1_context_continuation_score_envelope.json",
        "packet07_cycle1_context_continuation_trace_report.json",
        "packet07_cycle1_context_continuation_failure_source_report.json",
        "packet07_cycle1_context_continuation_variant_delta_report.json",
        "packet07_cycle1_context_continuation_cost_report.json",
        "packet07_cycle1_context_continuation_recommendation.md",
        "packet07_cycle1_context_continuation_deep_trace_analysis.md",
        "packet07_cycle1_context_continuation_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_continuation_manifest_swaps_tools_and_context_for_dispatch_variant():
    mod = _module()
    manifest = mod._build_route_manifest(mod.DISPATCH_VARIANT)
    tool_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] in {"tools_getter", "tool_executor"}]
    context_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "context"]
    orientation_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "orientation"]
    assert {row["module_import_path"] for row in tool_rows} == {
        "blocks.tools.app_evidence_projection_normalizer:get_tools",
        "blocks.tools.app_evidence_projection_normalizer:execute_tool_call",
    }
    assert context_rows[0]["module_import_path"] == "blocks.context.path_normalized_post_compute_answer_dispatch:manage"
    assert orientation_rows[0]["module_import_path"] == "blocks.orientation.packet07_context_doctrine:orient_post_compute_answer_dispatch"


def test_dispatch_context_extracts_post_compute_answer():
    mod = pytest.importorskip("blocks.context.path_normalized_post_compute_answer_dispatch")
    history = [
        {"role": "system", "content": "Workspace cwd: /tmp/ws"},
        {"role": "user", "content": "Provide a direct, concise answer."},
        {"role": "tool", "content": "raw_bash exit=0\nstdout:\n### rec-1 (owner: pers-0001)\nname: Dawn\nstate: Utah\n\nstderr:\n"},
    ]
    updated = mod.manage(history, {"role": "tool", "content": "raw_bash exit=0\nstdout:\nTammy Roberts\n\nstderr:\n"})
    content = updated[-1]["content"]
    assert "post_compute_dispatch=>next assistant turn should answer exactly: Tammy Roberts" in content
    assert "record_format=>plain-text ### records should be parsed as blocks" not in content

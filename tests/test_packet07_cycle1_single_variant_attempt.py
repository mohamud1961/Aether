from __future__ import annotations

import json
from pathlib import Path

import pytest


def _module():
    return pytest.importorskip("runner.packet07_cycle1_single_variant_attempt")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_single_variant_no_execute_writes_artifacts(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": []})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {"status": "pass", "blockers": [], "docker_available": False, "requires_docker_for_locked_board": False},
    )
    result = mod.launch_attempt(output_dir=tmp_path, execute=False)
    assert result["blocked"] is True
    required = {
        "packet07_cycle1_single_variant_result_records.jsonl",
        "packet07_cycle1_single_variant_score_envelope.json",
        "packet07_cycle1_single_variant_trace_report.json",
        "packet07_cycle1_single_variant_variant_delta_report.json",
        "packet07_cycle1_single_variant_cost_report.json",
        "packet07_cycle1_single_variant_recommendation.md",
        "packet07_cycle1_single_variant_deep_trace_analysis.md",
        "packet07_cycle1_single_variant_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_single_variant_local_manifest_swaps_only_context():
    mod = _module()
    manifest = mod._build_route_manifest(mod.ATTEMPT_VARIANT)
    context_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "context"]
    orientation_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "orientation"]
    assert context_rows[0]["module_import_path"] == "blocks.context.path_normalized_context_closure_projection:manage"
    assert orientation_rows[0]["module_import_path"] == "blocks.orientation.phase65_followup2_doctrine:orient_path_normalized_verifier_repair_projection"


def test_context_block_projects_python3_and_work_pocket_hints():
    mod = pytest.importorskip("blocks.context.path_normalized_context_closure_projection")
    history = [
        {"role": "system", "content": "Workspace cwd: /tmp/ws"},
        {"role": "user", "content": "Inspect all files under /app/case and write /app/artifacts/work_pocket.json. In the final answer, state the total and the artifact path."},
    ]
    updated = mod.manage(history, {"role": "tool", "content": "raw_bash exit=127 command=python - <<'PY'\ninvoice alpha total=17\n"})
    content = updated[-1]["content"]
    assert "retry_with_python3_only" in content
    assert "absolute /app/case/... evidence_paths" in content

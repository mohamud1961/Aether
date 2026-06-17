from __future__ import annotations

import json
from pathlib import Path

from tools.run_goal1b_tooling_family_sprint import run_goal1b_tooling_family_sprint


def test_goal1b_tooling_family_sprint_writes_combined_summary(tmp_path, monkeypatch):
    def fake_clean(root, **kwargs):
        result_dir = Path(root) / "result_rows"
        result_dir.mkdir(parents=True, exist_ok=True)
        row = {
            "route_id": "spb_01",
            "task_pack_id": "ctc_semantics_001_multi_required_order",
            "verdict": "pass",
            "failure_class": "none",
        }
        (result_dir / "clean.json").write_text(json.dumps(row), encoding="utf-8")
        (Path(root) / "run_summary.json").write_text(json.dumps({"row_count": 1}), encoding="utf-8")
        return {"row_count": 1}

    def fake_sentinel(root, **kwargs):
        result_dir = Path(root) / "result_rows"
        result_dir.mkdir(parents=True, exist_ok=True)
        row = {
            "route_id": "spb_01",
            "task_pack_id": "fec_bfcl_tool_call_sentinel_001",
            "verdict": "fail",
            "failure_class": "tool_contract",
        }
        (result_dir / "sentinel.json").write_text(json.dumps(row), encoding="utf-8")
        (Path(root) / "run_summary.json").write_text(json.dumps({"row_count": 1}), encoding="utf-8")
        return {"row_count": 1}

    monkeypatch.setattr("tools.run_goal1b_tooling_family_sprint.run_clean_tool_contract_model_backed", fake_clean)
    monkeypatch.setattr("tools.run_goal1b_tooling_family_sprint.run_model_backed_baseline_certified_core", fake_sentinel)
    monkeypatch.setattr("tools.run_goal1b_tooling_family_sprint.build_packet04_route_manifest", lambda route_id, scope: {"route_manifest_fingerprint": f"{route_id}:{scope}", "routed_modules": []})
    monkeypatch.setattr("tools.run_goal1b_tooling_family_sprint.load_runtime_callables", lambda manifest: manifest)

    summary = run_goal1b_tooling_family_sprint(tmp_path)

    assert summary["row_count"] == 2
    comparison = json.loads((tmp_path / "comparison_summary.json").read_text(encoding="utf-8"))
    assert comparison["spb_01"]["clean_positive_sentinel"] == "1/1"
    assert comparison["spb_01"]["bfcl_sentinel"] == "0/1"
    variant_factory = json.loads((tmp_path / "variant_factory_lite_admission.json").read_text(encoding="utf-8"))
    assert variant_factory["admitted"]["spb_01"]["status"] == "admitted_to_family_tournament"
    assert variant_factory["not_admitted"]["programmable_tool_calling_v0"] == "missing_executable_variant_id"

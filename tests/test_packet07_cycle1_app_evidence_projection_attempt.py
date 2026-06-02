from __future__ import annotations

import json
from pathlib import Path

import pytest


def _module():
    return pytest.importorskip("runner.packet07_cycle1_app_evidence_projection_attempt")


def test_app_evidence_projection_no_execute_writes_artifacts(tmp_path, monkeypatch):
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
        "packet07_cycle1_app_evidence_projection_result_records.jsonl",
        "packet07_cycle1_app_evidence_projection_score_envelope.json",
        "packet07_cycle1_app_evidence_projection_trace_report.json",
        "packet07_cycle1_app_evidence_projection_variant_delta_report.json",
        "packet07_cycle1_app_evidence_projection_cost_report.json",
        "packet07_cycle1_app_evidence_projection_recommendation.md",
        "packet07_cycle1_app_evidence_projection_deep_trace_analysis.md",
        "packet07_cycle1_app_evidence_projection_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_app_evidence_projection_manifest_swaps_only_tools():
    mod = _module()
    manifest = mod._build_route_manifest(mod.ATTEMPT_VARIANT)
    tool_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] in {"tools_getter", "tool_executor"}]
    context_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "context"]
    assert {row["module_import_path"] for row in tool_rows} == {
        "blocks.tools.app_evidence_projection_normalizer:get_tools",
        "blocks.tools.app_evidence_projection_normalizer:execute_tool_call",
    }
    assert context_rows[0]["module_import_path"] == "blocks.context.path_normalized_verifier_repair_projection:manage"


def test_tool_surface_rewrites_work_pocket_evidence_paths(tmp_path):
    mod = pytest.importorskip("blocks.tools.app_evidence_projection_normalizer")

    class _Sandbox:
        sandbox_type = "none"

        def __init__(self, cwd: Path):
            self.cwd = cwd

        def exec(self, command):  # type: ignore[no-untyped-def]
            artifact = self.cwd / "artifacts" / "work_pocket.json"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(
                json.dumps(
                    {
                        "verified_total": 50,
                        "verification_status": "verified",
                        "evidence_paths": [
                            f"{self.cwd}/case/alpha/invoice_a.txt",
                            f"{self.cwd}/case/beta/invoice_b.txt",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}

    sandbox = _Sandbox(tmp_path)
    mod.execute_tool_call({"name": "raw_bash", "arguments": json.dumps({"command": "python3 write work_pocket.json"})}, sandbox)
    payload = json.loads((tmp_path / "artifacts" / "work_pocket.json").read_text(encoding="utf-8"))
    assert payload["evidence_paths"] == ["/app/case/alpha/invoice_a.txt", "/app/case/beta/invoice_b.txt"]

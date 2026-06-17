from __future__ import annotations

import pytest


def _module():
    return pytest.importorskip("runner.packet07_cycle1_parser_continuation")


def test_parser_continuation_no_execute_writes_artifacts(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": []})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {"status": "pass", "blockers": [], "docker_available": False, "requires_docker_for_locked_board": False},
    )
    result = mod.launch_parser_continuation(output_dir=tmp_path, execute=False)
    assert result["blocked"] is True
    required = {
        "packet07_cycle1_parser_continuation_result_records.jsonl",
        "packet07_cycle1_parser_continuation_score_envelope.json",
        "packet07_cycle1_parser_continuation_trace_report.json",
        "packet07_cycle1_parser_continuation_failure_source_report.json",
        "packet07_cycle1_parser_continuation_variant_delta_report.json",
        "packet07_cycle1_parser_continuation_cost_report.json",
        "packet07_cycle1_parser_continuation_recommendation.md",
        "packet07_cycle1_parser_continuation_deep_trace_analysis.md",
        "packet07_cycle1_parser_continuation_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_parser_manifest_swaps_orientation_tools_and_context():
    mod = _module()
    manifest = mod._build_route_manifest(mod.PARSER_VARIANT)
    tool_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] in {"tools_getter", "tool_executor"}]
    context_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "context"]
    orientation_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "orientation"]
    assert {row["module_import_path"] for row in tool_rows} == {
        "blocks.tools.semistructured_record_bundle_parser:get_tools",
        "blocks.tools.semistructured_record_bundle_parser:execute_tool_call",
    }
    assert context_rows[0]["module_import_path"] == "blocks.context.semistructured_fact_projection:manage"
    assert orientation_rows[0]["module_import_path"] == "blocks.orientation.packet07_context_doctrine:orient_semistructured_record_bundle_parser_app_evidence_projection"


def test_semistructured_parser_emits_record_bundle():
    mod = pytest.importorskip("blocks.tools.semistructured_record_bundle_parser")

    class _Sandbox:
        cwd = "/tmp/ws"
        sandbox_type = "none"

    monkey_result = {
        "result_class": "success",
        "command": "cat case/records.txt",
        "stdout": "### rec-7 (owner: pers-0042)\nname: Tammy Roberts\nstate: Utah\npet_id: pet-01\n",
        "normalized_tool_call_payload": {"tool_name": "raw_bash"},
    }
    original = mod.execute_baseline_tool_call
    mod.execute_baseline_tool_call = lambda tool_call, sandbox: dict(monkey_result)
    try:
        result = mod.execute_tool_call({"name": "raw_bash", "arguments": "{\"command\":\"cat case/records.txt\"}"}, _Sandbox())
    finally:
        mod.execute_baseline_tool_call = original
    payload = result["normalized_tool_call_payload"]
    assert payload["semistructured_evidence_fact_count"] >= 1
    facts = payload["semistructured_evidence_facts"]
    bundle = next(fact for fact in facts if fact["fact_type"] == "record_bundle")
    assert bundle["value"]["owner"] == "pers-0042"
    assert bundle["value"]["state"] == "Utah"
    assert "SEMISTRUCTURED_FACT:" in result["stdout"]


def test_semistructured_fact_projection_reads_receipts():
    mod = pytest.importorskip("blocks.context.semistructured_fact_projection")
    content = (
        "raw_bash exit=0\nstdout:\nvalue found\n"
        "SEMISTRUCTURED_FACT: {\"fact_type\":\"labeled_value\",\"key\":\"name\",\"value\":\"Tammy Roberts\","
        "\"source_path\":\"/app/case/records.txt\",\"source_span\":\"line:1\",\"confidence\":0.86,\"parser_mode\":\"line_kv\"}\n"
        "stderr:\n"
    )
    updated = mod.manage([], {"role": "tool", "content": content})
    state = updated[-1]["semistructured_fact_projection"]
    assert state["fact_count"] == 1
    assert "parser_created_fact=true" in updated[-1]["content"]

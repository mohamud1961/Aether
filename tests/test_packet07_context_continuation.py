from __future__ import annotations

import json
from pathlib import Path

import pytest


def _module():
    return pytest.importorskip("runner.packet07_context_continuation")


def test_context_continuation_no_execute_writes_artifacts(tmp_path, monkeypatch):
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
        "packet07_context_continuation_result_records.jsonl",
        "packet07_context_continuation_score_envelope.json",
        "packet07_context_continuation_trace_report.json",
        "packet07_context_continuation_failure_source_report.json",
        "packet07_context_continuation_variant_delta_report.json",
        "packet07_context_continuation_cost_report.json",
        "packet07_context_continuation_recommendation.md",
        "packet07_context_continuation_deep_trace_analysis.md",
        "packet07_context_continuation_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_context_continuation_manifest_swaps_tools_and_context_for_successor():
    mod = _module()
    manifest = mod._build_route_manifest(mod.SUCCESSOR_VARIANT)
    tool_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] in {"tools_getter", "tool_executor"}]
    context_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "context"]
    assert {row["module_import_path"] for row in tool_rows} == {
        "blocks.tools.open_workflow_answer_candidate_normalizer:get_tools",
        "blocks.tools.open_workflow_answer_candidate_normalizer:execute_tool_call",
    }
    assert context_rows[0]["module_import_path"] == "blocks.context.open_workflow_answer_candidate_dispatch:manage"


def test_open_workflow_tool_surface_rewrites_letta_alias_and_adds_answer_candidate(tmp_path):
    mod = pytest.importorskip("blocks.tools.open_workflow_answer_candidate_normalizer")

    class _Sandbox:
        sandbox_type = "none"

        def __init__(self, cwd: Path):
            self.cwd = cwd
            self.command = ""

        def exec(self, command):  # type: ignore[no-untyped-def]
            self.command = command
            return {"exit_code": 0, "stdout": "pers-0099 George Peterson\n", "stderr": "", "timed_out": False}

    sandbox = _Sandbox(tmp_path)
    result = mod.execute_tool_call(
        {"name": "raw_bash", "arguments": json.dumps({"command": "python3 - <<'PY'\nprint('/letta/filesystem')\nPY"})},
        sandbox,
    )
    assert f"{tmp_path}/letta/filesystem" in sandbox.command
    assert "ANSWER_CANDIDATE: George Peterson" in result["stdout"]


def test_answer_candidate_dispatch_block_adds_direct_answer_hint():
    mod = pytest.importorskip("blocks.context.open_workflow_answer_candidate_dispatch")
    history = [
        {"role": "system", "content": "Provide a direct, concise answer only.\nWorkspace cwd: /tmp/workspace"},
        {"role": "tool", "content": "raw_bash exit=0\nstdout:\npers-0099 George Peterson\nANSWER_CANDIDATE: George Peterson\nstderr:\n"},
    ]
    updated = mod.manage(history, {"role": "tool", "content": "raw_bash exit=0\nstdout:\nANSWER_CANDIDATE: George Peterson\nstderr:\n"})
    assert "answer exactly: George Peterson" in updated[-1]["content"]

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _module():
    return pytest.importorskip("runner.packet07_context_grounded_architecture_variant")


def test_variant_no_execute_writes_artifacts(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": []})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {"status": "pass", "blockers": [], "docker_available": False, "requires_docker_for_locked_board": False},
    )
    result = mod.launch_variant(output_dir=tmp_path, execute=False)
    assert result["blocked"] is True
    required = {
        "packet07_context_grounded_architecture_variant_result_records.jsonl",
        "packet07_context_grounded_architecture_variant_score_envelope.json",
        "packet07_context_grounded_architecture_variant_trace_report.json",
        "packet07_context_grounded_architecture_variant_failure_source_report.json",
        "packet07_context_grounded_architecture_variant_variant_delta_report.json",
        "packet07_context_grounded_architecture_variant_cost_report.json",
        "packet07_context_grounded_architecture_variant_recommendation.md",
        "packet07_context_grounded_architecture_variant_deep_trace_analysis.md",
        "packet07_context_grounded_architecture_variant_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_manifest_swaps_tool_context_and_execution_for_architecture_variant():
    mod = _module()
    manifest = mod._build_route_manifest(mod.ARCH_VARIANT)
    by_key = {row["runtime_key"]: row["module_import_path"] for row in manifest["routed_modules"]}
    assert by_key["orientation"] == "blocks.orientation.packet07_context_doctrine:orient_grounded_fact_projection_dispatch"
    assert by_key["tools_getter"] == "blocks.tools.grounded_fact_projection_normalizer:get_tools"
    assert by_key["tool_executor"] == "blocks.tools.grounded_fact_projection_normalizer:execute_tool_call"
    assert by_key["context"] == "blocks.context.grounded_answer_ready_state:manage"
    assert by_key["execution"] == "blocks.execution.answer_ready_closeout_loop:run_loop"


def test_grounded_tool_surface_rewrites_alias_and_emits_markers(tmp_path):
    mod = pytest.importorskip("blocks.tools.grounded_fact_projection_normalizer")

    class _Sandbox:
        sandbox_type = "none"

        def __init__(self, cwd: Path):
            self.cwd = cwd
            self.command = ""

        def exec(self, command):  # type: ignore[no-untyped-def]
            self.command = command
            return {
                "exit_code": 0,
                "stdout": json.dumps({"answer": "George Peterson", "artifact_path": "artifacts/final.json"}),
                "stderr": "",
                "timed_out": False,
            }

    sandbox = _Sandbox(tmp_path)
    result = mod.execute_tool_call(
        {"name": "raw_bash", "arguments": json.dumps({"command": "python3 - <<'PY'\nprint('/letta/filesystem')\nPY"})},
        sandbox,
    )
    assert f"{tmp_path}/letta/filesystem" in sandbox.command
    assert "GROUNDED_FACT:" in result["stdout"]
    assert "/app/artifacts/final.json" in result["stdout"]


def test_grounded_context_block_marks_answer_ready():
    mod = pytest.importorskip("blocks.context.grounded_answer_ready_state")
    history = [{"role": "system", "content": "Provide a direct, concise answer only."}]
    updated = mod.manage(
        history,
        {
            "role": "tool",
            "content": "raw_bash exit=0\nstdout:\nANSWER_CANDIDATE: Tammy Roberts\nGROUNDED_FACT: {\"fact_type\": \"direct_answer\", \"key\": \"answer_candidate\", \"value\": \"Tammy Roberts\"}\nstderr:\n",
        },
    )
    assert "[grounded_answer_ready_state]" in updated[-1]["content"]
    assert '"answer_ready": true' in updated[-1]["content"]


def test_execution_block_forces_closeout_when_answer_ready():
    mod = pytest.importorskip("blocks.execution.answer_ready_closeout_loop")

    class _Model:
        def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            return {"text": "thinking", "tool_calls": [{"id": "1", "name": "raw_bash", "arguments": {"command": "echo noop"}}]}

    result = mod.run_loop(
        model=_Model(),
        tools={"raw_bash": lambda call: {"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}},
        context={
            "history": [
                {"role": "system", "content": "Provide a direct, concise answer only."},
                {
                    "role": "tool",
                    "content": '[grounded_answer_ready_state] {"answer":"Tammy Roberts","answer_ready":true,"direct_answer_task":true,"reason_code":"answer_candidate"}',
                },
            ],
            "manage_history": lambda history, obs: [*history, dict(obs)],
        },
        max_steps=1,
        tool_definitions=[{"name": "raw_bash"}],
    )
    assert result["status"] == "completed"
    assert result["answer_ready_closeout_state"]["forced_closeout"] is True
    assert result["history"][-1]["content"] == "Tammy Roberts"

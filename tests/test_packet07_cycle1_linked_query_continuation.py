from __future__ import annotations

import json

import pytest


def _module():
    return pytest.importorskip("runner.packet07_cycle1_linked_query_continuation")


def test_linked_query_continuation_no_execute_writes_artifacts(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": []})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {"status": "pass", "blockers": [], "docker_available": False, "requires_docker_for_locked_board": False},
    )
    result = mod.launch_linked_query_continuation(output_dir=tmp_path, execute=False)
    assert result["blocked"] is True
    required = {
        "packet07_cycle1_linked_query_continuation_result_records.jsonl",
        "packet07_cycle1_linked_query_continuation_score_envelope.json",
        "packet07_cycle1_linked_query_continuation_trace_report.json",
        "packet07_cycle1_linked_query_continuation_failure_source_report.json",
        "packet07_cycle1_linked_query_continuation_variant_delta_report.json",
        "packet07_cycle1_linked_query_continuation_cost_report.json",
        "packet07_cycle1_linked_query_continuation_recommendation.md",
        "packet07_cycle1_linked_query_continuation_deep_trace_analysis.md",
        "packet07_cycle1_linked_query_continuation_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_linked_query_manifest_swaps_orientation_tools_and_context():
    mod = _module()
    manifest = mod._build_route_manifest(mod.LINKED_QUERY_VARIANT)
    tool_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] in {"tools_getter", "tool_executor"}]
    context_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "context"]
    orientation_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "orientation"]
    assert {row["module_import_path"] for row in tool_rows} == {
        "blocks.tools.semistructured_record_bundle_parser:get_tools",
        "blocks.tools.semistructured_record_bundle_parser:execute_tool_call",
    }
    assert context_rows[0]["module_import_path"] == "blocks.context.linked_record_query_state:manage"
    assert orientation_rows[0]["module_import_path"] == "blocks.orientation.packet07_context_doctrine:orient_linked_record_query_state"


def test_linked_record_query_state_tracks_join_slots_and_reduction():
    mod = pytest.importorskip("blocks.context.linked_record_query_state")
    history = [
        {"role": "system", "content": "Workspace cwd: /tmp/ws"},
        {
            "role": "user",
            "content": (
                "Among all people who live in the same state as the owner of the vehicle with license plate '7D U3378', "
                "who does NOT own any pets?\nReturn one direct answer."
            ),
        },
    ]
    tool_content = "\n".join(
        [
            'SEMISTRUCTURED_FACT: {"fact_type":"field","key":"person_id","value":"pers-01","source_path":"/app/people.txt","source_span":"line:1","parser_mode":"line_kv"}',
            'SEMISTRUCTURED_FACT: {"fact_type":"field","key":"owner_id","value":"pers-01","source_path":"/app/vehicles.txt","source_span":"line:4","parser_mode":"line_kv"}',
            'SEMISTRUCTURED_FACT: {"fact_type":"field","key":"owner_region","value":"utah","source_path":"/app/addresses.txt","source_span":"line:7","parser_mode":"line_kv"}',
            'SEMISTRUCTURED_FACT: {"fact_type":"field","key":"region","value":"utah","source_path":"/app/pets.txt","source_span":"line:2","parser_mode":"line_kv"}',
        ]
    )
    updated = mod.manage(history, {"role": "tool", "content": tool_content})
    state = updated[-1]["linked_record_query_state"]
    assert state["linked_records_formed"] >= 1
    assert state["receipt_count"] >= 3
    assert state["reduction_ready"] is True
    assert {"person_id", "owner_id"} & set(state["join_keys"])
    assert "reduction_ready=true" in updated[-1]["content"]


def test_linked_query_proof_marks_fact_based_reduction(tmp_path):
    mod = _module()
    run_dir = tmp_path / "run"
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_events.jsonl").write_text(
        "[linked_record_query_state] linked_records_formed=true | query_slots_tracked=true | reduction_ready=true\n",
        encoding="utf-8",
    )
    (workspace / "artifacts").mkdir(parents=True, exist_ok=True)
    (workspace / "artifacts" / "final_report.json").write_text(json.dumps({"answer": "Tammy Roberts"}), encoding="utf-8")
    result = {
        "execution": {
            "steps": [
                {
                    "results": [
                        {
                            "normalized_tool_call_payload": {
                                "semistructured_evidence_facts": [
                                    {
                                        "fact_type": "record_bundle",
                                        "key": "record_bundle",
                                        "value": {"owner": "pers-01", "license_plate": "7D U3378"},
                                        "source_path": "/app/vehicles.txt",
                                        "source_span": "block:1",
                                        "parser_mode": "record_bundle",
                                    },
                                    {
                                        "fact_type": "record_bundle",
                                        "key": "record_bundle",
                                        "value": {"owner": "pers-01", "state": "Utah"},
                                        "source_path": "/app/addresses.txt",
                                        "source_span": "block:2",
                                        "parser_mode": "record_bundle",
                                    },
                                    {
                                        "fact_type": "record_bundle",
                                        "key": "record_bundle",
                                        "value": {"owner": "pers-02", "state": "Utah", "name": "Tammy Roberts"},
                                        "source_path": "/app/people.txt",
                                        "source_span": "block:3",
                                        "parser_mode": "record_bundle",
                                    },
                                ]
                            }
                        }
                    ]
                }
            ],
            "last_completion": {"text": "Tammy Roberts"},
        }
    }
    proof = mod._linked_query_proof(
        result,
        run_dir,
        workspace,
        (
            "Among all people who live in the same state as the owner of the vehicle with license plate '7D U3378', "
            "who does NOT own any pets?\nReturn one direct answer."
        ),
        "pass",
    )
    assert proof["linked_records_formed"] is True
    assert proof["query_slots_tracked"] is True
    assert proof["reduction_ready"] is True
    assert proof["fact_based_answer_or_artifact_use"] is True
    assert proof["answer_or_artifact_improved"] is True

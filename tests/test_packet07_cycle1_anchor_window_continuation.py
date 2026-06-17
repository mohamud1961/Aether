from __future__ import annotations

import json

import pytest


def _module():
    return pytest.importorskip("runner.packet07_cycle1_anchor_window_continuation")


def test_anchor_window_continuation_no_execute_writes_artifacts(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "_route_availability_check", lambda: {"status": "pass", "blockers": [], "rows": []})
    monkeypatch.setattr(mod, "_azure_dns_network_preflight", lambda: {"status": "pass", "blockers": []})
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {"status": "pass", "blockers": [], "docker_available": False, "requires_docker_for_locked_board": False},
    )
    result = mod.launch_anchor_window_continuation(output_dir=tmp_path, execute=False)
    assert result["blocked"] is True
    required = {
        "packet07_cycle1_anchor_window_continuation_result_records.jsonl",
        "packet07_cycle1_anchor_window_continuation_score_envelope.json",
        "packet07_cycle1_anchor_window_continuation_trace_report.json",
        "packet07_cycle1_anchor_window_continuation_failure_source_report.json",
        "packet07_cycle1_anchor_window_continuation_variant_delta_report.json",
        "packet07_cycle1_anchor_window_continuation_cost_report.json",
        "packet07_cycle1_anchor_window_continuation_recommendation.md",
        "packet07_cycle1_anchor_window_continuation_deep_trace_analysis.md",
        "packet07_cycle1_anchor_window_continuation_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_anchor_window_override_uses_anchor_tool_and_linked_context():
    mod = _module()
    override = mod.LOCAL_ROUTE_OVERRIDES[mod.ANCHOR_WINDOW_VARIANT]["modules"]
    assert override["orientation"]["module_import_path"] == (
        "blocks.orientation.packet07_context_doctrine:orient_linked_record_anchor_window_reduction"
    )
    assert override["tools_getter"]["file_rel"] == "blocks/tools/semistructured_anchor_window_bundle_parser.py"
    assert override["tools_getter"]["module_import_path"] == "blocks.tools.semistructured_anchor_window_bundle_parser:get_tools"
    assert override["tool_executor"]["module_import_path"] == (
        "blocks.tools.semistructured_anchor_window_bundle_parser:execute_tool_call"
    )
    assert override["context"]["module_import_path"] == "blocks.context.linked_record_query_state:manage"


def test_anchor_window_proof_marks_promoted_reduction(tmp_path):
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
                                        "parser_mode": "anchor_window_bundle",
                                    },
                                    {
                                        "fact_type": "record_bundle",
                                        "key": "record_bundle",
                                        "value": {"owner": "pers-01", "state": "Utah"},
                                        "source_path": "/app/addresses.txt",
                                        "source_span": "block:2",
                                        "parser_mode": "anchor_window_bundle",
                                    },
                                    {
                                        "fact_type": "record_bundle",
                                        "key": "record_bundle",
                                        "value": {"owner": "pers-02", "state": "Utah", "name": "Tammy Roberts"},
                                        "source_path": "/app/people.txt",
                                        "source_span": "block:3",
                                        "parser_mode": "anchor_window_bundle",
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
    proof = mod._anchor_window_proof(
        result,
        run_dir,
        workspace,
        (
            "Among all people who live in the same state as the owner of the vehicle with license plate '7D U3378', "
            "who does NOT own any pets?\nReturn one direct answer."
        ),
        "pass",
    )
    assert proof["anchor_window_promoted"] is True
    assert proof["linked_records_formed"] is True
    assert proof["query_slots_tracked"] is True
    assert proof["anchor_window_reduction_ready"] is True
    assert proof["fact_based_answer_or_artifact_use"] is True
    assert proof["answer_or_artifact_improved"] is True


def test_anchor_window_variant_delta_reports_partial_signal_without_letta_gain():
    mod = _module()
    records = [
        {
            "variant_id": mod.APP_EVIDENCE_VARIANT,
            "admission_level": "certified",
            "scoreboard_verdict": "pass",
            "lane": "context_handoff_answer_extraction",
            "eval_id": "contextbench_verified_03",
            "anchor_window_proof": {},
        },
        {
            "variant_id": mod.ANCHOR_WINDOW_VARIANT,
            "admission_level": "certified",
            "scoreboard_verdict": "pass",
            "lane": "context_handoff_answer_extraction",
            "eval_id": "contextbench_verified_03",
            "anchor_window_proof": {
                "anchor_window_promoted": True,
                "linked_records_formed": True,
                "query_slots_tracked": True,
                "anchor_window_reduction_ready": True,
                "fact_based_answer_or_artifact_use": True,
            },
        },
    ]
    delta = mod._variant_delta(records)
    assert delta["anchor_window_reduction"]["anchor_window_promoted_runs"] == 1
    assert delta["anchor_window_reduction"]["anchor_window_reduction_ready_runs"] == 1
    assert delta["anchor_window_status"] == "partial_signal"

from __future__ import annotations

import json

from aether.model_interface import build_model_interface_capture
from aether.postmerge_observability import (
    X0_OBSERVABILITY_SCHEMA_VERSION,
    build_x0_observability,
)


def _solver_capture(packet: dict) -> dict:
    messages = [
        {"role": "system", "content": "[stable_authority]\nfixed"},
        {
            "role": "system",
            "content": "[context_packet]\n" + json.dumps(
                packet,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        },
    ]
    return build_model_interface_capture(
        messages,
        model_role="solver",
        role_call_ordinal=1,
        max_output_tokens=16000,
        stable_prefix_count=1,
    )


def test_x0_accounts_context_provider_progress_and_latest_observation_without_behavior_claims():
    transition = {
        "decision": {"action_id": "a1", "action_kind": "run_command"},
        "results": [{
            "receipt_id": "r1",
            "kind": "run_command",
            "success": True,
            "stdout": "hello world!",
        }],
        "result_receipt_ids": ["r1"],
    }
    capture = _solver_capture({
        "latest_solver_transition": transition,
        "active_completion_findings": [],
    })
    telemetry = [{
        "event_kind": "provider_attempt",
        "role": "solver",
        "logical_call_id": 1,
        "attempt_ordinal": 1,
        "provider": "azure_openai_responses",
        "deployment": "gpt-5.6-luna",
        "status": "completed",
        "response_id": "resp-1",
        "input_tokens": 100,
        "cached_input_tokens": 40,
        "cache_write_tokens": 12,
        "output_tokens": 30,
        "total_tokens": 130,
        "reasoning_tokens": 10,
        "usage_status": "reported",
        "cache_metrics_status": "reported",
        "elapsed_s": 2.5,
        "pcr_reasoning_context_requested": "current_turn",
        "pcr_reasoning_context_effective": "current_turn",
        "pcr_reasoning_context_effective_status": "matched",
        "pcr_continuity_mode": "previous_response",
    }]
    receipts = [
        {
            "receipt_id": "decision",
            "step": 1,
            "kind": "solver_decision_state",
            "success": True,
            "payload": {"action_id": "a1"},
        },
        {
            "receipt_id": "r1",
            "step": 1,
            "kind": "run_command",
            "success": True,
            "payload": {
                "stdout": "hello world!",
                "stdout_bytes": 12,
                "stderr": "",
                "stderr_bytes": 0,
            },
        },
        {
            "receipt_id": "progress",
            "step": 1,
            "kind": "solver_progress_assessment",
            "success": True,
            "payload": {
                "action_id": "a1",
                "result_receipt_ids": ["r1"],
                "progress_signals": ["new_evidence"],
                "no_relevant_progress": False,
                "equivalent_repeat": False,
            },
        },
    ]

    result = build_x0_observability(
        model_call_telemetry=telemetry,
        model_interface_captures=[capture],
        receipt_records=receipts,
    )

    assert result["schema_version"] == X0_OBSERVABILITY_SCHEMA_VERSION
    assert result["status"] == "OBSERVED_NO_MODEL_FACING_BEHAVIOR_CHANGE"
    assert result["provider"]["uncached_input_tokens"]["sum_if_all_reported"] == 60
    assert result["provider"]["cache_write_tokens"]["sum_if_all_reported"] == 12
    assert result["provider"]["fresh_reasoning_tokens"]["sum_if_all_reported"] == 10
    assert result["provider"]["historical_reasoning_tokens"]["value"] is None
    assert result["provider"]["attempts"][0]["response_id"] == "resp-1"
    assert result["provider"]["attempts"][0]["reasoning_context_effective_status"] == "matched"
    assert result["receipts"]["mechanically_positive_progress_event_count"] == 1
    assert result["latest_observation"]["explicit_raw_result_bytes"] == 12
    assert result["latest_observation"]["model_visible_latest_transition_bytes_upper_bound"] > 0
    assert result["latest_observation"]["observation_materialisation_ratio_v1"] is not None
    assert result["context"]["calls"][0]["context_packet"]["sections"]["latest_solver_transition"]["utf8_bytes"] > 0
    assert result["context"]["calls"][0]["attention_projection"]["mode"] == "control_8k"
    assert result["efficiency"]["reported_total_tokens_per_mechanically_positive_progress_event"] == 130.0


def test_x0_keeps_missing_usage_unmeasured_instead_of_turning_it_into_zero():
    result = build_x0_observability(
        model_call_telemetry=[{
            "role": "solver",
            "status": "failed",
            "usage_status": "omitted",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "cached_input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
        }],
        model_interface_captures=[],
        receipt_records=[],
    )

    assert result["provider"]["input_tokens"]["status"] == "unmeasured"
    assert result["provider"]["input_tokens"]["sum_reported"] is None
    assert result["provider"]["cached_input_tokens"]["sum_if_all_reported"] is None
    assert result["provider"]["uncached_input_tokens"]["sum_reported"] is None
    assert result["provider"]["cost_usd"]["status"] == "unmeasured"
    assert result["provider"]["historical_reasoning_tokens"]["value"] is None


def test_x0_counts_retrievals_but_does_not_infer_retrieval_regret():
    receipts = [
        {"receipt_id": "r1", "kind": "read_output", "payload": {"chunk": "x"}},
        {"receipt_id": "r2", "kind": "query_artifact_history", "payload": {}},
        {"receipt_id": "r3", "kind": "read_file", "payload": {"bytes": 10}},
    ]
    result = build_x0_observability(
        model_call_telemetry=[],
        model_interface_captures=[],
        receipt_records=receipts,
    )
    assert result["receipts"]["retrieval_action_count"] == 2
    assert result["receipts"]["retrieval_action_kind_counts"] == {
        "query_artifact_history": 1,
        "read_output": 1,
    }
    assert result["receipts"]["retrieval_regret"] is None
    assert "causally" in result["receipts"]["retrieval_regret_status"]


def test_x0_marks_real_compaction_observation_without_inventing_regret():
    result = build_x0_observability(
        model_call_telemetry=[{
            "role": "solver",
            "status": "completed",
            "provider_compaction_item_count": 1,
            "pcr_continuity_compaction_observed": True,
        }],
        model_interface_captures=[],
        receipt_records=[],
    )
    assert result["provider"]["compaction_event_count"] == 1
    assert result["provider"]["compaction_regret"] is None
    assert result["provider"]["compaction_regret_status"] == "requires_post_compaction_reconstruction_attribution"


def test_x0_provider_attempt_denominator_excludes_continuity_admission_events():
    result = build_x0_observability(
        model_call_telemetry=[
            {
                "event_kind": "provider_attempt",
                "role": "solver",
                "status": "completed",
                "input_tokens": 10,
                "cached_input_tokens": 4,
                "output_tokens": 2,
                "total_tokens": 12,
            },
            {
                "event_kind": "pcr_continuity_parent_admission",
                "role": "solver",
                "status": "completed",
                "pcr_continuity_parent_disposition": "committed",
            },
        ],
        model_interface_captures=[],
        receipt_records=[],
    )
    provider = result["provider"]
    assert provider["telemetry_event_count"] == 2
    assert provider["telemetry_event_kind_counts"] == {
        "pcr_continuity_parent_admission": 1,
        "provider_attempt": 1,
    }
    assert provider["attempt_count"] == 1
    assert provider["input_tokens"]["sum_if_all_reported"] == 10
    assert len(provider["attempts"]) == 1
    assert provider["attempts"][0]["event_kind"] == "provider_attempt"

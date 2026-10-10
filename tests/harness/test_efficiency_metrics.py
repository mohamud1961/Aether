from __future__ import annotations

import pytest
from aether.kernel import KernelResult
from aether.ledger import Receipt
from aether.result_metrics import mechanical_efficiency_metrics, provider_efficiency_metrics


def test_mechanical_efficiency_metrics_aggregate_command_supervision() -> None:
    result = KernelResult(
        status="completed",
        step=1,
        reconfigurations=0,
        receipts=(
            Receipt(
                receipt_id="cmd-1",
                step=0,
                kind="run_command",
                success=True,
                summary="ok",
                payload={
                    "timed_out": False,
                    "metrics": {
                        "wall_time_s": 2.5,
                        "supervision_launch_elapsed_s": 0.2,
                        "supervision_status_probe_count": 4,
                        "supervision_status_probe_elapsed_s": 0.7,
                        "supervision_output_download_elapsed_s": 0.1,
                    },
                },
            ),
            Receipt(
                receipt_id="cmd-2",
                step=1,
                kind="run_command",
                success=False,
                summary="timeout",
                payload={
                    "timed_out": True,
                    "metrics": {
                        "wall_time_s": 3.5,
                        "supervision_launch_elapsed_s": 0.3,
                        "supervision_status_probe_count": 6,
                        "supervision_status_probe_elapsed_s": 1.2,
                        "supervision_output_download_elapsed_s": 0.15,
                    },
                },
            ),
        ),
    )
    metrics = mechanical_efficiency_metrics(result)
    assert metrics["mechanical_run_command_count"] == 2
    assert metrics["mechanical_run_command_failure_count"] == 1
    assert metrics["mechanical_run_command_timeout_count"] == 1
    assert metrics["mechanical_run_command_wall_time_s"] == 6.0
    assert metrics["harbor_supervision_launch_elapsed_s"] == 0.5
    assert metrics["harbor_supervision_status_probe_count"] == 10
    assert metrics["harbor_supervision_status_probe_elapsed_s"] == 1.9
    assert metrics["harbor_supervision_output_download_elapsed_s"] == 0.25


def test_provider_efficiency_metrics_separate_solver_verifier_and_cache() -> None:
    events = [
        {
            "event_kind": "provider_attempt",
            "role": "solver",
            "status": "completed",
            "elapsed_s": 3.0,
            "provider_request_elapsed_s": 2.4,
            "provider_request_build_elapsed_s": 0.02,
            "throughput_wait_s": 1.0,
            "throughput_wait_by_reason_s": {"dispatch_spacing": 0.8, "rolling_quota": 0.2},
            "input_tokens": 1000,
            "cached_input_tokens": 800,
            "cache_write_tokens": 50,
            "output_tokens": 100,
            "reasoning_tokens": 60,
            "provider_websocket_receive_timeout_slice_count": 2,
            "provider_websocket_connect_elapsed_s": 0.4,
            "provider_websocket_serialize_elapsed_s": 0.01,
            "provider_websocket_send_elapsed_s": 0.02,
            "provider_websocket_receive_elapsed_s": 2.3,
            "provider_websocket_json_decode_elapsed_s": 0.01,
            "provider_websocket_total_call_elapsed_s": 2.8,
            "provider_websocket_first_event_elapsed_s": 0.5,
            "provider_websocket_connection_reused": False,
            "provider_websocket_connection_persisted_after_completed": True,
            "persistent_continuity_reanchor_attempted": False,
            "persistent_continuity_reanchor_succeeded": False,
        },
        {
            "event_kind": "provider_attempt",
            "role": "verifier",
            "status": "completed",
            "elapsed_s": 2.0,
            "provider_request_elapsed_s": 1.5,
            "provider_request_build_elapsed_s": 0.03,
            "throughput_wait_s": 0.5,
            "throughput_wait_by_reason_s": {"fifo_queue": 0.5},
            "input_tokens": 400,
            "cached_input_tokens": 100,
            "cache_write_tokens": 0,
            "output_tokens": 50,
            "reasoning_tokens": 10,
            "provider_websocket_receive_timeout_slice_count": 1,
            "provider_websocket_connect_elapsed_s": 0.0,
            "provider_websocket_serialize_elapsed_s": 0.01,
            "provider_websocket_send_elapsed_s": 0.01,
            "provider_websocket_receive_elapsed_s": 1.7,
            "provider_websocket_json_decode_elapsed_s": 0.01,
            "provider_websocket_total_call_elapsed_s": 1.8,
            "provider_websocket_first_event_elapsed_s": 1.5,
            "provider_websocket_connection_reused": True,
            "provider_websocket_connection_persisted_after_completed": True,
            "persistent_continuity_reanchor_attempted": True,
            "persistent_continuity_reanchor_succeeded": True,
        },
        {
            "event_kind": "provider_attempt",
            "role": "solver",
            "status": "failed",
            "elapsed_s": 7.0,
            "attempt_ordinal": 1,
            "provider_request_build_elapsed_s": 0.01,
            "provider_request_elapsed_s": 4.5,
            "throughput_wait_s": 2.0,
            "provider_finish_reason": "length",
            "provider_output_cap_reached": True,
            "max_output_tokens": 24576,
            "reasoning_tokens": 24576,
            "native_tool_call_observed_known": True,
            "native_tool_call_observed": False,
            "provider_websocket_receive_timeout_slice_count": 3,
        },
        {"event_kind": "persistent_continuity_parent_admission", "role": "solver"},
    ]
    metrics = provider_efficiency_metrics(events)
    assert metrics["provider_attempt_count"] == 3
    assert metrics["provider_completed_attempt_count"] == 2
    assert metrics["provider_failed_attempt_count"] == 1
    assert metrics["provider_elapsed_s"] == 8.4
    assert metrics["provider_elapsed_p50_s"] == 2.4
    assert metrics["provider_elapsed_p95_s"] == 4.5
    assert metrics["provider_attempt_elapsed_s"] == 12.0
    assert metrics["provider_request_build_elapsed_s"] == 0.06
    assert metrics["provider_admission_wait_s"] == 3.5
    assert metrics["provider_admission_wait_p50_s"] == 1.0
    assert metrics["provider_admission_wait_p95_s"] == 2.0
    assert metrics["provider_admission_wait_missing_attempt_count"] == 0
    assert metrics["provider_admission_wait_by_reason_s"] == {
        "dispatch_spacing": 0.8,
        "fifo_queue": 0.5,
        "rolling_quota": 0.2,
    }
    assert metrics["provider_output_cap_reached_count"] == 1
    assert metrics["provider_no_native_action_attempt_count"] == 1
    assert metrics["provider_cap_without_native_action_count"] == 1
    assert metrics["provider_reasoning_cap_no_action_candidate_count"] == 1
    assert metrics["solver_provider_attempt_count"] == 2
    assert metrics["solver_provider_elapsed_s"] == 6.9
    assert metrics["verifier_provider_attempt_count"] == 1
    assert metrics["verifier_provider_elapsed_s"] == 1.5
    assert metrics["provider_usage_row_count"] == 2
    assert metrics["provider_usage_missing_attempt_count"] == 1
    assert metrics["provider_input_tokens"] == 1400
    assert metrics["provider_cached_input_tokens"] == 900
    assert metrics["provider_noncached_input_tokens"] == 500
    assert metrics["provider_cache_write_tokens"] == 50
    assert metrics["provider_output_tokens"] == 150
    assert metrics["provider_reasoning_tokens"] == 70
    assert metrics["provider_websocket_receive_timeout_slice_count"] == 6
    assert metrics["provider_websocket_connect_elapsed_s"] == 0.4
    assert metrics["provider_websocket_serialize_elapsed_s"] == 0.02
    assert metrics["provider_websocket_send_elapsed_s"] == 0.03
    assert metrics["provider_websocket_receive_elapsed_s"] == 4.0
    assert metrics["provider_websocket_json_decode_elapsed_s"] == 0.02
    assert metrics["provider_websocket_total_call_elapsed_s"] == 4.6
    assert metrics["provider_websocket_connection_reused_count"] == 1
    assert metrics["provider_websocket_connection_persisted_count"] == 2
    assert metrics["provider_websocket_first_event_observation_count"] == 2
    assert metrics["provider_websocket_first_event_elapsed_s_mean"] == 1.0
    assert metrics["provider_continuity_reanchor_attempt_count"] == 1
    assert metrics["provider_continuity_reanchor_success_count"] == 1


def test_provider_efficiency_metrics_aggregates_excluded_deadline_wait() -> None:
    events = [
        {
            "event_kind": "provider_attempt",
            "status": "completed",
            "role": "solver",
            "throughput_wait_s": 3.0,
            "throughput_task_deadline_excluded_wait_s": 3.0,
            "input_tokens": 10,
            "output_tokens": 2,
        },
        {
            "event_kind": "provider_attempt",
            "status": "completed",
            "role": "solver",
            "throughput_wait_s": 4.5,
            "throughput_task_deadline_excluded_wait_s": 4.5,
            "input_tokens": 11,
            "output_tokens": 3,
        },
    ]
    metrics = provider_efficiency_metrics(events)
    assert metrics["provider_admission_wait_s"] == pytest.approx(7.5)
    assert metrics["provider_task_deadline_excluded_wait_s"] == pytest.approx(7.5)
    assert metrics["provider_task_deadline_excluded_wait_attempt_count"] == 2

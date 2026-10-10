"""Deterministic run-result metrics derived from kernel receipts.

These helpers deliberately read the ledger/result evidence, not transient model
hook state, so result rows cannot hide parse/protocol errors that occurred
before a later successful model call reset hook-local buffers.
"""
from __future__ import annotations

from collections import Counter
from math import ceil
from typing import Any, Mapping, Sequence

from .kernel import KernelResult
from .ledger import Receipt


def _summary(receipt: Receipt, *, max_chars: int = 500) -> dict[str, Any]:
    payload = receipt.payload or {}
    return {
        "receipt_id": receipt.receipt_id,
        "step": receipt.step,
        "kind": receipt.kind,
        "success": receipt.success,
        "failure_class": receipt.failure_class,
        "summary": receipt.summary[:max_chars],
        "error": str(payload.get("error", ""))[:max_chars],
        "retry_attempted": payload.get("retry_attempted"),
    }


def parse_protocol_metrics(result: KernelResult) -> dict[str, Any]:
    """Aggregate solver parse/protocol evidence from immutable receipts."""
    receipts = tuple(result.receipts or ())
    solver_parse = [r for r in receipts if r.kind == "solver_parse_error"]
    verifier_parse = [r for r in receipts if r.kind == "verifier_parse_error"]
    turn_validation = [r for r in receipts if r.kind == "turn_validation"]
    unknown_actions = [r for r in receipts if r.kind == "unknown_action"]
    action_validation = [r for r in receipts if r.kind == "action_validation"]
    valid_action_steps: list[int] = []
    for receipt in receipts:
        payload = receipt.payload or {}
        if (
            receipt.kind == "runtime_accounting"
            and str(payload.get("event", "")) == "accepted_for_dispatch"
        ):
            valid_action_steps.append(receipt.step)
        elif receipt.kind in {"run_command", "read_file", "write_file", "check_result", "service_probe", "artifact_inspection"}:
            # Legacy/non-PERSISTENT compatibility path. Current PERSISTENT should be measured
            # from the kernel-owned accepted_for_dispatch event above.
            valid_action_steps.append(receipt.step)
    repair_attempts = sum(1 for r in solver_parse if bool((r.payload or {}).get("retry_attempted")))
    repair_failures = sum(1 for r in solver_parse if (r.receipt_id or "").endswith("retry"))
    return {
        "solver_parse_error_count": len(solver_parse),
        "solver_parse_error_examples": [_summary(r) for r in solver_parse[:5]],
        "verifier_parse_error_count": len(verifier_parse),
        "verifier_parse_error_examples": [_summary(r) for r in verifier_parse[:8]],
        "turn_validation_error_count": len(turn_validation),
        "unknown_action_count": len(unknown_actions),
        "action_validation_error_count": len(action_validation),
        "tool_schema_error_count": len(turn_validation) + len(unknown_actions) + len(action_validation),
        "parse_repair_attempts": repair_attempts,
        "parse_repair_failures": repair_failures,
        "parse_repair_successes": max(0, repair_attempts - repair_failures),
        "first_valid_action_step": min(valid_action_steps) if valid_action_steps else None,
    }


def model_parse_errors_for_row(result: KernelResult, hook_errors: Sequence[str] | None = None) -> list[Any]:
    """Return row-safe parse/protocol errors from receipts plus live hook state."""
    metrics = parse_protocol_metrics(result)
    row: list[Any] = [
        *metrics["solver_parse_error_examples"],
        *metrics["verifier_parse_error_examples"],
    ]
    durable_errors = {
        str(item.get("error", "")).strip()
        for item in metrics["verifier_parse_error_examples"]
        if isinstance(item, Mapping) and str(item.get("error", "")).strip()
    }
    for error in hook_errors or ():
        text = str(error).strip()
        if text and text[:500] not in durable_errors:
            row.append({"source": "model_hooks.last_parse_errors", "error": text[:500]})
    return row


def repeated_action_metrics(result: KernelResult) -> dict[str, Any]:
    """Summarise repeated/low-information loop evidence from receipts."""
    receipts = tuple(result.receipts or ())
    commands: Counter[str] = Counter()
    writes: Counter[str] = Counter()
    submit_steps: set[int] = set()
    unchanged_submit_skips = 0
    for receipt in receipts:
        payload = receipt.payload or {}
        if receipt.kind == "run_command":
            command = str(payload.get("command", "")).strip()
            if command:
                commands[command] += 1
        elif receipt.kind == "write_file":
            path = str(payload.get("path", "")).strip()
            content_hash = str(payload.get("content_hash", "") or payload.get("sha256", "")).strip()
            if path:
                writes[f"{path}:{content_hash}"] += 1
        elif receipt.kind == "model_verifier_skipped" and payload.get("reason") == "active_findings_without_intervening_evidence":
            unchanged_submit_skips += 1
            submit_steps.add(receipt.step)
        elif receipt.kind == "submit_outcome":
            submit_steps.add(receipt.step)
        elif (
            receipt.kind == "runtime_accounting"
            and str(payload.get("event", "")) == "submit_outcome"
        ):
            submit_steps.add(receipt.step)
    return {
        "repeated_command_count": sum(count - 1 for count in commands.values() if count > 1),
        "repeated_write_count": sum(count - 1 for count in writes.values() if count > 1),
        "submit_without_new_evidence_count": unchanged_submit_skips,
        "submit_receipt_count": len(submit_steps),
        "repeated_commands": [
            {"command": command, "count": count}
            for command, count in commands.most_common()
            if count > 1
        ][:10],
    }



def mechanical_efficiency_metrics(result: KernelResult) -> dict[str, Any]:
    """Aggregate mechanical command/supervision cost from immutable receipts."""
    receipts = tuple(result.receipts or ())
    commands = [receipt for receipt in receipts if receipt.kind == "run_command"]
    metric_rows = [
        dict(receipt.payload.get("metrics", {}) or {})
        for receipt in commands
        if isinstance(receipt.payload, Mapping)
    ]

    def _sum_numeric(key: str) -> float:
        total = 0.0
        for row in metric_rows:
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total += float(value)
        return round(total, 6)

    def _sum_integer(key: str) -> int:
        total = 0
        for row in metric_rows:
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total += int(value)
        return total

    return {
        "mechanical_run_command_count": len(commands),
        "mechanical_run_command_failure_count": sum(not receipt.success for receipt in commands),
        "mechanical_run_command_timeout_count": sum(
            bool((receipt.payload or {}).get("timed_out")) for receipt in commands
        ),
        "mechanical_run_command_wall_time_s": _sum_numeric("wall_time_s"),
        "harbor_supervision_launch_elapsed_s": _sum_numeric("supervision_launch_elapsed_s"),
        "harbor_supervision_status_probe_count": _sum_integer("supervision_status_probe_count"),
        "harbor_supervision_status_probe_elapsed_s": _sum_numeric("supervision_status_probe_elapsed_s"),
        "harbor_supervision_output_download_elapsed_s": _sum_numeric("supervision_output_download_elapsed_s"),
    }


def provider_efficiency_metrics(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate provider latency/token facts without interpreting model quality."""
    attempts = [
        event for event in events
        if isinstance(event, Mapping) and str(event.get("event_kind") or "") == "provider_attempt"
    ]

    def _sum_numeric(key: str, rows: Sequence[Mapping[str, Any]] = attempts) -> float:
        total = 0.0
        for row in rows:
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total += float(value)
        return round(total, 6)

    def _sum_integer(key: str, rows: Sequence[Mapping[str, Any]] = attempts) -> int:
        total = 0
        for row in rows:
            value = row.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                total += value
        return total

    def _values(key: str) -> list[float]:
        return [
            float(row[key])
            for row in attempts
            if isinstance(row.get(key), (int, float))
            and not isinstance(row.get(key), bool)
            and float(row[key]) >= 0
        ]

    def _percentile(values: Sequence[float], quantile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, ceil(quantile * len(ordered)) - 1))
        return round(ordered[index], 6)

    solver = [row for row in attempts if str(row.get("role") or "") == "solver"]
    verifier = [row for row in attempts if str(row.get("role") or "") == "verifier"]
    usage_rows = [
        row for row in attempts
        if isinstance(row.get("input_tokens"), int) or isinstance(row.get("output_tokens"), int)
    ]
    cached = _sum_integer("cached_input_tokens", usage_rows)
    input_tokens = _sum_integer("input_tokens", usage_rows)
    admission_waits = _values("throughput_wait_s")
    excluded_deadline_waits = _values("throughput_task_deadline_excluded_wait_s")
    provider_latencies = _values("provider_request_elapsed_s")
    request_build_rows = [row for row in attempts if row.get("attempt_ordinal", 1) == 1]
    request_build = _sum_numeric("provider_request_build_elapsed_s", request_build_rows)
    wait_by_reason: dict[str, float] = {}
    for row in attempts:
        reasons = row.get("throughput_wait_by_reason_s")
        if not isinstance(reasons, Mapping):
            continue
        for reason, value in reasons.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                name = str(reason)
                wait_by_reason[name] = wait_by_reason.get(name, 0.0) + float(value)
    output_cap_rows = [row for row in attempts if row.get("provider_output_cap_reached") is True]
    native_action_known = [
        row for row in attempts
        if row.get("native_tool_call_observed_known") is True
    ]
    cap_without_native_action = [
        row for row in output_cap_rows
        if row.get("native_tool_call_observed_known") is True
        and row.get("native_tool_call_observed") is False
    ]
    reasoning_cap_no_action_candidates = [
        row for row in cap_without_native_action
        if isinstance(row.get("max_output_tokens"), int)
        and not isinstance(row.get("max_output_tokens"), bool)
        and row["max_output_tokens"] > 0
        and isinstance(row.get("reasoning_tokens"), int)
        and not isinstance(row.get("reasoning_tokens"), bool)
        and row["reasoning_tokens"] >= row["max_output_tokens"]
    ]
    first_events = [
        float(row["provider_websocket_first_event_elapsed_s"])
        for row in attempts
        if isinstance(row.get("provider_websocket_first_event_elapsed_s"), (int, float))
    ]
    return {
        "provider_attempt_count": len(attempts),
        "provider_completed_attempt_count": sum(str(row.get("status") or "") == "completed" for row in attempts),
        "provider_failed_attempt_count": sum(str(row.get("status") or "") == "failed" for row in attempts),
        "provider_elapsed_s": _sum_numeric("provider_request_elapsed_s"),
        "provider_elapsed_p50_s": _percentile(provider_latencies, 0.50),
        "provider_elapsed_p95_s": _percentile(provider_latencies, 0.95),
        "provider_attempt_elapsed_s": _sum_numeric("elapsed_s"),
        "provider_request_build_elapsed_s": request_build,
        "provider_admission_wait_s": round(sum(admission_waits), 6),
        "provider_admission_wait_p50_s": _percentile(admission_waits, 0.50),
        "provider_admission_wait_p95_s": _percentile(admission_waits, 0.95),
        "provider_admission_wait_missing_attempt_count": len(attempts) - len(admission_waits),
        "provider_task_deadline_excluded_wait_s": round(sum(excluded_deadline_waits), 6),
        "provider_task_deadline_excluded_wait_attempt_count": len(excluded_deadline_waits),
        "provider_admission_wait_by_reason_s": {
            key: round(value, 6) for key, value in sorted(wait_by_reason.items())
        },
        "provider_output_cap_reached_count": len(output_cap_rows),
        "provider_no_native_action_attempt_count": sum(
            row.get("native_tool_call_observed") is False for row in native_action_known
        ),
        "provider_cap_without_native_action_count": len(cap_without_native_action),
        "provider_reasoning_cap_no_action_candidate_count": len(reasoning_cap_no_action_candidates),
        "solver_provider_attempt_count": len(solver),
        "solver_provider_elapsed_s": _sum_numeric("provider_request_elapsed_s", solver),
        "verifier_provider_attempt_count": len(verifier),
        "verifier_provider_elapsed_s": _sum_numeric("provider_request_elapsed_s", verifier),
        "provider_usage_row_count": len(usage_rows),
        "provider_usage_missing_attempt_count": len(attempts) - len(usage_rows),
        "provider_input_tokens": input_tokens,
        "provider_cached_input_tokens": cached,
        "provider_noncached_input_tokens": max(0, input_tokens - cached),
        "provider_cache_write_tokens": _sum_integer("cache_write_tokens", usage_rows),
        "provider_output_tokens": _sum_integer("output_tokens", usage_rows),
        "provider_reasoning_tokens": _sum_integer("reasoning_tokens", usage_rows),
        "provider_websocket_receive_timeout_slice_count": _sum_integer("provider_websocket_receive_timeout_slice_count"),
        "provider_websocket_connect_elapsed_s": _sum_numeric("provider_websocket_connect_elapsed_s"),
        "provider_websocket_serialize_elapsed_s": _sum_numeric("provider_websocket_serialize_elapsed_s"),
        "provider_websocket_send_elapsed_s": _sum_numeric("provider_websocket_send_elapsed_s"),
        "provider_websocket_receive_elapsed_s": _sum_numeric("provider_websocket_receive_elapsed_s"),
        "provider_websocket_json_decode_elapsed_s": _sum_numeric("provider_websocket_json_decode_elapsed_s"),
        "provider_websocket_total_call_elapsed_s": _sum_numeric("provider_websocket_total_call_elapsed_s"),
        "provider_websocket_connection_reused_count": sum(row.get("provider_websocket_connection_reused") is True for row in attempts),
        "provider_websocket_connection_persisted_count": sum(row.get("provider_websocket_connection_persisted_after_completed") is True for row in attempts),
        "provider_websocket_first_event_observation_count": len(first_events),
        "provider_websocket_first_event_elapsed_s_mean": (
            round(sum(first_events) / len(first_events), 6) if first_events else None
        ),
        "provider_continuity_reanchor_attempt_count": sum(row.get("persistent_continuity_reanchor_attempted") is True for row in attempts),
        "provider_continuity_reanchor_success_count": sum(row.get("persistent_continuity_reanchor_succeeded") is True for row in attempts),
    }

def run_metrics_for_row(result: KernelResult, hook_errors: Sequence[str] | None = None) -> dict[str, Any]:
    metrics = parse_protocol_metrics(result)
    metrics.update(repeated_action_metrics(result))
    metrics.update(mechanical_efficiency_metrics(result))
    metrics["model_parse_errors"] = model_parse_errors_for_row(result, hook_errors)
    return metrics

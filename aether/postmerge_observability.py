"""Post-merge X0 observability summaries.

This module is instrumentation only.  It consumes evidence Aether already
captures (exact model-interface manifests, provider telemetry, and immutable
receipt records) and derives bounded accounting views without changing model
messages, tool schemas, dispatch, context policy, or provider configuration.

The design deliberately distinguishes *unmeasured* from zero.  Provider-native
historical reasoning, monetary cost, retrieval regret, and compaction regret
are not inferred when the underlying evidence does not expose them.
"""
from __future__ import annotations

from collections import Counter
import json
from typing import Any, Iterable, Mapping


X0_OBSERVABILITY_SCHEMA_VERSION = "aether.postmerge.x0_observability.v1"
_CONTEXT_PACKET_PREFIX = "[context_packet]\n"
_RETRIEVAL_KINDS = frozenset({
    "read_output",
    "grep_output",
    "read_file_page",
    "query_artifact_history",
})
_POSITIVE_PROGRESS_SIGNALS = frozenset({
    "state_change",
    "new_evidence",
    "verification",
    "requirement_evidence",
})


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _utf8_bytes(value: Any) -> int:
    if isinstance(value, bytes):
        return len(value)
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    return len(_stable_json(value).encode("utf-8"))


def _token_estimate_v1_from_bytes(byte_count: int) -> int:
    return max(1, (int(byte_count) + 3) // 4) if int(byte_count) > 0 else 0


def _reported_sum(rows: list[Mapping[str, Any]], field: str) -> dict[str, Any]:
    values: list[int | float] = []
    for row in rows:
        value = row.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        values.append(value)
    return {
        "reported_attempts": len(values),
        "attempts": len(rows),
        "sum_reported": sum(values) if values else None,
        "sum_if_all_reported": sum(values) if len(values) == len(rows) and rows else None,
        "status": (
            "fully_reported" if rows and len(values) == len(rows)
            else ("partially_reported" if values else "unmeasured")
        ),
    }


def _context_packet_from_capture(capture: Mapping[str, Any]) -> dict[str, Any] | None:
    messages = capture.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if not isinstance(message, Mapping):
            continue
        content = str(message.get("content") or "")
        if not content.startswith(_CONTEXT_PACKET_PREFIX):
            continue
        try:
            packet = json.loads(content[len(_CONTEXT_PACKET_PREFIX):])
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return dict(packet) if isinstance(packet, Mapping) else None
    return None


def _context_packet_accounting(packet: Mapping[str, Any] | None) -> dict[str, Any]:
    if packet is None:
        return {
            "status": "not_present_or_unparseable",
            "section_count": 0,
            "utf8_bytes": None,
            "token_estimate_v1": None,
            "sections": {},
        }
    body = dict(packet)
    encoded = _stable_json(body)
    sections: dict[str, Any] = {}
    for key, value in sorted(body.items()):
        byte_count = _utf8_bytes(value)
        sections[str(key)] = {
            "utf8_bytes": byte_count,
            "token_estimate_v1": _token_estimate_v1_from_bytes(byte_count),
        }
    return {
        "status": "measured",
        "section_count": len(body),
        "utf8_bytes": len(encoded.encode("utf-8")),
        "token_estimate_v1": _token_estimate_v1_from_bytes(len(encoded.encode("utf-8"))),
        "sections": sections,
    }


def _interface_rows(captures: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for capture in captures:
        if not isinstance(capture, Mapping):
            continue
        manifest = capture.get("manifest")
        if not isinstance(manifest, Mapping):
            continue
        aggregate = manifest.get("aggregate") if isinstance(manifest.get("aggregate"), Mapping) else {}
        stable = manifest.get("stable_prefix") if isinstance(manifest.get("stable_prefix"), Mapping) else {}
        volatile = manifest.get("volatile") if isinstance(manifest.get("volatile"), Mapping) else {}
        packet = _context_packet_from_capture(capture)
        rows.append({
            "model_role": str(manifest.get("model_role") or ""),
            "role_call_ordinal": int(manifest.get("role_call_ordinal") or 0),
            "transcript_sha256": str(manifest.get("transcript_sha256") or ""),
            "message_count": int(manifest.get("message_count") or 0),
            "stable_prefix_count": int(manifest.get("stable_prefix_count") or 0),
            "aggregate": dict(aggregate),
            "stable_prefix": dict(stable),
            "dynamic_or_volatile": dict(volatile),
            "stable_prefix_byte_ratio": manifest.get("stable_prefix_byte_ratio"),
            "exact_duplicate_message_groups": len(manifest.get("exact_duplicate_messages") or ()),
            "attention_projection": (
                dict(manifest.get("attention_projection"))
                if isinstance(manifest.get("attention_projection"), Mapping)
                else None
            ),
            "postmerge_research": (
                dict(manifest.get("postmerge_research"))
                if isinstance(manifest.get("postmerge_research"), Mapping)
                else None
            ),
            "context_packet": _context_packet_accounting(packet),
        })
    return rows


def _provider_rows(telemetry: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in telemetry:
        if not isinstance(source, Mapping):
            continue
        event_kind = str(source.get("event_kind") or "").strip()
        if event_kind and event_kind != "provider_attempt":
            continue
        input_tokens = source.get("input_tokens")
        cached_tokens = source.get("cached_input_tokens")
        cache_write_tokens = source.get("cache_write_tokens")
        uncached_tokens: int | None = None
        if (
            isinstance(input_tokens, int) and not isinstance(input_tokens, bool)
            and isinstance(cached_tokens, int) and not isinstance(cached_tokens, bool)
        ):
            uncached_tokens = max(0, input_tokens - cached_tokens)
        response_id = (
            str(source.get("response_id") or "").strip()
            or str(source.get("job_id") or "").strip()
            or None
        )
        compaction_count = source.get("provider_compaction_item_count")
        if not isinstance(compaction_count, int) or isinstance(compaction_count, bool):
            compaction_count = None
        rows.append({
            "event_kind": event_kind or "provider_attempt_legacy",
            "role": str(source.get("role") or ""),
            "logical_call_id": source.get("logical_call_id"),
            "attempt_ordinal": source.get("attempt_ordinal"),
            "status": str(source.get("status") or ""),
            "provider": str(source.get("provider") or ""),
            "deployment": str(source.get("deployment") or ""),
            "response_id": response_id,
            "input_tokens": input_tokens if isinstance(input_tokens, (int, float)) and not isinstance(input_tokens, bool) else None,
            "cached_input_tokens": cached_tokens if isinstance(cached_tokens, (int, float)) and not isinstance(cached_tokens, bool) else None,
            "cache_write_tokens": cache_write_tokens if isinstance(cache_write_tokens, (int, float)) and not isinstance(cache_write_tokens, bool) else None,
            "uncached_input_tokens": uncached_tokens,
            "output_tokens": source.get("output_tokens") if isinstance(source.get("output_tokens"), (int, float)) and not isinstance(source.get("output_tokens"), bool) else None,
            "total_tokens": source.get("total_tokens") if isinstance(source.get("total_tokens"), (int, float)) and not isinstance(source.get("total_tokens"), bool) else None,
            "fresh_reasoning_tokens": source.get("reasoning_tokens") if isinstance(source.get("reasoning_tokens"), (int, float)) and not isinstance(source.get("reasoning_tokens"), bool) else None,
            "historical_reasoning_tokens": None,
            "historical_reasoning_tokens_status": "not_separately_reported_by_provider",
            "usage_status": str(source.get("usage_status") or ""),
            "cache_metrics_status": str(source.get("cache_metrics_status") or ""),
            "instructions_chars": source.get("instructions_chars"),
            "input_chars": source.get("input_chars"),
            "tool_schema_utf8_bytes": (
                source.get("pcr_primary_provider_schema_utf8_bytes")
                if source.get("pcr_primary_provider_schema_utf8_bytes") is not None
                else source.get("verifier_native_tool_schema_utf8_bytes")
            ),
            "prompt_cache_key_mode": source.get("prompt_cache_key_mode"),
            "pcr_continuity_mode": source.get("pcr_continuity_mode"),
            "reasoning_context_requested": source.get("pcr_reasoning_context_requested"),
            "reasoning_context_effective": source.get("pcr_reasoning_context_effective"),
            "reasoning_context_effective_status": source.get("pcr_reasoning_context_effective_status"),
            "provider_compaction_item_count": compaction_count,
            "compaction_observed": bool(
                (isinstance(compaction_count, int) and compaction_count > 0)
                or source.get("pcr_continuity_compaction_observed") is True
            ),
            "elapsed_s": source.get("elapsed_s") if isinstance(source.get("elapsed_s"), (int, float)) and not isinstance(source.get("elapsed_s"), bool) else None,
            "cost_usd": source.get("cost_usd") if isinstance(source.get("cost_usd"), (int, float)) and not isinstance(source.get("cost_usd"), bool) else None,
        })
    return rows


def _explicit_result_bytes(receipt: Mapping[str, Any]) -> tuple[int | None, list[str]]:
    """Return exact action-result byte counts only when the receipt exposes them.

    This is intentionally narrower than serialized receipt size.  We do not
    pretend that metadata bytes are equivalent to stdout/file/artifact bytes.
    """
    kind = str(receipt.get("kind") or "")
    payload = receipt.get("payload") if isinstance(receipt.get("payload"), Mapping) else {}
    sources: list[str] = []
    total = 0

    def add(field: str) -> None:
        nonlocal total
        value = payload.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            total += value
            sources.append(field)

    if kind == "run_command":
        add("stdout_bytes")
        add("stderr_bytes")
    elif kind in {"read_file", "write_file", "artifact_inspection"}:
        add("bytes")
    elif kind in {"read_output", "grep_output", "read_file_page"}:
        if isinstance(payload.get("bytes_read"), int) and not isinstance(payload.get("bytes_read"), bool):
            add("bytes_read")
        elif isinstance(payload.get("chunk"), str):
            total += _utf8_bytes(payload.get("chunk"))
            sources.append("chunk_utf8_bytes")
    elif kind == "terminal_read" and isinstance(payload.get("output"), str):
        total += _utf8_bytes(payload.get("output"))
        sources.append("output_utf8_bytes")
    elif kind == "environment_extension" and "result" in payload:
        total += _utf8_bytes(payload.get("result"))
        sources.append("result_stable_json_utf8_bytes")

    return (total, sources) if sources else (None, [])


def _latest_observation_accounting(
    receipt_records: list[Mapping[str, Any]],
    interface_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    latest_progress: Mapping[str, Any] | None = None
    for receipt in reversed(receipt_records):
        if str(receipt.get("kind") or "") == "solver_progress_assessment":
            latest_progress = receipt
            break
    if latest_progress is None:
        return {
            "status": "no_solver_progress_assessment",
            "result_receipt_ids": [],
            "explicit_raw_result_bytes": None,
            "model_visible_result_view_bytes": None,
            "observation_materialisation_ratio_v1": None,
        }

    payload = latest_progress.get("payload") if isinstance(latest_progress.get("payload"), Mapping) else {}
    result_ids = [str(item) for item in payload.get("result_receipt_ids", ()) if str(item).strip()]
    by_id = {str(row.get("receipt_id") or ""): row for row in receipt_records}
    raw_values: list[int] = []
    raw_rows: list[dict[str, Any]] = []
    for receipt_id in result_ids:
        receipt = by_id.get(receipt_id)
        if receipt is None:
            continue
        byte_count, sources = _explicit_result_bytes(receipt)
        raw_rows.append({
            "receipt_id": receipt_id,
            "kind": receipt.get("kind"),
            "explicit_result_bytes": byte_count,
            "byte_count_sources": sources,
        })
        if byte_count is not None:
            raw_values.append(byte_count)
    raw_total = sum(raw_values) if raw_values and len(raw_values) == len(raw_rows) else None

    latest_solver_packet: Mapping[str, Any] | None = None
    for row in reversed(interface_rows):
        if str(row.get("model_role") or "") != "solver":
            continue
        packet = row.get("context_packet")
        if isinstance(packet, Mapping):
            latest_solver_packet = packet
            break
    model_visible_result_bytes: int | None = None
    if isinstance(latest_solver_packet, Mapping):
        # The accounting view stores per-section sizes, not the parsed value.
        sections = latest_solver_packet.get("sections")
        if isinstance(sections, Mapping):
            transition = sections.get("latest_solver_transition")
            if isinstance(transition, Mapping) and isinstance(transition.get("utf8_bytes"), int):
                # This is a conservative upper bound because the transition
                # section also carries decision/mechanical metadata.  Do not
                # mislabel it as pure result bytes.
                model_visible_result_bytes = int(transition["utf8_bytes"])

    ratio = None
    if raw_total is not None and raw_total > 0 and model_visible_result_bytes is not None:
        ratio = round(model_visible_result_bytes / raw_total, 6)
    return {
        "status": "measured_with_explicit_byte_counts" if raw_total is not None else "partial_explicit_byte_counts",
        "progress_receipt_id": latest_progress.get("receipt_id"),
        "result_receipt_ids": result_ids,
        "results": raw_rows,
        "explicit_raw_result_bytes": raw_total,
        "model_visible_latest_transition_bytes_upper_bound": model_visible_result_bytes,
        "observation_materialisation_ratio_v1": ratio,
        "ratio_semantics": (
            "latest_solver_transition serialized bytes / exact explicit action-result bytes; "
            "numerator is an upper bound because it includes decision/mechanical metadata"
        ),
    }


def _receipt_accounting(receipts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [row for row in receipts if isinstance(row, Mapping)]
    kind_counts = Counter(str(row.get("kind") or "") for row in rows)
    retrieval_rows = [row for row in rows if str(row.get("kind") or "") in _RETRIEVAL_KINDS]
    progress_rows = [row for row in rows if str(row.get("kind") or "") == "solver_progress_assessment"]
    positive = 0
    no_progress = 0
    equivalent_repeat = 0
    progress_signal_counts: Counter[str] = Counter()
    for row in progress_rows:
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        signals = [str(item) for item in payload.get("progress_signals", ())]
        progress_signal_counts.update(signals)
        if _POSITIVE_PROGRESS_SIGNALS.intersection(signals):
            positive += 1
        if payload.get("no_relevant_progress") is True:
            no_progress += 1
        if payload.get("equivalent_repeat") is True:
            equivalent_repeat += 1
    return {
        "receipt_count": len(rows),
        "receipt_kind_counts": dict(sorted(kind_counts.items())),
        "retrieval_action_count": len(retrieval_rows),
        "retrieval_action_kind_counts": dict(sorted(Counter(
            str(row.get("kind") or "") for row in retrieval_rows
        ).items())),
        "retrieval_regret": None,
        "retrieval_regret_status": "not_causally_attributable_without_an_omission_treatment",
        "solver_progress_assessment_count": len(progress_rows),
        "mechanically_positive_progress_event_count": positive,
        "no_relevant_progress_event_count": no_progress,
        "equivalent_repeat_event_count": equivalent_repeat,
        "progress_signal_counts": dict(sorted(progress_signal_counts.items())),
    }


def build_x0_observability(
    *,
    model_call_telemetry: Iterable[Mapping[str, Any]],
    model_interface_captures: Iterable[Mapping[str, Any]],
    receipt_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one deterministic post-merge observability record.

    No input is mutated and no model-facing behavior is changed.
    """
    telemetry_sources = [
        dict(row) for row in model_call_telemetry if isinstance(row, Mapping)
    ]
    telemetry_rows = _provider_rows(telemetry_sources)
    telemetry_kind_counts: dict[str, int] = {}
    for row in telemetry_sources:
        kind = str(row.get("event_kind") or "legacy_unspecified").strip() or "legacy_unspecified"
        telemetry_kind_counts[kind] = telemetry_kind_counts.get(kind, 0) + 1
    interface_rows = _interface_rows(model_interface_captures)
    receipt_rows = [dict(row) for row in receipt_records if isinstance(row, Mapping)]

    input_summary = _reported_sum(telemetry_rows, "input_tokens")
    cached_summary = _reported_sum(telemetry_rows, "cached_input_tokens")
    cache_write_summary = _reported_sum(telemetry_rows, "cache_write_tokens")
    uncached_summary = _reported_sum(telemetry_rows, "uncached_input_tokens")
    output_summary = _reported_sum(telemetry_rows, "output_tokens")
    total_summary = _reported_sum(telemetry_rows, "total_tokens")
    reasoning_summary = _reported_sum(telemetry_rows, "fresh_reasoning_tokens")
    cost_summary = _reported_sum(telemetry_rows, "cost_usd")
    elapsed_summary = _reported_sum(telemetry_rows, "elapsed_s")

    context_totals = {
        "interface_call_count": len(interface_rows),
        "aggregate_token_estimate_v1": sum(
            int((row.get("aggregate") or {}).get("token_estimate_v1") or 0)
            for row in interface_rows
        ),
        "stable_prefix_token_estimate_v1": sum(
            int((row.get("stable_prefix") or {}).get("token_estimate_v1") or 0)
            for row in interface_rows
        ),
        "dynamic_or_volatile_token_estimate_v1": sum(
            int((row.get("dynamic_or_volatile") or {}).get("token_estimate_v1") or 0)
            for row in interface_rows
        ),
        "task_static_tokens": None,
        "task_static_tokens_status": "not_separately_tagged_in_current_interface_capture",
        "stable_authority_tokens": None,
        "stable_authority_tokens_status": "stable_prefix_is_measured_but_authority_vs_task_static_is_not_yet_separately_tagged",
    }

    receipt_accounting = _receipt_accounting(receipt_rows)
    positive_progress = int(receipt_accounting["mechanically_positive_progress_event_count"])
    total_tokens_all = total_summary.get("sum_if_all_reported")
    tokens_per_progress = None
    if isinstance(total_tokens_all, (int, float)) and positive_progress > 0:
        tokens_per_progress = round(float(total_tokens_all) / positive_progress, 3)

    compaction_events = sum(int(bool(row.get("compaction_observed"))) for row in telemetry_rows)
    return {
        "schema_version": X0_OBSERVABILITY_SCHEMA_VERSION,
        "status": "OBSERVED_NO_MODEL_FACING_BEHAVIOR_CHANGE",
        "measurement_laws": {
            "missing_provider_usage_is_unmeasured_not_zero": True,
            "historical_reasoning_tokens_are_not_inferred": True,
            "monetary_cost_is_not_inferred_from_tokens": True,
            "retrieval_regret_requires_a_causal_omission_treatment": True,
            "compaction_regret_requires_a_real_compaction_event_and_post_event_reconstruction_evidence": True,
            "token_estimate_v1_is_coarse_utf8_bytes_divided_by_four": True,
        },
        "context": {
            "totals": context_totals,
            "calls": interface_rows,
        },
        "provider": {
            "telemetry_event_count": len(telemetry_sources),
            "telemetry_event_kind_counts": dict(sorted(telemetry_kind_counts.items())),
            "attempt_count": len(telemetry_rows),
            "attempt_population": (
                "event_kind=provider_attempt; legacy rows without event_kind are retained as attempts"
            ),
            "completed_attempt_count": sum(row.get("status") == "completed" for row in telemetry_rows),
            "failed_attempt_count": sum(row.get("status") == "failed" for row in telemetry_rows),
            "input_tokens": input_summary,
            "cached_input_tokens": cached_summary,
            "cache_write_tokens": cache_write_summary,
            "uncached_input_tokens": uncached_summary,
            "output_tokens": output_summary,
            "total_tokens": total_summary,
            "fresh_reasoning_tokens": reasoning_summary,
            "historical_reasoning_tokens": {
                "value": None,
                "status": "not_separately_reported_by_provider",
            },
            "latency_seconds": elapsed_summary,
            "cost_usd": cost_summary,
            "compaction_event_count": compaction_events,
            "compaction_regret": None,
            "compaction_regret_status": (
                "no_compaction_event_observed" if compaction_events == 0
                else "requires_post_compaction_reconstruction_attribution"
            ),
            "attempts": telemetry_rows,
        },
        "receipts": receipt_accounting,
        "latest_observation": _latest_observation_accounting(receipt_rows, interface_rows),
        "efficiency": {
            "reported_total_tokens_per_mechanically_positive_progress_event": tokens_per_progress,
            "goal_directed_token_density": None,
            "goal_directed_token_density_status": (
                "progress_denominator_measured_but_causal_token_numerator_not_directly_observable"
            ),
            "cost_per_verified_progress_event_usd": None,
            "cost_per_verified_progress_event_status": (
                "unmeasured" if cost_summary.get("status") == "unmeasured"
                else "requires_positive_progress_and_complete_cost_attribution"
            ),
        },
    }


__all__ = [
    "X0_OBSERVABILITY_SCHEMA_VERSION",
    "build_x0_observability",
]

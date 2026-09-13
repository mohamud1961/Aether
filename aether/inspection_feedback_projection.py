"""Solver-safe factual projection of registered independent inspection results.

The independent review lane may interpret an observation, but Frontier remains the
semantic authority.  This module therefore projects only bounded factual fields
from the *executed inspection result* into Solver-facing feedback.  Reviewer
prose, repair strategy, internal reviewer identity, and execution plumbing are
never copied through this seam.
"""
from __future__ import annotations

import json
from typing import Any, Mapping


MAX_FACT_BYTES = 4096
MAX_TEXT_CHARS = 1400
MAX_ROWS = 6

_INTERNAL_REVIEW_METADATA = (
    ("model_verifier_result", "completion_review_outcome"),
    ("model_verifier", "completion_review"),
    ("verifier_inspection", "completion_observation"),
    ("reviewer_tool", "completion_observation_tool"),
    ("reviewer_capability", "completion_observation_capability"),
    ("run_verifier", "derived_execution"),
)


def _neutralize_metadata_text(value: Any) -> str:
    text = str(value or "")
    lowered = text.lower()
    for source, replacement in _INTERNAL_REVIEW_METADATA:
        if source in lowered:
            # Metadata identifiers are ASCII protocol labels in practice; keep
            # replacement simple and deterministic rather than interpreting task text.
            text = text.replace(source, replacement).replace(source.upper(), replacement)
            lowered = text.lower()
    return text

_NEUTRAL_KIND = {
    "read_file": "file_content_observation",
    "read_cited_receipt": "historical_file_content_observation",
    "read_output": "captured_output_observation",
    "compare_initial_path": "initial_current_comparison",
    "rerun_check": "declared_check_execution",
    "overlay_run_command": "derived_measurement_execution",
    "probe_port": "port_observation",
    "probe_http": "http_observation",
    "probe_process": "process_observation",
    "probe_job": "job_observation",
    "inspect_artifact": "artifact_metadata_observation",
    "perceive_artifact": "artifact_perception_observation",
    "inspect_artifact_history": "artifact_history_observation",
    "inspect_action_receipts": "action_history_observation",
    "inspect_recent_receipts": "runtime_history_observation",
}

# Factual scalar/list fields emitted by the trusted route implementations.  The
# projection deliberately excludes request_id, model-authored verification
# plans/commands, internal receipt IDs, reviewer identity, execution_scope, and
# provenance implementation names.
_COMMON_KEYS = (
    "path", "normalized_path", "handle", "host", "port", "url", "pattern",
    "job_id", "process_id", "process_generation", "service_name",
    "bytes", "content_chars", "content_hash", "sha256", "media_type",
    "offset", "span", "anchor", "returned_chars", "next_offset",
    "more_available", "snapshot_complete", "text_decode_lossless",
    "status", "status_code", "http_status", "open", "exists", "live",
    "running", "ready", "success", "exit_code", "returncode", "timed_out",
    "stdout_bytes", "stderr_bytes", "stdout_bytes_total", "stderr_bytes_total",
    "matching_count", "returned_count", "successful_count", "failed_count",
    "older_available_count", "newer_skipped_count", "omitted_count",
    "changed", "same", "initial_exists", "current_exists", "initial_bytes",
    "current_bytes", "initial_sha256", "current_sha256", "relation_digest",
    "lifecycle_binding_verified", "snapshot_verified", "read_only",
)

_TEXT_KEYS = (
    "excerpt", "stdout", "stderr", "body", "text", "transcription",
    "outcome_detail", "result_summary", "summary",
    "initial_excerpt", "current_excerpt",
)

_ROW_KEYS = (
    "path", "kind", "step", "success", "failure_class", "state_change",
    "bytes", "content_chars", "content_hash", "offset", "span", "anchor",
    "status", "status_code", "open", "exists", "live", "running",
    "exit_code", "returncode", "timed_out", "summary", "summary_bytes",
    "summary_sha256", "summary_truncated", "excerpt",
)


def _bounded_text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "")
    return text[: max(0, int(limit))]


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _safe_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _ROW_KEYS:
        if key not in row or row[key] in (None, "", (), [], {}):
            continue
        if key == "excerpt":
            # Excerpts are task/output content and must remain byte-faithful.
            out[key] = _bounded_text(row[key], 700)
        elif key in {"summary", "kind", "failure_class"}:
            # These are ledger metadata, not task bytes. Neutralize internal
            # independent-review implementation labels before Solver exposure.
            out[key] = _bounded_text(_neutralize_metadata_text(row[key]), 700)
        else:
            out[key] = _safe_scalar(row[key])
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        # Action-history payloads are already allowlisted by verifier_inspector.
        safe_payload: dict[str, Any] = {}
        for key, value in payload.items():
            if value in (None, "", (), [], {}):
                continue
            if isinstance(value, (str, int, float, bool)):
                safe_payload[str(key)] = _bounded_text(value, 500) if isinstance(value, str) else value
            elif isinstance(value, (list, tuple)):
                safe_payload[str(key)] = [_safe_scalar(item) for item in list(value)[:8]]
        if safe_payload:
            out["payload"] = safe_payload
    return out


def _truncate_to_budget(payload: dict[str, Any]) -> dict[str, Any]:
    """Fail smaller rather than leaking an unbounded result into Solver context."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    if len(encoded) <= MAX_FACT_BYTES:
        return payload
    compact = {
        key: value
        for key, value in payload.items()
        if key not in {"rows", "matches", "stdout", "stderr", "body", "text", "transcription", "excerpt"}
    }
    compact["observation_projection_truncated"] = True
    for key in ("excerpt", "stdout", "stderr", "body", "text", "transcription"):
        if key in payload:
            compact[key] = _bounded_text(payload[key], 500)
            break
    encoded = json.dumps(compact, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    if len(encoded) <= MAX_FACT_BYTES:
        return compact
    return {
        "observation_kind": payload.get("observation_kind", "bounded_observation"),
        "observation_projection_truncated": True,
    }


def solver_facing_inspection_observation(
    result: Mapping[str, Any],
    *,
    task_state_generation: int,
    admissibility: str,
    observation_type: str,
    target_identity: str,
    observation_valid: bool,
    actual_evidence_class: str = "",
) -> dict[str, Any]:
    """Return a bounded factual observation with no reviewer interpretation.

    The caller supplies registry-derived authority fields; content comes only
    from the executed route result. Invalid or exploratory observations remain
    auditable internally but are not projected as factual support to Frontier.
    """
    kind = str(result.get("kind") or "").strip()
    if not observation_valid or admissibility not in {"direct_admissible", "verdict_eligible"}:
        return {}
    if kind not in _NEUTRAL_KIND:
        return {}

    out: dict[str, Any] = {
        "observation_kind": _NEUTRAL_KIND[kind],
        "task_state_generation": int(task_state_generation),
        "observation_type": str(observation_type or ""),
        "target": str(target_identity or "target:opaque"),
        "observation_valid": True,
        "admissibility": str(admissibility),
    }
    if actual_evidence_class:
        out["evidence_class"] = str(actual_evidence_class)

    for key in _COMMON_KEYS:
        value = result.get(key)
        if value in (None, "", (), [], {}):
            continue
        if isinstance(value, (list, tuple)):
            out[key] = [_safe_scalar(item) for item in list(value)[:12]]
        elif isinstance(value, Mapping):
            continue
        else:
            out[key] = _safe_scalar(value)

    for key in _TEXT_KEYS:
        value = result.get(key)
        if value not in (None, ""):
            out[key] = _bounded_text(value)

    for key in ("rows", "matches"):
        rows = result.get(key)
        if isinstance(rows, list):
            safe_rows = [_safe_row(row) for row in rows[:MAX_ROWS] if isinstance(row, Mapping)]
            safe_rows = [row for row in safe_rows if row]
            if safe_rows:
                out[key] = safe_rows

    # Perception is explicitly model-derived, not ground truth. Preserve that
    # epistemic fact without surfacing reviewer identity.
    if kind == "perceive_artifact":
        out["perception_authority"] = "model_transcription_not_ground_truth"
    if kind in {"overlay_run_command", "rerun_check"}:
        out["measurement_authority"] = "independently_executed_measurement_not_task_semantics"

    return _truncate_to_budget(out)

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .hashes import stable_hash


NULL_EVENT_HASH = "0" * 64

# V1.1 minimal telemetry schema (section 15): fail closed when any required field is absent.
MIN_TELEMETRY_FIELDS = (
    "event_type",
    "step_id",
    "timestamp",
    "cwd",
    "tool_name",
    "tool_args",
    "exit_code",
    "files_read",
    "files_written",
    "artifact_refs",
    "truncation",
    "verifier_run",
    "verifier_result",
    "triggers_fired",
    "trigger_explanation",
    "workspace_fingerprint_hash",
    "dirty_since_last_verify",
    "context_pack_hash",
    "manifest_hash",
    "completion_signals",
    "termination_reason",
    "checkpoint_ref",
    "retry_after_fix",
    "recovery_candidate",
    "event_id",
    "prev_event_hash",
)

# Section 15 canonical event types.
ALLOWED_EVENT_TYPES = {
    "run_START",
    "INTENT_CONTRACT_DEFINED",
    "INTENT_COMPLETENESS_CHECK",
    "ORIENT_UNDERSTANDING_PRODUCED",
    "ORIENT_FALLBACK_USED",
    "CONTRACT_DEFINED",
    "PLAN_DEFINED",
    "PLAN_STATUS_CHANGED",
    "PLAN_UPDATE",
    "PLAN_STEP_STATUS",
    "CONTEXTPACK_COMPILED",
    "MODEL_CALL",
    "BUDGET_CHECK",
    "CONTEXT_SLICE_BOUND",
    "MODEL_ROUTE_DECISION",
    "TOOL_CALL",
    "TOOL_DENY",
    "RETRY_DENIED",
    "POLICY_VIOLATION",
    "PHASE_TRANSITION",
    "PHASE_TRANSITION_DENIED",
    "EXPLORATION_FLOOR_EVAL",
    "VERIFIER_run",
    "VERIFIER_RESULT",
    "RISK_EVAL",
    "APPROVAL_GRANTED",
    "GOVERNANCE_DECISION",
    "MODEL_REQUEST",
    "MODEL_RESPONSE",
    "MODEL_ERROR",
    "REPLAY_GATE",
    "APPROVAL_DENIED",
    "VERIFIER_PLAN",
    "PERMISSION_REQUEST",
    "PROCEED_INJECTION",
    "LOOP_BREAKER_TRIGGER",
    "REPAIR_ATTEMPT",
    "REPAIR_TERMINATION",
    "STEP_COMMIT",
    "REANCHOR_START",
    "REANCHOR_END",
    "REANCHOR_REPEAT_DETECTED",
    "COMPLETION_EVIDENCE_BUNDLE_CREATED",
    "ROLLBACK_LIMITATION",
    "LOG_INTEGRITY_CHECK",
    "LOG_ANCHOR_WRITTEN",
    "LOG_ANCHOR_VERIFY",
    "REDACTION_APPLIED",
    "DLP_SCAN_RESULT",
    "EVIDENCE_READ",
    "REPLAY_START",
    "DIVERGENCE_DETECTED",
    "REPLAY_END",
    "METRIC_SUMMARY",
    "run_END",
}

# Temporary one-to-one aliases for migration. Unknown raw types are rejected.
EVENT_TYPE_ALIASES: Dict[str, str] = {
    "run_start": "run_START",
    "run_end": "run_END",
    "intent_contract_defined": "INTENT_CONTRACT_DEFINED",
    "intent_completeness_check": "INTENT_COMPLETENESS_CHECK",
    "orient_understanding_produced": "ORIENT_UNDERSTANDING_PRODUCED",
    "orient_fallback_used": "ORIENT_FALLBACK_USED",
    "contract_defined": "CONTRACT_DEFINED",
    "plan_snapshot": "PLAN_DEFINED",
    "plan_defined": "PLAN_DEFINED",
    "plan_status_changed": "PLAN_STATUS_CHANGED",
    "plan_update": "PLAN_UPDATE",
    "plan_step_status": "PLAN_STEP_STATUS",
    "context_compiler": "CONTEXTPACK_COMPILED",
    "model_call": "MODEL_CALL",
    "context_slice_bound": "CONTEXT_SLICE_BOUND",
    "contextslice_binding": "CONTEXT_SLICE_BOUND",
    "CONTEXTSLICE_BINDING": "CONTEXT_SLICE_BOUND",
    "model_route_decision": "MODEL_ROUTE_DECISION",
    "tool_call": "TOOL_CALL",
    "tool_call_blocked": "TOOL_DENY",
    "tool_deny": "TOOL_DENY",
    "retry_denied": "RETRY_DENIED",
    "policy_violation": "POLICY_VIOLATION",
    "phase_transition_denied": "PHASE_TRANSITION_DENIED",
    "exploration_floor_eval": "EXPLORATION_FLOOR_EVAL",
    "verifier_run": "VERIFIER_run",
    "verifier_result": "VERIFIER_RESULT",
    "risk_eval": "RISK_EVAL",
    "approval_granted": "APPROVAL_GRANTED",
    "step_commit": "STEP_COMMIT",
    "reanchor_start": "REANCHOR_START",
    "reanchor_end": "REANCHOR_END",
    "reanchor_repeat_detected": "REANCHOR_REPEAT_DETECTED",
    "completion_evidence_bundle_created": "COMPLETION_EVIDENCE_BUNDLE_CREATED",
    "rollback_limitation": "ROLLBACK_LIMITATION",
    "hash_chain_verification": "LOG_INTEGRITY_CHECK",
    "log_integrity_check": "LOG_INTEGRITY_CHECK",
    "log_anchor_written": "LOG_ANCHOR_WRITTEN",
    "log_anchor_verify": "LOG_ANCHOR_VERIFY",
    "redaction_applied": "REDACTION_APPLIED",
    "dlp_scan": "DLP_SCAN_RESULT",
    "dlp_scan_result": "DLP_SCAN_RESULT",
    "evidence_read": "EVIDENCE_READ",
    "replay_start": "REPLAY_START",
    "divergence_detected": "DIVERGENCE_DETECTED",
    "replay_end": "REPLAY_END",
    "metric_summary": "METRIC_SUMMARY",
    # --- Phase 3 unmapped types (red team review 2026-02-17) ---
    "governance_decision": "GOVERNANCE_DECISION",
    "model_request": "MODEL_REQUEST",
    "model_response": "MODEL_RESPONSE",
    "model_error": "MODEL_ERROR",
    "state_transition": "PHASE_TRANSITION",
    "replay_gate": "REPLAY_GATE",
    "approval_denied": "APPROVAL_DENIED",
    "verifier_plan": "VERIFIER_PLAN",
    "permission_request": "PERMISSION_REQUEST",
    "proceed_injection": "PROCEED_INJECTION",
    "loop_breaker_trigger": "LOOP_BREAKER_TRIGGER",
    "repair_attempt": "REPAIR_ATTEMPT",
    "repair_termination": "REPAIR_TERMINATION",
}

REQUIRED_TrunCATION_FIELDS = ("truncated", "size_bytes", "captured_bytes", "unknown")
TOOL_LIKE_EVENT_TYPES = {"TOOL_CALL", "TOOL_DENY", "VERIFIER_RESULT"}
STEP_COMMIT_EVENT_TYPE = "STEP_COMMIT"
STEP_COMMIT_STATUSES = {"valid", "missing_components"}


def canonicalize_event_type(raw_event_type: Any) -> str:
    if not isinstance(raw_event_type, str) or not raw_event_type.strip():
        raise ValueError(f"Invalid event_type: {raw_event_type!r}")

    candidate = raw_event_type.strip()
    if candidate in ALLOWED_EVENT_TYPES:
        return candidate

    upper = candidate.upper()
    if upper in ALLOWED_EVENT_TYPES:
        return upper

    if candidate in EVENT_TYPE_ALIASES:
        return EVENT_TYPE_ALIASES[candidate]
    if upper in EVENT_TYPE_ALIASES:
        return EVENT_TYPE_ALIASES[upper]

    raise ValueError(f"Unknown event_type: {raw_event_type}")


@dataclass(frozen=True)
class Event:
    event_id: str
    prev_event_hash: str
    event_type: str
    step_id: int
    timestamp: str
    cwd: str
    payload: Mapping[str, Any]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Event":
        payload = dict(raw)
        event_type = canonicalize_event_type(payload.get("event_type"))

        step_id_raw = payload.get("step_id")
        step_id = int(step_id_raw) if isinstance(step_id_raw, int) else -1

        return cls(
            event_id=str(payload.get("event_id", "")),
            prev_event_hash=str(payload.get("prev_event_hash", "")),
            event_type=event_type,
            step_id=step_id,
            timestamp=str(payload.get("timestamp", "")),
            cwd=str(payload.get("cwd", "")),
            payload=payload,
        )


def _resolve_events_path(root: Path) -> Path:
    candidates = (root / "events.jsonl", root / "event_log.jsonl")
    for path in candidates:
        if path.exists():
            return path
    names = ", ".join(path.name for path in candidates)
    raise FileNotFoundError(f"Missing required telemetry file (expected one of: {names}) in {root}")


def load_events(artifact_dir: str | Path) -> List[Event]:
    root = Path(artifact_dir)
    events_path = _resolve_events_path(root)
    source_name = events_path.name

    events: List[Event] = []
    for line_no, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        raw = json.loads(stripped)
        if not isinstance(raw, dict):
            raise ValueError(f"{source_name} line {line_no} is not a JSON object")
        try:
            events.append(Event.from_dict(raw))
        except ValueError as exc:
            raise ValueError(f"{source_name} line {line_no}: {exc}") from exc
    return events


def validate_required_fields(
    events: Iterable[Event],
    required_event_types: Iterable[str],
) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    event_list = list(events)

    if not event_list:
        violations.append(
            {
                "code": "missing_events",
                "message": "No telemetry events were found",
                "step_id": None,
                "event_id": None,
            }
        )
        return violations

    seen_types = {event.event_type for event in event_list}
    normalized_required: List[str] = []
    for raw_required in sorted(set(required_event_types)):
        try:
            normalized_required.append(canonicalize_event_type(raw_required))
        except ValueError:
            violations.append(
                {
                    "code": "invalid_required_event_type",
                    "message": f"Required event type is not canonical/allowed: {raw_required}",
                    "required_event_type": raw_required,
                    "step_id": None,
                    "event_id": None,
                }
            )

    for event_type in sorted(set(normalized_required)):
        if event_type not in seen_types:
            violations.append(
                {
                    "code": "missing_required_event_type",
                    "message": f"Required event type is missing: {event_type}",
                    "required_event_type": event_type,
                    "step_id": None,
                    "event_id": None,
                }
            )

    for event in event_list:
        payload = event.payload

        raw_event_type = payload.get("event_type")
        event_type = None
        try:
            event_type = canonicalize_event_type(raw_event_type)
        except ValueError:
            pass
        if event_type is None:
            violations.append(
                {
                    "code": "unknown_event_type",
                    "message": f"Unknown event type: {raw_event_type}",
                    "event_type": raw_event_type,
                    "step_id": event.step_id,
                    "event_id": event.event_id,
                }
            )

        for field in MIN_TELEMETRY_FIELDS:
            if field not in payload:
                violations.append(
                    {
                        "code": "missing_required_field",
                        "message": f"Event missing required field: {field}",
                        "field": field,
                        "step_id": event.step_id,
                        "event_id": event.event_id,
                    }
                )

        if not isinstance(payload.get("step_id"), int):
            violations.append(
                {
                    "code": "invalid_step_id",
                    "message": "step_id must be an integer",
                    "step_id": payload.get("step_id"),
                    "event_id": event.event_id,
                }
            )

        artifact_refs = payload.get("artifact_refs")
        if artifact_refs is not None and not isinstance(artifact_refs, list):
            violations.append(
                {
                    "code": "invalid_artifact_refs",
                    "message": "artifact_refs must be a list",
                    "step_id": event.step_id,
                    "event_id": event.event_id,
                }
            )

        if event.event_type in TOOL_LIKE_EVENT_TYPES:
            truncation = payload.get("truncation")
            if not isinstance(truncation, dict):
                violations.append(
                    {
                        "code": "missing_truncation",
                        "message": "Tool-like events require truncation metadata",
                        "step_id": event.step_id,
                        "event_id": event.event_id,
                    }
                )
            else:
                for stream in ("stdout", "stderr"):
                    stream_meta = truncation.get(stream)
                    if not isinstance(stream_meta, dict):
                        violations.append(
                            {
                                "code": "missing_truncation_stream",
                                "message": f"Missing truncation metadata for {stream}",
                                "step_id": event.step_id,
                                "event_id": event.event_id,
                            }
                        )
                        continue
                    for key in REQUIRED_TrunCATION_FIELDS:
                        if key not in stream_meta:
                            violations.append(
                                {
                                    "code": "missing_truncation_field",
                                    "message": f"Missing truncation field {key} for {stream}",
                                    "step_id": event.step_id,
                                    "event_id": event.event_id,
                                    "field": key,
                                    "stream": stream,
                                }
                            )

    violations.sort(key=lambda item: (item.get("step_id") or -1, item.get("code", ""), item.get("message", "")))
    return violations


def validate_hash_chain(events: Iterable[Event]) -> tuple[bool, Optional[str]]:
    previous_hash = NULL_EVENT_HASH

    for event in events:
        payload = dict(event.payload)
        event_id = payload.get("event_id")
        prev_event_hash = payload.get("prev_event_hash")

        if not isinstance(event_id, str) or len(event_id) != 64:
            return False, event.event_id or f"step:{event.step_id}"
        if not isinstance(prev_event_hash, str) or len(prev_event_hash) != 64:
            return False, event.event_id or f"step:{event.step_id}"

        if prev_event_hash != previous_hash:
            return False, event.event_id

        recompute_payload = {
            key: value
            for key, value in payload.items()
            if key not in {"event_id", "prev_event_hash"}
        }
        expected_event_id = stable_hash(recompute_payload)
        if event_id != expected_event_id:
            return False, event.event_id

        previous_hash = event_id

    return True, None


def validate_step_atomicity(
    events: Iterable[Event],
    *,
    require_step_commit: bool = False,
) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    event_list = list(events)

    by_step: Dict[int, List[Mapping[str, Any]]] = {}
    step_commits: Dict[int, List[Mapping[str, Any]]] = {}

    for event in event_list:
        payload = event.payload
        step_id = payload.get("step_id")
        if not isinstance(step_id, int):
            continue

        by_step.setdefault(step_id, []).append(payload)
        if event.event_type == STEP_COMMIT_EVENT_TYPE:
            step_commits.setdefault(step_id, []).append(payload)

    if require_step_commit and not step_commits:
        violations.append(
            {
                "code": "missing_step_commit",
                "message": "No STEP_COMMIT events were found",
                "step_id": None,
            }
        )

    for step_id, commits in sorted(step_commits.items(), key=lambda item: item[0]):
        if len(commits) > 1:
            violations.append(
                {
                    "code": "duplicate_step_commit",
                    "message": "Multiple STEP_COMMIT events exist for the same step_id",
                    "step_id": step_id,
                    "count": len(commits),
                }
            )

        commit = commits[0]
        status = commit.get("commit_status", commit.get("status"))
        if status is None and isinstance(commit.get("valid"), bool):
            status = "valid" if commit.get("valid") else "missing_components"

        if not isinstance(status, str) or status not in STEP_COMMIT_STATUSES:
            violations.append(
                {
                    "code": "invalid_step_commit_status",
                    "message": "STEP_COMMIT status must be 'valid' or 'missing_components'",
                    "step_id": step_id,
                    "status": status,
                }
            )
            continue

        missing_components = commit.get("missing_components")
        if missing_components is None:
            missing_components = []
        if not isinstance(missing_components, list):
            violations.append(
                {
                    "code": "invalid_missing_components",
                    "message": "STEP_COMMIT missing_components must be a list",
                    "step_id": step_id,
                }
            )
            continue

        if status == "valid" and missing_components:
            violations.append(
                {
                    "code": "valid_has_missing_components",
                    "message": "STEP_COMMIT status 'valid' cannot include missing components",
                    "step_id": step_id,
                    "missing_components": missing_components,
                }
            )
        if status == "missing_components" and not missing_components:
            violations.append(
                {
                    "code": "missing_components_empty",
                    "message": "STEP_COMMIT status 'missing_components' requires at least one component",
                    "step_id": step_id,
                }
            )

        if step_id not in by_step:
            violations.append(
                {
                    "code": "orphan_step_commit",
                    "message": "STEP_COMMIT references a step that has no recorded events",
                    "step_id": step_id,
                }
            )

    violations.sort(key=lambda item: (item.get("step_id") or -1, item.get("code", "")))
    return violations


def index_by_step(events: Iterable[Event]) -> Dict[int, List[Event]]:
    index: Dict[int, List[Event]] = {}
    for event in events:
        index.setdefault(event.step_id, []).append(event)
    return dict(sorted(index.items(), key=lambda item: item[0]))


def filter_events(
    events: Iterable[Event],
    type: Optional[str] = None,
    step_id: Optional[int] = None,
) -> List[Event]:
    expected_type = canonicalize_event_type(type) if type is not None else None

    filtered: List[Event] = []
    for event in events:
        if expected_type is not None and event.event_type != expected_type:
            continue
        if step_id is not None and event.step_id != step_id:
            continue
        filtered.append(event)
    return filtered

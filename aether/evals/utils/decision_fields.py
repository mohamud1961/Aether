from __future__ import annotations

from typing import Dict, List, Mapping, Sequence


DECISION_FIELDS_VERSION = "v1.1.0"

# Explicit replay decision fields that are allowed to drive CT-03 divergence checks.
DECISION_EVENT_FIELDS: Dict[str, List[str]] = {
    "MODEL_ROUTE_DECISION": [
        "from_model_id",
        "to_model_id",
        "signals_hash",
        "reason_codes",
    ],
    "TOOL_DENY": [
        "tool_name",
        "deny_reason_code",
        "attempted_action_fingerprint",
    ],
    "VERIFIER_run": [
        "verifier_id",
        "params_hash",
        "verifier_stage",
    ],
}

# Required decision events for replay divergence validation. Missing any is fail-closed.
REQUIRED_DECISION_EVENT_TYPES: Sequence[str] = tuple(sorted(DECISION_EVENT_FIELDS.keys()))


def required_decision_events_present(events_by_type: Mapping[str, Sequence[Mapping[str, object]]]) -> List[str]:
    missing: List[str] = []
    for event_type in REQUIRED_DECISION_EVENT_TYPES:
        events = events_by_type.get(event_type, [])
        if not events:
            missing.append(event_type)
    return missing


def required_decision_fields_missing(event_type: str, event: Mapping[str, object]) -> List[str]:
    required = DECISION_EVENT_FIELDS.get(event_type, [])
    return [field for field in required if event.get(field) in (None, "")]

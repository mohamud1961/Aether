from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


def _payload(event: Any) -> Mapping[str, Any]:
    if hasattr(event, "payload"):
        payload = getattr(event, "payload")
        if isinstance(payload, Mapping):
            return payload
    if isinstance(event, Mapping):
        return event
    return {}


def compare_decisions(
    recorded_events: Iterable[Any],
    replay_events: Iterable[Any],
    decision_fields_spec: Mapping[str, Any] | Sequence[str],
) -> List[Dict[str, Any]]:
    if isinstance(decision_fields_spec, Mapping):
        event_type = decision_fields_spec.get("event_type")
        replay_event_type = decision_fields_spec.get("replay_event_type", event_type)
        pair_by = str(decision_fields_spec.get("pair_by", "step_id"))
        fields = list(decision_fields_spec.get("fields", []))
    else:
        event_type = None
        replay_event_type = None
        pair_by = "step_id"
        fields = list(decision_fields_spec)

    if not fields:
        fields = ["decision", "reason_code", "allow", "governance", "tool_name"]

    def select(events: Iterable[Any], required_type: Optional[str]) -> Dict[Any, Mapping[str, Any]]:
        selected: Dict[Any, Mapping[str, Any]] = {}
        for event in events:
            payload = _payload(event)
            candidate_type = payload.get("event_type")
            if required_type is not None:
                if candidate_type != required_type:
                    continue
            else:
                if "decision" not in str(candidate_type):
                    continue
            pair_key = payload.get(pair_by)
            if pair_key is None:
                continue
            selected[pair_key] = payload
        return selected

    recorded_idx = select(recorded_events, str(event_type) if event_type is not None else None)
    replay_idx = select(replay_events, str(replay_event_type) if replay_event_type is not None else None)

    decision_keys = sorted(set(recorded_idx) | set(replay_idx), key=lambda item: str(item))
    compared_total = len(decision_keys)

    divergences: List[Dict[str, Any]] = []
    for key in decision_keys:
        recorded = recorded_idx.get(key)
        replay = replay_idx.get(key)

        if recorded is None or replay is None:
            divergences.append(
                {
                    "decision_key": key,
                    "event_type": event_type,
                    "field": "*",
                    "recorded": recorded,
                    "replay": replay,
                    "reason": "missing_decision",
                    "compared_total": compared_total,
                }
            )
            continue

        for field in fields:
            recorded_value = recorded.get(field)
            replay_value = replay.get(field)
            if recorded_value != replay_value:
                divergences.append(
                    {
                        "decision_key": key,
                        "event_type": event_type,
                        "field": field,
                        "recorded": recorded_value,
                        "replay": replay_value,
                        "reason": "value_mismatch",
                        "compared_total": compared_total,
                    }
                )

    return divergences


def compute_divergence_rate(divergences: Sequence[Mapping[str, Any]]) -> float:
    if not divergences:
        return 0.0

    unique_keys = {item.get("decision_key") for item in divergences}
    compared_total = 0
    for item in divergences:
        candidate = item.get("compared_total")
        if isinstance(candidate, int) and candidate > compared_total:
            compared_total = candidate

    if compared_total <= 0:
        compared_total = len(unique_keys)

    return float(len(unique_keys)) / float(compared_total)

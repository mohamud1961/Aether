from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence


@dataclass(frozen=True)
class AssertionFailure:
    fail_signature: str
    message: str
    details: dict[str, Any]


def _payload(event: Any) -> Mapping[str, Any]:
    if hasattr(event, "payload"):
        payload = getattr(event, "payload")
        if isinstance(payload, Mapping):
            return payload
    if isinstance(event, Mapping):
        return event
    return {}


def _failure(signature: str, message: str, **details: Any) -> AssertionFailure:
    return AssertionFailure(
        fail_signature=signature,
        message=message,
        details=details,
    )


def require_event(
    events: Iterable[Any],
    type: str,
    predicate: Optional[Callable[[Mapping[str, Any]], bool]] = None,
) -> Optional[AssertionFailure]:
    matches = [_payload(event) for event in events if _payload(event).get("event_type") == type]
    if not matches:
        return _failure(
            signature=f"missing_event:{type}",
            message=f"Required event type missing: {type}",
            event_type=type,
        )

    if predicate is not None and not any(predicate(match) for match in matches):
        return _failure(
            signature=f"predicate_failed:{type}",
            message=f"No {type} event satisfied predicate",
            event_type=type,
        )

    return None


def require_one_to_one(
    events: Iterable[Any],
    left_type: str,
    right_type: str,
    key: str = "step_id",
) -> Optional[AssertionFailure]:
    left_events = [_payload(event) for event in events if _payload(event).get("event_type") == left_type]
    right_events = [_payload(event) for event in events if _payload(event).get("event_type") == right_type]

    if not left_events or not right_events:
        return _failure(
            signature=f"one_to_one_missing:{left_type}:{right_type}",
            message="One side of one-to-one mapping is missing",
            left_count=len(left_events),
            right_count=len(right_events),
            key=key,
        )

    left_keys = [event.get(key) for event in left_events]
    right_keys = [event.get(key) for event in right_events]

    if any(item is None for item in left_keys + right_keys):
        return _failure(
            signature=f"one_to_one_missing_key:{left_type}:{right_type}",
            message=f"One or more events missing mapping key: {key}",
            key=key,
        )

    for mapped_key in sorted(set(left_keys + right_keys), key=lambda item: str(item)):
        if left_keys.count(mapped_key) != 1 or right_keys.count(mapped_key) != 1:
            return _failure(
                signature=f"one_to_one_violation:{left_type}:{right_type}",
                message="One-to-one relationship violated",
                mapped_key=mapped_key,
                left_count=left_keys.count(mapped_key),
                right_count=right_keys.count(mapped_key),
                key=key,
            )

    return None


def require_no_success_if(condition: bool) -> Optional[AssertionFailure]:
    if condition:
        return _failure(
            signature="forbidden_success_condition",
            message="Success condition is forbidden under current evidence",
        )
    return None


def require_fields(payload: Mapping[str, Any], fields: Sequence[str]) -> Optional[AssertionFailure]:
    missing = [field for field in fields if field not in payload]
    if missing:
        return _failure(
            signature="missing_fields",
            message="Payload is missing required fields",
            missing_fields=missing,
        )
    return None


def require_hash_exists(artifact_store: Any, content_hash: str) -> Optional[AssertionFailure]:
    if not isinstance(content_hash, str) or not content_hash:
        return _failure(
            signature="invalid_hash_ref",
            message="Hash reference must be a non-empty string",
            content_hash=content_hash,
        )

    exists = bool(getattr(artifact_store, "exists")(content_hash))
    if not exists:
        return _failure(
            signature="missing_hash",
            message="Referenced CAS hash is missing",
            content_hash=content_hash,
        )

    return None


def require_enum(enum_registry: Any, enum_name: str, value: Any) -> Optional[AssertionFailure]:
    try:
        enum_registry.require(enum_name, value)
    except AssertionError as exc:
        violation = exc.args[0] if exc.args else None
        reason = getattr(violation, "reason", "enum_violation")
        known_values = getattr(violation, "known_values", [])
        return _failure(
            signature=f"enum_violation:{reason}",
            message=f"Enum validation failed for {enum_name}",
            enum_name=enum_name,
            value=value,
            reason=reason,
            known_values=known_values,
        )
    return None

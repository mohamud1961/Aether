from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .hashing import hash_canonical_json

NULL_EVENT_HASH = "0" * 64


def compute_event_id(event: Dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in event.items()
        if key not in ("event_id", "prev_event_hash")
    }
    return hash_canonical_json(payload)


def verify_event_chain(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    event_list = list(events)
    previous_hash = NULL_EVENT_HASH
    previous_step = None

    for index, event in enumerate(event_list):
        if "event_id" not in event:
            return _report(False, "missing_event_id", index)
        if "prev_event_hash" not in event:
            return _report(False, "missing_prev_event_hash", index)

        if event["prev_event_hash"] != previous_hash:
            return _report(False, "prev_hash_mismatch", index)

        expected_event_id = compute_event_id(event)
        if event["event_id"] != expected_event_id:
            return _report(False, "event_id_mismatch", index)

        step_id = event.get("step_id")
        if previous_step is not None and step_id is not None and step_id <= previous_step:
            return _report(False, "non_monotonic_step_id", index)

        previous_hash = event["event_id"]
        if step_id is not None:
            previous_step = step_id

    return _report(True, "ok", None, checked=len(event_list))


def _report(ok: bool, reason_code: str, failure_index: int | None, checked: int | None = None) -> Dict[str, Any]:
    report = {
        "ok": ok,
        "reason_code": reason_code,
        "failure_index": failure_index,
    }
    if checked is not None:
        report["checked_event_count"] = checked
    return report

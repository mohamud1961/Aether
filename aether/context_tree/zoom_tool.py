"""Exact binary-tree zoom tool [OptChat §7.1]."""
from __future__ import annotations

from typing import Any


def zoom(tree: Any, event_id: int, span: int) -> str:
    total = int(tree.event_count)
    valid = (
        isinstance(event_id, int) and not isinstance(event_id, bool)
        and isinstance(span, int) and not isinstance(span, bool)
        and span >= 1 and span & (span - 1) == 0
        and event_id >= 0 and event_id % span == 0
        and event_id + span <= total
    )
    if not valid:
        return f"No line {event_id}+{span}."
    if span == 1:
        event = tree.get_event(event_id)
        return f"{event_id}+0|{event['kind']}: {event['text']}"
    level = span.bit_length() - 1
    parent = tree.get_node(level, event_id // span)
    if parent is None:
        return f"No line {event_id}+{span}."
    child_span = span // 2
    rows = []
    for child_index in (event_id // child_span, event_id // child_span + 1):
        child = tree.get_node(level - 1, child_index)
        if child is None:
            return f"No line {event_id}+{span}."
        child_start = child_index * child_span
        rows.append(f"{child_start}+{child_span}|{child.text.replace(chr(10), ' ')}")
    return "\n".join(rows)

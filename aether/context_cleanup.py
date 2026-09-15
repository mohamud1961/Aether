"""Mechanical Solver-request accounting and exact-duplicate cleanup only."""
from __future__ import annotations
import hashlib
from typing import Any, Mapping, Sequence

CONTEXT_CLEANUP_OFF = "off"
CONTEXT_CLEANUP_CONSERVATIVE_V1 = "conservative_v1"
CONTEXT_CLEANUP_MODES = frozenset({CONTEXT_CLEANUP_OFF, CONTEXT_CLEANUP_CONSERVATIVE_V1})
_PROTECTED_SECTIONS = frozenset({"raw_user_task", "raw_task_binding", "context_packet"})


def section_name(message: Mapping[str, Any]) -> str:
    first = str(message.get("content", "")).partition("\n")[0]
    return first[1:-1] if first.startswith("[") and first.endswith("]") else "unsectioned"


def _raw(message: Mapping[str, Any]) -> bytes:
    return (str(message.get("role", "")) + "\0" + str(message.get("content", ""))).encode("utf-8")


def measure_messages(messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows, seen, total = [], {}, 0
    for index, message in enumerate(messages):
        raw = _raw(message); total += len(raw)
        duplicate_of = seen.get(raw); seen.setdefault(raw, index)
        rows.append({
            "index": index, "role": str(message.get("role", "")),
            "section": section_name(message), "bytes": len(raw),
            "token_estimate": max(1, (len(raw) + 3) // 4),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "exact_duplicate_of": duplicate_of,
        })
    return {
        "message_count": len(rows), "bytes": total,
        "token_estimate": max(1, (total + 3) // 4) if rows else 0,
        "sections": rows,
        "exact_duplicate_count": sum(row["exact_duplicate_of"] is not None for row in rows),
    }


def apply_context_cleanup(messages: Sequence[Mapping[str, Any]], *, mode: str = CONTEXT_CLEANUP_OFF):
    selected = str(mode or CONTEXT_CLEANUP_OFF).strip().lower()
    if selected not in CONTEXT_CLEANUP_MODES:
        raise ValueError(f"unsupported context cleanup mode: {mode}")
    before = measure_messages(messages); output = []; seen = set(); removed = []
    for index, message in enumerate(messages):
        normalized = {"role": str(message.get("role", "")), "content": str(message.get("content", ""))}
        raw = _raw(normalized); section = section_name(normalized)
        if selected == CONTEXT_CLEANUP_CONSERVATIVE_V1 and raw in seen and section not in _PROTECTED_SECTIONS:
            removed.append({"index": index, "section": section, "sha256": hashlib.sha256(raw).hexdigest(), "reason": "exact_duplicate_same_request"})
            continue
        output.append(normalized); seen.add(raw)
    after = measure_messages(output)
    return output, {
        "schema": "aether.context_cleanup_accounting.v1", "mode": selected,
        "semantic_summarization_used": False, "native_history_changed": False,
        "raw_task_authority_protected": True, "before": before, "after": after,
        "removed": removed, "saved_bytes": before["bytes"] - after["bytes"],
        "saved_token_estimate": before["token_estimate"] - after["token_estimate"],
    }

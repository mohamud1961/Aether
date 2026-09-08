"""Literal, model-directed retrieval over the immutable execution receipt ledger.

This module deliberately does not rank relevance, summarize, embed, infer intent,
or choose context for the Solver. The model supplies a literal query; the kernel
returns mechanically matching receipt addresses newest-first. Exact receipt or
stream bytes remain available through ``read_output``.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from .ledger import Receipt

# Keep query_history's own receipts out of the default corpus so a search cannot
# become self-referential merely because it was repeated.
_EXCLUDED_KINDS = frozenset({"query_history"})
_INDEX_KEYS = (
    "path", "command", "check_id", "target", "service_name", "job_id",
    "session_id", "blocker", "detail", "status", "mode", "media_type",
    "stdout_handle", "stderr_handle", "file_handle",
)
_RESULT_KEYS = (
    *_INDEX_KEYS,
    "exit_code", "bytes", "stdout_bytes", "stderr_bytes", "content_hash",
    "sha256", "after_content_hash", "before_content_hash", "modified_paths",
    "artifact_paths", "timed_out", "completed", "job_succeeded",
)


def _index_text(receipt: Receipt) -> str:
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    parts: list[str] = [
        receipt.receipt_id,
        receipt.kind,
        receipt.summary,
        receipt.failure_class,
    ]
    for key in _INDEX_KEYS:
        value = payload.get(key)
        if value not in (None, "", (), [], {}):
            parts.append(str(value))
    for key in ("modified_paths", "artifact_paths"):
        for value in payload.get(key, ()) or ():
            parts.append(str(value))
    return "\n".join(parts).lower()


def receipt_address(receipt: Receipt) -> dict[str, Any]:
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    row: dict[str, Any] = {
        "receipt_id": receipt.receipt_id,
        "receipt_handle": f"receipt:{receipt.receipt_id}",
        "step": receipt.step,
        "kind": receipt.kind,
        "success": receipt.success,
        "summary": receipt.summary,
        "state_change": receipt.state_change,
        "failure_class": receipt.failure_class,
    }
    for key in _RESULT_KEYS:
        value = payload.get(key)
        if value not in (None, "", (), [], {}):
            row[key] = value
    return row


def query_history(
    receipts: Iterable[Receipt],
    query: str,
    *,
    offset: int = 0,
    limit: int = 8,
) -> dict[str, Any]:
    """Return deterministic literal matches newest-first with exact addresses."""
    needle = str(query).lower()
    start = max(0, int(offset))
    bounded_limit = max(1, min(20, int(limit)))
    indexed = [
        (ordinal, receipt)
        for ordinal, receipt in enumerate(receipts)
        if receipt.kind not in _EXCLUDED_KINDS
        and (not needle or needle in _index_text(receipt))
    ]
    indexed.sort(key=lambda item: (item[1].step, item[0]), reverse=True)
    total = len(indexed)
    selected = indexed[start:start + bounded_limit]
    return {
        "query": str(query),
        "match_mode": "case_insensitive_literal_substring",
        "ordering": "newest_first",
        "semantic_ranking": False,
        "empty_query_lists_recent_receipts": True,
        "offset": start,
        "limit": bounded_limit,
        "total_matches": total,
        "more_available": start + len(selected) < total,
        "results": [receipt_address(receipt) for _, receipt in selected],
        "exact_retrieval": {
            "receipt": "read_output(handle='receipt:<receipt_id>')",
            "stream": "read_output(handle='<stdout_handle|stderr_handle>')",
        },
    }

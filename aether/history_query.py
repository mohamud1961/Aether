"""Literal, model-directed retrieval over the immutable execution receipt ledger.

This module deliberately does not rank relevance, summarize, embed, infer intent,
or choose context for the Solver. The model supplies a literal query; the kernel
returns mechanically matching receipt addresses newest-first. Exact receipt or
stream bytes remain available through ``read_output``.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
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

_CONTENT_KEYS = (
    "stdout_full", "stderr_full", "content", "chunk", "excerpt",
)
_STREAM_OVERFLOW = {
    "stdout_full": ("stdout_overflow_path", "stdout_handle"),
    "stderr_full": ("stderr_overflow_path", "stderr_handle"),
}
_STREAM_CHUNK_CHARS = 64 * 1024
_EXCERPT_BEFORE = 160
_EXCERPT_AFTER = 320
_MAX_QUERY_CHARS = 512
_MAX_EXCERPT_READ_CHARS = _MAX_QUERY_CHARS + _EXCERPT_AFTER
_SPOOL_DIR_PREFIX = "aether_output_spool_"
_SPOOL_FILE_NAMES = {
    "stdout_full": re.compile(r"^\d{6}_stdout\.txt$"),
    "stderr_full": re.compile(r"^\d{6}_stderr\.txt$"),
}
_INLINE_OVERFLOW_MARKER = re.compile(
    r"\n\.\.\. \[omitted \d+ chars inline; full \d+-char stream spooled to [^\n]*\]\n"
)


def _raw_overflow_path(payload: Mapping[str, Any], key: str) -> str:
    if key not in _STREAM_OVERFLOW:
        return ""
    overflow_key, _ = _STREAM_OVERFLOW[key]
    return str(payload.get(overflow_key, "") or "").strip()


def _overflow_path(payload: Mapping[str, Any], key: str) -> Path | None:
    raw_path = _raw_overflow_path(payload, key)
    if not raw_path:
        return None
    try:
        path = Path(raw_path).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    # RealExecutor's spool contract is a private, per-run directory with a
    # fixed filename shape. Reject arbitrary receipt metadata before opening a
    # path; this is a format/access boundary, not a substitute for custody.
    if not path.parent.name.startswith(_SPOOL_DIR_PREFIX):
        return None
    if not path.is_file() or not _SPOOL_FILE_NAMES[key].fullmatch(path.name):
        return None
    return path


def _inline_content(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if value in (None, ""):
        return ""
    text = str(value)
    if _raw_overflow_path(payload, key):
        # The executor's head/tail projection contains a synthetic line with
        # counts and a filesystem path. It is metadata, not command output.
        text = _INLINE_OVERFLOW_MARKER.sub("\n", text)
    return text


def _overflow_stream_match(
    payload: Mapping[str, Any], key: str, needle: str
) -> tuple[dict[str, Any] | None, bool]:
    """Find one literal match in the complete spooled stream without inlining it.

    ``RealExecutor`` stores only a bounded head+tail projection in ``stdout_full`` /
    ``stderr_full`` once a stream exceeds the inline cap. The omitted bytes remain
    authoritative through the overflow path and are already served by ``read_output``.
    History search must therefore consult that same source or text in the omitted
    middle becomes undiscoverable.
    """
    if not needle or key not in _STREAM_OVERFLOW:
        return None, True
    if not _raw_overflow_path(payload, key):
        return None, True
    overflow_path = _overflow_path(payload, key)
    if overflow_path is None:
        return None, False
    try:
        fh = overflow_path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        # A historical search is support, not runtime truth. Missing old spool
        # storage must not turn an otherwise valid query into invented evidence.
        return None, False

    overlap = min(max(_EXCERPT_BEFORE, len(needle) - 1), _MAX_QUERY_CHARS)
    carry = ""
    try:
        while True:
            chunk = fh.read(_STREAM_CHUNK_CHARS)
            if not chunk:
                return None, True
            buffer = carry + chunk
            pos = buffer.lower().find(needle)
            if pos >= 0:
                # Pull a little more text when the match is near the current chunk
                # boundary so the bounded excerpt remains useful without exposing
                # the complete stream.
                need_after = pos + len(needle) + _EXCERPT_AFTER - len(buffer)
                if need_after > 0:
                    buffer += fh.read(min(need_after, _MAX_EXCERPT_READ_CHARS))
                start = max(0, pos - _EXCERPT_BEFORE)
                end = min(len(buffer), pos + len(needle) + _EXCERPT_AFTER)
                row: dict[str, Any] = {
                    "field": key,
                    "excerpt": buffer[start:end],
                    "historical_observation": True,
                    "complete_stream_searched": True,
                    "source": "overflow_stream",
                }
                _, handle_key = _STREAM_OVERFLOW[key]
                handle = payload.get(handle_key)
                if handle:
                    row["handle"] = handle
                return row, True
            carry = buffer[-overlap:] if len(buffer) > overlap else buffer
    except OSError:
        return None, False
    finally:
        fh.close()


def _content_matches(receipt: Receipt, needle: str) -> list[dict[str, Any]]:
    if not needle:
        return []
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    matches: list[dict[str, Any]] = []
    for key in _CONTENT_KEYS:
        if _raw_overflow_path(payload, key):
            overflow_match, _ = _overflow_stream_match(payload, key, needle)
            if overflow_match is not None:
                matches.append(overflow_match)
            # Do not search the synthetic head/tail projection. The complete
            # stream is the only authoritative source when it is available.
            continue
        value = payload.get(key)
        if value not in (None, ""):
            text = _inline_content(payload, key)
            pos = text.lower().find(needle)
            if pos >= 0:
                start = max(0, pos - _EXCERPT_BEFORE)
                end = min(len(text), pos + len(needle) + _EXCERPT_AFTER)
                row: dict[str, Any] = {
                    "field": key,
                    "excerpt": text[start:end],
                    "historical_observation": True,
                    "complete_stream_searched": not bool(
                        key in _STREAM_OVERFLOW
                        and str(payload.get(_STREAM_OVERFLOW[key][0], "") or "").strip()
                    ),
                    "source": "inline_capture",
                }
                if key == "stdout_full" and payload.get("stdout_handle"):
                    row["handle"] = payload.get("stdout_handle")
                elif key == "stderr_full" and payload.get("stderr_handle"):
                    row["handle"] = payload.get("stderr_handle")
                elif key in {"content", "chunk", "excerpt"} and payload.get("file_handle"):
                    row["handle"] = payload.get("file_handle")
                matches.append(row)
        # Overflow-backed fields were handled from the complete stream above.
    return matches


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
    # Inline captured content remains in the cheap index. Overflow streams are
    # searched lazily only when the cheap index does not already match.
    for key in _CONTENT_KEYS:
        if _raw_overflow_path(payload, key):
            continue
        value = payload.get(key)
        if value not in (None, ""):
            parts.append(_inline_content(payload, key))
    return "\n".join(parts).lower()


def _receipt_matches(receipt: Receipt, needle: str) -> tuple[bool, bool]:
    if not needle:
        return True, True
    matched = needle in _index_text(receipt)
    complete = True
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    for key in _STREAM_OVERFLOW:
        if not _raw_overflow_path(payload, key):
            continue
        if matched:
            # The receipt is already included by a cheap indexed field. Do not
            # read every valid historical spool merely to rediscover that same
            # receipt; validate the referenced path so completeness still
            # reports missing or untrusted historical storage.
            complete = complete and _overflow_path(payload, key) is not None
            continue
        overflow_match, stream_complete = _overflow_stream_match(payload, key, needle)
        complete = complete and stream_complete
        matched = matched or overflow_match is not None
    return matched, complete


def receipt_address(receipt: Receipt, *, needle: str = "") -> dict[str, Any]:
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
    content_matches = _content_matches(receipt, needle)
    if content_matches:
        row["content_matches"] = content_matches
    return row


def query_history(
    receipts: Iterable[Receipt],
    query: str,
    *,
    offset: int = 0,
    limit: int = 8,
) -> dict[str, Any]:
    """Return deterministic literal matches newest-first with exact addresses."""
    raw_query = str(query)
    needle = raw_query.lower()
    start = max(0, int(offset))
    bounded_limit = max(1, min(20, int(limit)))
    if len(needle) > _MAX_QUERY_CHARS:
        return {
            "query": raw_query[:_MAX_QUERY_CHARS],
            "query_length": len(raw_query),
            "query_truncated": True,
            "query_rejected": True,
            "query_rejection_reason": f"query exceeds {_MAX_QUERY_CHARS} characters",
            "match_mode": "case_insensitive_literal_substring",
            "ordering": "newest_first",
            "semantic_ranking": False,
            "empty_query_lists_recent_receipts": True,
            "offset": start,
            "limit": bounded_limit,
            "total_matches": 0,
            "more_available": False,
            "results": [],
            "searched_content_fields": list(_CONTENT_KEYS),
            "complete_spooled_stream_search": False,
            "historical_results_are_current_state": False,
            "exact_retrieval": {
                "receipt": "read_output(handle='receipt:<receipt_id>')",
                "stream": "read_output(handle='<stdout_handle|stderr_handle>')",
            },
        }
    indexed: list[tuple[int, Receipt]] = []
    complete_spooled_stream_search = True
    for ordinal, receipt in enumerate(receipts):
        if receipt.kind in _EXCLUDED_KINDS:
            continue
        matched, receipt_search_complete = _receipt_matches(receipt, needle)
        complete_spooled_stream_search = (
            complete_spooled_stream_search and receipt_search_complete
        )
        if matched:
            indexed.append((ordinal, receipt))
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
        "results": [receipt_address(receipt, needle=needle) for _, receipt in selected],
        "searched_content_fields": list(_CONTENT_KEYS),
        "complete_spooled_stream_search": complete_spooled_stream_search,
        "historical_results_are_current_state": False,
        "exact_retrieval": {
            "receipt": "read_output(handle='receipt:<receipt_id>')",
            "stream": "read_output(handle='<stdout_handle|stderr_handle>')",
        },
    }

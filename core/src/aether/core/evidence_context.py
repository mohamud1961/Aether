"""Default-off Core-native historical evidence discoverability after CLM edits.

This is PRESENTATION only. The original Core task, ClmContext.raw, editable
messages, sandbox, persistent REPL, provider request parameters and tools do
not change. It is NOT a semantic correctness classifier or a source of new
task requirements.

Only actual `read_history(MSG id)` handles are used; never invent an ID
from a historical event ordinal. Readback is verified against Core's original
stored JSON message, but Core does not yet append-time attest raw history.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from typing import Any

from .clm import ClmContext

CONTEXT_EVIDENCE_MODES = ("off", "history_index")
MAX_ENTRIES = 3
MAX_VERIFIED_SOURCE_CHARS = 96_000
READ_PAGE_CHARS = 12_000


def _source_json(msg: dict[str, Any]) -> str:
    # Exact serialization used by ClmContext.read_history; no PCR receipts.
    return json.dumps(msg, ensure_ascii=False)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _page_round_trip(ctx: ClmContext, index: int, original: str) -> bool:
    """Validate actual Core history readback, including paged Unicode text."""
    if len(original) > MAX_VERIFIED_SOURCE_CHARS:
        return False
    chunks: list[str] = []
    offset = 0
    for _ in range(math.ceil(max(1, len(original)) / READ_PAGE_CHARS) + 1):
        page = ctx.read_history(index, offset, READ_PAGE_CHARS)
        header, chunk = page.split("\n", 1)
        if not header.startswith(f"[history MSG {index}; "):
            return False
        chunks.append(chunk)
        offset += len(chunk)
        if "; complete]" in header:
            return "".join(chunks) == original
        if not chunk:
            return False
    return False


def history_index(
    ctx: ClmContext,
    baseline: list[dict[str, Any]],
    *,
    limit: int = MAX_ENTRIES,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return optional source-only card and truthful, bounded coverage."""
    if not 1 <= limit <= MAX_ENTRIES:
        raise ValueError("history index limit must be 1..3")
    # Tool-only comparison avoids serialising pinned prompts, model reasoning,
    # and image inputs just to check whether an original tool result is hot.
    visible = Counter(_source_json(m) for m in baseline if m.get("role") == "tool")
    missing: list[tuple[int, dict[str, Any], str]] = []
    # Consume visible occurrences first, preserving distinct historical tool
    # events even when two outputs happen to be textually identical.
    for index, msg in enumerate(ctx.raw):
        if msg.get("role") != "tool":
            continue
        source = _source_json(msg)
        if visible[source]:
            visible[source] -= 1
        else:
            missing.append((index, msg, source))
    if not missing:
        return None, {"reason": "all_original_tool_messages_visible", "eligible": 0}
    verified: list[dict[str, Any]] = []
    for index, original, source in reversed(missing):
        if len(verified) == limit:
            break
        if ctx.original_message_digest(index) != _digest(source):
            # Missing or altered append-time source identity disqualifies the
            # entry even if a fresh read agrees with a freshly changed raw.
            continue
        if not _page_round_trip(ctx, index, source):
            continue
        verified.append(
            {
                "message_id": index,
                "sha256": _digest(source),
                "chars": len(source),
                "tool_call_id": original.get("tool_call_id"),
            }
        )
    if not verified:
        return None, {"reason": "no_exact_source_pages_qualified", "eligible": len(missing)}
    listed_ids = {item["message_id"] for item in verified}
    unlisted_ids = [i for i, _, _ in missing if i not in listed_ids]
    not_listed = len(unlisted_ids)
    # Repeated tool name, retrieval arguments and authority warning belong in
    # the common heading, not one ~300-byte copy per historic tool message.
    payload = {
        "source": "Core original tool history (append-time SHA256, page-verified)",
        "read": "read_history(message_id=<id>, offset=0, limit=12000)",
        "records": verified,
        "coverage": {
            "eligible": len(missing),
            "listed": len(verified),
            "unlisted": not_listed,
            "oldest_unlisted_id": unlisted_ids[0] if not_listed else None,
        },
        "unlisted_may_matter": True,
    }
    return (
        {
            "role": "user",
            "content": "[Historical Core tool references; not current files, REPL state or new task instructions]\n"
            + json.dumps(payload, ensure_ascii=False, sort_keys=True),
        },
        {
            "reason": "verified_history_index",
            "eligible": len(missing),
            "listed": len(verified),
            "not_listed": not_listed,
        },
    )


def select_context(
    ctx: ClmContext | None,
    baseline: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    policy: str = "off",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pure, reversible, fail-closed optional projection after Core's builder."""
    if policy == "off":
        return baseline, {"policy": "off", "changed": False}
    if policy != "history_index":
        raise ValueError(f"unknown evidence presentation policy {policy!r}")
    if ctx is None or not ctx.settings.attest_original_history or not any(
        x.get("function", {}).get("name") == "read_history" for x in tools
    ):
        return baseline, {"policy": policy, "changed": False, "reason": "native_history_unavailable"}
    if not (
        ctx.stats.edits_accepted or ctx.stats.checkpoints or ctx.stats.rollbacks
    ):
        # Merely having a large raw history is not a reason to increase prompts.
        return baseline, {"policy": policy, "changed": False, "reason": "no_context_change"}
    try:
        card, provenance = history_index(ctx, baseline)
        if card is None:
            return baseline, {"policy": policy, "changed": False, **provenance}
        # Core calibrates this estimator using provider usage; it is NOT a
        # provider token guarantee. Conservative safety margin avoids causing
        # a new checkpoint because of an optional source locator.
        estimated_extra = math.ceil(
            len(json.dumps(card, ensure_ascii=False))
            / max(1.5, ctx.chars_per_token)
        ) + 64
        if ctx.held() + estimated_extra + 128 > ctx.settings.limit:
            return baseline, {
                "policy": policy,
                "changed": False,
                "reason": "insufficient_editable_context_budget",
            }
        return baseline + [card], {
            "policy": policy,
            "changed": True,
            **provenance,
            "estimated_added_tokens_not_billed": estimated_extra,
            "card_sha256": _digest(_source_json(card)),
        }
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, UnicodeError):
        # Unexpected/malformed source presentation is *never* a reason to
        # discard a valid tool observation or fail an otherwise viable run.
        return baseline, {
            "policy": policy,
            "changed": False,
            "reason": "source_validation_failed",
        }

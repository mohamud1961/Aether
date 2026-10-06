"""Model-authored checkpoint at the Chat capacity boundary (``checkpoint_at_capacity_v1``).

When a Chat request would exceed the declared throughput limit, the plain
``recent_exchanges_v1`` rollover keeps only the last exact exchanges and drops
everything older, including all earlier reasoning.  This mode first asks the
model to write a checkpoint through the existing forced ``write_checkpoint``
call, then rebuilds the request as the immutable prefix, that checkpoint
(byte-for-byte, host writes no summary), the last exact exchanges and the
current packet.

This module is pure policy: it owns ordering, trimming and the outcome record.
Provider dispatch, pacing and request building are injected by the Chat
callable.  Any failure returns an explicit outcome with a reason; the caller
records it and falls back.  Nothing here swallows cancellation or deadlines.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .. import managed_context_checkpoint as _managed_context

CHECKPOINT_AT_CAPACITY_V1 = "checkpoint_at_capacity_v1"
FALLBACK_MODE = "recent_exchanges_v1"
KEPT_EXCHANGE_COUNT = 4
CAPACITY_CHECKPOINT_WRITTEN_EVENT = "capacity_checkpoint_written"
CAPACITY_CHECKPOINT_FAILED_EVENT = "capacity_checkpoint_failed"
CHECKPOINT_LABEL_PREFIX = "[your_checkpoint "


class CapacityCheckpointUnavailable(Exception):
    """The checkpoint call returned no usable checkpoint (recoverable, recorded)."""


@dataclass(frozen=True)
class CapacityCheckpointOutcome:
    ok: bool
    reason: str
    meta: dict[str, Any]
    content: str = ""
    rebuilt_messages: list[dict[str, Any]] = field(default_factory=list)
    estimated_tokens: int = 0


def is_checkpoint_message(message: Mapping[str, Any]) -> bool:
    content = message.get("content")
    return (
        message.get("role") == "user"
        and isinstance(content, str)
        and content.startswith(CHECKPOINT_LABEL_PREFIX)
    )


def fresh_prefix(
    fresh_messages: Sequence[Mapping[str, Any]], packet_prefix: str,
) -> list[dict[str, Any]]:
    """Immutable prefix: everything before the newest context packet."""
    rows = [dict(row) for row in fresh_messages]
    packet_indices = [
        i for i, row in enumerate(rows)
        if isinstance(row.get("content"), str) and row["content"].startswith(packet_prefix)
    ]
    return rows[:packet_indices[-1]] if packet_indices else rows[:-1]


def trim_checkpoint_view(
    prefix: Sequence[Mapping[str, Any]],
    segment: Sequence[Mapping[str, Any]],
    *,
    estimate: Callable[[list[dict[str, Any]]], int],
    token_limit: int,
) -> tuple[list[dict[str, Any]], int] | None:
    """Drop the oldest assistant exchanges until the checkpoint request fits.

    Leading non-assistant rows (an earlier checkpoint) are always kept.  Returns
    the kept segment and the dropped exchange count, or None when even the
    newest exchange cannot fit.
    """
    lead = 0
    while lead < len(segment) and segment[lead].get("role") != "assistant":
        lead += 1
    head = [dict(row) for row in segment[:lead]]
    body = [dict(row) for row in segment[lead:]]
    starts = [i for i, row in enumerate(body) if row.get("role") == "assistant"]
    if not starts:
        return None

    def view(dropped: int) -> list[dict[str, Any]]:
        return [*(dict(r) for r in prefix), *head, *body[starts[dropped]:]]

    low, high = 0, len(starts) - 1
    if estimate(view(high)) > token_limit:
        return None
    while low < high:
        mid = (low + high) // 2
        if estimate(view(mid)) <= token_limit:
            high = mid
        else:
            low = mid + 1
    return [*head, *body[starts[low]:]], low


def run_capacity_checkpoint(
    *,
    fresh_messages: Sequence[Mapping[str, Any]],
    pre_messages: Sequence[Mapping[str, Any]],
    packet_prefix: str,
    token_limit: int,
    pre_estimated_tokens: int,
    ordinal: int,
    step: int,
    select_exchanges: Callable[[Sequence[Mapping[str, Any]], int], list[dict[str, Any]]],
    estimate_view: Callable[[list[dict[str, Any]]], int],
    estimate_rebuilt: Callable[[list[dict[str, Any]]], int],
    dispatch: Callable[[list[dict[str, Any]]], str],
) -> CapacityCheckpointOutcome:
    meta: dict[str, Any] = {
        "mode": CHECKPOINT_AT_CAPACITY_V1,
        "pre_estimated_tokens": int(pre_estimated_tokens),
        "required_exchange_count": KEPT_EXCHANGE_COUNT,
        "semantic_ranking": False,
        "host_authored_summary": False,
    }

    def fail(reason: str) -> CapacityCheckpointOutcome:
        return CapacityCheckpointOutcome(False, reason, {**meta, "admission": "checkpoint_failed"})

    prefix = fresh_prefix(fresh_messages, packet_prefix)
    pre = [dict(row) for row in pre_messages]
    if pre[:len(prefix)] != prefix:
        return fail("fresh_prefix_not_leading_in_dispatched_request")
    exchanges = select_exchanges(pre, KEPT_EXCHANGE_COUNT)
    if not exchanges:
        return fail("recent_exchanges_unavailable")
    trimmed = trim_checkpoint_view(
        prefix, pre[len(prefix):], estimate=estimate_view, token_limit=token_limit,
    )
    if trimmed is None:
        return fail("checkpoint_request_over_capacity")
    segment, dropped = trimmed
    meta["checkpoint_view_dropped_exchange_count"] = dropped
    try:
        content = dispatch([*prefix, *segment])
    except CapacityCheckpointUnavailable as exc:
        return fail(f"checkpoint_call_failed:{exc}")
    if not isinstance(content, str) or not content.strip():
        return fail("checkpoint_content_empty")
    meta["checkpoint_bytes"] = len(content.encode("utf-8"))
    checkpoint = _managed_context.checkpoint_message(ordinal, step, content)
    rebuilt = [*prefix, checkpoint, *deepcopy(exchanges)]
    estimate = int(estimate_rebuilt(rebuilt))
    meta["estimated_tokens_with_recovery"] = estimate
    if estimate > int(token_limit):
        return CapacityCheckpointOutcome(
            False, "rebuilt_request_over_capacity",
            {**meta, "admission": "checkpoint_failed"}, content=content,
        )
    meta.update({
        "admission": "checkpoint_included",
        "post_estimated_tokens": estimate,
        "kept_exchange_count": sum(
            1 for i, row in enumerate(exchanges[:-1])
            if row.get("role") == "assistant" and exchanges[i + 1].get("role") == "tool"
        ),
    })
    return CapacityCheckpointOutcome(
        True, "", meta, content=content, rebuilt_messages=rebuilt, estimated_tokens=estimate,
    )


def failure_event(
    *, role: str, run_id: str, task_id: str, previous_call_id: str,
    outcome: CapacityCheckpointOutcome, token_limit: int,
) -> dict[str, Any]:
    return {
        "event_kind": CAPACITY_CHECKPOINT_FAILED_EVENT,
        "provider": "chat_completions",
        "role": role,
        "run_id": run_id,
        "task_id": task_id,
        "reason": outcome.reason,
        "mode": CHECKPOINT_AT_CAPACITY_V1,
        "fallback_mode": FALLBACK_MODE,
        "persistent_continuity_previous_call_id": previous_call_id,
        "pre_estimated_tokens": outcome.meta.get("pre_estimated_tokens"),
        "checkpoint_bytes": outcome.meta.get("checkpoint_bytes"),
        "throughput_token_limit": int(token_limit),
    }


def written_event(
    *, role: str, run_id: str, task_id: str, previous_call_id: str,
    outcome: CapacityCheckpointOutcome, token_limit: int,
) -> dict[str, Any]:
    return {
        "event_kind": CAPACITY_CHECKPOINT_WRITTEN_EVENT,
        "provider": "chat_completions",
        "role": role,
        "run_id": run_id,
        "task_id": task_id,
        "mode": CHECKPOINT_AT_CAPACITY_V1,
        "persistent_continuity_previous_call_id": previous_call_id,
        "pre_estimated_tokens": outcome.meta["pre_estimated_tokens"],
        "post_estimated_tokens": outcome.meta["post_estimated_tokens"],
        "checkpoint_bytes": outcome.meta["checkpoint_bytes"],
        "kept_exchange_count": outcome.meta["kept_exchange_count"],
        "throughput_token_limit": int(token_limit),
    }

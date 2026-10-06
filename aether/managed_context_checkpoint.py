"""GLM-authored checkpoint compaction (``managed_context_checkpoint_v1``), opt-in.

Once the Solver context is large, the model itself writes a checkpoint through a
forced native ``write_checkpoint`` call.  The conversation then continues from
the fixed prefix, that checkpoint byte-for-byte, the last K complete exchanges
and the current tool result.  Aether never edits, summarizes or validates what
the model wrote; the older turns stay retrievable through the receipt ledger
(``query_history`` / ``read_output``).

This module holds only the pure policy pieces (trigger arithmetic, the factual
checkpoint request text, request reshaping, bookkeeping).  Provider dispatch,
pacing and telemetry stay in ``providers.chat_model``.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

MANAGED_CONTEXT_POLICY_CONTROL = "control"
MANAGED_CONTEXT_POLICY_CHECKPOINT_V1 = "managed_context_checkpoint_v1"
MANAGED_CONTEXT_POLICY_CHECKPOINT_UNCACHED_V1 = "managed_context_checkpoint_uncached_v1"
MANAGED_CONTEXT_CHECKPOINT_POLICIES = frozenset({MANAGED_CONTEXT_POLICY_CHECKPOINT_V1, MANAGED_CONTEXT_POLICY_CHECKPOINT_UNCACHED_V1})
MANAGED_CONTEXT_POLICIES = frozenset({MANAGED_CONTEXT_POLICY_CONTROL, *MANAGED_CONTEXT_CHECKPOINT_POLICIES})
MANAGED_CONTEXT_DEFAULT_TRIGGER_TOKENS = 48000
MANAGED_CONTEXT_DEFAULT_KEEP_EXCHANGES = 2
MANAGED_CONTEXT_MAX_CHECKPOINT_ATTEMPTS = 2
MANAGED_CONTEXT_REPEAT_WINDOW_CALLS = 5
MANAGED_CONTEXT_FAILURE_COOLDOWN_CALLS = 5
MANAGED_CONTEXT_REQUIRED_TOOL_NAMES = ("query_history", "read_output")
MANAGED_CONTEXT_TOOL_NAME = "write_checkpoint"
MANAGED_CONTEXT_RECEIPT_KIND = "managed_context_checkpoint"
MANAGED_CONTEXT_FAILED_RECEIPT_KIND = "managed_context_checkpoint_failed"
_REPEAT_TOOLS = frozenset({"read_file", "read_output"})

CHECKPOINT_REQUEST_TEXT = (
    "[context_checkpoint] Older conversation turns will be replaced by a checkpoint that "
    "you write now. They remain retrievable with query_history and read_output. Call "
    "write_checkpoint with everything you need to continue: the task requirements and "
    "their status, files you changed and why, verified facts with receipt ids, current "
    "hypotheses, approaches that failed, and your exact next steps."
)

WRITE_CHECKPOINT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": MANAGED_CONTEXT_TOOL_NAME,
        "description": "Record the checkpoint that stands in for the older conversation turns.",
        "parameters": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}
FORCED_TOOL_CHOICE: dict[str, Any] = {"type": "function", "function": {"name": MANAGED_CONTEXT_TOOL_NAME}}


class CheckpointRejected(ValueError):
    """The checkpoint turn did not yield a usable write_checkpoint call."""


def message_bytes(message: Mapping[str, Any]) -> int:
    return len(json.dumps(
        message, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    ).encode("utf-8"))


def estimate_request_tokens(
    last_input_tokens: int,
    messages: Sequence[Mapping[str, Any]],
    last_message_count: int,
) -> int:
    """Last provider input tokens plus bytes/4 of messages appended since."""
    added = sum(message_bytes(m) for m in messages[max(0, int(last_message_count)):])
    return int(last_input_tokens) + added // 4


def checkpoint_request_messages(prepared: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [*(deepcopy(dict(m)) for m in prepared), {"role": "user", "content": CHECKPOINT_REQUEST_TEXT}]


def checkpoint_message(ordinal: int, step: int, content: str) -> dict[str, Any]:
    """The continuing-history message: fixed label line, then the content verbatim."""
    return {
        "role": "user",
        "content": f"[your_checkpoint {int(ordinal)}, written at step {int(step)}]\n{content}",
    }


def reshape_history(
    history: Sequence[Mapping[str, Any]],
    checkpoint: Mapping[str, Any],
    *,
    keep_exchanges: int,
) -> list[dict[str, Any]]:
    """Checkpoint, then the last K complete exchanges and the pending assistant turn.

    ``history`` is the committed transcript suffix that ends with the assistant
    message whose tool result is the current request's boundary.  Everything from
    the (K+1)-th last assistant message onward is kept unchanged.
    """
    assistants = [i for i, m in enumerate(history) if m.get("role") == "assistant"]
    if not assistants:
        raise CheckpointRejected("managed_context_history_has_no_assistant_turn")
    start = assistants[max(0, len(assistants) - (max(0, int(keep_exchanges)) + 1))]
    kept = [deepcopy(dict(m)) for m in history[start:]]
    # Only the newest assistant turn keeps its reasoning. Older kept turns'
    # reasoning otherwise holds the post-checkpoint floor near the trigger and
    # re-fires a checkpoint on nearly every call (Wave 1 r1/v1).
    newest = max(i for i, m in enumerate(kept) if m.get("role") == "assistant")
    for i, m in enumerate(kept):
        if i != newest and m.get("role") == "assistant":
            m.pop("reasoning_content", None)
    return [dict(checkpoint), *kept]


def extract_checkpoint_content(response: Any) -> tuple[str, dict[str, Any]]:
    """Return the model's checkpoint text exactly as written, or raise."""
    choices = _get(response, "choices") or ()
    if len(choices) != 1:
        raise CheckpointRejected("managed_context_choice_count_invalid")
    choice = choices[0]
    finish = str(_get(choice, "finish_reason") or "")
    if finish in {"length", "max_tokens", "content_filter"}:
        raise CheckpointRejected(f"managed_context_provider_output_truncated:{finish}")
    calls = _get(_get(choice, "message"), "tool_calls") or ()
    named = [c for c in calls if _get(_get(c, "function"), "name") == MANAGED_CONTEXT_TOOL_NAME]
    if not named:
        raise CheckpointRejected("managed_context_write_checkpoint_missing")
    call = named[0]
    raw = _get(_get(call, "function"), "arguments")
    try:
        args = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except (TypeError, ValueError):
        raise CheckpointRejected("managed_context_write_checkpoint_arguments_invalid") from None
    content = args.get("content") if isinstance(args, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise CheckpointRejected("managed_context_write_checkpoint_content_empty")
    return content, {
        "native_tool_name": MANAGED_CONTEXT_TOOL_NAME,
        "native_tool_call_id": str(_get(call, "id") or ""),
        "native_tool_call_count": len(calls),
        "native_tool_call_observed_known": True,
        "native_tool_call_observed": True,
        "finish_reason": finish,
        "managed_context_checkpoint_call": True,
    }


def read_action_key(tool_call: Mapping[str, Any]) -> str | None:
    """Stable key for a read_file/read_output call, else None."""
    function = tool_call.get("function") if isinstance(tool_call, Mapping) else None
    name = function.get("name") if isinstance(function, Mapping) else None
    if name not in _REPEAT_TOOLS:
        return None
    raw = function.get("arguments")
    try:
        args = json.loads(raw) if isinstance(raw, str) else raw
        canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        canonical = str(raw)
    return f"{name}:{canonical}"


def _get(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


@dataclass
class ClmScope:
    """Per task-scope bookkeeping owned by the chat callable."""

    step: int = 0
    last_input_tokens: int | None = None
    last_cached_input_tokens: int | None = None
    last_message_count: int = 0
    calls_since_checkpoint: int = 0
    cooldown_calls: int = 0
    post_checkpoint_floor: int | None = None
    post_checkpoint_uncached_floor: int | None = None
    ordinal: int = 0
    seen_reads: set[str] = field(default_factory=set)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def eligible_estimate(self, messages: Sequence[Mapping[str, Any]]) -> int | None:
        """Estimated total request tokens, or None when no measured input exists yet."""
        if self.last_input_tokens is None or self.cooldown_calls > 0:
            return None
        return estimate_request_tokens(self.last_input_tokens, messages, self.last_message_count)

    def eligible_uncached_estimate(
        self, messages: Sequence[Mapping[str, Any]],
    ) -> int | None:
        """Conservative estimate of uncached input for the next request.

        Provider cache telemetry is only known after a completed request. Stable
        previously cached input is assumed to remain cacheable; newly appended
        message bytes are charged as uncached. Missing cache telemetry fails
        closed by treating the whole previous input as uncached.
        """
        if self.last_input_tokens is None or self.cooldown_calls > 0:
            return None
        cached = (
            int(self.last_cached_input_tokens)
            if isinstance(self.last_cached_input_tokens, int)
            else 0
        )
        previous_uncached = max(0, int(self.last_input_tokens) - cached)
        added = sum(
            message_bytes(m)
            for m in messages[max(0, int(self.last_message_count)):]
        ) // 4
        return previous_uncached + added

    def trigger_threshold(self, trigger_tokens: int, *, uncached: bool = False) -> int:
        """Hysteresis: after a checkpoint, require T/2 growth above the new floor."""
        base = int(trigger_tokens)
        floor = (
            self.post_checkpoint_uncached_floor
            if uncached else self.post_checkpoint_floor
        )
        if floor is None:
            return base
        return max(base, int(floor) + base // 2)

    def note_response(
        self, *, input_tokens: Any, cached_input_tokens: Any = None,
        message_count: int,
    ) -> None:
        self.last_message_count = int(message_count)
        self.last_input_tokens = int(input_tokens) if isinstance(input_tokens, int) else None
        self.last_cached_input_tokens = (
            int(cached_input_tokens) if isinstance(cached_input_tokens, int) else None
        )
        self.calls_since_checkpoint += 1
        self.cooldown_calls = max(0, self.cooldown_calls - 1)
        for metric in self.metrics:
            if metric["input_tokens_next_request"] is None and isinstance(input_tokens, int):
                total = int(input_tokens)
                cached = (
                    int(cached_input_tokens)
                    if isinstance(cached_input_tokens, int) else None
                )
                uncached = total - cached if cached is not None else total
                metric["input_tokens_next_request"] = total
                metric["cached_input_tokens_next_request"] = cached
                metric["uncached_input_tokens_next_request"] = max(0, uncached)
                self.post_checkpoint_floor = total
                self.post_checkpoint_uncached_floor = max(0, uncached)

    def record_checkpoint(
        self, *, step: int, content: str, trigger_estimate: int,
        call_input_tokens: Any, call_cached_input_tokens: Any = None,
        attempts: int, trigger_basis: str = "total_input",
    ) -> dict[str, Any]:
        self.ordinal += 1
        encoded = content.encode("utf-8")
        metric = {
            "ordinal": self.ordinal,
            "step": int(step),
            "content_bytes": len(encoded),
            "content_sha256": sha256(encoded).hexdigest(),
            "input_tokens_before": self.last_input_tokens,
            "cached_input_tokens_before": self.last_cached_input_tokens,
            "uncached_input_tokens_before": (
                max(0, int(self.last_input_tokens) - int(self.last_cached_input_tokens))
                if isinstance(self.last_input_tokens, int)
                and isinstance(self.last_cached_input_tokens, int)
                else self.last_input_tokens
            ),
            "estimated_tokens_at_trigger": int(trigger_estimate),
            "trigger_basis": str(trigger_basis),
            "checkpoint_call_input_tokens": (
                int(call_input_tokens) if isinstance(call_input_tokens, int) else None
            ),
            "checkpoint_call_cached_input_tokens": (
                int(call_cached_input_tokens)
                if isinstance(call_cached_input_tokens, int) else None
            ),
            "checkpoint_call_uncached_input_tokens": (
                max(0, int(call_input_tokens) - int(call_cached_input_tokens))
                if isinstance(call_input_tokens, int)
                and isinstance(call_cached_input_tokens, int)
                else (int(call_input_tokens) if isinstance(call_input_tokens, int) else None)
            ),
            "input_tokens_next_request": None,
            "cached_input_tokens_next_request": None,
            "uncached_input_tokens_next_request": None,
            "repeated_reads_within_window": 0,
            "window_calls_observed": 0,
            "window_calls": MANAGED_CONTEXT_REPEAT_WINDOW_CALLS,
            "attempts": int(attempts),
            "_pre_seen": set(self.seen_reads),
        }
        self.metrics.append(metric)
        self.calls_since_checkpoint = 0
        self.last_input_tokens = None
        self.last_cached_input_tokens = None
        self.last_message_count = 0
        self.events.append({
            "kind": MANAGED_CONTEXT_RECEIPT_KIND,
            "step": int(step),
            "content": content,
            **{k: v for k, v in metric.items() if not k.startswith("_")},
        })
        return metric

    def record_failure(self, *, step: int, attempts: Sequence[Mapping[str, Any]]) -> None:
        # A failed checkpoint is not retried on every following step; the
        # untouched transcript keeps working and the next try comes later.
        self.cooldown_calls = MANAGED_CONTEXT_FAILURE_COOLDOWN_CALLS
        self.events.append({
            "kind": MANAGED_CONTEXT_FAILED_RECEIPT_KIND,
            "step": int(step),
            "attempted_ordinal": self.ordinal + 1,
            "attempts": [dict(a) for a in attempts],
            "history_cut": False,
        })

    def note_committed_action(self, key: str | None) -> list[dict[str, Any]]:
        """Update repeated-read windows for one admitted turn; return metric snapshots."""
        snapshots: list[dict[str, Any]] = []
        for metric in self.metrics:
            if metric["window_calls_observed"] >= metric["window_calls"]:
                continue
            metric["window_calls_observed"] += 1
            if key is not None and key in metric["_pre_seen"]:
                metric["repeated_reads_within_window"] += 1
            # Progressive snapshot per call; analysts take the last per ordinal.
            snapshots.append(public_metric(metric))
        if key is not None:
            self.seen_reads.add(key)
        return snapshots


def public_metric(metric: Mapping[str, Any]) -> dict[str, Any]:
    return {k: deepcopy(v) for k, v in metric.items() if not k.startswith("_")}

"""How a provider carries the model's reasoning on the wire (a protocol adapter; it never reads the reasoning).

Inside Core an assistant message keeps its reasoning in ``reasoning_content`` (text, or a list of opaque items), so the
CLM replay policies apply unchanged. Providers differ in where that reasoning arrives and where it must go back
(gate probes 2026-10-27, research/context_policy_20261027/gate):

- ``reasoning_content`` (default, Flint): streamed and replayed as ``reasoning_content``. Unchanged behaviour.
- ``reasoning`` (DeepSeek V4 on Dahl): streamed as ``reasoning``; the chat template renders ``reasoning`` and not
  ``reasoning_content`` (tool-loop prompt 700 vs 340 tokens), so it goes back as ``reasoning``.
- ``think_tags`` (MiniMax M2.7 on Dahl): the reasoning is inline in ``content`` as ``<think>...</think>``. It is split
  out after the stream so the replay policy can drop it, and put back inline when replayed.
- ``reasoning_details`` (Mercury 3): an encrypted list streamed as ``reasoning_details``; kept as opaque items and
  replayed as ``reasoning_details``.
"""

from __future__ import annotations

from typing import Any

WIRES = ("reasoning_content", "reasoning", "think_tags", "reasoning_details")
OPEN, CLOSE = "<think>", "</think>"


def _field(delta: Any, name: str) -> Any:
    value = getattr(delta, name, None)
    if value is None:
        value = (getattr(delta, "model_extra", None) or {}).get(name)
    return value


def read_delta(wire: str, delta: Any, turn: Any) -> None:
    """Add one streamed delta's reasoning to ``turn`` (content is handled by the caller)."""
    if wire == "reasoning_details":
        for item in _field(delta, "reasoning_details") or ():
            turn.reasoning_items.append(dict(item) if not isinstance(item, dict) else item)
        return
    name = "reasoning" if wire == "reasoning" else "reasoning_content"
    turn.reasoning += _field(delta, name) or ""


def finish(wire: str, turn: Any) -> None:
    """After the stream: split inline ``<think>`` reasoning out of the content (``think_tags`` only). On a tool-call
    turn MiniMax on Dahl sends ``<think>...`` with no closing tag (gate g1, 2026-10-27): all of it is reasoning."""
    if wire != "think_tags":
        return
    if CLOSE not in turn.content:
        if turn.content.lstrip().startswith(OPEN):
            turn.reasoning += turn.content.lstrip()[len(OPEN):]
            turn.content = ""
        return
    head, _, tail = turn.content.partition(CLOSE)
    turn.reasoning += head.split(OPEN, 1)[1] if OPEN in head else head
    turn.content = tail.lstrip("\n")


def outgoing(wire: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The messages as the provider expects them: Core's ``reasoning_content`` moved to the provider's field."""
    if wire == "reasoning_content":
        return messages
    out = []
    for msg in messages:
        if msg.get("role") != "assistant" or "reasoning_content" not in msg:
            out.append(msg)
            continue
        msg = dict(msg)
        value = msg.pop("reasoning_content")
        if wire == "think_tags":
            msg["content"] = f"{OPEN}{value}{CLOSE}\n\n{msg.get('content') or ''}"
        elif wire == "reasoning":
            msg["reasoning"] = value
        else:
            msg["reasoning_details"] = value
        out.append(msg)
    return out

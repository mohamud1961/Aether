"""Opt-in arm that stops replaying old tool-result bulk in the model-facing request history.

Under ``AETHER_G4_HISTORY_MODE=lean_v1`` a tool result that is older than ``TOOL_KEEP`` tool messages and
lies in a completed block of ``BLOCK`` tool messages (compacted ordinals ``< BLOCK * floor((n - TOOL_KEEP) / BLOCK)``
for ``n`` tool messages) is reduced to its first and last ``EDGE_CHARS`` characters with a marker naming how to see the
omitted middle. Assistant messages (content, tool_calls and ``reasoning_content``) are never touched:
historical reasoning is replayed complete and unmodified. Nothing is removed from stored evidence.

The projection is a pure function of the message list, applied to a copy at the request boundary.
Each message's projected form depends only on its own content and on whether it is among the newest
tool messages and block, so the compacted region grows ``BLOCK`` messages at a time (the request prefix
changes form once every ``BLOCK`` steps) and once a message has aged out it is rendered identically on every later request (the
provider prompt cache keeps matching everything before the message that is currently aging out).

Under the same mode the boundary ``[context_packet]`` tool message is also rendered cache-stably (see
``stable_packet_content``): ``latest_primary_result`` is serialized first and the volatile per-turn state
(budgets, remaining_run_sec, capabilities, evidence rows, feedback) after it. Under the
``observation_history_v1`` transport the next request rewrites that message to just
``latest_primary_result``; with the result first, the rewrite is a byte-prefix of what was sent, so the
provider prefix cache keeps everything up to the end of the result instead of missing from the packet start.
Model-visible content is unchanged apart from JSON key order.
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any, Mapping, Sequence

CONTROL = "control"
LEAN_V1 = "lean_v1"
SUPPORTED_HISTORY_MODES = frozenset({CONTROL, LEAN_V1})
HISTORY_MODE_ENV = "AETHER_G4_HISTORY_MODE"
TOOL_KEEP = 8
BLOCK = 8
EDGE_CHARS = 600
_HANDLE = re.compile(r'"handle"\s*:\s*"([^"]+)"')


class HistoryModeError(ValueError):
    """An unknown mode or an unexpected message shape was supplied."""


def resolve_history_mode(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(HISTORY_MODE_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_HISTORY_MODES:
        raise HistoryModeError(f"unknown history mode: {selected!r}")
    return selected


def add_history_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--history-mode", choices=sorted(SUPPORTED_HISTORY_MODES), default=CONTROL,
        help="shorten old tool results in the request history; assistant messages untouched (opt-in)",
    )


def build_history_launch_binding(mode: str | None) -> dict[str, Any]:
    selected = resolve_history_mode(mode)
    return {
        "history_mode": selected, "env": {HISTORY_MODE_ENV: selected},
        "manifest": {"history_mode": selected},
    }


def truncate_tool_content(content: str) -> str:
    """First and last ``EDGE_CHARS`` characters plus a marker; short content is returned unchanged."""
    omitted = len(content) - 2 * EDGE_CHARS
    if omitted <= 0:
        return content
    handle = _HANDLE.search(content)
    how = (
        f"re-run the command or use read_output on {handle.group(1)} to see it" if handle
        else "re-run the command or use query_history to see it"
    )
    return f"{content[:EDGE_CHARS]}\n[... {omitted} characters omitted; {how} ...]\n{content[-EDGE_CHARS:]}"


def project_history_lean(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return a shallow-copied list with old tool results shortened; non-tool messages are copied as-is.

    The newest tool message is last in ``messages`` for a request, so tool ordinals count from the oldest, which is stable as history is append-only.
    The input messages are never mutated.
    """
    tool_idx = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    cutoff = BLOCK * max(0, (len(tool_idx) - TOOL_KEEP) // BLOCK)
    old_tool = set(tool_idx[:cutoff])
    out: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        row = dict(message)
        if index in old_tool:
            content = row.get("content")
            if isinstance(content, str):
                row["content"] = truncate_tool_content(content)
            elif content is not None:
                raise HistoryModeError("tool content is not a string; refusing to guess a lean view")
        out.append(row)
    return out


PACKET_PREFIX = "[context_packet]\n"
_RESULT_KEY = "latest_primary_result"


def _dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_packet_content(content: str) -> str:
    """Re-serialize a ``[context_packet]`` with ``latest_primary_result`` first; other content is returned as is.

    The remaining keys keep their sorted order. A packet without a ``latest_primary_result`` mapping, or
    content that is not a packet, is returned unchanged.
    """
    if not isinstance(content, str) or not content.startswith(PACKET_PREFIX):
        return content
    try:
        packet = json.loads(content[len(PACKET_PREFIX):])
    except ValueError:
        return content
    if not isinstance(packet, dict) or not isinstance(packet.get(_RESULT_KEY), dict):
        return content
    rest = {key: value for key, value in packet.items() if key != _RESULT_KEY}
    head = f'{PACKET_PREFIX}{{"{_RESULT_KEY}":{_dumps(packet[_RESULT_KEY])}'
    return head + ("," + _dumps(rest)[1:] if rest else "}")

"""Fresh-call epochs and the stable M-TREE request prefix [OptChat §7–8]."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from .compactor import VIEW_DOC

EPOCH_TOKENS = 96_000
EPOCH_STEPS = 24

ZOOM_TOOL = {
    "type": "function",
    "function": {
        "name": "zoom",
        "description": "Open line id+n into its two child lines; n=1 returns the event whole.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "minimum": 0},
                "n": {"type": "integer", "minimum": 1},
            },
            "required": ["id", "n"], "additionalProperties": False,
        },
    },
}


class MTreeEpochOverflow(RuntimeError):
    code = "m_tree_epoch_overflow"

    def __init__(self, estimated_tokens: int, request_limit: int) -> None:
        self.estimated_tokens = int(estimated_tokens)
        self.request_limit = int(request_limit)
        super().__init__(
            f"m_tree_epoch_overflow: estimated request {estimated_tokens} exceeds {request_limit}"
        )


@dataclass
class EpochState:
    index: int = 0
    request_tokens: int = 0
    accepted_actions: int = 0


class EpochPolicy:
    """End an epoch only after a completed action and its result are logged."""

    def __init__(self, *, token_limit: int = EPOCH_TOKENS,
                 step_limit: int = EPOCH_STEPS) -> None:
        if token_limit < 1 or step_limit < 1:
            raise ValueError("epoch limits must be positive")
        self.token_limit = int(token_limit)
        self.step_limit = int(step_limit)
        self.current = EpochState()
        self.boundaries: list[dict[str, Any]] = []

    def note_request(self, estimated_tokens: int, *, request_limit: int) -> None:
        if estimated_tokens > request_limit:
            raise MTreeEpochOverflow(estimated_tokens, request_limit)
        self.current.request_tokens += max(0, int(estimated_tokens))

    def accepted_action(self) -> str | None:
        self.current.accepted_actions += 1
        reason = None
        if self.current.request_tokens >= self.token_limit:
            reason = "epoch_tokens"
        elif self.current.accepted_actions >= self.step_limit:
            reason = "epoch_steps"
        if reason is not None:
            self.boundaries.append({
                "epoch": self.current.index,
                "reason": reason,
                "request_tokens": self.current.request_tokens,
                "accepted_actions": self.current.accepted_actions,
            })
            self.current = EpochState(index=self.current.index + 1)
        return reason


def solver_system_prompt(existing_solver_text: str) -> str:
    return existing_solver_text + "\n\n" + VIEW_DOC


def build_fresh_call_request(*, tools: Sequence[Mapping[str, Any]],
                             system_prompt: str, raw_task: str, view_text: str,
                             context_packet: str, latest_action: str | None = None,
                             latest_result: str | None = None,
                             epoch_steps: Sequence[Mapping[str, Any]] = (),
                             epoch_index: int = 0) -> dict[str, Any]:
    """Build the ordered tools/system/task/view/volatile request prefix."""
    visible_tools = [deepcopy(dict(item)) for item in tools]
    if not any(_tool_name(item) == "zoom" for item in visible_tools):
        visible_tools.append(deepcopy(ZOOM_TOOL))
    volatile = str(context_packet)
    if latest_action is not None:
        volatile += f"\n\nLatest action: {latest_action}"
    if latest_result is not None:
        volatile += f"\nFull result:\n{latest_result}"
    prefix = [
        {"role": "system", "content": str(system_prompt)},
        {"role": "user", "content": [
            {"type": "text", "text": raw_task},
            {"type": "text", "text": view_text},
            {"type": "text", "text": volatile},
        ]},
    ]
    messages = prefix + [deepcopy(dict(item)) for item in epoch_steps]
    static_prefix = json.dumps(
        {"tools": visible_tools, "system": str(system_prompt)},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return {
        "tools": visible_tools,
        "messages": messages,
        "epoch_index": int(epoch_index),
        "static_prefix_sha256": hashlib.sha256(static_prefix).hexdigest(),
        "static_prefix_bytes": len(static_prefix),
    }


def preserve_control_request(request: Any) -> Any:
    """Control is returned as-is so M-TREE cannot alter its request identity."""
    return request


def _tool_name(tool: Mapping[str, Any]) -> str:
    function = tool.get("function")
    return str(function.get("name") or "") if isinstance(function, Mapping) else str(tool.get("name") or "")

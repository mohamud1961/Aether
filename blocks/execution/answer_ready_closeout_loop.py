"""Force a closeout assistant turn when direct-answer state is already grounded."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from blocks.execution.flat_loop import run_loop as baseline_run_loop

_STATE_KEY = "grounded_answer_ready_state"
_STATE_RE = re.compile(r"\[grounded_answer_ready_state\]\s*(\{.*\})")


def run_loop(
    model: Any,
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    context: dict[str, Any],
    max_steps: int,
    tool_definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    closeout_state = {
        "enabled": True,
        "forced_closeout": False,
        "forced_closeout_count": 0,
        "forced_answer": "",
        "reason_code": "",
        "suppressed_tool_names": [],
    }
    result = baseline_run_loop(
        model=_AnswerReadyCloseoutModel(model, closeout_state),
        tools=tools,
        context=context,
        max_steps=max_steps,
        tool_definitions=tool_definitions,
    )
    result["answer_ready_closeout_state"] = closeout_state
    return result


class _AnswerReadyCloseoutModel:
    def __init__(self, model: Any, closeout_state: dict[str, Any]) -> None:
        self._model = model
        self._closeout_state = closeout_state

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        completion = self._model.complete(messages, **kwargs)
        tool_calls = completion.get("tool_calls")
        closeout = _closeout_payload(messages)
        if not isinstance(tool_calls, list) or not tool_calls or not closeout:
            return completion
        self._closeout_state["forced_closeout"] = True
        self._closeout_state["forced_closeout_count"] += 1
        self._closeout_state["forced_answer"] = closeout["answer"]
        self._closeout_state["reason_code"] = closeout["reason_code"]
        self._closeout_state["suppressed_tool_names"] = [
            tool_call.get("name")
            for tool_call in tool_calls
            if isinstance(tool_call, dict) and isinstance(tool_call.get("name"), str)
        ]
        patched = dict(completion)
        patched["text"] = closeout["answer"]
        patched["tool_calls"] = []
        return patched


def _closeout_payload(messages: list[dict[str, Any]]) -> dict[str, str]:
    state = _latest_state(messages)
    answer = str(state.get("answer") or "").strip()
    if not state.get("direct_answer_task") or not state.get("answer_ready") or not answer:
        return {}
    return {"answer": answer, "reason_code": str(state.get("reason_code") or "answer_ready")}


def _latest_state(messages: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(messages):
        if not isinstance(row, dict):
            continue
        state = row.get(_STATE_KEY)
        if isinstance(state, dict):
            return dict(state)
        content = row.get("content")
        if not isinstance(content, str):
            continue
        for line in reversed(content.splitlines()):
            match = _STATE_RE.search(line.strip())
            if not match:
                continue
            try:
                parsed = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}

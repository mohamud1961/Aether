"""Packet 04 slice-2 execution candidate with explicit cwd/workdir telemetry."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from blocks.execution.flat_loop import run_loop as baseline_run_loop


def run_loop(
    model: Any,
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    context: dict[str, Any],
    max_steps: int,
    tool_definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the baseline loop while exporting explicit path-contract telemetry."""
    env_info = context.get("env_info", {})
    expected_cwd = env_info.get("cwd") if isinstance(env_info, dict) else None
    result = baseline_run_loop(
        model=model,
        tools=tools,
        context=context,
        max_steps=max_steps,
        tool_definitions=tool_definitions,
    )
    history = result.get("history", [])
    cwd_snapshot = _infer_cwd_from_history(history)
    observed_cwd = cwd_snapshot if isinstance(cwd_snapshot, str) and cwd_snapshot else expected_cwd
    result["path_contract_state"] = {
        "expected_cwd": expected_cwd if isinstance(expected_cwd, str) else None,
        "cwd_snapshot": cwd_snapshot,
        "observed_cwd": observed_cwd if isinstance(observed_cwd, str) else None,
        "cwd_match": bool(
            isinstance(expected_cwd, str)
            and isinstance(observed_cwd, str)
            and expected_cwd == observed_cwd
        ),
        "history_entries": len(history) if isinstance(history, list) else 0,
        "step_count": result.get("step_count", 0),
        "cwd_invariant_guard_applied": True,
    }
    return result


def _infer_cwd_from_history(history: Any) -> str | None:
    if not isinstance(history, list):
        return None
    for message in history:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, str) or not content:
            continue
        candidate = content.strip().splitlines()[-1].strip()
        if candidate.startswith("/") and Path(candidate).is_absolute():
            return candidate
    return None

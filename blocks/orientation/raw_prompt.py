"""Simplest orientation: pass the task prompt to the model unchanged.

Interface: OrientationBlock.orient(task_prompt, env_info) -> initial_context
"""

from __future__ import annotations

from typing import Any


def orient(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the minimal initial context for the baseline runner."""
    return {
        "task_prompt": task_prompt,
        "env_info": dict(env_info or {}),
        "messages": [{"role": "user", "content": task_prompt}],
    }

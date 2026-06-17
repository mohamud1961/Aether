"""Organize context into structured sections: doctrine, task, evidence.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

from typing import Any

from .full_history import append_observation

_SECTION_KEYS = ("doctrine", "task", "evidence")


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Attach a compact structured-section view when section payloads are present."""
    observation = dict(new_observation)
    section_state: dict[str, Any] = {}
    for key in _SECTION_KEYS:
        value = observation.get(key)
        if isinstance(value, str) and value:
            section_state[key] = value
    if section_state:
        observation["structured_sections"] = section_state
    return append_observation(history, observation)

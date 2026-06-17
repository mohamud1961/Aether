"""Keep full conversation history until context window overflows.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

from typing import Any


def append_observation(history: list[dict[str, Any]], observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Return history with a copied observation appended."""
    updated = list(history)
    updated.append(dict(observation))
    return updated


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Append observations without truncation."""
    return append_observation(history, new_observation)

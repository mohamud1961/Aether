"""Preserve bounded workspace-target evidence alongside normal history.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

from typing import Any

from .full_history import append_observation

_WORKSPACE_TARGET_KEYS = (
    "resolved_target_file_id",
    "touched_decoy_file_ids",
    "target_candidate_rank_trace",
    "workspace_integrity_summary",
    "reason_code_distribution",
)


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Append history and attach bounded workspace-target state when available."""
    observation = dict(new_observation)
    workspace_target_state = _extract_workspace_target_state(observation)
    if workspace_target_state:
        observation["workspace_target_state"] = workspace_target_state
    return append_observation(history, observation)


def _extract_workspace_target_state(observation: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key in _WORKSPACE_TARGET_KEYS:
        value = observation.get(key)
        if value is None:
            continue
        if key in {"workspace_integrity_summary", "reason_code_distribution"} and isinstance(value, dict):
            state[key] = dict(value)
            continue
        if key == "touched_decoy_file_ids" and isinstance(value, list):
            state[key] = [item for item in value if isinstance(item, str) and item]
            continue
        if key in {"resolved_target_file_id", "target_candidate_rank_trace"} and isinstance(value, str) and value:
            state[key] = value
    return state

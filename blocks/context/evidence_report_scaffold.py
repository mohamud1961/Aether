"""Attach lightweight report-scaffold state to each new observation.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

from typing import Any

from .full_history import append_observation
from .phase65_context_followup_merged import _collect_hints
from .structured_observation_register import apply_structured_observation_register

_REPORT_KEYS = (
    "justification",
    "tool_contract_cases",
    "tool_result_cases",
    "discovery_step_evidence",
    "final_justification_markers",
)


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Preserve canonical report keys so graders can attribute evidence consistently."""
    observation = apply_structured_observation_register(history, new_observation)
    scaffold_state = _extract_report_scaffold(observation)
    if scaffold_state:
        observation["evidence_report_scaffold"] = scaffold_state
    hints = _collect_hints(history, observation)
    if hints:
        existing = observation.get("content")
        prefix = f"[phase65_context_followup_merge] {' | '.join(hints)}"
        observation["content"] = f"{existing}\n\n{prefix}" if isinstance(existing, str) and existing else prefix
    return append_observation(history, observation)


def _extract_report_scaffold(observation: dict[str, Any]) -> dict[str, Any]:
    scaffold: dict[str, Any] = {}
    for key in _REPORT_KEYS:
        value = observation.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            scaffold[key] = dict(value)
            continue
        if isinstance(value, list):
            scaffold[key] = list(value)
            continue
        if isinstance(value, str) and value:
            scaffold[key] = value
    return scaffold

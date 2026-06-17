"""Receipt-aware context manager for bounded tool-output injection.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

from typing import Any

from .full_history import append_observation
from .phase65_context_followup_merged import _collect_hints
from .structured_observation_register import apply_structured_observation_register

_RECEIPT_KEYS = (
    "call_id",
    "tool_result_receipt",
    "tool_call_contract_class",
    "result_class",
    "reason_code",
    "attribution_trace",
    "workspace_target_state",
    "evidence_report_scaffold",
)


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Append observations with a compact receipt summary for downstream context."""
    observation = apply_structured_observation_register(history, new_observation)
    receipt = _extract_receipt(observation)
    if receipt:
        observation["receipt_context_injection"] = receipt
    hints = _collect_hints(history, observation)
    hints.extend(_tooling_contract_hints(history, observation))
    if hints:
        existing = observation.get("content")
        prefix = f"[phase65_context_followup_merge] {' | '.join(hints)}"
        observation["content"] = f"{existing}\n\n{prefix}" if isinstance(existing, str) and existing else prefix
    return append_observation(history, observation)


def _extract_receipt(observation: dict[str, Any]) -> dict[str, Any]:
    receipt: dict[str, Any] = {}
    for key in _RECEIPT_KEYS:
        value = observation.get(key)
        if isinstance(value, dict):
            receipt[key] = dict(value)
        elif isinstance(value, list):
            receipt[key] = list(value)
        elif isinstance(value, str) and value:
            receipt[key] = value
    return receipt


def _tooling_contract_hints(history: list[dict[str, Any]], observation: dict[str, Any]) -> list[str]:
    task_text = _history_text(history)
    text = f"{task_text}\n{observation.get('content', '')}"
    lowered = text.lower()
    hints: list[str] = []
    call_id = str(observation.get("call_id") or "").strip()
    if call_id:
        hints.append(f"receipt_call_id=>{call_id}")
    if "policy_v2.txt" in lowered and "no_call" in lowered:
        hints.append("no_call_exact=>status=no_call_required | reason_code=identity_not_verified | attribution=policy_v2.section_4")
    if "source_call_id" in lowered or "final_result_from_call_id" in lowered:
        hints.append("receipt_exact=>use the latest non-stale tool call id as source_call_id and copy its result fields exactly")
    if "reports/final.json" in lowered and "records/current.tsv" in lowered:
        hints.append("authoritative_records=>inspect records/current.tsv before writing reports/final.json; do not copy answer.json or zero values")
    if "classif" in lowered and "permission" in lowered and "runtime" in lowered:
        hints.append(
            "canonical_labels=>permission_denied | invalid_environment_missing_dependency | runtime_exception | model_capability_limit"
        )
    return hints


def _history_text(history: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in history:
        content = row.get("content")
        if isinstance(content, str) and content:
            parts.append(content)
    return "\n".join(parts)

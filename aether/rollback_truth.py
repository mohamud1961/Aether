from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from .enum_registry import load_enum_registry


@dataclass(frozen=True)
class SideEffectRecord:
    side_effect_scope: str  # WORKSPACE_LOCAL | EXTERNAL
    reversibility: str  # REVERSIBLE | NOT_REVERSIBLE | UNKNOWN
    description: str
    affected_paths: List[str]


def build_side_effect_records(
    *,
    tool_name: str,
    files_written: Sequence[str],
    risk_class: str,
) -> List[SideEffectRecord]:
    if files_written:
        return [
            SideEffectRecord(
                side_effect_scope="WORKSPACE_LOCAL",
                reversibility="REVERSIBLE",
                description=f"{tool_name} modified workspace paths",
                affected_paths=list(files_written),
            )
        ]

    if risk_class == "HIGH":
        return [
            SideEffectRecord(
                side_effect_scope="EXTERNAL",
                reversibility="NOT_REVERSIBLE",
                description=f"{tool_name} may produce external side effects",
                affected_paths=[],
            )
        ]

    return [
        SideEffectRecord(
            side_effect_scope="WORKSPACE_LOCAL",
            reversibility="UNKNOWN",
            description=f"{tool_name} produced no recorded writes",
            affected_paths=[],
        )
    ]


def summarize_side_effects(
    side_effects: Sequence[SideEffectRecord],
) -> tuple[str, str]:
    if not side_effects:
        return "WORKSPACE_LOCAL", "UNKNOWN"

    scope = "WORKSPACE_LOCAL"
    reversibility = "UNKNOWN"
    for effect in side_effects:
        if effect.side_effect_scope == "EXTERNAL":
            scope = "EXTERNAL"
        if effect.reversibility == "NOT_REVERSIBLE":
            reversibility = "NOT_REVERSIBLE"
            break
        if effect.reversibility == "REVERSIBLE":
            reversibility = "REVERSIBLE"
    _validate(scope, reversibility)
    return scope, reversibility


def emit_rollback_limitation_if_needed(
    *,
    event_log,
    timestamp: str,
    cwd: str,
    trigger_code: str,
    reason: str,
) -> Dict[str, Any] | None:
    for event in event_log.events:
        if event.get("event_type") != "TOOL_CALL":
            continue
        if event.get("side_effect_scope") == "EXTERNAL" and event.get("reversibility") == "NOT_REVERSIBLE":
            return event_log.append_event(
                {
                    "event_type": "ROLLBACK_LIMITATION",
                    "timestamp": timestamp,
                    "cwd": cwd,
                    "summary_reason_code": "external_side_effect_rollback_limitation",
                    "trigger_code": trigger_code,
                    "reason": reason,
                    "source_event_id": event.get("event_id"),
                }
            )
    return None


def _validate(scope: str, reversibility: str) -> None:
    registry = load_enum_registry()
    # Reuse existing closed enums if they exist; fail closed on unexpected values.
    if scope not in {"WORKSPACE_LOCAL", "EXTERNAL"}:
        raise ValueError(f"invalid_side_effect_scope:{scope}")
    if reversibility not in {"REVERSIBLE", "NOT_REVERSIBLE", "UNKNOWN"}:
        raise ValueError(f"invalid_reversibility:{reversibility}")
    # Touch registry to maintain closed-enum invariant behavior for this stage.
    _ = registry

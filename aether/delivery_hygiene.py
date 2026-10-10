"""Model-agnostic delivery-hygiene and state-safety context for Solver turns.

HY1 is deliberately advisory/factual.  It never decides that a changed path is
unwanted, never requires a backup unconditionally, and never supplies completion
authority.  The Primary Solver compares these facts/affordances against the raw
user task.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

CONTROL = "control"
DELIVERY_HYGIENE_V1 = "delivery_hygiene_v1"
SUPPORTED_MODES = frozenset({CONTROL, DELIVERY_HYGIENE_V1})

_CHANGED_PATH_KEYS = (
    "created",
    "modified",
    "removed",
    "generated_residue",
    "read",
)


def normalize_mode(value: str | None) -> str:
    mode = str(value or CONTROL).strip().lower()
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported delivery hygiene mode: {value!r}")
    return mode


def _changed_paths(dynamic_state: Mapping[str, Any] | None) -> dict[str, Any]:
    state = dict(dynamic_state or {})
    named = state.get("named_sections")
    named = dict(named) if isinstance(named, Mapping) else {}
    observed = named.get("observed_changed_paths")
    observed = dict(observed) if isinstance(observed, Mapping) else {}
    out: dict[str, Any] = {}
    for key in _CHANGED_PATH_KEYS:
        values = observed.get(key)
        if isinstance(values, (list, tuple)):
            out[key] = sorted({str(item) for item in values if str(item).strip()})
        else:
            out[key] = []
    for key in (
        "task_state_generation",
        "external_state_unknown",
        "latest_mutation_detection_status",
        "content_hash_availability",
    ):
        if key in observed:
            out[key] = deepcopy(observed[key])
    return out


def delivery_hygiene_context(
    dynamic_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return one small factual/advisory HY1 context packet."""
    return {
        "schema": "aether.delivery_hygiene.v1",
        "authority": "primary_solver_against_raw_task_and_observed_reality",
        "observed_changed_paths": _changed_paths(dynamic_state),
        "finish_checklist": (
            "Before finishing, compare the observed changed paths against the raw task. "
            "Remove task-unrequested scratch/debug/temporary artifacts when the raw task "
            "does not require them, and verify task-designated preserved/read-only/input "
            "state was not unintentionally changed."
        ),
        "state_safety_affordance": (
            "Before a destructive overwrite/removal of existing state, when the raw task "
            "requires preservation, rollback, or a safety copy, first capture the current "
            "state with existing read/inspection tools and create the required backup with "
            "existing write/command tools. Do not create a backup merely because this "
            "affordance is present; the raw task decides whether one is appropriate."
        ),
        "semantic_judgment_by_harness": False,
        "completion_veto": False,
    }


__all__ = [
    "CONTROL",
    "DELIVERY_HYGIENE_V1",
    "SUPPORTED_MODES",
    "delivery_hygiene_context",
    "normalize_mode",
]

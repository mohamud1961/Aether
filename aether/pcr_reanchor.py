"""PCR model-facing reality re-anchor projections.

The canonical PCR context remains the kernel authority. This module contains
pure projections used only at the Solver model boundary for explicitly enabled
native-continuity experiments. It never selects actions, changes evidence
custody, changes submission authority, or mutates the canonical packet.

The production projection deliberately keeps the canonical PCR section names.
C3 is a value-compaction experiment, not a second context dialect.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


CURRENT_FULL = "current_full"
REFINED_M = "refined_m"
CONTINUITY_FRESH_DELTA_V1 = "continuity_fresh_delta_v1"
SUPPORTED_REANCHOR_MODES = frozenset({CURRENT_FULL, REFINED_M, CONTINUITY_FRESH_DELTA_V1})


def _compact_identity(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    # Raw task authority is already pinned independently in every Solver prefix.
    # Source/runtime custody hashes remain in canonical kernel/evidence custody.
    keys = (
        "task_id",
        "run_id",
        "primary_agent_id",
        "workspace_id",
        "environment_id",
    )
    return {
        key: deepcopy(value[key])
        for key in keys
        if value.get(key) not in (None, "")
    }


def _compact_budgets(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    keys = (
        "max_kernel_steps",
        "used_solver_provider_turns",
        "remaining_kernel_steps",
    )
    return {key: deepcopy(value[key]) for key in keys if key in value}


def _compact_exact_access(access: Any) -> dict[str, Any]:
    """Preserve exact custody identity while dropping retrieval boilerplate."""
    if not isinstance(access, Mapping):
        return {}
    out: dict[str, Any] = {}
    for key in ("state", "handle", "sha256", "bytes"):
        if key in access and access.get(key) not in (None, ""):
            out[key] = deepcopy(access[key])
    related = access.get("related_handles")
    if isinstance(related, list) and related:
        out["related_handles"] = deepcopy(related)
    return out


def _compact_evidence_row(row: Any) -> Any:
    if not isinstance(row, Mapping):
        return deepcopy(row)
    projected: dict[str, Any] = {}
    for key in (
        "evidence_ref",
        "receipt_id",
        "evidence_type",
        "originating_action_id",
        "mechanical_description",
        "success",
        "state_change",
        "failure_class",
        "step",
        "currentness",
        "completion_evidence_eligible",
    ):
        if key in row:
            projected[key] = deepcopy(row[key])
    exact_access = _compact_exact_access(row.get("exact_access"))
    if exact_access:
        projected["exact_access"] = exact_access
    return projected


def _compact_evidence_index(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    # U intentionally does not perform evidence-row recency deletion. That is a
    # separate future treatment because it can change semantic recovery quality.
    return [_compact_evidence_row(row) for row in value]


def _compact_linked_history(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    # Current external/task reality only. Generic reconstruction history is the
    # native-continuity ablation target.
    keep = (
        "obligation_status",
        "monitor_alerts",
        "live_processes",
        "artifacts_present",
        "planned_checks",
        "pending_checks",
    )
    return {
        key: deepcopy(value[key])
        for key in keep
        if key in value and value[key] not in (None, [], {}, "")
    }


def _compact_mechanical_failure(fact: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: deepcopy(fact[key])
        for key in (
            "kind",
            "receipt_id",
            "receipt_kind",
            "failure_class",
            "summary",
            "step",
            "originating_action_id",
            "resolution_state",
        )
        if key in fact
    }
    exact_access = _compact_exact_access(fact.get("exact_access"))
    if exact_access:
        result["exact_access"] = exact_access
    return result


def _compact_runtime_facts(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    out: list[Any] = []
    for fact in value:
        if not isinstance(fact, Mapping):
            out.append(deepcopy(fact))
            continue
        kind = str(fact.get("kind") or "")
        if kind == "source_custody_gap":
            # Host provenance/admission state remains in immutable canonical
            # custody. It is not task-world reality needed for the next action.
            continue
        if kind == "mechanical_failure":
            out.append(_compact_mechanical_failure(fact))
            continue
        out.append(deepcopy(dict(fact)))
    return out


def _compact_helper(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    current = value.get("current_helpers")
    current_rows = deepcopy(current) if isinstance(current, list) else []
    omitted = int(value.get("omitted_older_helper_count", 0) or 0)
    result: dict[str, Any] = {
        "enabled": bool(value.get("enabled", False)),
        "task_local_dir": str(value.get("task_local_dir") or ""),
        "smoke_test_required": bool(value.get("smoke_test_required", False)),
        "trust_for_completion": bool(value.get("trust_for_completion", False)),
    }
    if current_rows:
        result["current_helpers"] = current_rows
    if omitted:
        result["omitted_older_helper_count"] = omitted
    return result


def refined_m_reanchor(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Project irreducible external reality for native-continuity C3 trials.

    Section names intentionally match the canonical PCR packet. The canonical
    packet itself remains untouched and continues to drive context-budget,
    working-state, submission, evidence, and completion gates.
    """
    out: dict[str, Any] = {
        # Exact immediately previous Aether observation remains fully inline.
        "latest_primary_result": deepcopy(packet.get("latest_primary_result", {})),
        "runtime_identity": _compact_identity(packet.get("runtime_identity")),
        "available_capabilities": deepcopy(packet.get("available_capabilities", {})),
        "budgets": _compact_budgets(packet.get("budgets")),
        "evidence_index": _compact_evidence_index(packet.get("evidence_index")),
        "linked_history": _compact_linked_history(packet.get("linked_history")),
    }
    facts = _compact_runtime_facts(packet.get("unresolved_runtime_facts"))
    if facts:
        out["unresolved_runtime_facts"] = facts
    for key in ("open_completion_findings", "submit_reentry_gate"):
        value = packet.get(key)
        if value not in (None, [], {}, ""):
            out[key] = deepcopy(value)
    helper = _compact_helper(packet.get("self_extension"))
    if helper:
        out["self_extension"] = helper
    # context_budget and reconstruction-only working-state/history metadata are
    # deliberately absent from the model view. The kernel still evaluates the
    # unmodified canonical context_budget before any provider call.
    return out


def continuity_fresh_delta_reanchor(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Project only fresh/current evidence on top of provider-native continuity.

    This is the S6 C1 treatment. It deliberately changes model-visible replay
    only: canonical PCR custody remains untouched. The kernel already labels
    latest action evidence as ``latest_primary_result`` and older completion
    evidence as ``historical_task_evidence``. C1 therefore needs no semantic
    relevance model: it drops only the latter from automatic replay and keeps
    every unknown/new currentness value fail-safe.
    """
    out = refined_m_reanchor(packet)
    rows = packet.get("evidence_index")
    if not isinstance(rows, list):
        out["evidence_index"] = []
        return out
    out["evidence_index"] = [
        _compact_evidence_row(row)
        for row in rows
        if not (
            isinstance(row, Mapping)
            and str(row.get("currentness") or "") == "historical_task_evidence"
        )
    ]
    return out


def project_pcr_context_for_model(
    packet: Mapping[str, Any],
    *,
    mode: str = CURRENT_FULL,
) -> Mapping[str, Any]:
    """Return the model-facing PCR packet without mutating canonical custody."""
    if mode == CURRENT_FULL:
        # Preserve the exact object and serialization in the qualified/default
        # path. U must be a true no-op unless explicitly enabled.
        return packet
    if mode == REFINED_M:
        return refined_m_reanchor(packet)
    if mode == CONTINUITY_FRESH_DELTA_V1:
        return continuity_fresh_delta_reanchor(packet)
    raise ValueError(f"unsupported PCR Solver re-anchor mode: {mode}")

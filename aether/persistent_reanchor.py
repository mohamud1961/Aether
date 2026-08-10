"""PERSISTENT model-facing reality re-anchor projections.

The canonical PERSISTENT context remains the kernel authority. This module contains
pure projections used only at the Solver model boundary for explicitly enabled
native-continuity experiments. It never selects actions, changes evidence
custody, changes submission authority, or mutates the canonical packet.

The production projection deliberately keeps the canonical PERSISTENT section names.
C3 is a value-compaction experiment, not a second context dialect.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


CURRENT_FULL = "current_full"
REFINED_M = "refined_m"
SUPPORTED_REANCHOR_MODES = frozenset({CURRENT_FULL, REFINED_M})


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


def _compact_working_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    # Native continuity owns the cognitive/narrative checkpoint in C3. Stable
    # evidence bindings remain external reality and are kept under the same
    # canonical working_state section name.
    bindings = value.get("evidence_bindings")
    if not isinstance(bindings, Mapping) or not bindings:
        return {}
    return {"evidence_bindings": deepcopy(dict(bindings))}


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

    Section names intentionally match the canonical PERSISTENT packet. The canonical
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
    for key in ("unresolved_verifier_findings", "verifier_reentry_state"):
        value = packet.get(key)
        if value not in (None, [], {}, ""):
            out[key] = deepcopy(value)
    helper = _compact_helper(packet.get("self_extension"))
    if helper:
        out["self_extension"] = helper
    working_state = _compact_working_state(packet.get("working_state"))
    if working_state:
        out["working_state"] = working_state
    # context_budget and reconstruction-only working-state/history metadata are
    # deliberately absent from the model view. The kernel still evaluates the
    # unmodified canonical context_budget before any provider call.
    return out


def project_persistent_context_for_model(
    packet: Mapping[str, Any],
    *,
    mode: str = CURRENT_FULL,
) -> Mapping[str, Any]:
    """Return the model-facing PERSISTENT packet without mutating canonical custody."""
    if mode == CURRENT_FULL:
        # Preserve the exact object and serialization in the qualified/default
        # path. U must be a true no-op unless explicitly enabled.
        return packet
    if mode == REFINED_M:
        return refined_m_reanchor(packet)
    raise ValueError(f"unsupported PERSISTENT Solver re-anchor mode: {mode}")

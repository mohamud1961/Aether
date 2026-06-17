"""Small model-facing working window for the active control-plane route."""

from __future__ import annotations

import json
from typing import Any

from blocks.context.full_history import append_observation

from runner.kernel_control_plane import validate_pinned_invariants
from runner.kernel_evidence_trail import project_evidence_trail_state
from runner.kernel_receipts import compact_receipt_digest, summarize_receipt
from runner.kernel_services import project_service_summary


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    window = observation.pop("control_plane_working_window", None)
    if window is None:
        window = observation.pop("working_window", None)
    if window is None:
        window = observation.pop("evidence_context_pack", None)
    if window is None:
        window = observation.pop("context_pack", None)
    if isinstance(window, dict):
        rendered = render_working_window(window)
        observation.setdefault("role", "system")
        existing = observation.get("content")
        observation["content"] = f"{existing}\n\n[control_plane_working_window]\n{rendered}" if isinstance(existing, str) and existing else f"[control_plane_working_window]\n{rendered}"
    return append_observation(history, observation)


def build_working_window(control_plane: dict[str, Any], kernel_state: Any, *, budget: int) -> dict[str, Any]:
    validation = validate_pinned_invariants(control_plane)
    if validation["status"] != "pass":
        raise ValueError(f"missing pinned invariants: {validation['missing_keys']}")
    receipts = list(getattr(kernel_state, "receipts", []))
    recent_limit = max(1, int(control_plane.get("window_hints", {}).get("recent_receipt_limit", 4) or 4))
    evidence_trail_state = dict(control_plane.get("evidence_trail_state", {}))
    if not evidence_trail_state:
        evidence_trail_state = project_evidence_trail_state(
            list(getattr(kernel_state, "evidence_trail_records", [])),
            success_contract=dict(getattr(kernel_state, "success_contract", {})) if isinstance(getattr(kernel_state, "success_contract", {}), dict) else {},
        )
    for limit in range(recent_limit, 0, -1):
        window = _build_window(
            control_plane,
            kernel_state,
            receipts,
            limit=limit,
            budget=budget,
            evidence_trail_state=evidence_trail_state,
        )
        if estimate_window_size(window) <= budget:
            return window
    return _build_window(
        control_plane,
        kernel_state,
        receipts,
        limit=1,
        budget=budget,
        evidence_trail_state=evidence_trail_state,
    )


def render_working_window(window: dict[str, Any]) -> str:
    compact = json.dumps(window, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    budget = int(window.get("budget_chars") or 6000)
    return compact if len(compact) <= budget else compact[: max(0, budget - 1)] + "…"


def estimate_window_size(window: dict[str, Any]) -> int:
    return len(render_working_window(window))


def _build_window(
    control_plane: dict[str, Any],
    kernel_state: Any,
    receipts: list[dict[str, Any]],
    *,
    limit: int,
    budget: int,
    evidence_trail_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from runner.kernel_compaction import classify_and_compact_receipt
    recent = receipts[-limit:] if limit > 0 else []
    omitted = receipts[: len(receipts) - len(recent)] if recent else list(receipts)
    omitted_ids = [receipt.get("receipt_id") for receipt in omitted if isinstance(receipt, dict) and isinstance(receipt.get("receipt_id"), str)]
    service_summary = project_service_summary(
        dict(getattr(kernel_state, "service_registry", {})),
        dict(getattr(kernel_state, "process_registry", {})),
    )
    evidence_trail_projection = dict(evidence_trail_state or control_plane.get("evidence_trail_state", {}) or {})
    window = {
        "working_window_version": "control_plane_working_window.v1",
        "route_variant_id": str(control_plane.get("route_variant_id") or ""),
        "budget_chars": int(budget),
        "task_contract": dict(control_plane.get("task_contract", {})),
        "success_criteria": dict(control_plane.get("success_criteria", {})),
        "model_contract": dict(control_plane.get("model_contract", {})),
        "model_success_criteria": _string_list(control_plane.get("model_success_criteria")),
        "workspace_contract": dict(control_plane.get("workspace_contract", {})),
        "pinned_invariants": dict(control_plane.get("pinned_invariants", {})),
        "semantic_sideband": _semantic_sideband(control_plane),
        "semantic_state": dict(control_plane.get("semantic_state", {})),
        "plan_state": dict(control_plane.get("plan_state", {})),
        "recent_receipts": [
            classify_and_compact_receipt(receipt, len(receipts), receipts)
            if control_plane.get("route_variant_id") == "model_led_evidence_substrate_v1"
            else summarize_receipt(receipt)
            for receipt in recent
        ],
        "compression": {
            "total_receipt_count": len(receipts),
            "recent_receipt_count": len(recent),
            "omitted_receipt_count": len(omitted),
            "omitted_receipt_digest": compact_receipt_digest(omitted) if omitted else "",
            "omitted_receipt_id_range": [omitted_ids[0], omitted_ids[-1]] if omitted_ids else [],
        },
        "verifier_state": dict(control_plane.get("verifier_state", {})),
        "artifact_state": dict(control_plane.get("artifact_state", {})),
        "provenance_state": dict(control_plane.get("provenance_state", {})),
        "service_state": service_summary,
        "native_tool_state": dict(control_plane.get("native_tool_state", {})),
        "evidence_trail_state": evidence_trail_projection,
        "open_obligations": dict(control_plane.get("open_obligations", {})),
        "service_obligations": dict(control_plane.get("service_obligations", {})),
        "latest_recovery_card": dict(control_plane.get("latest_recovery_card", {})),
        "last_model_compaction_summary": dict(control_plane.get("last_model_compaction_summary", {})),
        "last_model_compaction_summary_status": str(control_plane.get("last_model_compaction_summary_status") or ""),
        "last_model_compaction_summary_source": str(control_plane.get("last_model_compaction_summary_source") or ""),
        "known_failed_attempts": list(control_plane.get("known_failed_attempts", [])),
        "unresolved_contradictions": list(control_plane.get("unresolved_contradictions", [])),
        "raw_trace_pointers": dict(control_plane.get("raw_trace_pointers", {})),
        "control_plane_state_ref": {
            "pinned_invariant_hash": str(control_plane.get("pinned_invariant_hash") or ""),
            "last_compaction_boundary": dict(control_plane.get("last_compaction_boundary", {})),
        },
    }
    window["estimated_window_size"] = len(json.dumps(window, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    window["compression"]["over_budget"] = bool(window["estimated_window_size"] > budget)
    return window


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _semantic_sideband(control_plane: dict[str, Any]) -> dict[str, Any]:
    semantic_state = dict(control_plane.get("semantic_state", {}))
    plan_state = dict(control_plane.get("plan_state", {}))
    return {
        "current_objective": str(plan_state.get("current_objective") or ""),
        "current_step": str(plan_state.get("current_step") or ""),
        "next_action": str(plan_state.get("next_action") or ""),
        "status": str(plan_state.get("status") or ""),
        "summary": str(semantic_state.get("summary") or ""),
        "discoveries": _string_list(semantic_state.get("discoveries")),
        "assumptions": _string_list(semantic_state.get("assumptions")),
        "open_questions": _string_list(semantic_state.get("open_questions")),
        "evidence_notes": _string_list(semantic_state.get("evidence_notes")),
        "hypotheses": _string_list(semantic_state.get("hypotheses")),
        "evidence_targets": _string_list(semantic_state.get("evidence_targets")),
        "candidate_next_checks": _string_list(semantic_state.get("candidate_next_checks")),
        "subtasks": _string_list(semantic_state.get("subtasks")),
        "blocked_reason": str(semantic_state.get("blocked_reason") or ""),
        "confidence": str(semantic_state.get("confidence") or ""),
        "proposed_success_criteria": _string_list(semantic_state.get("proposed_success_criteria")),
        "finish_claim": bool(semantic_state.get("finish_claim")),
        "model_claimed_done": bool(semantic_state.get("model_claimed_done")),
        "interrupt_reason": str(semantic_state.get("interrupt_reason") or ""),
        "replan_requested": bool(semantic_state.get("replan_requested")),
    }

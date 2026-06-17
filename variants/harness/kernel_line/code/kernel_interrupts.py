"""Interrupt and finish-claim helpers for the control-plane route."""

from __future__ import annotations

import json
from typing import Any


def detect_interrupt(control_plane: dict[str, Any], kernel_state: Any, last_step_result: dict[str, Any] | None) -> dict[str, Any]:
    step_result = dict(last_step_result or {})
    completion = step_result.get("completion") if isinstance(step_result.get("completion"), dict) else {}
    semantic_state = _semantic_interrupt_state(control_plane)
    finish_claim = finish_claim_requires_gate(completion, control_plane, kernel_state)
    open_obligations = dict(getattr(kernel_state, "open_obligations", {}))
    repeated_count = int(getattr(kernel_state, "failure_signature_counts", {}).get(getattr(kernel_state, "last_failure_signature", ""), 0) or 0)
    reason = "model_no_progress"
    if finish_claim:
        reason = "completion_claimed"
    elif semantic_state.get("replan_requested"):
        reason = "model_replan_requested"
    elif semantic_state.get("blocked_reason"):
        reason = "model_blocked"
    elif open_obligations.get("service_not_ready"):
        reason = "service_state_ambiguous"
    elif open_obligations.get("process_not_running"):
        reason = "service_state_ambiguous"
    elif open_obligations.get("artifact_gate_missing_paths"):
        reason = "workspace_contract_violation"
    elif open_obligations.get("evidence_trail_missing"):
        reason = "evidence_trail_missing"
    elif repeated_count >= 3:
        reason = "same_failure_repeated"
    elif bool(control_plane.get("workspace_contract", {}).get("cwd")) and str(getattr(kernel_state, "cwd", "")) != str(control_plane.get("workspace_contract", {}).get("cwd")):
        reason = "path_contract_violation"
    budget_chars = int(control_plane.get("window_hints", {}).get("budget_chars", 0) or 0)
    current_size = int(step_result.get("working_window_size") or 0)
    if budget_chars and current_size > budget_chars:
        reason = "token_pressure"
    allowed_decisions = ["continue", "replan", "compact", "block"]
    if finish_claim:
        allowed_decisions.insert(0, "finish")
    return {
        "interrupt": reason != "model_no_progress" or finish_claim,
        "interrupt_reason": reason,
        "finish_claim": finish_claim,
        "finish_gate_required": finish_claim,
        "allowed_decisions": allowed_decisions,
        "open_obligations": open_obligations,
        "known_failed_attempts": list(control_plane.get("known_failed_attempts", [])),
        "semantic_state": semantic_state,
    }


def build_interrupt_packet(interrupt: dict[str, Any], control_plane: dict[str, Any], kernel_state: Any) -> dict[str, Any]:
    interrupt = dict(interrupt or {})
    open_obligations = dict(interrupt.get("open_obligations") or getattr(kernel_state, "open_obligations", {}))
    packet = {
        "interrupt_reason": interrupt.get("interrupt_reason", "model_no_progress"),
        "finish_claim": bool(interrupt.get("finish_claim")),
        "finish_gate_required": bool(interrupt.get("finish_gate_required")),
        "allowed_decisions": list(interrupt.get("allowed_decisions", ["continue", "replan", "compact", "block"])),
        "open_obligations": open_obligations,
        "known_failed_attempts": list(interrupt.get("known_failed_attempts", control_plane.get("known_failed_attempts", []))),
        "pinned_invariant_hash": str(control_plane.get("pinned_invariant_hash") or ""),
        "raw_trace_pointers": dict(control_plane.get("raw_trace_pointers", {})),
        "route_variant_id": str(control_plane.get("route_variant_id") or ""),
        "semantic_state": dict(interrupt.get("semantic_state") or _semantic_interrupt_state(control_plane)),
    }
    if interrupt.get("finish_claim"):
        packet["allowed_decisions"] = ["finish", *[decision for decision in packet["allowed_decisions"] if decision != "finish"]]
    return packet


def finish_claim_requires_gate(completion: dict[str, Any] | None, control_plane: dict[str, Any], kernel_state: Any) -> bool:
    if not isinstance(completion, dict):
        return False
    direct = _structured_finish_claim(completion)
    if isinstance(direct, bool):
        return direct
    _ = control_plane, kernel_state
    return False


def _structured_finish_claim(payload: dict[str, Any]) -> bool | None:
    for key in ("finish_claim", "model_claimed_done"):
        if isinstance(payload.get(key), bool):
            return bool(payload.get(key))
    for wrapper_key in ("control_plane_update", "semantic_state_update"):
        wrapper = payload.get(wrapper_key)
        if isinstance(wrapper, dict):
            for key in ("finish_claim", "model_claimed_done"):
                if isinstance(wrapper.get(key), bool):
                    return bool(wrapper.get(key))
            semantic_state = wrapper.get("semantic_state")
            if isinstance(semantic_state, dict):
                for key in ("finish_claim", "model_claimed_done"):
                    if isinstance(semantic_state.get(key), bool):
                        return bool(semantic_state.get(key))
    text = str(payload.get("text") or "").strip()
    if not text:
        return None
    parsed = _parse_json_like_text(text)
    if isinstance(parsed, dict):
        for key in ("finish_claim", "model_claimed_done"):
            if isinstance(parsed.get(key), bool):
                return bool(parsed.get(key))
        for wrapper_key in ("control_plane_update", "semantic_state_update"):
            wrapper = parsed.get(wrapper_key)
            if isinstance(wrapper, dict):
                for key in ("finish_claim", "model_claimed_done"):
                    if isinstance(wrapper.get(key), bool):
                        return bool(wrapper.get(key))
                semantic_state = wrapper.get("semantic_state")
                if isinstance(semantic_state, dict):
                    for key in ("finish_claim", "model_claimed_done"):
                        if isinstance(semantic_state.get(key), bool):
                            return bool(semantic_state.get(key))
    return None


def _semantic_interrupt_state(control_plane: dict[str, Any]) -> dict[str, Any]:
    semantic_state = dict(control_plane.get("semantic_state", {}))
    return {
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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _parse_json_like_text(text: str) -> Any:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    if candidate.startswith("```"):
        candidate = "\n".join(line for line in candidate.splitlines() if not line.startswith("```")).strip()
    try:
        return json.loads(candidate)
    except Exception:
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except Exception:
            return None
    return None

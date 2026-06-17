"""External control-plane state for the active evidence kernel."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from runner.kernel_services import project_service_summary

CONTROL_PLANE_VERSION = "active_evidence_kernel_control_plane.v1"
MODEL_UPDATE_VERSION = "active_evidence_kernel_control_plane_update.v1"
REQUIRED_PINNED_KEYS = (
    "task_prompt",
    "success_criteria",
    "workspace_contract",
    "verifier_state",
    "artifact_state",
    "known_failed_attempts",
    "open_obligations",
    "service_obligations",
    "tool_contract_state",
    "latest_recovery_card",
    "unresolved_contradictions",
    "raw_trace_pointers",
)
MODEL_PLAN_KEYS = ("current_objective", "current_step", "next_action", "active_plan", "status")
MODEL_SEMANTIC_KEYS = (
    "summary",
    "discoveries",
    "assumptions",
    "open_questions",
    "evidence_notes",
    "hypotheses",
    "evidence_targets",
    "candidate_next_checks",
    "subtasks",
    "blocked_reason",
    "confidence",
    "proposed_success_criteria",
    "finish_claim",
    "model_claimed_done",
    "interrupt_reason",
    "replan_requested",
)
MODEL_SEMANTIC_LIST_KEYS = (
    "discoveries",
    "assumptions",
    "open_questions",
    "evidence_notes",
    "hypotheses",
    "evidence_targets",
    "candidate_next_checks",
    "subtasks",
    "proposed_success_criteria",
)
MODEL_SEMANTIC_TEXT_KEYS = ("summary", "blocked_reason", "confidence", "interrupt_reason")
MODEL_SEMANTIC_BOOL_KEYS = ("finish_claim", "model_claimed_done", "replan_requested")
MODEL_ALIAS_KEYS = (
    "summary",
    "discoveries",
    "assumptions",
    "open_questions",
    "evidence_notes",
    "hypotheses",
    "evidence_targets",
    "candidate_next_checks",
    "subtasks",
    "blocked_reason",
    "confidence",
    "proposed_success_criteria",
    "success_criteria_delta",
    "current_objective",
    "current_step",
    "next_action",
    "active_plan",
    "status",
    "finish_claim",
    "model_claimed_done",
    "interrupt_reason",
    "replan_requested",
    "model_success_criteria",
)
PROTECTED_MODEL_UPDATE_KEYS = set(
    (
        "task_prompt",
        "task_contract",
        "success_criteria",
        "workspace_contract",
        "verifier_state",
        "artifact_state",
        "provenance_state",
        "service_state",
        "native_tool_state",
        "evidence_trail_state",
        "open_obligations",
        "service_obligations",
        "tool_contract_state",
        "known_failed_attempts",
        "latest_recovery_card",
        "unresolved_contradictions",
        "raw_trace_pointers",
        "pinned_invariants",
        "pinned_invariant_hash",
        "route_variant_id",
        "route_manifest_fingerprint",
        "control_plane_version",
        "window_hints",
        "compact_boundaries",
        "last_compaction_boundary",
        "last_model_update_receipt_id",
        "model_contract",
    )
)


def initialize_control_plane(kernel_state: Any, task_prompt: str, workspace_state: dict[str, Any] | None, route_manifest: dict[str, Any] | None) -> dict[str, Any]:
    control_plane = {
        "control_plane_version": CONTROL_PLANE_VERSION,
        "route_variant_id": str((route_manifest or {}).get("variant_id") or ""),
        "route_manifest_fingerprint": str((route_manifest or {}).get("route_manifest_fingerprint") or ""),
        "task_prompt": str(task_prompt or getattr(kernel_state, "task_prompt", "")),
        "model_contract": _model_contract(task_prompt, route_manifest),
        "task_contract": {
            "task_id": str(getattr(kernel_state, "task_id", "")),
            "task_prompt": str(task_prompt or getattr(kernel_state, "task_prompt", "")),
            "run_id": str(getattr(kernel_state, "run_id", "")),
        },
        "success_criteria": _success_criteria(task_prompt, workspace_state),
        "model_success_criteria": [],
        "workspace_contract": _workspace_contract(kernel_state, workspace_state),
        "plan_state": _plan_state(task_prompt),
        "semantic_state": _semantic_state(),
        "compact_boundaries": [],
        "last_compaction_boundary": {},
        "window_hints": {
            "budget_chars": int((workspace_state or {}).get("control_plane_budget_chars") or 6000),
            "recent_receipt_limit": int((workspace_state or {}).get("control_plane_recent_receipt_limit") or 4),
        },
        "last_model_update_receipt_id": "",
        "last_model_compaction_summary": {},
        "last_model_compaction_summary_status": "none",
        "last_model_compaction_summary_source": "",
    }
    return refresh_from_kernel_state(control_plane, kernel_state, workspace_state or {})


def apply_model_state_update(control_plane: dict[str, Any], update: dict[str, Any], *, receipt_id: str | None = None) -> dict[str, Any]:
    if not isinstance(control_plane, dict):
        return {"status": "rejected", "reason_codes": ["invalid_control_plane"]}
    if not isinstance(update, dict):
        return {"status": "rejected", "reason_codes": ["invalid_update_shape"]}
    normalized = _normalize_model_update(update)
    if normalized is None:
        return {"status": "rejected", "reason_codes": ["invalid_update_shape"]}
    next_control_plane = copy.deepcopy(control_plane)
    pinned_invariants = dict(next_control_plane.get("pinned_invariants", {}))
    rejected: list[str] = _reject_protected_model_keys(normalized, pinned_invariants)
    if rejected:
        return {"status": "rejected", "reason_codes": ["pinned_invariant_update_blocked", *sorted(rejected)]}
    semantic_state = dict(next_control_plane.get("semantic_state", {}))
    plan_state = dict(next_control_plane.get("plan_state", {}))
    semantic_update = dict(normalized.get("semantic_state", {}))
    plan_update = dict(normalized.get("plan_state", {}))
    semantic_state.update(semantic_update)
    plan_state.update(plan_update)
    if "model_success_criteria" in normalized:
        proposed = _string_list(normalized.get("model_success_criteria"))
        if proposed:
            next_control_plane["model_success_criteria"] = proposed
            semantic_state["proposed_success_criteria"] = list(proposed)
    if "finish_claim" in normalized:
        semantic_state["finish_claim"] = bool(normalized.get("finish_claim"))
        semantic_state["model_claimed_done"] = bool(normalized.get("finish_claim")) or bool(normalized.get("model_claimed_done"))
    if "model_claimed_done" in normalized:
        semantic_state["model_claimed_done"] = bool(normalized.get("model_claimed_done"))
    if "interrupt_reason" in normalized:
        semantic_state["interrupt_reason"] = str(normalized.get("interrupt_reason") or "")
    if "summary" in normalized:
        semantic_state["summary"] = str(normalized.get("summary") or "")
    if "discoveries" in normalized:
        semantic_state["discoveries"] = _string_list(normalized.get("discoveries"))
    if "assumptions" in normalized:
        semantic_state["assumptions"] = _string_list(normalized.get("assumptions"))
    if "open_questions" in normalized:
        semantic_state["open_questions"] = _string_list(normalized.get("open_questions"))
    if "evidence_notes" in normalized:
        semantic_state["evidence_notes"] = _string_list(normalized.get("evidence_notes"))
    if bool(semantic_state.get("finish_claim")) and not str(semantic_state.get("interrupt_reason") or ""):
        semantic_state["interrupt_reason"] = "finish_claim"
    elif bool(semantic_state.get("replan_requested")) and not str(semantic_state.get("interrupt_reason") or ""):
        semantic_state["interrupt_reason"] = "replan_requested"
    elif str(semantic_state.get("blocked_reason") or "") and not str(semantic_state.get("interrupt_reason") or ""):
        semantic_state["interrupt_reason"] = "model_blocked"
    if "current_objective" in normalized:
        plan_state["current_objective"] = str(normalized.get("current_objective") or plan_state.get("current_objective") or "")
    if "current_step" in normalized:
        plan_state["current_step"] = str(normalized.get("current_step") or "")
    if "next_action" in normalized:
        plan_state["next_action"] = str(normalized.get("next_action") or "")
    if "active_plan" in normalized:
        plan_state["active_plan"] = _string_list(normalized.get("active_plan"))
    if "status" in normalized:
        plan_state["status"] = str(normalized.get("status") or plan_state.get("status") or "")
    if bool(semantic_state.get("finish_claim")):
        semantic_state["model_claimed_done"] = True
    next_control_plane["semantic_state"] = semantic_state
    next_control_plane["plan_state"] = plan_state
    if receipt_id:
        next_control_plane["last_model_update_receipt_id"] = receipt_id
    next_control_plane["pinned_invariants"] = _pinned_invariants(next_control_plane)
    validation = validate_pinned_invariants(next_control_plane)
    if validation["status"] != "pass":
        return {"status": "rejected", "reason_codes": ["pinned_invariant_validation_failed", *validation["missing_keys"]]}
    next_control_plane["pinned_invariant_hash"] = validation["pinned_invariant_hash"]
    return {"status": "accepted", "reason_codes": [], "control_plane": next_control_plane}


def refresh_from_kernel_state(control_plane: dict[str, Any], kernel_state: Any, workspace_state: dict[str, Any] | None) -> dict[str, Any]:
    next_control_plane = copy.deepcopy(control_plane or {})
    workspace_state = dict(workspace_state or {})
    next_control_plane["task_contract"] = _task_contract(kernel_state, workspace_state, next_control_plane)
    next_control_plane["task_prompt"] = str(next_control_plane["task_contract"].get("task_prompt") or "")
    next_control_plane["model_contract"] = _model_contract(next_control_plane["task_prompt"], {"variant_id": next_control_plane.get("route_variant_id", "")})
    next_control_plane["success_criteria"] = _success_criteria(next_control_plane["task_contract"]["task_prompt"], workspace_state)
    next_control_plane["workspace_contract"] = _workspace_contract(kernel_state, workspace_state)
    next_control_plane["verifier_state"] = dict(getattr(kernel_state, "verifier_status", {}))
    next_control_plane["artifact_state"] = dict(getattr(kernel_state, "artifact_gate", {}))
    next_control_plane["provenance_state"] = dict(getattr(kernel_state, "provenance_status", {}))
    next_control_plane["service_state"] = project_service_summary(
        dict(getattr(kernel_state, "service_registry", {})),
        dict(getattr(kernel_state, "process_registry", {})),
    )
    next_control_plane["native_tool_state"] = dict(getattr(kernel_state, "native_tool_state", {}))
    next_control_plane["evidence_trail_state"] = dict(getattr(kernel_state, "evidence_trail_state", {}))
    next_control_plane["open_obligations"] = dict(getattr(kernel_state, "open_obligations", {}))
    next_control_plane["service_obligations"] = {
        "service_not_ready": list(next_control_plane["open_obligations"].get("service_not_ready", []))
        if isinstance(next_control_plane["open_obligations"].get("service_not_ready"), list)
        else [],
        "process_not_running": list(next_control_plane["open_obligations"].get("process_not_running", []))
        if isinstance(next_control_plane["open_obligations"].get("process_not_running"), list)
        else [],
    }
    next_control_plane["tool_contract_state"] = _tool_contract_state(kernel_state)
    next_control_plane["known_failed_attempts"] = _known_failed_attempts(kernel_state)
    next_control_plane["latest_recovery_card"] = dict(getattr(kernel_state, "recovery_card", {}))
    next_control_plane["unresolved_contradictions"] = _string_list(
        workspace_state.get("unresolved_contradictions") or next_control_plane.get("unresolved_contradictions", [])
    )
    next_control_plane["raw_trace_pointers"] = _raw_trace_pointers(next_control_plane)
    next_control_plane["pinned_invariants"] = _pinned_invariants(next_control_plane)
    validation = validate_pinned_invariants(next_control_plane)
    next_control_plane["pinned_invariant_hash"] = validation.get("pinned_invariant_hash", "")
    next_control_plane["validation"] = validation
    return next_control_plane


def validate_pinned_invariants(control_plane: dict[str, Any]) -> dict[str, Any]:
    pinned = dict(control_plane.get("pinned_invariants", {})) if isinstance(control_plane, dict) else {}
    missing = [key for key in REQUIRED_PINNED_KEYS if key not in pinned]
    task_prompt = str(pinned.get("task_prompt") or "")
    workspace_contract = pinned.get("workspace_contract") if isinstance(pinned.get("workspace_contract"), dict) else {}
    if not task_prompt:
        missing.append("task_prompt")
    if not isinstance(pinned.get("success_criteria"), dict):
        missing.append("success_criteria")
    if not isinstance(workspace_contract, dict) or not str(workspace_contract.get("cwd") or "") or not str(workspace_contract.get("workspace_root") or ""):
        missing.append("workspace_contract")
    if not isinstance(pinned.get("raw_trace_pointers"), dict) or not pinned.get("raw_trace_pointers"):
        missing.append("raw_trace_pointers")
    status = "pass" if not missing else "fail"
    return {
        "status": status,
        "missing_keys": _dedupe(missing),
        "pinned_invariant_hash": _stable_hash(pinned),
    }


def export_control_plane_artifacts(control_plane: dict[str, Any], artifact_dir: str | Path) -> dict[str, str]:
    artifact_root = Path(artifact_dir)
    artifact_root.mkdir(parents=True, exist_ok=True)
    refs = {"control_plane_state": str(_write_json(artifact_root / "control_plane_state.json", control_plane))}
    window = control_plane.get("last_working_window")
    if isinstance(window, dict):
        refs["control_plane_working_window"] = str(_write_json(artifact_root / "control_plane_working_window.json", window))
    boundary = control_plane.get("last_compaction_boundary")
    if isinstance(boundary, dict) and boundary:
        refs["control_plane_compaction_boundary"] = str(_write_json(artifact_root / "control_plane_compaction_boundary.json", boundary))
    return refs


def _task_contract(kernel_state: Any, workspace_state: dict[str, Any], control_plane: dict[str, Any]) -> dict[str, Any]:
    task_prompt = str(workspace_state.get("task_prompt") or getattr(kernel_state, "task_prompt", "") or control_plane.get("task_contract", {}).get("task_prompt", ""))
    return {
        "task_id": str(getattr(kernel_state, "task_id", "")),
        "task_prompt": task_prompt,
        "run_id": str(getattr(kernel_state, "run_id", "")),
    }


def _workspace_contract(kernel_state: Any, workspace_state: dict[str, Any]) -> dict[str, Any]:
    cwd = str(workspace_state.get("cwd") or getattr(kernel_state, "cwd", "") or "")
    workspace_root = str(workspace_state.get("workspace_root") or getattr(kernel_state, "workspace_root", "") or cwd)
    required_artifact_paths = _string_list(workspace_state.get("required_artifact_paths") or list(getattr(kernel_state, "artifact_gate", {}).get("required_paths", [])))
    return {
        "cwd": cwd,
        "workspace_root": workspace_root,
        "canonical_workspace_root": str(workspace_state.get("canonical_workspace_root") or workspace_root),
        "required_artifact_paths": required_artifact_paths,
    }


def _plan_state(task_prompt: str) -> dict[str, Any]:
    return {"current_objective": task_prompt, "current_step": "", "next_action": "continue", "active_plan": [], "status": "running"}


def _semantic_state() -> dict[str, Any]:
    return {
        "summary": "",
        "discoveries": [],
        "assumptions": [],
        "open_questions": [],
        "evidence_notes": [],
        "hypotheses": [],
        "evidence_targets": [],
        "candidate_next_checks": [],
        "subtasks": [],
        "blocked_reason": "",
        "confidence": "",
        "proposed_success_criteria": [],
        "finish_claim": False,
        "model_claimed_done": False,
        "interrupt_reason": "",
        "replan_requested": False,
    }


def _tool_contract_state(kernel_state: Any) -> dict[str, Any]:
    native_tool_state = dict(getattr(kernel_state, "native_tool_state", {}))
    return {
        "mode": native_tool_state.get("mode", "shell_only"),
        "runtime_status": native_tool_state.get("runtime_status", "native_tool_runtime_unknown"),
        "contract_status": native_tool_state.get("contract_status", "not_run"),
        "declared_tool_names": list(getattr(kernel_state, "declared_tool_names", [])),
        "declared_tool_schemas": dict(getattr(kernel_state, "declared_tool_schemas", {})),
    }


def _known_failed_attempts(kernel_state: Any) -> list[dict[str, Any]]:
    counts = dict(getattr(kernel_state, "failure_signature_counts", {}))
    return [{"failure_signature": signature, "count": int(count)} for signature, count in sorted(counts.items())]


def _raw_trace_pointers(control_plane: dict[str, Any]) -> dict[str, str]:
    return {
        "run_events": "run_events.jsonl",
        "route_manifest": "route_manifest.json",
        "control_plane_state": "control_plane_state.json",
        "control_plane_working_window": "control_plane_working_window.json",
        "control_plane_compaction_boundary": "control_plane_compaction_boundary.json",
        "variant_id": str(control_plane.get("route_variant_id") or ""),
    }


def _success_criteria(task_prompt: str, workspace_state: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "summary": "Complete through governed finish only after artifact, verifier, provenance, service, and tool-contract evidence is fresh.",
        "governed_finish_required": True,
        "task_prompt_echo": str(task_prompt or (workspace_state or {}).get("task_prompt") or ""),
    }


def _model_contract(task_prompt: str, route_manifest: dict[str, Any] | None) -> dict[str, Any]:
    route_variant_id = str((route_manifest or {}).get("variant_id") or "")
    return {
        "model_contract_version": MODEL_UPDATE_VERSION,
        "route_variant_id": route_variant_id,
        "authority_split": {
            "kernel_owned_truth": [
                "task_prompt",
                "success_criteria",
                "workspace_contract",
                "verifier_state",
                "artifact_state",
                "provenance_state",
                "service_state",
                "native_tool_state",
                "open_obligations",
                "service_obligations",
                "tool_contract_state",
                "known_failed_attempts",
                "latest_recovery_card",
                "unresolved_contradictions",
                "raw_trace_pointers",
            ],
            "model_owned_proposals": [
                "plan_state.current_objective",
                "plan_state.current_step",
                "plan_state.next_action",
                "plan_state.active_plan",
                "semantic_state.summary",
                "semantic_state.discoveries",
                "semantic_state.assumptions",
                "semantic_state.open_questions",
                "semantic_state.evidence_notes",
                "semantic_state.hypotheses",
                "semantic_state.evidence_targets",
                "semantic_state.candidate_next_checks",
                "semantic_state.subtasks",
                "semantic_state.blocked_reason",
                "semantic_state.confidence",
                "semantic_state.proposed_success_criteria",
                "semantic_state.finish_claim",
                "semantic_state.model_claimed_done",
                "semantic_state.interrupt_reason",
                "semantic_state.replan_requested",
            ],
            "kernel_pinned_success_criteria": True,
            "model_proposed_success_criteria_storage": "model_success_criteria",
        },
        "model_guidance": [
            "Use control_plane_update or semantic_state_update when you have structured semantic progress to share.",
            "Use plan_state for the immediate step sequence and semantic_state for the wider work layer: hypotheses, evidence_targets, candidate_next_checks, subtasks, discoveries, open_questions, evidence_notes, blocked_reason, confidence, proposed_success_criteria, finish_claim, model_claimed_done, interrupt_reason, and replan_requested.",
            "Do not mutate kernel-owned truth, pinned invariants, or verifier/artifact/service state.",
            "Finish claims must be explicit booleans; text-only finish language is ignored.",
        ],
        "update_protocol": {
            "accepted_wrappers": ["control_plane_update", "semantic_state_update"],
            "top_level_aliases": list(MODEL_ALIAS_KEYS),
        },
        "accepted_update_shape": {
            "control_plane_update": {
                "plan_state": _plan_state_schema(),
                "semantic_state": _semantic_state_schema(),
            }
        },
        "finish_claim_policy": {
            "explicit_boolean_required": True,
            "accepted_fields": ["finish_claim", "model_claimed_done"],
            "text_only_claims_rejected": True,
        },
        "compaction_policy": {
            "semantic_summary_allowed": True,
            "summary_must_stay_separate_from_kernel_truth": True,
            "deterministic_fallback_required": True,
        },
        "task_prompt_echo": str(task_prompt or ""),
    }


def render_model_contract(task_prompt: str, route_manifest: dict[str, Any] | None) -> str:
    contract = _model_contract(task_prompt, route_manifest)
    return json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def extract_model_state_update(completion: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(completion, dict):
        return None
    for key in ("control_plane_update", "semantic_state_update"):
        value = completion.get(key)
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            parsed = _parse_json_like_object(value)
            if isinstance(parsed, dict):
                return _unwrap_model_update(parsed)
    text = completion.get("text")
    if isinstance(text, str) and text:
        parsed = _parse_json_like_object(text)
        if isinstance(parsed, dict):
            return _unwrap_model_update(parsed)
    return None


def _unwrap_model_update(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("control_plane_update"), dict):
        return dict(payload["control_plane_update"])
    if isinstance(payload.get("semantic_state_update"), dict):
        return dict(payload["semantic_state_update"])
    return dict(payload)


def _normalize_model_update(update: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(update, dict):
        return None
    payload = dict(update)
    for wrapper_key in ("control_plane_update", "semantic_state_update"):
        if wrapper_key in payload:
            wrapper_value = payload.pop(wrapper_key)
            if not isinstance(wrapper_value, dict):
                return None
            payload.update(dict(wrapper_value))
    normalized: dict[str, Any] = {}
    if "plan_state" in payload:
        if not isinstance(payload["plan_state"], dict):
            return None
        plan_section = dict(payload["plan_state"])
        unknown_plan_keys = [key for key in plan_section if key not in MODEL_PLAN_KEYS]
        if unknown_plan_keys:
            normalized.setdefault("unknown_keys", []).extend(f"plan_state.{key}" for key in unknown_plan_keys)
        normalized["plan_state"] = {key: value for key, value in plan_section.items() if key in MODEL_PLAN_KEYS}
    if "semantic_state" in payload:
        if not isinstance(payload["semantic_state"], dict):
            return None
        semantic_section = dict(payload["semantic_state"])
        unknown_semantic_keys = [key for key in semantic_section if key not in MODEL_SEMANTIC_KEYS]
        if unknown_semantic_keys:
            normalized.setdefault("unknown_keys", []).extend(f"semantic_state.{key}" for key in unknown_semantic_keys)
        normalized["semantic_state"] = {
            key: _normalize_semantic_value(key, value)
            for key, value in semantic_section.items()
            if key in MODEL_SEMANTIC_KEYS
        }
        if "proposed_success_criteria" in semantic_section and "model_success_criteria" not in normalized:
            normalized["model_success_criteria"] = _string_list(semantic_section["proposed_success_criteria"])
    for key in MODEL_PLAN_KEYS:
        if key in payload:
            normalized.setdefault("plan_state", {})[key] = payload[key]
    for key in MODEL_SEMANTIC_KEYS:
        if key in payload:
            normalized.setdefault("semantic_state", {})[key] = _normalize_semantic_value(key, payload[key])
    if "success_criteria_delta" in payload:
        normalized["model_success_criteria"] = _string_list(payload["success_criteria_delta"])
    if "model_success_criteria" in payload:
        normalized["model_success_criteria"] = _string_list(payload["model_success_criteria"])
    # Preserve explicit top-level model proposals that are not nested into sections.
    if "proposed_success_criteria" in payload and "model_success_criteria" not in normalized:
        normalized["model_success_criteria"] = _string_list(payload["proposed_success_criteria"])
    if "finish_claim" in payload:
        normalized["finish_claim"] = bool(payload["finish_claim"])
    if "model_claimed_done" in payload:
        normalized["model_claimed_done"] = bool(payload["model_claimed_done"])
    if "interrupt_reason" in payload:
        normalized["interrupt_reason"] = str(payload["interrupt_reason"] or "")
    if "summary" in payload:
        normalized["summary"] = str(payload["summary"] or "")
    if "discoveries" in payload:
        normalized["discoveries"] = _string_list(payload["discoveries"])
    if "assumptions" in payload:
        normalized["assumptions"] = _string_list(payload["assumptions"])
    if "open_questions" in payload:
        normalized["open_questions"] = _string_list(payload["open_questions"])
    if "evidence_notes" in payload:
        normalized["evidence_notes"] = _string_list(payload["evidence_notes"])
    if "current_objective" in payload:
        normalized["current_objective"] = str(payload["current_objective"] or "")
    if "current_step" in payload:
        normalized["current_step"] = str(payload["current_step"] or "")
    if "next_action" in payload:
        normalized["next_action"] = str(payload["next_action"] or "")
    if "active_plan" in payload:
        normalized["active_plan"] = _string_list(payload["active_plan"])
    if "status" in payload:
        normalized["status"] = str(payload["status"] or "")
    # Unknown top-level keys are rejected rather than silently ignored.
    unknown_keys = [key for key in payload.keys() if key not in MODEL_ALIAS_KEYS and key not in {"plan_state", "semantic_state"}]
    if unknown_keys:
        normalized["unknown_keys"] = unknown_keys
    return normalized


def _reject_protected_model_keys(update: dict[str, Any], pinned_invariants: dict[str, Any]) -> list[str]:
    rejected: list[str] = []
    unknown_keys = update.get("unknown_keys")
    if isinstance(unknown_keys, list):
        rejected.extend(str(key) for key in unknown_keys if isinstance(key, str) and key)
    for key in PROTECTED_MODEL_UPDATE_KEYS:
        if key in update:
            rejected.append(key)
    semantic_state = update.get("semantic_state") if isinstance(update.get("semantic_state"), dict) else {}
    plan_state = update.get("plan_state") if isinstance(update.get("plan_state"), dict) else {}
    for key in PROTECTED_MODEL_UPDATE_KEYS:
        if key in semantic_state or key in plan_state:
            rejected.append(key)
    for key, value in pinned_invariants.items():
        if key in update and update[key] != value:
            rejected.append(key)
        if key in semantic_state and semantic_state[key] != value:
            rejected.append(key)
        if key in plan_state and plan_state[key] != value:
            rejected.append(key)
    return _dedupe(rejected)


def _parse_json_like_object(text: str) -> Any:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    if candidate.startswith("```"):
        stripped_lines = [line for line in candidate.splitlines() if not line.startswith("```")]
        candidate = "\n".join(stripped_lines).strip()
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


def _pinned_invariants(control_plane: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(control_plane.get(key)) for key in REQUIRED_PINNED_KEYS}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _plan_state_schema() -> dict[str, str]:
    return {
        "current_objective": "<string>",
        "current_step": "<string>",
        "next_action": "<string>",
        "active_plan": "<list of strings>",
        "status": "<string>",
    }


def _semantic_state_schema() -> dict[str, str]:
    schema = {
        "summary": "<string>",
        "discoveries": "<list of strings>",
        "assumptions": "<list of strings>",
        "open_questions": "<list of strings>",
        "evidence_notes": "<list of strings>",
        "hypotheses": "<list of strings>",
        "evidence_targets": "<list of strings>",
        "candidate_next_checks": "<list of strings>",
        "subtasks": "<list of strings>",
        "blocked_reason": "<string>",
        "confidence": "<string>",
        "proposed_success_criteria": "<list of strings>",
        "finish_claim": "<boolean>",
        "model_claimed_done": "<boolean>",
        "interrupt_reason": "<string>",
        "replan_requested": "<boolean>",
    }
    return schema


def _normalize_semantic_value(key: str, value: Any) -> Any:
    if key in MODEL_SEMANTIC_LIST_KEYS:
        return _string_list(value)
    if key in MODEL_SEMANTIC_BOOL_KEYS:
        return bool(value)
    if key in MODEL_SEMANTIC_TEXT_KEYS:
        return str(value or "")
    return value


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

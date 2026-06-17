"""Lean Cockpit v1 for MLPCP v2.

Purpose:
- Keep the full audit/control state inside the harness.
- Show the model a compact operating dashboard.
- Orient the model with known state, unresolved requirements, evidence refs,
  and already-known evidence.
- Preserve agency: no "you must write now" forcing language.
- Prevent waste: repeated same-action/same-state work is shown as already-known
  evidence and dedup-mirrored by the executor.

This is a formatter layer, not a control system.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


COERCIVE_PHRASES = (
    "next useful action must",
    "next action must write",
    "must create the required artifact",
    "do not continue generic inspection",
    "forced strategic pivot",
)

DEFAULT_TOOL_HINTS = {
    "write_file": "create or replace files such as required artifacts",
    "raw_bash": "run shell commands, compile, execute checks, or inspect specific implementation-critical details",
    "read_file": "read a specific visible file",
    "search_files": "find visible files when the target is not already known",
    "view_receipt": "retrieve prior command/file output by receipt id instead of repeating work",
    "search_receipts": "search prior evidence instead of rerunning equivalent commands",
    "run_verifier": "run visible/verifier checks when available",
    "probe_service": "measure service readiness when the task requires a service",
}


@dataclass
class LeanCockpit:
    cockpit_version: str = "lean_cockpit.v1"
    step: int | None = None
    mode: str = "execute"
    objective: str = ""
    known_state: dict[str, Any] = field(default_factory=dict)
    current_focus: dict[str, Any] = field(default_factory=dict)
    unresolved_requirements: list[dict[str, Any]] = field(default_factory=list)
    workspace_state: dict[str, Any] = field(default_factory=dict)
    evidence_state: dict[str, Any] = field(default_factory=dict)
    working_checklist: dict[str, Any] = field(default_factory=dict)
    recent_progress: dict[str, Any] = field(default_factory=dict)
    already_known_evidence: list[dict[str, Any]] = field(default_factory=list)
    available_tools: dict[str, str] = field(default_factory=dict)
    verification_state: dict[str, Any] = field(default_factory=dict)
    memory_refs: dict[str, Any] = field(default_factory=dict)
    finalization_boundary: dict[str, Any] = field(default_factory=dict)
    retrieval_hint: str = "Use view_receipt/search_receipts for details instead of repeating equivalent work."

    def to_dict(self) -> dict[str, Any]:
        return {
            "cockpit_version": self.cockpit_version,
            "step": self.step,
            "mode": self.mode,
            "objective": self.objective,
            "known_state": self.known_state,
            "current_focus": self.current_focus,
            "unresolved_requirements": self.unresolved_requirements,
            "workspace_state": self.workspace_state,
            "evidence_state": self.evidence_state,
            "working_checklist": self.working_checklist,
            "recent_progress": self.recent_progress,
            "already_known_evidence": self.already_known_evidence,
            "available_tools": self.available_tools,
            "verification_state": self.verification_state,
            "memory_refs": self.memory_refs,
            "finalization_boundary": self.finalization_boundary,
            "retrieval_hint": self.retrieval_hint,
            "formatter_policy": {
                "full_state_retained_in_harness": True,
                "model_visible_context_is_lean": True,
                "already_known_evidence_is_a_reminder_not_a_hard_force_gate": True,
                "same_action_same_state_should_be_dedup_mirrored_not_reexecuted": True,
                "same_action_after_state_change_is_allowed": True,
                "more_specific_followup_is_allowed": True,
            },
        }


def _safe_str(value: Any, limit: int = 500) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str, sort_keys=True)
        except Exception:
            text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        try:
            out = value.to_dict()
            return out if isinstance(out, dict) else {}
        except Exception:
            return {}
    return {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _collect_refs(value: Any, *, limit: int = 12) -> list[str]:
    refs: list[str] = []

    def walk(v: Any) -> None:
        if len(refs) >= limit:
            return
        if isinstance(v, dict):
            if "ref_id" in v:
                ref_type = v.get("ref_type") or "ref"
                refs.append(f"{ref_type}:{v.get('ref_id')}")
                return
            for item in v.values():
                walk(item)
        elif isinstance(v, list):
            for item in v:
                walk(item)
        elif isinstance(v, str):
            for m in re.finditer(r"(?:receipt|artifact|file|lock):[A-Za-z0-9_.:/-]+", v):
                refs.append(m.group(0))
                if len(refs) >= limit:
                    return

    walk(value)
    out: list[str] = []
    seen = set()
    for ref in refs:
        if ref not in seen:
            out.append(ref)
            seen.add(ref)
    return out[:limit]


def _contract_summary(raw: dict) -> dict:
    for key in ("model_owned_success_contract", "success_contract", "success_contract_snapshot"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _objective(raw: dict, task_prompt: str = "") -> str:
    contract = _contract_summary(raw)

    pieces: list[str] = []
    if isinstance(raw.get("objective"), str):
        pieces.append(raw["objective"])
    if isinstance(raw.get("task_objective"), str):
        pieces.append(raw["task_objective"])
    if isinstance(contract.get("done_condition"), str):
        pieces.append(contract["done_condition"])

    required_outputs = contract.get("required_outputs")
    if isinstance(required_outputs, list) and required_outputs:
        paths = []
        for item in required_outputs[:4]:
            if isinstance(item, dict):
                path = item.get("path") or item.get("artifact") or item.get("name")
                if path:
                    paths.append(str(path))
            elif isinstance(item, str):
                paths.append(item)
        if paths:
            pieces.append("Required output(s): " + ", ".join(paths))

    if not pieces and task_prompt:
        pieces.append(task_prompt[:500])

    return _safe_str(" | ".join(pieces), 900)


def _extract_known_files_from_text(text: str) -> dict:
    files: dict[str, dict[str, Any]] = {}

    known_paths = [
        "/app/gpt2-124M.ckpt",
        "/app/vocab.bpe",
        "/app/gpt2.c",
        "/app/a.out",
    ]

    for path in known_paths:
        if path in text:
            status = "mentioned"
            low = text.lower()
            path_low = path.lower()
            window = ""
            idx = low.find(path_low)
            if idx >= 0:
                window = low[max(0, idx - 120): idx + len(path_low) + 160]
            if any(word in window for word in ("missing", "not found", "does not exist", "no /app/gpt2.c", "has not been created")):
                status = "missing"
            elif any(word in window for word in ("exists", "present", "found", "listed")):
                status = "exists"
            files[path] = {"status": status}

    return files


def _known_state(raw: dict, task_prompt: str = "") -> dict:
    text = json.dumps(raw, default=str)
    files = _extract_known_files_from_text(text + "\n" + task_prompt)

    artifact_summary = raw.get("artifact_summary")
    if isinstance(artifact_summary, dict):
        required = artifact_summary.get("required_artifacts") or artifact_summary.get("items") or []
        for item in _as_list(required):
            if isinstance(item, dict):
                path = item.get("path") or item.get("ref") or item.get("artifact")
                if path:
                    files[str(path)] = {
                        "status": item.get("status", "unknown"),
                        "evidence_refs": _collect_refs(item, limit=4),
                    }

    return {
        "files": files,
        "workspace_inspection": _workspace_inspection_state(raw),
    }


def _workspace_inspection_state(raw: dict) -> dict:
    refs = _collect_refs(raw.get("deduplication_mirror") or raw.get("memory_refs") or raw, limit=8)
    text = json.dumps(raw, default=str).lower()
    done = any(term in text for term in ("find /app", "ls -la /app", "workspace inspection", "gpt2-124m.ckpt", "vocab.bpe"))
    return {
        "status": "done" if done else "unknown",
        "evidence_refs": refs[:6],
    }


def _current_focus(raw: dict) -> dict:
    plan = raw.get("model_owned_working_plan") or raw.get("active_plan") or raw.get("plan") or {}
    plan_dict = _as_dict(plan)

    focus = (
        plan_dict.get("current_focus")
        or plan_dict.get("active_plan_step")
        or plan_dict.get("current_goal")
        or raw.get("current_goal")
        or ""
    )
    focus_text = _safe_str(focus, 260)

    text = json.dumps(raw, default=str).lower()
    stale = False
    stale_reason = ""
    if "inspect visible" in focus_text.lower() or "locate" in focus_text.lower():
        if "gpt2-124m.ckpt" in text and "vocab.bpe" in text and ("gpt2.c" in text and ("missing" in text or "not found" in text)):
            stale = True
            stale_reason = "previous focus is inspection, but visible workspace evidence has already identified the key assets and missing artifact"

    if stale:
        suggested_focus = "decide implementation approach, inspect one specific implementation-critical detail, or create a first artifact draft"
    else:
        suggested_focus = focus_text or "continue from current evidence"

    return {
        "active_focus": focus_text,
        "stale_focus_detected": stale,
        "stale_focus_reason": stale_reason,
        "suggested_focus": suggested_focus,
    }


def _failure_class_from_requirement(item: dict) -> str:
    fc = item.get("failure_class") or item.get("kind") or item.get("status") or "unknown"
    return str(fc)


def _unresolved_requirements(raw: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for item in _as_list(raw.get("open_obligations")):
        if not isinstance(item, dict):
            continue
        out.append({
            "id": item.get("requirement_id") or item.get("check_id") or item.get("id") or "unresolved",
            "status": item.get("status") or "open",
            "failure_class": _failure_class_from_requirement(item),
            "summary": _safe_str(item.get("summary") or item.get("description") or item, 260),
            "needed_evidence": _safe_str(item.get("needed_evidence") or item.get("next_evidence") or "", 220),
            "evidence_refs": _collect_refs(item, limit=4),
        })

    blocker = raw.get("current_blocker")
    if isinstance(blocker, dict) and blocker.get("failure_class") not in (None, "", "none"):
        # Preserve genuine external/final verifier blockers, but do not convert
        # neutral progress_state/workspace facts into pressure-style requirements.
        if blocker.get("type") != "progress_state":
            blocker_id = blocker.get("requirement_id") or blocker.get("check_id") or f"blocker:{blocker.get('failure_class', 'unknown')}"
            if not any(item["id"] == blocker_id for item in out):
                out.insert(0, {
                    "id": blocker_id,
                    "status": "open",
                    "failure_class": str(blocker.get("failure_class") or "unknown"),
                    "summary": _safe_str(blocker.get("summary") or blocker, 280),
                    "needed_evidence": _safe_str(blocker.get("needed_evidence") or "", 220),
                    "evidence_refs": _collect_refs(blocker, limit=4),
                })

    # If no obligations were represented but known GPT-2 state is present, add
    # generic missing-evidence requirements without pretending semantic truth.
    text = json.dumps(raw, default=str).lower()
    has_mutation_evidence = any(
        term in text
        for term in (
            "write_file",
            "created /app/gpt2.c",
            "modified /app/gpt2.c",
            "hash_after",
            "artifact_written",
        )
    )
    if not out and "gpt2.c" in text and not has_mutation_evidence:
        if "missing" in text or "not found" in text or "has not been created" in text:
            out.append({
                "id": "artifact:gpt2.c",
                "status": "unknown",
                "failure_class": "artifact_evidence_gap",
                "summary": "Required artifact existence is not yet fully receipt-backed or behavior-verified",
                "needed_evidence": "receipt-backed artifact creation plus compile/run behavior evidence",
                "evidence_refs": _collect_refs(raw, limit=4),
            })

    return out[:5]



def _progress_state(raw: dict) -> dict:
    value = raw.get("progress_state")
    return value if isinstance(value, dict) else {}


def _workspace_state(raw: dict) -> dict:
    progress = _progress_state(raw)
    known = _known_state(raw)
    files = known.get("files") if isinstance(known, dict) else {}

    expected = []
    for path in progress.get("missing_required_artifacts") or []:
        expected.append({
            "path": str(path),
            "state": "missing",
            "note": "State only. Creating a placeholder file does not satisfy the task.",
        })

    artifact_facts = []
    for item in progress.get("artifact_states") or []:
        if not isinstance(item, dict):
            continue
        artifact_facts.append({
            "path": item.get("path"),
            "exists": item.get("exists"),
            "size_bytes": item.get("size_bytes"),
            "signals": item.get("signals") or [],
            "likely_stub": item.get("likely_stub"),
            "likely_invalid": item.get("likely_invalid"),
        })

    return {
        "files": files,
        "expected_artifacts": expected[:8],
        "artifact_facts": artifact_facts[:8],
        "state_policy": "This is workspace state, not a checklist to game. Existence alone is not success.",
    }


def _evidence_state(raw: dict) -> dict:
    progress = _progress_state(raw)
    last = raw.get("last_result") or raw.get("last_action_result") or {}

    facts = progress.get("facts") if isinstance(progress, dict) else []
    return {
        "compile_attempted": bool(progress.get("compile_attempted")),
        "runtime_attempted": bool(progress.get("runtime_attempted")),
        "productive_step": progress.get("productive_step"),
        "progress_stage": progress.get("progress_stage"),
        "failure_hint": progress.get("failure_hint"),
        "facts": facts[:8] if isinstance(facts, list) else [],
        "last_result_summary": _safe_str(last, 450),
        "evidence_policy": "Evidence should show behaviour against the original task, not only file existence, compilation, non-empty output, or prompt echo.",
    }


def _working_checklist(raw: dict) -> dict:
    plan = raw.get("model_owned_working_plan") or raw.get("active_plan") or raw.get("plan") or {}
    plan_dict = _as_dict(plan)
    inner = plan_dict.get("plan") if isinstance(plan_dict.get("plan"), dict) else plan_dict

    checklist = (
        inner.get("working_checklist")
        or inner.get("checklist_update")
        or inner.get("checklist")
        or []
    )
    if isinstance(checklist, dict):
        checklist = [checklist]
    if not isinstance(checklist, list):
        checklist = []

    updated_at = plan_dict.get("updated_at_step")
    current_step = raw.get("step") or raw.get("step_index")
    stale = False
    try:
        stale = bool(updated_at is not None and current_step is not None and int(updated_at) < int(current_step) - 1)
    except Exception:
        stale = False

    return {
        "schema": "model_owned_checklist.v1",
        "updated_at_step": updated_at,
        "possibly_stale": stale,
        "items": checklist[:12],
        "model_notes": inner.get("model_notes") or plan_dict.get("model_notes") or {},
        "usage": "Editable model-owned checklist. Update it when evidence changes. Do not treat it as a harness gate.",
    }



def _recent_progress(raw: dict) -> dict:
    last = raw.get("last_result") or raw.get("last_action_result") or {}
    progress = _progress_state(raw)

    action_types = progress.get("action_types") if isinstance(progress, dict) else []
    artifact_states = progress.get("artifact_states") if isinstance(progress, dict) else []
    wrote_artifact = bool(
        isinstance(action_types, list)
        and "write_file" in action_types
        and any(isinstance(item, dict) and item.get("exists") for item in artifact_states)
    )

    return {
        "last_result_summary": _safe_str(last, 450),
        "last_action_types": action_types[:8] if isinstance(action_types, list) else [],
        "artifact_written_this_step": wrote_artifact,
        "artifact_written": wrote_artifact,
        "last_mutation": "present" if wrote_artifact else "none_detected",
        "progress_stage": progress.get("progress_stage"),
        "failure_hint": progress.get("failure_hint"),
        "facts": (progress.get("facts") or [])[:6] if isinstance(progress.get("facts"), list) else [],
    }


def _already_known_evidence(raw: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    text = json.dumps(raw, default=str)

    # Dedup mirror is the best direct source.
    mirror = raw.get("deduplication_mirror") or raw.get("dedup_mirror") or {}
    if isinstance(mirror, dict):
        signals = mirror.get("signals") or mirror.get("repeated_actions") or mirror.get("items") or []
        for item in _as_list(signals):
            if not isinstance(item, dict):
                continue
            out.append({
                "fact": _safe_str(item.get("known_result") or item.get("summary") or item.get("message") or "Equivalent action already produced this evidence", 240),
                "evidence_refs": _collect_refs(item, limit=4),
                "note": "repeat only if relevant state changed or the follow-up is more specific",
            })

    lower = text.lower()
    if "gpt2-124m.ckpt" in lower and "vocab.bpe" in lower:
        out.append({
            "fact": "/app/gpt2-124M.ckpt and /app/vocab.bpe have already been observed in visible workspace evidence",
            "evidence_refs": _collect_refs(raw, limit=4),
            "note": "use prior receipts instead of repeating generic workspace inspection",
        })
    has_mutation_evidence = any(
        term in lower
        for term in (
            "write_file",
            "created /app/gpt2.c",
            "modified /app/gpt2.c",
            "hash_after",
            "artifact_written",
        )
    )
    if (
        "gpt2.c" in lower
        and ("missing" in lower or "not found" in lower or "has not been created" in lower)
        and not has_mutation_evidence
    ):
        out.append({
            "fact": "required artifact existence is not yet fully receipt-backed or behavior-verified",
            "evidence_refs": _collect_refs(raw, limit=4),
            "note": "this is an evidence/verification gap, not a reason to repeat generic workspace inspection",
        })
    if "find /app" in lower or "ls -la /app" in lower or "find / " in lower:
        out.append({
            "fact": "generic workspace inspection has already been performed",
            "evidence_refs": _collect_refs(raw, limit=5),
            "note": "repeat only after workspace state changes or when inspecting a more specific implementation-critical detail",
        })

    # Deduplicate by fact.
    deduped: list[dict[str, Any]] = []
    seen = set()
    for item in out:
        key = item.get("fact")
        if key and key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped[:6]


def _available_tools(raw: dict) -> dict[str, str]:
    allowed = raw.get("allowed_next_actions") or raw.get("available_actions") or raw.get("tools") or []
    tools: dict[str, str] = {}

    if isinstance(allowed, dict):
        candidates = list(allowed.keys())
    else:
        candidates = []
        for item in _as_list(allowed):
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("tool") or item.get("action_type")
                if name:
                    candidates.append(str(name))

    if not candidates:
        candidates = list(DEFAULT_TOOL_HINTS.keys())

    for name in candidates:
        if name in DEFAULT_TOOL_HINTS:
            tools[name] = DEFAULT_TOOL_HINTS[name]
        else:
            tools[name] = "available action"

    return tools


def _verification_state(raw: dict) -> dict:
    finalization = raw.get("finalization") or {}
    verifier = raw.get("verifier_summary") or raw.get("critic_result") or raw.get("verification_state") or {}

    completion_allowed = False
    if isinstance(finalization, dict):
        completion_allowed = bool(finalization.get("allowed")) and not raw.get("open_obligations")

    return {
        "last_verifier_summary": _safe_str(verifier, 420),
        "completion_allowed": completion_allowed,
    }


def _finalization_boundary(raw: dict) -> dict:
    finalization = raw.get("finalization") or {}
    blocker = raw.get("current_blocker") or {}
    obligations = raw.get("open_obligations") or []

    submit_allowed = False
    reason = ""

    if isinstance(finalization, dict):
        submit_allowed = bool(finalization.get("allowed")) and not obligations
        reason = _safe_str(finalization.get("summary") or "", 260)

    if not submit_allowed:
        if isinstance(blocker, dict) and blocker.get("summary"):
            reason = _safe_str(blocker.get("summary"), 260)
        elif obligations:
            reason = "open requirements remain"
        else:
            reason = reason or "completion requires receipt-backed evidence"

    return {
        "submit_allowed": submit_allowed,
        "reason": reason,
    }


def _strip_coercive_language(value: Any) -> Any:
    """Remove model-visible strategy pressure while preserving factual state.

    Internal blockers may still exist elsewhere in the harness. This function only
    sanitizes the compact cockpit shown to the solver.
    """
    drop_keys = {
        "required_next_mode",
        "must_not_actions",
        "next_required_actions",
        "repair_protocol",
        "bad_repair_patterns",
    }

    coercive_phrases = (
        "Repair protocol",
        "Identify the next unsatisfied",
        "Produce or verify",
        "Pick one unsatisfied",
        "Write or run a self-check that fails",
        "Repair or replace the artifact/service",
        "Run the self-check",
        "repair_not_finalize",
        "do not finalize",
        "repeat_same_invalid_artifact",
    )

    neutral_replacements = (
        (
            "The model-owned success_contract exists. Finalization remains blocked until required outputs and behavior are supported by typed receipt-backed evidence.",
            "Finalization requires receipt-backed evidence for required outputs and behavior.",
        ),
        (
            "Produce or verify required artifacts with measured receipt-backed evidence.",
            "Required artifacts and behavior still need receipt-backed evidence.",
        ),
        (
            "Repair protocol:",
            "Evidence gap:",
        ),
    )

    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in drop_keys:
                continue
            out[k] = _strip_coercive_language(v)
        return out

    if isinstance(value, list):
        cleaned = []
        for item in value:
            cleaned_item = _strip_coercive_language(item)
            if cleaned_item in ({}, [], None, ""):
                continue
            cleaned.append(cleaned_item)
        return cleaned

    if isinstance(value, str):
        text = value
        for old, new in neutral_replacements:
            text = text.replace(old, new)

        # Drop any remaining sentence-like fragments containing coercive phrases.
        for phrase in coercive_phrases:
            if phrase in text:
                parts = re.split(r"(?<=[.!?])\s+", text)
                kept = [part for part in parts if phrase not in part]
                text = " ".join(kept).strip()

        # Last-resort neutralization if the whole string was coercive.
        if any(phrase in text for phrase in coercive_phrases):
            return "Evidence gap remains; use measured receipts to decide next work."

        return text

    return value


def build_lean_cockpit(raw_cockpit: Any, *, step: int | None = None, task_prompt: str = "", max_chars: int = 9000) -> dict[str, Any]:
    raw = _as_dict(raw_cockpit)
    raw = _strip_coercive_language(raw)

    lean = LeanCockpit(
        step=step or raw.get("step") or raw.get("step_index"),
        objective=_objective(raw, task_prompt=task_prompt),
        known_state=_known_state(raw, task_prompt=task_prompt),
        current_focus=_current_focus(raw),
        unresolved_requirements=_unresolved_requirements(raw),
        workspace_state=_workspace_state(raw),
        evidence_state=_evidence_state(raw),
        working_checklist=_working_checklist(raw),
        recent_progress=_recent_progress(raw),
        already_known_evidence=_already_known_evidence(raw),
        available_tools=_available_tools(raw),
        verification_state=_verification_state(raw),
        memory_refs={
            "important_receipts": _collect_refs(raw, limit=10),
            "full_context_available_via_tools": True,
        },
        finalization_boundary=_finalization_boundary(raw),
    ).to_dict()

    # Enforce a real upper bound by trimming lower priority text fields first.
    text = json.dumps(lean, default=str, sort_keys=True)
    if len(text) <= max_chars:
        return _strip_coercive_language(lean)

    # Trim summaries/notes, not structural state.
    for item in lean.get("already_known_evidence", []):
        if isinstance(item, dict):
            item["note"] = _safe_str(item.get("note"), 120)
    for item in lean.get("unresolved_requirements", []):
        if isinstance(item, dict):
            item["summary"] = _safe_str(item.get("summary"), 140)
            item["needed_evidence"] = _safe_str(item.get("needed_evidence"), 120)
    lean["objective"] = _safe_str(lean.get("objective"), 500)
    lean["verification_state"]["last_verifier_summary"] = _safe_str(
        lean.get("verification_state", {}).get("last_verifier_summary"), 220
    )
    lean["recent_progress"]["last_result_summary"] = _safe_str(
        lean.get("recent_progress", {}).get("last_result_summary"), 220
    )

    text = json.dumps(lean, default=str, sort_keys=True)
    if len(text) > max_chars:
        # Last-resort trim that preserves the dashboard shape.
        lean["already_known_evidence"] = lean.get("already_known_evidence", [])[:4]
        lean["unresolved_requirements"] = lean.get("unresolved_requirements", [])[:5]
        lean["memory_refs"]["important_receipts"] = lean.get("memory_refs", {}).get("important_receipts", [])[:6]

    return lean


__all__ = ["LeanCockpit", "build_lean_cockpit"]

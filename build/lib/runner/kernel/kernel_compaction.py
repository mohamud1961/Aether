"""Deterministic compact-boundary helpers for the control-plane route."""

from __future__ import annotations

import copy
import json
from typing import Any

from runner.kernel_control_plane import refresh_from_kernel_state, validate_pinned_invariants
from runner.kernel_receipts import compact_receipt_digest, summarize_receipt
from runner.kernel_working_window import build_working_window, estimate_window_size


def get_model_context_window(kernel_state: Any) -> int:
    model_mode = ""
    if hasattr(kernel_state, "env_info") and isinstance(kernel_state.env_info, dict):
        model_mode = str(kernel_state.env_info.get("model_route_mode") or kernel_state.env_info.get("model_mode") or "")
    if not model_mode:
        import os
        model_mode = os.environ.get("HARNESS_MODEL_MODE") or os.environ.get("OPENAI_MODEL") or ""
    
    model_mode = model_mode.lower()
    if "gemini" in model_mode:
        return 1000000
    elif "gpt-3.5" in model_mode:
        return 16385
    elif "claude-3" in model_mode:
        return 200000
    # Default is 128k
    return 128000


def should_compact(control_plane: dict[str, Any], kernel_state: Any, history: list[dict[str, Any]] | None, *, budget: int) -> dict[str, Any]:
    model_led_active = getattr(kernel_state, "model_led_evidence_substrate_active", False)
    receipts = list(getattr(kernel_state, "receipts", []))
    history_len = len(history or [])
    recent_limit = int(control_plane.get("window_hints", {}).get("recent_receipt_limit") or 4)

    if model_led_active:
        # Token-based triggers: estimate tokens (total_chars // 4)
        history_str = json.dumps(history or [], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        total_chars = len(history_str)
        estimated_tokens = max(0, total_chars // 4)
        
        model_context_window = get_model_context_window(kernel_state)
        scale_factor = model_context_window / 128000.0
        
        green_ceiling = int(40000 * scale_factor)
        yellow_ceiling = int(75000 * scale_factor)
        red_ceiling = int(80000 * scale_factor)
        hard_ceiling = int(90000 * scale_factor)
        
        # Trigger compaction at an earlier, tighter threshold to prevent attention decay
        threshold_tokens = min(8000, int(model_context_window * 0.15))
        
        triggered = estimated_tokens >= threshold_tokens or len(receipts) > 8
        reason = "context_pressure" if estimated_tokens >= threshold_tokens else "receipt_pressure" if len(receipts) > 8 else "none"
        
        # Build working window with compaction budget
        preview = build_working_window(control_plane, kernel_state, budget=budget)
        preview_size = estimate_window_size(preview)
        
        return {
            "triggered": triggered,
            "trigger": reason,
            "estimated_window_size": preview_size,
            "estimated_tokens": estimated_tokens,
            "budget_chars": budget,
            "history_length": history_len,
            "receipt_count": len(receipts),
            "recent_receipt_limit": recent_limit,
            "preview_window": preview,
            "compaction_zone": "green" if estimated_tokens < green_ceiling else "yellow" if estimated_tokens < yellow_ceiling else "red" if estimated_tokens < red_ceiling else "hard_ceiling",
        }
    else:
        # Legacy behavior
        budget_chars = int(budget or control_plane.get("window_hints", {}).get("budget_chars") or 6000)
        preview = build_working_window(control_plane, kernel_state, budget=budget_chars)
        preview_size = estimate_window_size(preview)
        trigger = preview_size > budget_chars or len(receipts) > recent_limit + 6 or history_len > 30
        reason = "context_pressure" if preview_size > budget_chars else "history_pressure" if history_len > 30 else "receipt_pressure" if len(receipts) > recent_limit + 6 else "none"
        return {
            "triggered": trigger,
            "trigger": reason,
            "estimated_window_size": preview_size,
            "budget_chars": budget_chars,
            "history_length": history_len,
            "receipt_count": len(receipts),
            "recent_receipt_limit": recent_limit,
            "preview_window": preview,
        }



def build_compaction_prompt(control_plane: dict[str, Any], kernel_state: Any, receipt_range: tuple[int, int] | list[int] | None) -> list[dict[str, Any]]:
    receipts = list(getattr(kernel_state, "receipts", []))
    receipt_ids = [receipt.get("receipt_id") for receipt in receipts if isinstance(receipt, dict) and isinstance(receipt.get("receipt_id"), str)]
    recent_limit = int(control_plane.get("window_hints", {}).get("recent_receipt_limit") or 4)
    payload = {
        "compaction_prompt_version": "control_plane_compaction_prompt.v1",
        "route_variant_id": control_plane.get("route_variant_id"),
        "pinned_invariant_hash": control_plane.get("pinned_invariant_hash"),
        "receipt_range": list(receipt_range or []),
        "recent_receipt_ids": receipt_ids[-recent_limit:],
        "semantic_state": dict(control_plane.get("semantic_state", {})),
        "plan_state": dict(control_plane.get("plan_state", {})),
        "open_obligations": dict(control_plane.get("open_obligations", {})),
        "instructions": {
            "do_not_change_kernel_truth": True,
            "output_shape": {
                "compaction_summary": {
                    "summary": "<string>",
                    "receipt_ids": ["<recent receipt ids>"],
                    "artifact_refs": ["<optional artifact refs>"],
                    "discoveries": ["<optional findings>"],
                    "hypotheses": ["<optional hypotheses>"],
                    "evidence_targets": ["<optional evidence targets>"],
                    "candidate_next_checks": ["<optional candidate checks>"],
                    "subtasks": ["<optional subtasks>"],
                    "open_questions": ["<optional questions>"],
                    "next_action": "<optional next action>",
                    "blocked_reason": "<optional blocked reason>",
                    "confidence": "<optional confidence note>",
                    "proposed_success_criteria": ["<optional proposed criteria>"],
                }
            },
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "Summarize the current control-plane state without changing any pinned invariant or using tools. "
                "Return structured JSON only. The kernel owns verifier/artifact/service truth and pinned invariants; "
                "the summary may only describe semantic state and the preserved receipt suffix."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        },
    ]


def create_compaction_boundary(control_plane: dict[str, Any], kernel_state: Any, summary: Any, trigger: str) -> dict[str, Any]:
    validation = validate_pinned_invariants(control_plane)
    if validation["status"] != "pass":
        raise ValueError(f"missing pinned invariants: {validation['missing_keys']}")
    receipts = list(getattr(kernel_state, "receipts", []))
    recent_limit = int(control_plane.get("window_hints", {}).get("recent_receipt_limit") or 4)
    preserved = receipts[-recent_limit:] if recent_limit > 0 else []
    omitted = receipts[: len(receipts) - len(preserved)] if preserved else list(receipts)
    preserved_ids = [receipt.get("receipt_id") for receipt in preserved if isinstance(receipt, dict) and isinstance(receipt.get("receipt_id"), str)]
    boundary = {
        "compact_id": f"cp_{len(control_plane.get('compact_boundaries', [])) + 1:04d}",
        "trigger": trigger,
        "budget_chars": int(control_plane.get("window_hints", {}).get("budget_chars") or 6000),
        "pre_receipt_count": len(receipts),
        "preserved_receipt_ids": preserved_ids,
        "preserved_receipt_id_range": [preserved_ids[0], preserved_ids[-1]] if preserved_ids else [],
        "omitted_receipt_count": len(omitted),
        "omitted_receipt_digest": compact_receipt_digest(omitted) if omitted else "",
        "pinned_invariant_hash": validation["pinned_invariant_hash"],
        "raw_trace_pointer": dict(control_plane.get("raw_trace_pointers", {})).get("run_events", "run_events.jsonl"),
        "summary": _summary_text(summary),
        "summary_kind": _summary_kind(summary),
        "summary_source": _summary_source(summary),
    }
    boundary["preserved_receipts"] = [summarize_receipt(receipt) for receipt in preserved]
    return boundary


def extract_compaction_summary(completion: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(completion, dict):
        return None
    for key in ("compaction_summary", "semantic_state_update", "control_plane_update"):
        value = completion.get(key)
        if isinstance(value, dict):
            return _unwrap_compaction_payload(value)
        if isinstance(value, str):
            parsed = _parse_json_like_object(value)
            if isinstance(parsed, dict):
                return _unwrap_compaction_payload(parsed)
    text = completion.get("text")
    if isinstance(text, str) and text:
        parsed = _parse_json_like_object(text)
        if isinstance(parsed, dict):
            return _unwrap_compaction_payload(parsed)
    return None


def validate_compaction_summary(
    summary: dict[str, Any] | None,
    control_plane: dict[str, Any],
    kernel_state: Any,
    compact_check: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {"status": "rejected", "reason_codes": ["invalid_compaction_summary_shape"]}
    rejected_keys = [key for key in summary if key in {"success_criteria", "verifier_state", "artifact_state", "workspace_contract", "task_contract", "pinned_invariants"}]
    if rejected_keys:
        return {"status": "rejected", "reason_codes": ["compaction_summary_attempted_truth_override", *sorted(rejected_keys)]}
    summary_text = _summary_text(summary)
    if not summary_text:
        return {"status": "rejected", "reason_codes": ["compaction_summary_missing_text"]}
    receipt_ids = _string_list(summary.get("receipt_ids"))
    artifact_refs = _string_list(summary.get("artifact_refs"))
    recent_receipts = list((compact_check or {}).get("preview_window", {}).get("recent_receipts", []))
    recent_receipt_ids = [receipt.get("receipt_id") for receipt in recent_receipts if isinstance(receipt, dict) and isinstance(receipt.get("receipt_id"), str)]
    if receipt_ids and recent_receipt_ids and not any(receipt_id in recent_receipt_ids for receipt_id in receipt_ids):
        return {
            "status": "rejected",
            "reason_codes": ["compaction_summary_missing_recent_receipt_reference"],
            "recent_receipt_ids": list(recent_receipt_ids),
        }
    if not receipt_ids and not artifact_refs:
        return {"status": "rejected", "reason_codes": ["compaction_summary_missing_evidence_references"]}
    validated = {
        "status": "accepted",
        "reason_codes": [],
        "summary": summary_text,
        "receipt_ids": receipt_ids,
        "artifact_refs": artifact_refs,
        "discoveries": _string_list(summary.get("discoveries")),
        "hypotheses": _string_list(summary.get("hypotheses")),
        "evidence_targets": _string_list(summary.get("evidence_targets")),
        "candidate_next_checks": _string_list(summary.get("candidate_next_checks")),
        "subtasks": _string_list(summary.get("subtasks")),
        "open_questions": _string_list(summary.get("open_questions")),
        "next_action": str(summary.get("next_action") or ""),
        "blocked_reason": str(summary.get("blocked_reason") or ""),
        "confidence": str(summary.get("confidence") or ""),
        "proposed_success_criteria": _string_list(summary.get("proposed_success_criteria")),
        "source": str(summary.get("source") or summary.get("summary_source") or "model"),
        "model_led": True,
        "compact_id": str((control_plane.get("last_compaction_boundary") or {}).get("compact_id") or ""),
    }
    _ = kernel_state
    return validated


def render_compaction_summary(summary: dict[str, Any] | None) -> str:
    payload = dict(summary or {})
    payload.setdefault("model_led", True)
    return "[control_plane_compaction_summary]\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def rehydrate_after_compaction(control_plane: dict[str, Any], kernel_state: Any, boundary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(boundary, dict):
        raise ValueError("boundary must be a mapping")
    updated = copy.deepcopy(control_plane)
    boundaries = list(updated.get("compact_boundaries", []))
    boundaries.append(dict(boundary))
    updated["compact_boundaries"] = boundaries
    updated["last_compaction_boundary"] = dict(boundary)
    semantic_state = dict(updated.get("semantic_state", {}))
    semantic_state["summary"] = str(boundary.get("summary") or semantic_state.get("summary") or "")
    semantic_state["interrupt_reason"] = "compaction_boundary"
    semantic_state["last_compaction_boundary"] = {
        "compact_id": boundary.get("compact_id", ""),
        "summary_kind": boundary.get("summary_kind", ""),
        "summary_source": boundary.get("summary_source", ""),
        "trigger": boundary.get("trigger", ""),
    }
    updated["semantic_state"] = semantic_state
    refreshed = refresh_from_kernel_state(updated, kernel_state, {})
    validation = validate_pinned_invariants(refreshed)
    if validation["status"] != "pass":
        raise ValueError(f"missing pinned invariants after compaction: {validation['missing_keys']}")
    return {"status": "pass", "control_plane": refreshed, "boundary": dict(boundary), "pinned_invariant_hash": validation["pinned_invariant_hash"]}


def _summary_text(summary: Any) -> str:
    if isinstance(summary, str):
        return summary
    if isinstance(summary, dict):
        for key in ("summary", "text", "rendered", "content"):
            value = summary.get(key)
            if isinstance(value, str) and value:
                return value
        return json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return str(summary or "")


def _summary_kind(summary: Any) -> str:
    if isinstance(summary, dict):
        return "model" if summary.get("model_led") else "deterministic"
    return "deterministic"


def _summary_source(summary: Any) -> str:
    if isinstance(summary, dict):
        return str(summary.get("source") or summary.get("summary_source") or ("model" if summary.get("model_led") else "deterministic"))
    return "deterministic"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _unwrap_compaction_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("compaction_summary"), dict):
        return dict(payload["compaction_summary"])
    if isinstance(payload.get("semantic_state_update"), dict):
        semantic_state = dict(payload["semantic_state_update"])
        if isinstance(semantic_state.get("compaction_summary"), dict):
            return dict(semantic_state["compaction_summary"])
        return semantic_state
    if isinstance(payload.get("control_plane_update"), dict):
        control_plane_update = dict(payload["control_plane_update"])
        if isinstance(control_plane_update.get("compaction_summary"), dict):
            return dict(control_plane_update["compaction_summary"])
        return control_plane_update
    return dict(payload)


def _parse_json_like_object(text: str) -> Any:
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


def get_receipt_step(receipt: dict[str, Any], index: int) -> int:
    rid = str(receipt.get("receipt_id") or "")
    if rid.startswith("r") and rid[1:].isdigit():
        return int(rid[1:])
    return index


def classify_receipt(receipt: dict[str, Any], current_step: int, receipts: list[dict[str, Any]]) -> str:
    try:
        step = get_receipt_step(receipt, receipts.index(receipt) if receipt in receipts else 0)
    except Exception:
        step = 0
    if current_step - step <= 10:
        return "keep_full"
        
    tool_name = str(receipt.get("tool_name") or "")
    command = str(receipt.get("command") or "")
    exit_code = receipt.get("exit_code")
    
    is_read = "view_file" in tool_name or "cat " in command or "read_file" in tool_name or "view_file" in command
    if is_read:
        file_path = ""
        if isinstance(receipt.get("tool_call"), dict):
            args = receipt["tool_call"].get("arguments") or {}
            file_path = args.get("AbsolutePath") or args.get("TargetFile") or args.get("path") or ""
        if not file_path:
            for token in command.split():
                if "/" in token or "." in token:
                    file_path = token
                    break
        if file_path:
            for later_receipt in receipts:
                try:
                    later_step = get_receipt_step(later_receipt, receipts.index(later_receipt))
                except Exception:
                    later_step = 0
                if later_step > step:
                    later_changes = later_receipt.get("changed_files") or []
                    if any(file_path in str(ch) or str(ch) in file_path for ch in later_changes):
                        return "stale"
                        
    is_install_or_build = any(x in command for x in ("pip install", "npm install", "go build", "poetry install", "cargo build"))
    if is_install_or_build and exit_code == 0:
        return "noise"
        
    is_explorer = any(x in command or x in tool_name for x in ("ls", "find", "grep", "tree", "rg"))
    if is_explorer and current_step - step > 5:
        return "explored"
        
    if is_read and current_step - step > 8:
        return "compact_to_reference"
        
    return "keep_full"


def classify_and_compact_receipt(receipt: dict[str, Any], current_step: int, all_receipts: list[dict[str, Any]]) -> dict[str, Any]:
    classification = classify_receipt(receipt, current_step, all_receipts)
    if classification == "keep_full":
        return summarize_receipt(receipt)
        
    receipt_id = receipt.get("receipt_id", "")
    try:
        step = get_receipt_step(receipt, all_receipts.index(receipt) if receipt in all_receipts else 0)
    except Exception:
        step = 0
    command = str(receipt.get("command") or "")
    exit_code = receipt.get("exit_code")
    
    if classification == "stale":
        line_count = len(str(receipt.get("stdout") or "").splitlines()) or 100
        file_path = ""
        if isinstance(receipt.get("tool_call"), dict):
            args = receipt["tool_call"].get("arguments") or {}
            file_path = args.get("AbsolutePath") or args.get("TargetFile") or args.get("path") or ""
        if not file_path:
            for token in command.split():
                if "/" in token or "." in token:
                    file_path = token
                    break
        mod_step = step + 4
        for r in all_receipts:
            try:
                r_step = get_receipt_step(r, all_receipts.index(r))
            except Exception:
                r_step = 0
            if r_step > step and file_path and any(file_path in str(ch) for ch in (r.get("changed_files") or [])):
                mod_step = r_step
                break
        return {
            "receipt_id": receipt_id,
            "step": step,
            "classification": "stale",
            "summary": f"Read {file_path} ({line_count} lines) at step {step} — file was modified at step {mod_step}, this version is stale"
        }
        
    elif classification == "noise":
        cmd_head = command.splitlines()[0] if command else ""
        if len(cmd_head) > 50:
            cmd_head = cmd_head[:47] + "..."
        return {
            "receipt_id": receipt_id,
            "step": step,
            "classification": "noise",
            "summary": f"{cmd_head}: success (exit {exit_code})"
        }
        
    elif classification == "explored":
        cmd_head = command.splitlines()[0] if command else ""
        if len(cmd_head) > 50:
            cmd_head = cmd_head[:47] + "..."
        items_count = len(str(receipt.get("stdout_excerpt") or "").splitlines())
        return {
            "receipt_id": receipt_id,
            "step": step,
            "classification": "explored",
            "summary": f"{cmd_head}: {items_count} items found (exit {exit_code})"
        }
        
    elif classification == "compact_to_reference":
        line_count = len(str(receipt.get("stdout_excerpt") or "").splitlines()) or 50
        file_path = ""
        if isinstance(receipt.get("tool_call"), dict):
            args = receipt["tool_call"].get("arguments") or {}
            file_path = args.get("AbsolutePath") or args.get("TargetFile") or args.get("path") or ""
        if not file_path:
            for token in command.split():
                if "/" in token or "." in token:
                    file_path = token
                    break
        stdout_hash = str(receipt.get("stdout_sha256") or "")[:7] or "abc123"
        return {
            "receipt_id": receipt_id,
            "step": step,
            "classification": "compact_to_reference",
            "summary": f"Read {file_path} ({line_count} lines) at step {step} — still current, hash {stdout_hash}"
        }
        
    return summarize_receipt(receipt)


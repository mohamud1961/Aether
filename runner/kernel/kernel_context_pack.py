"""Evidence-preserving context-pack projection and history manager."""

from __future__ import annotations

import json
from typing import Any

from blocks.context.full_history import append_observation

from runner.kernel_evidence_trail import project_evidence_trail_state
from runner.kernel_receipts import compact_receipt_digest, summarize_receipt
from runner.kernel_services import project_service_summary
from runner.kernel_artifacts import summarize_artifact_registry


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    pack = observation.pop("evidence_context_pack", None)
    if pack is None:
        pack = observation.pop("context_pack", None)
    if pack is not None:
        rendered = render_context_pack(pack)
        observation.setdefault("role", "system")
        existing = observation.get("content")
        if isinstance(existing, str) and existing:
            observation["content"] = f"{existing}\n\n[active_evidence_context_pack]\n{rendered}"
        else:
            observation["content"] = f"[active_evidence_context_pack]\n{rendered}"
    return append_observation(history, observation)


def build_context_pack(state: Any, *, max_recent_receipts: int = 5) -> dict[str, Any]:
    receipts = list(getattr(state, "receipts", []))
    recent = receipts[-max_recent_receipts:] if max_recent_receipts > 0 else []
    omitted = receipts[: len(receipts) - len(recent)] if recent else list(receipts)
    omitted_ids = [
        receipt.get("receipt_id")
        for receipt in omitted
        if isinstance(receipt, dict) and isinstance(receipt.get("receipt_id"), str)
    ]
    service_projection = project_service_summary(
        dict(getattr(state, "service_registry", {})),
        dict(getattr(state, "process_registry", {})),
    )
    native_tool_state = dict(getattr(state, "native_tool_state", {}))
    verifier_state = dict(getattr(state, "verifier_status", {}))
    artifact_state = dict(getattr(state, "artifact_gate", {}))
    provenance_state = dict(getattr(state, "provenance_status", {}))
    evidence_capsule = dict(getattr(state, "evidence_capsule", {}))
    open_obligations = dict(getattr(state, "open_obligations", {}))
    failure_signature_counts = dict(getattr(state, "failure_signature_counts", {}))
    success_contract = dict(getattr(state, "success_contract", {}))
    evidence_trail_state = dict(getattr(state, "evidence_trail_state", {}))
    if not evidence_trail_state:
        evidence_trail_state = project_evidence_trail_state(
            list(getattr(state, "evidence_trail_records", [])),
            success_contract=success_contract,
        )
    layer2_audit_state = dict(getattr(state, "layer2_audit_state", {}))
    model_led_active = getattr(state, "model_led_evidence_substrate_active", False)
    recent_compact = []
    for receipt in recent:
        if model_led_active:
            from runner.kernel_compaction import classify_and_compact_receipt
            summary = classify_and_compact_receipt(receipt, len(receipts), receipts)
        else:
            summary = summarize_receipt(receipt)
        if isinstance(receipt, dict) and "artifact_inspection" in receipt:
            summary["artifact_inspection"] = receipt["artifact_inspection"]
        recent_compact.append(summary)
    artifact_registry = dict(getattr(state, "artifact_registry", {}))
    artifact_registry_summary = summarize_artifact_registry(artifact_registry)
    return {
        "context_pack_version": "active_evidence_kernel_context.v1",
        "model_led_active": model_led_active,
        "task_contract": {
            "run_id": getattr(state, "run_id", ""),
            "task_id": getattr(state, "task_id", ""),
            "task_prompt": getattr(state, "task_prompt", ""),
        },
        "environment": {
            "cwd": getattr(state, "cwd", ""),
            "workspace_root": str(getattr(state, "workspace_root", "")),
            "declared_tool_names": list(getattr(state, "declared_tool_names", [])),
            "native_tool_mode_active": bool(getattr(state, "native_tool_mode_active", False)),
        },
        "recent_receipts": recent_compact,
        "compression": {
            "total_receipt_count": len(receipts),
            "recent_receipt_count": len(recent),
            "omitted_receipt_count": len(omitted),
            "omitted_receipt_digest": compact_receipt_digest(omitted) if omitted else "",
            "omitted_receipt_id_range": [omitted_ids[0], omitted_ids[-1]] if omitted_ids else [],
        },
        "selected_facts": list(getattr(state, "selected_facts", [])),
        "rejected_decoys": list(getattr(state, "rejected_decoys", [])),
        "artifact_lineage": {
            "files_read": list(getattr(state, "files_read", [])),
            "files_written": list(getattr(state, "files_written", [])),
            "artifact_candidates": list(getattr(state, "artifact_candidates", [])),
        },
        "verifier_state": verifier_state,
        "artifact_state": artifact_state,
        "artifact_registry_summary": artifact_registry_summary,
        "provenance_state": provenance_state,
        "service_state": service_projection,
        "native_tool_state": native_tool_state,
        "evidence_trail_state": evidence_trail_state,
        "failures": {
            "last_failure_signature": getattr(state, "last_failure_signature", None),
            "failure_signature_counts": failure_signature_counts,
            "last_failure": dict(getattr(state, "last_failure", {})),
            "recovery_card": dict(getattr(state, "recovery_card", {})),
            "stale_facts": list(getattr(state, "stale_facts", [])),
        },
        "open_obligations": open_obligations,
        "evidence_capsule": evidence_capsule,
        "success_contract": success_contract,
        "layer2_audit_state": layer2_audit_state,
        "model_call_count": int(getattr(state, "model_call_count", 0) or 0),
        "tool_call_count": int(getattr(state, "tool_call_count", 0) or 0),
        "verifier_run_count": int(getattr(state, "verifier_run_count", 0) or 0),
        "service_probe_count": int(getattr(state, "service_probe_count", 0) or 0),
    }


def render_context_pack(context_pack: dict[str, Any]) -> str:
    return json.dumps(context_pack, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

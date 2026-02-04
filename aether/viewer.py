from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .hash_chain import verify_event_chain


def build_view(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    context_slice_by_step = _context_slice_events_by_step(events)
    channel_a = [_render_event(event, context_slice_by_step) for event in events]
    context_pack_hash, manifest_hash = _latest_hashes(events)
    context_pack_ref, manifest_ref = _latest_context_refs(events)
    context_slice_ref, context_slice_hash = _latest_context_slice_ref(events)
    completion_bundle = _latest_completion_bundle(events)
    hash_chain_report = verify_event_chain(events)

    channel_b = {
        "context_pack_hash": context_pack_hash,
        "manifest_hash": manifest_hash,
        "context_pack_ref": context_pack_ref,
        "manifest_ref": manifest_ref,
        "latest_context_slice_ref": context_slice_ref,
        "latest_context_slice_hash": context_slice_hash,
        "completion_evidence_bundle_ref": completion_bundle.get("completion_evidence_bundle_ref"),
        "completion_evidence_bundle_id": completion_bundle.get("completion_evidence_bundle_id"),
        "completion_evidence_bundle_hash": completion_bundle.get("completion_evidence_bundle_hash"),
        "completion_required_context_slice_refs": completion_bundle.get("required_context_slice_refs"),
        "completion_required_verifier_result_refs": completion_bundle.get("required_verifier_result_refs"),
        "completion_required_verifier_report_refs": completion_bundle.get("required_verifier_report_refs"),
        "completion_required_governance_decision_refs": completion_bundle.get("required_governance_decision_refs"),
    }

    return {
        "channel_a": channel_a,
        "channel_b": channel_b,
        "hash_chain_report": hash_chain_report,
    }


def _latest_hashes(events: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    context_pack_hash = None
    manifest_hash = None
    for event in events:
        if event.get("context_pack_hash"):
            context_pack_hash = event.get("context_pack_hash")
        if event.get("manifest_hash"):
            manifest_hash = event.get("manifest_hash")
    return context_pack_hash, manifest_hash


def _latest_context_refs(events: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    context_pack_ref = None
    manifest_ref = None
    for event in events:
        if event.get("event_type") not in {"context_compiler", "CONTEXTPACK_COMPILED"}:
            continue
        if isinstance(event.get("context_pack_ref"), str):
            context_pack_ref = event.get("context_pack_ref")
        if isinstance(event.get("manifest_ref"), str):
            manifest_ref = event.get("manifest_ref")
        refs = event.get("artifact_refs") or []
        if len(refs) >= 2 and (context_pack_ref is None or manifest_ref is None):
            context_pack_ref = refs[0]
            manifest_ref = refs[1]
    return context_pack_ref, manifest_ref


def _latest_context_slice_ref(events: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    context_slice_ref = None
    context_slice_hash = None
    for event in events:
        if event.get("event_type") != "context_slice_bound":
            continue
        if isinstance(event.get("context_slice_ref"), str):
            context_slice_ref = event.get("context_slice_ref")
        if isinstance(event.get("context_slice_hash"), str):
            context_slice_hash = event.get("context_slice_hash")
    return context_slice_ref, context_slice_hash


def _latest_completion_bundle(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    latest: Dict[str, Any] = {}
    for event in events:
        if event.get("event_type") != "completion_evidence_bundle_created":
            continue
        latest = event
    return latest


def _context_slice_events_by_step(events: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    mapping: Dict[int, Dict[str, Any]] = {}
    latest: Optional[Dict[str, Any]] = None
    for event in events:
        step_id = event.get("step_id")
        if event.get("event_type") != "context_slice_bound":
            if isinstance(step_id, int) and latest is not None:
                mapping.setdefault(step_id, latest)
            continue
        if isinstance(step_id, int):
            latest = event
            mapping[step_id] = event
    return mapping


def _render_event(
    event: Dict[str, Any],
    context_slice_by_step: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    tool_name = event.get("tool_name")
    tool_args = event.get("tool_args") if tool_name is not None else None
    exit_code = event.get("exit_code") if tool_name is not None else None

    triggers_fired = event.get("triggers_fired") or []
    completion_signals = event.get("completion_signals") or []
    step_id = event.get("step_id")
    context_slice = context_slice_by_step.get(step_id) if isinstance(step_id, int) else None
    artifact_refs = event.get("artifact_refs") if isinstance(event.get("artifact_refs"), list) else []

    return {
        "step_id": step_id,
        "event_id": event.get("event_id"),
        "prev_event_hash": event.get("prev_event_hash"),
        "event_type": event.get("event_type"),
        "tool_name": tool_name,
        "tool_args": tool_args,
        "exit_code": exit_code,
        "stdout_ref": event.get("stdout_ref"),
        "stderr_ref": event.get("stderr_ref"),
        "verifier_result": event.get("verifier_result")
        if event.get("verifier_result") is not None
        else None,
        "triggers_fired": triggers_fired if triggers_fired else None,
        "completion_signals": completion_signals if completion_signals else None,
        "termination_reason": event.get("termination_reason")
        if event.get("termination_reason") is not None
        else None,
        "context_slice_ref": event.get("context_slice_ref")
        if isinstance(event.get("context_slice_ref"), str)
        else context_slice.get("context_slice_ref")
        if context_slice
        else None,
        "context_slice_hash": event.get("context_slice_hash")
        if isinstance(event.get("context_slice_hash"), str)
        else context_slice.get("context_slice_hash")
        if context_slice
        else None,
        "saw_context_pack_hash": event.get("context_pack_hash")
        if isinstance(event.get("context_pack_hash"), str)
        else context_slice.get("context_pack_hash")
        if context_slice
        else None,
        "saw_manifest_hash": event.get("manifest_hash")
        if isinstance(event.get("manifest_hash"), str)
        else context_slice.get("manifest_hash")
        if context_slice
        else None,
        "saw_model_request_hash": event.get("model_request_hash")
        if isinstance(event.get("model_request_hash"), str)
        else context_slice.get("model_request_hash")
        if context_slice
        else None,
        "did_receipt_refs": artifact_refs if artifact_refs else None,
    }

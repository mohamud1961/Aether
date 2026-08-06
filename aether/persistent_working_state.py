"""Bounded model-owned reasoning continuity for PERSISTENT V0.

This is not hidden chain of thought and it is never task-completion evidence.
The Primary Agent may optionally publish a concise working-state checkpoint.
The Kernel validates shape, size, evidence custody, lineage, freshness and
versioning, then preserves the model-authored content without interpreting it.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from .ledger import ExecutionLedger, Receipt
from .persistent_evidence import is_persistent_completion_evidence
from .persistent_provider_protocol import (
    PCRProviderProtocolError,
    validate_persistent_working_state,
)
from .runtime_ir import SolverTurn, stable_json


PERSISTENT_WORKING_STATE_FIELDS = frozenset({
    "current_objective",
    "established_facts",
    "open_questions",
    "active_hypotheses",
    "current_approach",
    "rejected_approaches",
    "pending_external_state",
    "completion_gaps",
})
PERSISTENT_WORKING_STATE_MAX_BYTES = 16_384


def _visible_evidence(
    context_packet: Mapping[str, Any],
    ledger: ExecutionLedger,
) -> dict[str, tuple[Mapping[str, Any], Receipt]]:
    receipts = {receipt.receipt_id: receipt for receipt in ledger.all_receipts()}
    visible: dict[str, tuple[Mapping[str, Any], Receipt]] = {}
    rows = context_packet.get("evidence_index", ())
    if not isinstance(rows, list):
        return visible
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        alias = str(row.get("evidence_ref", "")).strip()
        receipt_id = str(row.get("receipt_id", "")).strip()
        receipt = receipts.get(receipt_id)
        if not alias or receipt is None:
            continue
        if row.get("completion_evidence_eligible") is not True:
            continue
        if not is_persistent_completion_evidence(receipt):
            continue
        visible[alias] = (row, receipt)
    return visible


def _all_checkpoint_refs(checkpoint: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for fact in checkpoint.get("established_facts", ()) or ():
        if isinstance(fact, Mapping):
            refs.extend(str(item).strip() for item in fact.get("evidence_refs", ()) or ())
    for rejected in checkpoint.get("rejected_approaches", ()) or ():
        if isinstance(rejected, Mapping):
            refs.extend(str(item).strip() for item in rejected.get("evidence_refs", ()) or ())
    return tuple(item for item in refs if item)


def _latest_primary_result_index_id(ledger: ExecutionLedger) -> str:
    receipt = ledger.latest_receipt("primary_action_result_index")
    return receipt.receipt_id if receipt is not None else ""


def _record_rejection(
    ledger: ExecutionLedger,
    *,
    step: int,
    code: str,
    detail: str,
) -> Receipt:
    receipt = Receipt(
        receipt_id=f"step-{step}:persistent_working_state_rejected:{code}",
        step=step,
        kind="persistent_working_state_rejected",
        success=False,
        summary="Primary Agent working-state checkpoint was not admitted.",
        failure_class=code,
        payload={
            "detail": detail,
            "checkpoint_execution_effect": "none",
            "task_action_may_continue": True,
            "semantic_content_interpreted_by_kernel": False,
        },
    )
    ledger.record(receipt)
    return receipt


def record_persistent_working_state(
    turn: SolverTurn,
    context_packet: Mapping[str, Any],
    ledger: ExecutionLedger,
    *,
    step: int,
) -> Receipt | None:
    """Validate and persist an optional checkpoint without blocking the turn."""
    checkpoint = dict(turn.working_state or {})
    if not checkpoint:
        return None
    try:
        checkpoint = validate_persistent_working_state(checkpoint)
    except PCRProviderProtocolError as exc:
        return _record_rejection(
            ledger,
            step=step,
            code="persistent_working_state_shape_invalid",
            detail=str(exc),
        )
    encoded = stable_json(checkpoint).encode("utf-8")
    if len(encoded) > PERSISTENT_WORKING_STATE_MAX_BYTES:
        return _record_rejection(
            ledger,
            step=step,
            code="persistent_working_state_too_large",
            detail=(
                f"working state has {len(encoded)} bytes; maximum is "
                f"{PERSISTENT_WORKING_STATE_MAX_BYTES}"
            ),
        )

    visible = _visible_evidence(context_packet, ledger)
    refs = _all_checkpoint_refs(checkpoint)
    for ref in refs:
        pair = visible.get(ref)
        if pair is None:
            return _record_rejection(
                ledger,
                step=step,
                code="persistent_working_state_evidence_not_current",
                detail=f"working state evidence alias {ref!r} is not in current context",
            )
        _row, receipt = pair
        if receipt.step >= step:
            return _record_rejection(
                ledger,
                step=step,
                code="persistent_working_state_future_evidence",
                detail=f"working state evidence alias {ref!r} is not prior evidence",
            )

    identity = dict(context_packet.get("runtime_identity", {}) or {})
    if identity != dict(ledger.runtime_identity or {}):
        return _record_rejection(
            ledger,
            step=step,
            code="persistent_working_state_identity_mismatch",
            detail="working state context identity differs from canonical run identity",
        )

    prior = [
        receipt for receipt in ledger.all_receipts()
        if receipt.kind == "persistent_working_state_checkpoint" and receipt.success
    ]
    version = len(prior) + 1
    state_generation = ledger.task_state_generation()
    primary_result_index_id = _latest_primary_result_index_id(ledger)
    evidence_bindings = {
        ref: visible[ref][1].receipt_id for ref in dict.fromkeys(refs)
    }
    checkpoint_sha256 = sha256(stable_json({
        "version": version,
        "checkpoint": checkpoint,
        "evidence_bindings": evidence_bindings,
        "task_state_generation": state_generation,
        "latest_primary_result_index_receipt_id": primary_result_index_id,
        "task_id": identity.get("task_id", ""),
        "run_id": identity.get("run_id", ""),
        "workspace_id": identity.get("workspace_id", ""),
    }).encode("utf-8")).hexdigest()
    receipt = Receipt(
        receipt_id=f"step-{step}:persistent_working_state:v{version}:{checkpoint_sha256[:16]}",
        step=step,
        kind="persistent_working_state_checkpoint",
        success=True,
        summary=f"preserved Primary Agent working-state checkpoint version {version}",
        state_change=False,
        payload={
            "version": version,
            "checkpoint_sha256": checkpoint_sha256,
            "checkpoint": checkpoint,
            "evidence_bindings": evidence_bindings,
            "evidence_refs": list(refs),
            "task_state_generation": state_generation,
            "latest_primary_result_index_receipt_id": primary_result_index_id,
            "task_id": identity.get("task_id", ""),
            "run_id": identity.get("run_id", ""),
            "workspace_id": identity.get("workspace_id", ""),
            "authority": "primary_agent_working_state_only",
            "completion_evidence_eligible": False,
            "semantic_content_interpreted_by_kernel": False,
            "hidden_chain_of_thought": False,
        },
    )
    ledger.record(receipt)
    return receipt


def latest_persistent_working_state(ledger: ExecutionLedger) -> dict[str, Any]:
    """Render the latest checkpoint with mechanical freshness metadata."""
    receipt = ledger.latest_receipt("persistent_working_state_checkpoint")
    if receipt is None or not receipt.success:
        return {
            "status": "not_authored",
            "authority": "primary_agent_working_state_only",
            "completion_evidence_eligible": False,
        }
    payload = receipt.payload if isinstance(receipt.payload, dict) else {}
    authored_generation = int(payload.get("task_state_generation", -1))
    current_generation = ledger.task_state_generation()
    authored_primary_result_id = str(
        payload.get("latest_primary_result_index_receipt_id", "") or ""
    )
    current_primary_result_id = _latest_primary_result_index_id(ledger)
    newer_primary_observation = authored_primary_result_id != current_primary_result_id
    task_state_mutated = authored_generation != current_generation
    if task_state_mutated:
        status = "potentially_stale_after_task_mutation"
    elif newer_primary_observation:
        status = "potentially_stale_after_new_primary_observation"
    else:
        status = "current"
    return {
        "status": status,
        "receipt_id": receipt.receipt_id,
        "authored_step": receipt.step,
        "version": payload.get("version"),
        "checkpoint_sha256": payload.get("checkpoint_sha256", ""),
        "task_state_generation_at_authorship": authored_generation,
        "current_task_state_generation": current_generation,
        "latest_primary_result_index_receipt_id_at_authorship": authored_primary_result_id,
        "current_latest_primary_result_index_receipt_id": current_primary_result_id,
        "new_primary_observation_since_authorship": newer_primary_observation,
        "task_state_mutated_since_authorship": task_state_mutated,
        "checkpoint": payload.get("checkpoint", {}),
        "evidence_bindings": payload.get("evidence_bindings", {}),
        "authority": "primary_agent_working_state_only",
        "completion_evidence_eligible": False,
        "semantic_content_interpreted_by_kernel": False,
        "freshness_rule": (
            "A newer Primary action result or task mutation after authorship marks "
            "the checkpoint potentially stale; the Primary Agent decides what to revise."
        ),
    }

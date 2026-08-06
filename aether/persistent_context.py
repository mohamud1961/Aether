"""PERSISTENT V0 projection over the canonical production ContextCompiler.

This module does not select strategy or create a second context engine. It wraps
the already-bounded canonical packet with pinned mechanical facts that PERSISTENT must
never lose: stable task-run identity, the latest Primary Agent action result,
current runtime failures/findings, visible evidence aliases, capabilities, and
hard budgets.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from . import context_views as _views
from .persistent_capabilities import persistent_capability_contract
from .persistent_context_budget import finalize_persistent_context_budget
from .finding_evidence import evidence_after_latest_verifier
from .persistent_evidence import is_persistent_completion_evidence
from .persistent_helper_tools import helper_context
from .persistent_working_state import latest_persistent_working_state
from .runtime_ir import CompiledRuntime, stable_json

if False:  # pragma: no cover - type-only without an import cycle at runtime.
    from .ledger import ExecutionLedger, Receipt


_MAX_EVIDENCE_ROWS = 24
_CONTROL_KINDS = frozenset({
    "accounting",
    "runtime_accounting",
    "automatic_memory",
    "config_realization",
    "primary_decision",
    "runtime_identity",
    "solver_decision_state",
    "solver_progress_assessment",
    "primary_action_result_index",
    "persistent_repeat_observation",
    "persistent_repeat_permit",
    "persistent_repeat_permit_consumed",
})


def _receipt_payload_bytes(receipt: Any) -> bytes:
    return stable_json({
        "receipt_id": receipt.receipt_id,
        "step": receipt.step,
        "kind": receipt.kind,
        "success": receipt.success,
        "summary": receipt.summary,
        "state_change": receipt.state_change,
        "failure_class": receipt.failure_class,
        "payload": receipt.payload,
    }).encode("utf-8")


def receipt_exact_handle(receipt_id: str) -> str:
    return f"receipt:{receipt_id}"


def evidence_alias(receipt_id: str) -> str:
    digest = sha256(receipt_id.encode("utf-8")).hexdigest()[:16]
    return f"evidence:{digest}"


def _handles(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, stream in (
        ("stdout_handle", "stdout"),
        ("stderr_handle", "stderr"),
        ("file_handle", "file"),
        ("output_handle", "output"),
    ):
        handle = str(payload.get(key, "") or "").strip()
        if handle:
            row: dict[str, Any] = {"handle": handle, "stream": stream}
            size = payload.get(f"{stream}_bytes", payload.get("bytes"))
            if size not in (None, ""):
                row["bytes"] = size
            rows.append(row)
    return rows


def _originating_action_id(receipt: Any) -> str:
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    explicit = str(payload.get("action_id", "") or "").strip()
    if explicit:
        return explicit
    parts = str(receipt.receipt_id).split(":")
    for part in parts:
        if part.startswith("persistent-"):
            return part
    return ""


def _exact_access(receipt: Any) -> dict[str, Any]:
    raw = _receipt_payload_bytes(receipt)
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    return {
        "state": "receipt_handle_exact",
        "handle": receipt_exact_handle(receipt.receipt_id),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "related_handles": _handles(payload),
        "retrieval": {
            "action_kind": "read_output",
            "arguments": {"handle": receipt_exact_handle(receipt.receipt_id)},
            "paging_supported": True,
        },
    }


def _evidence_row(
    receipt: Any,
    *,
    identity: Mapping[str, Any],
    currentness: str,
) -> dict[str, Any]:
    return {
        "evidence_ref": evidence_alias(receipt.receipt_id),
        "completion_evidence_eligible": True,
        "receipt_id": receipt.receipt_id,
        "evidence_type": receipt.kind,
        "originating_action_id": _originating_action_id(receipt),
        "mechanical_description": receipt.summary,
        "success": receipt.success,
        "state_change": receipt.state_change,
        "failure_class": receipt.failure_class,
        "step": receipt.step,
        "currentness": currentness,
        "task_id": identity.get("task_id", ""),
        "run_id": identity.get("run_id", ""),
        "workspace_id": identity.get("workspace_id", ""),
        "bounded_view": _views.receipt_inline_view(receipt),
        "exact_access": _exact_access(receipt),
    }


def _primary_result_row(
    receipt: Any,
    *,
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    if is_persistent_completion_evidence(receipt):
        return _evidence_row(
            receipt, identity=identity, currentness="latest_primary_result"
        )
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    return {
        "receipt_id": receipt.receipt_id,
        "evidence_type": receipt.kind,
        "originating_action_id": _originating_action_id(receipt),
        "mechanical_description": receipt.summary,
        "success": receipt.success,
        "state_change": receipt.state_change,
        "failure_class": receipt.failure_class,
        "step": receipt.step,
        "currentness": "latest_primary_result",
        "completion_evidence_eligible": False,
        "bounded_view": _views.receipt_inline_view(receipt),
        "exact_access": _exact_access(receipt),
        "related_handles": _handles(payload),
    }


def _latest_primary_result(
    receipts: tuple[Any, ...],
    *,
    identity: Mapping[str, Any],
) -> tuple[dict[str, Any], set[str], list[dict[str, Any]]]:
    indexes = [receipt for receipt in receipts if receipt.kind == "primary_action_result_index"]
    if not indexes:
        return ({
            "status": "no_primary_action_yet",
            "outcome_receipts": [],
            "exact_access_state": "not_applicable",
        }, set(), [])
    index = indexes[-1]
    payload = index.payload if isinstance(index.payload, Mapping) else {}
    receipt_by_id = {receipt.receipt_id: receipt for receipt in receipts}
    requested = [str(item) for item in payload.get("outcome_receipt_ids", ()) or ()]
    outcomes = [receipt_by_id[item] for item in requested if item in receipt_by_id]
    rows = [
        _primary_result_row(receipt, identity=identity)
        for receipt in outcomes
    ]
    latest_evidence_rows = [
        row for row in rows if row.get("completion_evidence_eligible") is True
    ]
    latest_evidence_ids = {
        str(row.get("receipt_id", "")) for row in latest_evidence_rows
    }
    missing = [item for item in requested if item not in receipt_by_id]
    status = str(payload.get("status", "") or "")
    if missing:
        status = "missing_indexed_receipt"
    elif not outcomes:
        status = status or "missing_result_receipt"
    return ({
        "status": status or "observed",
        "index_receipt_id": index.receipt_id,
        "action_id": str(payload.get("action_id", "") or ""),
        "action_kind": str(payload.get("action_kind", "") or ""),
        "outcome_receipt_ids": requested,
        "missing_outcome_receipt_ids": missing,
        "outcome_receipts": rows,
        "exact_access_state": (
            "available" if outcomes and not missing else "incomplete"
        ),
    }, latest_evidence_ids, latest_evidence_rows)


def _mechanically_unresolved_failures(
    receipts: tuple[Any, ...],
    *,
    identity: Mapping[str, Any],
    latest_result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for key, state_key in (
        ("source_commit", "source_commit_state"),
        ("runtime_manifest_sha256", "runtime_manifest_state"),
    ):
        if not str(identity.get(key, "") or "").strip():
            facts.append({
                "kind": "source_custody_gap",
                "field": key,
                "state": identity.get(state_key, "not_supplied"),
                "authority": "runtime_identity",
            })
    if latest_result.get("exact_access_state") == "incomplete":
        facts.append({
            "kind": "latest_result_access_gap",
            "state": latest_result.get("status"),
            "authority": "primary_action_result_index",
        })

    successful_action_ids = {
        _originating_action_id(receipt)
        for receipt in receipts
        if receipt.success and _originating_action_id(receipt)
    }
    candidates = [
        receipt
        for receipt in receipts
        if not receipt.success
        and receipt.kind not in _CONTROL_KINDS
        and receipt.failure_class
    ][-12:]
    for receipt in candidates:
        action_id = _originating_action_id(receipt)
        if action_id and action_id in successful_action_ids:
            continue
        facts.append({
            "kind": "mechanical_failure",
            "receipt_id": receipt.receipt_id,
            "receipt_kind": receipt.kind,
            "failure_class": receipt.failure_class,
            "summary": receipt.summary,
            "step": receipt.step,
            "originating_action_id": action_id,
            "resolution_state": "no_later_success_for_same_action_observed",
            "exact_access": _exact_access(receipt),
        })
    return facts


def _verifier_reentry_state(ledger: Any, *, step: int) -> dict[str, Any] | None:
    all_findings = ledger.active_finding_context(step, limit=1000)
    if not all_findings:
        return None
    rows: list[dict[str, Any]] = []
    all_have_relevant_evidence = True
    for finding in all_findings:
        relevant = evidence_after_latest_verifier(ledger, finding)
        has_relevant = bool(relevant)
        all_have_relevant_evidence = all_have_relevant_evidence and has_relevant
        if len(rows) < 4:
            rows.append({
                "finding_id": str(finding.get("finding_id", "")),
                "relevant_evidence_after_latest_verifier": has_relevant,
                "relevant_evidence_receipt_ids": [
                    receipt.receipt_id for receipt in relevant[-4:]
                ],
            })
    return {
        "active_finding_count": len(all_findings),
        "projected_finding_count": len(rows),
        "all_active_findings_have_relevant_evidence": all_have_relevant_evidence,
        "submit_reentry_gate": (
            "mechanically_eligible"
            if all_have_relevant_evidence
            else "awaiting_relevant_evidence"
        ),
        "findings": rows,
        "authority": "kernel_finding_evidence_lifecycle",
        "semantic_sufficiency": "not_determined_by_this_gate",
    }


def _evidence_index(
    receipts: tuple[Any, ...],
    *,
    identity: Mapping[str, Any],
    latest_ids: set[str],
    latest_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = list(latest_rows)
    seen = set(latest_ids)
    candidates = [
        receipt
        for receipt in receipts
        if receipt.receipt_id not in seen
        and is_persistent_completion_evidence(receipt)
    ]
    for receipt in reversed(candidates):
        if len(rows) >= _MAX_EVIDENCE_ROWS:
            break
        rows.append(_evidence_row(
            receipt,
            identity=identity,
            currentness="historical_task_evidence",
        ))
        seen.add(receipt.receipt_id)
    return rows


_PERSISTENT_LINKED_HISTORY_EXCLUDED = frozenset({
    "automatic_memory_available",
    "automatic_memory_guidance",
    "automatic_memory_findings",
    "memory_loop_feedback",
    "repeat_efficiency_guidance",
    "no_progress_controls",
    "action_constraints",
    "submission_recovery_directive",
    "stuck",
    "latest_solver_transition",
})


def _persistent_submission_coherence_state(
    linked_history: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Project the canonical submission block as factual PERSISTENT control state.

    The generic ContextCompiler directive includes explanatory strategy prose and
    is intentionally excluded from PERSISTENT linked history.  PERSISTENT still needs the
    mechanical blocker, exact evidence boundary, and already-existing retrieval
    handles that can satisfy it.  This projection keeps only those facts; it does
    not choose a task action, target, or technical conclusion.
    """
    raw = linked_history.get("submission_recovery_directive")
    if not isinstance(raw, Mapping):
        return None
    reason = str(raw.get("reason_code", "") or "").strip()
    if not reason:
        return None
    allowed_routes: list[dict[str, Any]] = []
    routes = raw.get("available_direct_observation_routes")
    if isinstance(routes, (list, tuple)):
        for value in routes:
            if not isinstance(value, Mapping):
                continue
            kind = str(value.get("kind", "") or "").strip()
            arguments = value.get("arguments")
            source_receipt_id = str(value.get("source_receipt_id", "") or "").strip()
            if kind != "read_output" or not isinstance(arguments, Mapping):
                continue
            handle = str(arguments.get("handle", "") or "").strip()
            if not handle or not source_receipt_id:
                continue
            row: dict[str, Any] = {
                "kind": "read_output",
                "arguments": {"handle": handle},
                "source_receipt_id": source_receipt_id,
                "authority": "existing_execution_result_handle",
            }
            for key in ("stream", "bytes"):
                item = value.get(key)
                if item not in (None, ""):
                    row[key] = item
            allowed_routes.append(row)
    result: dict[str, Any] = {
        "source": "submission_coherence",
        "submission_allowed": bool(raw.get("submission_allowed", False)),
        "reason_code": reason,
        "detail": str(raw.get("detail", "") or "").strip(),
        "required_next_turn_kind": str(raw.get("required_next_turn_kind", "") or "").strip(),
        "forbidden_next_turn_kind": str(raw.get("forbidden_next_turn_kind", "") or "").strip(),
        "clears_only_after": str(raw.get("clears_only_after", "") or "").strip(),
        "preflight_step": raw.get("preflight_step"),
        "blocked_receipt_id": str(raw.get("blocked_receipt_id", "") or "").strip(),
        "blocked_round": raw.get("blocked_round"),
        "record_observation_is_direct_evidence": bool(
            raw.get("record_observation_is_direct_evidence", False)
        ),
        "control_plane_authority": "kernel_submission_coherence",
        "semantic_task_action_selected": False,
    }
    if allowed_routes:
        result["available_direct_observation_routes"] = allowed_routes
    return {
        key: value for key, value in result.items()
        if value not in (None, "", [], {})
    }


def _factual_persistent_linked_history(linked_history: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        str(key): value
        for key, value in linked_history.items()
        if str(key) not in _PERSISTENT_LINKED_HISTORY_EXCLUDED
    }
    pending = result.get("pending_checks")
    if isinstance(pending, list):
        result["pending_checks"] = [
            {
                str(key): value
                for key, value in row.items()
                if str(key) != "repair_hint"
            }
            if isinstance(row, Mapping) else row
            for row in pending
        ]
    open_rows = result.get("open_obligations")
    status_rows = result.get("obligation_status")
    if isinstance(open_rows, list) and isinstance(status_rows, list):
        derived_open = [
            row for row in status_rows
            if isinstance(row, Mapping) and row.get("status") != "satisfied"
        ]
        if open_rows == derived_open:
            # obligation_status is the complete authority and exactly derives
            # open_obligations. Keep one copy of each clause/status in PERSISTENT view.
            result.pop("open_obligations", None)
    result["persistent_context_boundary"] = {
        "linked_history_is_factual_projection": True,
        "kernel_strategy_guidance_exposed": False,
        "legacy_automatic_memory_exposed": False,
        "generic_stuck_judgment_exposed": False,
    }
    return result


def compile_persistent_context(
    compiled: CompiledRuntime,
    ledger: Any,
    linked_history: Mapping[str, Any],
) -> dict[str, Any]:
    """Pin PERSISTENT facts around the canonical, already-bounded context packet."""
    receipts = tuple(ledger.all_receipts())
    identity = dict(getattr(ledger, "runtime_identity", {}) or {})
    latest_result, latest_ids, latest_rows = _latest_primary_result(
        receipts,
        identity=identity,
    )
    evidence = _evidence_index(
        receipts,
        identity=identity,
        latest_ids=latest_ids,
        latest_rows=latest_rows,
    )
    findings = ledger.active_finding_context(len(receipts))
    budgets = dict(identity.get("budgets", {}) or {})
    max_steps = budgets.get("max_kernel_steps")
    if isinstance(max_steps, int) and not isinstance(max_steps, bool):
        used_turns = ledger.accounting_value("solver_provider_turns")
        budgets["used_solver_provider_turns"] = used_turns
        budgets["remaining_kernel_steps"] = max(0, max_steps - used_turns)
    else:
        budgets["remaining_kernel_steps"] = None
    capability_contract = persistent_capability_contract(compiled)
    packet = {
        "latest_primary_result": latest_result,
        "runtime_identity": identity,
        "unresolved_runtime_facts": _mechanically_unresolved_failures(
            receipts,
            identity=identity,
            latest_result=latest_result,
        ),
        "unresolved_verifier_findings": findings,
        "evidence_index": evidence,
        "available_capabilities": {
            # Exact executable ownership contract. Action kinds are the keys;
            # capability IDs are the values, so parallel copied lists add no fact.
            "action_owners": {
                action_kind: list(owners)
                for action_kind, owners in capability_contract.items()
            },
        },
        "budgets": budgets,
        "working_state": latest_persistent_working_state(ledger),
        "self_extension": helper_context(compiled, ledger),
        "linked_history": _factual_persistent_linked_history(linked_history),
    }
    submission_coherence = _persistent_submission_coherence_state(linked_history)
    if submission_coherence is not None:
        packet["submission_coherence"] = submission_coherence
    reentry_state = _verifier_reentry_state(ledger, step=len(receipts))
    if reentry_state is not None:
        packet["verifier_reentry_state"] = reentry_state
    return finalize_persistent_context_budget(packet, compiled)

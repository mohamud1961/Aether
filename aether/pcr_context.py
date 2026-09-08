"""PCR V0 projection over the canonical production ContextCompiler.

This module does not select strategy or create a second context engine. It wraps
the already-bounded canonical packet with pinned mechanical facts that PCR must
never lose: stable task-run identity, the latest Primary Agent action result,
current runtime failures/findings, visible evidence aliases, capabilities, and
hard budgets.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from . import context_views as _views
from .pcr_capabilities import pcr_capability_contract
from .pcr_context_budget import finalize_pcr_context_budget
from .finding_evidence import evidence_after_latest_verifier
from .pcr_evidence import PCR_COMPLETION_EVIDENCE_KINDS, is_pcr_completion_evidence
from .pcr_helper_tools import helper_context
from .runtime_ir import CompiledRuntime, stable_json
from .ledger import TASK_STATE_SNAPSHOT_BINDING_VERSION
from .submission_coherence import evaluate_submission_coherence, submission_recovery_directive
from .solver_facing_projection import (
    neutralize_evidence_type,
    solver_facing_completion_projection,
    solver_facing_factual_defect_projection,
)

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
    "model_verifier_result",
    "model_verifier_inspection",
    "model_verifier_error",
    "verifier_state_unavailable",
    "verifier_tooling_blocked",
    "primary_action_result_index",
    "pcr_repeat_observation",
    "pcr_repeat_permit",
    "pcr_repeat_permit_consumed",
})

# Verifier-side records are not Solver-authored current task evidence. Keep the
# legacy PCR projection untouched; native PCR excludes these from its evidence
# aliases so prior Verifier output cannot become a Solver completion citation.
_THIN_SOLVER_EXCLUDED_EVIDENCE_KINDS = frozenset({
    "model_verifier_inspection",
    "verifier_result_evidence",
    "proof_evidence_admission",
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
        if part.startswith("pcr-"):
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
        "evidence_type": neutralize_evidence_type(receipt.kind),
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
    if is_pcr_completion_evidence(receipt):
        return _evidence_row(
            receipt, identity=identity, currentness="latest_primary_result"
        )
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    return {
        "receipt_id": receipt.receipt_id,
        "evidence_type": neutralize_evidence_type(receipt.kind),
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
    if missing or not outcomes:
        status = "missing"
    elif all(receipt.success for receipt in outcomes):
        status = "succeeded"
    elif all(not receipt.success for receipt in outcomes):
        status = "failed"
    else:
        status = "mixed"
    return ({
        "status": status,
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
    superseded_failures = _kernel_validated_failure_supersessions(receipts)
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

    candidates = [
        receipt
        for receipt in receipts
        if not receipt.success
        and receipt.kind not in _CONTROL_KINDS
        and receipt.failure_class
    ][-12:]
    for receipt in candidates:
        if receipt.receipt_id in superseded_failures:
            continue
        action_id = _originating_action_id(receipt)
        facts.append({
            "kind": "mechanical_failure",
            "receipt_id": receipt.receipt_id,
            "receipt_kind": receipt.kind,
            "failure_class": receipt.failure_class,
            "summary": receipt.summary,
            "step": receipt.step,
            "originating_action_id": action_id,
            # Receipt identity is shared by model decisions, accounting and
            # task outcomes. A later success with that identity is therefore
            # not evidence that this failed task observation was repaired.
            # Keep the failure until a future kernel-owned supersession record
            # can bind a relevant changed state to a successful task result.
            "resolution_state": "no_kernel_validated_supersession_observed",
            "exact_access": _exact_access(receipt),
        })
    return facts


def _kernel_validated_failure_supersessions(receipts: tuple[Any, ...]) -> set[str]:
    """Return failures with a complete kernel-owned repair lineage.

    A successful accounting/control receipt is never a resolution.  The only
    accepted link is a kernel-issued record joining a failed task result to a
    later successful task result of the same action signature after its state
    fingerprint changed.
    """
    by_id = {str(receipt.receipt_id): receipt for receipt in receipts}
    resolved: set[str] = set()
    for link in receipts:
        if link.kind != "pcr_task_failure_supersession" or link.success is not True:
            continue
        payload = link.payload if isinstance(link.payload, Mapping) else {}
        source_id = str(payload.get("source_failure_receipt_id", ""))
        successor_id = str(payload.get("successor_receipt_id", ""))
        source = by_id.get(source_id)
        successor = by_id.get(successor_id)
        if (
            not source_id
            or source is None
            or successor is None
            or source.success is True
            or not source.failure_class
            or source.kind not in PCR_COMPLETION_EVIDENCE_KINDS
            or successor.success is not True
            or successor.kind not in PCR_COMPLETION_EVIDENCE_KINDS
            or str(payload.get("authority", ""))
            != "kernel_observed_same_action_after_changed_state"
            or not str(payload.get("action_signature", ""))
            or not str(payload.get("source_relevant_state_fingerprint", ""))
            or not str(payload.get("successor_relevant_state_fingerprint", ""))
            or str(payload.get("source_relevant_state_fingerprint", ""))
            == str(payload.get("successor_relevant_state_fingerprint", ""))
        ):
            continue
        resolved.add(source_id)
    return resolved


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
            projected = solver_facing_completion_projection([dict(finding)], current_step=step)
            row = projected[0] if projected else {}
            rows.append({
                "finding_id": row.get("finding_id", finding.get("finding_id","")),
                "summary": row.get("summary", ""),
                "verdict": row.get("verdict", ""),
                "relevant_evidence_after_latest_review": has_relevant,
                "relevant_evidence_receipt_ids": [
                    r.receipt_id for r in relevant[-4:]
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
        and is_pcr_completion_evidence(receipt)
        and str(getattr(receipt, "kind", "")) not in _THIN_SOLVER_EXCLUDED_EVIDENCE_KINDS
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


_PCR_LINKED_HISTORY_EXCLUDED = frozenset({
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


def _pcr_submission_coherence_state(
    linked_history: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Project the canonical submission block as factual PCR control state.

    The generic ContextCompiler directive includes explanatory strategy prose and
    is intentionally excluded from PCR linked history.  PCR still needs the
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
        "preflight_step": raw.get("preflight_step"),
        "blocked_receipt_id": str(raw.get("blocked_receipt_id", "") or "").strip(),
        "blocked_round": raw.get("blocked_round"),
        "control_plane_authority": "kernel_submission_coherence",
        "semantic_task_action_selected": False,
    }
    if allowed_routes:
        result["available_direct_observation_routes"] = allowed_routes
    return {
        key: value for key, value in result.items()
        if value not in (None, "", [], {})
    }


def _factual_pcr_linked_history(
    linked_history: Mapping[str, Any],
) -> dict[str, Any]:
    excluded = set(_PCR_LINKED_HISTORY_EXCLUDED)
    excluded.update({
        "active_completion_findings", "open_completion_findings",
        "open_obligations", "obligation_status", "pending_checks",
        "verifier", "repair_instruction", "finding",
    })
    result = {
        str(key): value
        for key, value in linked_history.items()
        if str(key) not in excluded
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
            # open_obligations. Keep one copy of each clause/status in PCR view.
            result.pop("open_obligations", None)
    result["pcr_context_boundary"] = {
        "linked_history_is_factual_projection": True,
        "kernel_strategy_guidance_exposed": False,
        "legacy_automatic_memory_exposed": False,
        "generic_stuck_judgment_exposed": False,
    }
    return result



def _direct_submission_recovery(ledger: Any) -> dict[str, Any] | None:
    """Build only the factual submission-coherence state PCR actually exposes."""
    receipts = list(ledger.all_receipts())
    next_step = max((receipt.step for receipt in receipts), default=-1) + 1
    coherence = evaluate_submission_coherence(ledger, current_step=next_step)
    if coherence.allowed:
        return None
    blocks = [
        receipt for receipt in receipts
        if receipt.kind == "submission_coherence_blocked" and not receipt.success
    ]
    latest_block = blocks[-1] if blocks else None
    block_payload = (
        latest_block.payload
        if latest_block is not None and isinstance(latest_block.payload, Mapping)
        else {}
    )
    raw = submission_recovery_directive(coherence.reason_code, coherence.detail) | {
        "preflight_step": next_step,
        "blocked_receipt_id": "" if latest_block is None else latest_block.receipt_id,
        "blocked_round": block_payload.get("blocked_round"),
    }
    if coherence.reason_code == "unobserved_state_change":
        routes = _views.submission_observation_routes(
            ledger,
            progress_receipt_id=coherence.latest_progress_receipt_id,
        )
        if routes:
            raw["available_direct_observation_routes"] = routes
    return raw


def _direct_factual_linked_history(
    ledger: Any,
    alerts: list[Any],
) -> dict[str, Any]:
    """Derive the selected production linked-history view directly from authorities.

    This intentionally contains no memory, stuck/replan judgment, recovery prose,
    candidate ranking, semantic obligation synthesis, or task-strategy field.
    """
    receipts = tuple(ledger.all_receipts())
    linked: dict[str, Any] = {}
    alert_rows = [
        {
            "code": alert.code,
            "message": alert.message,
            "severity": alert.severity,
            "blocker_code": alert.blocker_code,
        }
        for alert in alerts
    ]
    if alert_rows:
        linked["monitor_alerts"] = alert_rows
    live = ledger.live_processes()
    if live:
        linked["live_processes"] = live
    artifacts = sorted(ledger.current_artifacts())
    if artifacts:
        linked["artifacts_present"] = artifacts

    handles: list[dict[str, Any]] = []
    for receipt in receipts:
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        for key, stream, size_key in (
            ("stdout_handle", "stdout", "stdout_bytes"),
            ("stderr_handle", "stderr", "stderr_bytes"),
            ("file_handle", "file", "bytes"),
        ):
            handle = str(payload.get(key, "") or "").strip()
            if not handle:
                continue
            row: dict[str, Any] = {
                "handle": handle,
                "receipt_id": receipt.receipt_id,
                "stream": stream,
                "bytes": payload.get(size_key, 0),
            }
            if stream == "file" and payload.get("path"):
                row["path"] = payload.get("path")
            handles.append(row)
    if handles:
        linked["output_handles"] = handles[-16:]

    failures = [
        receipt for receipt in receipts
        if not receipt.success and receipt.kind not in _CONTROL_KINDS and receipt.failure_class
    ]
    if failures:
        linked["latest_failure"] = _views.receipt_inline_view(failures[-1])
    failed_checks = [
        _views.receipt_inline_view(receipt)
        for receipt in receipts
        if receipt.kind == "check_result" and not receipt.success
    ][-8:]
    if failed_checks:
        linked["failed_checks"] = failed_checks

    recovery = _direct_submission_recovery(ledger)
    if recovery is not None:
        linked["submission_recovery_directive"] = recovery
    return _factual_pcr_linked_history(linked)


def _selected_production_projection(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the frozen minimal-v1 production projection without research envs."""
    protected = (
        "latest_primary_result",
        "runtime_identity",
        "task_state_generation",
        "task_state_snapshot_digest",
        "task_state_snapshot_known",
        "snapshot_binding_version",
        "unresolved_runtime_facts",
        "open_completion_findings",
        "available_capabilities",
        "budgets",
        "self_extension",
        "submission_coherence",
        "submit_reentry_gate",
        "history_access",
    )
    result = {key: packet[key] for key in protected if key in packet}
    evidence = packet.get("evidence_index")
    if isinstance(evidence, list):
        result["evidence_index"] = []
        for value in evidence:
            if not isinstance(value, Mapping):
                result["evidence_index"].append(value)
                continue
            row = dict(value)
            if str(row.get("currentness") or "") == "historical_task_evidence":
                row.pop("bounded_view", None)
            result["evidence_index"].append(row)
    linked = packet.get("linked_history")
    if isinstance(linked, Mapping):
        keep = (
            "obligation_status",
            "monitor_alerts",
            "live_processes",
            "artifacts_present",
            "pending_checks",
            "output_handles",
            "latest_failure",
            "failed_checks",
            "pcr_context_boundary",
        )
        result["linked_history"] = {key: linked[key] for key in keep if key in linked}
    result["context_projection"] = {
        "schema_version": "aether.postmerge_context_projection.v1",
        "mode": "minimal_v1",
        "protected_authority_envelope_preserved": True,
        "historical_completion_evidence": "exact_access_metadata_without_redundant_bounded_view",
        "explicit_retrieval_handles_preserved": True,
        "semantic_summary_added": False,
    }
    return result


def build_pcr_context(
    compiled: CompiledRuntime,
    ledger: Any,
    alerts: list[Any],
) -> dict[str, Any]:
    """Build the selected production PCR packet directly from factual authorities."""
    packet = compile_pcr_context(
        compiled,
        ledger,
        _direct_factual_linked_history(ledger, alerts),
    )
    return _selected_production_projection(packet)

def compile_pcr_context(
    compiled: CompiledRuntime,
    ledger: Any,
    linked_history: Mapping[str, Any],
) -> dict[str, Any]:
    """Pin PCR facts around the canonical, already-bounded context packet."""
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
    raw_findings = ledger.active_finding_context(len(receipts))
    witness_handles: dict[str, str] = {}
    for receipt in receipts:
        if receipt.kind != "completion_finding_witness" or not receipt.success:
            continue
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        finding_id = str(payload.get("finding_id", "") or "").strip()
        if finding_id:
            witness_handles[finding_id] = receipt_exact_handle(receipt.receipt_id)
    findings = list(solver_facing_factual_defect_projection(
        raw_findings,
        current_step=len(receipts),
        current_task_state_generation=ledger.task_state_generation(),
        witness_handles=witness_handles,
    ))
    budgets = dict(identity.get("budgets", {}) or {})
    dynamic_budget_state = getattr(ledger, "runtime_budget_state", {})
    if isinstance(dynamic_budget_state, Mapping):
        budgets.update(dict(dynamic_budget_state))
    max_steps = budgets.get("max_kernel_steps")
    if isinstance(max_steps, int) and not isinstance(max_steps, bool):
        used_turns = ledger.accounting_value("solver_provider_turns")
        budgets["used_solver_provider_turns"] = used_turns
        budgets["remaining_kernel_steps"] = max(0, max_steps - used_turns)
    else:
        budgets["remaining_kernel_steps"] = None
    capability_contract = pcr_capability_contract(
        compiled,
        runtime_capability_ids=tuple(
            getattr(ledger, "runtime_capabilities", set()) or ()
        ),
    )
    packet = {
        "latest_primary_result": latest_result,
        "runtime_identity": identity,
        "unresolved_runtime_facts": _mechanically_unresolved_failures(
            receipts,
            identity=identity,
            latest_result=latest_result,
        ),
        "open_completion_findings": findings,
        "evidence_index": evidence,
        "available_capabilities": {"action_kinds": sorted(capability_contract)},
        "budgets": budgets,
        "self_extension": helper_context(compiled, ledger),
        "history_access": {
            "action": "query_history",
            "match_mode": "case_insensitive_literal_substring",
            "ordering": "newest_first",
            "semantic_ranking": False,
            "empty_query_lists_recent_receipts": True,
            "exact_receipts_via": "read_output receipt:<receipt_id>",
            "exact_streams_via": "read_output stdout_handle/stderr_handle",
        },
        "linked_history": _factual_pcr_linked_history(linked_history),
    }
    # Canonical submission validation always needs exact snapshot custody.
    packet.update({
        "task_state_generation": ledger.task_state_generation(),
        "task_state_snapshot_digest": ledger.task_state_snapshot_digest(),
        "task_state_snapshot_known": ledger.task_state_snapshot_known(),
        "snapshot_binding_version": TASK_STATE_SNAPSHOT_BINDING_VERSION,
        "task_state_snapshot_authority": "execution_ledger_observed_boundaries",
    })
    submission_coherence = _pcr_submission_coherence_state(linked_history)
    if submission_coherence is not None:
        packet["submission_coherence"] = submission_coherence
    return finalize_pcr_context_budget(packet, compiled)

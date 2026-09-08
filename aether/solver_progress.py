"""Deterministic Solver action-progress signals.

The kernel records objective properties of one decision/result boundary. It
never judges whether an arbitrary technical conclusion is semantically correct.
"""
from __future__ import annotations

from typing import Iterable

from .ledger import ExecutionLedger, Receipt
from .observation_batch import mutation_generation
from .runtime_ir import ActionRequest

_ANCILLARY_KINDS = frozenset({
    "runtime_accounting",
    "solver_decision_state",
    "automatic_memory",
    "automatic_memory_advisory",
    "pcr_repeat_observation",
    "pcr_repeat_permit",
    "pcr_repeat_permit_consumed",
})
_EVIDENCE_KINDS = frozenset({
    "read_file", "read_file_page", "read_output", "grep_output",
    "run_command", "artifact_inspection",
    "query_artifact_history", "inspect_diff", "service_probe",
    "process_launch", "process_stop", "job_probe", "check_result", "schema_validation",
})
_VERIFICATION_KINDS = frozenset({
    "check_result", "schema_validation", "service_probe", "job_probe",
})
_POLICY_FAILURE_KINDS = frozenset({
    "action_validation", "safety_block", "integrity_block",
    "action_budget_refused", "automatic_memory_block", "no_progress_control",
    "pcr_repeat_block",
})


def direct_result_receipts(receipts: Iterable[Receipt]) -> tuple[Receipt, ...]:
    rows: list[Receipt] = []
    for receipt in receipts:
        if receipt.kind in _ANCILLARY_KINDS:
            continue
        if receipt.kind == "no_progress_control":
            consequence = str((receipt.payload or {}).get("consequence", ""))
            if consequence != "soft_block":
                continue
        rows.append(receipt)
    return tuple(rows)


def _has_new_evidence(receipt: Receipt) -> bool:
    if not receipt.success or receipt.kind not in _EVIDENCE_KINDS:
        return False
    payload = receipt.payload or {}
    if bool(payload.get("no_new_evidence")):
        return False
    return True


def build_progress_receipt(
    action: ActionRequest,
    *,
    step: int,
    step_receipts: Iterable[Receipt],
    ledger: ExecutionLedger,
) -> Receipt:
    all_rows = tuple(step_receipts)
    results = direct_result_receipts(all_rows)
    state_change_count = sum(bool(row.state_change) for row in results)
    task_world_mutation_uncertain_count = sum(
        1
        for row in results
        if isinstance((row.payload or {}).get("state_delta"), dict)
        and str((row.payload or {}).get("state_delta", {}).get("mutation_detection_status", "")).strip()
        in {"coarse", "truncated", "unavailable"}
    )
    successful_result_count = sum(bool(row.success) for row in results)
    failed_result_count = len(results) - successful_result_count
    evidence_rows = tuple(row for row in results if _has_new_evidence(row))
    verification_rows = tuple(
        row for row in results
        if row.success and row.kind in _VERIFICATION_KINDS
    )
    repeat_rows = tuple(
        row for row in results
        if row.kind in {"automatic_memory_block", "pcr_repeat_block"}
        or (
            row.kind == "no_progress_control"
            and str((row.payload or {}).get("consequence", "")) == "soft_block"
        )
    )
    repeat_reuse_rows = tuple(
        row for row in results if row.kind == "pcr_repeat_reuse"
    )
    policy_failure_rows = tuple(
        row for row in results if row.kind in _POLICY_FAILURE_KINDS
    )
    dispatch_performed = any(
        row.kind == "runtime_accounting"
        and str((row.payload or {}).get("event", "")) == "accepted_for_dispatch"
        for row in all_rows
    )

    signals: list[str] = []
    if repeat_rows:
        signals.append("equivalent_repeat")
    if repeat_reuse_rows:
        signals.append("equivalent_repeat_reused")
    if state_change_count:
        signals.append("state_change")
    if task_world_mutation_uncertain_count:
        signals.append("task_world_mutation_uncertain")
    if evidence_rows:
        signals.append("new_evidence")
    if verification_rows:
        signals.extend(("verification", "requirement_evidence"))
    if failed_result_count and not repeat_rows:
        signals.append("failure_observed")
    if policy_failure_rows:
        signals.append("protocol_or_policy_failure")
    if not signals:
        signals.append("no_relevant_progress")

    if repeat_rows:
        classification = "equivalent_repeat_blocked"
    elif repeat_reuse_rows:
        classification = "equivalent_repeat_reused"
    elif state_change_count:
        classification = "state_changed"
    elif successful_result_count and failed_result_count:
        classification = "mixed_results_no_state_change"
    elif failed_result_count:
        classification = "unsuccessful_result_no_state_change"
    elif successful_result_count and task_world_mutation_uncertain_count:
        classification = "successful_result_task_world_mutation_uncertain"
    elif successful_result_count:
        classification = "successful_result_no_state_change"
    else:
        classification = "no_direct_result"

    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:solver_progress_assessment",
        step=step,
        kind="solver_progress_assessment",
        success=True,
        summary=f"mechanical action-result summary: {classification}",
        payload={
            "classification": classification,
            "progress_signals": signals,
            "action_id": action.action_id,
            "action_kind": action.kind,
            "result_receipt_ids": [row.receipt_id for row in results],
            "result_count": len(results),
            "successful_result_count": successful_result_count,
            "failed_result_count": failed_result_count,
            "state_change_count": state_change_count,
            "task_world_mutation_uncertain_count": task_world_mutation_uncertain_count,
            "task_world_mutation_observability": (
                "observed_change"
                if state_change_count
                else "uncertain"
                if task_world_mutation_uncertain_count
                else "observed_no_change"
            ),
            "new_evidence_count": len(evidence_rows),
            "verification_count": len(verification_rows),
            "equivalent_repeat": bool(repeat_rows),
            "no_relevant_progress": signals == ["no_relevant_progress"],
            "dispatch_performed": dispatch_performed,
            "mutation_generation": mutation_generation(ledger),
            "interpretation_authority": "solver",
        },
    )

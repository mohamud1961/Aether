"""Mechanical PERSISTENT V0 bridge from independent Verifier evidence to task clauses.

PERSISTENT deliberately has no Architect-authored proof contract. Its immutable task
contract therefore needs a narrow completion bridge: a current Primary Agent
claim plus a completed independent Verifier result whose clause coverage cites
current, registered, proof-eligible read-only inspections. The bridge validates
only identity, freshness, coverage, and provenance; it does not judge semantics.
"""
from __future__ import annotations

from typing import Any

from .inspection_registry import inspection_records_by_id
from .ledger import ExecutionLedger, Receipt
from .proof_contract import EVIDENCE_STRENGTH


def _strength(value: str) -> int:
    return EVIDENCE_STRENGTH.get(str(value or "").strip(), -1)


def _failure_receipt(
    *,
    step: int,
    code: str,
    detail: str,
    payload: dict[str, Any] | None = None,
) -> Receipt:
    return Receipt(
        receipt_id=f"step-{step}:persistent_verifier_clause_admission:{code}",
        step=step,
        kind="persistent_verifier_clause_admission",
        success=False,
        summary=detail,
        failure_class=code,
        payload=dict(payload or {}),
    )


def admit_persistent_completed_task_clauses(
    ledger: ExecutionLedger,
    *,
    result: Any,
    compiled: Any,
    step: int,
    packet_signature: str,
) -> tuple[Receipt, ...]:
    """Admit current independent Verifier coverage for PERSISTENT raw-task clauses."""
    if str(getattr(compiled, "solver_turn_protocol", "")) != "persistent_v0":
        return ()
    if str(getattr(result, "verdict", "")) != "completed":
        return ()

    task_contract = getattr(compiled, "task_contract", None)
    expected = set(getattr(task_contract, "clause_ids", ()) or ())
    if not expected:
        receipt = _failure_receipt(
            step=step,
            code="persistent_task_contract_missing",
            detail="PERSISTENT completed Verifier result had no immutable task clauses to admit.",
        )
        ledger.record(receipt)
        return (receipt,)

    claim = ledger.latest_receipt("primary_submission_claim")
    current_generation = ledger.task_state_generation()
    if claim is None or not claim.success:
        receipt = _failure_receipt(
            step=step,
            code="persistent_current_claim_missing",
            detail="PERSISTENT Verifier completed without a current accepted Primary Agent claim.",
        )
        ledger.record(receipt)
        return (receipt,)
    claim_payload = claim.payload if isinstance(claim.payload, dict) else {}
    try:
        claim_generation = int(claim_payload.get("task_state_generation", -1))
    except (TypeError, ValueError):
        claim_generation = -1
    if claim_generation != current_generation:
        receipt = _failure_receipt(
            step=step,
            code="persistent_claim_state_stale",
            detail="PERSISTENT completion claim was not bound to the current task-state generation.",
            payload={
                "claim_receipt_id": claim.receipt_id,
                "claim_task_state_generation": claim_generation,
                "current_task_state_generation": current_generation,
            },
        )
        ledger.record(receipt)
        return (receipt,)

    records = inspection_records_by_id(ledger)
    coverage: dict[str, set[str]] = {clause_id: set() for clause_id in expected}
    evidence_classes: dict[str, set[str]] = {clause_id: set() for clause_id in expected}
    actual_evidence_classes: dict[str, set[str]] = {clause_id: set() for clause_id in expected}
    for entry in tuple(getattr(result, "completion_evidence", ()) or ()):
        clause_ids = {
            str(item).strip()
            for item in tuple(getattr(entry, "clause_ids", ()) or ())
            if str(item).strip()
        }
        refs = tuple(
            str(item).strip()
            for item in tuple(getattr(entry, "inspection_refs", ()) or ())
            if str(item).strip()
        )
        evidence_class = str(getattr(entry, "evidence_class", "")).strip()
        if not refs or not evidence_class:
            continue
        valid_refs: set[str] = set()
        actual_classes_for_entry: list[str] = []
        entry_provenance_valid = True
        for ref in refs:
            inspection = records.get(ref)
            if inspection is None or not inspection.success:
                entry_provenance_valid = False
                break
            payload = inspection.payload if isinstance(inspection.payload, dict) else {}
            try:
                generation_matches = int(payload.get("task_state_generation", -1)) == current_generation
            except (TypeError, ValueError):
                generation_matches = False
            if not generation_matches:
                entry_provenance_valid = False
                break
            if str(payload.get("packet_signature", "")) != packet_signature:
                entry_provenance_valid = False
                break
            if not bool(payload.get("eligible_for_proof", False)):
                entry_provenance_valid = False
                break
            actual_class = str(payload.get("actual_evidence_class", "")).strip()
            if _strength(actual_class) < 0:
                entry_provenance_valid = False
                break
            valid_refs.add(ref)
            actual_classes_for_entry.append(actual_class)
        # Composite completion evidence can combine weak source reads with a
        # strong independent execution.  All cited refs must remain current,
        # successful, proof-eligible provenance, but the declared evidence
        # class is bounded by the strongest valid cited route.  This matches
        # validate_compiled_evidence() and prevents weak supporting reads from
        # discarding an otherwise valid composite proof.
        if not entry_provenance_valid or not valid_refs or valid_refs != set(refs):
            continue
        strongest_actual = max((_strength(item) for item in actual_classes_for_entry), default=-1)
        if _strength(evidence_class) > strongest_actual:
            continue
        for clause_id in clause_ids & expected:
            coverage[clause_id].update(valid_refs)
            evidence_classes[clause_id].add(evidence_class)
            for ref in valid_refs:
                payload = records[ref].payload if isinstance(records[ref].payload, dict) else {}
                actual_evidence_classes[clause_id].add(str(payload.get("actual_evidence_class", "")).strip())

    missing = sorted(clause_id for clause_id in expected if not coverage[clause_id])
    if missing:
        receipt = _failure_receipt(
            step=step,
            code="persistent_verifier_clause_coverage_incomplete",
            detail=(
                "PERSISTENT completed Verifier result did not provide current registered "
                "inspection coverage for every raw-task clause: " + ", ".join(missing)
            ),
            payload={
                "expected_clause_ids": sorted(expected),
                "covered_clause_ids": sorted(expected - set(missing)),
                "missing_clause_ids": missing,
                "claim_receipt_id": claim.receipt_id,
                "packet_signature": packet_signature,
                "task_state_generation": current_generation,
            },
        )
        ledger.record(receipt)
        return (receipt,)

    admitted: list[Receipt] = []
    for clause_id in sorted(expected):
        receipt = Receipt(
            receipt_id=f"step-{step}:persistent_verifier_clause_admission:{clause_id}",
            step=step,
            kind="persistent_verifier_clause_admission",
            success=True,
            summary=f"admitted independent current Verifier evidence for PERSISTENT clause {clause_id}",
            payload={
                "clause_id": clause_id,
                "claim_receipt_id": claim.receipt_id,
                "claim_evidence_set_sha256": str(claim_payload.get("evidence_set_sha256", "")),
                "inspection_refs": sorted(coverage[clause_id]),
                "evidence_classes": sorted(evidence_classes[clause_id]),
                "actual_evidence_classes": sorted(actual_evidence_classes[clause_id]),
                "packet_signature": packet_signature,
                "task_state_generation": current_generation,
                "semantic_sufficiency_judged_by_kernel": False,
                "admission_authority": "current_independent_verifier_clause_coverage",
            },
        )
        ledger.record(receipt)
        ledger.mark_obligation_satisfied(clause_id, receipt.receipt_id)
        admitted.append(receipt)
    return tuple(admitted)

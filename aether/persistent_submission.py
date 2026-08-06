"""Mechanical PERSISTENT V0 completion-claim and evidence-reference binding."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from .ledger import ExecutionLedger, Receipt
from .persistent_context import evidence_alias, receipt_exact_handle
from .persistent_evidence import is_persistent_completion_evidence
from .runtime_ir import SolverTurn, stable_json
from .submission_coherence import SubmissionCoherenceDecision


@dataclass(frozen=True)
class PCRSubmissionBinding:
    claim: str
    evidence_refs: tuple[str, ...]
    receipt_ids: tuple[str, ...]
    evidence_set_sha256: str
    task_state_generation: int
    context_identity: Mapping[str, Any]
    evidence_roles: tuple[str, ...] = ()
    evidence_generations: tuple[int | None, ...] = ()


def _rejected(code: str, detail: str) -> tuple[SubmissionCoherenceDecision, None]:
    return SubmissionCoherenceDecision(False, code, detail), None


def validate_persistent_submission_binding(
    turn: SolverTurn,
    context_packet: Mapping[str, Any],
    ledger: ExecutionLedger,
    *,
    current_step: int,
) -> tuple[SubmissionCoherenceDecision, PCRSubmissionBinding | None]:
    """Resolve only evidence aliases visible in the exact current context."""
    refs = tuple(str(item).strip() for item in turn.evidence_refs)
    if not turn.claim.strip():
        return _rejected("submission_claim_missing", "The completion claim is empty.")
    if not refs:
        return _rejected(
            "submission_evidence_missing",
            "PERSISTENT completion claims require at least one cited evidence reference.",
        )
    if any(not item for item in refs):
        return _rejected(
            "submission_evidence_reference_invalid",
            "Evidence references must be non-empty aliases from the current context.",
        )
    if len(set(refs)) != len(refs):
        return _rejected(
            "duplicate_evidence_reference",
            "The completion claim repeats the same evidence alias.",
        )

    identity = dict(context_packet.get("runtime_identity", {}) or {})
    ledger_identity = dict(getattr(ledger, "runtime_identity", {}) or {})
    if identity != ledger_identity:
        return _rejected(
            "submission_context_identity_mismatch",
            "The current context identity does not match the canonical task-run ledger identity.",
        )
    rows = context_packet.get("evidence_index", ())
    if not isinstance(rows, list):
        return _rejected(
            "submission_evidence_index_missing",
            "The current PERSISTENT context did not expose a usable evidence index.",
        )
    visible: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        alias = str(row.get("evidence_ref", "") or "").strip()
        if alias:
            visible[alias] = row

    receipts = {receipt.receipt_id: receipt for receipt in ledger.all_receipts()}
    resolved: list[Receipt] = []
    for ref in refs:
        row = visible.get(ref)
        if row is None:
            return _rejected(
                "evidence_reference_not_current_context",
                f"Evidence alias {ref!r} was not visible in the current context packet.",
            )
        receipt_id = str(row.get("receipt_id", "") or "").strip()
        receipt = receipts.get(receipt_id)
        if receipt is None:
            return _rejected(
                "evidence_receipt_missing",
                f"Evidence alias {ref!r} resolves to a missing receipt.",
            )
        if ref != evidence_alias(receipt_id):
            return _rejected(
                "evidence_alias_binding_mismatch",
                f"Evidence alias {ref!r} does not match its canonical receipt binding.",
            )
        if receipt.step >= current_step:
            return _rejected(
                "future_evidence_reference",
                f"Evidence alias {ref!r} was not available before the submission turn.",
            )
        for key in ("task_id", "run_id", "workspace_id"):
            if row.get(key, "") != identity.get(key, ""):
                return _rejected(
                    "evidence_lineage_mismatch",
                    f"Evidence alias {ref!r} has a different {key}.",
                )
        if str(row.get("evidence_type", "") or "") != receipt.kind:
            return _rejected(
                "evidence_type_binding_mismatch",
                f"Evidence alias {ref!r} has a different receipt type.",
            )
        if row.get("completion_evidence_eligible") is not True:
            return _rejected(
                "evidence_not_admissible_for_completion",
                f"Evidence alias {ref!r} was not admitted as task completion evidence.",
            )
        if not is_persistent_completion_evidence(receipt):
            return _rejected(
                "evidence_not_admissible_for_completion",
                f"Receipt kind {receipt.kind!r} cannot support a PERSISTENT completion claim.",
            )
        resolved.append(receipt)

    current_generation = ledger.task_state_generation()
    evidence_generations = tuple(
        ledger.receipt_task_state_generation(receipt.receipt_id)
        for receipt in resolved
    )
    evidence_roles: list[str] = []
    for ref, generation in zip(refs, evidence_generations):
        if generation is None or generation > current_generation:
            return _rejected(
                "evidence_stale",
                (
                    f"Evidence alias {ref!r} has invalid task-state generation "
                    f"{generation}; current generation is {current_generation}."
                ),
            )
        evidence_roles.append(
            "current_anchor" if generation == current_generation else "historical_support"
        )
    if "current_anchor" not in evidence_roles:
        return _rejected(
            "evidence_stale",
            (
                "PERSISTENT completion claims require at least one current task-state evidence anchor; "
                "older same-run evidence may support historical/comparative facts only."
            ),
        )

    receipt_ids = tuple(receipt.receipt_id for receipt in resolved)
    evidence_set_hash = sha256(stable_json({
        "claim": turn.claim,
        "evidence_refs": refs,
        "receipt_ids": receipt_ids,
        "task_id": identity.get("task_id", ""),
        "run_id": identity.get("run_id", ""),
        "workspace_id": identity.get("workspace_id", ""),
        "task_state_generation": ledger.task_state_generation(),
    }).encode("utf-8")).hexdigest()
    return SubmissionCoherenceDecision(True), PCRSubmissionBinding(
        claim=turn.claim,
        evidence_refs=refs,
        receipt_ids=receipt_ids,
        evidence_set_sha256=evidence_set_hash,
        task_state_generation=ledger.task_state_generation(),
        context_identity=identity,
        evidence_roles=tuple(evidence_roles),
        evidence_generations=evidence_generations,
    )


def record_persistent_submission_claim(
    ledger: ExecutionLedger,
    *,
    step: int,
    binding: PCRSubmissionBinding,
) -> Receipt:
    """Persist one external CLAIM bound only to cited same-run DID/SAW."""
    claim_id = f"claim:{binding.evidence_set_sha256[:20]}"
    receipt = Receipt(
        receipt_id=f"step-{step}:primary_submission_claim:{claim_id}",
        step=step,
        kind="primary_submission_claim",
        success=True,
        summary=binding.claim,
        payload={
            "claim_id": claim_id,
            "claim": binding.claim,
            "evidence_refs": list(binding.evidence_refs),
            "evidence_receipt_ids": list(binding.receipt_ids),
            "evidence_bindings": [
                {
                    "evidence_ref": evidence_ref,
                    "receipt_id": receipt_id,
                    "role": role,
                    "task_state_generation": generation,
                }
                for evidence_ref, receipt_id, role, generation in zip(
                    binding.evidence_refs,
                    binding.receipt_ids,
                    binding.evidence_roles,
                    binding.evidence_generations,
                )
            ],
            "current_anchor_count": sum(1 for role in binding.evidence_roles if role == "current_anchor"),
            "historical_support_count": sum(1 for role in binding.evidence_roles if role == "historical_support"),
            "evidence_set_sha256": binding.evidence_set_sha256,
            "task_state_generation": binding.task_state_generation,
            "task_id": binding.context_identity.get("task_id", ""),
            "run_id": binding.context_identity.get("run_id", ""),
            "workspace_id": binding.context_identity.get("workspace_id", ""),
            "evidence_exact_handles": [
                receipt_exact_handle(receipt_id) for receipt_id in binding.receipt_ids
            ],
            "claim_authority": "primary_agent_external_claim",
            "semantic_sufficiency_judged_by_kernel": False,
        },
    )
    ledger.record(receipt)
    return receipt

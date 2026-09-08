"""Mechanical PCR V0 completion-claim and evidence-reference binding."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from .ledger import (
    TASK_STATE_SNAPSHOT_BINDING_VERSION,
    ExecutionLedger,
    Receipt,
)
from .pcr_context import evidence_alias, receipt_exact_handle
from .pcr_evidence import is_pcr_completion_evidence
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
    task_state_snapshot_digest: str = ""
    task_state_snapshot_known: bool = True


def _rejected(code: str, detail: str) -> tuple[SubmissionCoherenceDecision, None]:
    return SubmissionCoherenceDecision(False, code, detail), None


def validate_pcr_submission_binding(
    turn: SolverTurn,
    context_packet: Mapping[str, Any],
    ledger: ExecutionLedger,
    *,
    current_step: int,
    strict_snapshot_binding: bool = False,
) -> tuple[SubmissionCoherenceDecision, PCRSubmissionBinding | None]:
    """Resolve only evidence aliases visible in the exact current context."""
    refs = tuple(str(item).strip() for item in turn.evidence_refs)
    if not turn.claim.strip():
        return _rejected("submission_claim_missing", "The completion claim is empty.")
    if not refs:
        return _rejected(
            "submission_evidence_missing",
            "PCR completion claims require at least one cited evidence reference.",
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
    context_snapshot = ""
    if strict_snapshot_binding:
        if str(context_packet.get("snapshot_binding_version", "")).strip() != TASK_STATE_SNAPSHOT_BINDING_VERSION:
            return _rejected(
                "submission_snapshot_schema_invalid",
                "The current context does not use the canonical task-state snapshot schema.",
            )
        context_snapshot = str(context_packet.get("task_state_snapshot_digest", "")).strip()
        if not context_snapshot:
            return _rejected(
                "submission_snapshot_unknown",
                "The current context does not contain a task-state snapshot digest.",
            )
        try:
            context_generation = int(context_packet.get("task_state_generation", -1))
        except (TypeError, ValueError):
            context_generation = -1
        if context_generation != ledger.task_state_generation():
            return _rejected(
                "submission_context_snapshot_stale",
                "The current context is bound to an older task-state generation.",
            )
        if context_snapshot != ledger.task_state_snapshot_digest():
            return _rejected(
                "submission_context_snapshot_stale",
                "The current context is bound to an older task-state snapshot.",
            )
    rows = context_packet.get("evidence_index", ())
    if not isinstance(rows, list):
        return _rejected(
            "submission_evidence_index_missing",
            "The current PCR context did not expose a usable evidence index.",
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
        if strict_snapshot_binding and not ledger.receipt_payload_is_intact(receipt):
            return _rejected(
                "evidence_payload_drift",
                f"Evidence alias {ref!r} resolves to a receipt whose payload changed after recording.",
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
        eligible = row.get("completion_evidence_eligible") is True
        if strict_snapshot_binding:
            eligible = eligible or row.get("task_evidence_candidate") is True
        if not eligible:
            return _rejected(
                "evidence_not_admissible_for_completion",
                (
                    f"Evidence alias {ref!r} was not a current task-evidence candidate."
                    if strict_snapshot_binding
                    else f"Evidence alias {ref!r} was not admitted as task completion evidence."
                ),
            )
        if not is_pcr_completion_evidence(receipt):
            return _rejected(
                "evidence_not_admissible_for_completion",
                f"Receipt kind {receipt.kind!r} cannot support a PCR completion claim.",
            )
        resolved.append(receipt)

    current_generation = ledger.task_state_generation()
    task_state_snapshot_digest = ""
    task_state_snapshot_known = True
    if strict_snapshot_binding:
        task_state_snapshot_digest = ledger.task_state_snapshot_digest()
        task_state_snapshot_known = ledger.task_state_snapshot_known()
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
                "PCR completion claims require at least one current task-state evidence anchor; "
                "older same-run evidence may support historical/comparative facts only."
            ),
        )

    receipt_ids = tuple(receipt.receipt_id for receipt in resolved)
    evidence_set_payload = {
        "claim": turn.claim,
        "evidence_refs": refs,
        "receipt_ids": receipt_ids,
        "task_id": identity.get("task_id", ""),
        "run_id": identity.get("run_id", ""),
        "workspace_id": identity.get("workspace_id", ""),
        "task_state_generation": ledger.task_state_generation(),
    }
    if strict_snapshot_binding:
        evidence_set_payload["task_state_snapshot_digest"] = task_state_snapshot_digest
        evidence_set_payload["task_state_snapshot_known"] = task_state_snapshot_known
    evidence_set_hash = sha256(stable_json(evidence_set_payload).encode("utf-8")).hexdigest()
    return SubmissionCoherenceDecision(True), PCRSubmissionBinding(
        claim=turn.claim,
        evidence_refs=refs,
        receipt_ids=receipt_ids,
        evidence_set_sha256=evidence_set_hash,
        task_state_generation=ledger.task_state_generation(),
        context_identity=identity,
        evidence_roles=tuple(evidence_roles),
        evidence_generations=evidence_generations,
        task_state_snapshot_digest=task_state_snapshot_digest,
        task_state_snapshot_known=task_state_snapshot_known,
    )


def record_pcr_submission_claim(
    ledger: ExecutionLedger,
    *,
    step: int,
    binding: PCRSubmissionBinding,
    task_state_custody: Mapping[str, Any] | None = None,
    submission_mode: str = "submit",
) -> Receipt:
    """Persist one external CLAIM bound only to cited same-run DID/SAW."""
    claim_id = f"claim:{binding.evidence_set_sha256[:20]}"
    custody = deepcopy(dict(task_state_custody)) if isinstance(task_state_custody, Mapping) else None
    custody_payload = {
        "status": "captured_compact_world_state" if custody is not None else "not_captured",
        "snapshot": custody,
        "snapshot_sha256": (
            sha256(stable_json(custody).encode("utf-8")).hexdigest()
            if custody is not None else ""
        ),
        "observed_state_only": True,
    }
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
            **({
                "task_state_snapshot_digest": binding.task_state_snapshot_digest,
                "snapshot_binding_version": TASK_STATE_SNAPSHOT_BINDING_VERSION,
                "task_state_snapshot_known": binding.task_state_snapshot_known,
            } if binding.task_state_snapshot_digest else {}),
            "task_id": binding.context_identity.get("task_id", ""),
            "run_id": binding.context_identity.get("run_id", ""),
            "workspace_id": binding.context_identity.get("workspace_id", ""),
            "evidence_exact_handles": [
                receipt_exact_handle(receipt_id) for receipt_id in binding.receipt_ids
            ],
            "claim_authority": "primary_agent_external_claim",
            "submission_mode": str(submission_mode or "submit"),
            "semantic_sufficiency_judged_by_kernel": False,
            # Compact current state is captured at the claim boundary so the
            # first Solver submit can be reconstructed even if later actions
            # mutate the live world. This is custody, not task semantics.
            "submission_task_state_custody": custody_payload,
        },
    )
    ledger.record(receipt)
    return receipt

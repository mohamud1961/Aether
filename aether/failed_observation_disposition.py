"""Research-only failed-observation disposition substrate for Thin Frontier.

The harness does not decide whether a failed task observation is semantically
important. It only projects failed task-evidence receipts that still belong to
the current *confirmed candidate generation* and gives them stable finding IDs
so the same Primary can explicitly account for them before final submission.

A confirmed candidate generation advances only when Aether records a receipt
with ``state_change=True``. Generic shell observations that merely create an
uncertain task-state boundary do not retire failures: if the harness cannot
confirm a candidate change, the failure remains factual completion context.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .ledger import ExecutionLedger, Receipt
from .persistent_evidence import PERSISTENT_COMPLETION_EVIDENCE_KINDS

CONTROL = "control"
CURRENT_CANDIDATE_V1 = "current_candidate_v1"
SUPPORTED_MODES = frozenset({CONTROL, CURRENT_CANDIDATE_V1})
MAX_OPEN_FAILED_OBSERVATIONS = 8


def _finding_id(receipt_id: str) -> str:
    digest = hashlib.sha256(str(receipt_id).encode("utf-8")).hexdigest()[:16]
    return f"failed-observation:{digest}"


def _current_generation_result_ids(
    ledger: ExecutionLedger,
) -> tuple[tuple[str, ...], str]:
    """Return result IDs after the latest confirmed candidate mutation.

    Receipt order is the authority. A ``state_change=True`` receipt starts a new
    confirmed candidate generation. Progress receipts recorded after that
    boundary belong to the current generation. Opaque/uncertain boundaries do
    not advance this treatment-specific generation.
    """
    receipts = list(ledger.all_receipts())
    anchor_index = -1
    anchor_receipt_id = "initial"
    for index, receipt in enumerate(receipts):
        if receipt.state_change:
            anchor_index = index
            anchor_receipt_id = receipt.receipt_id

    result: list[str] = []
    for receipt in receipts[anchor_index + 1 :]:
        if receipt.kind != "solver_progress_assessment":
            continue
        payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        for value in payload.get("result_receipt_ids", ()):
            receipt_id = str(value).strip()
            if receipt_id and receipt_id not in result:
                result.append(receipt_id)
    return tuple(result), anchor_receipt_id


def current_candidate_failed_observations(
    ledger: ExecutionLedger,
    *,
    mode: str = CONTROL,
    limit: int = MAX_OPEN_FAILED_OBSERVATIONS,
) -> tuple[dict[str, Any], ...]:
    """Project current-candidate failed task observations without semantic judgment.

    A later *confirmed* task-world mutation retires older failures. Read-only
    follow-up and task-state-uncertain boundaries do not retire them.
    """
    selected = str(mode or CONTROL).strip().lower()
    if selected not in SUPPORTED_MODES:
        raise ValueError(f"unsupported failed observation disposition mode: {mode}")
    if selected == CONTROL:
        return ()

    result_ids, anchor_receipt_id = _current_generation_result_ids(ledger)
    by_id: dict[str, Receipt] = {
        receipt.receipt_id: receipt for receipt in ledger.all_receipts()
    }
    rows: list[dict[str, Any]] = []
    for receipt_id in result_ids:
        receipt = by_id.get(receipt_id)
        if receipt is None or receipt.success:
            continue
        if receipt.kind not in PERSISTENT_COMPLETION_EVIDENCE_KINDS:
            continue
        payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        row: dict[str, Any] = {
            "finding_id": _finding_id(receipt.receipt_id),
            "currentness": "current_candidate",
            "finding_type": "mechanical_failed_observation",
            "source_receipt_id": receipt.receipt_id,
            "candidate_generation_anchor_receipt_id": anchor_receipt_id,
            "step": receipt.step,
            "kind": receipt.kind,
            "summary": receipt.summary,
            "failure_class": receipt.failure_class,
            "semantic_interpretation_authority": "solver",
            "harness_role": "factual_failure_custody_only",
        }
        for key in ("stdout_handle", "stderr_handle"):
            value = str(payload.get(key) or "").strip()
            if value:
                row[key] = value
        rows.append(row)
    if limit <= 0:
        return tuple(rows)
    return tuple(rows[-int(limit):])


__all__ = [
    "CONTROL",
    "CURRENT_CANDIDATE_V1",
    "MAX_OPEN_FAILED_OBSERVATIONS",
    "SUPPORTED_MODES",
    "current_candidate_failed_observations",
]

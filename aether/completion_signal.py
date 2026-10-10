"""Factual, opt-in completion signal for the Thin Solver.

The signal never decides that a task is complete.  It observes only the latest
kernel-owned primary action boundary and, when that boundary contains a
successful verification-like shell command whose completion evidence was not
invalidated, reminds the Solver that further work should be justified by a
concrete unmet requirement.
"""
from __future__ import annotations

from typing import Any, Mapping

from .kernel_dispatch import is_verification_command
from .verification_oracle_guard import oracle_edit_observation

CONTROL = "control"
VERIFICATION_V1 = "verification_v1"
VERIFICATION_AUTHORITY_V2 = "verification_authority_v2"
VERIFICATION_ORACLE_GUARD_V1 = "verification_oracle_guard_v1"
SUPPORTED_MODES = frozenset({
    CONTROL, VERIFICATION_V1, VERIFICATION_AUTHORITY_V2, VERIFICATION_ORACLE_GUARD_V1,
})
_AUTHORITY_MODES = frozenset({VERIFICATION_AUTHORITY_V2, VERIFICATION_ORACLE_GUARD_V1})
SCHEMA = "aether.completion_signal.v1"


def normalize_mode(value: str | None) -> str:
    mode = str(value or CONTROL).strip().lower()
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported completion signal mode: {value!r}")
    return mode


def completion_signal_context(ledger: Any, *, mode: str = CONTROL) -> dict[str, Any] | None:
    """Return one factual signal for the latest primary result, if eligible."""
    selected = normalize_mode(mode)
    if selected == CONTROL:
        return None

    receipts = tuple(ledger.all_receipts())
    indexes = [r for r in receipts if getattr(r, "kind", "") == "primary_action_result_index"]
    if not indexes:
        return None
    index = indexes[-1]
    payload = getattr(index, "payload", {}) or {}
    if str(payload.get("action_kind") or "") != "run_command":
        return None

    by_id = {str(getattr(r, "receipt_id", "")): r for r in receipts}
    eligible: list[Any] = []
    oracle_edits: dict[str, dict[str, Any]] = {}
    integrity_rejected: list[tuple[Any, str]] = []
    for receipt_id in payload.get("outcome_receipt_ids", ()) or ():
        receipt = by_id.get(str(receipt_id))
        if receipt is None or getattr(receipt, "kind", "") != "run_command":
            continue
        if getattr(receipt, "success", False) is not True:
            continue
        rp = getattr(receipt, "payload", {}) or {}
        command = str(rp.get("command") or "")
        edit = (
            oracle_edit_observation(receipts, receipt)
            if selected == VERIFICATION_ORACLE_GUARD_V1
            else None
        )
        if not is_verification_command(command) and edit is None:
            continue
        if edit is not None:
            oracle_edits[str(receipt.receipt_id)] = edit
        risk = str(rp.get("verification_integrity_risk") or "").strip()
        if rp.get("completion_evidence_eligible") is False or risk:
            if risk:
                integrity_rejected.append((receipt, risk))
            continue
        eligible.append(receipt)

    if not eligible:
        if selected not in _AUTHORITY_MODES or not integrity_rejected:
            return None
        return {
            "schema": SCHEMA,
            "mode": selected,
            "basis": "latest_primary_result",
            "observation": (
                "The latest primary action includes a verification-like shell command whose "
                "successful shell status is not admissible completion evidence because the "
                "kernel detected verification-status integrity risk."
            ),
            "source_receipt_ids": [str(r.receipt_id) for r, _ in integrity_rejected],
            "verification_integrity_risks": [risk for _, risk in integrity_rejected],
            "semantic_completion_authority": "solver_against_raw_task_and_observed_reality",
            "verification_evidence_scope": (
                "This command result is still a factual shell observation, but its status cannot "
                "establish that the intended verification passed. It must not be promoted into "
                "completion evidence."
            ),
            "instruction": (
                "Do not finish on the basis of this verification result. Rerun the intended "
                "verification in a fail-closed form whose shell exit status preserves the test "
                "failure status. After obtaining admissible verification, compare its observed "
                "scope against the raw task's stated success authority before finishing."
            ),
        }

    signal = {
        "schema": SCHEMA,
        "mode": selected,
        "basis": "latest_primary_result",
        "observation": (
            "The latest primary action includes a successful verification-like shell command "
            "with no kernel-detected status masking or failure signature."
        ),
        "source_receipt_ids": [str(r.receipt_id) for r in eligible],
        "semantic_completion_authority": "solver_against_raw_task_and_observed_reality",
        "instruction": (
            "If this verification covers all remaining task requirements, preserve the current "
            "working state and call finish. Continue changing the task only for a concrete unmet "
            "requirement or unresolved observed failure."
        ),
    }
    if selected in _AUTHORITY_MODES:
        signal["verification_evidence_scope"] = (
            "A successful local verification supports only the properties it directly observed. "
            "A self-authored or substitute check is not independent evidence that an unobserved "
            "task-declared external, live, or acceptance surface passed."
        )
        signal["instruction"] = (
            "Compare this verification against the raw task's stated success authority. If every "
            "remaining requirement is directly covered by observed evidence, preserve the working "
            "state and call finish. If the raw task names an external acceptance check or live "
            "surface that this check did not observe, keep that requirement unresolved rather than "
            "inferring success from a substitute check. Continue changing the task only for a "
            "concrete unmet requirement or unresolved observed failure."
        )
    if selected == VERIFICATION_ORACLE_GUARD_V1:
        edit = oracle_edits.get(str(eligible[-1].receipt_id))
        if edit is None:
            edit = oracle_edit_observation(receipts, eligible[-1])
        if edit is not None:
            signal["verification_edit_observation"] = edit
    return signal


__all__ = [
    "CONTROL",
    "SCHEMA",
    "SUPPORTED_MODES",
    "VERIFICATION_V1",
    "VERIFICATION_AUTHORITY_V2",
    "VERIFICATION_ORACLE_GUARD_V1",
    "completion_signal_context",
    "normalize_mode",
]

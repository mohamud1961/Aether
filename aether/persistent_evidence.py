"""Mechanical PERSISTENT V0 task-evidence admission.

This module is the single authority for which receipt kinds may be presented
or cited as evidence of the external task state. Control-plane bookkeeping,
model-authored observations, provider telemetry, repeat metadata, and context
indexes are deliberately excluded even when they are successful receipts.
"""
from __future__ import annotations

from typing import Any, Mapping


PERSISTENT_COMPLETION_EVIDENCE_KINDS = frozenset({
    "read_file",
    "read_file_page",
    "read_output",
    "grep_output",
    "write_file",
    "run_command",
    "bootstrap",
    "process_launch",
    "service_probe",
    "job_probe",
    "process_stop",
    "terminal_start",
    "terminal_send",
    "terminal_read",
    "terminal_wait",
    "terminal_interrupt",
    "terminal_close",
    "artifact_inspection",
    "query_artifact_history",
    "inspect_diff",
    "check_result",
    "schema_validation",
    "model_verifier_inspection",
    "verifier_result_evidence",
    "proof_evidence_admission",
})

# Receipts that are direct terminal outcomes of a Primary Agent action and may
# be pinned as its latest causal result. This is intentionally broader than the
# completion-evidence set: a validation refusal or repeat block is a real action
# result the model must observe, but it is not proof that the task is complete.
PERSISTENT_PRIMARY_ACTION_RESULT_KINDS = frozenset({
    *PERSISTENT_COMPLETION_EVIDENCE_KINDS,
    # Control-plane bookkeeping can still be the direct result of a model
    # action. Keeping those receipts in this causal-result index prevents the
    # next Solver turn from receiving a false ``missing_primary_action_result``
    # signal. These kinds remain absent from PERSISTENT_COMPLETION_EVIDENCE_KINDS and
    # therefore cannot be cited as proof that the external task is complete.
    "job_disposition",
    "completion_record_revision",
    "completion_record_update",
    "query_history",
    "report_blocker",
    "action_validation",
    "safety_block",
    "integrity_block",
    "action_budget_refused",
    "automatic_memory_block",
    "no_progress_control",
    "persistent_repeat_block",
    "persistent_repeat_reuse",
    "persistent_repeat_permit_consumed",
    "persistent_action_execution_block",
    "unknown_action",
})


def is_persistent_completion_evidence(receipt: Any) -> bool:
    """Return whether *receipt* may enter a PERSISTENT completion evidence index.

    This is a structural admission decision only. Semantic sufficiency remains
    the independent Verifier's responsibility.
    """
    payload = getattr(receipt, "payload", {})
    if isinstance(payload, dict) and payload.get("completion_evidence_eligible") is False:
        return False
    # A failed task action remains first-class causal truth for the Primary Agent,
    # but it cannot be nominated as evidence that the task is complete merely
    # because its receipt kind normally carries task evidence. Negative task
    # state must be represented by a successful observation route (for example
    # an artifact/probe result), not by laundering a failed tool invocation.
    if getattr(receipt, "success", False) is not True:
        return False
    return str(getattr(receipt, "kind", "")) in PERSISTENT_COMPLETION_EVIDENCE_KINDS


def is_persistent_admitted_completion_evidence(receipt: Any) -> bool:
    """Return whether a receipt carries kernel-derived proof admission.

    ``is_persistent_completion_evidence`` intentionally remains the broad task-state
    candidate selector used to show useful action results to the Solver.  This
    narrower predicate is the separate proof status: it requires a registered,
    current, valid route whose kernel-derived class and ceiling are available.
    """
    if not is_persistent_completion_evidence(receipt):
        return False
    payload = getattr(receipt, "payload", {})
    if not isinstance(payload, Mapping):
        return False
    if str(getattr(receipt, "kind", "")) == "proof_evidence_admission":
        return bool(getattr(receipt, "success", False) and payload.get("admitted") is True)
    return bool(
        payload.get("observation_valid") is True
        and payload.get("eligible_for_proof") is True
        and str(payload.get("admissibility", "")).strip()
        in {"direct_admissible", "verdict_eligible"}
        and str(payload.get("actual_evidence_class", "")).strip()
        and str(payload.get("evidence_ceiling", "")).strip()
    )


def is_persistent_primary_action_result(receipt: Any) -> bool:
    """Return whether *receipt* is a direct causal result of one PERSISTENT action."""
    return str(getattr(receipt, "kind", "")) in PERSISTENT_PRIMARY_ACTION_RESULT_KINDS

"""Mechanical PERSISTENT V0 task-evidence admission.

This module is the single authority for which receipt kinds may be presented
or cited as evidence of the external task state. Control-plane bookkeeping,
model-authored observations, provider telemetry, repeat metadata, and context
indexes are deliberately excluded even when they are successful receipts.
"""
from __future__ import annotations

from typing import Any


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
    "query_memory",
    "record_observation",
    "inspect_checks",
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


def is_persistent_primary_action_result(receipt: Any) -> bool:
    """Return whether *receipt* is a direct causal result of one PERSISTENT action."""
    return str(getattr(receipt, "kind", "")) in PERSISTENT_PRIMARY_ACTION_RESULT_KINDS

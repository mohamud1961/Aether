"""Mechanical finite-job lifecycle and relevance vocabulary.

Execution state and model-declared relevance are deliberately independent.  The
helpers in this module only normalize recorded fields; they never decide whether
the work was sufficient for a task.
"""
from __future__ import annotations

from typing import Any, Mapping


JOB_RELEVANCE_VALUES = frozenset({
    "unclassified",
    "required",
    "optional",
    "superseded",
    "abandoned",
})

JOB_EXECUTION_STATES = frozenset({
    "running",
    "exited_success",
    "exited_failure",
    "cancelled",
    "unknown",
})


def normalize_job_relevance(value: Any) -> str:
    """Return one declared relevance value, defaulting invalid input safely."""
    normalized = str(value or "").strip().lower().replace("-", "_")
    return normalized if normalized in JOB_RELEVANCE_VALUES else "unclassified"


def declared_job_relevance(arguments: Mapping[str, Any]) -> tuple[str | None, str, str]:
    """Read optional action metadata without inventing a disposition.

    ``None`` means the action did not declare relevance.  Callers that register
    a job should store ``unclassified`` explicitly; callers updating a job should
    leave its existing declaration untouched when this returns ``None``.
    """
    if "job_relevance" in arguments:
        raw = arguments.get("job_relevance")
    elif "relevance" in arguments:
        raw = arguments.get("relevance")
    else:
        return None, "", ""
    normalized = normalize_job_relevance(raw)
    reason = str(
        arguments.get("job_relevance_reason", arguments.get("reason", "")) or ""
    ).strip()
    replacement = str(arguments.get("replacement_job_id", "") or "").strip()
    return normalized, reason, replacement


def job_execution_state(process: Mapping[str, Any]) -> str:
    """Project a registered process onto an honest finite-job state."""
    status = str(process.get("status") or "unknown").strip().lower()
    if bool(process.get("live", False)) or status in {"running", "starting"}:
        return "running"
    if status in {"cancelled", "canceled", "stopped"} or process.get("stopped_by"):
        return "cancelled"
    if bool(process.get("completed", False)) and process.get("job_succeeded") is True:
        return "exited_success"
    if bool(process.get("completed", False)) and process.get("job_succeeded") is False:
        return "exited_failure"
    # A terminal-looking label without the corresponding completion bit is not
    # enough to claim an exit.  Preserve it as unknown for reconciliation.
    return "unknown"


def project_job_lifecycle(process: Mapping[str, Any]) -> dict[str, Any]:
    """Return bounded lifecycle/relevance facts for model-facing projections."""
    relevance = normalize_job_relevance(process.get("relevance"))
    state = job_execution_state(process)
    row: dict[str, Any] = {
        "execution_state": state,
        "relevance": relevance,
        "relevance_source": str(
            process.get("relevance_source") or "default_unclassified"
        ),
    }
    reason = str(process.get("relevance_reason") or "").strip()
    if reason:
        row["relevance_reason"] = reason[:1000]
    replacement = str(process.get("replacement_job_id") or "").strip()
    if replacement:
        row["replacement_job_id"] = replacement
    return row


def relevance_is_non_blocking(relevance: str, state: str) -> bool:
    """Whether observed-terminal job debt is not a mechanical completion blocker.

    ``unknown`` is intentionally blocking even for optional/abandoned work: an
    unknown outcome may still represent a live writer or an unreconciled side
    effect. Relevance can retire replay debt only after execution is observed
    terminal.
    """
    return (
        state in {"cancelled", "exited_failure", "exited_success"}
        and relevance in {"optional", "abandoned", "superseded"}
    )


__all__ = [
    "JOB_EXECUTION_STATES",
    "JOB_RELEVANCE_VALUES",
    "declared_job_relevance",
    "job_execution_state",
    "normalize_job_relevance",
    "project_job_lifecycle",
    "relevance_is_non_blocking",
]

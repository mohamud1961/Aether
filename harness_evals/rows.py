"""Trial-row validity: classify each trial row so that invalid rows stay out of A/B statistics.

A trial row is valid, invalid or contaminated. A row is invalid when no model work started or
when the launch failed before model work; a row is contaminated when a positive reward is
contradicted by the trace's ownership evidence. Invalid rows are kept in the evaluation
board, annotated and never removed or replaced.

Only the conditions the classifier implements are here. Other invalid-row causes belong to
the launcher that produced the row.
"""

from __future__ import annotations

from typing import Any


def classify_row_validity(row: dict[str, Any]) -> dict[str, Any]:
    """Return ``{row_validity, invalid_reason, ownership, ...}`` for a trial row."""
    reason_code = row.get("reason_code")
    model_calls = row.get("model_calls")
    mean_reward = row.get("mean")
    provider_preflight_status = str(
        row.get("provider_preflight_status")
        or row.get("preflight_status")
        or row.get("board_preflight_status")
        or ""
    ).strip()
    model_work_started = bool(isinstance(model_calls, (int, float)) and model_calls > 0)

    def _result(
        row_validity: str, invalid_reason: str | None, *, ownership: str | None
    ) -> dict[str, Any]:
        return {
            "row_validity": row_validity,
            "invalid_reason": invalid_reason,
            "exclude_from_ab": row_validity != "valid",
            "model_work_started": model_work_started,
            "model_calls": model_calls,
            "provider_preflight_status": provider_preflight_status or None,
            "ownership": ownership,
        }

    # Condition 1: backend/provider failure before model work
    if provider_preflight_status == "preflight_failed":
        return _result("invalid", "provider_preflight_failed", ownership=None)
    if reason_code == "harbor_native_backend_error":
        return _result("invalid", "backend_failure_before_model_work", ownership=None)
    if model_calls is None or (
        isinstance(model_calls, (int, float)) and model_calls <= 0
    ):
        return _result("invalid", "no_model_calls", ownership=None)

    # Condition 2: reward-positive but ownership contradicted by the trace
    if isinstance(mean_reward, (int, float)) and mean_reward > 0:
        ownership = _check_candidate_ownership(row)
        if ownership == "contradicted":
            return _result(
                "contaminated",
                "reward_positive_ownership_contradicted",
                ownership="contradicted",
            )
        return _result("valid", None, ownership=ownership)

    return _result("valid", None, ownership=None)


def _check_candidate_ownership(row: dict[str, Any]) -> str:
    """Return "confirmed", "contradicted" or "unknown" from the row's finalize reason.

    Without ownership evidence the answer is "unknown", and an unknown row is not invalid.
    """
    if not row.get("remote_workspace_root") or not row.get("status_path"):
        return "unknown"
    finalize_reason = row.get("finalize_reason", "")
    if not isinstance(finalize_reason, str):
        return "unknown"
    if "port_never_bound" in finalize_reason or "service_not_owned" in finalize_reason:
        return "contradicted"
    if "port_bound" in finalize_reason or "service_owned" in finalize_reason:
        return "confirmed"
    return "unknown"


def annotate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of every trial row with its validity fields merged in."""
    return [{**row, **classify_row_validity(row)} for row in rows]


def compute_validity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate validity counts and invalid reasons over annotated rows."""
    validity_counts: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in rows:
        validity = str(row.get("row_validity") or "unknown")
        validity_counts[validity] = validity_counts.get(validity, 0) + 1
        reason = row.get("invalid_reason")
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "total_rows": len(rows),
        "valid_rows": validity_counts.get("valid", 0),
        "invalid_rows": validity_counts.get("invalid", 0),
        "contaminated_rows": validity_counts.get("contaminated", 0),
        "unknown_rows": validity_counts.get("unknown", 0),
        "validity_counts": validity_counts,
        "invalid_reasons": reasons,
    }


__all__ = ["annotate_rows", "classify_row_validity", "compute_validity_summary"]

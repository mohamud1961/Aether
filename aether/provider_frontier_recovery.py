"""Mechanical admission rules for bounded Solver provider-frontier recovery.

This module contains no task semantics.  It only classifies a narrow provider
failure in which an accepted Solver response exhausted its output allowance
without ever yielding a native tool call.  The kernel may use that fact to
admit at most one fresh ledger re-anchor when an explicit research mode is
enabled.  Unknown transport facts fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CONTROL = "control"
NO_TOOL_MAX_OUTPUT_V1 = "no_tool_max_output_v1"
SUPPORTED_MODES = frozenset({CONTROL, NO_TOOL_MAX_OUTPUT_V1})
PROTECTED_FINAL_RESERVE_MAX_S = 120.0
PROTECTED_FINAL_RESERVE_FRACTION = 0.25


class ProviderFrontierReserveReached(RuntimeError):
    """A task-owned final reserve was reached before a Solver tool frontier.

    The provider request was already accepted and emitted partial output, so the
    interrupted response is never replayed.  This exception carries only
    mechanical transport facts used by the same fail-closed classifier as a
    provider `response.incomplete` boundary.
    """

    def __init__(
        self,
        *,
        request_accepted: bool,
        partial_output_observed: bool,
        native_tool_call_observed: bool,
        remaining_run_s: float,
        protected_reserve_s: float,
    ) -> None:
        self.event_type = "aether.provider_frontier_reserve"
        self.retry_safe = False
        self.request_accepted = bool(request_accepted)
        self.partial_output_observed = bool(partial_output_observed)
        self.native_tool_call_observed = bool(native_tool_call_observed)
        self.incomplete_reason = "protected_final_reserve"
        self.replay_safety_reason = "accepted_partial_provider_response_not_replayed"
        self.remaining_run_s = float(remaining_run_s)
        self.protected_reserve_s = float(protected_reserve_s)
        super().__init__(
            "protected task-final reserve reached before provider emitted a native tool call"
        )


def protected_final_reserve_s(run_timeout_s: float | None) -> float | None:
    """Return the bounded research reserve derived only from task wall time.

    120 seconds rounds above the current provider-corpus maximum successful
    Solver call (~110.4s).  Capping the reserve at 25% of total task time keeps
    short tasks from surrendering most of their execution window.  This is an
    experimental resource boundary, not a semantic confidence threshold.
    """
    if run_timeout_s is None:
        return None
    timeout = float(run_timeout_s)
    if timeout <= 0:
        return None
    return min(PROTECTED_FINAL_RESERVE_MAX_S, timeout * PROTECTED_FINAL_RESERVE_FRACTION)


@dataclass(frozen=True)
class FrontierRecoveryDecision:
    eligible: bool
    reason: str
    facts: dict[str, Any]


def classify_frontier_recovery(
    exc: Any,
    *,
    mode: str,
    used_recoveries: int,
    max_recoveries: int = 1,
) -> FrontierRecoveryDecision:
    """Return a fail-closed mechanical recovery decision for one provider error."""
    selected = str(mode or CONTROL).strip().lower()
    if selected not in SUPPORTED_MODES:
        raise ValueError(f"unsupported provider frontier recovery mode: {mode}")

    facts = {
        "role": str(getattr(exc, "role", "") or ""),
        "budget_admission_refused": bool(
            getattr(exc, "pre_dispatch_budget_admission_refused", False)
        ),
        "terminal_event_type": getattr(exc, "provider_terminal_event_type", None),
        "terminal_retry_safe": getattr(exc, "provider_terminal_retry_safe", None),
        "request_accepted": getattr(exc, "provider_request_accepted", None),
        "partial_output_observed": getattr(exc, "provider_partial_output_observed", None),
        "native_tool_call_observed": getattr(exc, "provider_native_tool_call_observed", None),
        "native_tool_call_observed_known": bool(
            getattr(exc, "provider_native_tool_call_observed_known", False)
        ),
        "incomplete_reason": getattr(exc, "provider_incomplete_reason", None),
        "replay_safety_reason": getattr(exc, "provider_replay_safety_reason", None),
        "remaining_run_s_at_frontier_stop": getattr(
            exc, "provider_remaining_run_s_at_frontier_stop", None
        ),
        "protected_reserve_s": getattr(exc, "provider_protected_reserve_s", None),
        "used_recoveries": int(used_recoveries),
        "max_recoveries": int(max_recoveries),
    }

    if selected == CONTROL:
        return FrontierRecoveryDecision(False, "control_mode", facts)
    if int(used_recoveries) >= int(max_recoveries):
        return FrontierRecoveryDecision(False, "recovery_budget_exhausted", facts)
    if facts["role"] != "solver":
        return FrontierRecoveryDecision(False, "non_solver_role", facts)
    if facts["budget_admission_refused"]:
        return FrontierRecoveryDecision(False, "pre_dispatch_budget_refusal", facts)
    accepted_boundary = (
        facts["terminal_event_type"] == "response.incomplete"
        and facts["incomplete_reason"] == "max_output_tokens"
    ) or (
        facts["terminal_event_type"] == "aether.provider_frontier_reserve"
        and facts["incomplete_reason"] == "protected_final_reserve"
    )
    if not accepted_boundary:
        return FrontierRecoveryDecision(False, "not_supported_no_tool_boundary", facts)
    if facts["request_accepted"] is not True:
        return FrontierRecoveryDecision(False, "acceptance_not_observed", facts)
    if facts["partial_output_observed"] is not True:
        return FrontierRecoveryDecision(False, "partial_output_not_observed", facts)
    if not facts["native_tool_call_observed_known"]:
        return FrontierRecoveryDecision(False, "native_tool_observation_unknown", facts)
    if facts["native_tool_call_observed"] is not False:
        return FrontierRecoveryDecision(False, "native_tool_observed", facts)
    if facts["terminal_retry_safe"] is not False:
        return FrontierRecoveryDecision(False, "retry_safety_not_explicitly_false", facts)

    reason = (
        "accepted_no_tool_max_output_incomplete"
        if facts["incomplete_reason"] == "max_output_tokens"
        else "accepted_no_tool_protected_final_reserve"
    )
    return FrontierRecoveryDecision(True, reason, facts)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from .control_plane import ControlPlane, last_verified_fingerprint_hash
from .event_log import EventLog
from .policy_config import PolicyConfig


PHASES = ("Orient", "Explore", "Plan", "Implement", "Verify", "Review")
_LEGACY_TO_PHASE = {
    "ACT": "Implement",
    "VERIFY": "Verify",
    "REPAIR": "Review",
    "COMMIT": "Review",
}


@dataclass(frozen=True)
class PhaseTransitionResult:
    accepted: bool
    next_phase: str
    deny_reason_code: str | None = None


def request_phase_transition(
    current_phase: str,
    requested_phase: str,
    phase_reason_code: str,
    run_state: Mapping[str, Any],
) -> PhaseTransitionResult:
    event_log = run_state.get("event_log")
    if not isinstance(event_log, EventLog):
        raise ValueError("run_state.event_log must be EventLog")

    timestamp = str(run_state.get("timestamp", ""))
    cwd = str(run_state.get("cwd", "."))
    normalized_current = _normalize_phase(current_phase)
    normalized_requested = _normalize_phase(requested_phase)

    if normalized_requested not in PHASES:
        event_log.append_event(
            {
                "event_type": "PHASE_TRANSITION_DENIED",
                "timestamp": timestamp,
                "cwd": cwd,
                "from_phase": normalized_current,
                "to_phase": normalized_requested,
                "reason": "unknown_phase",
                "phase_reason_code": phase_reason_code,
                "deny_reason_code": "PHASE_TRANSITION_DENIED",
                "missing_conditions": ["requested_phase_known"],
                "resolution_hint": "Request a known phase: Orient, Explore, Plan, Implement, Verify, or Review.",
            }
        )
        return PhaseTransitionResult(False, normalized_current, "PHASE_TRANSITION_DENIED")

    control_plane = run_state.get("control_plane")
    if not isinstance(control_plane, ControlPlane):
        policy_config = run_state.get("policy_config")
        control_plane = ControlPlane(
            event_log=event_log,
            policy_config=policy_config if isinstance(policy_config, PolicyConfig) else None,
        )

    workspace_fingerprint_hash = _optional_str(
        run_state.get("workspace_fingerprint_hash", run_state.get("workspace_digest"))
    )
    events = run_state.get("events")
    history = events if isinstance(events, list) else event_log.events
    verified_fingerprint_hash = _optional_str(
        run_state.get("last_verified_fingerprint_hash", last_verified_fingerprint_hash(history))
    )
    plan_status = run_state.get("plan_status")
    verifier_result = run_state.get("verifier_result")
    verifier_plan_id = _optional_str(run_state.get("verifier_plan_id"))
    completion_signals = run_state.get("completion_signals")
    files_written_count = run_state.get("files_written_count")

    outcome = control_plane.transition(
        current_state=normalized_current,
        requested_state=normalized_requested,
        dirty_since_last_verify=bool(run_state.get("dirty_since_last_verify", False)),
        verifier_result=str(verifier_result) if verifier_result is not None else None,
        workspace_fingerprint_hash=workspace_fingerprint_hash,
        last_verified_fingerprint_hash=verified_fingerprint_hash,
        verifier_run=bool(run_state.get("verifier_run", False)),
        completion_signals=completion_signals if isinstance(completion_signals, list) else None,
        files_written_count=files_written_count if isinstance(files_written_count, int) else None,
        verification_hint_detected=bool(run_state.get("verification_hint_detected", False)),
        verifier_plan_id=verifier_plan_id,
        repair_attempts_exhausted=bool(run_state.get("repair_attempts_exhausted", False)),
        timestamp=timestamp,
        cwd=cwd,
        completion_contract_exists=bool(run_state.get("completion_contract_exists", True)),
        plan_status=str(plan_status) if isinstance(plan_status, str) else None,
    )

    accepted = outcome.next_state == normalized_requested
    if not accepted and not _denial_already_logged(event_log.events, normalized_current, normalized_requested):
        event_log.append_event(
            {
                "event_type": "PHASE_TRANSITION_DENIED",
                "timestamp": timestamp,
                "cwd": cwd,
                "from_phase": normalized_current,
                "to_phase": normalized_requested,
                "reason": "requested_phase_not_satisfied",
                "phase_reason_code": phase_reason_code,
                "deny_reason_code": "PHASE_TRANSITION_DENIED",
                "missing_conditions": (
                    ["verifier_pass_evidence", "workspace_fingerprint_match_verified"]
                    if normalized_requested == "Review"
                    else ["control_plane_transition_constraints_satisfied"]
                ),
                "resolution_hint": (
                    "Run verification and obtain a pass bound to the current workspace fingerprint, then request Review again."
                    if normalized_requested == "Review"
                    else "Satisfy phase transition constraints and request transition again."
                ),
            }
        )

    return PhaseTransitionResult(
        accepted=accepted,
        next_phase=outcome.next_state,
        deny_reason_code=None if accepted else _latest_deny_reason_code(event_log.events),
    )


def _normalize_phase(phase: str) -> str:
    value = str(phase).strip()
    return _LEGACY_TO_PHASE.get(value, value)


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    coerced = str(value).strip()
    return coerced or None


def _latest_deny_reason_code(events: list[Dict[str, Any]]) -> str:
    for event in reversed(events):
        if str(event.get("event_type", "")).upper() != "PHASE_TRANSITION_DENIED":
            continue
        code = event.get("deny_reason_code")
        if isinstance(code, str) and code.strip():
            return code
        break
    return "PHASE_TRANSITION_DENIED"


def _denial_already_logged(events: list[Dict[str, Any]], from_phase: str, to_phase: str) -> bool:
    for event in reversed(events):
        if str(event.get("event_type", "")).upper() != "PHASE_TRANSITION_DENIED":
            continue
        return event.get("from_phase") == from_phase and event.get("to_phase") == to_phase
    return False

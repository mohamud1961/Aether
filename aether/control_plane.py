from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .enum_registry import get_enum_values

from .event_log import EventLog
from .exploration_floor import (
    check_exploration_floor,
    compute_explore_floor_passed,
    emit_exploration_floor_eval,
)
from .mandatory_verifier_phase import mandatory_verifier_phase_required
from .policy_config import PolicyConfig


PHASES = ["Orient", "Explore", "Plan", "Implement", "Verify", "Review"]
_LEGACY_TO_PHASE = {
    "ACT": "Implement",
    "VERIFY": "Verify",
    "REPAIR": "Review",
    "COMMIT": "Review",
}
_PHASE_TO_LEGACY = {
    "Implement": "ACT",
    "Verify": "VERIFY",
    "Review": "REPAIR",
}
_PHASE_REASON_CODES = frozenset(get_enum_values("phase_reason_code"))


@dataclass(frozen=True)
class TransitionOutcome:
    next_state: str
    triggers_fired: List[str]
    trigger_explanation: Optional[str]


class ControlPlane:
    def __init__(self, event_log: EventLog, policy_config: Optional[PolicyConfig] = None) -> None:
        self.event_log = event_log
        self.policy_config = policy_config or PolicyConfig.from_env()
        self.current_phase: str = "Orient"

    def transition(
        self,
        *,
        current_state: str,
        requested_state: str,
        dirty_since_last_verify: bool,
        verifier_result: Optional[str],
        workspace_fingerprint_hash: Optional[str],
        last_verified_fingerprint_hash: Optional[str],
        verifier_run: Optional[bool] = None,
        completion_signals: Optional[List[Dict[str, object]]] = None,
        files_written_count: Optional[int] = None,
        verification_hint_detected: Optional[bool] = None,
        verifier_plan_id: Optional[str] = None,
        repair_attempts_exhausted: Optional[bool] = None,
        timestamp: str,
        cwd: str,
        completion_contract_exists: bool = True,
        plan_status: Optional[str] = None,
        phase_reason_code: Optional[str] = None,
        backtrack_context: Optional[Mapping[str, Any]] = None,
        transition_source: str = "system",
    ) -> TransitionOutcome:
        triggers: List[str] = []
        explanation: Optional[str] = None

        phase_mode = current_state in PHASES or requested_state in PHASES
        current_phase = _normalize_phase(current_state)
        requested_phase = _normalize_phase(requested_state)
        next_phase = requested_phase
        requested_reason_code = (
            phase_reason_code.strip()
            if isinstance(phase_reason_code, str) and phase_reason_code.strip()
            else None
        )

        if phase_mode and requested_phase == current_phase:
            self._emit_phase_transition_denied(
                from_phase=current_phase,
                to_phase=requested_phase,
                timestamp=timestamp,
                cwd=cwd,
                deny_reason_code="NO_OP_TRANSITION",
                phase_reason_code=requested_reason_code or "default_deny",
                reason="requested_phase_matches_current_phase",
                missing_conditions=["requested_phase_differs_from_current_phase"],
                resolution_hint="Continue work in the current phase and request a new phase only when preconditions change.",
            )
            return TransitionOutcome(
                next_state=_phase_to_result_state(
                    original_state=current_state,
                    requested_state=requested_state,
                    phase=current_phase,
                ),
                triggers_fired=["no_op_transition_denied"],
                trigger_explanation="requested phase matches current phase",
            )

        if phase_mode and _is_hard_denied_phase_transition(
            current_phase=current_phase,
            requested_phase=requested_phase,
        ):
            self._emit_phase_transition_denied(
                from_phase=current_phase,
                to_phase=requested_phase,
                timestamp=timestamp,
                cwd=cwd,
                deny_reason_code="PHASE_ORDER_VIOLATION",
                phase_reason_code=requested_reason_code or "default_deny",
                reason="requested_phase_violates_hard_ordering",
                missing_conditions=["phase_legal_transition"],
                resolution_hint=(
                    "Use sequential progress: Orient -> Explore -> Plan -> Implement -> Verify -> Review."
                ),
            )
            return TransitionOutcome(
                next_state=_phase_to_result_state(
                    original_state=current_state,
                    requested_state=requested_state,
                    phase=current_phase,
                ),
                triggers_fired=["phase_order_violation_denied"],
                trigger_explanation="requested phase violates hard transition ordering",
            )

        current_phase_index = _phase_index(current_phase)
        requested_phase_index = _phase_index(requested_phase)
        is_backward_transition = requested_phase_index < current_phase_index
        if phase_mode and transition_source == "tool_request" and is_backward_transition:
            backtrack_context_valid = (
                isinstance(backtrack_context, Mapping)
                and bool(
                    [
                        key
                        for key in backtrack_context.keys()
                        if isinstance(key, str) and key.strip()
                    ]
                )
            )
            reason_code_valid = bool(
                requested_reason_code and requested_reason_code in _PHASE_REASON_CODES
            )
            if not reason_code_valid or not backtrack_context_valid:
                missing: List[str] = []
                if not reason_code_valid:
                    missing.append("phase_reason_code_closed_enum")
                if not backtrack_context_valid:
                    missing.append("backtrack_context_non_empty_object")
                self._emit_phase_transition_denied(
                    from_phase=current_phase,
                    to_phase=requested_phase,
                    timestamp=timestamp,
                    cwd=cwd,
                    deny_reason_code="BACKTRACK_CONTEXT_REQUIRED",
                    phase_reason_code=requested_reason_code or "default_deny",
                    reason="backward_transition_missing_required_context",
                    missing_conditions=missing,
                    resolution_hint=(
                        "Provide a closed phase_reason_code and a non-empty backtrack_context object explaining why backtracking is required."
                    ),
                )
                return TransitionOutcome(
                    next_state=_phase_to_result_state(
                        original_state=current_state,
                        requested_state=requested_state,
                        phase=current_phase,
                    ),
                    triggers_fired=["backtrack_context_missing"],
                    trigger_explanation="backward transitions require structured context",
                )

        completion_signals = completion_signals or []
        files_written_count = files_written_count or 0
        verifier_run = bool(verifier_run) if verifier_run is not None else False
        verification_hint_detected = bool(verification_hint_detected)

        fingerprint_mismatch = (
            workspace_fingerprint_hash is not None
            and last_verified_fingerprint_hash is not None
            and workspace_fingerprint_hash != last_verified_fingerprint_hash
        )
        if requested_phase == "Implement":
            floor = check_exploration_floor(
                {
                    "workspace_digest": workspace_fingerprint_hash,
                    "events": self.event_log.events,
                    "explore_floor_passed": compute_explore_floor_passed(
                        {"events": self.event_log.events}
                    ),
                    "plan_artifact_present": _plan_artifact_present(
                        events=self.event_log.events,
                        plan_status=plan_status,
                    ),
                    "plan_status": plan_status,
                }
            )
            emit_exploration_floor_eval(
                event_log=self.event_log,
                result=floor,
                timestamp=timestamp,
                cwd=cwd,
            )
            if not floor.passed:
                self._emit_phase_transition_denied(
                    from_phase=current_phase,
                    to_phase=requested_phase,
                    timestamp=timestamp,
                    cwd=cwd,
                    deny_reason_code="PLAN_MISSING_LINKAGE",
                    phase_reason_code="plan_update_required",
                    reason="exploration_floor_not_met",
                    missing_conditions=floor.missing_conditions,
                    resolution_hint=(
                        "Satisfy exploration floor requirements and request Explore -> Implement again."
                    ),
                )
                return TransitionOutcome(
                    next_state=_phase_to_result_state(
                        original_state=current_state,
                        requested_state=requested_state,
                        phase=current_phase,
                    ),
                    triggers_fired=["exploration_floor_missing"],
                    trigger_explanation="exploration floor must pass before Implement",
                )
            if not completion_contract_exists:
                self._emit_phase_transition_denied(
                    from_phase=current_phase,
                    to_phase=requested_phase,
                    timestamp=timestamp,
                    cwd=cwd,
                    deny_reason_code="CONTRACT_MISSING",
                    phase_reason_code="default_deny",
                    missing_conditions=["completion_contract_exists"],
                    resolution_hint="Create a completion contract before entering Implement.",
                )
                return TransitionOutcome(
                    next_state=_phase_to_result_state(
                        original_state=current_state,
                        requested_state=requested_state,
                        phase=current_phase,
                    ),
                    triggers_fired=["completion_contract_missing"],
                    trigger_explanation="completion contract required before Implement",
                )
            if plan_status not in {"APPROVED", "EXECUTING"}:
                self._emit_phase_transition_denied(
                    from_phase=current_phase,
                    to_phase=requested_phase,
                    timestamp=timestamp,
                    cwd=cwd,
                    deny_reason_code="PLAN_MISSING_LINKAGE",
                    phase_reason_code="plan_update_required",
                    missing_conditions=["plan_status_approved_or_executing"],
                    resolution_hint="Approve the implementation plan, then request Explore -> Implement again.",
                )
                return TransitionOutcome(
                    next_state=_phase_to_result_state(
                        original_state=current_state,
                        requested_state=requested_state,
                        phase=current_phase,
                    ),
                    triggers_fired=["plan_not_approved"],
                    trigger_explanation="Implement requires APPROVED or EXECUTING plan status",
                )

        if requested_phase == "Review":
            has_fingerprint_delta = dirty_since_last_verify or fingerprint_mismatch
            needs_verify = has_fingerprint_delta

            if dirty_since_last_verify:
                next_phase = "Verify"
                triggers.append("dirty_since_last_verify")
                explanation = "dirty workspace requires Verify"
            elif fingerprint_mismatch:
                next_phase = "Verify"
                triggers.append("fingerprint_mismatch")
                explanation = "workspace fingerprint mismatch requires Verify"
            elif (
                self.policy_config.feature_flags.ff_mandatory_verifier_phase
                and mandatory_verifier_phase_required(
                    files_written_count=files_written_count,
                    completion_signals=completion_signals,
                    verifier_run=verifier_run,
                )
            ):
                next_phase = "Verify"
                triggers.append("mandatory_verifier_phase")
                explanation = "completion with writes requires verifier run"
            elif self.policy_config.feature_flags.ff_semantic_success_detection and (
                verification_hint_detected and not verifier_run
            ):
                next_phase = "Verify"
                triggers.append("verification_hint_detected")
                explanation = "verification hint requires verifier run"
        elif requested_phase == "Verify":
            if repair_attempts_exhausted:
                next_phase = "Review"
                triggers.append("repair_attempts_exhausted")
                explanation = "repair attempts exhausted"
            elif self.policy_config.feature_flags.ff_verify_and_repair and verifier_result in {"fail", "unknown"}:
                next_phase = "Review"
                triggers.append("verifier_failed")
                explanation = "verifier failed, routing to review/repair"

        reason_code = _phase_reason_code(next_phase, triggers)
        if (
            transition_source == "tool_request"
            and requested_reason_code in _PHASE_REASON_CODES
            and phase_mode
        ):
            reason_code = requested_reason_code
        if phase_mode and current_phase != next_phase:
            transition_event: Dict[str, Any] = {
                "event_type": "PHASE_TRANSITION",
                "timestamp": timestamp,
                "cwd": cwd,
                "from_phase": current_phase,
                "to_phase": next_phase,
                "phase_reason_code": reason_code,
                "triggers_fired": triggers,
                "trigger_explanation": explanation,
                "workspace_fingerprint_hash": workspace_fingerprint_hash,
                "dirty_since_last_verify": dirty_since_last_verify,
            }
            if is_backward_transition and isinstance(backtrack_context, Mapping):
                transition_event["backtrack_context"] = {
                    str(key): value for key, value in backtrack_context.items()
                }
            self.event_log.append_event(transition_event)
        self.current_phase = next_phase

        self.event_log.append_event(
            {
                "event_type": "state_transition",
                "timestamp": timestamp,
                "cwd": cwd,
                "triggers_fired": triggers,
                "trigger_explanation": explanation,
                "termination_reason": None,
                "workspace_fingerprint_hash": workspace_fingerprint_hash,
                "dirty_since_last_verify": dirty_since_last_verify,
                "from_phase": current_phase,
                "to_phase": next_phase,
                "phase_reason_code": reason_code,
            }
        )

        return TransitionOutcome(
            next_state=_phase_to_result_state(
                original_state=current_state,
                requested_state=requested_state,
                phase=next_phase,
            ),
            triggers_fired=triggers,
            trigger_explanation=explanation,
        )

    def _emit_phase_transition_denied(
        self,
        *,
        from_phase: str,
        to_phase: str,
        timestamp: str,
        cwd: str,
        deny_reason_code: str,
        phase_reason_code: str,
        reason: Optional[str] = None,
        missing_conditions: Optional[List[str]] = None,
        resolution_hint: Optional[str] = None,
    ) -> None:
        normalized_missing = sorted(
            {
                str(item)
                for item in (missing_conditions or [])
                if isinstance(item, str) and item.strip()
            }
        )
        self.event_log.append_event(
            {
                "event_type": "PHASE_TRANSITION_DENIED",
                "timestamp": timestamp,
                "cwd": cwd,
                "from_phase": from_phase,
                "to_phase": to_phase,
                "reason": reason or deny_reason_code,
                "deny_reason_code": deny_reason_code,
                "phase_reason_code": phase_reason_code,
                "missing_conditions": normalized_missing,
                "resolution_hint": resolution_hint,
            }
        )


def _normalize_phase(value: str) -> str:
    if value in PHASES:
        return value
    return _LEGACY_TO_PHASE.get(value, value)


def _phase_index(phase: str) -> int:
    try:
        return PHASES.index(phase)
    except ValueError:
        return len(PHASES)


def _phase_to_result_state(original_state: str, requested_state: str, phase: str) -> str:
    if original_state in PHASES:
        return phase
    if requested_state in _LEGACY_TO_PHASE or requested_state in {"COMMIT", "VERIFY", "REPAIR", "ACT"}:
        if phase == "Implement":
            return "ACT"
        if phase == "Verify":
            return "VERIFY"
        if phase == "Review":
            if requested_state == "COMMIT":
                return "COMMIT"
            if requested_state == "VERIFY":
                return "REPAIR"
            return "REPAIR"
        if phase == "FAIL":
            return "FAIL"
        return requested_state
    return phase


def _phase_reason_code(phase: str, triggers: List[str]) -> str:
    if not triggers:
        return "default_allow"
    if "mandatory_verifier_phase" in triggers or phase == "Verify":
        return "verification_required"
    if "repair_attempts_exhausted" in triggers:
        return "timeout"
    return "plan_update_required"


def _is_hard_denied_phase_transition(*, current_phase: str, requested_phase: str) -> bool:
    if current_phase == "Explore" and requested_phase in {"Verify", "Review"}:
        return True
    if current_phase == "Plan" and requested_phase in {"Verify", "Review"}:
        return True
    return False


def last_verified_fingerprint_hash(events: List[Dict[str, object]]) -> Optional[str]:
    for event in reversed(events):
        if event.get("event_type") not in {"verifier_result", "VERIFIER_RESULT"}:
            continue
        if event.get("verifier_result") != "pass":
            continue
        fingerprint = event.get("workspace_fingerprint_hash")
        if isinstance(fingerprint, str):
            return fingerprint
    return None


def _plan_artifact_present(*, events: Sequence[Mapping[str, Any]], plan_status: Optional[str]) -> bool:
    if isinstance(plan_status, str) and bool(plan_status.strip()):
        return True
    for event in events:
        event_type = str(event.get("event_type", "")).upper()
        if event_type in {"PLAN_DEFINED", "PLAN_UPDATE", "PLAN_STATUS_CHANGED"}:
            return True
    return False


def export_readiness_vector(
    *,
    events: Sequence[Mapping[str, Any]],
    plan_status: Optional[str],
    dirty_since_last_verify: bool,
    workspace_fingerprint_hash: Optional[str],
    last_verified_fingerprint_hash: Optional[str],
) -> Dict[str, bool]:
    """
    Deterministic compact readiness vector for model-visible STATE projection.
    """
    fingerprint_mismatch = (
        workspace_fingerprint_hash is not None
        and last_verified_fingerprint_hash is not None
        and workspace_fingerprint_hash != last_verified_fingerprint_hash
    )
    needs_verify = bool(dirty_since_last_verify or fingerprint_mismatch)
    explore_floor_passed = compute_explore_floor_passed({"events": events})
    plan_approved = bool(isinstance(plan_status, str) and plan_status in {"APPROVED", "EXECUTING"})
    can_review = not needs_verify
    return {
        "explore_floor_passed": bool(explore_floor_passed),
        "plan_approved": bool(plan_approved),
        "needs_verify": bool(needs_verify),
        "can_review": bool(can_review),
    }


def latest_phase_transition_denial_code(events: Sequence[Mapping[str, Any]]) -> Optional[str]:
    for event in reversed(events):
        if str(event.get("event_type", "")).upper() != "PHASE_TRANSITION_DENIED":
            continue
        deny_reason_code = event.get("deny_reason_code")
        if isinstance(deny_reason_code, str) and deny_reason_code.strip():
            return deny_reason_code.strip()
        break
    return None


def latest_plan_status(events: Sequence[Mapping[str, Any]]) -> Optional[str]:
    for event in reversed(events):
        event_type = str(event.get("event_type", "")).upper()
        if event_type == "PLAN_STATUS_CHANGED":
            to_status = event.get("to_status")
            if isinstance(to_status, str) and to_status.strip():
                return to_status.strip()
        status_value = event.get("status")
        if isinstance(status_value, str) and status_value.strip():
            if event_type in {"PLAN_DEFINED", "PLAN_UPDATE", "PLAN_STEP_STATUS"}:
                return status_value.strip()
    return None

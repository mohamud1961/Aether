from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .event_log import EventLog
from .policy_config import PolicyConfig
from .proceed_gate import ProceedGate, ProceedDecision


@dataclass(frozen=True)
class ResolverOutcome:
    proceed_injected: bool
    governance_decision_id: Optional[str]
    reason_code: str


class PermissionLoopResolver:
    def __init__(
        self,
        proceed_gate: ProceedGate,
        event_log: EventLog,
        *,
        policy_config: Optional[PolicyConfig] = None,
        max_auto_proceeds_per_step: int = 1,
        max_auto_proceeds_per_session: int = 10,
    ) -> None:
        self.proceed_gate = proceed_gate
        self.event_log = event_log
        self.policy_config = policy_config or PolicyConfig.from_env()
        self.max_auto_proceeds_per_step = max_auto_proceeds_per_step
        self.max_auto_proceeds_per_session = max_auto_proceeds_per_session
        self._per_step_counts: Dict[int, int] = defaultdict(int)
        self._per_session_counts: Dict[str, int] = defaultdict(int)

    def resolve(
        self,
        *,
        completion_signals: Sequence[Dict[str, Any]],
        timestamp: str,
        cwd: str,
        session_id: str,
        step_id: Optional[int] = None,
    ) -> ResolverOutcome:
        signal = self._first_permission_request(completion_signals)
        if signal is None:
            return ResolverOutcome(
                proceed_injected=False,
                governance_decision_id=None,
                reason_code="no_permission_request",
            )

        argv_prefix_signature = signal.get("argv_prefix_signature")
        self.event_log.append_event(
            {
                "event_type": "permission_request",
                "timestamp": timestamp,
                "cwd": cwd,
                "argv_prefix_signature": argv_prefix_signature,
                "permission_request_source": signal.get("source"),
            }
        )

        if not self.policy_config.feature_flags.ff_permission_loop_resolver:
            return ResolverOutcome(
                proceed_injected=False,
                governance_decision_id=None,
                reason_code="resolver_disabled",
            )

        step_key = step_id if isinstance(step_id, int) else timestamp
        if self._per_step_counts[step_key] >= self.max_auto_proceeds_per_step:
            decision = self._record_suppression(
                argv_prefix_signature,
                reason_code="permission_loop_suppressed",
                timestamp=timestamp,
                cwd=cwd,
            )
            self._log_proceed_injection(
                timestamp=timestamp,
                cwd=cwd,
                resolution_timestamp=timestamp,
                argv_prefix_signature=argv_prefix_signature,
                decision=decision,
                proceed_injected=False,
            )
            return ResolverOutcome(
                proceed_injected=False,
                governance_decision_id=decision.decision_id,
                reason_code=decision.reason_code,
            )

        if self._per_session_counts[session_id] >= self.max_auto_proceeds_per_session:
            decision = self._record_suppression(
                argv_prefix_signature,
                reason_code="session_limit_reached",
                timestamp=timestamp,
                cwd=cwd,
            )
            self._log_proceed_injection(
                timestamp=timestamp,
                cwd=cwd,
                resolution_timestamp=timestamp,
                argv_prefix_signature=argv_prefix_signature,
                decision=decision,
                proceed_injected=False,
            )
            return ResolverOutcome(
                proceed_injected=False,
                governance_decision_id=decision.decision_id,
                reason_code=decision.reason_code,
            )

        if not self.policy_config.feature_flags.ff_proceed_gate:
            decision = self._record_suppression(
                argv_prefix_signature,
                reason_code="proceed_gate_disabled",
                timestamp=timestamp,
                cwd=cwd,
            )
            self._log_proceed_injection(
                timestamp=timestamp,
                cwd=cwd,
                resolution_timestamp=timestamp,
                argv_prefix_signature=argv_prefix_signature,
                decision=decision,
                proceed_injected=False,
            )
            return ResolverOutcome(
                proceed_injected=False,
                governance_decision_id=decision.decision_id,
                reason_code=decision.reason_code,
            )

        decision = self.proceed_gate.evaluate(
            argv_prefix_signature=_coerce_signature(argv_prefix_signature),
            risk_tier="permission_request",
            timestamp=timestamp,
            cwd=cwd,
            evaluation_suite_mode=self.policy_config.feature_flags.ff_evaluation_suite_mode,
        )

        proceed_injected = decision.allow
        if proceed_injected:
            self._per_step_counts[step_key] += 1
            self._per_session_counts[session_id] += 1

        self._log_proceed_injection(
            timestamp=timestamp,
            cwd=cwd,
            resolution_timestamp=timestamp,
            argv_prefix_signature=argv_prefix_signature,
            decision=decision,
            proceed_injected=proceed_injected,
        )

        return ResolverOutcome(
            proceed_injected=proceed_injected,
            governance_decision_id=decision.decision_id,
            reason_code=decision.reason_code,
        )

    @staticmethod
    def _first_permission_request(
        completion_signals: Sequence[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        for signal in completion_signals:
            if signal.get("type") == "permission_request":
                return signal
        return None

    def _record_suppression(
        self,
        argv_prefix_signature: Optional[object],
        *,
        reason_code: str,
        timestamp: str,
        cwd: str,
    ) -> ProceedDecision:
        return self.proceed_gate.record_decision(
            argv_prefix_signature=_coerce_signature(argv_prefix_signature),
            allow=False,
            reason_code=reason_code,
            risk_tier="permission_request",
            timestamp=timestamp,
            cwd=cwd,
        )

    def _log_proceed_injection(
        self,
        *,
        timestamp: str,
        cwd: str,
        resolution_timestamp: str,
        argv_prefix_signature: Optional[object],
        decision: ProceedDecision,
        proceed_injected: bool,
    ) -> None:
        self.event_log.append_event(
            {
                "event_type": "proceed_injection",
                "timestamp": timestamp,
                "cwd": cwd,
                "resolution_timestamp": resolution_timestamp,
                "argv_prefix_signature": argv_prefix_signature,
                "governance_decision_id": decision.decision_id,
                "reason_code": decision.reason_code,
                "proceed_injected": proceed_injected,
            }
        )


def _coerce_signature(argv_prefix_signature: Optional[object]) -> Optional[List[str]]:
    if isinstance(argv_prefix_signature, list):
        return argv_prefix_signature
    return None

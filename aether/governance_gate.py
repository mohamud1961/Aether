from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set

from .event_log import EventLog
from .hashing import canonical_json_bytes


DEFAULT_POLICY_PROFILE_ID = "default_policy"
ROLES = ["operator", "developer", "auditor"]
APPROVAL_TYPES = [
    "PLAN_HIGH_RISK_UPDATE",
    "PLAN_WAIVER",
    "BUDGET_EXTENSION",
    "HIGH_RISK_EXECUTION",
    "DLP_OVERRIDE",
]

_REQUIRED_HUMAN_APPROVAL_TYPES = {"HIGH_RISK_EXECUTION", "BUDGET_EXTENSION"}
_ALLOWED_APPROVER_ROLES = {
    "PLAN_HIGH_RISK_UPDATE": {"developer", "operator"},
    "PLAN_WAIVER": {"operator"},
    "BUDGET_EXTENSION": {"operator"},
    "HIGH_RISK_EXECUTION": {"operator"},
    "DLP_OVERRIDE": {"auditor", "operator"},
}


@dataclass(frozen=True)
class GovernancePolicy:
    allowlist: Set[str]
    blocklist: Set[str]
    default_decision: str = "deny"


@dataclass(frozen=True)
class GovernanceDecision:
    allow: bool
    reason_code: str
    decision_id: Optional[str] = None
    binding_signature: Optional[str] = None


@dataclass(frozen=True)
class ApprovalDecision:
    granted: bool
    reason_code: str
    event_id: Optional[str]


class GovernanceGate:
    def __init__(self, policy: GovernancePolicy, event_log: EventLog, *, policy_profile: str = "eval") -> None:
        self.policy = policy
        self.event_log = event_log
        self.policy_profile = policy_profile.strip().lower() if isinstance(policy_profile, str) else "eval"
        self._last_decisions: Dict[str, GovernanceDecision] = {}
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._approval_counter: int = 0

    @property
    def approval_counter(self) -> int:
        return self._approval_counter

    def evaluate(
        self,
        action: str,
        risk_tier: str,
        timestamp: str,
        cwd: str,
        step_id: Optional[int] = None,
        tool_args: Dict[str, Any] | None = None,
        policy_profile_id: Optional[str] = None,
    ) -> GovernanceDecision:
        normalized_tool_args = self._canonicalize_tool_args(tool_args or {"action": action})
        normalized_policy_profile = self._normalize_policy_profile_id(policy_profile_id)
        normalized_cwd_scope = self._normalize_cwd_scope(cwd)
        allow = self.policy.default_decision == "allow"
        reason_code = f"default_{self.policy.default_decision}"

        if action in self.policy.blocklist:
            allow = False
            reason_code = "blocklist"
        elif action in self.policy.allowlist:
            allow = True
            reason_code = "allowlist"

        return self.record_decision(
            action=action,
            allow=allow,
            reason_code=reason_code,
            risk_tier=risk_tier,
            timestamp=timestamp,
            cwd=cwd,
            step_id=step_id,
            tool_args=normalized_tool_args,
            policy_profile_id=normalized_policy_profile,
            cwd_scope=normalized_cwd_scope,
        )

    def record_decision(
        self,
        *,
        action: str,
        allow: bool,
        reason_code: str,
        risk_tier: str,
        timestamp: str,
        cwd: str,
        step_id: Optional[int] = None,
        tool_args: Dict[str, Any] | None = None,
        policy_profile_id: Optional[str] = None,
        cwd_scope: Optional[str] = None,
    ) -> GovernanceDecision:
        if tool_args is None:
            raise ValueError("tool_args is required for exact action binding")
        normalized_tool_args = self._canonicalize_tool_args(tool_args)
        normalized_policy_profile = self._normalize_policy_profile_id(policy_profile_id)
        normalized_cwd_scope = self._normalize_cwd_scope(cwd_scope or cwd)
        decision_key = self._decision_key(
            action,
            normalized_tool_args,
            normalized_policy_profile,
            normalized_cwd_scope,
        )

        event = self.event_log.append_event(
            {
                "event_type": "governance_decision",
                "step_id": step_id,
                "timestamp": timestamp,
                "cwd": cwd,
                "tool_name": action,
                "tool_args": normalized_tool_args,
                "policy_profile_id": normalized_policy_profile,
                "governance": {
                    "decision": "allow" if allow else "deny",
                    "reason_code": reason_code,
                    "risk_tier": risk_tier,
                    "decision_key": decision_key,
                    "cwd_scope": normalized_cwd_scope,
                },
            }
        )

        decision = GovernanceDecision(
            allow=allow,
            reason_code=reason_code,
            decision_id=event.get("event_id"),
            binding_signature=decision_key,
        )
        self._last_decisions[decision_key] = decision
        return decision

    def require_decision(
        self,
        action: str,
        tool_args: Dict[str, Any] | None = None,
        policy_profile_id: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> None:
        try:
            decision_key = self._decision_key(action, tool_args, policy_profile_id, cwd)
        except ValueError as exc:
            raise RuntimeError(f"missing_governance_decision: {exc}") from exc

        decision = self._last_decisions.get(decision_key)
        if decision is None:
            raise RuntimeError(
                f"missing_governance_decision: No decision recorded for action '{action}' and provided tool_args"
            )

        if not decision.allow:
            raise RuntimeError(f"governance_deny: Action '{action}' was denied by governance")

    def has_any_decision_for_action(
        self,
        action: str,
        *,
        policy_profile_id: Optional[str] = None,
    ) -> bool:
        normalized_policy_profile = self._normalize_policy_profile_id(policy_profile_id)
        prefix = f"{normalized_policy_profile}::{action}::"
        legacy_prefix = f"{action}:"
        for key in self._last_decisions.keys():
            if not isinstance(key, str):
                continue
            if key.startswith(prefix) or key.startswith(legacy_prefix):
                return True
        return False

    def request_approval(
        self,
        *,
        approval_type: str,
        actor_id: str,
        actor_role: str,
        timestamp: str,
        cwd: str,
        action_fingerprint: Optional[str] = None,
        approval_source: Optional[str] = None,
    ) -> ApprovalDecision:
        normalized_type = str(approval_type).strip().upper()
        normalized_role = str(actor_role).strip().lower()
        normalized_actor = str(actor_id).strip()

        if normalized_type not in APPROVAL_TYPES:
            return self._deny_approval(
                approval_type=normalized_type,
                actor_id=normalized_actor,
                actor_role=normalized_role,
                timestamp=timestamp,
                cwd=cwd,
                reason_code="UNKNOWN",
            )

        if normalized_role not in ROLES:
            return self._deny_approval(
                approval_type=normalized_type,
                actor_id=normalized_actor,
                actor_role=normalized_role,
                timestamp=timestamp,
                cwd=cwd,
                reason_code="GOVERNANCE_DENY",
            )

        # Self-approval is forbidden.
        if normalized_actor.lower() in {"model", "agent", "assistant"}:
            return self._deny_approval(
                approval_type=normalized_type,
                actor_id=normalized_actor,
                actor_role=normalized_role,
                timestamp=timestamp,
                cwd=cwd,
                reason_code="GOVERNANCE_DENY",
            )

        allowed_roles = _ALLOWED_APPROVER_ROLES.get(normalized_type, set())
        if normalized_role not in allowed_roles:
            return self._deny_approval(
                approval_type=normalized_type,
                actor_id=normalized_actor,
                actor_role=normalized_role,
                timestamp=timestamp,
                cwd=cwd,
                reason_code="GOVERNANCE_DENY",
            )

        source = approval_source or ("EVAL_IMPLIED" if self.policy_profile == "eval" else "HUMAN")
        if self.policy_profile == "prod" and normalized_type in _REQUIRED_HUMAN_APPROVAL_TYPES and source != "HUMAN":
            return self._deny_approval(
                approval_type=normalized_type,
                actor_id=normalized_actor,
                actor_role=normalized_role,
                timestamp=timestamp,
                cwd=cwd,
                reason_code="GOVERNANCE_DENY",
            )

        key = self._approval_key(normalized_type, action_fingerprint)
        event = self.event_log.append_event(
            {
                "event_type": "APPROVAL_GRANTED",
                "timestamp": timestamp,
                "cwd": cwd,
                "approval_type": normalized_type,
                "actor_id": normalized_actor,
                "actor_role": normalized_role,
                "approval_source": source,
                "action_fingerprint": action_fingerprint,
                "policy_profile_id": self.policy_profile,
            }
        )
        self._approvals[key] = {
            "event_id": event.get("event_id"),
            "approval_type": normalized_type,
            "action_fingerprint": action_fingerprint,
            "actor_id": normalized_actor,
            "actor_role": normalized_role,
            "approval_source": source,
        }
        self._approval_counter += 1
        return ApprovalDecision(granted=True, reason_code="default_allow", event_id=event.get("event_id"))

    def has_approval(self, *, approval_type: str, action_fingerprint: Optional[str] = None) -> bool:
        key = self._approval_key(approval_type, action_fingerprint)
        if key in self._approvals:
            return True
        wildcard = self._approval_key(approval_type, None)
        return wildcard in self._approvals

    def log_evidence_read(
        self,
        *,
        actor_id: str,
        actor_role: str,
        object_type: str,
        object_id: str,
        redacted: bool = False,
        timestamp: str,
        cwd: str,
    ) -> Dict[str, Any]:
        normalized_role = str(actor_role).strip().lower()
        if normalized_role not in ROLES:
            normalized_role = "auditor"
        return self.event_log.append_event(
            {
                "event_type": "EVIDENCE_READ",
                "timestamp": timestamp,
                "cwd": cwd,
                "actor_id": str(actor_id),
                "actor_role": normalized_role,
                "object_type": str(object_type),
                "object_id": str(object_id),
                "redacted": bool(redacted),
            }
        )

    def _deny_approval(
        self,
        *,
        approval_type: str,
        actor_id: str,
        actor_role: str,
        timestamp: str,
        cwd: str,
        reason_code: str,
    ) -> ApprovalDecision:
        event = self.event_log.append_event(
            {
                "event_type": "APPROVAL_DENIED",
                "timestamp": timestamp,
                "cwd": cwd,
                "approval_type": approval_type,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "deny_reason_code": reason_code,
                "policy_profile_id": self.policy_profile,
            }
        )
        return ApprovalDecision(granted=False, reason_code=reason_code, event_id=event.get("event_id"))

    def _approval_key(self, approval_type: str, action_fingerprint: Optional[str]) -> str:
        normalized_type = str(approval_type).strip().upper()
        fingerprint = str(action_fingerprint) if isinstance(action_fingerprint, str) else "*"
        return f"{normalized_type}::{fingerprint}"

    @staticmethod
    def _decision_key(
        action: str,
        tool_args: Dict[str, Any] | None,
        policy_profile_id: Optional[str] = None,
        cwd_scope: Optional[str] = None,
    ) -> str:
        normalized_policy_profile = GovernanceGate._normalize_policy_profile_id(policy_profile_id)
        normalized_cwd_scope = GovernanceGate._normalize_cwd_scope(cwd_scope)
        canonical_args = canonical_json_bytes(
            GovernanceGate._canonicalize_tool_args(tool_args or {"action": action})
        ).decode("utf-8")
        return f"{normalized_policy_profile}::{action}::{normalized_cwd_scope}::{canonical_args}"

    @staticmethod
    def _normalize_policy_profile_id(policy_profile_id: Optional[str]) -> str:
        if isinstance(policy_profile_id, str) and policy_profile_id.strip():
            return policy_profile_id.strip()
        return DEFAULT_POLICY_PROFILE_ID

    @staticmethod
    def _normalize_cwd_scope(cwd_scope: Optional[str]) -> str:
        if isinstance(cwd_scope, str) and cwd_scope.strip():
            normalized = cwd_scope.strip()
            try:
                path = Path(normalized)
                return path.resolve().as_posix()
            except Exception:
                return normalized
        return "__missing_cwd_scope__"

    @staticmethod
    def _canonicalize_tool_args(tool_args: Dict[str, Any] | None) -> Dict[str, Any]:
        if tool_args is None:
            return {}
        if not isinstance(tool_args, dict):
            raise ValueError("tool_args must be a canonicalizable mapping")

        try:
            canonical_bytes = canonical_json_bytes(tool_args)
        except Exception as exc:
            raise ValueError("tool_args must be canonicalizable") from exc

        try:
            canonicalized = json.loads(canonical_bytes.decode("utf-8"))
        except Exception as exc:
            raise ValueError("tool_args canonicalization failed") from exc

        if not isinstance(canonicalized, dict):
            raise ValueError("tool_args must be a canonicalizable mapping")

        return canonicalized

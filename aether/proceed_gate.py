from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from .governance_gate import GovernanceGate


DEFAULT_ALLOWLIST: Sequence[Sequence[str]] = (
    ("python", "-m", "unittest"),
    ("python", "-m", "pytest"),
    ("pytest",),
    ("npm", "test"),
    ("pnpm", "test"),
    ("yarn", "test"),
    ("make", "test"),
    ("python3", "-m", "pip", "install", "--target"),
    ("npm", "install", "--ignore-scripts", "--no-save", "--no-audit", "--no-fund"),
)

DEFAULT_BLOCKLIST: Sequence[Sequence[str]] = (
    ("rm",),
    ("mv",),
    ("chmod",),
    ("chown",),
    ("sudo",),
    ("bash", "-c"),
    ("sh", "-c"),
    ("eval",),
    ("exec",),
    ("curl",),
    ("wget",),
)

# evaluation suite mode allowlist - commands that are safe in isolated Docker containers
# These override the blocklist when FF_EVALUATION_SUITE_MODE is enabled
evaluation_suite_allowlist: Sequence[Sequence[str]] = (
    ("curl",),
    ("wget",),
    ("chmod",),
    ("chown",),
    ("rm",),
    ("rm", "-rf"),
    ("mv",),
    ("apt-get",),
    ("apt",),
    ("service",),
    ("systemctl",),
    ("eval",),  # Needed for opam, conda, etc
)

_AMBIGUOUS_SINGLETONS = {
    "python",
    "python3",
    "bash",
    "sh",
    "zsh",
    "pwsh",
    "powershell",
    "cmd",
    "node",
}


@dataclass(frozen=True)
class ProceedPolicy:
    allowlist: Sequence[Sequence[str]] = DEFAULT_ALLOWLIST
    blocklist: Sequence[Sequence[str]] = DEFAULT_BLOCKLIST
    default_decision: str = "deny"
    signature_type: str = "argv_prefix_list"


@dataclass(frozen=True)
class ProceedDecision:
    allow: bool
    reason_code: str
    decision_id: Optional[str] = None


class ProceedGate:
    def __init__(self, governance_gate: GovernanceGate, policy: Optional[ProceedPolicy] = None) -> None:
        self.governance_gate = governance_gate
        self.policy = policy or ProceedPolicy()

    def evaluate(
        self,
        *,
        argv_prefix_signature: Optional[List[str]],
        risk_tier: str,
        timestamp: str,
        cwd: str,
        evaluation_suite_mode: bool = False,
    ) -> ProceedDecision:
        normalized = _normalize_signature(argv_prefix_signature)
        if normalized is None:
            decision = self.governance_gate.record_decision(
                action="proceed_injection:unbound",
                allow=False,
                reason_code="unbound_permission_request",
                risk_tier=risk_tier,
                timestamp=timestamp,
                cwd=cwd,
                tool_args={"argv_prefix_signature": argv_prefix_signature},
            )
            return ProceedDecision(
                allow=decision.allow,
                reason_code=decision.reason_code,
                decision_id=decision.decision_id,
            )

        # In evaluation suite mode, check evaluation suite allowlist first (overrides blocklist)
        if evaluation_suite_mode and _matches_prefix(normalized, evaluation_suite_allowlist):
            reason_code = "evaluation_suite_allowlist"
            allow = True
        elif _matches_prefix(normalized, self.policy.blocklist):
            reason_code = "blocklist"
            allow = False
        elif _matches_prefix(normalized, self.policy.allowlist):
            reason_code = "allowlist"
            allow = True
        else:
            reason_code = "signature_mismatch"
            allow = False

        decision = self.governance_gate.record_decision(
            action=_action_label(normalized),
            allow=allow,
            reason_code=reason_code,
            risk_tier=risk_tier,
            timestamp=timestamp,
            cwd=cwd,
            tool_args={"argv_prefix_signature": normalized},
        )
        return ProceedDecision(
            allow=decision.allow,
            reason_code=decision.reason_code,
            decision_id=decision.decision_id,
        )

    def record_decision(
        self,
        *,
        argv_prefix_signature: Optional[List[str]],
        allow: bool,
        reason_code: str,
        risk_tier: str,
        timestamp: str,
        cwd: str,
    ) -> ProceedDecision:
        normalized = _normalize_signature(argv_prefix_signature)
        decision = self.governance_gate.record_decision(
            action=_action_label(normalized),
            allow=allow,
            reason_code=reason_code,
            risk_tier=risk_tier,
            timestamp=timestamp,
            cwd=cwd,
            tool_args={"argv_prefix_signature": normalized},
        )
        return ProceedDecision(
            allow=decision.allow,
            reason_code=decision.reason_code,
            decision_id=decision.decision_id,
        )


def _matches_prefix(argv: List[str], patterns: Iterable[Sequence[str]]) -> bool:
    for prefix in patterns:
        if len(argv) >= len(prefix) and argv[: len(prefix)] == list(prefix):
            return True
    return False


def _normalize_signature(argv_prefix_signature: Optional[List[str]]) -> Optional[List[str]]:
    if argv_prefix_signature is None:
        return None
    if not isinstance(argv_prefix_signature, list):
        return None
    cleaned: List[str] = []
    for item in argv_prefix_signature:
        if not isinstance(item, str):
            return None
        token = item.strip()
        if token:
            cleaned.append(token)
    if not cleaned:
        return None
    if len(cleaned) == 1 and cleaned[0] in _AMBIGUOUS_SINGLETONS:
        return None
    return cleaned


def _action_label(argv: Optional[List[str]]) -> str:
    if not argv:
        return "proceed_injection:unbound"
    return "proceed_injection:" + " ".join(argv)

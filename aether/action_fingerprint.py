from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from .hashing import canonical_json_bytes, sha256_hex


@dataclass(frozen=True)
class RetryDecision:
    allowed: bool
    deny_reason_code: Optional[str]


@dataclass
class _FailureRecord:
    workspace_hash: Optional[str]
    evidence_counter: int
    plan_version_id: Optional[str]
    approval_counter: int
    deny_count: int = 0


def compute_fingerprint(
    tool_name: str,
    tool_args: Dict,
    cwd: str,
    policy_flags: Dict,
    plan_linkage: Dict,
    workspace_hash: str,
) -> str:
    """SHA-256 of deterministic serialization of all inputs."""
    payload = {
        "tool_name": str(tool_name),
        "tool_args": _canonical_object(tool_args),
        "cwd": str(cwd),
        "policy_flags": _canonical_object(policy_flags),
        "plan_linkage": _canonical_object(plan_linkage),
        "workspace_hash": str(workspace_hash),
    }
    return sha256_hex(canonical_json_bytes(payload))


class RetryTracker:
    """Tracks failed action fingerprints and blocks identical no-progress retries."""

    def __init__(self) -> None:
        self._failed: Dict[str, _FailureRecord] = {}

    def evaluate_retry(
        self,
        *,
        fingerprint: str,
        workspace_hash: Optional[str],
        evidence_counter: int,
        plan_version_id: Optional[str],
        approval_counter: int,
    ) -> RetryDecision:
        prior = self._failed.get(fingerprint)
        if prior is None:
            return RetryDecision(allowed=True, deny_reason_code=None)

        progress = (
            prior.workspace_hash != workspace_hash
            or prior.evidence_counter != evidence_counter
            or prior.plan_version_id != plan_version_id
            or prior.approval_counter != approval_counter
        )
        if progress:
            return RetryDecision(allowed=True, deny_reason_code=None)

        deny_reason_code = "RETRY_NO_PROGRESS" if prior.deny_count == 0 else "REPEAT_FAILED_ATTEMPT"
        prior.deny_count += 1
        return RetryDecision(allowed=False, deny_reason_code=deny_reason_code)

    def record_failure(
        self,
        *,
        fingerprint: str,
        workspace_hash: Optional[str],
        evidence_counter: int,
        plan_version_id: Optional[str],
        approval_counter: int,
    ) -> None:
        prior = self._failed.get(fingerprint)
        deny_count = prior.deny_count if prior else 0
        self._failed[fingerprint] = _FailureRecord(
            workspace_hash=workspace_hash,
            evidence_counter=evidence_counter,
            plan_version_id=plan_version_id,
            approval_counter=approval_counter,
            deny_count=deny_count,
        )


def _canonical_object(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical_object(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_canonical_object(item) for item in value]
    return value

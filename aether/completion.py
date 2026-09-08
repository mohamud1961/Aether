from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .ledger import TASK_STATE_SNAPSHOT_BINDING_VERSION, ExecutionLedger
from .monitors import MonitorAlert
from .runtime_ir import CompiledRuntime


@dataclass(frozen=True)
class Blocker:
    code: str
    detail: str = ""
    source: str = ""


@dataclass(frozen=True)
class CompletionDecision:
    ready: bool
    blockers: tuple[Blocker, ...] = ()
    used_check_ids: tuple[str, ...] = ()
    satisfied_obligations: tuple[str, ...] = ()


class FailureParser:
    def classify(self, text: str, *, exit_code: int | None = None) -> str:
        lowered = (text or "").lower()

        if "command not found" in lowered or "not recognized as an internal or external command" in lowered:
            return "missing_capability"
        if (
            "syntax error near unexpected token" in lowered
            or "unterminated quoted string" in lowered
            or "parse error near" in lowered
        ):
            return "check_broken"
        if "no such file or directory" in lowered:
            return "missing_artifact"
        if "interactive_job_requires_session_start" in lowered or "requires session start" in lowered:
            return "mode_mismatch"
        if "tty" in lowered and "required" in lowered:
            return "mode_mismatch"
        if "connection refused" in lowered or "login prompt not found" in lowered or "not ready" in lowered:
            return "service_not_ready"
        if "permission denied" in lowered or "protected path" in lowered or "immutable" in lowered:
            return "integrity_violation"
        if "schema" in lowered and ("missing" in lowered or "invalid" in lowered or "wrong type" in lowered):
            return "schema_mismatch"
        if "timeout" in lowered or "timed out" in lowered:
            return "timeout"
        if self._looks_like_threshold_failure(lowered):
            return "threshold_not_met"
        if "assert" in lowered or "failed" in lowered or "mismatch" in lowered or "traceback" in lowered:
            return "test_failure"
        if exit_code and exit_code != 0:
            return "command_failure"
        return ""

    @staticmethod
    def _looks_like_threshold_failure(text: str) -> bool:
        patterns = (
            r"(accuracy|score|similarity).*(<|below)",
            r"(latency|runtime|size|loss).*(>|above)",
            r"(target|threshold).*(not met|failed)",
        )
        return any(re.search(pattern, text) for pattern in patterns)


class CompletionGate:
    """Mechanical completion custody for the sole PCR production runtime."""

    def evaluate(
        self,
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
        alerts: list[MonitorAlert],
    ) -> CompletionDecision:
        blockers: list[Blocker] = []

        if compiled.completion_policy.require_clean_integrity and ledger.integrity_violations:
            blockers.append(Blocker(
                code="integrity_violation",
                detail=ledger.integrity_violations[-1],
                source="integrity_guard",
            ))

        snapshot_known = ledger.task_state_snapshot_known()
        valid_current_submission_claim = False
        claim_bridges_unknown_snapshot = False
        claim = ledger.latest_receipt("primary_submission_claim")
        claim_payload = claim.payload if claim is not None and isinstance(claim.payload, Mapping) else {}
        if claim is None:
            blockers.append(Blocker(
                code="submission_snapshot_unknown",
                detail="Primary Agent completion claim lacks a canonical task-state snapshot binding",
                source="primary_submission_claim",
            ))
        elif str(claim_payload.get("snapshot_binding_version", "")).strip() != TASK_STATE_SNAPSHOT_BINDING_VERSION:
            blockers.append(Blocker(
                code="submission_snapshot_schema_invalid",
                detail="Primary Agent completion claim lacks the canonical task-state snapshot schema",
                source="primary_submission_claim",
            ))
        else:
            try:
                claim_generation = int(claim_payload.get("task_state_generation", -1))
            except (TypeError, ValueError):
                claim_generation = -1
            claim_snapshot_valid = bool(
                ledger.receipt_payload_is_intact(claim)
                and claim.success is True
                and claim_generation == ledger.task_state_generation()
                and str(claim_payload.get("task_state_snapshot_digest", "")).strip() == ledger.task_state_snapshot_digest()
            )
            valid_current_submission_claim = bool(
                claim_snapshot_valid
                and int(claim_payload.get("current_anchor_count", 0) or 0) > 0
            )
            if not claim_snapshot_valid:
                blockers.append(Blocker(
                    code="submission_snapshot_invalid",
                    detail=(
                        "Primary Agent completion claim is not intact and exactly bound "
                        "to the current task-state boundary"
                    ),
                    source="primary_submission_claim",
                ))
        if valid_current_submission_claim and not snapshot_known:
            claim_bridges_unknown_snapshot = ledger.submission_claim_bridges_unknown_snapshot(claim)
        if not snapshot_known and not claim_bridges_unknown_snapshot:
            blockers.append(Blocker(
                code="task_state_snapshot_unknown",
                detail="task-state mutation boundary is incomplete or receipt payload drifted",
                source="ledger",
            ))

        if not (
            valid_current_submission_claim
            or ledger.has_current_authoritative_observation()
        ):
            blockers.append(Blocker(
                code="no_current_authoritative_observation",
                detail=(
                    "current task state lacks either a valid current Luna evidence binding "
                    "or an independently admitted observation"
                ),
                source="ledger",
            ))

        for alert in alerts:
            if alert.severity in {"error", "fatal"}:
                blockers.append(Blocker(
                    code=alert.blocker_code or alert.code,
                    detail=alert.message,
                    source=alert.code,
                ))

        deduped = self._dedupe_blockers(blockers)
        return CompletionDecision(
            ready=not deduped,
            blockers=tuple(deduped),
            used_check_ids=(),
            satisfied_obligations=ledger.satisfied_obligation_ids(),
        )

    @staticmethod
    def _dedupe_blockers(blockers: list[Blocker]) -> list[Blocker]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[Blocker] = []
        for blocker in blockers:
            key = (blocker.code, blocker.detail, blocker.source)
            if key not in seen:
                seen.add(key)
                deduped.append(blocker)
        return deduped

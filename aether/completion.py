from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .ledger import TASK_STATE_SNAPSHOT_BINDING_VERSION, ExecutionLedger
from .lifecycle import (
    job_execution_state,
    normalize_job_relevance,
    relevance_is_non_blocking,
)
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
    mechanical_status: str = "blocked"
    solver_submission_status: str = "not_recorded"
    submission_currentness: str = "unknown"
    semantic_status: str = "unavailable"
    official_grade_status: str = "unavailable"

    def as_payload(self) -> dict[str, object]:
        """Expose separate custody states without turning one into another."""
        return {
            "solver_submission_status": self.solver_submission_status,
            "submission_currentness": self.submission_currentness,
            "mechanical_readiness": self.mechanical_status,
            "semantic_review_status": self.semantic_status,
            "official_grade_status": self.official_grade_status,
            "blocker_codes": [blocker.code for blocker in self.blockers],
            "semantic_pass_not_inferred_from_mechanical_readiness": True,
        }


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
    """Mechanical completion custody for the sole PERSISTENT production runtime."""

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
        solver_submission_status = "not_recorded"
        submission_currentness = "unknown"
        claim_payload = claim.payload if claim is not None and isinstance(claim.payload, Mapping) else {}
        if claim is None:
            blockers.append(Blocker(
                code="submission_snapshot_unknown",
                detail="Primary Agent completion claim lacks a canonical task-state snapshot binding",
                source="primary_submission_claim",
            ))
        elif str(claim_payload.get("snapshot_binding_version", "")).strip() != TASK_STATE_SNAPSHOT_BINDING_VERSION:
            solver_submission_status = "recorded"
            submission_currentness = "invalid"
            blockers.append(Blocker(
                code="submission_snapshot_schema_invalid",
                detail="Primary Agent completion claim lacks the canonical task-state snapshot schema",
                source="primary_submission_claim",
            ))
        else:
            solver_submission_status = "recorded"
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
                and ledger.submission_claim_has_valid_current_anchor(claim)
            )
            submission_currentness = "current" if valid_current_submission_claim else "stale_or_unbound"
            if not claim_snapshot_valid:
                blockers.append(Blocker(
                    code="submission_snapshot_invalid",
                    detail=(
                        "Primary Agent completion claim is not intact and exactly bound "
                        "to the current task-state boundary"
                    ),
                    source="primary_submission_claim",
                ))
            elif not valid_current_submission_claim:
                blockers.append(Blocker(
                    code="submission_current_anchor_invalid",
                    detail=(
                        "Primary Agent completion claim does not contain an intact cited "
                        "current-anchor receipt matching the declared task-state generation"
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
                    "current task state lacks either a valid current Frontier evidence binding "
                    "or an independently admitted observation"
                ),
                source="ledger",
            ))

        # ``start_job`` represents finite asynchronous work unless the compiled
        # task contract explicitly requires that named process to remain live.
        # Lifecycle termination is not equivalent to successful work: a failed,
        # canceled, stopped, or otherwise unresolved finite job leaves a
        # completion debt.  The debt can be superseded by a replacement job of
        # the same name or by later cited execution/verification evidence; the
        # kernel does not judge whether that evidence is semantically sufficient.
        persistent_services = {
            str(service.name).strip()
            for service in compiled.objective_graph.service_requirements
            if service.must_be_live and str(service.name).strip()
        }
        claim_evidence_ids = {
            str(value).strip()
            for value in claim_payload.get("evidence_receipt_ids", ())
            if str(value).strip()
        }
        claim_evidence_rows = [
            receipt for receipt in ledger.all_receipts()
            if receipt.receipt_id in claim_evidence_ids
        ]
        receipt_order = {
            receipt.receipt_id: index
            for index, receipt in enumerate(ledger.all_receipts())
        }
        def _qualifying_post_failure_evidence(receipt: object, process: Mapping[str, object]) -> bool:
            """Whether cited evidence mechanically replays this failed finite job.

            Completion custody must not infer that an arbitrary successful check or
            command semantically replaces a stopped/failed finite operation.  The
            only non-replacement recovery admitted here is an exact foreground
            replay of the same command in the current task-state generation.
            """
            if getattr(receipt, "success", False) is not True:
                return False
            if str(getattr(receipt, "kind", "")) != "run_command":
                return False
            payload = getattr(receipt, "payload", {})
            if not isinstance(payload, Mapping):
                return False
            replay_command = str(payload.get("command", "")).strip()
            failed_command = str(process.get("command", "")).strip()
            if not replay_command or not failed_command or replay_command != failed_command:
                return False
            if "exit_code" not in payload or "timed_out" not in payload:
                return False
            try:
                exit_code = int(payload["exit_code"])
            except (TypeError, ValueError):
                return False
            return exit_code == 0 and payload.get("timed_out") is False

        for process_id, process in ledger.registered_processes().items():
            launch_mode = str(process.get("launch_mode", "")).strip()
            is_finite_job = launch_mode == "background_job" or (
                not launch_mode
                and bool(process.get("detached", False))
                and str(process.get("kind", "")) == "process_launch"
            )
            if not is_finite_job:
                continue
            name = str(process.get("name", "")).strip()
            if name in persistent_services or process_id in persistent_services:
                continue
            # An older finite-job generation is mechanically superseded only
            # by another finite background-job generation.  A same-name
            # managed service/process is not evidence that the finite work was
            # replaced or completed.
            superseded_by = str(process.get("superseded_by", "")).strip()
            if superseded_by:
                replacement = ledger.registered_processes().get(superseded_by)
                if replacement is not None:
                    replacement_mode = str(replacement.get("launch_mode", "")).strip()
                    replacement_is_finite = replacement_mode == "background_job" or (
                        not replacement_mode
                        and bool(replacement.get("detached", False))
                        and str(replacement.get("kind", "")) == "process_launch"
                    )
                    original_command = str(process.get("command", "")).strip()
                    replacement_command = str(replacement.get("command", "")).strip()
                    replacement_is_same_operation = bool(
                        replacement_is_finite
                        and original_command
                        and replacement_command == original_command
                    )
                    if replacement_is_same_operation:
                        continue
            status = str(process.get("status", "unknown") or "unknown").strip().lower()
            lifecycle_state = job_execution_state(process)
            relevance = normalize_job_relevance(process.get("relevance"))
            generation = str(process.get("process_generation", "")).strip()
            label = name or process_id
            if lifecycle_state == "running":
                detail = (
                    f"finite background job '{label}' ({process_id}) is still live"
                    f" with status={status or 'unknown'} relevance={relevance}"
                )
                if generation:
                    detail += f" generation={generation}"
                detail += "; obtain an exact terminal lifecycle observation before completion"
                blockers.append(Blocker(
                    code="live_finite_background_job",
                    detail=detail,
                    source="ledger.processes",
                ))
                continue

            completed = bool(process.get("completed", False))
            succeeded = process.get("job_succeeded") is True
            if lifecycle_state == "exited_success" and completed and succeeded:
                # Lifecycle success is durable. Whether this completed work is
                # semantically sufficient/current validation for a later-mutated
                # candidate is an evidence/semantic question, not a lifecycle fact.
                continue

            # Optional/abandoned diagnostics still retain their terminal facts,
            # but do not create a pointless replay debt once they are no longer
            # running. Relevance never changes the recorded lifecycle state.
            if relevance_is_non_blocking(relevance, lifecycle_state):
                continue

            terminal_receipt_id = str(
                process.get("terminal_receipt_id")
                or process.get("last_job_probe_receipt_id")
                or process.get("stopped_by")
                or process.get("launch_receipt_id")
                or ""
            ).strip()
            terminal_index = receipt_order.get(terminal_receipt_id, -1)
            later_cited_execution_evidence = any(
                _qualifying_post_failure_evidence(receipt, process)
                and receipt_order.get(receipt.receipt_id, -1) > terminal_index
                for receipt in claim_evidence_rows
            )
            if later_cited_execution_evidence:
                continue

            blockers.append(Blocker(
                code="unsuccessful_finite_background_job",
                detail=(
                    f"finite background job '{label}' ({process_id}) did not produce a verified "
                    f"successful terminal result (status={status or 'unknown'}, "
                    f"execution_state={lifecycle_state}, relevance={relevance}); "
                    "stopping or losing "
                    "the job does not prove its work succeeded, and the completion claim cites no "
                    "later successful execution/verification evidence"
                ),
                source="ledger.processes",
            ))

        for alert in alerts:
            if alert.severity in {"error", "fatal"}:
                blockers.append(Blocker(
                    code=alert.blocker_code or alert.code,
                    detail=alert.message,
                    source=alert.code,
                ))

        deduped = self._dedupe_blockers(blockers)
        semantic_status = self._latest_semantic_status(ledger)
        official_grade_status = self._latest_official_grade_status(ledger)
        return CompletionDecision(
            ready=not deduped,
            blockers=tuple(deduped),
            used_check_ids=(),
            satisfied_obligations=ledger.satisfied_obligation_ids(),
            mechanical_status="ready" if not deduped else "blocked",
            solver_submission_status=solver_submission_status,
            submission_currentness=submission_currentness,
            semantic_status=semantic_status,
            official_grade_status=official_grade_status,
        )

    @staticmethod
    def _latest_semantic_status(ledger: ExecutionLedger) -> str:
        """Read a semantic review verdict when one was actually recorded."""
        for receipt in reversed(ledger.all_receipts()):
            if receipt.kind != "model_verifier_result":
                continue
            payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
            runtime_identity = payload.get("runtime_identity")
            runtime_identity = runtime_identity if isinstance(runtime_identity, Mapping) else {}
            review_arm = str(runtime_identity.get("research_h1_review_arm", "")).strip().lower()
            # A completed mechanical-control review only establishes currentness
            # of the cited evidence.  It must never be surfaced as semantic pass.
            # Unknown review authority is also fail-closed for this status field.
            if review_arm != "semantic":
                return "unavailable"
            verdict = str(payload.get("verdict", "")).strip().lower()
            if verdict in {"completed", "pass", "passed"}:
                return "passed"
            if verdict in {
                "failed", "fail", "needs_repair", "incomplete",
                "incomplete_semantic_mismatch", "probe_inconclusive",
            }:
                return "failed"
            return "unavailable"
        return "unavailable"

    @staticmethod
    def _latest_official_grade_status(ledger: ExecutionLedger) -> str:
        """Read only an explicitly recorded external-grade result."""
        official_kinds = {
            "official_grade",
            "official_grader_result",
        }
        for receipt in reversed(ledger.all_receipts()):
            if receipt.kind not in official_kinds:
                continue
            payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
            value = str(
                payload.get("status", payload.get("grade", payload.get("verdict", "")))
                or ""
            ).strip().lower()
            if value in {"pass", "passed", "complete", "completed", "success"}:
                return "passed"
            if value in {"fail", "failed", "incomplete", "error"}:
                return "failed"
            return "unavailable"
        return "unavailable"

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

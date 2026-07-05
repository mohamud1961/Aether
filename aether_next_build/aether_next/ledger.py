from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from .runtime_ir import CompiledRuntime, ObjectiveGraph
from .verifier import ActiveFindingStore, ModelVerifierResult

if TYPE_CHECKING:
    from .monitors import MonitorAlert


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    step: int
    kind: str
    success: bool
    summary: str
    state_change: bool = False
    failure_class: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CheckOutcome:
    check_id: str
    command: str
    passed: bool
    origin: str
    detail: str = ""
    receipt_id: str = ""
    blocker_code: str = ""


@dataclass
class CandidateRecord:
    candidate_id: str
    summary: str
    status: str = "active"
    metrics: dict[str, float] = field(default_factory=dict)
    passed_checks: set[str] = field(default_factory=set)
    artifacts: set[str] = field(default_factory=set)

    def sort_key(self) -> tuple[int, float, str]:
        return (len(self.passed_checks), sum(self.metrics.values()), self.candidate_id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "summary": self.summary,
            "status": self.status,
            "metrics": dict(sorted(self.metrics.items())),
            "passed_checks": sorted(self.passed_checks),
            "artifacts": sorted(self.artifacts),
        }


@dataclass
class ObligationStatus:
    obligation_id: str
    kind: str
    description: str
    target: str = ""
    status: str = "open"
    evidence_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "kind": self.kind,
            "description": self.description,
            "target": self.target,
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
        }


class ExecutionLedger:
    def __init__(self) -> None:
        self.receipts: list[Receipt] = []
        self._seen_receipts: set[str] = set()
        self.objective_graph: ObjectiveGraph | None = None
        self._artifacts: set[str] = set()
        self._modified_paths: list[str] = []
        self.integrity_violations: list[str] = []
        self.processes: dict[str, dict[str, Any]] = {}
        self.checks: dict[str, CheckOutcome] = {}
        self.candidates: dict[str, CandidateRecord] = {}
        self.metrics: dict[str, float] = {}
        self.installed_capabilities: set[str] = set()
        self.obligations: dict[str, ObligationStatus] = {}
        self.failure_counts: Counter[str] = Counter()
        self.reconfigure_causes: list[str] = []
        self.findings = ActiveFindingStore()

    def seed_capabilities(self, capability_ids: list[str] | tuple[str, ...] | set[str]) -> None:
        for capability_id in capability_ids:
            item = str(capability_id).strip()
            if item:
                self.installed_capabilities.add(item)

    def record_config_realization(self, realization: dict[str, Any], *, receipt_id: str = "config:realization") -> None:
        self.record(Receipt(
            receipt_id=receipt_id, step=0, kind="config_realization", success=True,
            summary="compiled architect config realization",
            payload={"config_realization": dict(realization)},
        ))

    def ensure_objective(self, objective_graph: ObjectiveGraph) -> None:
        self.objective_graph = objective_graph
        for obligation in objective_graph.obligations:
            if obligation.obligation_id not in self.obligations:
                status = "satisfied" if obligation.obligation_id == "integrity:clean" else "open"
                self.obligations[obligation.obligation_id] = ObligationStatus(
                    obligation_id=obligation.obligation_id,
                    kind=obligation.kind,
                    description=obligation.description,
                    target=obligation.target,
                    status=status,
                )
        self._reconcile_objective()

    def record(self, receipt: Receipt) -> None:
        if receipt.receipt_id in self._seen_receipts:
            return
        self._seen_receipts.add(receipt.receipt_id)
        self.receipts.append(receipt)

        if receipt.failure_class:
            self.failure_counts[receipt.failure_class] += 1

        payload = dict(receipt.payload)

        for path in payload.get("artifact_paths", ()) or ():
            normalized = str(path).strip()
            if normalized:
                self._artifacts.add(normalized)
                self._mark_obligation(f"artifact:{normalized}", "satisfied", receipt.receipt_id)

        for path in payload.get("modified_paths", ()) or ():
            normalized = str(path).strip()
            if normalized:
                self._modified_paths.append(normalized)

        integrity_violation = str(payload.get("integrity_violation", "")).strip()
        if integrity_violation:
            self.integrity_violations.append(integrity_violation)
            self._mark_obligation("integrity:clean", "failed", receipt.receipt_id)

        process_id = str(payload.get("process_id", "")).strip()
        if process_id:
            self.processes[process_id] = {
                "process_id": process_id,
                "name": str(payload.get("service_name") or payload.get("name") or ""),
                "command": str(payload.get("command", "")),
                "live": bool(payload.get("live", receipt.success)),
                "detail": str(payload.get("detail", receipt.summary)),
                "step": receipt.step,
                "kind": receipt.kind,
            }

        if receipt.kind == "check_result":
            check_id = str(payload.get("check_id", "")).strip()
            if check_id:
                outcome = CheckOutcome(
                    check_id=check_id,
                    command=str(payload.get("command", "")),
                    passed=bool(payload.get("passed", receipt.success)),
                    origin=str(payload.get("origin", "")),
                    detail=str(payload.get("detail", "")),
                    receipt_id=receipt.receipt_id,
                    blocker_code=str(payload.get("blocker_code", receipt.failure_class)),
                )
                self.checks[check_id] = outcome

            # A passing `test -e <path>` existence check is ground-truth
            # proof the artifact exists (even if created via shell, not
            # write_file).  Mark it present in _artifacts and satisfy the
            # corresponding obligation so the completion gate clears.
            command = str(payload.get("command", ""))
            _TEST_E_PREFIX = "test -e "
            if receipt.success and command.startswith(_TEST_E_PREFIX):
                path = command[len(_TEST_E_PREFIX):].strip()
                if path:
                    self._artifacts.add(path)
                    self._mark_obligation(
                        f"artifact:{path}", "satisfied", receipt.receipt_id,
                    )

        if receipt.kind == "service_probe":
            service_name = str(payload.get("service_name", "")).strip()
            if service_name and bool(payload.get("live", False)):
                self._mark_obligation(f"service:{service_name}", "satisfied", receipt.receipt_id)

        for capability_id in payload.get("capabilities_added", ()) or ():
            item = str(capability_id).strip()
            if item:
                self.installed_capabilities.add(item)

        metric_name = str(payload.get("metric_name", "")).strip()
        metric_value = payload.get("metric_value")
        if metric_name and metric_value is not None:
            try:
                self.metrics[metric_name] = float(metric_value)
            except (TypeError, ValueError):
                pass

        candidate_id = str(payload.get("candidate_id", "")).strip()
        if candidate_id:
            candidate = self.candidates.setdefault(
                candidate_id,
                CandidateRecord(
                    candidate_id=candidate_id,
                    summary=str(payload.get("candidate_summary", candidate_id)),
                ),
            )
            summary = str(payload.get("candidate_summary", "")).strip()
            if summary:
                candidate.summary = summary
            status = str(payload.get("candidate_status", "")).strip()
            if status:
                candidate.status = status
            if metric_name and metric_name in self.metrics:
                candidate.metrics[metric_name] = self.metrics[metric_name]
            for artifact in payload.get("artifact_paths", ()) or ():
                candidate.artifacts.add(str(artifact))
            passed_check = str(payload.get("check_id", "")).strip()
            if passed_check and bool(payload.get("passed", False)):
                candidate.passed_checks.add(passed_check)

        reconfigure_cause = str(payload.get("reconfigure_cause", "")).strip()
        if reconfigure_cause:
            self.reconfigure_causes.append(reconfigure_cause)

        self._reconcile_objective()

    def _reconcile_objective(self) -> None:
        if self.objective_graph is None:
            return

        for deliverable in self.objective_graph.deliverables:
            if deliverable.path in self._artifacts:
                self._mark_obligation(f"artifact:{deliverable.path}", "satisfied", "reconcile")

        for process in self.processes.values():
            service_name = str(process.get("name", "")).strip()
            if service_name and bool(process.get("live", False)):
                recent_probe = self.last_probe_step(service_name)
                if recent_probe is not None:
                    self._mark_obligation(f"service:{service_name}", "satisfied", "reconcile")

        if self.integrity_violations:
            self._mark_obligation("integrity:clean", "failed", "reconcile")
        elif "integrity:clean" in self.obligations and self.obligations["integrity:clean"].status != "failed":
            self._mark_obligation("integrity:clean", "satisfied", "reconcile")

    def _mark_obligation(self, obligation_id: str, status: str, evidence_id: str) -> None:
        obligation = self.obligations.get(obligation_id)
        if obligation is None:
            return
        if obligation.status == "failed" and status != "failed":
            if evidence_id not in obligation.evidence_ids:
                obligation.evidence_ids.append(evidence_id)
            return
        obligation.status = status
        if evidence_id and evidence_id not in obligation.evidence_ids:
            obligation.evidence_ids.append(evidence_id)

    def current_artifacts(self) -> set[str]:
        return set(self._artifacts)

    def modified_paths(self) -> tuple[str, ...]:
        return tuple(self._modified_paths)

    def live_processes(self) -> dict[str, dict[str, Any]]:
        return {
            process_id: dict(payload)
            for process_id, payload in sorted(self.processes.items())
            if bool(payload.get("live", False))
        }

    def open_obligations(self) -> list[ObligationStatus]:
        return [
            obligation
            for _, obligation in sorted(self.obligations.items())
            if obligation.status != "satisfied"
        ]

    def satisfied_obligation_ids(self) -> tuple[str, ...]:
        return tuple(
            obligation_id
            for obligation_id, obligation in sorted(self.obligations.items())
            if obligation.status == "satisfied"
        )

    def obligation_snapshot(self) -> list[dict[str, Any]]:
        return [obligation.as_dict() for _, obligation in sorted(self.obligations.items())]

    def recent_receipts(self, limit: int, kind: str | None = None) -> list[Receipt]:
        items = self.receipts if kind is None else [receipt for receipt in self.receipts if receipt.kind == kind]
        return items[-max(0, limit):]

    def recent_progress(self, limit: int) -> list[Receipt]:
        items = [
            receipt
            for receipt in self.receipts
            if receipt.state_change
            or (receipt.kind == "check_result" and receipt.success)
            or (receipt.kind == "schema_validation" and receipt.success)
        ]
        return items[-max(0, limit):]

    def failure_clusters(self, limit: int = 4) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for receipt in self.recent_receipts(20):
            if receipt.success:
                continue
            key = receipt.failure_class or receipt.kind
            counter[key] += 1
        return [
            {"failure_class": failure_class, "count": count}
            for failure_class, count in counter.most_common(limit)
        ]

    def files_already_read(self, limit: int = 12) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        last_step: dict[str, int] = {}
        for receipt in self.receipts:
            if receipt.kind != "read_file" or not receipt.success:
                continue
            path = str(receipt.payload.get("path", "")).strip()
            if not path:
                continue
            counter[path] += 1
            last_step[path] = receipt.step
        return [
            {"path": path, "read_count": count, "last_step": last_step[path]}
            for path, count in counter.most_common(limit)
        ]

    def repeated_actions(self, limit: int = 8) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        last_step: dict[str, int] = {}
        for receipt in self.receipts:
            key = ""
            if receipt.kind == "run_command":
                key = str(receipt.payload.get("command", "")).strip()
            elif receipt.kind == "read_file" and receipt.success:
                path = str(receipt.payload.get("path", "")).strip()
                if path:
                    key = f"read_file:{path}"
            if not key:
                continue
            counter[key] += 1
            last_step[key] = receipt.step
        repeated = [
            {"action": action, "count": count, "last_step": last_step[action]}
            for action, count in counter.most_common()
            if count > 1
        ]
        return repeated[: max(0, limit)]

    def query_memory(
        self,
        query: str,
        limit: int = 8,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search structured receipts for evidence relevant to *query*."""
        from .memory_query import query_receipts

        return query_receipts(self.receipts, query, filters=filters, max_results=limit)

    def repeat_guard(self, *, kind: str, target: str) -> dict[str, Any]:
        from .memory_query import repeat_guard

        return repeat_guard(self.receipts, kind=kind, target=target)

    def apply_verifier_result(
        self,
        result: ModelVerifierResult,
        *,
        step: int,
        compiled: CompiledRuntime | None = None,
    ) -> None:
        del compiled
        self.findings.apply_result(result, step=step, resolve_stale_by_evidence=False)
        self.record(Receipt(
            receipt_id=f"step-{step}:model_verifier", step=step,
            kind="model_verifier_result", success=result.verdict == "completed",
            summary=f"model verifier verdict: {result.verdict}",
            state_change=result.verdict == "completed",
            failure_class="" if result.verdict == "completed" else result.verdict,
            payload=result.as_dict(),
        ))

    def active_finding_context(self, step: int, limit: int = 4) -> list[dict[str, Any]]:
        return self.findings.context(current_step=step, limit=limit)

    def no_progress_streak(self) -> int:
        streak = 0
        for receipt in reversed(self.receipts):
            if receipt.state_change or (receipt.kind == "check_result" and receipt.success):
                break
            streak += 1
        return streak

    def latest_checks(self, check_ids: tuple[str, ...]) -> tuple[CheckOutcome, ...]:
        outcomes: list[CheckOutcome] = []
        for check_id in check_ids:
            outcome = self.checks.get(check_id)
            if outcome is not None:
                outcomes.append(outcome)
        return tuple(outcomes)

    def candidate_leaderboard(self, limit: int) -> list[dict[str, Any]]:
        candidates = sorted(
            self.candidates.values(),
            key=lambda candidate: candidate.sort_key(),
            reverse=True,
        )
        return [candidate.as_dict() for candidate in candidates[: max(0, limit)]]

    def last_probe_step(self, service_name: str) -> int | None:
        for receipt in reversed(self.receipts):
            if receipt.kind != "service_probe":
                continue
            payload_name = str(receipt.payload.get("service_name", "")).strip()
            if payload_name == service_name:
                return receipt.step
        return None

    def latest_receipt(self, kind: str) -> Receipt | None:
        for receipt in reversed(self.receipts):
            if receipt.kind == kind:
                return receipt
        return None

    def all_receipts(self) -> tuple[Receipt, ...]:
        return tuple(self.receipts)

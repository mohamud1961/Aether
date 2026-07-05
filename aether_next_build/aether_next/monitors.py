from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from .ledger import ExecutionLedger
from .runtime_ir import ActionRequest, CompiledRuntime, ObjectiveGraph


@dataclass(frozen=True)
class MonitorAlert:
    code: str
    message: str
    severity: str = "error"
    blocker_code: str = ""
    recommend_reconfigure: bool = False


class IntegrityGuards:
    def explain_path_violation(self, objective: ObjectiveGraph, path: str) -> str | None:
        normalized = path.strip()
        if not normalized:
            return "empty path"
        for protected in objective.protected_paths:
            if normalized == protected or normalized.startswith(protected + "/"):
                return f"protected path edit: {normalized}"
        allowed_roots = objective.allowed_edit_roots or (".",)
        if not any(self._is_under_root(normalized, root) for root in allowed_roots):
            return f"path outside allowed_edit_roots: {normalized}"
        return None

    def validate_modified_paths(self, objective: ObjectiveGraph, paths: tuple[str, ...]) -> str | None:
        for path in paths:
            violation = self.explain_path_violation(objective, path)
            if violation:
                return violation
        return None

    @staticmethod
    def _is_under_root(path: str, root: str) -> bool:
        if root in {"", "."}:
            return not path.startswith("../")
        return path == root or path.startswith(root + "/")


class LocalOnlySafetyGuard:
    _URL_RE = re.compile(r"https?://[^\s'\"`]+", re.IGNORECASE)
    _SSH_RE = re.compile(r"\bssh\s+(?:-[^\s]+\s+)*(?:[^@\s]+@)?([A-Za-z0-9_.-]+)\b", re.IGNORECASE)

    def violation(self, compiled: CompiledRuntime, action: ActionRequest) -> str | None:
        if not compiled.refusal_policy.allowed_local_categories:
            return None
        if not compiled.refusal_policy.forbid_external_targets:
            return None

        for text in self._iter_strings(action.arguments):
            for url in self._URL_RE.findall(text):
                host = (urlparse(url).hostname or "").lower()
                if host and host not in {"localhost", "127.0.0.1", "::1"}:
                    return f"external target blocked by local-only policy: {url}"
            ssh_match = self._SSH_RE.search(text)
            if ssh_match:
                host = ssh_match.group(1).lower()
                if host not in {"localhost", "127.0.0.1", "::1"}:
                    return f"external target blocked by local-only policy: ssh {host}"
        return None

    def _iter_strings(self, value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            items: list[str] = []
            for item in value.values():
                items.extend(self._iter_strings(item))
            return items
        if isinstance(value, (list, tuple, set)):
            items = []
            for item in value:
                items.extend(self._iter_strings(item))
            return items
        return []


class MonitorRunner:
    def __init__(self) -> None:
        self.integrity_guards = IntegrityGuards()

    def run(self, compiled: CompiledRuntime, ledger: ExecutionLedger) -> list[MonitorAlert]:
        alerts: list[MonitorAlert] = []

        if "no_progress" in compiled.enforced_monitors:
            recent_failures = [
                receipt
                for receipt in ledger.recent_receipts(6)
                if not receipt.success and receipt.failure_class
            ]
            if len(recent_failures) >= 3:
                tail = recent_failures[-3:]
                failure_classes = {receipt.failure_class for receipt in tail}
                if len(failure_classes) == 1 and not any(receipt.state_change for receipt in tail):
                    repeated = next(iter(failure_classes))
                    alerts.append(
                        MonitorAlert(
                            code="no_progress",
                            message=f"Repeated failure class with no progress: {repeated}",
                            severity="error",
                            blocker_code="no_progress",
                            recommend_reconfigure=repeated in {"missing_capability", "mode_mismatch", "service_not_ready"},
                        )
                    )

        if "service_liveness" in compiled.enforced_monitors:
            live_processes = ledger.live_processes()
            for service in compiled.objective_graph.service_requirements:
                matches = [
                    payload
                    for payload in live_processes.values()
                    if payload.get("name") == service.name
                ]
                if service.must_be_live and not matches:
                    alerts.append(
                        MonitorAlert(
                            code="service_not_live",
                            message=f"Required service '{service.name}' is not live.",
                            severity="error",
                            blocker_code="service_not_ready",
                            recommend_reconfigure=True,
                        )
                    )
                    continue
                if compiled.process_policy.require_fresh_probe and ledger.last_probe_step(service.name) is None:
                    alerts.append(
                        MonitorAlert(
                            code="stale_service_proof",
                            message=f"Required service '{service.name}' has no fresh probe receipt.",
                            severity="error",
                            blocker_code="service_not_ready",
                            recommend_reconfigure=False,
                        )
                    )

        if "artifact_accounting" in compiled.enforced_monitors:
            missing = [
                deliverable.path
                for deliverable in compiled.objective_graph.deliverables
                if deliverable.required and deliverable.path not in ledger.current_artifacts()
            ]
            if missing:
                alerts.append(
                    MonitorAlert(
                        code="missing_artifacts",
                        message=f"Required artifacts not yet present: {', '.join(sorted(missing))}",
                        severity="warning",
                        blocker_code="missing_artifacts",
                        recommend_reconfigure=False,
                    )
                )

        if "integrity_guard" in compiled.enforced_monitors:
            for violation in dict.fromkeys(ledger.integrity_violations):
                alerts.append(
                    MonitorAlert(
                        code="integrity_violation",
                        message=violation,
                        severity="error",
                        blocker_code="integrity_violation",
                        recommend_reconfigure=False,
                    )
                )

        return alerts

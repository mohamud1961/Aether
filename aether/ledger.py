from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping, TYPE_CHECKING

from .runtime_ir import CompiledRuntime, ObjectiveGraph
from .verifier import ActiveFindingStore, ModelVerifierResult

if TYPE_CHECKING:
    from .monitors import MonitorAlert


TASK_STATE_SNAPSHOT_BINDING_VERSION = "task_state_snapshot.v1"
_SNAPSHOT_RECOVERY_OBSERVATION_KINDS = frozenset({
    "inspection_record",
    "check_result",
    "schema_validation",
    "job_probe",
    "service_probe",
    "read_file",
    "read_file_page",
    "read_output",
    "grep_output",
    "inspect_artifact",
})

# A current Luna completion claim may bridge an explicitly unknown *global*
# task-state boundary without rewriting that boundary as globally known.  The
# bridge must cite a fresh, successful, typed observation made after the latest
# opaque boundary.  Mutating actions and generic shell commands are excluded:
# they create/extend uncertainty rather than observe a bounded current fact.
_SNAPSHOT_CLAIM_BRIDGE_OBSERVATION_KINDS = frozenset({
    # Direct, typed observations of current task state.  Deliberately exclude
    # generic shell output paging, provider/reviewer conclusions, and control
    # receipts: those may carry useful evidence but do not independently
    # observe the current task world.
    "inspection_record",
    "check_result",
    "schema_validation",
    "job_probe",
    "service_probe",
    "read_file",
    "read_file_page",
    "artifact_inspection",
})


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


def _canonical_payload(value: Any) -> str:
    """Serialize a receipt payload deterministically for identity checks."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _payload_sha256(value: Any) -> str:
    return sha256(_canonical_payload(value).encode("utf-8")).hexdigest()


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
        self._removed_paths: list[str] = []
        self.integrity_violations: list[str] = []
        self.processes: dict[str, dict[str, Any]] = {}
        self.checks: dict[str, CheckOutcome] = {}
        self.candidates: dict[str, CandidateRecord] = {}
        self.metrics: dict[str, float] = {}
        self.installed_capabilities: set[str] = set()
        # Current live environment capabilities may appear or disappear during
        # a run (for example a desktop/VNC endpoint started by the Solver).
        # Keep this separate from monotonic installed capabilities so model
        # context and action admission can reflect the exact decision boundary
        # without rewriting the compiled runtime.
        self.runtime_capabilities: set[str] = set()
        self.obligations: dict[str, ObligationStatus] = {}
        self.failure_counts: Counter[str] = Counter()
        self.findings = ActiveFindingStore()
        # ``step`` is a trace position, not an execution budget.  Keep the
        # independently auditable quantities here and append a receipt for
        # every increment so result rows never infer them from step numbers.
        self._accounting: Counter[str] = Counter()
        # Monotonic freshness generation for grader-visible task state. It
        # advances on a proven mutation OR an explicitly incomplete mutation
        # observation. The latter does not fabricate ``state_change`` or task
        # progress; it only invalidates evidence that can no longer be proven
        # current. This remains separate from trace/provider/control receipts.
        self._task_state_generation = 0
        # Keep ordinary mutable payload dictionaries for compatibility, but
        # retain an append-time identity so evidence consumers can fail closed
        # if a recorded payload is changed in place later.
        self._receipt_payload_digests: dict[str, str] = {}
        self.runtime_identity: dict[str, Any] = {}
        self.runtime_budget_state: dict[str, Any] = {}

    def update_runtime_budget_state(self, state: Mapping[str, Any]) -> None:
        """Replace factual dynamic wall-clock budget state for model context."""
        self.runtime_budget_state = {str(key): value for key, value in state.items()}

    def install_runtime_identity(self, identity: Mapping[str, Any]) -> None:
        normalized = {str(key): value for key, value in identity.items()}
        if self.runtime_identity and self.runtime_identity != normalized:
            raise ValueError("runtime identity is immutable within one task run")
        self.runtime_identity = normalized
        self.record(Receipt(
            receipt_id="runtime:identity",
            step=0,
            kind="runtime_identity",
            success=True,
            summary="installed stable task-run and Primary Agent identity",
            payload={"runtime_identity": dict(normalized)},
        ))

    def seed_capabilities(self, capability_ids: list[str] | tuple[str, ...] | set[str]) -> None:
        for capability_id in capability_ids:
            item = str(capability_id).strip()
            if item:
                self.installed_capabilities.add(item)

    def set_runtime_capabilities(self, capability_ids: list[str] | tuple[str, ...] | set[str]) -> bool:
        """Replace current live capability truth; return whether it changed."""
        normalized = {
            str(capability_id).strip()
            for capability_id in capability_ids
            if str(capability_id).strip()
        }
        changed = normalized != self.runtime_capabilities
        self.runtime_capabilities = normalized
        return changed

    def record_config_realization(self, realization: dict[str, Any], *, receipt_id: str = "config:realization") -> None:
        self.record(Receipt(
            receipt_id=receipt_id, step=0, kind="config_realization", success=True,
            summary="compiled mechanical runtime realization",
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

    def receipt_payload_sha256(self, receipt_id: str) -> str | None:
        """Return the append-time payload identity for one recorded receipt."""
        return self._receipt_payload_digests.get(str(receipt_id))

    def receipt_payload_is_intact(self, receipt: Receipt | str) -> bool:
        """Whether a recorded receipt still has its append-time payload.

        Payload dictionaries remain mutable for legacy construction paths. Any
        provenance consumer that uses a receipt as evidence must check this
        boundary before admitting it.
        """
        receipt_id = receipt if isinstance(receipt, str) else receipt.receipt_id
        expected = self._receipt_payload_digests.get(str(receipt_id))
        if expected is None:
            return False
        current = next(
            (item for item in self.receipts if item.receipt_id == str(receipt_id)),
            None,
        )
        return current is not None and _payload_sha256(current.payload) == expected

    def receipt_snapshot_binding_is_current(
        self,
        receipt: Receipt | str,
        *,
        expected_generation: int | None = None,
        expected_digest: str | None = None,
        require_version: bool = True,
    ) -> bool:
        """Validate one receipt's complete current-snapshot provenance.

        This is deliberately stricter than checking a copied generation field:
        the receipt must still match its append-time payload digest, the ledger
        must know all task-state boundaries, the derived receipt generation and
        payload generation must agree, and the payload must carry the canonical
        snapshot version/digest. Legacy or partially populated records are
        therefore non-admissible rather than compatibility-proof.
        """
        if (
            not self.task_state_snapshot_known()
            or not self.receipt_payload_is_intact(receipt)
        ):
            return False
        receipt_id = receipt if isinstance(receipt, str) else receipt.receipt_id
        current = next(
            (item for item in self.receipts if item.receipt_id == str(receipt_id)),
            None,
        )
        if (
            current is None
            or current.success is not True
            or not isinstance(current.payload, Mapping)
        ):
            return False
        payload = current.payload
        generation = self.task_state_generation() if expected_generation is None else int(expected_generation)
        digest = self.task_state_snapshot_digest() if expected_digest is None else str(expected_digest)
        try:
            payload_generation = int(payload.get("task_state_generation", -1))
            derived_generation = self.receipt_task_state_generation(current.receipt_id)
        except (TypeError, ValueError):
            return False
        if payload_generation != generation or derived_generation != generation:
            return False
        if payload.get("task_state_snapshot_known") is not True:
            # A direct observation can be the first successful observation
            # after an incomplete mutation inventory.  Its payload was
            # necessarily stamped while the prior boundary was unknown, but
            # the later receipt itself is what re-establishes a current
            # snapshot.  Permit that narrow recovery case only for the
            # typed/read-only observation kinds; arbitrary receipts remain
            # fail-closed.
            if not (
                current.success is True
                and current.receipt_id
                and current.kind in _SNAPSHOT_RECOVERY_OBSERVATION_KINDS
            ):
                return False
        if str(payload.get("task_state_snapshot_digest", "")).strip() != digest:
            return False
        if require_version and str(payload.get("snapshot_binding_version", "")).strip() != TASK_STATE_SNAPSHOT_BINDING_VERSION:
            return False
        return True

    def current_snapshot_binding_payload(self) -> dict[str, Any]:
        """Return the canonical binding fields for a non-mutating receipt.

        Callers must use this only for observations recorded at the current
        task-state boundary.  Mutating receipts advance the boundary and must
        not copy a pre-record snapshot into their payload.
        """
        return {
            "task_state_generation": self.task_state_generation(),
            "task_state_snapshot_digest": self.task_state_snapshot_digest(),
            "task_state_snapshot_known": self.task_state_snapshot_known(),
            "snapshot_binding_version": TASK_STATE_SNAPSHOT_BINDING_VERSION,
        }

    def model_verifier_result_payload(
        self,
        result: ModelVerifierResult,
        *,
        compiled: CompiledRuntime | None = None,
        packet_signature: str = "",
        extra_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the complete model-verifier payload before it is recorded.

        Model-verifier receipts are provenance boundaries, not mutable scratch
        records.  All result, snapshot, runtime/proof identity, and caller
        evidence fields must therefore be assembled before :meth:`record`
        computes the append-time payload digest.  Canonical fields are applied
        last so an optional diagnostic payload cannot replace their bindings.
        """
        from .proof_contract import (
            PROOF_REGISTRY_DIGEST,
            PROOF_REGISTRY_VERSION,
            proof_requirements_identity,
        )

        payload = dict(result.as_dict())
        if extra_payload:
            payload.update(dict(extra_payload))

        contract_identity = ""
        if compiled is not None and compiled.proof_requirements:
            contract_identity = (
                compiled.proof_requirements_identity
                or proof_requirements_identity(compiled.proof_requirements)
            )
        payload.update({
            **self.current_snapshot_binding_payload(),
            "packet_signature": str(packet_signature),
            "runtime_identity": dict(self.runtime_identity),
            "proof_contract_identity": contract_identity,
            "proof_registry_version": PROOF_REGISTRY_VERSION,
            "proof_registry_digest": PROOF_REGISTRY_DIGEST,
        })
        return payload

    def record_model_verifier_result(
        self,
        result: ModelVerifierResult,
        *,
        receipt_id: str,
        step: int,
        summary: str | None = None,
        failure_class: str = "",
        compiled: CompiledRuntime | None = None,
        packet_signature: str = "",
        extra_payload: Mapping[str, Any] | None = None,
    ) -> Receipt:
        """Append one complete model-verifier result atomically."""
        receipt = Receipt(
            receipt_id=receipt_id,
            step=step,
            kind="model_verifier_result",
            success=result.verdict == "completed",
            summary=summary or f"completion review outcome: {result.verdict}",
            state_change=False,
            failure_class=failure_class or ("" if result.verdict == "completed" else result.verdict),
            payload=self.model_verifier_result_payload(
                result,
                compiled=compiled,
                packet_signature=packet_signature,
                extra_payload=extra_payload,
            ),
        )
        self.record(receipt)
        return receipt

    def task_state_snapshot_known(self) -> bool:
        """Whether observed task-state boundaries are complete enough to bind.

        A coarse, truncated, or unavailable mutation inventory is an unknown
        boundary. It must not be converted into a clean snapshot merely
        because no concrete path delta was reported.
        """
        boundaries: list[tuple[int, Receipt, Mapping[str, Any]]] = []
        for index, receipt in enumerate(self.receipts):
            payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
            state_delta = payload.get("state_delta")
            if not (
                self._changes_task_state(receipt)
                or self.is_uncertain_task_state_boundary(receipt)
            ):
                continue
            boundaries.append((index, receipt, payload))
        if not boundaries:
            return True

        # A historical coarse/unavailable boundary is not permanent poison. A
        # later successful direct observation (or a later complete mutation)
        # re-establishes the current boundary. Only an unresolved *latest*
        # boundary remains unknown.
        latest_index, latest_receipt, latest_payload = boundaries[-1]
        latest_delta = latest_payload.get("state_delta")
        latest_uncertain = (
            isinstance(latest_delta, Mapping)
            and str(latest_delta.get("mutation_detection_status", "")).strip()
            in {"unavailable", "truncated", "coarse"}
        )
        if not self.receipt_payload_is_intact(latest_receipt):
            return False
        if latest_uncertain:
            scope = str(latest_delta.get("mutation_detection_scope", "")).strip() if isinstance(latest_delta, Mapping) else ""
            opaque_task_world_scopes = {
                "opaque_run_command_task_world",
                "opaque_terminal_task_world",
                "opaque_process_task_world",
                "opaque_bootstrap_task_world",
            }
            recovery_kinds = (
                frozenset({"inspection_record"})
                if scope in opaque_task_world_scopes
                else _SNAPSHOT_RECOVERY_OBSERVATION_KINDS
            )
            for receipt in self.receipts[latest_index + 1:]:
                if not self.receipt_payload_is_intact(receipt) or receipt.success is not True:
                    continue
                if receipt.kind in recovery_kinds:
                    return True
            return False
        # Earlier boundary uncertainty has been superseded by this intact,
        # complete latest boundary. Do not let stale history block the run.
        return True

    def submission_claim_bridges_unknown_snapshot(self, claim: Receipt | None) -> bool:
        """Whether *claim* safely bridges the latest explicit unknown boundary.

        This does **not** change :meth:`task_state_snapshot_known`.  A generic
        shell/process boundary can leave the global task world epistemically
        unknown, while Luna may still possess a current typed observation of
        the exact fact it is citing for completion (for example, a live service
        probe after a curl command).  In that case mechanical custody should
        validate the claim/evidence lineage rather than require an unavailable
        reviewer to make the whole world "known".

        Fail closed unless the latest unknown boundary is itself intact and
        explicitly coarse/truncated/unavailable, the claim is intact/current,
        and at least one cited current-anchor observation was recorded after
        that boundary.  Stale, mutating, failed, or control-plane receipts can
        never bridge it.
        """
        if self.task_state_snapshot_known():
            return True
        if claim is None or claim.kind != "primary_submission_claim":
            return False
        if claim.success is not True or not self.receipt_payload_is_intact(claim):
            return False
        payload = claim.payload if isinstance(claim.payload, Mapping) else {}
        if str(payload.get("snapshot_binding_version", "")).strip() != TASK_STATE_SNAPSHOT_BINDING_VERSION:
            return False
        try:
            claim_generation = int(payload.get("task_state_generation", -1))
        except (TypeError, ValueError):
            return False
        if claim_generation != self.task_state_generation():
            return False
        if str(payload.get("task_state_snapshot_digest", "")).strip() != self.task_state_snapshot_digest():
            return False
        if int(payload.get("current_anchor_count", 0) or 0) <= 0:
            return False

        latest_boundary_index: int | None = None
        for index, receipt in enumerate(self.receipts):
            if not (
                self._changes_task_state(receipt)
                or self.is_uncertain_task_state_boundary(receipt)
            ):
                continue
            latest_boundary_index = index
        if latest_boundary_index is None:
            return False
        boundary = self.receipts[latest_boundary_index]
        if not self.receipt_payload_is_intact(boundary):
            # Payload drift is an integrity/custody failure, not bridgeable
            # epistemic uncertainty.
            return False
        boundary_payload = boundary.payload if isinstance(boundary.payload, Mapping) else {}
        delta = boundary_payload.get("state_delta")
        if not isinstance(delta, Mapping):
            return False
        if str(delta.get("mutation_detection_status", "")).strip() not in {
            "unavailable", "truncated", "coarse",
        }:
            return False

        evidence_bindings = payload.get("evidence_bindings", ())
        declared_receipt_ids = payload.get("evidence_receipt_ids", ())
        if not isinstance(evidence_bindings, list) or not isinstance(declared_receipt_ids, list):
            return False
        declared_receipt_ids = {str(item).strip() for item in declared_receipt_ids if str(item).strip()}
        receipts_by_id = {receipt.receipt_id: (index, receipt) for index, receipt in enumerate(self.receipts)}
        for binding in evidence_bindings:
            if not isinstance(binding, Mapping) or str(binding.get("role", "")) != "current_anchor":
                continue
            try:
                evidence_generation = int(binding.get("task_state_generation", -1))
            except (TypeError, ValueError):
                continue
            if evidence_generation != self.task_state_generation():
                continue
            receipt_id = str(binding.get("receipt_id", "")).strip()
            if receipt_id not in declared_receipt_ids:
                continue
            indexed = receipts_by_id.get(receipt_id)
            if indexed is None:
                continue
            evidence_index, evidence = indexed
            if evidence.success is not True or not self.receipt_payload_is_intact(evidence):
                continue
            evidence_payload = evidence.payload if isinstance(evidence.payload, Mapping) else {}
            # A successful arbitrary shell command remains an opaque *global*
            # task-world boundary.  However, Luna may cite the exact result of
            # that same latest command as a claim-local current anchor when the
            # executor completely observed the task workspace around it.  This
            # does not make task_state_snapshot_known() true and does not grant
            # the command independent semantic authority; it only preserves the
            # exact, current evidence lineage Luna selected.  Any later boundary,
            # truncated workspace inventory, timeout, failure, integrity issue,
            # or payload drift fails closed.
            same_boundary_command_anchor = bool(
                evidence_index == latest_boundary_index
                and evidence is boundary
                and evidence.kind == "run_command"
                and str(delta.get("mutation_detection_scope", "")).strip()
                    == "opaque_run_command_task_world"
                and str(delta.get("workspace_mutation_detection_status", "")).strip()
                    == "complete"
                and str(delta.get("path_set_delta_status", "")).strip() == "complete"
                and delta.get("before_truncated") is False
                and delta.get("after_truncated") is False
                and int(evidence_payload.get("exit_code", -1)) == 0
                and evidence_payload.get("timed_out") is not True
                and not str(evidence_payload.get("integrity_violation", "")).strip()
                and bool(str(evidence_payload.get("stdout_handle", "")).strip())
                and bool(str(evidence_payload.get("stderr_handle", "")).strip())
            )
            if same_boundary_command_anchor:
                if self.receipt_task_state_generation(evidence.receipt_id) != self.task_state_generation():
                    continue
                return True
            if evidence_index <= latest_boundary_index:
                continue
            if evidence.kind not in _SNAPSHOT_CLAIM_BRIDGE_OBSERVATION_KINDS:
                continue
            if evidence.kind in {"service_probe", "job_probe"}:
                # A live endpoint/job is a bridge only when Aether can bind it
                # to the managed generation.  An unrelated listener must not
                # become completion authority merely because it answers.
                if evidence_payload.get("process_generation_verified") is not True:
                    continue
                if not str(evidence_payload.get("process_generation", "")).strip():
                    continue
            if self.receipt_task_state_generation(evidence.receipt_id) != self.task_state_generation():
                continue
            return True
        return False

    def task_state_snapshot_digest(self) -> str:
        """Digest the ledger's observed task-state boundary, not control noise.

        Inspection and provider receipts do not alter this digest. A changed
        task-state payload produces an ``invalid_payload`` marker, so a claim
        bound before the mutation cannot silently continue to match it. This
        is an observed-ledger identity, not a claim that arbitrary external
        state is physically observable; unknown mutation boundaries are
        reported separately by :meth:`task_state_snapshot_known`.
        """
        rows: list[dict[str, Any]] = []
        for receipt in self.receipts:
            if not (
                self._changes_task_state(receipt)
                or self.is_uncertain_task_state_boundary(receipt)
            ):
                continue
            payload_digest = self._receipt_payload_digests.get(receipt.receipt_id)
            if not self.receipt_payload_is_intact(receipt):
                payload_digest = "invalid_payload:" + receipt.receipt_id
            rows.append({
                "receipt_id": receipt.receipt_id,
                "step": receipt.step,
                "kind": receipt.kind,
                "success": receipt.success,
                "state_change": receipt.state_change,
                "failure_class": receipt.failure_class,
                "payload_sha256": payload_digest,
            })
        return _payload_sha256({
            "schema_version": "task_state_snapshot.v1",
            "task_state_generation": self.task_state_generation(),
            "rows": rows,
        })

    def has_current_authoritative_observation(self) -> bool:
        """Return whether current task state has a mechanical observation.

        This replaces activity-based progress for PCR completion. A mutation
        or a recent successful command is not enough; the observation must be
        current, valid, and admitted by a typed inspection/check route.
        """
        for receipt in reversed(self.receipts):
            if not self.receipt_snapshot_binding_is_current(receipt):
                continue
            payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
            if receipt.kind == "inspection_record":
                if (
                    receipt.success is True
                    and
                    payload.get("observation_valid") is True
                    and payload.get("eligible_for_proof") is True
                    and str(payload.get("admissibility", "")).strip()
                    in {"direct_admissible", "verdict_eligible"}
                ):
                    return True
            elif receipt.kind in {
                "check_result", "schema_validation", "job_probe", "service_probe",
            } and receipt.success is True:
                return True
            elif receipt.kind in {
                "pcr_verifier_clause_admission", "proof_evidence_admission",
            } and receipt.success is True:
                return True
        return False

    def record(self, receipt: Receipt) -> None:
        if receipt.receipt_id in self._seen_receipts:
            return
        self._seen_receipts.add(receipt.receipt_id)
        self._receipt_payload_digests[receipt.receipt_id] = _payload_sha256(receipt.payload)
        self.receipts.append(receipt)
        if (
            self._changes_task_state(receipt)
            or self.is_uncertain_task_state_boundary(receipt)
        ):
            self._task_state_generation += 1

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

        for path in payload.get("removed_paths", ()) or ():
            normalized = str(path).strip()
            if not normalized:
                continue
            self._removed_paths.append(normalized)
            self._artifacts.discard(normalized)
            self._mark_obligation(
                f"artifact:{normalized}", "open", receipt.receipt_id,
            )

        integrity_violation = str(payload.get("integrity_violation", "")).strip()
        if integrity_violation:
            self.integrity_violations.append(integrity_violation)
            self._mark_obligation("integrity:clean", "failed", receipt.receipt_id)

        process_id = str(payload.get("process_id", "")).strip()
        if process_id and receipt.kind in {"process_launch", "process_stop"}:
            service_name = str(payload.get("service_name") or payload.get("name") or "").strip()
            process_generation = str(payload.get("process_generation", "")).strip()
            if receipt.kind == "process_stop":
                # A failed stop attempt is not evidence that the registered
                # generation is dead. Preserve the last verified lifecycle
                # state unless the executor confirms teardown success.
                if receipt.success:
                    stopped_service_names: set[str] = set()
                    for existing_id, existing in self.processes.items():
                        if existing_id == process_id or (service_name and existing.get("name") == service_name):
                            existing["live"] = False
                            existing["detail"] = str(payload.get("detail", receipt.summary))
                            existing["stopped_by"] = receipt.receipt_id
                            actual_name = str(existing.get("name", "")).strip()
                            if actual_name:
                                stopped_service_names.add(actual_name)
                    # stop_process receipts retain the caller's target alias in
                    # service_name, which may itself be a process ID. Reopen
                    # obligations for the resolved registered service identity,
                    # not for an alias that has no objective obligation.
                    for stopped_name in stopped_service_names:
                        self._mark_obligation(
                            f"service:{stopped_name}", "open", receipt.receipt_id,
                        )
            else:
                if receipt.kind == "process_launch" and service_name:
                    for existing_id, existing in self.processes.items():
                        if existing_id != process_id and existing.get("name") == service_name:
                            existing["live"] = False
                            existing["superseded_by"] = process_id
                    self._mark_obligation(f"service:{service_name}", "open", receipt.receipt_id)
                self.processes[process_id] = {
                    "process_id": process_id,
                    "name": service_name,
                    "command": str(payload.get("command", "")),
                    "live": bool(payload.get("live", receipt.success)),
                    "detail": str(payload.get("detail", receipt.summary)),
                    "pid": payload.get("pid"),
                    "start_time_ticks": str(payload.get("start_time_ticks", "")),
                    "command_sha256": str(payload.get("command_sha256", "")),
                    "process_generation": process_generation,
                    "stdout_log": str(payload.get("stdout_log", "")),
                    "stderr_log": str(payload.get("stderr_log", "")),
                    "step": receipt.step,
                    "kind": receipt.kind,
                }

        if receipt.kind.startswith("terminal_"):
            session_id = str(payload.get("session_id", "")).strip()
            if session_id:
                if receipt.kind == "terminal_start":
                    self.processes[session_id] = {
                        "process_id": session_id,
                        "session_id": session_id,
                        "session_name": str(payload.get("name", "")),
                        "command": str(payload.get("command", "")),
                        "live": bool(payload.get("live", receipt.success)),
                        "pid": payload.get("pid"),
                        "start_time_ticks": str(payload.get("start_time_ticks", "")),
                        "command_sha256": str(payload.get("command_sha256", "")),
                        "process_generation": str(payload.get("process_generation", "")),
                        "process_group_id": payload.get("process_group_id"),
                        "session_leader_id": payload.get("session_leader_id"),
                        "cursor": int(payload.get("cursor", 0) or 0),
                        "total_bytes": int(payload.get("total_bytes", 0) or 0),
                        "step": receipt.step,
                        "kind": "terminal_session",
                    }
                else:
                    registered = self.processes.get(session_id)
                    if registered is not None and registered.get("kind") == "terminal_session":
                        if "live" in payload:
                            registered["live"] = bool(payload.get("live", False))
                        if "exit_code" in payload:
                            registered["exit_code"] = payload.get("exit_code")
                        if "cursor" in payload:
                            registered["cursor"] = int(payload.get("cursor", 0) or 0)
                        if "total_bytes" in payload:
                            registered["total_bytes"] = int(payload.get("total_bytes", 0) or 0)
                        registered["step"] = receipt.step
                        registered["last_terminal_receipt_id"] = receipt.receipt_id
                        if receipt.kind == "terminal_close":
                            registered["live"] = False

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

        if receipt.kind == "job_probe":
            job_id = str(payload.get("job_id") or payload.get("process_id") or "").strip()
            generation = str(payload.get("process_generation", "")).strip()
            registered = self.processes.get(job_id)
            if (
                registered is not None
                and generation
                and generation == str(registered.get("process_generation", ""))
                and bool(payload.get("process_generation_verified", False))
            ):
                status = str(payload.get("job_status", "unknown")).strip()
                registered["live"] = status == "running"
                registered["status"] = status
                registered["completed"] = bool(payload.get("completed", False))
                registered["exit_code"] = payload.get("exit_code")
                registered["last_job_probe_receipt_id"] = receipt.receipt_id

        if receipt.kind == "service_probe":
            service_name = str(payload.get("service_name", "")).strip()
            probe_process_id = str(payload.get("process_id", "")).strip()
            probe_generation = str(payload.get("process_generation", "")).strip()
            registered = self.processes.get(probe_process_id)
            generation_verified = bool(payload.get("process_generation_verified", False))
            current_generation = (
                registered is not None
                and bool(registered.get("live", False))
                and probe_generation
                and probe_generation == str(registered.get("process_generation", ""))
                and service_name == str(registered.get("name", ""))
            )
            if service_name and bool(payload.get("live", False)) and generation_verified and current_generation:
                self._mark_obligation(f"service:{service_name}", "satisfied", receipt.receipt_id)
            elif service_name:
                self._mark_obligation(f"service:{service_name}", "open", receipt.receipt_id)

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

        self._reconcile_objective()


    @staticmethod
    def _changes_task_state(receipt: Receipt) -> bool:
        """Whether a receipt advances grader-visible task-state generation."""
        if not receipt.state_change:
            return False
        if receipt.kind in {
            "write_file",
            "run_command",
            "bootstrap_acquire",
            "bootstrap",
            "process_launch",
            "process_stop",
            "run_experiment",
            "experiment",
        }:
            return True
        payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        if receipt.kind == "environment_extension":
            # A generic external tool call can mutate task-visible UI/service
            # state without yielding a filesystem delta.  Treat a successful
            # tools_call as a conservative freshness boundary while keeping
            # tools/list observational.  The payload explicitly says mutation
            # semantics are unknown; Aether does not invent a concrete delta.
            return bool(
                receipt.success
                and payload.get("operation") == "tools_call"
                and payload.get("mutation_semantics")
                == "unknown_possible_external_state_change"
            )
        state_delta = payload.get("state_delta")
        if isinstance(state_delta, dict) and any(
            value not in (None, "", (), [], {}) for value in state_delta.values()
        ):
            return True
        return bool(
            tuple(payload.get("modified_paths", ()) or ())
            or tuple(payload.get("created_paths", ()) or ())
            or tuple(payload.get("artifact_paths", ()) or ())
            or tuple(payload.get("removed_paths", ()) or ())
        )

    @staticmethod
    def is_uncertain_task_state_boundary(receipt: Receipt) -> bool:
        """Whether task-state mutation observation was explicitly incomplete.

        This is a freshness boundary only. It does not assert a concrete state
        change and therefore must not become Solver progress by itself.
        """
        payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        state_delta = payload.get("state_delta")
        if not isinstance(state_delta, dict):
            return False
        return str(state_delta.get("mutation_detection_status", "")) in {
            "unavailable", "truncated", "coarse",
        }

    def task_state_generation(self) -> int:
        """Current grader-visible task-state freshness generation."""
        return int(self._task_state_generation)

    def receipt_task_state_generation(self, receipt_id: str) -> int | None:
        """Generation of grader-visible task state observed by one receipt.

        A mutating receipt describes the state after its own effect, so its
        generation is advanced before the receipt is matched. Read-only and
        control receipts inherit the generation current when they were
        recorded. This derivation stays authoritative even for ledgers rebuilt
        from immutable receipts.
        """
        generation = 0
        target = str(receipt_id)
        for receipt in self.receipts:
            if (
                self._changes_task_state(receipt)
                or self.is_uncertain_task_state_boundary(receipt)
            ):
                generation += 1
            if receipt.receipt_id == target:
                return generation
        return None

    def record_accounting(
        self,
        *,
        receipt_id: str,
        step: int,
        counter: str,
        event: str,
        action_id: str = "",
        detail: str = "",
    ) -> Receipt:
        """Append one immutable accounting event and update its exact counter."""
        self._accounting[counter] += 1
        receipt = Receipt(
            receipt_id=receipt_id,
            step=step,
            kind="runtime_accounting",
            success=True,
            summary=detail or f"{counter}: {event}",
            payload={
                "counter": counter,
                "event": event,
                "value": self._accounting[counter],
                "action_id": action_id,
            },
        )
        self.record(receipt)
        return receipt

    def accounting_value(self, counter: str) -> int:
        return int(self._accounting[counter])

    def accounting_snapshot(self) -> dict[str, int]:
        return dict(sorted(self._accounting.items()))

    def _reconcile_objective(self) -> None:
        if self.objective_graph is None:
            return

        for deliverable in self.objective_graph.deliverables:
            if deliverable.path in self._artifacts:
                self._mark_obligation(f"artifact:{deliverable.path}", "satisfied", "reconcile")

        for process in self.processes.values():
            service_name = str(process.get("name", "")).strip()
            generation = str(process.get("process_generation", "")).strip()
            if service_name and generation and bool(process.get("live", False)):
                recent_probe = self.last_verified_probe(service_name, generation)
                if recent_probe is not None:
                    self._mark_obligation(f"service:{service_name}", "satisfied", recent_probe.receipt_id)

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

    def removed_paths(self) -> tuple[str, ...]:
        return tuple(self._removed_paths)

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

    def mark_obligation_satisfied(self, obligation_id: str, evidence_id: str) -> None:
        """Mark one existing obligation from a current admitted proof bridge."""
        self._mark_obligation(str(obligation_id), "satisfied", str(evidence_id))

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
            or (receipt.kind == "job_probe" and receipt.success)
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

    def apply_verifier_result(
        self,
        result: ModelVerifierResult,
        *,
        step: int,
        compiled: CompiledRuntime | None = None,
        packet_signature: str = "",
        extra_payload: Mapping[str, Any] | None = None,
    ) -> None:
        resolved_finding_ids: set[str] = set()
        if result.verdict == "completed":
            from .finding_evidence import resolved_finding_ids_for_completed
            resolved_finding_ids = resolved_finding_ids_for_completed(
                self, result, packet_signature=packet_signature,
            )
        self.findings.apply_result(
            result,
            step=step,
            resolve_stale_by_evidence=False,
            task_state_generation=self.task_state_generation(),
            resolved_finding_ids=resolved_finding_ids,
        )
        # Preserve a model-retrievable factual witness without exposing reviewer
        # repair strategy.  The raw verifier result remains audit authority; this
        # receipt is the explicit Solver-facing evidence bridge.
        for index, finding in enumerate(result.findings):
            witness_id = f"step-{step}:completion_finding_witness:{index}"
            self.record(Receipt(
                receipt_id=witness_id,
                step=step,
                kind="completion_finding_witness",
                success=True,
                summary=str(finding.summary),
                payload={
                    "finding_id": str(finding.finding_id),
                    "claim_status": str(finding.verdict),
                    "source": "independent_review",
                    "semantic_authority": "raw_user_task",
                    "summary": str(finding.summary),
                    "challenged_requirement_claim": str(finding.summary),
                    "challenged_requirement_status": "review_interpretation_against_raw_user_task",
                    "observed_precondition_status": "not_separately_reported_by_reviewer",
                    "observations": [str(item) for item in finding.evidence],
                    "actual_observed_result_status": (
                        "inspection_linked_review_observation"
                        if finding.supporting_inspection_ids
                        else "review_reported_observation_without_explicit_inspection_ref"
                    ),
                    "expected_result_status": "not_separately_task_grounded_by_reviewer",
                    "applies_to": [str(item) for item in finding.applies_to],
                    "observed_task_state_generation": self.task_state_generation(),
                    "supporting_observation_ids": [
                        str(item) for item in finding.supporting_inspection_ids
                    ],
                    "coverage_status": (
                        "explicit_support_refs_present"
                        if finding.supporting_inspection_ids
                        else "no_explicit_support_refs"
                    ),
                    "supporting_observation_count": len(finding.supporting_inspection_ids),
                    "repair_strategy_included": False,
                },
            ))
        verifier_result_receipt_id = f"step-{step}:model_verifier"
        if compiled is not None:
            from .proof_contract import record_verifier_result_evidence
            record_verifier_result_evidence(
                self, result=result, compiled=compiled, step=step,
            )
            if compiled.proof_requirements:
                from .proof_contract import (
                    proof_requirements_identity,
                    record_shadow_proof_evidence_admission,
                )
                contract_identity = (
                    compiled.proof_requirements_identity
                    or proof_requirements_identity(compiled.proof_requirements)
                )
                record_shadow_proof_evidence_admission(
                    self,
                    result=result,
                    requirements=compiled.proof_requirements,
                    step=step,
                    packet_signature=packet_signature,
                    proof_contract_identity=contract_identity,
                    verifier_result_receipt_id=verifier_result_receipt_id,
                )
        result_payload = dict(extra_payload or {})
        # Resolve findings before append so the final context is part of the
        # same payload digest as the result and snapshot/proof bindings.
        result_payload["active_findings_after"] = self.active_finding_context(step + 1)
        self.record_model_verifier_result(
            result,
            receipt_id=verifier_result_receipt_id,
            step=step,
            compiled=compiled,
            packet_signature=packet_signature,
            extra_payload=result_payload,
        )

    def active_finding_context(self, step: int, limit: int = 4) -> list[dict[str, Any]]:
        return self.findings.context(current_step=step, limit=limit)

    def no_progress_streak(self) -> int:
        streak = 0
        ancillary = {
            "runtime_accounting",
            "solver_decision_state",
            "solver_progress_assessment",
            "automatic_memory",
            "automatic_memory_advisory",
        }
        for receipt in reversed(self.receipts):
            if receipt.kind in ancillary:
                continue
            if (
                receipt.state_change
                or (receipt.kind == "check_result" and receipt.success)
                or (receipt.kind == "schema_validation" and receipt.success)
                or (receipt.kind == "job_probe" and receipt.success)
            ):
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

    def last_verified_probe(self, service_name: str, process_generation: str) -> Receipt | None:
        for receipt in reversed(self.receipts):
            if receipt.kind != "service_probe" or not receipt.success:
                continue
            payload = receipt.payload
            if str(payload.get("service_name", "")).strip() != service_name:
                continue
            if str(payload.get("process_generation", "")).strip() != process_generation:
                continue
            if not bool(payload.get("process_generation_verified", False)):
                continue
            return receipt
        return None

    def last_probe_step(self, service_name: str) -> int | None:
        current = [
            item for item in self.processes.values()
            if item.get("name") == service_name and item.get("live")
        ]
        if not current:
            return None
        generation = str(current[-1].get("process_generation", ""))
        receipt = self.last_verified_probe(service_name, generation)
        return receipt.step if receipt is not None else None

    def latest_receipt(self, kind: str) -> Receipt | None:
        for receipt in reversed(self.receipts):
            if receipt.kind == kind:
                return receipt
        return None

    def all_receipts(self) -> tuple[Receipt, ...]:
        return tuple(self.receipts)

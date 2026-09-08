"""Trusted verifier recovery and semantic evidence gates.

This module is deliberately small and canonical: it operates on the existing
``ModelVerifierResult``/``VerifierInspectionRequest`` protocol and does not
implement a second runtime.  The kernel owns route execution; this module
only supplies deterministic ownership, retry, and evidence decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping

from .verifier import ModelVerifierResult, SOLVER_REPAIR_VERDICTS


class VerifierRecoveryAction(str, Enum):
    RETRY_VERIFIER = "retry_verifier"
    REVIEW_UNAVAILABLE = "review_unavailable"
    TERMINAL_INFRASTRUCTURE = "terminal_infrastructure"
    RETURN_TO_SOLVER = "return_to_solver"
    TERMINATE_SUCCESS = "terminate_success"


class EvidenceClass(str, Enum):
    """Ordered evidence strengths used by compiled semantic gates."""

    SHAPE = "shape"
    METADATA_PROXY = "metadata_proxy"
    SOLVER_AUTHORED_TEST = "solver_authored_test"
    SAME_METHOD = "same_method"
    BEHAVIORAL = "behavioral"
    EXACT_CONTRACT = "exact_contract"
    INDEPENDENT_SEMANTIC = "independent_semantic"


_EVIDENCE_RANK = {item: index for index, item in enumerate(EvidenceClass)}


@dataclass(frozen=True)
class CompiledEvidenceRequirement:
    clause_id: str
    minimum_class: EvidenceClass
    allowed_route_kinds: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class RouteAttempt:
    route: str
    success: bool
    inspection_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class RecoveryResult:
    attempts: tuple[RouteAttempt, ...]
    action: VerifierRecoveryAction


def execute_primary_then_fallback(
    *,
    primary_route: str,
    fallback_route: str | None,
    executor: Callable[[str], Any],
    inspection_id_factory: Callable[[str], str] | None = None,
) -> tuple[RouteAttempt, ...]:
    """Execute exactly one compiled fallback after a primary failure.

    A failed primary is never converted into Solver feedback.  The returned
    attempts are receipts for the Verifier lane and the caller decides whether
    a packet retry is still available.
    """
    if not str(primary_route).strip():
        raise ValueError("primary verifier route must be non-empty")
    attempts: list[RouteAttempt] = []
    routes = [str(primary_route)]
    if fallback_route and str(fallback_route).strip() and str(fallback_route) != str(primary_route):
        routes.append(str(fallback_route))
    for route in routes:
        inspection_id = inspection_id_factory(route) if inspection_id_factory else ""
        try:
            result = executor(route)
        except Exception as exc:  # route failure stays verifier-owned
            attempts.append(RouteAttempt(route, False, inspection_id, f"{type(exc).__name__}: {exc}"))
            continue
        # ``None`` is the historical executor success sentinel, so only an
        # explicit false status denotes a failed route.  Do not report
        # fallback success when a boolean executor rejects the route.
        if result is False:
            attempts.append(RouteAttempt(route, False, inspection_id, "route returned failure status"))
            continue
        attempts.append(RouteAttempt(route, True, inspection_id))
        break
    return tuple(attempts)


@dataclass
class VerifierRecoveryRouter:
    """Bounded routing keyed by candidate generation and infrastructure incident.

    Packet signatures include claim/evidence presentation and therefore may change
    without any material repair to the candidate or failed review backend.  Retry
    custody must survive that presentation churn.
    """

    max_packet_retries: int = 1
    _retry_counts: dict[tuple[str, str, str], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_packet_retries < 0:
            raise ValueError("max_packet_retries must be non-negative")

    def route(
        self,
        result: ModelVerifierResult,
        *,
        packet_signature: str,
        blocker_owner: str = "",
        blocker_verified: bool = False,
        incident_key: str = "",
        candidate_generation: int | str | None = None,
        integrity_destroying: bool = False,
    ) -> VerifierRecoveryAction:
        """Return the only legal next owner for a verifier outcome.

        ``needs_repair`` is the sole outcome that can return to Solver. Tool,
        protocol, provider, and harness failures remain outside Solver.
        """
        verdict = str(result.verdict)
        if verdict == "completed":
            return VerifierRecoveryAction.TERMINATE_SUCCESS
        if verdict in SOLVER_REPAIR_VERDICTS:
            return VerifierRecoveryAction.RETURN_TO_SOLVER
        owner = blocker_owner.strip() or (
            "verifier_tooling" if verdict in {"blocked_by_tooling", "reviewer_tool_execution_failed", "reviewer_capability_missing"}
            else "harness_config" if verdict == "blocked_by_harness_config" else "protocol"
        )
        incident = str(incident_key or verdict or "review_infrastructure").strip()
        generation = "run" if candidate_generation is None else str(candidate_generation)
        key = (generation, owner, incident)
        used = self._retry_counts.get(key, 0)
        if used < self.max_packet_retries:
            self._retry_counts[key] = used + 1
            return VerifierRecoveryAction.RETRY_VERIFIER
        if integrity_destroying:
            return VerifierRecoveryAction.TERMINAL_INFRASTRUCTURE
        return VerifierRecoveryAction.REVIEW_UNAVAILABLE


def validate_compiled_evidence(
    evidence: Iterable[Any],
    *,
    requirements: Iterable[CompiledEvidenceRequirement],
    known_inspection_ids: Iterable[str],
    inspection_ceilings: Mapping[str, EvidenceClass | str] | None = None,
    inspection_routes: Mapping[str, str] | None = None,
    inspection_task_state_generations: Mapping[str, int | str] | None = None,
    current_task_state_generation: int | None = None,
    inspection_snapshot_digests: Mapping[str, str] | None = None,
    current_snapshot_digest: str | None = None,
    known_clause_ids: Iterable[str] = (),
) -> tuple[EvidenceValidationError, ...]:
    """Validate completed evidence against compiled clause thresholds.

    The gate is content-blind about the observation text, but it is strict on
    provenance, clause coverage, evidence class, and tool ceilings.  Shape,
    metadata proxies, and solver-authored self-tests cannot satisfy stronger
    semantic clauses merely by being present.
    """
    known = {str(item).strip() for item in known_inspection_ids if str(item).strip()}
    ceilings = dict(inspection_ceilings or {})
    routes = {str(key): str(value) for key, value in dict(inspection_routes or {}).items()}
    generations = dict(inspection_task_state_generations or {})
    snapshots = {str(key): str(value) for key, value in dict(inspection_snapshot_digests or {}).items()}
    requirement_rows = tuple(requirements)
    compiled_clause_ids = {
        str(item.clause_id).strip()
        for item in requirement_rows
        if str(item.clause_id).strip()
    }
    recognized_clause_ids = compiled_clause_ids | {
        str(item).strip() for item in known_clause_ids if str(item).strip()
    }
    errors: list[EvidenceValidationError] = []
    by_clause: dict[str, list[tuple[EvidenceClass, Any, tuple[str, ...]]]] = {}
    for index, item in enumerate(evidence):
        refs = tuple(str(ref).strip() for ref in (getattr(item, "inspection_refs", ()) or ()) if str(ref).strip())
        clause_ids = tuple(str(value).strip() for value in (getattr(item, "clause_ids", ()) or ()) if str(value).strip())
        evidence_class_raw = str(getattr(item, "evidence_class", "") or "").strip()
        if not refs:
            errors.append(EvidenceValidationError("missing_inspection_id", f"evidence[{index}] requires inspection_refs"))
        unknown = sorted(set(refs) - known)
        if unknown:
            errors.append(EvidenceValidationError("unknown_inspection_id", f"evidence[{index}] cites unknown inspection IDs: {unknown}"))
        if not str(getattr(item, "falsification_check", "") or "").strip():
            errors.append(EvidenceValidationError("missing_falsification", f"evidence[{index}] requires falsification_check"))
        try:
            claimed = EvidenceClass(evidence_class_raw)
        except ValueError:
            errors.append(EvidenceValidationError("unknown_evidence_class", f"evidence[{index}] has unknown class: {evidence_class_raw}"))
            continue
        resolved_ceilings: dict[str, EvidenceClass] = {}
        for ref in refs:
            ceiling_raw = ceilings.get(ref)
            if ceiling_raw is None or not str(ceiling_raw).strip():
                errors.append(EvidenceValidationError(
                    "missing_inspection_ceiling",
                    f"inspection {ref} has no registered evidence ceiling",
                ))
                continue
            try:
                ceiling = ceiling_raw if isinstance(ceiling_raw, EvidenceClass) else EvidenceClass(str(ceiling_raw))
            except ValueError:
                errors.append(EvidenceValidationError("unknown_ceiling", f"inspection {ref} has unknown evidence ceiling: {ceiling_raw}"))
                continue
            resolved_ceilings[ref] = ceiling

        if current_task_state_generation is not None:
            if not generations:
                errors.append(EvidenceValidationError(
                    "missing_inspection_generation",
                    f"evidence[{index}] has no inspection-generation provenance map",
                ))
            else:
                stale_refs = []
                for ref in refs:
                    try:
                        generation = int(generations.get(ref, -1))
                    except (TypeError, ValueError):
                        generation = -1
                    if ref not in generations or generation != int(current_task_state_generation):
                        stale_refs.append(ref)
                if stale_refs:
                    errors.append(EvidenceValidationError(
                        "stale_inspection",
                        f"evidence[{index}] cites inspections outside current task-state generation: {stale_refs}",
                    ))
        if current_snapshot_digest is not None and str(current_snapshot_digest).strip():
            if not snapshots:
                errors.append(EvidenceValidationError(
                    "missing_inspection_snapshot",
                    f"evidence[{index}] has no inspection-snapshot provenance map",
                ))
            else:
                stale_snapshot_refs = [
                    ref for ref in refs
                    if ref not in snapshots
                    or snapshots.get(ref, "") != str(current_snapshot_digest)
                ]
                if stale_snapshot_refs:
                    errors.append(EvidenceValidationError(
                        "stale_snapshot",
                        f"evidence[{index}] cites inspections from a different observation snapshot: {stale_snapshot_refs}",
                    ))

        # A composite entry may combine supporting observations, but its
        # claimed class must be earned by a reference on an allowed route. Do
        # not select the route from one ref and the strength from another: that
        # would let weak-allowed + strong-disallowed references launder proof.
        # The requirement route is applied below, once clause IDs are known.
        # Here we only validate an unconstrained composite against all refs.
        if resolved_ceilings:
            strongest_ceiling = max(resolved_ceilings.values(), key=lambda value: _EVIDENCE_RANK[value])
            if _EVIDENCE_RANK[claimed] > _EVIDENCE_RANK[strongest_ceiling]:
                errors.append(EvidenceValidationError(
                    "evidence_ceiling_exceeded",
                    f"evidence class {claimed.value} exceeds strongest cited inspection ceiling {strongest_ceiling.value}",
                ))
        for clause_id in clause_ids:
            if recognized_clause_ids and clause_id not in recognized_clause_ids:
                errors.append(EvidenceValidationError(
                    "unknown_clause_id",
                    f"evidence[{index}] cites unknown clause ID: {clause_id}",
                ))
            by_clause.setdefault(clause_id, []).append((claimed, item, refs))
    for requirement in requirement_rows:
        candidates = by_clause.get(requirement.clause_id, ())
        if not candidates:
            errors.append(EvidenceValidationError("missing_clause_evidence", f"completed lacks evidence for clause {requirement.clause_id}"))
            continue
        allowed = set(requirement.allowed_route_kinds)
        def _ceiling_rank(ref: str) -> int:
            raw = ceilings.get(ref)
            try:
                value = raw if isinstance(raw, EvidenceClass) else EvidenceClass(str(raw))
            except ValueError:
                return -1
            return _EVIDENCE_RANK.get(value, -1)

        routed_candidates: list[tuple[EvidenceClass, Any, tuple[str, ...], tuple[str, ...]]] = []
        for claimed, item, refs in candidates:
            route_refs = tuple(
                ref for ref in refs
                if not allowed or routes.get(ref, "") in allowed
            )
            if route_refs:
                routed_candidates.append((claimed, item, refs, route_refs))
        if allowed and not routed_candidates:
            errors.append(EvidenceValidationError(
                "wrong_evidence_route",
                f"clause {requirement.clause_id} requires inspection route(s) {sorted(allowed)}",
            ))
            continue
        strongest = max(
            min(
                _EVIDENCE_RANK[claimed],
                max((_ceiling_rank(ref) for ref in route_refs), default=-1),
            )
            for claimed, _item, _refs, route_refs in routed_candidates
        )
        if strongest < _EVIDENCE_RANK[requirement.minimum_class]:
            errors.append(EvidenceValidationError("weak_evidence", f"clause {requirement.clause_id} requires {requirement.minimum_class.value}; weaker/proxy evidence supplied"))
    return tuple(errors)


def findings_for_solver_context(result: ModelVerifierResult) -> list[dict[str, Any]]:
    """Project only conclusive Solver-state findings into the next context."""
    if result.verdict == "completed":
        return []
    if result.verdict not in SOLVER_REPAIR_VERDICTS:
        return []
    return [
        {
            "finding_id": finding.finding_id,
            "summary": finding.summary,
            "evidence": list(finding.evidence),
            "repair_instruction": finding.repair_instruction,
            "applies_to": list(finding.applies_to),
        }
        for finding in result.findings
    ]

"""Minimal typed work-and-proof contract for certified completion.

This module does not decide arbitrary task semantics. It certifies whether an
Architect-declared evidence route can reach the required evidential strength,
and whether current receipted evidence satisfies each critical clause.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import posixpath
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from .ledger import ExecutionLedger, Receipt


EVIDENCE_STRENGTH: dict[str, int] = {
    "model_claim": 0,
    "shape": 1,
    "metadata_proxy": 2,
    "solver_authored_test": 3,
    "same_method": 3,
    "behavioral": 4,
    "exact_contract": 5,
    "independent_semantic": 6,
    "official_grader": 7,
}

# Maximum evidence class that a route can establish. The route still has to
# execute successfully and produce content supporting the clause. In
# particular, process/port liveness can never establish protocol semantics.
ROUTE_EVIDENCE_CEILINGS: dict[str, str] = {
    "read_file": "exact_contract",
    "read_cited_receipt": "exact_contract",
    "read_output": "behavioral",
    "compare_initial_path": "exact_contract",
    "inspect_artifact": "exact_contract",
    "rerun_check": "exact_contract",
    "overlay_run_command": "exact_contract",
    "probe_port": "metadata_proxy",
    "probe_process": "metadata_proxy",
    "probe_job": "exact_contract",
    "probe_http": "behavioral",
    "perceive_artifact": "independent_semantic",
    "inspect_recent_receipts": "metadata_proxy",
    "inspect_action_receipts": "exact_contract",
    "inspect_artifact_history": "metadata_proxy",
}

INDEPENDENT_ROUTE_KINDS = frozenset({
    "read_file",
    "compare_initial_path",
    "inspect_artifact",
    "rerun_check",
    "overlay_run_command",
    "probe_port",
    "probe_process",
    "probe_http",
    "perceive_artifact",
})

INDEPENDENT_PROVENANCE = frozenset({
    "direct_current_state",
    "independent_interface_probe",
    "task_provided_check",
    "verifier_inspection",
    "official_grader",
})


# Architect proof kinds are a small semantic vocabulary.  The admission
# registry below is kernel-owned; the Architect contract only exposes the
# enum and never receives route-selection or current-runtime compatibility
# data.
PROOF_KINDS = (
    "exact_state",
    "public_behavior",
    "independent_comparison",
    "direct_perception",
)


@dataclass(frozen=True)
class ProofKindAdmissionSpec:
    proof_kind: str
    minimum_evidence_class: str
    verifier_origin_required: bool
    independent_derivation_required: bool
    direct_perception_required: bool
    eligible_route_kinds: frozenset[str]


PROOF_KIND_REGISTRY: Mapping[str, ProofKindAdmissionSpec] = MappingProxyType({
    "exact_state": ProofKindAdmissionSpec(
        proof_kind="exact_state",
        minimum_evidence_class="exact_contract",
        verifier_origin_required=True,
        independent_derivation_required=False,
        direct_perception_required=False,
        eligible_route_kinds=frozenset({"read_file", "inspect_artifact", "rerun_check", "overlay_run_command", "inspect_action_receipts", "probe_job"}),
    ),
    "public_behavior": ProofKindAdmissionSpec(
        proof_kind="public_behavior",
        minimum_evidence_class="behavioral",
        verifier_origin_required=True,
        independent_derivation_required=False,
        direct_perception_required=False,
        eligible_route_kinds=frozenset({"probe_http", "overlay_run_command"}),
    ),
    "independent_comparison": ProofKindAdmissionSpec(
        proof_kind="independent_comparison",
        minimum_evidence_class="exact_contract",
        verifier_origin_required=True,
        independent_derivation_required=True,
        direct_perception_required=False,
        eligible_route_kinds=frozenset({"overlay_run_command", "compare_initial_path"}),
    ),
    "direct_perception": ProofKindAdmissionSpec(
        proof_kind="direct_perception",
        minimum_evidence_class="independent_semantic",
        verifier_origin_required=True,
        independent_derivation_required=False,
        direct_perception_required=True,
        eligible_route_kinds=frozenset({"perceive_artifact"}),
    ),
})

# The registry is kernel-owned compatibility data.  A proof receipt is only
# comparable with requirements compiled against the same version and digest;
# this prevents a later registry edit from silently reinterpreting old
# evidence.  The digest is deliberately derived from the typed registry, not
# from model-authored prose.
PROOF_REGISTRY_VERSION = "aether-proof-registry.v5"


def _proof_registry_payload() -> list[dict[str, Any]]:
    return [
        {
            "proof_kind": kind,
            "minimum_evidence_class": spec.minimum_evidence_class,
            "verifier_origin_required": spec.verifier_origin_required,
            "independent_derivation_required": spec.independent_derivation_required,
            "direct_perception_required": spec.direct_perception_required,
            "eligible_route_kinds": sorted(spec.eligible_route_kinds),
        }
        for kind, spec in sorted(PROOF_KIND_REGISTRY.items())
    ]


PROOF_REGISTRY_DIGEST = hashlib.sha256(
    json.dumps(_proof_registry_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


# Compatibility telemetry only.  This is not part of the Architect schema and
# does not select a route.  It records which existing V1 surfaces can carry a
# kind today, including known expressiveness gaps.
CURRENT_PROOF_ROUTE_COMPATIBILITY: dict[str, Mapping[str, Any]] = {
    "exact_state": {
        "route_kinds": ("read_file", "inspect_artifact", "rerun_check", "overlay_run_command", "inspect_action_receipts", "probe_job"),
        "current_proof_obligation": "exact_state",
    },
    "public_behavior": {
        "route_kinds": ("read_output", "probe_http", "overlay_run_command"),
        "current_proof_obligation": "public_behavior",
    },
    "independent_comparison": {
        "route_kinds": ("compare_initial_path", "overlay_run_command"),
        "current_proof_obligation": "independent_comparison",
    },
    "direct_perception": {
        "route_kinds": ("perceive_artifact",),
        "current_proof_obligation": None,
    },
}


@dataclass(frozen=True)
class CompiledProofRequirement:
    """Route-independent proof requirement carried by the existing runtime."""

    proof_id: str
    obligation_ids: tuple[str, ...]
    risk_ids: tuple[str, ...]
    proof_kind: str
    acceptance_observation: str
    falsification_observation: str
    minimum_evidence_class: str
    verifier_origin_required: bool
    independent_derivation_required: bool
    direct_perception_required: bool
    target_type: str = "outcome"
    target_id: str = ""
    registry_version: str = PROOF_REGISTRY_VERSION
    registry_digest: str = PROOF_REGISTRY_DIGEST
    insufficient_proxies: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "proof_id": self.proof_id,
            "obligation_ids": list(self.obligation_ids),
            "risk_ids": list(self.risk_ids),
            "proof_kind": self.proof_kind,
            "acceptance_observation": self.acceptance_observation,
            "falsification_observation": self.falsification_observation,
            "minimum_evidence_class": self.minimum_evidence_class,
            "verifier_origin_required": self.verifier_origin_required,
            "independent_derivation_required": self.independent_derivation_required,
            "direct_perception_required": self.direct_perception_required,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "registry_version": self.registry_version,
            "registry_digest": self.registry_digest,
        }
        if self.insufficient_proxies:
            payload["insufficient_proxies"] = list(self.insufficient_proxies)
        return payload


def proof_requirements_identity(
    requirements: Sequence[CompiledProofRequirement],
) -> str:
    """Return the stable identity of the current compiled proof contract."""
    payload = [requirement.as_dict() for requirement in requirements]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def proof_kind_admission(proof_kind: str) -> ProofKindAdmissionSpec:
    try:
        return PROOF_KIND_REGISTRY[proof_kind]
    except KeyError:
        expected = ", ".join(PROOF_KINDS)
        raise ValueError(f"unknown proof kind {proof_kind!r}; expected one of: {expected}") from None


_PROOF_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


def _proof_identifier(value: Any, location: str) -> str:
    text = str(value or "").strip()
    if not _PROOF_ID_PATTERN.fullmatch(text):
        raise ValueError(f"{location} is not a valid proof identifier")
    return text


def _proof_text(value: Any, location: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{location} must be a non-empty string")
    return text


def compile_proof_requirements(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[CompiledProofRequirement, ...]:
    """Compile typed Architect proof intent without selecting inspection routes."""
    compiled: list[CompiledProofRequirement] = []
    proof_ids: set[str] = set()
    for index, row in enumerate(rows):
        location = f"proof_intent[{index}]"
        proof_id = _proof_identifier(row.get("proof_id"), f"{location}.proof_id")
        if proof_id in proof_ids:
            raise ValueError(f"duplicate proof id: {proof_id}")
        proof_ids.add(proof_id)
        raw_obligations = row.get("obligation_refs", ())
        if not isinstance(raw_obligations, (list, tuple)) or not raw_obligations:
            raise ValueError(f"{location}.obligation_refs must be a non-empty array")
        refs = tuple(
            _proof_identifier(item, f"{location}.obligation_refs[{ref_index}]")
            for ref_index, item in enumerate(raw_obligations)
        )
        if len(set(refs)) != len(refs):
            raise ValueError(f"{location}.obligation_refs must be unique")
        raw_risks = row.get("risk_refs", ())
        if raw_risks is None:
            raw_risks = ()
        if not isinstance(raw_risks, (list, tuple)):
            raise ValueError(f"{location}.risk_refs must be an array")
        risk_ids = tuple(
            _proof_identifier(item, f"{location}.risk_refs[{ref_index}]")
            for ref_index, item in enumerate(raw_risks)
        )
        if len(set(risk_ids)) != len(risk_ids):
            raise ValueError(f"{location}.risk_refs must be unique")
        raw_proxies = row.get(
            "insufficient_proxies",
            row.get("insufficient_proxy_evidence", ()),
        )
        if raw_proxies is None:
            raw_proxies = ()
        if not isinstance(raw_proxies, (list, tuple)):
            raise ValueError(f"{location}.insufficient_proxies must be an array")
        insufficient_proxies = tuple(
            _proof_text(
                item,
                f"{location}.insufficient_proxies[{proxy_index}]",
            )
            for proxy_index, item in enumerate(raw_proxies)
        )
        if len(set(insufficient_proxies)) != len(insufficient_proxies):
            raise ValueError(f"{location}.insufficient_proxies must be unique")
        # The same semantic obligation may require multiple typed proof facets.
        # Admission evaluates every compiled requirement and only closes obligations
        # after the full proof contract is admitted.
        proof_kind = str(row.get("proof_kind", "")).strip()
        spec = proof_kind_admission(proof_kind)
        target_type = str(row.get("target_type", "outcome")).strip() or "outcome"
        target_id = str(row.get("target_id", "")).strip()
        if target_type not in {"outcome", "constraint"}:
            raise ValueError(f"{location}.target_type must be outcome or constraint")
        if target_type == "constraint" and not target_id:
            raise ValueError(f"{location}.target_id is required for constraint proof")
        compiled.append(CompiledProofRequirement(
            proof_id=proof_id,
            obligation_ids=refs,
            risk_ids=risk_ids,
            proof_kind=proof_kind,
            acceptance_observation=_proof_text(row.get("acceptance_observation"), f"{location}.acceptance_observation"),
            falsification_observation=_proof_text(row.get("falsification_observation"), f"{location}.falsification_observation"),
            minimum_evidence_class=spec.minimum_evidence_class,
            verifier_origin_required=spec.verifier_origin_required,
            independent_derivation_required=spec.independent_derivation_required,
            direct_perception_required=spec.direct_perception_required,
            target_type=target_type,
            target_id=target_id,
            insufficient_proxies=insufficient_proxies,
        ))
    return tuple(compiled)


PROOF_READ_ONLY_ROUTE_KINDS = frozenset({
    "read_file",
    "read_output",
    "compare_initial_path",
    "inspect_artifact",
    "rerun_check",
    "overlay_run_command",
    "probe_http",
    "probe_job",
    "perceive_artifact",
    "inspect_action_receipts",
})
VERIFIER_ORIGIN_REQUESTERS = frozenset({"model_verifier", "kernel_verifier"})


@dataclass(frozen=True)
class ProofEvidenceAdmissionDecision:
    proof_id: str
    admitted: bool
    code: str
    detail: str
    evidence_receipt_ids: tuple[str, ...] = ()


def _bound_proof_ids(payload: Mapping[str, Any]) -> set[str]:
    route_parameters = payload.get("route_parameters", {})
    raw = route_parameters.get("proof_ids", ()) if isinstance(route_parameters, Mapping) else ()
    if isinstance(raw, str):
        raw = (raw,)
    if not isinstance(raw, (list, tuple, set, frozenset)):
        raw = ()
    direct = payload.get("proof_id", "")
    values = set(str(item).strip() for item in raw if str(item).strip())
    if str(direct).strip():
        values.add(str(direct).strip())
    return values


def evaluate_compiled_proof_requirements(
    requirements: Sequence[CompiledProofRequirement],
    ledger: ExecutionLedger,
    selected_inspection_refs: Mapping[str, Sequence[str]],
    *,
    packet_signature: str = "",
    proof_contract_identity: str = "",
) -> tuple[ProofEvidenceAdmissionDecision, ...]:
    """Admit Verifier-selected receipts against route-independent requirements.

    This function validates a concrete action and receipt chosen by the
    Verifier.  It never chooses a route or interprets acceptance/falsification
    prose.  Existing V1 clause evaluation is untouched and remains the path
    used when ``requirements`` is empty.
    """
    from .inspection_registry import (
        inspection_records_by_id,
        inspection_superseded_by_later_observation,
    )

    registry = inspection_records_by_id(ledger)
    current_generation = int(ledger.task_state_generation())
    decisions: list[ProofEvidenceAdmissionDecision] = []
    computed_identity = proof_requirements_identity(requirements)
    for requirement in requirements:
        admission = proof_kind_admission(requirement.proof_kind)
        if (
            requirement.registry_version != PROOF_REGISTRY_VERSION
            or requirement.registry_digest != PROOF_REGISTRY_DIGEST
        ):
            decisions.append(ProofEvidenceAdmissionDecision(
                requirement.proof_id, False, "proof_registry_mismatch",
                "proof requirement was compiled against a different kernel proof registry",
            ))
            continue
        if proof_contract_identity and proof_contract_identity != computed_identity:
            decisions.append(ProofEvidenceAdmissionDecision(
                requirement.proof_id, False, "proof_contract_identity_mismatch",
                "selected proof evidence does not match the current compiled proof contract",
            ))
            continue
        raw_refs = selected_inspection_refs.get(requirement.proof_id, ())
        if isinstance(raw_refs, str):
            raw_refs = (raw_refs,)
        refs = tuple(str(item).strip() for item in raw_refs if str(item).strip())
        if not refs:
            decisions.append(ProofEvidenceAdmissionDecision(
                requirement.proof_id, False, "missing_verifier_inspection",
                "no Verifier-selected inspection was supplied",
            ))
            continue
        stale: list[str] = []
        unregistered: list[str] = []
        rejected: list[str] = []
        accepted: list[str] = []
        for inspection_id in refs:
            receipt = registry.get(inspection_id)
            if receipt is None:
                unregistered.append(inspection_id)
                continue
            payload = receipt.payload
            if not receipt.success:
                rejected.append(inspection_id)
                continue
            if inspection_superseded_by_later_observation(ledger, receipt):
                rejected.append(inspection_id)
                continue
            if packet_signature and str(payload.get("packet_signature", "")) != packet_signature:
                stale.append(inspection_id)
                continue
            if proof_contract_identity and str(payload.get("proof_contract_identity", "")) != proof_contract_identity:
                rejected.append(inspection_id)
                continue
            route_kind = str(payload.get("route_kind", "")).strip()
            if route_kind not in PROOF_READ_ONLY_ROUTE_KINDS:
                rejected.append(inspection_id)
                continue
            if route_kind not in admission.eligible_route_kinds:
                rejected.append(inspection_id)
                continue
            action_history_binding = False
            if route_kind == "probe_job" and not bool(payload.get("lifecycle_binding_verified", False)):
                rejected.append(inspection_id)
                continue
            if route_kind == "inspect_action_receipts":
                route_parameters = payload.get("route_parameters", {})
                clause_ids = {
                    str(item).strip()
                    for item in (
                        route_parameters.get("clause_ids", ())
                        if isinstance(route_parameters, Mapping) else ()
                    )
                    if str(item).strip()
                }
                if requirement.target_type == "constraint":
                    action_history_binding = requirement.target_id in clause_ids
                    if not action_history_binding:
                        rejected.append(inspection_id)
                        continue
                else:
                    action_history_binding = bool(
                        tuple(payload.get("action_contract_guarantees", ()) or ())
                    )
                    if not action_history_binding:
                        rejected.append(inspection_id)
                        continue
            if requirement.verifier_origin_required and str(payload.get("requester", "")).strip() not in VERIFIER_ORIGIN_REQUESTERS:
                rejected.append(inspection_id)
                continue
            if (
                requirement.proof_id not in _bound_proof_ids(payload)
                and not action_history_binding
            ):
                rejected.append(inspection_id)
                continue
            if route_kind == "overlay_run_command" and str(payload.get("execution_scope", "")).strip() != "verifier_overlay":
                rejected.append(inspection_id)
                continue
            try:
                generation = int(payload.get("task_state_generation", -1))
            except (TypeError, ValueError):
                generation = -1
            if generation != current_generation:
                stale.append(inspection_id)
                continue
            admissibility = str(payload.get("admissibility", "")).strip()
            if admissibility not in {"direct_admissible", "verdict_eligible"}:
                rejected.append(inspection_id)
                continue
            if requirement.independent_derivation_required and admissibility != "verdict_eligible":
                rejected.append(inspection_id)
                continue
            if requirement.direct_perception_required and route_kind != "perceive_artifact":
                rejected.append(inspection_id)
                continue
            actual_class = str(payload.get("actual_evidence_class", "")).strip()
            if _strength(actual_class) < _strength(requirement.minimum_evidence_class):
                rejected.append(inspection_id)
                continue
            accepted.append(inspection_id)
        if accepted:
            decisions.append(ProofEvidenceAdmissionDecision(
                requirement.proof_id, True, "proof_evidence_admitted",
                "a current Verifier-origin receipt met the typed mechanical evidence-admission requirements",
                tuple(accepted),
            ))
        elif stale and not rejected and not unregistered:
            decisions.append(ProofEvidenceAdmissionDecision(
                requirement.proof_id, False, "stale_proof_evidence",
                f"selected inspection(s) are not at current task generation {current_generation}",
                tuple(stale),
            ))
        elif unregistered:
            decisions.append(ProofEvidenceAdmissionDecision(
                requirement.proof_id, False, "unregistered_inspection",
                "selected inspection ID is not present in the immutable registry",
                tuple(unregistered),
            ))
        else:
            decisions.append(ProofEvidenceAdmissionDecision(
                requirement.proof_id, False, "proof_evidence_not_admitted",
                "selected receipts failed route, origin, binding, freshness, admissibility, or evidence checks",
                tuple(rejected or stale),
            ))
    return tuple(decisions)


@dataclass(frozen=True)
class ShadowProofEvidenceAdmission:
    admitted: bool
    decisions: tuple[ProofEvidenceAdmissionDecision, ...] = ()
    problems: tuple[str, ...] = ()


def evaluate_shadow_proof_evidence_admission(
    result: Any,
    requirements: Sequence[CompiledProofRequirement],
    ledger: ExecutionLedger,
    *,
    packet_signature: str,
    proof_contract_identity: str,
) -> ShadowProofEvidenceAdmission:
    """Validate the current typed completion bridge without judging semantic text.

    ``observed`` and ``falsification_check`` remain model-authored claims.
    This function only checks exact proof-ID coverage, current inspection
    references, round identity, registry identity, and typed route admission.
    """
    from .inspection_registry import inspection_records_by_id

    if not requirements:
        return ShadowProofEvidenceAdmission(True)
    entries = tuple(getattr(result, "completion_evidence", ()) or ())
    known = {requirement.proof_id for requirement in requirements}
    refs_by_proof: dict[str, tuple[str, ...]] = {}
    problems: list[str] = []
    if str(getattr(result, "verdict", "")).strip() != "completed":
        problems.append("proof evidence admission requires a completed Verifier verdict")
    for index, entry in enumerate(entries):
        proof_ids = tuple(str(item).strip() for item in getattr(entry, "proof_ids", ()) if str(item).strip())
        if not proof_ids:
            problems.append(f"completion_evidence[{index}].proof_ids is empty")
            continue
        if len(set(proof_ids)) != len(proof_ids):
            problems.append(f"completion_evidence[{index}].proof_ids contains duplicates")
        if not getattr(entry, "inspection_refs", ()):
            problems.append(f"completion_evidence[{index}].inspection_refs is empty for proof evidence")
        if not str(getattr(entry, "observed", "")).strip() or not str(getattr(entry, "falsification_check", "")).strip():
            problems.append(f"completion_evidence[{index}] has empty model-authored proof text")
        for proof_id in proof_ids:
            if proof_id not in known:
                problems.append(f"unknown proof_id: {proof_id}")
                continue
            if proof_id in refs_by_proof:
                problems.append(f"proof_id appears more than once: {proof_id}")
                continue
            refs_by_proof[proof_id] = tuple(
                str(item).strip() for item in getattr(entry, "inspection_refs", ()) if str(item).strip()
            )
    missing = sorted(known - set(refs_by_proof))
    if missing:
        problems.append("missing proof_ids: " + ", ".join(missing))
    # Independent comparison has a second mechanical provenance seam: the
    # model-authored method-validity record must point at the same current
    # derived execution and at current source receipts.  The kernel does not
    # evaluate the prose fields.
    validity = getattr(result, "method_validity", None)
    if any(requirement.independent_derivation_required for requirement in requirements):
        if validity is None:
            problems.append("independent comparison requires method_validity")
        else:
            execution_ref = str(getattr(validity, "execution_ref", "")).strip()
            source_refs = tuple(
                str(item).strip()
                for item in getattr(validity, "authoritative_source_refs", ())
                if str(item).strip()
            )
            comparison_ids = {
                requirement.proof_id
                for requirement in requirements
                if requirement.independent_derivation_required
            }
            if execution_ref not in {
                ref for proof_id in comparison_ids for ref in refs_by_proof.get(proof_id, ())
            }:
                problems.append("method_validity.execution_ref is not the current proof-linked derived execution")
            records = inspection_records_by_id(ledger)
            for source_ref in source_refs:
                if source_ref == "task:prompt":
                    continue
                receipt = records.get(source_ref)
                if receipt is None:
                    problems.append(f"method_validity source ref is not a registered inspection: {source_ref}")
                    continue
                if packet_signature and str(receipt.payload.get("packet_signature", "")) != packet_signature:
                    problems.append(f"method_validity source ref is from another verification round: {source_ref}")
    decisions = evaluate_compiled_proof_requirements(
        requirements,
        ledger,
        refs_by_proof,
        packet_signature=packet_signature,
        proof_contract_identity=proof_contract_identity,
    )
    if any(not decision.admitted for decision in decisions):
        problems.extend(
            f"{decision.proof_id}: {decision.code}"
            for decision in decisions
            if not decision.admitted
        )
    return ShadowProofEvidenceAdmission(
        not problems and all(decision.admitted for decision in decisions),
        decisions=decisions,
        problems=tuple(dict.fromkeys(problems)),
    )


@dataclass(frozen=True)
class CertifiedProofClause:
    clause_id: str
    requirement: str
    solver_handling: str
    verifier_route: str
    fallback_route: str
    falsification_check: str
    required_evidence_class: str
    route_kind: str
    route_evidence_ceiling: str
    requires_independent_evidence: bool = True
    proof_obligation: str = "exact_state"

    def as_dict(self) -> dict[str, Any]:
        return {
            "clause_id": self.clause_id,
            "requirement": self.requirement,
            "solver_handling": self.solver_handling,
            "verifier_route": self.verifier_route,
            "fallback_route": self.fallback_route,
            "falsification_check": self.falsification_check,
            "required_evidence_class": self.required_evidence_class,
            "proof_obligation": self.proof_obligation,
            "route_kind": self.route_kind,
            "route_evidence_ceiling": self.route_evidence_ceiling,
            "requires_independent_evidence": self.requires_independent_evidence,
        }


@dataclass(frozen=True)
class ProofContractIssue:
    code: str
    clause_id: str
    detail: str


@dataclass(frozen=True)
class ClauseEvidenceDecision:
    clause_id: str
    satisfied: bool
    code: str
    detail: str
    evidence_receipt_ids: tuple[str, ...] = ()


def _route_kind(route: str) -> str:
    return str(route or "").strip().split(":", 1)[0]


def _allowed_route_kinds(clause: CertifiedProofClause) -> set[str]:
    """Return execution kinds compatible with an Architect proof contract.

    ``verifier_route`` describes the intended evidence method.  It is not an
    executable command identity: derived commands are chosen later by the
    read-only Verifier and registered as immutable command hashes.  Requiring
    those two strings to match makes a valid V3 inspection impossible, while
    accepting an arbitrary route would weaken the contract.  Match only the
    compiler-certified route kind here; evidence class, provenance,
    admissibility, freshness, and the Verifier's clause reference remain
    mandatory at the surrounding gates.
    """
    routes = {clause.verifier_route}
    if clause.fallback_route:
        routes.add(clause.fallback_route)
    return {_route_kind(route) for route in routes if _route_kind(route)}


def _strength(value: str) -> int:
    return EVIDENCE_STRENGTH.get(str(value).strip(), -1)


def _certified_routes(clause: CertifiedProofClause) -> set[str]:
    routes = {str(clause.verifier_route or "").strip()}
    if clause.fallback_route:
        routes.add(str(clause.fallback_route).strip())
    return {route for route in routes if route}


_PATH_TARGET_ROUTE_KINDS = frozenset({
    "read_file", "inspect_artifact", "perceive_artifact", "compare_initial_path",
})


def _canonical_workspace_path_target(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if text.startswith("/app/"):
        text = text[5:]
    elif text == "/app":
        text = "."
    normalized = posixpath.normpath(text or ".")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _registered_route_matches_certified(
    payload: Mapping[str, Any],
    *,
    certified_routes: set[str],
) -> bool:
    """Bind a registered direct observation to the compiler-certified target.

    Derived overlay commands intentionally have runtime-chosen command hashes and
    are bound separately by exact clause IDs. Direct routes are different: when
    the Architect certified a concrete target, a same-kind observation of another
    file/check/interface must not satisfy that clause. Kind-only certified routes
    remain generic by construction.
    """
    observed_kind = str(payload.get("route_kind", "")).strip() or _route_kind(
        str(payload.get("route", ""))
    )
    if observed_kind == "overlay_run_command":
        return True
    candidates = [
        route for route in certified_routes if _route_kind(route) == observed_kind
    ]
    if not candidates:
        return False
    # A kind-only route explicitly leaves the target unconstrained.
    if any(":" not in route or not route.split(":", 1)[1].strip() for route in candidates):
        return True

    actual_route = str(payload.get("route", "")).strip()
    actual_target = actual_route.split(":", 1)[1].strip() if ":" in actual_route else ""
    if observed_kind in _PATH_TARGET_ROUTE_KINDS:
        identity = str(payload.get("target_identity", "")).strip()
        if identity.startswith("path:"):
            actual_target = identity[len("path:"):].strip()
        if not actual_target:
            return False
        actual = _canonical_workspace_path_target(actual_target)
        return any(
            actual == _canonical_workspace_path_target(route.split(":", 1)[1])
            for route in candidates
        )
    return bool(actual_target) and any(
        actual_target == route.split(":", 1)[1].strip() for route in candidates
    )


def certify_proof_contract(
    coverage_rows: Sequence[Mapping[str, Any]],
    check_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[CertifiedProofClause, ...], tuple[ProofContractIssue, ...]]:
    """Certify clause/route alignment and evidential ceilings."""
    if not coverage_rows and not check_rows:
        return (), ()
    issues: list[ProofContractIssue] = []
    coverage_by_id: dict[str, Mapping[str, Any]] = {}
    checks_by_id: dict[str, Mapping[str, Any]] = {}
    for source, rows, target in (
        ("coverage", coverage_rows, coverage_by_id),
        ("check", check_rows, checks_by_id),
    ):
        for row in rows:
            clause_id = str(row.get("clause_id", "")).strip()
            if not clause_id:
                issues.append(ProofContractIssue(
                    "proof_clause_id_missing", "", f"{source} row has no clause_id",
                ))
                continue
            if clause_id in target:
                issues.append(ProofContractIssue(
                    "proof_clause_id_duplicate", clause_id, f"duplicate {source} row",
                ))
                continue
            target[clause_id] = row
    for clause_id in sorted(set(coverage_by_id) ^ set(checks_by_id)):
        issues.append(ProofContractIssue(
            "proof_clause_route_missing", clause_id,
            "clause coverage and verifier route IDs must match exactly",
        ))

    certified: list[CertifiedProofClause] = []
    for clause_id in sorted(set(coverage_by_id) & set(checks_by_id)):
        coverage = coverage_by_id[clause_id]
        check = checks_by_id[clause_id]
        route = str(check.get("inspection_route", "")).strip()
        kind = _route_kind(route)
        required = str(check.get("required_evidence_class", "")).strip()
        obligation = str(check.get("proof_obligation", "exact_state")).strip() or "exact_state"
        ceiling = ROUTE_EVIDENCE_CEILINGS.get(kind, "")
        if obligation == "public_behavior" and _strength(required) < _strength("behavioral"):
            issues.append(ProofContractIssue("proof_obligation_underclassified", clause_id, "public_behavior requires behavioral evidence or stronger"))
            continue
        if obligation == "generated_interface_semantics" and _strength(required) < _strength("independent_semantic"):
            issues.append(ProofContractIssue("proof_obligation_underclassified", clause_id, "generated_interface_semantics requires independent_semantic evidence"))
            continue
        if required not in EVIDENCE_STRENGTH:
            issues.append(ProofContractIssue(
                "proof_evidence_class_unknown", clause_id,
                f"unknown required evidence class: {required!r}",
            ))
            continue
        if not ceiling:
            issues.append(ProofContractIssue(
                "proof_route_unavailable", clause_id,
                f"unsupported verifier route kind: {kind!r}",
            ))
            continue
        if _strength(ceiling) < _strength(required):
            issues.append(ProofContractIssue(
                "proof_route_strength_insufficient", clause_id,
                f"route {route!r} ceiling={ceiling} cannot establish required={required}",
            ))
            continue
        falsification = str(check.get("falsification_check", "")).strip()
        if not falsification:
            issues.append(ProofContractIssue(
                "proof_falsification_missing", clause_id,
                "critical clause has no falsification check",
            ))
            continue
        certified.append(CertifiedProofClause(
            clause_id=clause_id,
            requirement=str(coverage.get("verifier_check", "")).strip(),
            solver_handling=str(coverage.get("solver_handling", "")).strip(),
            verifier_route=route,
            fallback_route=str(check.get("fallback_route", "") or "").strip(),
            falsification_check=falsification,
            required_evidence_class=required,
            proof_obligation=obligation,
            route_kind=kind,
            route_evidence_ceiling=ceiling,
            requires_independent_evidence=kind in INDEPENDENT_ROUTE_KINDS,
        ))
    return tuple(certified), tuple(issues)


def record_clause_evidence(
    ledger: ExecutionLedger,
    *,
    receipt_id: str,
    step: int,
    clause_id: str,
    route: str,
    evidence_class: str,
    provenance: str,
    supports_clause: bool,
    observation: str,
    state_generation: str = "",
    task_state_generation: int | None = None,
    inspection_ids: Sequence[str] = (),
) -> Receipt:
    """Record one current proof/disproof observation for a clause."""
    current_generation = (
        ledger.task_state_generation()
        if task_state_generation is None else int(task_state_generation)
    )
    receipt = Receipt(
        receipt_id=receipt_id,
        step=step,
        kind="proof_evidence",
        success=bool(supports_clause),
        summary=observation,
        failure_class="" if supports_clause else "clause_disproved",
        payload={
            "clause_id": clause_id,
            "route": route,
            "route_kind": _route_kind(route),
            "evidence_class": evidence_class,
            "provenance": provenance,
            "supports_clause": bool(supports_clause),
            "observation": observation,
            "state_generation": state_generation or str(current_generation),
            "task_state_generation": current_generation,
            "inspection_ids": [str(item) for item in inspection_ids if str(item).strip()],
        },
    )
    ledger.record(receipt)
    return receipt


def evaluate_proof_contract(
    clauses: Sequence[Mapping[str, Any] | CertifiedProofClause],
    ledger: ExecutionLedger,
) -> tuple[ClauseEvidenceDecision, ...]:
    """Evaluate current receipted proof without interpreting task semantics."""
    decisions: list[ClauseEvidenceDecision] = []
    current_generation = ledger.task_state_generation()
    proof_receipts = [receipt for receipt in ledger.all_receipts() if receipt.kind == "proof_evidence"]
    for raw_clause in clauses:
        clause = raw_clause if isinstance(raw_clause, CertifiedProofClause) else CertifiedProofClause(
            clause_id=str(raw_clause.get("clause_id", "")),
            requirement=str(raw_clause.get("requirement", "")),
            solver_handling=str(raw_clause.get("solver_handling", "")),
            verifier_route=str(raw_clause.get("verifier_route", "")),
            fallback_route=str(raw_clause.get("fallback_route", "")),
            falsification_check=str(raw_clause.get("falsification_check", "")),
            required_evidence_class=str(raw_clause.get("required_evidence_class", "")),
            proof_obligation=str(raw_clause.get("proof_obligation", "exact_state")),
            route_kind=str(raw_clause.get("route_kind", "")),
            route_evidence_ceiling=str(raw_clause.get("route_evidence_ceiling", "")),
            requires_independent_evidence=bool(raw_clause.get("requires_independent_evidence", True)),
        )
        matching = [
            receipt for receipt in proof_receipts
            if str(receipt.payload.get("clause_id", "")).strip() == clause.clause_id
        ]
        if not matching:
            decisions.append(ClauseEvidenceDecision(
                clause.clause_id, False, "missing_clause_evidence",
                f"no proof evidence recorded for {clause.clause_id}",
            ))
            continue
        latest_disproof = next((receipt for receipt in reversed(matching) if not receipt.success), None)
        latest_support = next((receipt for receipt in reversed(matching) if receipt.success), None)
        if latest_disproof is not None and (
            latest_support is None or latest_disproof.step >= latest_support.step
        ):
            decisions.append(ClauseEvidenceDecision(
                clause.clause_id, False, "clause_disproved",
                latest_disproof.summary, (latest_disproof.receipt_id,),
            ))
            continue
        candidates: list[Receipt] = []
        stale_candidates: list[Receipt] = []
        allowed_route_kinds = _allowed_route_kinds(clause)
        for receipt in matching:
            if not receipt.success:
                continue
            payload = receipt.payload
            observed_kind = str(payload.get("route_kind", "")).strip() or _route_kind(
                str(payload.get("route", ""))
            )
            if observed_kind not in allowed_route_kinds:
                continue
            evidence_class = str(payload.get("evidence_class", "")).strip()
            if _strength(evidence_class) < _strength(clause.required_evidence_class):
                continue
            if str(payload.get("source", "")).strip() == "model_verifier_completion_evidence":
                actual_class = str(payload.get("actual_evidence_class", "")).strip()
                if _strength(evidence_class) > _strength(actual_class):
                    continue
            if clause.requires_independent_evidence:
                provenance = str(payload.get("provenance", "")).strip()
                if provenance not in INDEPENDENT_PROVENANCE:
                    continue
            try:
                evidence_generation = int(payload.get("task_state_generation"))
            except (TypeError, ValueError):
                evidence_generation = -1
            if evidence_generation != current_generation:
                stale_candidates.append(receipt)
                continue
            candidates.append(receipt)
        if not candidates:
            if stale_candidates:
                generations = sorted({
                    int(item.payload.get("task_state_generation", -1))
                    for item in stale_candidates
                })
                decisions.append(ClauseEvidenceDecision(
                    clause.clause_id,
                    False,
                    "stale_clause_evidence",
                    f"proof observed task generation(s) {generations}; current generation={current_generation}",
                    tuple(item.receipt_id for item in stale_candidates),
                ))
                continue
            strongest = max(
                (_strength(str(receipt.payload.get("evidence_class", ""))) for receipt in matching if receipt.success),
                default=-1,
            )
            decisions.append(ClauseEvidenceDecision(
                clause.clause_id, False, "insufficient_clause_evidence",
                (
                    f"required route={clause.verifier_route!r}, class={clause.required_evidence_class}; "
                    f"strongest observed rank={strongest}"
                ),
                tuple(receipt.receipt_id for receipt in matching),
            ))
            continue
        accepted = candidates[-1]
        decisions.append(ClauseEvidenceDecision(
            clause.clause_id, True, "clause_proved", accepted.summary,
            (accepted.receipt_id,),
        ))
    return tuple(decisions)


def _registered_inspection_support(
    ledger: ExecutionLedger,
    *,
    inspection_ids: Sequence[str],
    allowed_route_kinds: set[str],
    certified_routes: set[str],
    evidence_class: str,
    clause_id: str,
) -> Receipt | None:
    """Strongest successful registered inspection matching a proof route."""
    from .inspection_registry import (
        inspection_records_by_id,
        inspection_superseded_by_later_observation,
    )

    registry = inspection_records_by_id(ledger)
    candidates: list[Receipt] = []
    for inspection_id in inspection_ids:
        receipt = registry.get(str(inspection_id))
        if receipt is None or not receipt.success:
            continue
        payload = receipt.payload
        if not bool(payload.get("eligible_for_proof", False)):
            continue
        if inspection_superseded_by_later_observation(ledger, receipt):
            continue
        observed_kind = str(payload.get("route_kind", "")).strip() or _route_kind(
            str(payload.get("route", ""))
        )
        if observed_kind not in allowed_route_kinds:
            continue
        if not _registered_route_matches_certified(
            payload, certified_routes=certified_routes,
        ):
            continue
        if observed_kind == "overlay_run_command":
            parameters = payload.get("route_parameters", {})
            bound_clause_ids = parameters.get("clause_ids", ()) if isinstance(parameters, Mapping) else ()
            if clause_id not in {str(item).strip() for item in bound_clause_ids}:
                continue
        actual_class = str(payload.get("actual_evidence_class", "")).strip()
        if _strength(actual_class) < _strength(evidence_class):
            continue
        candidates.append(receipt)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: _strength(str(item.payload.get("actual_evidence_class", ""))),
    )


def record_verifier_result_evidence(
    ledger: ExecutionLedger,
    *,
    result: Any,
    compiled: Any,
    step: int,
) -> tuple[Receipt, ...]:
    """Project validated Verifier clause evidence into durable proof receipts.

    ``verify_with_inspector`` already validates completion inspection refs
    before this point. This bridge does not reinterpret the Verifier's
    reasoning; it binds clause IDs and evidence classes to the compiler-owned
    route so the completion gate can enforce the typed contract.
    """
    contract_by_id = {
        str(row.get("clause_id", "")).strip(): row
        for row in getattr(compiled, "proof_contract", ())
        if isinstance(row, Mapping) and str(row.get("clause_id", "")).strip()
    }
    if not contract_by_id:
        return ()
    recorded: list[Receipt] = []

    if getattr(result, "verdict", "") == "completed":
        for entry_index, entry in enumerate(getattr(result, "completion_evidence", ())):
            inspection_ids = tuple(
                str(item).strip()
                for item in getattr(entry, "inspection_refs", ())
                if str(item).strip()
            )
            evidence_class = str(getattr(entry, "evidence_class", "")).strip()
            for clause_id in getattr(entry, "clause_ids", ()):
                clause_id = str(clause_id).strip()
                contract = contract_by_id.get(clause_id)
                if contract is None:
                    continue
                clause = CertifiedProofClause(
                    clause_id=clause_id,
                    requirement=str(contract.get("requirement", "")),
                    solver_handling=str(contract.get("solver_handling", "")),
                    verifier_route=str(contract.get("verifier_route", "")),
                    fallback_route=str(contract.get("fallback_route", "")),
                    falsification_check=str(contract.get("falsification_check", "")),
                    required_evidence_class=str(contract.get("required_evidence_class", "")),
                    proof_obligation=str(contract.get("proof_obligation", "exact_state")),
                    route_kind=str(contract.get("route_kind", "")),
                    route_evidence_ceiling=str(contract.get("route_evidence_ceiling", "")),
                    requires_independent_evidence=bool(contract.get("requires_independent_evidence", True)),
                )
                allowed_route_kinds = _allowed_route_kinds(clause)
                certified_routes = _certified_routes(clause)
                chosen = _registered_inspection_support(
                    ledger,
                    inspection_ids=inspection_ids,
                    allowed_route_kinds=allowed_route_kinds,
                    certified_routes=certified_routes,
                    evidence_class=evidence_class,
                    clause_id=clause_id,
                )
                if chosen is None:
                    rejected = record_clause_evidence(
                        ledger,
                        receipt_id=f"step-{step}:proof:{clause_id}:rejected:{entry_index}",
                        step=step,
                        clause_id=clause_id,
                        route="unregistered_inspection",
                        evidence_class="model_claim",
                        provenance="verifier_inspection",
                        supports_clause=False,
                        observation=(
                            f"completion evidence for {clause_id} did not cite a successful "
                            "registered inspection on an allowed route"
                        ),
                        inspection_ids=inspection_ids,
                    )
                    rejected.payload.update({
                        "source": "model_verifier_completion_evidence_rejected",
                        "allowed_route_kinds": sorted(allowed_route_kinds),
                        "certified_routes": sorted(certified_routes),
                    })
                    recorded.append(rejected)
                    continue
                actual = chosen.payload
                receipt = record_clause_evidence(
                    ledger,
                    receipt_id=f"step-{step}:proof:{clause_id}:completed:{entry_index}",
                    step=step,
                    clause_id=clause_id,
                    route=str(actual.get("route", "")),
                    evidence_class=evidence_class,
                    provenance="verifier_inspection",
                    supports_clause=True,
                    observation=str(getattr(entry, "observed", "") or getattr(entry, "requirement", "")),
                    state_generation=str(actual.get("target_generation", "")),
                    task_state_generation=int(actual.get("task_state_generation", -1)),
                    inspection_ids=inspection_ids,
                )
                receipt.payload.update({
                    "inspection_refs": list(inspection_ids),
                    "selected_inspection_id": str(actual.get("inspection_id", chosen.receipt_id)),
                    "target_identity": str(actual.get("target_identity", "")),
                    "target_generation": str(actual.get("target_generation", "")),
                    "result_hash": str(actual.get("result_hash", "")),
                    "tool_identity": str(actual.get("tool_identity", "")),
                    "actual_evidence_class": str(actual.get("actual_evidence_class", "")),
                    "actual_evidence_ceiling": str(actual.get("evidence_ceiling", "")),
                    "falsification_check": str(getattr(entry, "falsification_check", "")),
                    "source": "model_verifier_completion_evidence",
                })
                recorded.append(receipt)
        return tuple(recorded)

    for finding_index, finding in enumerate(getattr(result, "findings", ())):
        targets = {
            str(target).strip()
            for target in getattr(finding, "applies_to", ())
            if str(target).strip()
        }
        for clause_id in sorted(targets & set(contract_by_id)):
            contract = contract_by_id[clause_id]
            observation_parts = [str(getattr(finding, "summary", "")).strip()]
            observation_parts.extend(str(item).strip() for item in getattr(finding, "evidence", ()) if str(item).strip())
            observation = "; ".join(part for part in observation_parts if part)
            receipt = record_clause_evidence(
                ledger,
                receipt_id=f"step-{step}:proof:{clause_id}:finding:{finding_index}",
                step=step,
                clause_id=clause_id,
                route=str(contract.get("verifier_route", "")),
                evidence_class=str(contract.get("required_evidence_class", "")),
                provenance="verifier_inspection",
                supports_clause=False,
                observation=observation or f"Verifier finding for {clause_id}",
            )
            receipt.payload.update({
                "finding_id": str(getattr(finding, "finding_id", "")),
                "repair_instruction": str(getattr(finding, "repair_instruction", "")),
                "source": "model_verifier_finding",
            })
            recorded.append(receipt)
    return tuple(recorded)


def record_shadow_proof_evidence_admission(
    ledger: ExecutionLedger,
    *,
    result: Any,
    requirements: Sequence[CompiledProofRequirement],
    step: int,
    packet_signature: str,
    proof_contract_identity: str,
    verifier_result_receipt_id: str,
) -> ShadowProofEvidenceAdmission:
    """Record the mechanical typed evidence-admission projection.

    This receipt is deliberately separate from the model's semantic verdict.
    ``admitted`` means only that the kernel accepted the proof references and
    their executable receipts under the current round and registry identity.
    """
    evaluation = evaluate_shadow_proof_evidence_admission(
        result,
        requirements,
        ledger,
        packet_signature=packet_signature,
        proof_contract_identity=proof_contract_identity,
    )
    admission_receipt_id = f"step-{step}:proof_evidence_admission"
    ledger.record(Receipt(
        receipt_id=admission_receipt_id,
        step=step,
        kind="proof_evidence_admission",
        success=evaluation.admitted,
        summary=(
            "kernel proof evidence admitted"
            if evaluation.admitted
            else "kernel proof evidence not admitted"
        ),
        failure_class="" if evaluation.admitted else "proof_evidence_not_admitted",
        payload={
            "admitted": evaluation.admitted,
            "code": "proof_evidence_admitted" if evaluation.admitted else "proof_evidence_not_admitted",
            "problems": list(evaluation.problems),
            "decisions": [
                {
                    "proof_id": decision.proof_id,
                    "admitted": decision.admitted,
                    "code": decision.code,
                    "detail": decision.detail,
                    "evidence_receipt_ids": list(decision.evidence_receipt_ids),
                }
                for decision in evaluation.decisions
            ],
            "packet_signature": packet_signature,
            "proof_contract_identity": proof_contract_identity,
            "proof_registry_version": PROOF_REGISTRY_VERSION,
            "proof_registry_digest": PROOF_REGISTRY_DIGEST,
            "task_state_generation": ledger.task_state_generation(),
            "verifier_result_receipt_id": verifier_result_receipt_id,
            "verifier_verdict": str(getattr(result, "verdict", "")),
            "source": "kernel_proof_evidence_admission",
        },
    ))
    if evaluation.admitted and str(getattr(result, "verdict", "")) == "completed":
        for requirement in requirements:
            for obligation_id in requirement.obligation_ids:
                ledger.mark_obligation_satisfied(obligation_id, admission_receipt_id)
    return evaluation

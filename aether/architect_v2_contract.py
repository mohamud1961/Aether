"""Zero-model validation for the proposed Architect v2 authority contract.

This module validates the semantic contract and deliberately does not choose
runtime routes or render a prompt.  The optional route-independent proof seam
lives in the kernel proof registry and is carried by the existing runtime
types; v2 validation remains a separate authority check until activation.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence

from .model_hooks import ModelOutputError
from .proof_contract import (
    PROOF_KINDS,
    CompiledProofRequirement,
    compile_proof_requirements,
    proof_requirements_identity,
)


V2_SCHEMA_VERSION = "aether_architect.v2"
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SOURCES = frozenset({"task_prompt", "visible_environment", "visible_material"})
# These are mechanics or runtime authorities.  They are rejected by key,
# never inferred from natural-language values.  This keeps semantic text free
# to discuss a task's actual concepts without making a lexical policy gate.
FORBIDDEN_MODEL_KEYS = frozenset({
    "action",
    "command",
    "context_policy",
    "context_selector",
    "evidence_class",
    "fallback_route",
    "freshness",
    "inspection_route",
    "memory_policy",
    "proof_strength",
    "provider",
    "required_evidence_class",
    "receipt",
    "response_schema",
    "route",
    "tool",
    "transport",
})

_OBLIGATION_PROOF_KEYS = frozenset({
    "acceptance_intent",
    "evidence_intent",
    "falsification_intent",
    "independence_emphasis",
    "independence_requirement",
})

_SOLVER_REQUIRED = frozenset({
    "mission",
    "strategy",
})
_SOLVER_OPTIONAL = frozenset({
    "priorities",
    "task_specific_rules",
    "failure_response",
    "self_verification_emphasis",
    "completion_emphasis",
})
_VERIFIER_REQUIRED = frozenset({
    "mission",
    "verification_strategy",
})
_VERIFIER_OPTIONAL = frozenset({
    "falsification_priorities",
    "false_positive_risks",
    "completion_emphasis",
})


@dataclass(frozen=True)
class ArchitectV2Contract:
    """Immutable validated semantic authority; not a runtime configuration."""

    _canonical_payload: str
    contract_identity: str
    fact_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    proof_ids: tuple[str, ...]
    proof_kinds: tuple[str, ...]

    @property
    def payload(self) -> Mapping[str, Any]:
        """Return a fresh decoded view so callers cannot mutate authority."""
        return json.loads(self._canonical_payload)

    @property
    def canonical_payload(self) -> str:
        return self._canonical_payload


class ArchitectV2CompatibilityError(ModelOutputError):
    """Raised when v2 cannot be safely represented by the current runtime."""


@dataclass(frozen=True)
class ArchitectV2ProofSeam:
    """Shadow-only binding from v2 proof intent to the existing proof type.

    This is intentionally narrower than a runtime adapter.  It validates the
    v2 contract, compiles its route-independent proof records with the kernel
    compiler, and exposes the existing compiled identity.  It does not choose
    routes, render prompts, construct ``HarnessConfigIR``, or dispatch a
    provider/model call.
    """

    contract: ArchitectV2Contract
    requirements: tuple[CompiledProofRequirement, ...]
    requirements_identity: str
    status: str = "shadow_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": self.contract.payload.get("schema_version"),
            "contract_identity": self.contract.contract_identity,
            "proof_requirements": [item.as_dict() for item in self.requirements],
            "proof_requirements_identity": self.requirements_identity,
            "runtime_targets": [
                "RuntimeConfigIR.proof_requirements",
                "CompiledRuntime.proof_requirements",
                "verifier_packet.compiled_proof_requirements",
            ],
            "route_selection": "kernel/verifier-owned; absent from v2 binding",
            "activation": "not_runtime_eligible",
        }


@dataclass(frozen=True)
class ArchitectV2ShadowProjection:
    """Lossless, non-dispatching projection of v2 semantic material.

    The projection is intentionally not a ``HarnessConfigIR``.  It gives the
    future adapter a tested representation for the parts that can already be
    carried by current consumers while making the unresolved anchor mapping
    explicit instead of guessing owner/type semantics.
    """

    contract: ArchitectV2Contract
    proof_seam: ArchitectV2ProofSeam
    task_material: str
    solver_prompt: str
    verifier_prompt: str
    deferred_projections: tuple[str, ...]
    status: str = "shadow_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "task_material": self.task_material,
            "solver_prompt": self.solver_prompt,
            "verifier_prompt": self.verifier_prompt,
            "proof_seam": self.proof_seam.as_dict(),
            "deferred_projections": list(self.deferred_projections),
            "activation": "not_runtime_eligible",
        }


def _render_values(title: str, values: Sequence[str]) -> list[str]:
    if not values:
        return []
    return [title + ":", *(f"- {value}" for value in values)]


def _render_role_design(
    title: str,
    design: Mapping[str, Any],
    *,
    list_fields: Sequence[tuple[str, str]],
    row_fields: Sequence[tuple[str, str]],
) -> str:
    lines = [f"[{title}]", f"Mission: {design['mission']}"]
    strategy_key = "strategy" if "strategy" in design else "verification_strategy"
    lines.append(f"Strategy: {design[strategy_key]}")
    for field, label in list_fields:
        values = design.get(field, ())
        if isinstance(values, str):
            values = (values,)
        if values:
            lines.extend(_render_values(label, tuple(str(item) for item in values)))
    for field, label in row_fields:
        rows = design.get(field, ())
        if not rows:
            continue
        lines.append(label + ":")
        for row in rows:
            refs = ",".join(str(item) for item in row.get("obligation_refs", ()))
            suffix = f" [obligations: {refs}]" if refs else ""
            item_id = row.get("rule_id", row.get("risk_id", "item"))
            authority = str(row.get("authority") or "").strip()
            authority_prefix = f"[{authority}] " if authority else ""
            lines.append(f"- {item_id}: {authority_prefix}{row['statement']}{suffix}")
    return "\n".join(lines)


def project_architect_v2_shadow(
    payload_or_contract: Mapping[str, Any] | ArchitectV2Contract,
) -> ArchitectV2ShadowProjection:
    """Project v2 facts and role design without activating a runtime.

    ``task_material`` is canonical JSON containing exact facts and
    obligations only. Information emphasis is Solver-only advisory material.
    It is lossless transport material
    for an existing summary/evidence consumer, not a new semantic authority.
    Exact anchors are retained there but are not guessed into the current
    ``visible_contract`` type because v2 does not provide owner/type meaning.
    Role prompts contain only role-design fields and therefore do not repeat
    the task contract or proof observations.
    """

    contract = (
        payload_or_contract
        if isinstance(payload_or_contract, ArchitectV2Contract)
        else validate_architect_v2(payload_or_contract)
    )
    seam = bind_architect_v2_proof_seam(contract)
    task = contract.payload["task_contract"]
    task_material = json.dumps(
        {
            "exact_facts": task["exact_facts"],
            "obligations": task["obligations"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    solver_prompt = _render_role_design(
        "Architect v2 Solver design",
        contract.payload["solver_design"],
        list_fields=(
            ("priorities", "Priorities"),
            ("failure_response", "Failure response"),
            ("self_verification_emphasis", "Self-verification emphasis"),
            ("completion_emphasis", "Completion emphasis"),
        ),
        row_fields=(("task_specific_rules", "Task-specific rules"),),
    )
    method_rows = tuple(contract.payload.get("method_constraints", ()))
    if method_rows:
        lines = [solver_prompt, "[Architect v2 required methods]"]
        for row in method_rows:
            refs = ",".join(str(item) for item in row.get("obligation_refs", ()))
            suffix = f" [obligations: {refs}]" if refs else ""
            lines.append(
                f"- {row['constraint_id']}: {row['statement']}{suffix}"
            )
        solver_prompt = "\n".join(lines)
    emphasis = tuple(contract.payload.get("information_emphasis", ()))
    if emphasis:
        lines = [solver_prompt, "[Architect v2 information emphasis]"]
        for row in emphasis:
            fact_refs = ",".join(str(item) for item in row.get("fact_refs", ()))
            obligation_refs = ",".join(
                str(item) for item in row.get("obligation_refs", ())
            )
            ref_parts = []
            if fact_refs:
                ref_parts.append(f"facts: {fact_refs}")
            if obligation_refs:
                ref_parts.append(f"obligations: {obligation_refs}")
            suffix = f" [{'; '.join(ref_parts)}]" if ref_parts else ""
            lines.append(f"- {row['topic']}: {row['rationale']}{suffix}")
        solver_prompt = "\n".join(lines)
    verifier_prompt = _render_role_design(
        "Architect v2 Verifier design",
        contract.payload["verifier_design"],
        list_fields=(
            ("falsification_priorities", "Falsification priorities"),
            ("completion_emphasis", "Completion emphasis"),
        ),
        # false_positive_risks are structured completion authority. The adapter
        # realizes them through RuntimeConfigIR.false_positive_risks so the
        # Verifier packet and exact risk_refs gate carry them once, without
        # duplicating the same semantics in identity prose.
        row_fields=(),
    )
    return ArchitectV2ShadowProjection(
        contract=contract,
        proof_seam=seam,
        task_material=task_material,
        solver_prompt=solver_prompt,
        verifier_prompt=verifier_prompt,
        deferred_projections=(
            "v2 exact facts and anchors remain canonical TaskContract material; visible_contract is intentionally unused",
        ),
    )


def bind_architect_v2_proof_seam(
    payload_or_contract: Mapping[str, Any] | ArchitectV2Contract,
) -> ArchitectV2ProofSeam:
    """Bind validated v2 proof intent to the canonical kernel proof seam.

    The function is a zero-model compatibility check.  It deliberately
    returns existing ``CompiledProofRequirement`` values rather than a new
    v2 runtime type.  Any v2 validation or kernel compilation failure is
    surfaced as a fail-closed compatibility error.
    """

    contract = (
        payload_or_contract
        if isinstance(payload_or_contract, ArchitectV2Contract)
        else validate_architect_v2(payload_or_contract)
    )
    if sha256(contract.canonical_payload.encode("utf-8")).hexdigest() != contract.contract_identity:
        raise ArchitectV2CompatibilityError("Architect v2 contract identity mismatch")
    try:
        requirements = compile_proof_requirements(
            tuple(contract.payload.get("proof_intent", ()))
        )
    except (TypeError, ValueError) as exc:
        raise ArchitectV2CompatibilityError(
            f"Architect v2 proof intent cannot bind to the canonical proof seam: {exc}"
        ) from exc

    compiled_ids = tuple(item.proof_id for item in requirements)
    if compiled_ids != contract.proof_ids:
        raise ArchitectV2CompatibilityError(
            "Architect v2 proof seam changed proof IDs during compilation"
        )
    identity = proof_requirements_identity(requirements)
    return ArchitectV2ProofSeam(
        contract=contract,
        requirements=requirements,
        requirements_identity=identity,
    )


def _path(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child


def _mapping(value: Any, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelOutputError(f"{location} must be an object")
    return value


def _list(value: Any, location: str, *, minimum: int = 0, maximum: int | None = None) -> list[Any]:
    if not isinstance(value, list):
        raise ModelOutputError(f"{location} must be an array")
    if len(value) < minimum:
        raise ModelOutputError(f"{location} must contain at least {minimum} item(s)")
    if maximum is not None and len(value) > maximum:
        raise ModelOutputError(f"{location} must contain at most {maximum} item(s)")
    return value


def _text(value: Any, location: str, *, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelOutputError(f"{location} must be a non-empty string")
    text = value.strip()
    if len(text) > maximum:
        raise ModelOutputError(f"{location} exceeds {maximum} characters")
    return text


def _id(value: Any, location: str) -> str:
    text = _text(value, location, maximum=64)
    if not _ID_PATTERN.fullmatch(text):
        raise ModelOutputError(f"{location} is not a valid v2 identifier")
    return text


def _unique_ids(rows: Sequence[Mapping[str, Any]], key: str, location: str) -> tuple[str, ...]:
    values = tuple(_id(row.get(key), f"{location}[{index}].{key}") for index, row in enumerate(rows))
    if len(set(values)) != len(values):
        raise ModelOutputError(f"{location}.{key} values must be unique")
    return values


def _refs(value: Any, location: str, known: set[str]) -> tuple[str, ...]:
    return _refs_with_minimum(value, location, known, minimum=1)


def _refs_with_minimum(value: Any, location: str, known: set[str], *, minimum: int) -> tuple[str, ...]:
    raw = _list(value, location, minimum=minimum)
    result = tuple(_id(item, f"{location}[{index}]") for index, item in enumerate(raw))
    if len(set(result)) != len(result):
        raise ModelOutputError(f"{location} values must be unique")
    unknown = sorted(set(result) - known)
    if unknown:
        raise ModelOutputError(f"{location} contains unknown references: {', '.join(unknown)}")
    return result


def _optional_refs(value: Any, location: str, known: set[str]) -> tuple[str, ...]:
    if value is None:
        return ()
    return _refs_with_minimum(value, location, known, minimum=0)


def _assert_keys(value: Mapping[str, Any], allowed: set[str], required: set[str], location: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ModelOutputError(f"{location} has unsupported fields: {', '.join(unknown)}")
    missing = sorted(required - set(value))
    if missing:
        raise ModelOutputError(f"{location} is missing required fields: {', '.join(missing)}")


def _scan_forbidden_keys(value: Any, location: str = "v2") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_MODEL_KEYS:
                raise ModelOutputError(f"{_path(location, str(key))} is kernel-owned and forbidden in v2")
            _scan_forbidden_keys(child, _path(location, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_forbidden_keys(child, f"{location}[{index}]")


def _reject_exact_anchors(
    text: str,
    anchors: set[str],
    location: str,
) -> None:
    leaked = sorted(anchor for anchor in anchors if anchor and anchor in text)
    if leaked:
        raise ModelOutputError(
            f"{location} repeats method-only exact anchors: " + ", ".join(leaked)
        )


def _validate_verifier_design(
    root: Mapping[str, Any],
    obligation_set: set[str],
    method_only_anchors: set[str],
) -> tuple[Mapping[str, Any], tuple[Mapping[str, Any], ...], tuple[str, ...], Mapping[str, tuple[str, ...]]]:
    """Validate global Verifier design before proof facets are authored.

    Risk prose remains model authority. This helper only establishes exact IDs,
    obligation bindings, and the reference set that proof_intent must close.
    """
    verifier = _mapping(root["verifier_design"], "v2.verifier_design")
    if "checks" in verifier or "clause_checks" in verifier:
        raise ModelOutputError("v2.verifier_design must not duplicate per-obligation checks")
    _assert_keys(
        verifier,
        set(_VERIFIER_REQUIRED | _VERIFIER_OPTIONAL),
        set(_VERIFIER_REQUIRED),
        "v2.verifier_design",
    )
    _text(verifier.get("mission"), "v2.verifier_design.mission")
    _text(verifier.get("verification_strategy"), "v2.verifier_design.verification_strategy")
    for field in ("falsification_priorities", "completion_emphasis"):
        if field not in verifier:
            continue
        priorities = _list(verifier[field], f"v2.verifier_design.{field}", maximum=16)
        for index, item in enumerate(priorities):
            _text(item, f"v2.verifier_design.{field}[{index}]")
    if "false_positive_risks" in verifier:
        risks = tuple(
            _mapping(item, f"v2.verifier_design.false_positive_risks[{index}]")
            for index, item in enumerate(
                _list(
                    verifier["false_positive_risks"],
                    "v2.verifier_design.false_positive_risks",
                    maximum=32,
                )
            )
        )
    else:
        risks = ()
    _assert_no_unknown_rows(
        risks,
        {"risk_id", "statement", "obligation_refs"},
        "v2.verifier_design.false_positive_risks",
    )
    risk_ids = _unique_ids(risks, "risk_id", "v2.verifier_design.false_positive_risks")
    risk_obligation_refs: dict[str, tuple[str, ...]] = {}
    for index, row in enumerate(risks):
        risk_statement = _text(
            row.get("statement"),
            f"v2.verifier_design.false_positive_risks[{index}].statement",
        )
        _reject_exact_anchors(
            risk_statement,
            method_only_anchors,
            f"v2.verifier_design.false_positive_risks[{index}].statement",
        )
        risk_obligation_refs[risk_ids[index]] = _optional_refs(
            row.get("obligation_refs"),
            f"v2.verifier_design.false_positive_risks[{index}].obligation_refs",
            obligation_set,
        )
    return verifier, risks, risk_ids, risk_obligation_refs


def validate_architect_v2(payload: Mapping[str, Any]) -> ArchitectV2Contract:
    """Validate v2 structure and semantic reference ownership.

    This function validates only the proposed authority contract.  It does
    not choose routes, infer evidence strength, render a prompt, or compile
    to ``HarnessConfigIR``.
    """
    root = _mapping(payload, "v2")
    _assert_keys(
        root,
        {"schema_version", "task_contract", "method_constraints", "proof_intent", "solver_design", "verifier_design", "information_emphasis"},
        {"schema_version", "task_contract", "method_constraints", "proof_intent", "solver_design", "verifier_design"},
        "v2",
    )
    if root.get("schema_version") != V2_SCHEMA_VERSION:
        raise ModelOutputError(f"v2.schema_version must be {V2_SCHEMA_VERSION}")
    _scan_forbidden_keys(root)

    task = _mapping(root["task_contract"], "v2.task_contract")
    _assert_keys(task, {"exact_facts", "obligations"}, {"exact_facts", "obligations"}, "v2.task_contract")

    fact_rows = [_mapping(item, f"v2.task_contract.exact_facts[{index}]") for index, item in enumerate(
        _list(task["exact_facts"], "v2.task_contract.exact_facts", minimum=0, maximum=256)
    )]
    _assert_no_unknown_rows(
        fact_rows,
        {"fact_id", "statement", "source", "verbatim_anchors"},
        "v2.task_contract.exact_facts",
    )
    fact_ids = _unique_ids(fact_rows, "fact_id", "v2.task_contract.exact_facts")
    for index, row in enumerate(fact_rows):
        _text(row.get("statement"), f"v2.task_contract.exact_facts[{index}].statement")
        if row.get("source") not in _SOURCES:
            raise ModelOutputError(f"v2.task_contract.exact_facts[{index}].source is unsupported")
        anchors = _list(
            row.get("verbatim_anchors"),
            f"v2.task_contract.exact_facts[{index}].verbatim_anchors",
            minimum=1,
            maximum=64,
        )
        if len(set(anchors)) != len(anchors):
            raise ModelOutputError(f"v2.task_contract.exact_facts[{index}].verbatim_anchors must be unique")
        for anchor_index, anchor in enumerate(anchors):
            anchor_text = _text(anchor, f"v2.task_contract.exact_facts[{index}].verbatim_anchors[{anchor_index}]", maximum=1000)
            if anchor_text not in row["statement"]:
                raise ModelOutputError(
                    f"v2.task_contract.exact_facts[{index}].verbatim_anchors[{anchor_index}] "
                    "must occur byte-for-byte in statement"
                )

    obligation_rows = [_mapping(item, f"v2.task_contract.obligations[{index}]") for index, item in enumerate(
        _list(task["obligations"], "v2.task_contract.obligations", minimum=1, maximum=128)
    )]
    for index, row in enumerate(obligation_rows):
        if _OBLIGATION_PROOF_KEYS.intersection(row):
            raise ModelOutputError(
                f"v2.task_contract.obligations[{index}] must not repeat proof semantics"
            )
        _text(row.get("statement"), f"v2.task_contract.obligations[{index}].statement")
    _assert_no_unknown_rows(obligation_rows, {"obligation_id", "statement", "fact_refs"}, "v2.task_contract.obligations")
    obligation_ids = _unique_ids(obligation_rows, "obligation_id", "v2.task_contract.obligations")
    fact_set = set(fact_ids)
    obligation_fact_refs: set[str] = set()
    for index, row in enumerate(obligation_rows):
        refs = _optional_refs(
            row.get("fact_refs"),
            f"v2.task_contract.obligations[{index}].fact_refs",
            fact_set,
        )
        obligation_fact_refs.update(refs)

    method_rows = [
        _mapping(item, f"v2.method_constraints[{index}]")
        for index, item in enumerate(
            _list(root["method_constraints"], "v2.method_constraints", maximum=32)
        )
    ]
    _assert_no_unknown_rows(
        method_rows,
        {
            "constraint_id", "statement", "verbatim_anchors",
            "obligation_refs", "acceptance_observation",
            "falsification_observation",
        },
        "v2.method_constraints",
    )
    _unique_ids(method_rows, "constraint_id", "v2.method_constraints")
    obligation_set = set(obligation_ids)
    method_anchor_rows: list[set[str]] = []
    for index, row in enumerate(method_rows):
        statement = _text(
            row.get("statement"), f"v2.method_constraints[{index}].statement"
        )
        anchors = _list(
            row.get("verbatim_anchors"),
            f"v2.method_constraints[{index}].verbatim_anchors",
            minimum=1,
            maximum=64,
        )
        if len(set(anchors)) != len(anchors):
            raise ModelOutputError(
                f"v2.method_constraints[{index}].verbatim_anchors must be unique"
            )
        normalized_anchors: set[str] = set()
        for anchor_index, anchor in enumerate(anchors):
            anchor_text = _text(
                anchor,
                f"v2.method_constraints[{index}].verbatim_anchors[{anchor_index}]",
                maximum=1000,
            )
            normalized_anchors.add(anchor_text)
        method_anchor_rows.append(normalized_anchors)
        _refs(
            row.get("obligation_refs"),
            f"v2.method_constraints[{index}].obligation_refs",
            obligation_set,
        )
        _text(
            row.get("acceptance_observation"),
            f"v2.method_constraints[{index}].acceptance_observation",
        )
        _text(
            row.get("falsification_observation"),
            f"v2.method_constraints[{index}].falsification_observation",
        )

    outcome_anchors = {
        str(anchor)
        for row in fact_rows
        for anchor in row.get("verbatim_anchors", ())
    }
    method_anchors = set().union(*method_anchor_rows) if method_anchor_rows else set()
    method_only_anchors = method_anchors - outcome_anchors
    for index, row in enumerate(obligation_rows):
        _reject_exact_anchors(
            str(row["statement"]),
            method_only_anchors,
            f"v2.task_contract.obligations[{index}].statement",
        )

    verifier, risks, risk_ids, risk_obligation_refs = _validate_verifier_design(
        root,
        obligation_set,
        method_only_anchors,
    )
    risk_set = set(risk_ids)

    proof_rows = [_mapping(item, f"v2.proof_intent[{index}]") for index, item in enumerate(
        _list(root["proof_intent"], "v2.proof_intent", minimum=1, maximum=128)
    )]
    _assert_no_unknown_rows(
        proof_rows,
        {"proof_id", "obligation_refs", "risk_refs", "proof_kind", "acceptance_observation", "falsification_observation"},
        "v2.proof_intent",
    )
    proof_ids = _unique_ids(proof_rows, "proof_id", "v2.proof_intent")
    proof_coverage: list[str] = []
    risk_coverage: list[str] = []
    proof_kinds: list[str] = []
    for index, row in enumerate(proof_rows):
        obligation_refs = _refs(
            row.get("obligation_refs"),
            f"v2.proof_intent[{index}].obligation_refs",
            obligation_set,
        )
        risk_refs = _optional_refs(
            row.get("risk_refs"),
            f"v2.proof_intent[{index}].risk_refs",
            risk_set,
        )
        for risk_id in risk_refs:
            bound_obligations = set(risk_obligation_refs.get(risk_id, ()))
            if bound_obligations and not bound_obligations.intersection(obligation_refs):
                raise ModelOutputError(
                    f"v2.proof_intent[{index}].risk_refs includes {risk_id} but the "
                    "proof and risk share no obligation_refs"
                )
        risk_coverage.extend(risk_refs)
        proof_kind = str(row.get("proof_kind", "")).strip()
        if proof_kind not in PROOF_KINDS:
            raise ModelOutputError(
                f"v2.proof_intent[{index}].proof_kind must be one of: {', '.join(PROOF_KINDS)}"
            )
        proof_kinds.append(proof_kind)
        for field in ("acceptance_observation", "falsification_observation"):
            observation = _text(row.get(field), f"v2.proof_intent[{index}].{field}")
            _reject_exact_anchors(
                observation,
                method_only_anchors,
                f"v2.proof_intent[{index}].{field}",
            )
        proof_coverage.extend(row["obligation_refs"])
    # Multiple typed proof facets may reference the same semantic obligation.
    # They are conjunctive at admission: completion remains blocked until every
    # compiled proof requirement is admitted. Only missing coverage is invalid.
    missing = sorted(obligation_set - set(proof_coverage))
    if missing:
        raise ModelOutputError("proof_intent does not cover obligations: " + ", ".join(missing))
    unclosed_risks = sorted(risk_set - set(risk_coverage))
    if unclosed_risks:
        raise ModelOutputError(
            "proof_intent does not formally close false-positive risks: "
            + ", ".join(unclosed_risks)
        )

    solver = _mapping(root["solver_design"], "v2.solver_design")
    if "workflow" in solver:
        raise ModelOutputError("v2.solver_design.workflow is not permitted; use adaptive strategy")
    _assert_keys(solver, set(_SOLVER_REQUIRED | _SOLVER_OPTIONAL), set(_SOLVER_REQUIRED), "v2.solver_design")
    for field in ("mission", "strategy"):
        _text(solver.get(field), f"v2.solver_design.{field}")
    for field in ("priorities", "self_verification_emphasis", "completion_emphasis"):
        if field not in solver:
            continue
        rows = _list(solver.get(field), f"v2.solver_design.{field}", maximum=16)
        for index, item in enumerate(rows):
            _text(item, f"v2.solver_design.{field}[{index}]")
    rules = [_mapping(item, f"v2.solver_design.task_specific_rules[{index}]") for index, item in enumerate(
        _list(solver.get("task_specific_rules", []), "v2.solver_design.task_specific_rules", maximum=32)
    )]
    _assert_no_unknown_rows(
        rules,
        {"rule_id", "statement"},
        "v2.solver_design.task_specific_rules",
    )
    _unique_ids(rules, "rule_id", "v2.solver_design.task_specific_rules")
    for index, row in enumerate(rules):
        _text(row.get("statement"), f"v2.solver_design.task_specific_rules[{index}].statement")
    if "failure_response" in solver:
        _text(solver["failure_response"], "v2.solver_design.failure_response")

    if "information_emphasis" in root:
        emphasis = [_mapping(item, f"v2.information_emphasis[{index}]") for index, item in enumerate(
            _list(root["information_emphasis"], "v2.information_emphasis", maximum=12)
        )]
    else:
        emphasis = []
    _assert_no_unknown_rows(emphasis, {"topic", "rationale", "fact_refs", "obligation_refs"}, "v2.information_emphasis")
    emphasized_fact_refs: set[str] = set()
    for index, row in enumerate(emphasis):
        _text(row.get("topic"), f"v2.information_emphasis[{index}].topic")
        _text(row.get("rationale"), f"v2.information_emphasis[{index}].rationale")
        emphasized_fact_refs.update(
            _optional_refs(
                row.get("fact_refs"),
                f"v2.information_emphasis[{index}].fact_refs",
                fact_set,
            )
        )
        _optional_refs(row.get("obligation_refs"), f"v2.information_emphasis[{index}].obligation_refs", obligation_set)

    unused_facts = sorted(
        fact_set - obligation_fact_refs - emphasized_fact_refs
    )
    if unused_facts:
        raise ModelOutputError(
            "exact facts must be referenced by an obligation or information emphasis: "
            + ", ".join(unused_facts)
        )

    canonical_payload = json.dumps(
        root, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return ArchitectV2Contract(
        _canonical_payload=canonical_payload,
        contract_identity=sha256(canonical_payload.encode("utf-8")).hexdigest(),
        fact_ids=fact_ids,
        obligation_ids=obligation_ids,
        proof_ids=proof_ids,
        proof_kinds=tuple(proof_kinds),
    )


def assert_current_runtime_compatibility_is_ready() -> None:
    """Keep production activation fail-closed until the full adapter exists.

    The route-independent proof seam now exists and is tested through
    ``bind_architect_v2_proof_seam``. Production activation remains blocked
    because provider/parser dispatch is deliberately not wired to the reviewed
    shadow adapter. Keeping this guard is intentional: deterministic
    compatibility must not be mistaken for live Architect qualification.
    """
    raise ArchitectV2CompatibilityError(
        "Architect v2 production dispatch remains blocked: the shadow adapter is not runtime-selected; "
        "v2 is not runtime-eligible"
    )


def _assert_no_unknown_rows(rows: Sequence[Mapping[str, Any]], allowed: set[str], location: str) -> None:
    for index, row in enumerate(rows):
        unknown = sorted(set(row) - allowed)
        if unknown:
            raise ModelOutputError(f"{location}[{index}] has unsupported fields: {', '.join(unknown)}")


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def find_exact_normalized_duplicates(payload: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    """Find exact case/whitespace-normalized prose repeats.

    This is a diagnostic lint only.  It does not infer semantic equivalence,
    reject paraphrases, or make a promotion decision.
    """
    locations: dict[str, list[str]] = {}

    def add(path: str, value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        normalized = _normalized_text(value)
        locations.setdefault(normalized, []).append(path)

    task = payload.get("task_contract", {}) if isinstance(payload, Mapping) else {}
    if isinstance(task, Mapping):
        for index, row in enumerate(task.get("exact_facts", [])):
            if isinstance(row, Mapping):
                add(f"task_contract.exact_facts[{index}].statement", row.get("statement"))
        for index, row in enumerate(task.get("obligations", [])):
            if isinstance(row, Mapping):
                add(f"task_contract.obligations[{index}].statement", row.get("statement"))
    for index, row in enumerate(payload.get("proof_intent", [])) if isinstance(payload, Mapping) else ():
        if isinstance(row, Mapping):
            for field in ("acceptance_observation", "falsification_observation"):
                add(f"proof_intent[{index}].{field}", row.get(field))
    for index, row in enumerate(payload.get("method_constraints", [])) if isinstance(payload, Mapping) else ():
        if isinstance(row, Mapping):
            for field in (
                "statement", "acceptance_observation",
                "falsification_observation",
            ):
                add(f"method_constraints[{index}].{field}", row.get(field))
    solver = payload.get("solver_design", {}) if isinstance(payload, Mapping) else {}
    if isinstance(solver, Mapping):
        for field in ("mission", "strategy", "failure_response"):
            add(f"solver_design.{field}", solver.get(field))
        for field in ("priorities", "self_verification_emphasis", "completion_emphasis"):
            for index, value in enumerate(solver.get(field, [])):
                add(f"solver_design.{field}[{index}]", value)
        for index, row in enumerate(solver.get("task_specific_rules", [])):
            if isinstance(row, Mapping):
                add(f"solver_design.task_specific_rules[{index}].statement", row.get("statement"))
    verifier = payload.get("verifier_design", {}) if isinstance(payload, Mapping) else {}
    if isinstance(verifier, Mapping):
        for field in ("mission", "verification_strategy"):
            add(f"verifier_design.{field}", verifier.get(field))
        for field in ("falsification_priorities", "completion_emphasis"):
            for index, value in enumerate(verifier.get(field, [])):
                add(f"verifier_design.{field}[{index}]", value)
        for index, row in enumerate(verifier.get("false_positive_risks", [])):
            if isinstance(row, Mapping):
                add(f"verifier_design.false_positive_risks[{index}].statement", row.get("statement"))
    emphasis = payload.get("information_emphasis", []) if isinstance(payload, Mapping) else []
    for index, row in enumerate(emphasis):
        if isinstance(row, Mapping):
            add(f"information_emphasis[{index}].topic", row.get("topic"))
            add(f"information_emphasis[{index}].rationale", row.get("rationale"))
    return {
        key: tuple(paths)
        for key, paths in locations.items()
        if len(paths) > 1
    }


def architect_v2_json_schema() -> dict[str, Any]:
    """Return the canonical provider/parser schema for Architect v2.

    The checked-in handoff JSON is generated from this function and parity
    tested.  It is intentionally not wired into production request dispatch
    until the route-independent runtime seam is approved.
    """
    text = {"type": "string", "minLength": 1, "maxLength": 4000, "pattern": r".*\S.*"}
    identifier = {"type": "string", "pattern": _ID_PATTERN.pattern, "maxLength": 64}
    refs = {"type": "array", "uniqueItems": True, "items": identifier}
    optional_refs = {"type": "array", "uniqueItems": True, "items": identifier}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://aether.invalid/schemas/aether_architect.v2.canonical.json",
        "title": "Aether Architect v2 canonical authority contract",
        "description": "Generated from aether.architect_v2_contract; not activated.",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "task_contract", "method_constraints", "proof_intent", "solver_design", "verifier_design"],
        "properties": {
            "schema_version": {"const": V2_SCHEMA_VERSION},
            "task_contract": {
                "type": "object",
                "additionalProperties": False,
                "required": ["exact_facts", "obligations"],
                "properties": {
                    "exact_facts": {
                        "type": "array",
                        "maxItems": 256,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["fact_id", "statement", "source", "verbatim_anchors"],
                            "properties": {
                                "fact_id": identifier,
                                "statement": text,
                                "source": {"type": "string", "enum": sorted(_SOURCES)},
                                "verbatim_anchors": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 64,
                                    "uniqueItems": True,
                                    "items": {"type": "string", "maxLength": 1000, "pattern": r".*\S.*"},
                                },
                            },
                        },
                    },
                    "obligations": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 128,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["obligation_id", "statement"],
                            "properties": {
                                "obligation_id": identifier,
                                "statement": text,
                                "fact_refs": optional_refs,
                            },
                        },
                    },
                },
            },
            "method_constraints": {
                "type": "array",
                "maxItems": 32,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "constraint_id",
                        "statement",
                        "verbatim_anchors",
                        "obligation_refs",
                        "acceptance_observation",
                        "falsification_observation",
                    ],
                    "properties": {
                        "constraint_id": identifier,
                        "statement": text,
                        "verbatim_anchors": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 64,
                            "uniqueItems": True,
                            "items": {
                                "type": "string", "maxLength": 1000,
                                "pattern": r".*\S.*",
                            },
                        },
                        "obligation_refs": {**refs, "minItems": 1},
                        "acceptance_observation": text,
                        "falsification_observation": text,
                    },
                },
            },
            "proof_intent": {
                "type": "array",
                "minItems": 1,
                "maxItems": 128,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "proof_id",
                        "obligation_refs",
                        "proof_kind",
                        "acceptance_observation",
                        "falsification_observation",
                    ],
                    "properties": {
                        "proof_id": identifier,
                        "obligation_refs": {**refs, "minItems": 1},
                        "risk_refs": optional_refs,
                        "proof_kind": {"type": "string", "enum": list(PROOF_KINDS)},
                        "acceptance_observation": text,
                        "falsification_observation": text,
                    },
                },
            },
            "solver_design": {
                "type": "object",
                "additionalProperties": False,
                "required": ["mission", "strategy"],
                "properties": {
                    "mission": text,
                    "strategy": text,
                    "priorities": {"type": "array", "maxItems": 16, "items": text},
                    "task_specific_rules": {
                        "type": "array",
                        "maxItems": 32,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["rule_id", "statement"],
                            "properties": {
                                "rule_id": identifier,
                                "statement": text,
                            },
                        },
                    },
                    "failure_response": text,
                    "self_verification_emphasis": {"type": "array", "maxItems": 16, "items": text},
                    "completion_emphasis": {"type": "array", "maxItems": 16, "items": text},
                },
            },
            "verifier_design": {
                "type": "object",
                "additionalProperties": False,
                "required": ["mission", "verification_strategy"],
                "properties": {
                    "mission": text,
                    "verification_strategy": text,
                    "falsification_priorities": {"type": "array", "maxItems": 16, "items": text},
                    "false_positive_risks": {
                        "type": "array",
                        "maxItems": 32,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["risk_id", "statement"],
                            "properties": {"risk_id": identifier, "statement": text, "obligation_refs": optional_refs},
                        },
                    },
                    "completion_emphasis": {"type": "array", "maxItems": 16, "items": text},
                },
            },
            "information_emphasis": {
                "type": "array",
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["topic", "rationale"],
                    "properties": {"topic": text, "rationale": text, "fact_refs": optional_refs, "obligation_refs": optional_refs},
                },
            },
        },
    }

def _provider_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and any(
        isinstance(item, Mapping) and item.get("type") == "null"
        for item in any_of
    ):
        return schema
    return {"anyOf": [schema, {"type": "null"}]}


def _provider_strict_node(value: Any) -> Any:
    if isinstance(value, list):
        return [_provider_strict_node(item) for item in value]
    if not isinstance(value, Mapping):
        return deepcopy(value)

    is_object = value.get("type") == "object"
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"$schema", "$id", "uniqueItems"}:
            continue
        if is_object and key == "properties":
            continue
        result[str(key)] = _provider_strict_node(item)

    if "const" in result:
        constant = result.pop("const")
        result["enum"] = [constant]
        if "type" not in result:
            if isinstance(constant, bool):
                result["type"] = "boolean"
            elif isinstance(constant, int):
                result["type"] = "integer"
            elif isinstance(constant, float):
                result["type"] = "number"
            elif isinstance(constant, str):
                result["type"] = "string"

    if is_object:
        properties = value.get("properties", {})
        if not isinstance(properties, Mapping):
            raise ValueError("object schema properties must be a mapping")
        original_required = set(value.get("required", ()))
        strict_properties: dict[str, Any] = {}
        for name, child in properties.items():
            rendered = _provider_strict_node(child)
            if str(name) not in original_required:
                rendered = _provider_nullable(rendered)
            strict_properties[str(name)] = rendered
        result["properties"] = strict_properties
        result["required"] = list(strict_properties)
        result["additionalProperties"] = False
    return result


def architect_v2_provider_schema() -> dict[str, Any]:
    """Return the Azure/OpenAI strict provider shape for canonical v2 output.

    The canonical JSON schema remains aligned with sparse parser semantics.
    The provider schema requires every object property and represents parser-
    optional properties as nullable, matching the Responses strict-schema
    contract without changing Architect semantic authority.
    """

    rendered = _provider_strict_node(architect_v2_json_schema())
    if not isinstance(rendered, dict):  # pragma: no cover - construction invariant
        raise TypeError("Architect v2 provider schema must be an object")
    properties = rendered.get("properties", {})
    if not isinstance(properties, Mapping):  # pragma: no cover - construction invariant
        raise TypeError("Architect v2 provider schema properties must be an object")
    order = (
        "schema_version",
        "task_contract",
        "method_constraints",
        "verifier_design",
        "proof_intent",
        "solver_design",
        "information_emphasis",
    )
    if set(properties) != set(order):  # pragma: no cover - construction invariant
        raise ValueError("Architect v2 provider schema top-level fields changed")
    rendered["properties"] = {name: properties[name] for name in order}
    rendered["required"] = list(order)
    return rendered

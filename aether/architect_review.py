"""Strict model-led review contract for Runtime Workbench Architect drafts."""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping


_REVIEW_STATUS = {"pass", "needs_revision"}
_CANDIDATE_STATUS = {
    "present_exact", "present_equivalent", "missing", "incorrect", "duplicated"
}
_FINDING_CATEGORY = {
    "contract_omission", "binding_error", "invented_constraint", "duplication",
    "clause_coverage", "proof_route", "solver_operationalization",
    "verifier_operationalization", "cross_section_consistency", "other",
}
_FINDING_SEVERITY = {"critical", "major", "minor"}


ARCHITECT_REVIEWER_SYSTEM_PROMPT = """You are an independent Runtime Workbench Architect reviewer. Audit an untrusted candidate workbench against only the original visible Architect request and runtime contract. Do not produce a replacement configuration and do not infer hidden tests or grader behaviour. Return one strict structured review report.

Perform an exhaustive, evidence-based review:
1. Build an inventory of every atomic exact named path, destination directory, artifact, dependency, version, service, operation, message, field, class, state, port, format, cardinality, and other final-state fact stated by the visible task. For inventory scoring, a final-state fact is present only when visible_contract explicitly represents it. Mentions in clauses, Solver guidance, Verifier guidance, or free prose do not substitute for a missing visible_contract row. Equivalent graph structure is allowed, but the exact fact itself must remain explicit in the ledger.
2. Check each visible_contract row for exact literal identity, immediate ownership, and exact requirement. Owner and requirement are independent. Categories belong in meaning. Detect omissions, duplicates, lookalikes, invented constraints, and facts hidden only in prose.
3. Check that every independently judgeable final-state obligation has one matched clause and proof route with a unique clause_id.
4. For generated artifacts, reject existence, filenames, importability, metadata, directory listing, or shape as sufficient semantic proof. Require independent comparison of the current generated public interface, descriptors, signatures, or equivalent semantics against the current source contract.
5. For running systems, separate liveness from behaviour. Require a fresh independent public-interface probe that exercises the visible task behaviour and validates returned state or output. Process or port evidence may support liveness but cannot replace behaviour.
6. Check that Solver guidance, Verifier guidance, evidence classes, routes, falsification checks, and stop conditions operationalize the same completion boundary.
7. Report every concrete defect with its task basis, exact candidate observation, why it can cause false success or failure, and the required semantic correction. Do not prescribe hidden commands or copy a benchmark-specific answer.
8. If no defect exists, return pass. Otherwise return needs_revision. Do not omit a defect because another section partially mentions it."""


ARCHITECT_FINALIZER_APPENDIX = """You are performing one bounded Architect finalization pass over an untrusted candidate configuration and an independent model-authored review.
Return one complete replacement configuration in the same strict schema. Do not return a patch, critique, explanation, or references to the candidate or review.
Re-derive the workbench from the original visible request and runtime manual. Treat both the candidate and review as fallible working material, not authorities.
Before answering, audit the replacement for all of these generic obligations:
1. Completeness: inventory every atomic exact named path, destination directory, artifact, dependency, version, service, operation, message, field, class, state, port, working directory, format, cardinality, and other final-state fact stated by the visible task. Represent every material fact exactly once in visible_contract. A mention in clauses or prompts cannot substitute for a missing visible_contract row.
2. Binding: owner and requirement are independent. Use owner only for an actual immediate semantic owner. Use requirement only for an exact task-stated type, version, format, cardinality, or equivalent constraint. Categories belong in meaning.
3. Review disposition: address every major or critical reviewer finding, preserve reviewer-identified strengths, and independently check for defects the reviewer may have missed. Do not blindly copy a reviewer correction that conflicts with the original request.
4. Clause coverage: create one independently judgeable clause for every material final-state obligation, including produced artifacts, running state, and live behavior. Matched clause and route IDs must be complete and unique.
5. Generated artifacts: when outputs are generated from a source contract, existence, filenames, importability, metadata, directory listing, or shape alone are insufficient. Require an independent current public-interface, descriptor, signature, or equivalent semantic comparison against the current source contract.
6. Running systems: process existence, port binding, logs, or liveness alone are insufficient. Require a fresh independent public-interface behavioral probe that exercises the task-stated behavior and validates returned state or output. Put this obligation in clause_coverage, verifier_strategy, Solver guidance, and Verifier guidance.
7. Cross-section consistency: the exact contract, clauses, proof routes, Solver instructions, Verifier evidence requirements, falsification checks, and stop conditions must describe the same completion boundary.
8. Final audit: reject proxy evidence, same-method self-confirmation, unobserved assumptions, duplicate selectors, and any completion route that could pass while a visible task requirement is still false.
Return only the complete JSON object."""


def _closed_object(properties: Mapping[str, Any], required: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required),
    }


def architect_review_schema() -> dict[str, Any]:
    nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    inventory_item = _closed_object(
        {
            "fact": {"type": "string"},
            "owner": nullable_string,
            "requirement": nullable_string,
            "task_basis": {"type": "string"},
            "candidate_status": {"type": "string", "enum": sorted(_CANDIDATE_STATUS)},
            "candidate_observation": {"type": "string"},
        },
        ("fact", "owner", "requirement", "task_basis", "candidate_status", "candidate_observation"),
    )
    finding_item = _closed_object(
        {
            "finding_id": {"type": "string"},
            "category": {"type": "string", "enum": sorted(_FINDING_CATEGORY)},
            "severity": {"type": "string", "enum": sorted(_FINDING_SEVERITY)},
            "task_basis": {"type": "string"},
            "candidate_observation": {"type": "string"},
            "risk": {"type": "string"},
            "required_correction": {"type": "string"},
        },
        (
            "finding_id", "category", "severity", "task_basis",
            "candidate_observation", "risk", "required_correction",
        ),
    )
    return _closed_object(
        {
            "review_status": {"type": "string", "enum": sorted(_REVIEW_STATUS)},
            "inventory": {"type": "array", "items": inventory_item},
            "findings": {"type": "array", "items": finding_item},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "finalizer_directives": {"type": "array", "items": {"type": "string"}},
        },
        ("review_status", "inventory", "findings", "strengths", "finalizer_directives"),
    )


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(f"{label} fields mismatch: expected={sorted(expected)} actual={sorted(actual)}")


def _require_string(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def parse_architect_review_report(raw: str) -> dict[str, Any]:
    """Parse one closed review object without semantic repair or first-object extraction."""
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise ValueError(f"architect review is not one strict JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("architect review must be a JSON object")
    _require_exact_keys(
        value,
        {"review_status", "inventory", "findings", "strengths", "finalizer_directives"},
        "architect review",
    )
    status = _require_string(value["review_status"], "review_status")
    if status not in _REVIEW_STATUS:
        raise ValueError(f"invalid review_status: {status}")
    for key in ("inventory", "findings", "strengths", "finalizer_directives"):
        if not isinstance(value[key], list):
            raise ValueError(f"{key} must be an array")
    inventory_keys = {
        "fact", "owner", "requirement", "task_basis", "candidate_status", "candidate_observation"
    }
    for index, item in enumerate(value["inventory"]):
        if not isinstance(item, dict):
            raise ValueError(f"inventory[{index}] must be an object")
        _require_exact_keys(item, inventory_keys, f"inventory[{index}]")
        _require_string(item["fact"], f"inventory[{index}].fact")
        _require_string(item["owner"], f"inventory[{index}].owner", nullable=True)
        _require_string(item["requirement"], f"inventory[{index}].requirement", nullable=True)
        _require_string(item["task_basis"], f"inventory[{index}].task_basis")
        candidate_status = _require_string(item["candidate_status"], f"inventory[{index}].candidate_status")
        if candidate_status not in _CANDIDATE_STATUS:
            raise ValueError(f"invalid inventory candidate_status: {candidate_status}")
        _require_string(item["candidate_observation"], f"inventory[{index}].candidate_observation")
    finding_keys = {
        "finding_id", "category", "severity", "task_basis", "candidate_observation",
        "risk", "required_correction",
    }
    finding_ids: list[str] = []
    for index, item in enumerate(value["findings"]):
        if not isinstance(item, dict):
            raise ValueError(f"findings[{index}] must be an object")
        _require_exact_keys(item, finding_keys, f"findings[{index}]")
        finding_id = _require_string(item["finding_id"], f"findings[{index}].finding_id")
        finding_ids.append(str(finding_id))
        category = _require_string(item["category"], f"findings[{index}].category")
        severity = _require_string(item["severity"], f"findings[{index}].severity")
        if category not in _FINDING_CATEGORY:
            raise ValueError(f"invalid finding category: {category}")
        if severity not in _FINDING_SEVERITY:
            raise ValueError(f"invalid finding severity: {severity}")
        for key in ("task_basis", "candidate_observation", "risk", "required_correction"):
            _require_string(item[key], f"findings[{index}].{key}")
    if len(finding_ids) != len(set(finding_ids)):
        raise ValueError("finding_id values must be unique")
    for key in ("strengths", "finalizer_directives"):
        for index, item in enumerate(value[key]):
            _require_string(item, f"{key}[{index}]")
    if status == "pass" and value["findings"]:
        raise ValueError("pass review cannot contain findings")
    if status == "needs_revision" and not value["findings"]:
        raise ValueError("needs_revision review must contain at least one finding")
    return copy.deepcopy(value)


def build_architect_review_packet(
    request: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "architect_request": dict(request),
        "candidate_config": copy.deepcopy(dict(candidate)),
        "instruction": "Audit the candidate and return the complete reviewer report.",
    }


def build_architect_finalizer_packet(
    request: Mapping[str, Any],
    candidate: Mapping[str, Any],
    review: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "architect_request": dict(request),
        "candidate_config": copy.deepcopy(dict(candidate)),
        "independent_review": copy.deepcopy(dict(review)),
        "instruction": "Produce the complete corrected replacement configuration.",
    }

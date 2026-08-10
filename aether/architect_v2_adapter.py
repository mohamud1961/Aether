"""Dispatch-inactive Architect v2 adapter for the existing runtime.

The adapter applies model-authored task semantics and role design to a
kernel-owned neutral RuntimeConfigIR. It creates no second runtime and is not
reachable from provider dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from hashlib import sha256
from typing import Any, Mapping

from .architect_v2_contract import (
    ArchitectV2CompatibilityError,
    ArchitectV2Contract,
    project_architect_v2_shadow,
    validate_architect_v2,
)
from .proof_contract import PROOF_REGISTRY_DIGEST, PROOF_REGISTRY_VERSION
from .runtime_ir import EnvMap, RuntimeConfigIR
from .task_contract import MethodConstraint, TaskClause, TaskContract, TaskFact


MAX_SOLVER_ROLE_PROMPT_CHARS = 12_000
MAX_VERIFIER_ROLE_PROMPT_CHARS = 12_000


def _digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


_MODEL_OWNED_V1_FIELDS = (
    "architect_summary",
    "solver_identity_prompt",
    "verifier_identity_prompt",
    "visible_contract",
    "inspection_plan",
    "proof_plan",
    "success_definition",
    "evidence_requirements",
    "false_positive_risks",
    "minimum_completion_evidence",
    "re_derivable_claims",
    "semantic_clause_coverage",
    "semantic_verifier_checks",
    "semantic_false_positive_traps",
    "proof_requirements",
    "task_contract",
    "architect_v2_contract_identity",
    "architect_v2_realization",
)


@dataclass(frozen=True)
class ArchitectV2RuntimeAdapterResult:
    contract: ArchitectV2Contract
    task_contract: TaskContract
    runtime_ir: RuntimeConfigIR
    realization_manifest: Mapping[str, Any]
    status: str = "shadow_only"


def _require_neutral_baseline(baseline: RuntimeConfigIR) -> None:
    populated = []
    for name in _MODEL_OWNED_V1_FIELDS:
        value = getattr(baseline, name)
        if value not in (None, "", (), [], {}):
            populated.append(name)
    if populated:
        raise ArchitectV2CompatibilityError(
            "Architect v2 requires a kernel-owned semantic-neutral baseline; populated V1 fields: "
            + ", ".join(populated)
        )


def _task_contract(contract: ArchitectV2Contract, envmap: EnvMap) -> TaskContract:
    payload = contract.payload["task_contract"]
    facts = tuple(TaskFact(
        fact_id=str(row["fact_id"]),
        statement=str(row["statement"]),
        source=str(row["source"]),
        verbatim_anchors=tuple(str(item) for item in row.get("verbatim_anchors", ())),
    ) for row in payload["exact_facts"])
    facts_by_id = {fact.fact_id: fact for fact in facts}
    clauses = []
    for row in payload["obligations"]:
        refs = tuple(str(item) for item in row.get("fact_refs", ()))
        atoms = tuple(dict.fromkeys(
            anchor for ref in refs for anchor in facts_by_id[ref].verbatim_anchors
        ))
        clauses.append(TaskClause(
            clause_id=str(row["obligation_id"]),
            text=str(row["statement"]),
            exact_atoms=atoms,
            fact_refs=refs,
        ))
    method_constraints = tuple(
        MethodConstraint(
            constraint_id=str(row["constraint_id"]),
            statement=str(row["statement"]),
            obligation_refs=tuple(str(item) for item in row.get("obligation_refs", ())),
            verbatim_anchors=tuple(
                str(item) for item in row.get("verbatim_anchors", ())
            ),
            acceptance_observation=str(row["acceptance_observation"]),
            falsification_observation=str(row["falsification_observation"]),
        )
        for row in contract.payload.get("method_constraints", ())
    )
    return TaskContract.create(
        envmap.task_prompt,
        clauses,
        facts=facts,
        method_constraints=method_constraints,
        schema_version="task_contract.v2",
    )


def _field_owner(path: str) -> str:
    if path == "schema_version":
        return "architect_contract_identity"
    if path.startswith("task_contract."):
        return "canonical_task_contract"
    if path.startswith("method_constraints"):
        return "structured_method_constraint"
    if path.startswith("proof_intent"):
        return "compiled_proof_requirement"
    if path.startswith("solver_design."):
        return "solver_identity_prompt"
    if path.startswith("verifier_design.false_positive_risks"):
        return "structured_false_positive_risks"
    if path.startswith("verifier_design."):
        return "verifier_identity_prompt"
    if path.startswith("information_emphasis"):
        return "solver_advisory_prompt"
    raise ArchitectV2CompatibilityError(f"Architect v2 field has no runtime owner: {path}")


def _field_dispositions(payload: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    """Record exactly one existing-runtime owner for every submitted leaf field."""
    rows: list[dict[str, str]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            if not value:
                rows.append({"path": path, "owner": _field_owner(path)})
                return
            for key in sorted(value, key=str):
                child = f"{path}.{key}" if path else str(key)
                walk(value[key], child)
            return
        if isinstance(value, list):
            if not value:
                rows.append({"path": path, "owner": _field_owner(path)})
                return
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
            return
        rows.append({"path": path, "owner": _field_owner(path)})

    walk(payload, "")
    paths = [row["path"] for row in rows]
    if len(paths) != len(set(paths)):
        raise ArchitectV2CompatibilityError("Architect v2 realization produced duplicate field dispositions")
    return tuple(rows)


def adapt_architect_v2_to_runtime(
    payload_or_contract: Mapping[str, Any] | ArchitectV2Contract,
    *,
    baseline: RuntimeConfigIR,
    envmap: EnvMap,
) -> ArchitectV2RuntimeAdapterResult:
    """Realise v2 into existing owners without enabling production dispatch."""
    _require_neutral_baseline(baseline)
    contract = (
        payload_or_contract
        if isinstance(payload_or_contract, ArchitectV2Contract)
        else validate_architect_v2(payload_or_contract)
    )
    projection = project_architect_v2_shadow(contract)
    if len(projection.solver_prompt) > MAX_SOLVER_ROLE_PROMPT_CHARS:
        raise ArchitectV2CompatibilityError(
            f"Architect v2 Solver role prompt exceeds {MAX_SOLVER_ROLE_PROMPT_CHARS} characters"
        )
    if len(projection.verifier_prompt) > MAX_VERIFIER_ROLE_PROMPT_CHARS:
        raise ArchitectV2CompatibilityError(
            f"Architect v2 Verifier role prompt exceeds {MAX_VERIFIER_ROLE_PROMPT_CHARS} characters"
        )
    task_contract = _task_contract(contract, envmap)
    verifier_design = contract.payload["verifier_design"]
    risk_statements = tuple(
        str(row["statement"])
        for row in verifier_design.get("false_positive_risks", ())
    )
    manifest = {
        "schema_version": "architect_v2_realization.v1",
        "status": "shadow_only",
        "architect_contract_identity": contract.contract_identity,
        "task_contract_identity": task_contract.contract_identity,
        "task_contract_sha256": task_contract.contract_identity,
        "solver_prompt_sha256": _digest_text(projection.solver_prompt),
        "solver_prompt_chars": len(projection.solver_prompt),
        "solver_prompt_max_chars": MAX_SOLVER_ROLE_PROMPT_CHARS,
        "verifier_prompt_sha256": _digest_text(projection.verifier_prompt),
        "verifier_prompt_chars": len(projection.verifier_prompt),
        "verifier_prompt_max_chars": MAX_VERIFIER_ROLE_PROMPT_CHARS,
        "structured_method_constraint_count": len(task_contract.method_constraints),
        "structured_method_constraints_sha256": _digest_text(
            json.dumps(
                [item.as_payload() for item in task_contract.method_constraints],
                sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            )
        ),
        "structured_false_positive_risk_count": len(risk_statements),
        "structured_false_positive_risks_sha256": _digest_text(
            "\n".join(risk_statements)
        ),
        "proof_requirements_identity": projection.proof_seam.requirements_identity,
        "proof_registry_version": PROOF_REGISTRY_VERSION,
        "proof_registry_digest": PROOF_REGISTRY_DIGEST,
        "field_dispositions": list(_field_dispositions(contract.payload)),
        "v1_visible_contract": "intentionally_unused",
        "production_dispatch": "blocked",
    }
    runtime_ir = replace(
        baseline,
        solver_identity_prompt=projection.solver_prompt,
        verifier_identity_prompt=projection.verifier_prompt,
        false_positive_risks=risk_statements,
        proof_requirements=projection.proof_seam.requirements,
        task_contract=task_contract,
        architect_v2_contract_identity=contract.contract_identity,
        architect_v2_realization=manifest,
    )
    return ArchitectV2RuntimeAdapterResult(
        contract=contract,
        task_contract=task_contract,
        runtime_ir=runtime_ir,
        realization_manifest=manifest,
    )

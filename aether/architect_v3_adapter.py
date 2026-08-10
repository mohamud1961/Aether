"""Mechanical production realization of a validated Architect v3 contract.

This module does not infer task semantics. It projects model-authored outcomes,
explicit constraints, proof facets, and Solver pilot briefing into the existing
RuntimeConfigIR, TaskContract, Solver, and neutral Verifier surfaces.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .architect_v3_contract import ArchitectV3Contract, project_architect_v3_runtime
from .runtime_ir import (
    BootstrapPolicy,
    CompletionPolicy,
    EnvMap,
    EvalIndex,
    HelperToolPolicy,
    ReconfigurePolicy,
    RuntimeConfigIR,
)
from .task_contract import MethodConstraint, TaskClause, TaskContract


def _parameter_atoms(owner: Mapping[str, Any]) -> tuple[str, ...]:
    """Return unique exact source spans while preserving model-authored order.

    Several owner-local values may legitimately share one coupled source span,
    such as host and port grounded by `127.0.0.1:8123`. TaskContract atoms are
    set-like anchors, so duplicate spans are mechanically deduplicated without
    changing or interpreting their task meaning.
    """
    return tuple(dict.fromkeys(
        str(row.get("source_text", "")).strip()
        for row in owner.get("parameters", ())
        if str(row.get("source_text", "")).strip()
    ))


def _render_owner_text(owner: Mapping[str, Any]) -> str:
    description = str(owner.get("description", "")).strip()
    parameters = tuple(owner.get("parameters", ()))
    if not parameters:
        return description
    rendered = ", ".join(
        f"{row['parameter_id']}={row['value']!r}"
        for row in parameters
    )
    return f"{description} [parameters: {rendered}]"


def architect_v3_task_contract(contract: ArchitectV3Contract, task_text: str) -> TaskContract:
    """Project V3 owners into TaskContract without inventing global facts."""
    payload = contract.payload
    clauses = tuple(
        TaskClause(
            clause_id=str(row["outcome_id"]),
            text=_render_owner_text(row),
            exact_atoms=_parameter_atoms(row),
        )
        for row in payload["outcomes"]
    )
    proofs_by_constraint = {
        str(row["target_id"]): row
        for row in payload["proof_facets"]
        if str(row.get("target_type")) == "constraint"
    }
    method_constraints = tuple(
        MethodConstraint(
            constraint_id=str(row["constraint_id"]),
            statement=_render_owner_text(row),
            obligation_refs=tuple(str(item) for item in row["applies_to"]),
            constraint_kind=str(row["kind"]),
            fact_refs=(),
            verbatim_anchors=_parameter_atoms(row),
            acceptance_observation=str(
                proofs_by_constraint[str(row["constraint_id"])]["acceptance_observation"]
            ),
            falsification_observation=str(
                proofs_by_constraint[str(row["constraint_id"])]["falsification_observation"]
            ),
        )
        for row in payload["constraints"]
    )
    return TaskContract.create(
        task_text,
        clauses,
        facts=(),
        method_constraints=method_constraints,
        schema_version="architect_v3",
    )


def architect_v3_runtime_ir(
    contract: ArchitectV3Contract,
    envmap: EnvMap,
    eval_index: EvalIndex,
) -> RuntimeConfigIR:
    """Mechanically realize one validated V3 contract in the certified runtime."""
    projection = project_architect_v3_runtime(contract)
    payload = contract.payload
    task_contract = architect_v3_task_contract(contract, envmap.task_prompt)
    available_capabilities = tuple(
        capability_id
        for capability_id, descriptor in sorted(envmap.capabilities.items())
        if descriptor.available
    )
    if not available_capabilities:
        raise ValueError("Architect v3 runtime requires at least one available capability")

    visible_contract = tuple(
        {"owner_type": "outcome", **dict(row)}
        for row in payload["outcomes"]
    ) + tuple(
        {"owner_type": "constraint", **dict(row)}
        for row in payload["constraints"]
    )
    proof_rows = tuple(dict(row) for row in payload["proof_facets"])
    authoritative_checks = tuple(
        check.check_id for check in eval_index.authoritative_checks()
    )
    capability_set = set(available_capabilities)
    helper_supported = {"filesystem", "shell"}.issubset(capability_set)
    bootstrap_supported = "shell" in capability_set

    realization = {
        "schema_version": "architect_v3_runtime_realization.v1",
        "contract_identity": contract.contract_identity,
        "outcome_ids": list(contract.outcome_ids),
        "constraint_ids": list(contract.constraint_ids),
        "proof_ids": list(contract.proof_ids),
        "parameter_ids": list(contract.parameter_ids),
        "proof_requirements_identity": projection.requirements_identity,
        "proof_targets": [
            {"proof_id": proof_id, "target_type": target_type, "target_id": target_id}
            for proof_id, target_type, target_id in projection.proof_targets
        ],
        "task_contract_identity": task_contract.contract_identity,
        "tool_selection_owner": "kernel_stable_core",
        "model_correction_calls": 0,
        "reviewer_calls": 0,
        "finalizer_calls": 0,
    }
    success_definition = json.dumps(
        {
            "outcomes": payload["outcomes"],
            "explicit_constraints": payload["constraints"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return RuntimeConfigIR(
        architect_summary=(
            "Architect V3 task-specific semantic and cognitive contract "
            + contract.contract_identity
        ),
        solver_identity_prompt=projection.solver_prompt,
        selected_capabilities=available_capabilities,
        visible_contract=visible_contract,
        helper_tool_policy=HelperToolPolicy(
            allow_creation=helper_supported,
            require_smoke_test=helper_supported,
            trust_for_completion=False,
        ),
        bootstrap_policy=BootstrapPolicy(
            allow_acquisition=bootstrap_supported,
        ),
        completion_policy=CompletionPolicy(
            require_authoritative_check=bool(authoritative_checks),
            allow_evidence_fallback=True,
            require_all_obligations=True,
            require_recent_progress=True,
            require_clean_integrity=True,
        ),
        reconfigure_policy=ReconfigurePolicy(
            max_reconfigurations=0,
            allowed_owners=(),
            typed_triggers=(),
        ),
        check_plan=authoritative_checks,
        advisory_notes=(
            "tool_policy_mode=stable_core",
            "architect_mode=architect_v3",
            "architect_model_correction_calls=0",
        ),
        success_definition=success_definition,
        verifier_identity_prompt=projection.verifier_prompt,
        evidence_requirements=tuple(
            str(row["acceptance_observation"]) for row in proof_rows
        ),
        false_positive_risks=tuple(
            str(row["falsification_observation"]) for row in proof_rows
        ),
        minimum_completion_evidence=tuple(
            f"{row['proof_id']}:{row['proof_kind']}" for row in proof_rows
        ),
        proof_requirements=projection.requirements,
        task_contract=task_contract,
        architect_v3_contract_identity=contract.contract_identity,
        architect_v3_realization=realization,
    )


@dataclass(frozen=True)
class ArchitectV3RuntimeResult:
    runtime_ir: RuntimeConfigIR | None
    contract: ArchitectV3Contract | None
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return self.runtime_ir is not None and self.contract is not None and not self.errors

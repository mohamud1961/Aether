"""Mechanical construction of Aether's single production PCR runtime.

The runtime is derived only from raw task custody and observed environment
capabilities.  No configuration model, task-semantic classifier, Architect,
or alternate cognition path participates in construction.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .compiler_prefix import pcr_model_environment_probe, pcr_model_environment_probe_compact, protocol_card_sections
from .pcr_task_contract import raw_task_contract
from .runtime_ir import (
    ACTION_SCHEMA,
    FIXED_KERNEL_TOOL_SURFACE,
    BootstrapPolicy,
    CapabilityDescriptor,
    CompiledRuntime,
    CompletionPolicy,
    ContextPolicy,
    EnvMap,
    EvalIndex,
    HelperToolPolicy,
    ModelVerifierPolicy,
    ObjectiveGraph,
    ProcessPolicy,
    RefusalPolicy,
    stable_json,
)


PRIMARY_AGENT_CONSTITUTION = """You are Aether's persistent Primary Agent.

Own the task from first observation until independently verified completion.

Treat the raw task and observed reality as authoritative.

Use computation to understand, modify and verify the environment.

The Kernel executes actions and preserves reality. It does not choose your strategy.

Completion must be supported by observed evidence that the task requirements are met."""


PCR_VERIFIER_CONSTITUTION = """You are Aether's independent PCR Verifier.

Judge the exact Primary Agent completion claim against current observed state and the cited same-run evidence.

Do not trust a claim, plan, summary, model-authored observation, bookkeeping receipt, or helper output merely because it exists.

Use read-only inspections when the available evidence does not establish the claim. Distinguish task-state evidence from metadata and proxy evidence.

Return completed only when the current evidence establishes the raw task. Otherwise return the precise incomplete, uncertain, or tooling-blocked verdict supported by reality."""


@dataclass(frozen=True)
class RuntimeState:
    """Traceable mechanical runtime identity containing no semantic strategy."""

    schema_version: str
    selected_capabilities: tuple[str, ...]
    task_contract_identity: str
    environment_digest: str
    configuration_model_calls: int = 0
    model_authored_reconfiguration: bool = False


@dataclass(frozen=True)
class ResolvedPCRRuntime:
    runtime_state: RuntimeState
    compiled: CompiledRuntime | None
    objective_graph: ObjectiveGraph
    eval_index: EvalIndex
    config_invalid_blockers: tuple[str, ...] = ()

    @property
    def runtime_ir(self) -> RuntimeState:
        """Temporary trace compatibility alias; RuntimeState is authoritative."""
        return self.runtime_state


def _selected_capabilities(envmap: EnvMap) -> tuple[CapabilityDescriptor, ...]:
    return tuple(
        descriptor
        for _capability_id, descriptor in sorted(envmap.capabilities.items())
        if descriptor.available
    )


def _fixed_action_schema() -> tuple[tuple[str, tuple[str, ...]], ...]:
    allowed = set(FIXED_KERNEL_TOOL_SURFACE)
    return tuple((name, args) for name, args in ACTION_SCHEMA if name in allowed)


def _refusal_boundary(policy: RefusalPolicy) -> str:
    if not policy.allowed_local_categories:
        return "No local-only external-grading allowance compiled."
    categories = ", ".join(sorted(policy.allowed_local_categories))
    return (
        f"Local-only external-grading allowance compiled for categories: {categories}. "
        "Allowed scope: workspace files, local processes, and localhost services only. "
        "External targets remain forbidden."
    )


def _state(envmap: EnvMap, capability_ids: tuple[str, ...], task_contract_identity: str) -> RuntimeState:
    return RuntimeState(
        schema_version="aether.pcr_runtime.v1",
        selected_capabilities=capability_ids,
        task_contract_identity=task_contract_identity,
        environment_digest=envmap.digest(),
    )


SOLVER_CONTEXT_MODES = frozenset({"full", "compact"})


def build_pcr_runtime(envmap: EnvMap, *, solver_context_mode: str = "full") -> ResolvedPCRRuntime:
    """Build the one production runtime from raw task + observed capabilities."""
    selected = _selected_capabilities(envmap)
    capability_ids = tuple(cap.capability_id for cap in selected)
    if not selected:
        blockers = ("runtime_compile:ValueError:PCR requires at least one observed available capability",)
        return ResolvedPCRRuntime(_state(envmap, (), ""), None, ObjectiveGraph(), EvalIndex(), blockers)

    capability_set = set(capability_ids)
    helper_supported = {"filesystem", "shell"}.issubset(capability_set)
    bootstrap_supported = "shell" in capability_set
    task_contract = raw_task_contract(envmap.task_prompt)

    # No task-semantic ObjectiveGraph/EvalIndex is synthesized in production.
    # The raw task remains the sole semantic authority.
    objective = ObjectiveGraph()
    checks = EvalIndex()
    context_policy = ContextPolicy()
    process_policy = ProcessPolicy()
    context_mode = str(solver_context_mode or "full").strip().lower()
    if context_mode not in SOLVER_CONTEXT_MODES:
        raise ValueError(f"unsupported Solver context mode: {solver_context_mode}")

    helper_policy = HelperToolPolicy(
        allow_creation=helper_supported,
        require_smoke_test=helper_supported,
        trust_for_completion=False,
    )
    bootstrap_policy = BootstrapPolicy(allow_acquisition=bootstrap_supported)
    completion_policy = CompletionPolicy(
        require_authoritative_check=False,
        allow_evidence_fallback=True,
        require_all_obligations=True,
        require_recent_progress=False,
        require_clean_integrity=True,
    )
    verifier_policy = ModelVerifierPolicy(enabled=True, runs_on=("solver_submit",))
    refusal_policy = RefusalPolicy()
    action_schema = _fixed_action_schema()
    environment_probe = dict((envmap.task_metadata or {}).get("environment_probe", {}) or {})
    model_environment_probe = (
        pcr_model_environment_probe(environment_probe)
        if context_mode == "full"
        else pcr_model_environment_probe_compact(environment_probe)
    )

    config_realization: dict[str, Any] = {
        "schema_version": "aether.pcr_runtime_realization.v1",
        "runtime_path": "pcr_v0",
        "configuration_model_calls": 0,
        "model_authored_reconfiguration": False,
        "task_semantic_compiler": False,
        "raw_task_semantic_authority": True,
        "tool_policy_mode": "stable_core",
        "solver_context_mode": context_mode,
        "capabilities_realized": list(capability_ids),
        "tools_visible_to_solver": sorted(name for name, _args in action_schema),
        "environment_probe": environment_probe,
        "environment_probe_available": bool(environment_probe),
        "model_verifier_policy": asdict(verifier_policy),
        "verification_authority": {
            "luna": "final_semantic_authority",
            "model_verifier": "advisory_independent_review",
            "mechanical_completion_gate": "runtime_reality_only",
            "official_grader": "external_official_grader",
        },
        "task_contract_identity": task_contract.contract_identity,
        "compiled_evidence_requirements": [],
    }

    # This is the exact S1b Thin model-visible prefix.  Keeping it stable makes
    # S2 a structural authority change rather than a cognition treatment.
    prefix_sections: list[tuple[str, str]] = [
        *protocol_card_sections(),
        ("task_prompt", envmap.task_prompt),
        ("envmap", stable_json(envmap.compact_summary() | {"env_digest": envmap.digest()})),
    ]
    if context_mode == "full":
        prefix_sections.extend((
            ("envmap_file_tree", envmap.file_tree or ""),
            ("envmap_file_map_summary", stable_json(dict(envmap.file_map_summary))),
        ))
    else:
        prefix_sections.append((
            "environment_discovery",
            "Detailed file, command, and package inventories are not preloaded. "
            "Use the unchanged native file/shell tools to inspect what you need; "
            "Aether retains the full environment probe for audit custody.",
        ))
    prefix_sections.extend((
        ("solver_identity", PRIMARY_AGENT_CONSTITUTION),
        ("environment_probe", stable_json(model_environment_probe)),
        ("refusal_boundary", _refusal_boundary(refusal_policy)),
    ))

    compiled = CompiledRuntime(
        task_prompt=envmap.task_prompt,
        env_digest=envmap.digest(),
        objective_graph=objective,
        eval_index=checks,
        selected_capabilities=selected,
        stable_prefix_sections=tuple(prefix_sections),
        context_policy=context_policy,
        process_policy=process_policy,
        helper_tool_policy=helper_policy,
        bootstrap_policy=bootstrap_policy,
        completion_policy=completion_policy,
        model_verifier_policy=verifier_policy,
        refusal_policy=refusal_policy,
        enforced_monitors=("no_progress", "integrity_guard"),
        check_plan_ids=(),
        forbidden_paths=(),
        action_schema=action_schema,
        solver_identity_prompt=PRIMARY_AGENT_CONSTITUTION,
        success_definition="",
        local_verification_limits=(),
        verifier_identity_prompt=PCR_VERIFIER_CONSTITUTION,
        evidence_requirements=(),
        false_positive_risks=(),
        minimum_completion_evidence=(),
        re_derivable_claims=(),
        proof_contract=(),
        config_realization=config_realization,
        proof_requirements=(),
        proof_requirements_identity="",
        task_contract=task_contract,
        task_contract_identity=task_contract.contract_identity,
    )
    return ResolvedPCRRuntime(
        _state(envmap, capability_ids, task_contract.contract_identity),
        compiled,
        objective,
        checks,
    )


__all__ = [
    "PCR_VERIFIER_CONSTITUTION",
    "PRIMARY_AGENT_CONSTITUTION",
    "ResolvedPCRRuntime",
    "RuntimeState",
    "build_pcr_runtime",
]

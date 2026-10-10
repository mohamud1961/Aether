"""Mechanical construction of Aether's single production PERSISTENT runtime.

The runtime is derived only from raw task custody and observed environment
capabilities.  No configuration model, task-semantic classifier, Architect,
or alternate cognition path participates in construction.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .env_lean import (
    CONTROL as ENV_CONTROL, LEAN_V1 as ENV_LEAN_V1, LEAN_V2 as ENV_LEAN_V2,
    SUPPORTED_ENV_MODES, lean_environment_probe, lean_v2_environment_probe, lean_file_map,
)
from .compiler_prefix import (
    persistent_model_environment_probe,
    persistent_model_environment_probe_compact,
    persistent_model_environment_probe_compact_guided,
    persistent_model_environment_probe_compact_scoped,
    protocol_card_sections,
)
from .persistent_task_contract import raw_task_contract, source_linked_task_clauses
from .persistent_hosted_tool_search import (
    CONTROL as SOLVER_HOSTED_TOOL_SEARCH_CONTROL,
    HOSTED_V1 as SOLVER_HOSTED_TOOL_SEARCH_V1,
    SUPPORTED_MODES as SOLVER_HOSTED_TOOL_SEARCH_MODES,
)
from .verifier_activation_continuity import (
    FRESH_CONTROL as VERIFIER_ACTIVATION_CONTINUITY_CONTROL,
    PREVIOUS_RESPONSE_V1 as VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1,
    SUPPORTED_MODES as VERIFIER_ACTIVATION_CONTINUITY_MODES,
)
from .edit_file_tool import EDIT_FILE_ACTION_SCHEMA_ENTRY
from .long_command_mode import LONG_COMMAND_BACKGROUND_V1, selected_long_command_mode
from .persistent_provider_protocol import persistent_finish_intent_exposed, persistent_persistent_shell
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

Treat every task-mandated method, interface boundary, and stated unknown as a global invariant, not merely an outcome hint. If the task says to use a particular query/API/interface, or says some internal value is unknown, do not inspect or use implementation internals, hidden ground truth, private attributes, source revelations, or direct validation against that unknown even for debugging. Verification must use evidence admissible under the same task-defined method.

Use computation to understand, modify and verify the environment.

The Kernel executes actions and preserves reality. It does not choose your strategy.

Completion must be supported by observed evidence that the task requirements are met."""


PERSISTENT_VERIFIER_CONSTITUTION = """You are Aether's independent PERSISTENT Verifier.

Judge the exact completion claim against current observed state and cited same-run evidence.

Method integrity is correctness. If the task mandates an interface/method or says something is unknown, reject completion when actions bypass it, inspect hidden/internal ground truth, or use inadmissible validation. Inspect history if unsure.

Distrust claims, summaries, bookkeeping and helper output unless grounded in observed task state.

Inspect read-only when evidence is insufficient. Return completed only when admissible evidence establishes the raw task; otherwise return the supported incomplete, uncertain, or tooling-blocked verdict."""


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


def _fixed_action_schema(
    tool_surface_mode: str = "control",
    long_command_mode: str = "control",
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    allowed = set(FIXED_KERNEL_TOOL_SURFACE)
    schema = tuple((name, args) for name, args in ACTION_SCHEMA if name in allowed)
    if tool_surface_mode in {"static_kernel_edit_v1", "static_kernel_edit_flat_v1"}:
        schema = (*schema, EDIT_FILE_ACTION_SCHEMA_ENTRY)
    if long_command_mode == LONG_COMMAND_BACKGROUND_V1:
        schema = (*schema, *((name, args) for name, args in ACTION_SCHEMA if name in {"job_output", "job_wait", "job_stop"}))
    return schema


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
        schema_version="aether.persistent_runtime.v1",
        selected_capabilities=capability_ids,
        task_contract_identity=task_contract_identity,
        environment_digest=envmap.digest(),
    )


SOLVER_CONTEXT_MODES = frozenset({"full", "compact", "compact_guided", "compact_scoped"})
INCUMBENT_PREFIX_RENDERER = "incumbent_context"
MINIMAL_REALITY_LOOP_PREFIX_RENDERER = "minimal_reality_loop_static_v1"
SOLVER_PREFIX_RENDERERS = frozenset({INCUMBENT_PREFIX_RENDERER, MINIMAL_REALITY_LOOP_PREFIX_RENDERER})
SOLVER_REASONING_MODES = frozenset({
    "control", "discriminating_experiment_v1", "vertical_slice_v1", "commitment_v1",
})
SOLVER_ASYNC_CONTROL = "control"
SOLVER_ASYNC_SERIAL_JOBS_V1 = "serial_jobs_v1"
SOLVER_ASYNC_INDEPENDENT_JOBS_V1 = "independent_jobs_v1"
SOLVER_ASYNC_MODES = frozenset({
    SOLVER_ASYNC_CONTROL,
    SOLVER_ASYNC_SERIAL_JOBS_V1,
    SOLVER_ASYNC_INDEPENDENT_JOBS_V1,
})
SOLVER_TASK_CONTRACT_CONTROL = "raw_task_control"
SOLVER_TASK_CONTRACT_SOURCE_CLAUSES_V1 = "source_clauses_v1"
SOLVER_TASK_CONTRACT_MODES = frozenset({
    SOLVER_TASK_CONTRACT_CONTROL,
    SOLVER_TASK_CONTRACT_SOURCE_CLAUSES_V1,
})
SOLVER_REALITY_TRANSPORT_CONTROL = "full_snapshot_control"
SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1 = "delta_only_v1"  # Responses route only; untouched.
SOLVER_REALITY_TRANSPORT_OBSERVATION_HISTORY_V1 = "observation_history_v1"
SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1 = "latest_exchange_v1"
SOLVER_REALITY_TRANSPORT_REASONING_ACTIONS_NO_RESULTS_V1 = "reasoning_actions_no_results_v1"
SOLVER_REALITY_TRANSPORT_REASONING_LATEST_ACTION_NO_RESULTS_V1 = "reasoning_latest_action_no_results_v1"
SOLVER_REALITY_TRANSPORT_ACTIONS_RESULTS_NO_REASONING_V1 = "actions_results_no_reasoning_v1"
SOLVER_REALITY_TRANSPORT_MODES = frozenset({
    SOLVER_REALITY_TRANSPORT_CONTROL,
    SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1,
    SOLVER_REALITY_TRANSPORT_OBSERVATION_HISTORY_V1,
    SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1,
    SOLVER_REALITY_TRANSPORT_REASONING_ACTIONS_NO_RESULTS_V1,
    SOLVER_REALITY_TRANSPORT_REASONING_LATEST_ACTION_NO_RESULTS_V1,
    SOLVER_REALITY_TRANSPORT_ACTIONS_RESULTS_NO_REASONING_V1,
})
SOLVER_WORKING_CONTEXT_OFF = "off"
SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1 = "assistant_content_v1"
SOLVER_WORKING_CONTEXT_READ_INDEX_V1 = "read_index_v1"
SOLVER_WORKING_CONTEXT_TOOL_NOTES_V1 = "tool_notes_v1"
SOLVER_WORKING_CONTEXT_TOOL_NOTES_GROUNDED_V1 = "tool_notes_grounded_v1"
SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1 = "read_index_tool_notes_v1"
SOLVER_WORKING_CONTEXT_MODES = frozenset({
    SOLVER_WORKING_CONTEXT_OFF,
    SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1,
    SOLVER_WORKING_CONTEXT_READ_INDEX_V1,
    SOLVER_WORKING_CONTEXT_TOOL_NOTES_V1,
    SOLVER_WORKING_CONTEXT_TOOL_NOTES_GROUNDED_V1,
    SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1,
})
SOLVER_COMMITMENT_V1_GUIDANCE = (
    "For each act turn, author only a compact auditable commitment: the current subgoal, the unresolved "
    "evidence gap, why this one action addresses it, the concrete observation you expect, and what you "
    "would do next if the action fails or contradicts that expectation. Keep each field concise; do not "
    "provide chain-of-thought. The commitment is non-binding working state, not a harness judgment: observed "
    "reality and the raw task remain authoritative, and you remain responsible for interpretation and the next decision."
)

DISCRIMINATING_EXPERIMENT_GUIDANCE = (
    "When you have a plausible explanation or solution but a material assumption could still be wrong, "
    "or an observation is surprising, consider a plausible alternative explanation. Before committing "
    "substantial further work, choose a practical observation whose possible outcomes would distinguish "
    "the explanations, execute it with the existing tools, and let the observed result influence your next "
    "decision. The observation may be a direct inspection, counterexample or property test, small reference "
    "implementation, real service interaction, or calculation. Do not do this mechanically when there is no "
    "material uncertainty. You own the hypothesis, experiment, interpretation, and decision; the raw task "
    "and observed reality remain authoritative."
)

VERTICAL_SLICE_V1_GUIDANCE = (
    "When practical, establish an early end-to-end working path through the task's real interfaces before "
    "deep local optimization. Use that path to expose integration assumptions and preserve it while improving "
    "the solution. If observed evidence contradicts the current strategy, revise the strategy rather than "
    "defending it; do not switch strategies gratuitously when the evidence still supports the current path. "
    "Do not force a vertical slice when the task has no meaningful end-to-end path."
)

SERIAL_JOBS_V1_GUIDANCE = (
    "Use the managed background-job interface for finite jobs, but keep at most one background job live at "
    "a time. Wait for the current registered job to reach a terminal state before starting another finite "
    "background job. Aether will surface current registered job status in runtime_operations. Bind probes and "
    "cancellation to the exact registered job and do not finish while a required job remains unresolved."
)

INDEPENDENT_JOBS_V1_GUIDANCE = (
    "Use managed background jobs to overlap work only when operations are genuinely independent and overlap "
    "is likely to help. Keep at most two background jobs live at once. For shell work with unknown read/write "
    "sets, do not speculate that operations are independent: serialize unless independence is established from "
    "observed task/environment facts. After launching jobs, continue useful independent work instead of polling "
    "mechanically; Aether will surface current registered job status in runtime_operations. Bind every probe or "
    "cancellation to the exact registered job. Do not finish while a required job remains unresolved."
)


def build_persistent_runtime(
    envmap: EnvMap, *, solver_context_mode: str = "full", solver_reasoning_mode: str = "control",
    solver_async_mode: str = SOLVER_ASYNC_CONTROL,
    solver_task_contract_mode: str = SOLVER_TASK_CONTRACT_CONTROL,
    solver_prefix_renderer: str = INCUMBENT_PREFIX_RENDERER,
    solver_reality_transport_mode: str = SOLVER_REALITY_TRANSPORT_CONTROL,
    solver_working_context_mode: str = SOLVER_WORKING_CONTEXT_OFF,
    solver_hosted_tool_search_mode: str = SOLVER_HOSTED_TOOL_SEARCH_CONTROL,
    verifier_activation_continuity_mode: str = VERIFIER_ACTIVATION_CONTINUITY_CONTROL,
    solver_tool_surface_mode: str = "control",
    solver_long_command_mode: str | None = None,
    solver_env_mode: str = ENV_CONTROL,
) -> ResolvedPCRRuntime:
    """Build the one production runtime from raw task + observed capabilities."""
    selected = _selected_capabilities(envmap)
    capability_ids = tuple(cap.capability_id for cap in selected)
    if not selected:
        blockers = ("runtime_compile:ValueError:PERSISTENT requires at least one observed available capability",)
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
    reasoning_mode = str(solver_reasoning_mode or "control").strip().lower()
    if reasoning_mode not in SOLVER_REASONING_MODES:
        raise ValueError(f"unsupported Solver reasoning mode: {solver_reasoning_mode}")
    async_mode = str(solver_async_mode or SOLVER_ASYNC_CONTROL).strip().lower()
    if async_mode not in SOLVER_ASYNC_MODES:
        raise ValueError(f"unsupported Solver async mode: {solver_async_mode}")
    task_contract_mode = str(
        solver_task_contract_mode or SOLVER_TASK_CONTRACT_CONTROL
    ).strip().lower()
    if task_contract_mode not in SOLVER_TASK_CONTRACT_MODES:
        raise ValueError(
            f"unsupported Solver task-contract mode: {solver_task_contract_mode}"
        )
    reality_transport_mode = str(
        solver_reality_transport_mode or SOLVER_REALITY_TRANSPORT_CONTROL
    ).strip().lower()
    if reality_transport_mode not in SOLVER_REALITY_TRANSPORT_MODES:
        raise ValueError(
            f"unsupported Solver reality transport mode: {solver_reality_transport_mode}"
        )
    working_context_mode = str(
        solver_working_context_mode or SOLVER_WORKING_CONTEXT_OFF
    ).strip().lower()
    if working_context_mode not in SOLVER_WORKING_CONTEXT_MODES:
        raise ValueError(
            f"unsupported Solver working-context mode: {solver_working_context_mode}"
        )
    if (
        working_context_mode != SOLVER_WORKING_CONTEXT_OFF
        and reality_transport_mode != SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1
    ):
        raise ValueError(
            "non-off Solver working context requires latest_exchange_v1 reality transport"
        )
    hosted_tool_search_mode = str(
        solver_hosted_tool_search_mode or SOLVER_HOSTED_TOOL_SEARCH_CONTROL
    ).strip().lower()
    if hosted_tool_search_mode not in SOLVER_HOSTED_TOOL_SEARCH_MODES:
        raise ValueError(
            f"unsupported Solver hosted tool search mode: {solver_hosted_tool_search_mode}"
        )
    verifier_continuity_mode = str(
        verifier_activation_continuity_mode or VERIFIER_ACTIVATION_CONTINUITY_CONTROL
    ).strip().lower()
    if verifier_continuity_mode not in VERIFIER_ACTIVATION_CONTINUITY_MODES:
        raise ValueError(
            f"unsupported Verifier activation continuity mode: {verifier_activation_continuity_mode}"
        )
    prefix_renderer = str(solver_prefix_renderer or INCUMBENT_PREFIX_RENDERER).strip().lower()
    if prefix_renderer not in SOLVER_PREFIX_RENDERERS:
        raise ValueError(f"unsupported Solver prefix renderer: {solver_prefix_renderer}")
    env_mode = str(solver_env_mode or ENV_CONTROL).strip()
    if env_mode not in SUPPORTED_ENV_MODES:
        raise ValueError(f"unsupported Solver env mode: {solver_env_mode}")
    if env_mode != ENV_CONTROL and (context_mode != "full" or prefix_renderer != INCUMBENT_PREFIX_RENDERER):
        # The arm only changes the full inventory rendering; elsewhere it would be a silent no-op.
        raise ValueError(f"env mode {env_mode} requires the full context mode and incumbent prefix renderer")

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
    long_command_mode = (
        selected_long_command_mode() if solver_long_command_mode is None
        else str(solver_long_command_mode).strip()
    )
    if long_command_mode not in {"control", LONG_COMMAND_BACKGROUND_V1}:
        raise ValueError(f"unsupported long-command mode: {long_command_mode!r}")
    action_schema = _fixed_action_schema(solver_tool_surface_mode, long_command_mode)
    environment_probe = dict((envmap.task_metadata or {}).get("environment_probe", {}) or {})
    if context_mode == "full":
        model_environment_probe = (
            lean_environment_probe(environment_probe) if env_mode == ENV_LEAN_V1
            else lean_v2_environment_probe(environment_probe) if env_mode == ENV_LEAN_V2
            else persistent_model_environment_probe(environment_probe)
        )
    elif context_mode == "compact_guided":
        model_environment_probe = persistent_model_environment_probe_compact_guided(environment_probe)
    elif context_mode == "compact_scoped":
        model_environment_probe = persistent_model_environment_probe_compact_scoped(environment_probe)
    else:
        model_environment_probe = persistent_model_environment_probe_compact(environment_probe)

    config_realization: dict[str, Any] = {
        "schema_version": "aether.persistent_runtime_realization.v1",
        "runtime_path": "persistent_v0",
        "configuration_model_calls": 0,
        "model_authored_reconfiguration": False,
        "task_semantic_compiler": False,
        "raw_task_semantic_authority": True,
        "tool_policy_mode": "stable_core",
        "solver_context_mode": context_mode,
        **({"solver_reality_transport_mode": reality_transport_mode}
           if reality_transport_mode != SOLVER_REALITY_TRANSPORT_CONTROL else {}),
        **({"solver_working_context_mode": working_context_mode}
           if working_context_mode != SOLVER_WORKING_CONTEXT_OFF else {}),
        **({"solver_hosted_tool_search_mode": hosted_tool_search_mode}
           if hosted_tool_search_mode != SOLVER_HOSTED_TOOL_SEARCH_CONTROL else {}),
        **({"verifier_activation_continuity_mode": verifier_continuity_mode}
           if verifier_continuity_mode != VERIFIER_ACTIVATION_CONTINUITY_CONTROL else {}),
        **({"solver_prefix_renderer": prefix_renderer} if prefix_renderer != INCUMBENT_PREFIX_RENDERER else {}),
        **({"solver_env_mode": env_mode} if env_mode != ENV_CONTROL else {}),
        **({"solver_reasoning_mode": reasoning_mode} if reasoning_mode != "control" else {}),
        **({"solver_async_mode": async_mode} if async_mode != SOLVER_ASYNC_CONTROL else {}),
        **(
            {"solver_task_contract_mode": task_contract_mode}
            if task_contract_mode != SOLVER_TASK_CONTRACT_CONTROL else {}
        ),
        **({"solver_persistent_shell": True} if persistent_persistent_shell(solver_tool_surface_mode) else {}),
        **({"solver_long_command_mode": long_command_mode} if long_command_mode != "control" else {}),
        **({} if persistent_finish_intent_exposed(solver_tool_surface_mode)
           else {"solver_finish_intent_exposed": False}),
        "capabilities_realized": list(capability_ids),
        "tools_visible_to_solver": sorted(name for name, _args in action_schema),
        "environment_probe": environment_probe,
        "environment_probe_available": bool(environment_probe),
        "model_verifier_policy": asdict(verifier_policy),
        "verification_authority": {
            "frontier": "final_semantic_authority",
            "model_verifier": "advisory_independent_review",
            "mechanical_completion_gate": "runtime_reality_only",
            "official_grader": "external_official_grader",
        },
        "task_contract_identity": task_contract.contract_identity,
        "compiled_evidence_requirements": [],
    }

    # The incumbent renderer is byte-for-byte the pre-ablation stable prefix.
    # The minimal-reality-loop renderer removes only preloaded factual inventory
    # sections. It adds no strategy, planner, critic, or discovery guidance; Frontier
    # retains the raw task and unchanged native tools for demand-driven discovery.
    prefix_sections: list[tuple[str, str]] = [
        *protocol_card_sections(solver_tool_surface_mode),
        ("task_prompt", envmap.task_prompt),
    ]
    if task_contract_mode == SOLVER_TASK_CONTRACT_SOURCE_CLAUSES_V1:
        prefix_sections.append((
            "task_contract_view",
            stable_json({
                "schema": "aether.solver_task_contract_view.v1",
                "authority": "navigation_only_raw_task_remains_authoritative",
                "source": "exact_raw_task_substrings",
                "clauses": list(source_linked_task_clauses(envmap.task_prompt)),
            }),
        ))
    if prefix_renderer == INCUMBENT_PREFIX_RENDERER:
        prefix_sections.append(
            ("envmap", stable_json(envmap.compact_summary() | {"env_digest": envmap.digest()}))
        )
        if context_mode == "full" and env_mode in {ENV_LEAN_V1, ENV_LEAN_V2}:
            prefix_sections.append(
                ("envmap_file_map_summary", stable_json(lean_file_map(envmap.file_map_summary)))
            )
        elif context_mode == "full":
            prefix_sections.extend((
                ("envmap_file_tree", envmap.file_tree or ""),
                ("envmap_file_map_summary", stable_json(dict(envmap.file_map_summary))),
            ))
        else:
            prefix_sections.append((
                "environment_discovery",
                (
                    "Detailed file, command, and package inventories are not preloaded. "
                    "Use the unchanged native file/shell tools to inspect what you need; "
                    "Aether retains the full environment probe for audit custody."
                    if context_mode == "compact" else
                    (
                        "Detailed inventories are not preloaded. Use one bounded live discovery action, "
                        "favoring workspace-local/task-local roots exposed in environment_probe. When the "
                        "task identifies an unknown command or module by behavior/version/ROLE, combine "
                        "candidate enumeration and discrimination in that bounded action when practical. "
                        "Do not assume query_history can resolve facts Aether has never observed."
                        if context_mode == "compact_scoped" else
                        "Detailed inventories are demand-loaded. When the task supplies a literal "
                        "descriptor for an unknown command or module, call query_history with that "
                        "descriptor first, then revalidate the returned identity live. Otherwise use "
                        "bounded portable discovery; never brute-force every PATH entry."
                    )
                ),
            ))
        if context_mode == "compact_scoped":
            prefix_sections.append((
                "completion_freshness_guidance",
                (
                    "After your final state-changing action, evidence observed before that mutation may be historical. "
                    f"Before {'finish_intent' if persistent_finish_intent_exposed(solver_tool_surface_mode) else 'finish'}, if a decisive completion fact still depends on pre-mutation observation, "
                    "collect one bounded current read-only observation that re-establishes the necessary source/final-state "
                    "facts; combine related checks in one action when practical. You choose what must be re-observed."
                ),
            ))
    if async_mode == SOLVER_ASYNC_SERIAL_JOBS_V1:
        prefix_sections.append(("solver_async_execution", SERIAL_JOBS_V1_GUIDANCE))
    elif async_mode == SOLVER_ASYNC_INDEPENDENT_JOBS_V1:
        prefix_sections.append(("solver_async_execution", INDEPENDENT_JOBS_V1_GUIDANCE))
    if reasoning_mode == "discriminating_experiment_v1":
        prefix_sections.append(("solver_reasoning_treatment", DISCRIMINATING_EXPERIMENT_GUIDANCE))
    elif reasoning_mode == "vertical_slice_v1":
        prefix_sections.append(("solver_reasoning_treatment", VERTICAL_SLICE_V1_GUIDANCE))
    elif reasoning_mode == "commitment_v1":
        prefix_sections.append(("solver_commitment_contract", SOLVER_COMMITMENT_V1_GUIDANCE))
    prefix_sections.append(("solver_identity", PRIMARY_AGENT_CONSTITUTION))
    if prefix_renderer == INCUMBENT_PREFIX_RENDERER:
        prefix_sections.append(("environment_probe", stable_json(model_environment_probe)))
    prefix_sections.append(("refusal_boundary", _refusal_boundary(refusal_policy)))

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
        verifier_identity_prompt=PERSISTENT_VERIFIER_CONSTITUTION,
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
    "PERSISTENT_VERIFIER_CONSTITUTION",
    "PRIMARY_AGENT_CONSTITUTION",
    "ResolvedPCRRuntime",
    "RuntimeState",
    "SOLVER_REASONING_MODES",
    "SOLVER_ASYNC_CONTROL",
    "SOLVER_ASYNC_SERIAL_JOBS_V1",
    "SOLVER_ASYNC_INDEPENDENT_JOBS_V1",
    "SOLVER_ASYNC_MODES",
    "SOLVER_TASK_CONTRACT_CONTROL",
    "SOLVER_TASK_CONTRACT_SOURCE_CLAUSES_V1",
    "SOLVER_TASK_CONTRACT_MODES",
    "INCUMBENT_PREFIX_RENDERER",
    "MINIMAL_REALITY_LOOP_PREFIX_RENDERER",
    "SOLVER_PREFIX_RENDERERS",
    "SOLVER_COMMITMENT_V1_GUIDANCE",
    "DISCRIMINATING_EXPERIMENT_GUIDANCE",
    "VERTICAL_SLICE_V1_GUIDANCE",
    "SERIAL_JOBS_V1_GUIDANCE",
    "INDEPENDENT_JOBS_V1_GUIDANCE",
    "build_persistent_runtime",
]

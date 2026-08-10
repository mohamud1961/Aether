"""Mechanical PERSISTENT V0 runtime profile.

The persistent Primary Agent path is compiled directly from raw task authority
and observed environment capabilities. It performs no Architect model call
and adds no task-semantic interpretation in the Kernel.
"""
from __future__ import annotations

from .persistent_task_contract import compile_persistent_task_contract
from .runtime_ir import (
    AutomaticMemoryPolicy,
    BootstrapPolicy,
    CompletionPolicy,
    EnvMap,
    EvalIndex,
    HelperToolPolicy,
    ReconfigurePolicy,
    RuntimeConfigIR,
)


PRIMARY_AGENT_CONSTITUTION = """You are Aether's persistent Primary Agent.

Own the task from first observation until independently verified completion.

Treat the raw task and observed reality as authoritative.

Use computation to understand, modify and verify the environment.

The Kernel executes actions and preserves reality. It does not choose your strategy.

Completion must be supported by observed evidence. An independent Verifier may challenge your claim."""


PERSISTENT_VERIFIER_CONSTITUTION = """You are Aether's independent PERSISTENT Verifier.

Judge the exact Primary Agent completion claim against current observed state and the cited same-run evidence.

Do not trust a claim, plan, summary, model-authored observation, bookkeeping receipt, or helper output merely because it exists.

Use read-only inspections when the available evidence does not establish the claim. Distinguish task-state evidence from metadata and proxy evidence.

Return completed only when the current evidence establishes the raw task. Otherwise return the precise incomplete, uncertain, or tooling-blocked verdict supported by reality."""


def persistent_primary_runtime_ir(
    envmap: EnvMap,
    eval_index: EvalIndex,
) -> RuntimeConfigIR:
    """Compile the direct persistent runtime without model-authored config."""
    available_capabilities = tuple(
        capability_id
        for capability_id, descriptor in sorted(envmap.capabilities.items())
        if descriptor.available
    )
    if not available_capabilities:
        raise ValueError("PERSISTENT V0 requires at least one observed available capability")

    capability_set = set(available_capabilities)
    helper_supported = {"filesystem", "shell"}.issubset(capability_set)
    bootstrap_supported = "shell" in capability_set
    authoritative_checks = tuple(
        check.check_id for check in eval_index.authoritative_checks()
    )
    task_contract = compile_persistent_task_contract(envmap.task_prompt)

    return RuntimeConfigIR(
        architect_summary=(
            "PERSISTENT V0 direct persistent runtime compiled mechanically from raw "
            "task authority and observed capabilities; Architect model calls=0."
        ),
        solver_identity_prompt=PRIMARY_AGENT_CONSTITUTION,
        verifier_identity_prompt=PERSISTENT_VERIFIER_CONSTITUTION,
        selected_capabilities=available_capabilities,
        solver_turn_protocol="persistent_v0",
        helper_tool_policy=HelperToolPolicy(
            allow_creation=helper_supported,
            require_smoke_test=helper_supported,
            trust_for_completion=False,
        ),
        bootstrap_policy=BootstrapPolicy(
            allow_acquisition=bootstrap_supported,
        ),
        automatic_memory_policy=AutomaticMemoryPolicy(mode="off"),
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
            "runtime_mode=persistent_v0",
            "architect_model_calls=0",
        ),
        task_contract=task_contract,
    )

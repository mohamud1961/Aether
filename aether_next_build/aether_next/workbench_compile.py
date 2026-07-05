"""Compile vNext HarnessConfigIR into the legacy RuntimeConfigIR path."""
from __future__ import annotations

from dataclasses import asdict

from .smoke_compile import compile_visible_smoke_tests
from .runtime_ir import (
    ALWAYS_AVAILABLE_ACTION_KINDS,
    AutomaticMemoryPolicy,
    BootstrapPolicy,
    CompletionPolicy,
    ContextPolicy,
    ContextRecipe,
    ContextRecipeRecent,
    EnvMap,
    HelperToolPolicy,
    ModelVerifierPolicy,
    RuntimeConfigIR,
)
from .workbench_config import HarnessConfigIR, SUPPORTED_TOP_LEVEL_CONFIG_FIELDS

# The stable core is the FULL generic workbench: every kernel-implemented,
# capability-backed tool a task class could legitimately require.  The
# architect's tool_policy is recorded as guidance, never as a gate -- a
# missing tool must never be a hidden harness ceiling (caught 2026-07-05 by
# the Docker service-class smoke: launch_process was unreachable).
STABLE_CORE_SOLVER_TOOLS = (
    "read_file",
    "write_file",
    "run_command",
    "launch_process",
    "probe_service",
    "stop_process",
    "inspect_artifact",
    "bootstrap_acquire",
    "query_memory",
    "query_artifact_history",
    "inspect_diff",
    "record_observation",
    "inspect_checks",
    "run_check",
)

AUDIT_SEPARATELY_TOOLS = (
    "run_experiment",
    "register_candidate",
    "reconfigure",
)

_DEFAULT_CAPABILITY_TOOLS = {
    "shell": ("run_command",),
    "filesystem": ("read_file", "write_file"),
    "managed_process": ("launch_process", "probe_service", "stop_process"),
    "service_probe": ("probe_service",),
    "artifact_inspection": ("inspect_artifact",),
    "network_fetch": ("bootstrap_acquire",),
}


TOP_LEVEL_CONFIG_FIELDS = (
    *sorted(SUPPORTED_TOP_LEVEL_CONFIG_FIELDS),
)


def harness_config_to_runtime_ir(config: HarnessConfigIR, envmap: EnvMap) -> RuntimeConfigIR:
    """Translate vNext workbench config into a runtime the current compiler can realize."""
    selected_caps = _stable_core_capabilities(envmap)
    helper_enabled = config.helper_script_policy.enabled and {"shell", "filesystem"}.issubset(selected_caps)
    smoke_result = compile_visible_smoke_tests(config, envmap)
    advisory_notes = [
        "vNext HarnessConfigIR compiled into RuntimeConfigIR.",
        "tool_policy_mode=stable_core",
        "architect_tool_selection_applied=False",
        "architect tool policy is advisory; stable core tools are exposed unless the environment/safety layer forbids them.",
        "architect_requested_tools=" + str(list(config.tool_policy.enabled_tools)),
        "architect_disabled_tools_advisory=" + str(list(config.tool_policy.disabled_tools)),
        f"context_policy={config.context_policy.mode}",
        f"model_verifier_enabled={config.model_verifier_policy.enabled}",
        f"failure_feedback_persist_until={config.failure_feedback_policy.persist_until}",
    ]
    env_probe = envmap.task_metadata.get("environment_probe", {}) or {}
    if isinstance(env_probe, dict) and env_probe:
        preferred_python = (
            env_probe.get("validation_guidance", {}).get("preferred_python")
            if isinstance(env_probe.get("validation_guidance"), dict)
            else ""
        )
        advisory_notes.append("environment_probe_available=True")
        if preferred_python:
            advisory_notes.append(f"environment_preferred_python={preferred_python}")
    advisory_notes.extend(config.local_verification_limits)
    if config.evidence_requirements:
        advisory_notes.append("evidence_requirements=" + str(list(config.evidence_requirements)))
    if config.false_positive_risks:
        advisory_notes.append("false_positive_risks=" + str(list(config.false_positive_risks)))
    if config.minimum_completion_evidence:
        advisory_notes.append("minimum_completion_evidence=" + str(list(config.minimum_completion_evidence)))
    if config.verification_policy.visible_smoke_tests:
        advisory_notes.append("visible_smoke_tests=" + str([dict(item) for item in config.verification_policy.visible_smoke_tests]))
        if smoke_result.checks:
            advisory_notes.append("compiled_visible_smoke_checks=" + str([check.check_id for check in smoke_result.checks]))
        if smoke_result.rejected:
            advisory_notes.append("visible_smoke_compile_rejections=" + str([dict(item) for item in smoke_result.rejected]))
    if config.repair_warning_codes:
        advisory_notes.append("workbench_config_repairs=" + ",".join(config.repair_warning_codes))
    return RuntimeConfigIR(
        architect_summary=config.task_understanding,
        solver_identity_prompt=config.solver_system_prompt.render(),
        verifier_identity_prompt=config.verifier_system_prompt.render(),
        selected_capabilities=selected_caps,
        context_policy=ContextPolicy(
            mode=config.context_policy.mode,
            include_sections=_context_sections(config),
            recipe=_context_recipe(config),
        ),
        automatic_memory_policy=AutomaticMemoryPolicy(mode=config.memory_policy.automatic_repeat_mode),
        bootstrap_policy=BootstrapPolicy(allow_acquisition="shell" in selected_caps),
        helper_tool_policy=HelperToolPolicy(
            allow_creation=helper_enabled,
            trust_for_completion=False,
            task_local_dir=config.helper_script_policy.directory.replace("/app/", ""),
        ),
        completion_policy=CompletionPolicy(),
        model_verifier_policy=ModelVerifierPolicy(
            enabled=bool(config.model_verifier_policy.enabled),
            runs_on=tuple(config.model_verifier_policy.runs_on),
        ),
        inspection_plan=tuple(config.solver_system_prompt.workflow[:3]) or ("follow architect solver prompt",),
        proof_plan=tuple(config.solver_system_prompt.self_verification) or ("self-verify visible evidence",),
        check_plan=tuple(check.check_id for check in smoke_result.checks),
        compiler_injected_checks=smoke_result.checks,
        advisory_notes=tuple(advisory_notes),
        success_definition=config.success_definition,
        local_verification_limits=config.local_verification_limits,
        evidence_requirements=config.evidence_requirements,
        false_positive_risks=config.false_positive_risks,
        minimum_completion_evidence=config.minimum_completion_evidence,
    )


def _capabilities_for_tools(tools: tuple[str, ...], envmap: EnvMap) -> tuple[str, ...]:
    wanted = set(tools) - set(ALWAYS_AVAILABLE_ACTION_KINDS)
    selected: list[str] = []
    for capability_id, cap in sorted(envmap.capabilities.items()):
        if wanted.intersection(set(cap.tool_names)):
            selected.append(capability_id)
    # If the registry lacks tool_names, fall back to common capability names.
    if "read_file" in wanted or "write_file" in wanted:
        selected.append("filesystem")
    if "run_command" in wanted:
        selected.append("shell")
    deduped = []
    for item in selected:
        if item in envmap.capabilities and item not in deduped:
            deduped.append(item)
    return tuple(deduped or tuple(envmap.capabilities)[:1])


def _stable_core_capabilities(envmap: EnvMap) -> tuple[str, ...]:
    return _capabilities_for_tools(STABLE_CORE_SOLVER_TOOLS, envmap)


def _context_sections(config: HarnessConfigIR) -> tuple[str, ...]:
    base = list(config.context_policy.always_include)
    base.extend(config.context_policy.include_on_failure)
    if not base:
        base = [
            "open_obligations", "obligation_status", "recent_progress", "failure_clusters",
            "artifacts_present", "planned_checks", "pending_checks", "command_results",
        ]
    allowed = {
        "open_obligations", "obligation_status", "monitor_alerts", "live_processes",
        "recent_progress", "failure_clusters", "artifacts_present", "candidate_leaderboard",
        "installed_capabilities", "planned_checks", "pending_checks", "command_results",
    }
    return tuple(item for item in dict.fromkeys(base) if item in allowed)


def _context_recipe(config: HarnessConfigIR) -> ContextRecipe | None:
    recipe = config.context_policy.recipe
    if recipe is None:
        return None
    return ContextRecipe(
        always_include=tuple(dict.fromkeys(recipe.always_include)),
        include_recent=tuple(
            ContextRecipeRecent(selector=item.selector, count=max(0, int(item.count)))
            for item in recipe.include_recent
        ),
        include_last_failure=max(0, int(recipe.include_last_failure)),
        preserve_exact=tuple(dict.fromkeys(recipe.preserve_exact)),
        make_queryable_not_inline=tuple(dict.fromkeys(recipe.make_queryable_not_inline)),
        unsupported_fields=tuple(dict.fromkeys(recipe.unsupported_fields)),
    )


def realization_preview(config: HarnessConfigIR, envmap: EnvMap) -> dict[str, object]:
    ir = harness_config_to_runtime_ir(config, envmap)
    return {
        "schema_version": config.schema_version,
        "selected_capabilities": list(ir.selected_capabilities),
        "context_policy_mode": ir.context_policy.mode,
        "solver_prompt_inserted": bool(ir.solver_identity_prompt.strip()),
        "verifier_prompt_inserted": bool(ir.verifier_identity_prompt.strip()),
        "helper_scripts_enabled": ir.helper_tool_policy.allow_creation,
        "tool_policy_mode": "stable_core",
        "architect_tool_selection_applied": False,
        "advisory_notes": list(ir.advisory_notes),
        "repair_warning_codes": list(config.repair_warning_codes),
        "repair_warnings": list(config.repair_warnings),
        "rejected_config_items": [dict(item) for item in config.rejected_config_items],
        "realization_audit": config_realization_audit(config, envmap),
        "raw_config": asdict(config),
    }


def config_realization_audit(config: HarnessConfigIR, envmap: EnvMap) -> dict[str, object]:
    """Explain how each HarnessConfigIR field is handled.

    This is deliberately conservative: a field is marked realized only when it
    changes current runtime architecture, not when it is merely parsed.
    """
    ir = harness_config_to_runtime_ir(config, envmap)
    realized_tools = _realized_tools(ir.selected_capabilities, envmap)
    smoke_count = len(config.verification_policy.visible_smoke_tests)
    smoke_compile = compile_visible_smoke_tests(config, envmap)
    structural_count = len(config.verification_policy.structural_checks)
    dispositions = {
        "schema_version": {
            "status": "validated",
            "evidence": "parse_harness_config_ir rejects non-harness_config.v1",
        },
        "task_understanding": {
            "status": "realized",
            "realized_as": "RuntimeConfigIR.architect_summary",
        },
        "success_definition": {
            "status": "realized_advisory",
            "realized_as": "RuntimeConfigIR.success_definition and verifier packet metadata",
        },
        "solver_system_prompt": {
            "status": "realized",
            "realized_as": "RuntimeConfigIR.solver_identity_prompt",
            "inserted": bool(ir.solver_identity_prompt.strip()),
        },
        "verifier_system_prompt": {
            "status": "realized",
            "realized_as": "RuntimeConfigIR.verifier_identity_prompt and verifier packet/prompt metadata",
            "inserted": bool(ir.verifier_identity_prompt.strip()),
        },
        "evidence_requirements": {
            "status": "realized_advisory",
            "count": len(config.evidence_requirements),
            "realized_as": "RuntimeConfigIR.evidence_requirements, config_realization, and verifier packet metadata",
        },
        "false_positive_risks": {
            "status": "realized_advisory",
            "count": len(config.false_positive_risks),
            "realized_as": "RuntimeConfigIR.false_positive_risks, config_realization, and verifier packet metadata",
        },
        "minimum_completion_evidence": {
            "status": "realized_advisory",
            "count": len(config.minimum_completion_evidence),
            "realized_as": "RuntimeConfigIR.minimum_completion_evidence, config_realization, and verifier packet metadata",
        },
        "tool_policy": {
            "status": "advisory_not_applied_to_core_visibility",
            "tool_policy_mode": "stable_core",
            "architect_tool_selection_applied": False,
            "architect_tool_guidance_recorded": True,
            "enabled_tools_declared": list(config.tool_policy.enabled_tools),
            "disabled_tools_declared": list(config.tool_policy.disabled_tools),
            "stable_core_solver_tools": list(STABLE_CORE_SOLVER_TOOLS),
            "audit_separately_tools": list(AUDIT_SEPARATELY_TOOLS),
            "selected_capabilities": list(ir.selected_capabilities),
            "runtime_allowed_tools_expected": realized_tools,
            "always_available_tools": sorted(ALWAYS_AVAILABLE_ACTION_KINDS),
            "note": "Workbench stable-core mode does not hide core solver tools merely because the architect omitted them; real restrictions must come from env/safety/runtime capability availability.",
        },
        "context_policy": {
            "status": "realized_partial",
            "mode": ir.context_policy.mode,
            "sections": list(ir.context_policy.include_sections),
            "recipe_declared": ir.context_policy.recipe is not None,
            "recipe": (
                {
                    "always_include": list(ir.context_policy.recipe.always_include),
                    "include_recent": [
                        {"selector": item.selector, "count": item.count}
                        for item in ir.context_policy.recipe.include_recent
                    ],
                    "include_last_failure": ir.context_policy.recipe.include_last_failure,
                    "preserve_exact": list(ir.context_policy.recipe.preserve_exact),
                    "make_queryable_not_inline": list(ir.context_policy.recipe.make_queryable_not_inline),
                    "unsupported_fields": list(ir.context_policy.recipe.unsupported_fields),
                }
                if ir.context_policy.recipe is not None
                else None
            ),
            "note": "supported modes are realized; custom sections are allowlisted; optional recipes are compiled into ContextPolicy and realized by ContextCompiler with explicit metadata",
        },
        "memory_policy": {
            "status": "realized_partial",
            "automatic_repeat_mode": config.memory_policy.automatic_repeat_mode,
            "runtime_automatic_memory_policy": asdict(ir.automatic_memory_policy),
            "index_by": list(config.memory_policy.index_by),
            "require_query_before_repeat": config.memory_policy.require_query_before_repeat,
            "require_query_before_overwrite": config.memory_policy.require_query_before_overwrite,
            "note": "automatic_repeat_mode is compiled into RuntimeConfigIR.automatic_memory_policy; legacy query-before fields remain advisory metadata while automatic memory replaces solver-called query rituals",
        },
        "verification_policy": {
            "status": "realized_partial",
            "visible_smoke_tests": smoke_count,
            "compiled_visible_smoke_checks": [check.check_id for check in smoke_compile.checks],
            "smoke_compile_rejections": [dict(item) for item in smoke_compile.rejected],
            "structural_checks": structural_count,
            "repair_warning_codes": list(config.repair_warning_codes),
            "repair_warnings": list(config.repair_warnings),
            "rejected_config_items": [dict(item) for item in config.rejected_config_items],
            "note": "safe typed visible smoke specs compile into internal CheckSpec evidence; unsupported or under-specified specs are rejected/quarantined and never become official grader authority",
        },
        "model_verifier_policy": {
            "status": "realized",
            "enabled": config.model_verifier_policy.enabled,
            "runs_on": list(config.model_verifier_policy.runs_on),
            "realized_as": "RuntimeConfigIR.model_verifier_policy and kernel_verifier reason filtering",
        },
        "failure_feedback_policy": {
            "status": "advisory_partial",
            "persist_until": config.failure_feedback_policy.persist_until,
            "note": "active findings persist via ActiveFindingStore; policy variants are not compiled yet",
        },
        "helper_script_policy": {
            "status": "realized",
            "enabled": ir.helper_tool_policy.allow_creation,
            "directory": ir.helper_tool_policy.task_local_dir,
        },
        "local_verification_limits": {
            "status": "realized_advisory",
            "count": len(config.local_verification_limits),
            "realized_as": "RuntimeConfigIR.local_verification_limits, advisory_notes, and verifier packet metadata",
        },
        "expected_steps": {
            "status": "realized_advisory",
            "value": int(getattr(config, "expected_steps", 0) or 0),
            "realized_as": "config_realization.expected_steps and result-row step_efficiency (advisory metric, never a gate)",
        },
    }
    missing = [field for field in TOP_LEVEL_CONFIG_FIELDS if field not in dispositions]
    return {
        "top_level_fields": list(TOP_LEVEL_CONFIG_FIELDS),
        "dispositions": dispositions,
        "missing_dispositions": missing,
        "has_silent_ignored_fields": bool(missing),
    }


def _realized_tools(selected_capabilities: tuple[str, ...], envmap: EnvMap) -> list[str]:
    tools = set(ALWAYS_AVAILABLE_ACTION_KINDS)
    for capability_id in selected_capabilities:
        cap = envmap.capabilities.get(capability_id)
        if cap is not None:
            tools.update(cap.tool_names or _DEFAULT_CAPABILITY_TOOLS.get(cap.capability_id, ()))
    return sorted(tools)

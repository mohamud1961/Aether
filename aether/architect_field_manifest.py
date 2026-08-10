"""Field authority and runtime-realization contract for Architect v1.

The Architect emits task-local guidance and a small set of runtime controls;
the kernel owns invariants such as the action surface.  This manifest makes
that boundary executable so a newly marked controlling field cannot silently
fall through compilation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


ARCHITECT_RUNTIME_CONTROL = "architect_owned_runtime_control"
KERNEL_INVARIANT = "kernel_owned_invariant"
ADVISORY_METADATA = "explicit_advisory_metadata"
MIGRATION_ONLY = "deprecated_migration_only"


@dataclass(frozen=True)
class FieldRealization:
    path: str
    authority: str
    runtime_consumer: str | None
    notes: str


def _control(path: str, consumer: str, notes: str) -> FieldRealization:
    return FieldRealization(path, ARCHITECT_RUNTIME_CONTROL, consumer, notes)


def _advisory(path: str, notes: str, consumer: str | None = None) -> FieldRealization:
    return FieldRealization(path, ADVISORY_METADATA, consumer, notes)


def _invariant(path: str, notes: str) -> FieldRealization:
    return FieldRealization(path, KERNEL_INVARIANT, None, notes)


def _migration(path: str, notes: str) -> FieldRealization:
    return FieldRealization(path, MIGRATION_ONLY, None, notes)


# Keep this list explicit: changes to the v1 schema must update the manifest
# and the focused coverage test, rather than inheriting an accidental default.
FIELD_REALIZATION_MANIFEST: tuple[FieldRealization, ...] = (
    _invariant("$.schema_version", "Parser accepts only harness_config.v1."),
    _control("$.task_understanding", "RuntimeConfigIR.architect_summary", "Inserted as the task-local architect summary."),
    _control("$.visible_contract", "RuntimeConfigIR.visible_contract/ConfigCompiler.architect_visible_contract", "Architect-authored standalone, constrained-standalone, scoped, and typed-scoped bindings are preserved in a dedicated Solver context section."),
    _advisory("$.success_definition", "Recorded in runtime and verifier packet metadata.", "RuntimeConfigIR.success_definition"),
    _control("$.solver_system_prompt", "RuntimeConfigIR.solver_identity_prompt", "Rendered into the solver context."),
    _control("$.verifier_system_prompt", "RuntimeConfigIR.verifier_identity_prompt", "Rendered into verifier packet/context."),
    _control("$.clause_coverage", "RuntimeConfigIR.semantic_clause_coverage", "Compiled into the proof contract when present."),
    _control("$.verifier_strategy", "RuntimeConfigIR.semantic_verifier_checks", "Compiled into verifier inspection routes when present."),
    _migration("$.tool_policy", "Legacy tool selection is recorded and ignored; kernel owns the fixed action surface."),
    _control("$.context_policy", "RuntimeConfigIR.context_policy", "Controls supported context mode, sections, recipe, and view budget."),
    _control("$.context_policy.mode", "ContextPolicy.mode", "Selects a supported context assembly mode."),
    _control("$.context_policy.always_include", "ContextPolicy.include_sections", "Adds allowlisted context sections."),
    _control("$.context_policy.include_on_failure", "ContextPolicy.include_sections", "Adds allowlisted failure sections."),
    _control("$.context_policy.model_context_window_tokens", "ContextPolicy.model_context_window_tokens", "Sets the bounded context view ceiling."),
    _control("$.context_policy.recipe", "ContextPolicy.recipe", "Compiles supported context recipe selectors."),
    _control("$.memory_policy", "RuntimeConfigIR.automatic_memory_policy", "Only automatic_repeat_mode controls runtime; legacy child knobs are migration-only."),
    _control("$.memory_policy.automatic_repeat_mode", "RuntimeConfigIR.automatic_memory_policy", "Controls kernel automatic-repeat interception."),
    _migration("$.memory_policy.require_query_before_repeat", "Legacy solver ritual; automatic memory owns repeat handling."),
    _migration("$.memory_policy.require_query_before_overwrite", "Legacy solver ritual; no runtime consumer."),
    _migration("$.memory_policy.index_by", "Legacy metadata index hint; no runtime consumer."),
    _control("$.verification_policy", "compile_visible_smoke_tests", "Only typed visible smoke tests control compilation; unsupported structural checks fail closed."),
    _control("$.verification_policy.visible_smoke_tests", "compile_visible_smoke_tests", "Compiles supported typed visible checks into evidence checks."),
    _migration("$.verification_policy.structural_checks", "No canonical executor; non-empty values are rejected before Solver start."),
    _migration("$.verification_policy.solver_callable_checks", "Legacy quality-rubric knob; no runtime consumer."),
    _control("$.model_verifier_policy", "RuntimeConfigIR.model_verifier_policy", "Controls the internal verifier gate and trigger."),
    _control("$.model_verifier_policy.enabled", "RuntimeConfigIR.model_verifier_policy", "Controls the internal verifier gate."),
    _control("$.model_verifier_policy.runs_on", "RuntimeConfigIR.model_verifier_policy", "Constrains verifier trigger to solver_submit."),
    _control("$.reconfigure_policy", "RuntimeConfigIR.reconfigure_policy", "Only max_versions and allowed_owners control non-certified reconfiguration."),
    _control("$.reconfigure_policy.max_versions", "RuntimeConfigIR.reconfigure_policy", "Bounds non-certified reconfiguration versions."),
    _control("$.reconfigure_policy.allowed_owners", "RuntimeConfigIR.reconfigure_policy", "Constrains non-certified reconfiguration owners."),
    _migration("$.reconfigure_policy.enabled", "Certified production suspends model-authored reconfiguration; flag has no consumer."),
    _advisory("$.evidence_requirements", "Natural completion evidence recorded for verifier/ledger context.", "RuntimeConfigIR.evidence_requirements"),
    _advisory("$.false_positive_risks", "Task-specific false-success warnings recorded for verifier context.", "RuntimeConfigIR.false_positive_risks"),
    _advisory("$.minimum_completion_evidence", "Minimum evidence guidance recorded for verifier context.", "RuntimeConfigIR.minimum_completion_evidence"),
    _control("$.re_derivable_claims", "RuntimeConfigIR.re_derivable_claims", "Triggers independent-derivation verifier requirements."),
    _advisory("$.failure_feedback_policy", "Legacy feedback display policy retained only as explicit metadata."),
    _migration("$.failure_feedback_policy.persist_until", "ActiveFindingStore owns persistence semantics."),
    _migration("$.failure_feedback_policy.show_age_steps", "No runtime consumer."),
    _migration("$.failure_feedback_policy.show_evidence", "Evidence visibility is kernel-owned."),
    _control("$.helper_script_policy", "RuntimeConfigIR.helper_tool_policy", "Only enabled and directory control helper realization; trust is kernel-owned."),
    _control("$.helper_script_policy.enabled", "RuntimeConfigIR.helper_tool_policy.allow_creation", "Controls helper creation when required capabilities exist."),
    _control("$.helper_script_policy.directory", "RuntimeConfigIR.helper_tool_policy.task_local_dir", "Controls the task-local helper directory."),
    _migration("$.helper_script_policy.trust_level", "Helper output is never completion authority; trust is kernel-owned."),
    _advisory("$.local_verification_limits", "Limits and caveats recorded in runtime/verifier metadata.", "RuntimeConfigIR.local_verification_limits"),
    _advisory("$.expected_steps", "Advisory efficiency expectation only; never an execution or completion gate.", "config_realization.expected_steps/result-row step_efficiency"),
)


def validate_field_realization_manifest() -> None:
    """Fail closed if the manifest itself declares an unrealized control."""
    seen: set[str] = set()
    valid_authorities = {ARCHITECT_RUNTIME_CONTROL, KERNEL_INVARIANT, ADVISORY_METADATA, MIGRATION_ONLY}
    for entry in FIELD_REALIZATION_MANIFEST:
        if entry.path in seen:
            raise RuntimeError(f"duplicate Architect field manifest path: {entry.path}")
        seen.add(entry.path)
        if entry.authority not in valid_authorities:
            raise RuntimeError(f"unknown Architect field authority: {entry.authority}")
        if entry.authority == ARCHITECT_RUNTIME_CONTROL and not entry.runtime_consumer:
            raise RuntimeError(f"controlling Architect field has no runtime consumer: {entry.path}")


def field_realization_manifest_as_dicts() -> list[dict[str, object]]:
    validate_field_realization_manifest()
    return [asdict(entry) for entry in FIELD_REALIZATION_MANIFEST]


validate_field_realization_manifest()

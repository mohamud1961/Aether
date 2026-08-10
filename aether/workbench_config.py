"""HarnessConfigIR v1: typed workbench architecture emitted by vNext architect.

This module is intentionally non-invasive for the first implementation slice:
it defines and validates the target schema without changing the legacy runtime
path until the compiler is ready to consume all fields.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .context_views import (
    TOP_LEVEL_CONTEXT_SECTION_SELECTORS,
    _RECENT_RECIPE_SELECTORS,
    _SUPPORTED_EXACT_RECIPE_SELECTORS,
)
from .model_hooks import ModelOutputError, _extract_json_object
from .proof_contract import ROUTE_EVIDENCE_CEILINGS
from .runtime_manual import (
    ALLOWED_VISIBLE_SMOKE_TEST_TYPES,
    SUPPORTED_CONTEXT_POLICIES,
    SUPPORTED_SYNTAX_CHECK_LANGUAGES,
)
from .runtime_ir import ACTION_SCHEMA, AUTOMATIC_MEMORY_POLICY_MODES, ContextRecipe, ContextRecipeRecent

ALLOWED_SMOKE_TEST_TYPES = frozenset(ALLOWED_VISIBLE_SMOKE_TEST_TYPES)
UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE = "unsupported_visible_smoke_test_type_quarantined"
RAW_COMMAND_VISIBLE_SMOKE_TEST_CODE = "raw_command_visible_smoke_test_quarantined"
# Legacy Workbench output may still contain ``tool_policy``.  It is parsed only
# for compatibility and is never allowed to control the kernel action surface.
LEGACY_TOOL_SELECTION_WARNING_CODE = "legacy_tool_selection_ignored_fixed_kernel_surface"
# These paths remain parseable only so older captured Architect outputs can be
# inspected and migrated.  They are deliberately absent from the model-facing
# contract and have no authority over the certified runtime.
DEPRECATED_MIGRATION_FIELD_PATHS = frozenset({
    "$.tool_policy",
    "$.reconfigure_policy.enabled",
    "$.memory_policy.require_query_before_repeat",
    "$.memory_policy.require_query_before_overwrite",
    "$.memory_policy.index_by",
    "$.verification_policy.structural_checks",
    "$.verification_policy.solver_callable_checks",
    "$.failure_feedback_policy.persist_until",
    "$.failure_feedback_policy.show_age_steps",
    "$.failure_feedback_policy.show_evidence",
    "$.helper_script_policy.trust_level",
})
SUPPORTED_TOP_LEVEL_CONFIG_FIELDS = frozenset({
    "schema_version",
    "task_understanding",
    "visible_contract",
    "success_definition",
    "solver_system_prompt",
    "verifier_system_prompt",
    "clause_coverage",
    "verifier_strategy",
    "reconfigure_policy",
    "evidence_requirements",
    "false_positive_risks",
    "minimum_completion_evidence",
    "re_derivable_claims",
    "tool_policy",
    "context_policy",
    "memory_policy",
    "verification_policy",
    "model_verifier_policy",
    "failure_feedback_policy",
    "helper_script_policy",
    "local_verification_limits",
    "expected_steps",
})

SUPPORTED_EVIDENCE_CLASSES = frozenset({
    "shape", "metadata_proxy", "solver_authored_test", "same_method",
    "behavioral", "exact_contract", "independent_semantic",
})


@dataclass(frozen=True)
class SolverPromptSpec:
    role: str
    workflow: tuple[str, ...] = ()
    self_verification: tuple[str, ...] = ()
    memory_use: tuple[str, ...] = ()
    stop_conditions: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()

    def render(self) -> str:
        sections = [f"Role: {self.role}"]
        for title, values in (
            ("Workflow", self.workflow),
            ("Self-verification", self.self_verification),
            ("Memory/query use", self.memory_use),
            ("Stop conditions", self.stop_conditions),
            ("Avoid", self.avoid),
        ):
            if values:
                sections.append(title + ":\n" + "\n".join(f"- {v}" for v in values))
        return "\n\n".join(sections)


@dataclass(frozen=True)
class VerifierPromptSpec:
    role: str
    success_criteria: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    false_positive_traps: tuple[str, ...] = ()
    verdict_guidance: tuple[str, ...] = ()
    feedback_guidance: tuple[str, ...] = ()

    def render(self) -> str:
        sections = [f"Role: {self.role}"]
        for title, values in (
            ("Task-specific success criteria", self.success_criteria),
            ("Required evidence for completed", self.required_evidence),
            ("False-positive traps", self.false_positive_traps),
            ("Verdict guidance", self.verdict_guidance),
            ("Feedback guidance", self.feedback_guidance),
        ):
            if values:
                sections.append(title + ":\n" + "\n".join(f"- {v}" for v in values))
        return "\n\n".join(sections)


@dataclass(frozen=True)
class ClauseCoverageSpec:
    clause_id: str
    solver_handling: str
    verifier_check: str


@dataclass(frozen=True)
class VisibleContractSpec:
    literal: str
    meaning: str
    contrast: str = ""
    kind: str = "literal"
    owner: str = ""
    exact_type: str = ""
    contrast_owner: str = ""

    @property
    def is_scoped(self) -> bool:
        return self.kind in {"scoped_symbol", "owned_symbol"}

    @property
    def required_binding(self) -> str:
        return f"{self.owner}.{self.literal}" if self.is_scoped else self.literal

    @property
    def contrast_binding(self) -> str:
        if not self.contrast:
            return ""
        return (
            f"{self.contrast_owner}.{self.contrast}"
            if self.is_scoped and self.contrast_owner
            else self.contrast
        )

    def as_dict(self) -> dict[str, Any]:
        if self.kind == "constrained_literal":
            return {
                "kind": self.kind,
                "literal": self.literal,
                "exact_type": self.exact_type,
                "meaning": self.meaning,
                "contrast": self.contrast,
            }
        if self.kind == "owned_symbol":
            return {
                "kind": self.kind,
                "owner": self.owner,
                "literal": self.literal,
                "exact_type": self.exact_type,
                "meaning": self.meaning,
                "contrast_owner": self.contrast_owner,
                "contrast": self.contrast,
            }
        if self.kind == "scoped_symbol":
            return {
                "kind": self.kind,
                "owner": self.owner,
                "literal": self.literal,
                "meaning": self.meaning,
                "contrast_owner": self.contrast_owner,
                "contrast": self.contrast,
            }
        return {
            "kind": "literal",
            "literal": self.literal,
            "meaning": self.meaning,
            "contrast": self.contrast,
        }


@dataclass(frozen=True)
class VerifierClauseCheckSpec:
    clause_id: str
    inspection_route: str
    fallback_route: str | None
    falsification_check: str
    required_evidence_class: str
    proof_obligation: str = "exact_state"


@dataclass(frozen=True)
class ReconfigurePolicySpec:
    enabled: bool = True
    max_versions: int = 2
    allowed_owners: tuple[str, ...] = ("harness_config",)


@dataclass(frozen=True)
class ToolPolicySpec:
    enabled_tools: tuple[str, ...]
    disabled_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextPolicySpec:
    mode: str = "default_bounded"
    always_include: tuple[str, ...] = ()
    include_on_failure: tuple[str, ...] = ()
    # Architect-settable working-context view budget (tokens). Ceiling, not
    # target; see runtime_ir.ContextPolicy.model_context_window_tokens.
    model_context_window_tokens: int = 50_000
    recipe: ContextRecipe | None = None


@dataclass(frozen=True)
class MemoryPolicySpec:
    require_query_before_repeat: bool = True
    require_query_before_overwrite: bool = True
    index_by: tuple[str, ...] = ("path", "action_kind", "check_id", "failure_kind")
    automatic_repeat_mode: str = "advisory"


@dataclass(frozen=True)
class VerificationPolicySpec:
    structural_checks: tuple[dict[str, Any], ...] = ()
    visible_smoke_tests: tuple[dict[str, Any], ...] = ()
    solver_callable_checks: bool = True


@dataclass(frozen=True)
class ModelVerifierPolicySpec:
    enabled: bool = True
    runs_on: tuple[str, ...] = ("solver_submit",)


@dataclass(frozen=True)
class FailureFeedbackPolicySpec:
    persist_until: str = "resolved_or_superseded"
    show_age_steps: bool = True
    show_evidence: bool = True


@dataclass(frozen=True)
class HelperScriptPolicySpec:
    enabled: bool = True
    directory: str = "/app/.aether_tools"
    trust_level: str = "advisory"


@dataclass(frozen=True)
class HarnessConfigIR:
    schema_version: str
    task_understanding: str
    success_definition: str
    solver_system_prompt: SolverPromptSpec
    visible_contract: tuple[VisibleContractSpec, ...] = ()
    tool_policy: ToolPolicySpec = field(default_factory=lambda: ToolPolicySpec(enabled_tools=()))
    verifier_system_prompt: VerifierPromptSpec = field(default_factory=lambda: VerifierPromptSpec(role="Task-specific evidence verifier"))
    clause_coverage: tuple[ClauseCoverageSpec, ...] = ()
    verifier_strategy: tuple[VerifierClauseCheckSpec, ...] = ()
    verifier_false_positive_traps: tuple[str, ...] = ()
    reconfigure_policy: ReconfigurePolicySpec = field(default_factory=ReconfigurePolicySpec)
    evidence_requirements: tuple[str, ...] = ()
    false_positive_risks: tuple[str, ...] = ()
    minimum_completion_evidence: tuple[str, ...] = ()
    # Optional: claims whose correctness the reviewer can independently
    # re-derive (counts, frame indices, decoded/parsed values, field names,
    # hashes). Empty means unflagged -- unchanged legacy behavior. See
    # verify_completion_protocol.py's independence-kind gate.
    re_derivable_claims: tuple[str, ...] = ()
    context_policy: ContextPolicySpec = field(default_factory=ContextPolicySpec)
    memory_policy: MemoryPolicySpec = field(default_factory=MemoryPolicySpec)
    verification_policy: VerificationPolicySpec = field(default_factory=VerificationPolicySpec)
    model_verifier_policy: ModelVerifierPolicySpec = field(default_factory=ModelVerifierPolicySpec)
    failure_feedback_policy: FailureFeedbackPolicySpec = field(default_factory=FailureFeedbackPolicySpec)
    helper_script_policy: HelperScriptPolicySpec = field(default_factory=HelperScriptPolicySpec)
    local_verification_limits: tuple[str, ...] = ()
    repair_warning_codes: tuple[str, ...] = ()
    repair_warnings: tuple[str, ...] = ()
    rejected_config_items: tuple[dict[str, Any], ...] = ()
    legacy_tool_selection_paths: tuple[str, ...] = ()
    legacy_tool_selection_warning: str = ""
    # Paths accepted for migration/audit compatibility but excluded from the
    # model-facing v1 contract and ignored by runtime compilation.
    deprecated_field_paths: tuple[str, ...] = ()
    expected_steps: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Preserve byte-stable compatibility for historical configs created
        # before the model-facing visible-contract ledger existed. Canonicalize
        # present rows through their typed model-facing representation.
        if not self.visible_contract:
            payload.pop("visible_contract", None)
        else:
            payload["visible_contract"] = [item.as_dict() for item in self.visible_contract]
        return payload


@dataclass(frozen=True)
class HarnessConfigParseRepair:
    config: HarnessConfigIR | None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()
    rejected_config_items: tuple[dict[str, Any], ...] = ()
    raw_output: str = ""
    repaired_json: str | None = None


def _tuple_str(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    if isinstance(value, str):
        return (value,)
    return ()


def _dict_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def _parse_visible_contract(value: Any) -> tuple[VisibleContractSpec, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ModelOutputError("visible_contract must be an array")
    rows: list[VisibleContractSpec] = []
    seen_literal_rows: set[tuple[str, str, str]] = set()
    scoped_by_binding: dict[tuple[str, str], VisibleContractSpec] = {}
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ModelOutputError(f"visible_contract[{index}] must be an object")

        # Current provider rows are uniform and omit the historical `kind`.
        # Presence/absence of owner and requirement mechanically determines
        # the runtime rendering; this is structural projection, not semantic
        # extraction or repair.
        uniform = "kind" not in item and any(
            key in item for key in ("owner", "requirement", "contrast_owner")
        )
        if uniform:
            allowed = {"literal", "owner", "requirement", "meaning", "contrast", "contrast_owner"}
            unknown = sorted(set(item) - allowed)
            if unknown:
                raise ModelOutputError(
                    f"visible_contract[{index}] has unsupported fields: " + ", ".join(unknown)
                )
            literal = str(item.get("literal", "")).strip()
            meaning = str(item.get("meaning", "")).strip()
            contrast = str(item.get("contrast", "")).strip()
            raw_owner = item.get("owner")
            raw_requirement = item.get("requirement")
            raw_contrast_owner = item.get("contrast_owner")
            owner = "" if raw_owner is None else str(raw_owner).strip()
            exact_type = "" if raw_requirement is None else str(raw_requirement).strip()
            contrast_owner = "" if raw_contrast_owner is None else str(raw_contrast_owner).strip()
            if raw_owner is not None and not owner:
                raise ModelOutputError(f"visible_contract[{index}].owner must be non-empty or null")
            if raw_requirement is not None and not exact_type:
                raise ModelOutputError(f"visible_contract[{index}].requirement must be non-empty or null")
            if raw_contrast_owner is not None and not contrast_owner:
                raise ModelOutputError(f"visible_contract[{index}].contrast_owner must be non-empty or null")
            if not literal:
                raise ModelOutputError(f"visible_contract[{index}].literal is required")
            if not meaning:
                raise ModelOutputError(f"visible_contract[{index}].meaning is required")
            if owner:
                kind = "owned_symbol" if exact_type else "scoped_symbol"
                if contrast_owner and not contrast:
                    raise ModelOutputError(
                        f"visible_contract[{index}].contrast_owner requires a non-empty contrast"
                    )
                if contrast and owner == contrast_owner and literal == contrast:
                    raise ModelOutputError(
                        f"visible_contract[{index}] required and contrast bindings must differ"
                    )
            else:
                kind = "constrained_literal" if exact_type else "literal"
                if contrast_owner:
                    raise ModelOutputError(
                        f"visible_contract[{index}].contrast_owner requires an immediate owner"
                    )
        else:
            # Historical rows remain readable exactly as captured.
            kind = str(item.get("kind", "literal")).strip() or "literal"
            if kind == "literal":
                allowed = {"kind", "literal", "meaning", "contrast"}
            elif kind == "constrained_literal":
                allowed = {"kind", "literal", "exact_type", "meaning", "contrast"}
            elif kind == "owned_symbol":
                allowed = {
                    "kind", "owner", "literal", "exact_type", "meaning",
                    "contrast_owner", "contrast",
                }
            elif kind == "scoped_symbol":
                allowed = {
                    "kind", "owner", "literal", "meaning", "contrast_owner", "contrast",
                }
            else:
                raise ModelOutputError(
                    f"visible_contract[{index}].kind must be literal, constrained_literal, scoped_symbol, or owned_symbol"
                )
            unknown = sorted(set(item) - allowed)
            if unknown:
                raise ModelOutputError(
                    f"visible_contract[{index}] has unsupported fields: " + ", ".join(unknown)
                )
            literal = str(item.get("literal", "")).strip()
            meaning = str(item.get("meaning", "")).strip()
            contrast = str(item.get("contrast", "")).strip()
            owner = str(item.get("owner", "")).strip()
            exact_type = str(item.get("exact_type", "")).strip()
            contrast_owner = str(item.get("contrast_owner", "")).strip()
            if not literal:
                raise ModelOutputError(f"visible_contract[{index}].literal is required")
            if not meaning:
                raise ModelOutputError(f"visible_contract[{index}].meaning is required")
            if kind in {"scoped_symbol", "owned_symbol"}:
                if not owner:
                    raise ModelOutputError(f"visible_contract[{index}].owner is required")
                if kind == "owned_symbol" and not exact_type:
                    raise ModelOutputError(f"visible_contract[{index}].exact_type is required")
                if kind == "scoped_symbol" and exact_type:
                    raise ModelOutputError(
                        f"visible_contract[{index}] scoped_symbol cannot carry exact_type"
                    )
                if bool(contrast_owner) != bool(contrast):
                    raise ModelOutputError(
                        f"visible_contract[{index}] contrast_owner and contrast must both be set or both be empty"
                    )
                if contrast and owner == contrast_owner and literal == contrast:
                    raise ModelOutputError(
                        f"visible_contract[{index}] required and contrast bindings must differ"
                    )
            elif kind == "constrained_literal":
                if owner or contrast_owner:
                    raise ModelOutputError(
                        f"visible_contract[{index}] constrained_literal cannot carry owner fields"
                    )
                if not exact_type:
                    raise ModelOutputError(
                        f"visible_contract[{index}].exact_type is required"
                    )
            elif owner or exact_type or contrast_owner:
                raise ModelOutputError(
                    f"visible_contract[{index}] literal rows cannot carry scoped-symbol fields"
                )

        row = VisibleContractSpec(
            kind=kind,
            owner=owner,
            literal=literal,
            exact_type=exact_type,
            meaning=meaning,
            contrast_owner=contrast_owner,
            contrast=contrast,
        )
        if kind in {"literal", "constrained_literal"}:
            literal_key = (literal, meaning, contrast, exact_type)
            if literal_key in seen_literal_rows:
                continue
            seen_literal_rows.add(literal_key)
        else:
            binding_key = (owner, literal)
            previous = scoped_by_binding.get(binding_key)
            if previous is not None:
                if previous == row:
                    continue
                raise ModelOutputError(
                    f"visible_contract[{index}] conflicts with an earlier binding: {row.required_binding}"
                )
            scoped_by_binding[binding_key] = row
        rows.append(row)
    return tuple(rows)


def _parse_semantic_evidence_contract(
    data: dict[str, Any],
    *,
    require_complete: bool = False,
) -> tuple[tuple[ClauseCoverageSpec, ...], tuple[VerifierClauseCheckSpec, ...], tuple[str, ...]]:
    """Parse optional V4-style clause coverage and verifier strategy fields.

    Older v1 configs remain parseable but are marked uncompiled by the
    compiler.  A config that supplies either structured section must supply a
    complete, typed section; malformed or partial semantic contracts fail
    before Solver start rather than degrading to prose-only evidence.
    """
    raw_coverage = data.get("clause_coverage", ())
    if raw_coverage in (None, ()):
        coverage: tuple[ClauseCoverageSpec, ...] = ()
    else:
        if not isinstance(raw_coverage, list):
            raise ModelOutputError("clause_coverage must be a list")
        rows: list[ClauseCoverageSpec] = []
        for index, item in enumerate(raw_coverage):
            if not isinstance(item, dict):
                raise ModelOutputError(f"clause_coverage[{index}] must be an object")
            unknown = sorted(set(item) - {"clause_id", "solver_handling", "verifier_check"})
            if unknown:
                raise ModelOutputError(f"unsupported fields in clause_coverage[{index}]: {', '.join(unknown)}")
            values = {key: str(item.get(key, "")).strip() for key in ("clause_id", "solver_handling", "verifier_check")}
            if not all(values.values()):
                raise ModelOutputError(f"clause_coverage[{index}] requires clause_id, solver_handling, verifier_check")
            rows.append(ClauseCoverageSpec(**values))
        coverage = tuple(rows)
        coverage_ids = [item.clause_id for item in coverage]
        if len(set(coverage_ids)) != len(coverage_ids):
            raise ModelOutputError("clause_coverage clause_id values must be unique")

    raw_strategy = data.get("verifier_strategy", {})
    if raw_strategy in (None, {}):
        if coverage:
            raise ModelOutputError("verifier_strategy is required when clause_coverage is present")
        if require_complete:
            raise ModelOutputError("production Architect output requires non-empty clause_coverage and verifier_strategy")
        return (), (), ()
    _reject_unknown_nested_fields("verifier_strategy", raw_strategy)
    if not isinstance(raw_strategy, dict):
        raise ModelOutputError("verifier_strategy must be an object")
    raw_checks = raw_strategy.get("clause_checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        raise ModelOutputError("verifier_strategy.clause_checks must be a non-empty list")
    checks: list[VerifierClauseCheckSpec] = []
    for index, item in enumerate(raw_checks):
        if not isinstance(item, dict):
            raise ModelOutputError(f"verifier_strategy.clause_checks[{index}] must be an object")
        allowed = {"clause_id", "proof_obligation", "inspection_route", "fallback_route", "falsification_check", "required_evidence_class"}
        unknown = sorted(set(item) - allowed)
        if unknown:
            raise ModelOutputError(f"unsupported fields in verifier_strategy.clause_checks[{index}]: {', '.join(unknown)}")
        values = {key: str(item.get(key, "")).strip() for key in ("clause_id", "inspection_route", "falsification_check", "required_evidence_class")}
        values["proof_obligation"] = str(item.get("proof_obligation", "exact_state")).strip() or "exact_state"
        if not all(values.values()):
            raise ModelOutputError(f"verifier_strategy.clause_checks[{index}] is incomplete")
        if values["proof_obligation"] not in {"exact_state", "public_behavior", "generated_interface_semantics"}:
            raise ModelOutputError(f"unknown proof obligation: {values['proof_obligation']}")
        if values["required_evidence_class"] not in SUPPORTED_EVIDENCE_CLASSES:
            raise ModelOutputError(f"unknown evidence class: {values['required_evidence_class']}")
        route_kind = values["inspection_route"].split(":", 1)[0].strip()
        if route_kind not in ROUTE_EVIDENCE_CEILINGS:
            raise ModelOutputError(f"unsupported verifier inspection route: {route_kind}")
        fallback = item.get("fallback_route")
        fallback_route = str(fallback).strip() if fallback is not None else None
        if fallback_route:
            fallback_kind = fallback_route.split(":", 1)[0].strip()
            if fallback_kind not in ROUTE_EVIDENCE_CEILINGS:
                raise ModelOutputError(f"unsupported verifier fallback route: {fallback_kind}")
        checks.append(VerifierClauseCheckSpec(
            **values,
            fallback_route=fallback_route,
        ))
    traps = _tuple_str(raw_strategy.get("false_positive_traps", ()))
    if not traps:
        raise ModelOutputError("verifier_strategy.false_positive_traps must not be empty")
    if raw_strategy.get("return_all_findings", True) is not True:
        raise ModelOutputError("verifier_strategy.return_all_findings must remain true")
    if not coverage:
        raise ModelOutputError("clause_coverage is required when verifier_strategy is present")
    coverage_ids = {item.clause_id for item in coverage}
    check_ids = [item.clause_id for item in checks]
    if len(set(check_ids)) != len(check_ids):
        raise ModelOutputError("verifier_strategy clause_id values must be unique")
    if coverage_ids != set(check_ids):
        missing = sorted(coverage_ids - set(check_ids))
        extra = sorted(set(check_ids) - coverage_ids)
        raise ModelOutputError(
            "clause_coverage and verifier_strategy clause_id values must match exactly; "
            f"missing_checks={missing}, extra_checks={extra}"
        )
    return coverage, tuple(checks), traps


_NESTED_CONFIG_FIELDS: dict[str, frozenset[str]] = {
    "solver_system_prompt": frozenset({
        "role", "workflow", "self_verification", "memory_use", "stop_conditions", "avoid",
    }),
    "verifier_system_prompt": frozenset({
        "role", "success_criteria", "required_evidence", "false_positive_traps",
        "verdict_guidance", "feedback_guidance",
    }),
    "verifier_strategy": frozenset({"clause_checks", "false_positive_traps", "return_all_findings"}),
    "reconfigure_policy": frozenset({"enabled", "max_versions", "allowed_owners"}),
    # ``tool_policy`` is retained solely for legacy compatibility.  Its
    # contents are recorded as non-authoritative guidance, but unknown keys
    # are still rejected instead of silently discarded.
    "tool_policy": frozenset({"enabled_tools", "disabled_tools"}),
    "context_policy": frozenset({
        "mode", "always_include", "include_on_failure", "model_context_window_tokens", "recipe",
    }),
    "context_policy.recipe": frozenset({
        "always_include", "include_recent", "include_last_failure", "preserve_exact",
        "make_queryable_not_inline",
    }),
    "memory_policy": frozenset({
        "require_query_before_repeat", "require_query_before_overwrite", "index_by", "automatic_repeat_mode",
    }),
    "verification_policy": frozenset({"structural_checks", "visible_smoke_tests", "solver_callable_checks"}),
    "model_verifier_policy": frozenset({"enabled", "runs_on"}),
    "failure_feedback_policy": frozenset({"persist_until", "show_age_steps", "show_evidence"}),
    "helper_script_policy": frozenset({"enabled", "directory", "trust_level"}),
}


def _reject_unknown_nested_fields(path: str, value: Any) -> None:
    """Fail closed for unknown nested config keys.

    Architect output is model-authored input.  Dropping a misspelled nested
    field creates a false realization receipt, so every typed object is
    checked before coercion/defaulting.  The visible-smoke quarantine path may
    still salvage only its explicitly supported smoke-test entries; it does
    not bypass this contract.
    """
    if value is None and path == "context_policy.recipe":
        return
    if not isinstance(value, dict):
        raise ModelOutputError(f"{path} must be an object")
    allowed = _NESTED_CONFIG_FIELDS[path]
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ModelOutputError(
            f"unsupported fields in {path}: " + ", ".join(unknown)
        )


def _deprecated_field_paths(data: dict[str, Any]) -> tuple[str, ...]:
    """Return deprecated fields present in a legacy Architect payload."""
    paths: list[str] = []
    if "tool_policy" in data:
        paths.append("$.tool_policy")
    for section, fields in (
        ("reconfigure_policy", ("enabled",)),
        ("memory_policy", ("require_query_before_repeat", "require_query_before_overwrite", "index_by")),
        ("verification_policy", ("structural_checks", "solver_callable_checks")),
        ("failure_feedback_policy", ("persist_until", "show_age_steps", "show_evidence")),
        ("helper_script_policy", ("trust_level",)),
    ):
        value = data.get(section, {})
        if isinstance(value, dict):
            paths.extend(f"$.{section}.{field_name}" for field_name in fields if field_name in value)
    return tuple(path for path in paths if path in DEPRECATED_MIGRATION_FIELD_PATHS)


def _nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _selector_values(value: Any, *, path: str) -> tuple[str, ...]:
    if value in (None, (), []):
        return ()
    if isinstance(value, str):
        values = (value.strip(),)
    elif isinstance(value, (list, tuple)):
        if not all(isinstance(item, str) and item.strip() for item in value):
            raise ModelOutputError(f"{path} must contain non-empty strings")
        values = tuple(item.strip() for item in value)
    else:
        raise ModelOutputError(f"{path} must be a string or list of strings")
    return tuple(item for item in values if item)


def _validate_context_policy_values(ctx_raw: dict[str, Any]) -> None:
    for field_name in ("always_include", "include_on_failure"):
        values = _selector_values(ctx_raw.get(field_name, ()), path=f"context_policy.{field_name}")
        invalid = sorted(set(values) - TOP_LEVEL_CONTEXT_SECTION_SELECTORS)
        if invalid:
            raise ModelOutputError(
                f"unsupported context_policy.{field_name} selectors: {', '.join(invalid)}"
            )

    recipe = ctx_raw.get("recipe")
    if recipe in (None, {}):
        return
    if not isinstance(recipe, dict):
        raise ModelOutputError("context_policy.recipe must be an object")
    for field_name in ("always_include", "preserve_exact", "make_queryable_not_inline"):
        values = _selector_values(
            recipe.get(field_name, ()), path=f"context_policy.recipe.{field_name}"
        )
        invalid = sorted(set(values) - _SUPPORTED_EXACT_RECIPE_SELECTORS)
        if invalid:
            raise ModelOutputError(
                f"unsupported context_policy.recipe.{field_name} selectors: {', '.join(invalid)}"
            )
    include_recent = recipe.get("include_recent", [])
    if include_recent in (None, (), []):
        recent_rows = []
    elif isinstance(include_recent, dict):
        recent_rows = [
            {"selector": str(selector), "count": raw_count}
            for selector, raw_count in include_recent.items()
        ]
    elif isinstance(include_recent, list):
        recent_rows = include_recent
    else:
        raise ModelOutputError(
            "context_policy.recipe.include_recent must be an array of selector/count objects"
        )
    selectors: list[str] = []
    for index, row in enumerate(recent_rows):
        if not isinstance(row, dict):
            raise ModelOutputError(
                f"context_policy.recipe.include_recent[{index}] must be an object"
            )
        unknown = sorted(set(row) - {"selector", "count"})
        if unknown:
            raise ModelOutputError(
                f"unsupported fields in context_policy.recipe.include_recent[{index}]: "
                + ", ".join(unknown)
            )
        selector = str(row.get("selector", "")).strip()
        if selector not in _RECENT_RECIPE_SELECTORS:
            raise ModelOutputError(
                f"unsupported context_policy.recipe.include_recent selectors: {selector}"
            )
        if selector in selectors:
            raise ModelOutputError(
                f"duplicate context_policy.recipe.include_recent selector: {selector}"
            )
        selectors.append(selector)
        raw_count = row.get("count")
        if isinstance(raw_count, bool):
            raise ModelOutputError(
                f"context_policy.recipe.include_recent[{index}].count must be a non-negative integer"
            )
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            raise ModelOutputError(
                f"context_policy.recipe.include_recent[{index}].count must be a non-negative integer"
            ) from None
        if count < 0:
            raise ModelOutputError(
                f"context_policy.recipe.include_recent[{index}].count must be a non-negative integer"
            )
    last_failure = recipe.get("include_last_failure", 0)
    if isinstance(last_failure, bool):
        raise ModelOutputError("context_policy.recipe.include_last_failure must be a non-negative integer")
    try:
        parsed_last_failure = int(last_failure)
    except (TypeError, ValueError):
        raise ModelOutputError("context_policy.recipe.include_last_failure must be a non-negative integer") from None
    if parsed_last_failure < 0:
        raise ModelOutputError("context_policy.recipe.include_last_failure must be a non-negative integer")


def _parse_context_recipe(value: Any) -> ContextRecipe | None:
    if not isinstance(value, dict):
        return None
    allowed_fields = {
        "always_include",
        "include_recent",
        "include_last_failure",
        "preserve_exact",
        "make_queryable_not_inline",
    }
    include_recent_raw = value.get("include_recent", ())
    include_recent: list[ContextRecipeRecent] = []
    if isinstance(include_recent_raw, dict):
        include_recent_rows = [
            {"selector": selector, "count": count}
            for selector, count in include_recent_raw.items()
        ]
    elif isinstance(include_recent_raw, list):
        include_recent_rows = include_recent_raw
    else:
        include_recent_rows = []
    for item in include_recent_rows:
        if isinstance(item, dict):
            include_recent.append(
                ContextRecipeRecent(
                    selector=str(item.get("selector", "")),
                    count=_nonnegative_int(item.get("count")),
                )
            )
    return ContextRecipe(
        always_include=_tuple_str(value.get("always_include", ())),
        include_recent=tuple(include_recent),
        include_last_failure=_nonnegative_int(value.get("include_last_failure", 0)),
        preserve_exact=_tuple_str(value.get("preserve_exact", ())),
        make_queryable_not_inline=_tuple_str(value.get("make_queryable_not_inline", ())),
        unsupported_fields=tuple(
            str(field_name)
            for field_name in value
            if str(field_name) not in allowed_fields
        ),
    )


def _validate_smoke_tests(items: tuple[dict[str, Any], ...]) -> None:
    for item in items:
        smoke_type = str(item.get("type", "")).strip()
        if smoke_type not in ALLOWED_SMOKE_TEST_TYPES:
            raise ModelOutputError(f"unsupported visible smoke test type: {smoke_type}")
        if "command" in item:
            raise ModelOutputError("visible smoke tests must be typed specs, not raw commands")
        if smoke_type == "syntax_check":
            language = item.get("language")
            if language is not None and str(language).strip().lower() not in SUPPORTED_SYNTAX_CHECK_LANGUAGES:
                raise ModelOutputError(
                    "unsupported syntax_check language: " + str(language)
                )
        allowed = {
            "type", "path", "target", "artifact_path", "language", "contains",
            "not_contains", "assertions", "min_bytes", "argv", "stdin_file",
        }
        unknown = sorted(set(item) - allowed)
        if unknown:
            raise ModelOutputError(
                "unsupported fields in verification_policy.visible_smoke_tests item: "
                + ", ".join(unknown)
            )


def _reject_unimplemented_structural_checks(value: Any) -> None:
    """Reject verifier structural checks until a runtime owner exists.

    The canonical compiler currently has an executable path for typed visible
    smoke checks, but no evaluator for ``structural_checks``.  Accepting this
    field and then retaining only its count in the realization receipt would
    silently discard architect authority.  Fail closed before Solver start
    rather than pretending the checks are enforced.
    """
    if value in (None, (), []):
        return
    if not isinstance(value, list):
        raise ModelOutputError(
            "verification_policy.structural_checks must be a list; "
            "structural_checks are unsupported in canonical workbench mode"
        )
    raise ModelOutputError(
        "verification_policy.structural_checks are unsupported in canonical "
        "workbench mode; use supported typed visible_smoke_tests or explicit "
        "verifier evidence requirements"
    )


def _load_harness_config_data(text: str) -> dict[str, Any]:
    raw_json = _extract_json_object(text)
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ModelOutputError("expected a JSON object")
    return data


def _quarantine_visible_smoke_tests(
    data: dict[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...], tuple[dict[str, Any], ...]]:
    ver_raw = data.get("verification_policy", {})
    if not isinstance(ver_raw, dict):
        return data, (), (), ()
    smoke_tests = ver_raw.get("visible_smoke_tests", ())
    if not isinstance(smoke_tests, list):
        return data, (), (), ()

    kept: list[Any] = []
    warnings: list[str] = []
    warning_codes: list[str] = []
    rejected: list[dict[str, Any]] = []
    changed = False
    for idx, item in enumerate(smoke_tests):
        if not isinstance(item, dict):
            kept.append(item)
            continue
        smoke_type = str(item.get("type", "")).strip()
        path = f"verification_policy.visible_smoke_tests[{idx}]"
        if "command" in item:
            changed = True
            warning_codes.append(RAW_COMMAND_VISIBLE_SMOKE_TEST_CODE)
            message = (
                f"Removed {path}: raw command smoke tests are never authoritative; "
                "the item was quarantined and not compiled."
            )
            warnings.append(message)
            rejected.append({
                "status": "quarantined",
                "path": path,
                "reason_code": RAW_COMMAND_VISIBLE_SMOKE_TEST_CODE,
                "message": message,
                "original_item": dict(item),
            })
            continue
        if smoke_type not in ALLOWED_SMOKE_TEST_TYPES:
            changed = True
            warning_codes.append(UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE)
            message = (
                f"Removed {path}: unsupported visible smoke test type {smoke_type!r}; "
                f"allowed types are {list(ALLOWED_VISIBLE_SMOKE_TEST_TYPES)}."
            )
            warnings.append(message)
            rejected.append({
                "status": "quarantined",
                "path": path,
                "reason_code": UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE,
                "message": message,
                "original_item": dict(item),
            })
            continue
        kept.append(dict(item))

    if not changed:
        return data, (), (), ()

    repaired_verification = dict(ver_raw)
    repaired_verification["visible_smoke_tests"] = kept
    repaired = dict(data)
    repaired["verification_policy"] = repaired_verification
    return repaired, tuple(warnings), tuple(warning_codes), tuple(rejected)


def parse_harness_config_ir(
    text: str,
    *,
    require_semantic_contract: bool = False,
) -> HarnessConfigIR:
    """Parse strict JSON model output into HarnessConfigIR v1.

    ``require_semantic_contract`` is enabled for live production Architect
    output.  The default remains false only so historical captured configs can
    still be inspected and migrated without rewriting evidence.
    """
    data = _load_harness_config_data(text)
    deprecated_field_paths = _deprecated_field_paths(data)
    if str(data.get("schema_version", "")) != "harness_config.v1":
        raise ModelOutputError("schema_version must be harness_config.v1")
    unsupported_top_level = sorted(set(data) - SUPPORTED_TOP_LEVEL_CONFIG_FIELDS)
    if unsupported_top_level:
        raise ModelOutputError(
            "unsupported top-level HarnessConfigIR fields: "
            + ", ".join(unsupported_top_level)
        )
    solver_raw = data.get("solver_system_prompt", {})
    for path in (
        "solver_system_prompt", "verifier_system_prompt",
        "context_policy", "memory_policy", "verification_policy",
        "model_verifier_policy", "failure_feedback_policy", "helper_script_policy",
        "reconfigure_policy",
    ):
        _reject_unknown_nested_fields(path, data.get(path, {}))
    if "tool_policy" in data:
        _reject_unknown_nested_fields("tool_policy", data.get("tool_policy", {}))
    context_raw_for_validation = data.get("context_policy", {})
    if isinstance(context_raw_for_validation, dict):
        _reject_unknown_nested_fields(
            "context_policy.recipe", context_raw_for_validation.get("recipe", {})
        )
    if not isinstance(solver_raw, dict) or not str(solver_raw.get("role", "")).strip():
        raise ModelOutputError("solver_system_prompt.role is required")
    verifier_raw = data.get("verifier_system_prompt", {})
    if not isinstance(verifier_raw, dict) or not str(verifier_raw.get("role", "")).strip():
        raise ModelOutputError("verifier_system_prompt.role is required")
    if not _tuple_str(verifier_raw.get("success_criteria", ())):
        raise ModelOutputError("verifier_system_prompt.success_criteria must not be empty")
    if not _tuple_str(verifier_raw.get("required_evidence", ())):
        raise ModelOutputError("verifier_system_prompt.required_evidence must not be empty")
    tools_raw = data.get("tool_policy", {})
    if not isinstance(tools_raw, dict):
        raise ModelOutputError("legacy tool_policy must be an object when present")
    enabled = _tuple_str(tools_raw.get("enabled_tools", ()))
    # Empty enabled_tools means "no architect tool preference" in stable-core mode.
    # The harness still exposes the stable core toolset unless env/safety forbids it.
    known_tools = {name for name, _ in ACTION_SCHEMA}
    unknown = sorted(set(enabled) - known_tools)
    if unknown:
        raise ModelOutputError(f"unknown enabled tools: {', '.join(unknown)}")
    ctx_raw = data.get("context_policy", {})
    if not isinstance(ctx_raw, dict):
        ctx_raw = {}
    _validate_context_policy_values(ctx_raw)
    mode = str(ctx_raw.get("mode", "default_bounded"))
    if mode not in SUPPORTED_CONTEXT_POLICIES:
        raise ModelOutputError(f"unsupported context policy: {mode}")
    window_raw = ctx_raw.get("model_context_window_tokens", 50_000)
    try:
        context_window_tokens = int(window_raw)
    except (TypeError, ValueError):
        raise ModelOutputError(
            "context_policy.model_context_window_tokens must be an integer"
        ) from None
    if not 1_000 <= context_window_tokens <= 400_000:
        raise ModelOutputError(
            "context_policy.model_context_window_tokens must be between 1000 and 400000"
        )
    mem_raw = data.get("memory_policy", {}) if isinstance(data.get("memory_policy", {}), dict) else {}
    automatic_repeat_mode = str(mem_raw.get("automatic_repeat_mode", "advisory")).strip() or "advisory"
    if automatic_repeat_mode not in AUTOMATIC_MEMORY_POLICY_MODES:
        raise ModelOutputError(f"unsupported automatic memory repeat mode: {automatic_repeat_mode}")
    ver_raw = data.get("verification_policy", {}) if isinstance(data.get("verification_policy", {}), dict) else {}
    _reject_unimplemented_structural_checks(ver_raw.get("structural_checks", ()))
    smoke_tests = _dict_tuple(ver_raw.get("visible_smoke_tests", ()))
    _validate_smoke_tests(smoke_tests)
    model_ver_raw = data.get("model_verifier_policy", {}) if isinstance(data.get("model_verifier_policy", {}), dict) else {}
    model_verifier_runs_on = _tuple_str(model_ver_raw.get("runs_on", ("solver_submit",)))
    if model_verifier_runs_on != ("solver_submit",):
        raise ModelOutputError(
            "model_verifier_policy.runs_on must be exactly ['solver_submit'] "
            "in canonical workbench mode"
        )
    feedback_raw = data.get("failure_feedback_policy", {}) if isinstance(data.get("failure_feedback_policy", {}), dict) else {}
    helper_raw = data.get("helper_script_policy", {}) if isinstance(data.get("helper_script_policy", {}), dict) else {}
    reconfigure_raw = data.get("reconfigure_policy", {})
    if not isinstance(reconfigure_raw, dict):
        raise ModelOutputError("reconfigure_policy must be an object")
    allowed_owners = _tuple_str(reconfigure_raw.get("allowed_owners", ("harness_config",)))
    invalid_owners = sorted(set(allowed_owners) - {"harness_config", "verifier_tooling", "environment"})
    if invalid_owners or "solver_state" in allowed_owners:
        raise ModelOutputError("unsupported reconfiguration owners: " + ", ".join(invalid_owners or ["solver_state"]))
    try:
        max_versions = int(reconfigure_raw.get("max_versions", 2))
    except (TypeError, ValueError):
        raise ModelOutputError("reconfigure_policy.max_versions must be an integer") from None
    if max_versions < 1:
        raise ModelOutputError("reconfigure_policy.max_versions must be >= 1")
    reconfigure_policy = ReconfigurePolicySpec(
        enabled=bool(reconfigure_raw.get("enabled", True)),
        max_versions=max_versions,
        allowed_owners=allowed_owners,
    )
    clause_coverage, verifier_strategy, verifier_false_positive_traps = _parse_semantic_evidence_contract(
        data, require_complete=require_semantic_contract
    )
    solver_prompt = SolverPromptSpec(
        role=str(solver_raw.get("role", "")).strip(),
        workflow=_tuple_str(solver_raw.get("workflow", ())),
        self_verification=_tuple_str(solver_raw.get("self_verification", ())),
        memory_use=_tuple_str(solver_raw.get("memory_use", ())),
        stop_conditions=_tuple_str(solver_raw.get("stop_conditions", ())),
        avoid=_tuple_str(solver_raw.get("avoid", ())),
    )
    verifier_prompt = VerifierPromptSpec(
        role=str(verifier_raw.get("role", "")).strip(),
        success_criteria=_tuple_str(verifier_raw.get("success_criteria", ())),
        required_evidence=_tuple_str(verifier_raw.get("required_evidence", ())),
        false_positive_traps=_tuple_str(verifier_raw.get("false_positive_traps", ())),
        verdict_guidance=_tuple_str(verifier_raw.get("verdict_guidance", ())),
        feedback_guidance=_tuple_str(verifier_raw.get("feedback_guidance", ())),
    )
    # The reduced provider contract has one model-authored authority per fact.
    # Historical full configs preserve their explicit mirror prose exactly;
    # new reduced configs mechanically project mirrors from canonical authored
    # sections so existing runtime consumers keep the same typed interface.
    task_understanding = str(data.get("task_understanding", "")).strip() or solver_prompt.role
    success_definition = str(data.get("success_definition", "")).strip() or " ".join(
        item.verifier_check for item in clause_coverage
    )
    evidence_requirements = (
        _tuple_str(data.get("evidence_requirements", ())) or verifier_prompt.required_evidence
    )
    false_positive_risks = _tuple_str(data.get("false_positive_risks", ())) or tuple(
        dict.fromkeys((*verifier_prompt.false_positive_traps, *verifier_false_positive_traps))
    )
    minimum_completion_evidence = (
        _tuple_str(data.get("minimum_completion_evidence", ()))
        or verifier_prompt.required_evidence
    )
    local_verification_limits = _tuple_str(data.get("local_verification_limits", ()))
    return HarnessConfigIR(
        schema_version="harness_config.v1",
        task_understanding=task_understanding,
        visible_contract=_parse_visible_contract(data.get("visible_contract")),
        expected_steps=_parse_expected_steps(data.get("expected_steps")),
        success_definition=success_definition,
        solver_system_prompt=solver_prompt,
        verifier_system_prompt=verifier_prompt,
        clause_coverage=clause_coverage,
        verifier_strategy=verifier_strategy,
        verifier_false_positive_traps=verifier_false_positive_traps,
        reconfigure_policy=reconfigure_policy,
        evidence_requirements=evidence_requirements,
        false_positive_risks=false_positive_risks,
        minimum_completion_evidence=minimum_completion_evidence,
        re_derivable_claims=_tuple_str(data.get("re_derivable_claims", ())),
        tool_policy=ToolPolicySpec(
            enabled_tools=enabled,
            disabled_tools=_tuple_str(tools_raw.get("disabled_tools", ())),
        ),
        context_policy=ContextPolicySpec(
            mode=mode,
            always_include=_tuple_str(ctx_raw.get("always_include", ())),
            include_on_failure=_tuple_str(ctx_raw.get("include_on_failure", ())),
            model_context_window_tokens=context_window_tokens,
            recipe=_parse_context_recipe(ctx_raw.get("recipe")),
        ),
        memory_policy=MemoryPolicySpec(
            require_query_before_repeat=bool(mem_raw.get("require_query_before_repeat", True)),
            require_query_before_overwrite=bool(mem_raw.get("require_query_before_overwrite", True)),
            index_by=_tuple_str(mem_raw.get("index_by", ("path", "action_kind", "check_id", "failure_kind"))),
            automatic_repeat_mode=automatic_repeat_mode,
        ),
        verification_policy=VerificationPolicySpec(
            structural_checks=_dict_tuple(ver_raw.get("structural_checks", ())),
            visible_smoke_tests=smoke_tests,
            solver_callable_checks=bool(ver_raw.get("solver_callable_checks", True)),
        ),
        model_verifier_policy=ModelVerifierPolicySpec(
            enabled=bool(model_ver_raw.get("enabled", True)),
            runs_on=model_verifier_runs_on,
        ),
        failure_feedback_policy=FailureFeedbackPolicySpec(
            persist_until=str(feedback_raw.get("persist_until", "resolved_or_superseded")),
            show_age_steps=bool(feedback_raw.get("show_age_steps", True)),
            show_evidence=bool(feedback_raw.get("show_evidence", True)),
        ),
        helper_script_policy=HelperScriptPolicySpec(
            enabled=bool(helper_raw.get("enabled", True)),
            directory=str(helper_raw.get("directory", "/app/.aether_tools")),
            trust_level=str(helper_raw.get("trust_level", "advisory")),
        ),
        local_verification_limits=local_verification_limits,
        legacy_tool_selection_paths=("$.tool_policy",) if "tool_policy" in data else (),
        legacy_tool_selection_warning=(
            LEGACY_TOOL_SELECTION_WARNING_CODE if "tool_policy" in data else ""
        ),
        deprecated_field_paths=deprecated_field_paths,
    )


def parse_workbench_architect_output(
    text: str,
    *,
    require_semantic_contract: bool = False,
) -> HarnessConfigParseRepair:
    """Parse architect output, salvaging only quarantinable visible smoke tests."""
    try:
        config = parse_harness_config_ir(
            text, require_semantic_contract=require_semantic_contract
        )
        return HarnessConfigParseRepair(config=config, raw_output=text)
    except Exception as exc:
        strict_error = str(exc)

    try:
        data = _load_harness_config_data(text)
    except Exception:
        return HarnessConfigParseRepair(config=None, errors=(strict_error,), raw_output=text)

    repaired_data, warnings, warning_codes, rejected = _quarantine_visible_smoke_tests(data)
    if not warnings:
        return HarnessConfigParseRepair(config=None, errors=(strict_error,), raw_output=text)

    repaired_json = json.dumps(repaired_data)
    try:
        repaired_config = parse_harness_config_ir(
            repaired_json, require_semantic_contract=require_semantic_contract
        )
    except Exception as exc:
        return HarnessConfigParseRepair(
            config=None,
            errors=(strict_error, f"repair parse failed: {exc}"),
            warnings=warnings,
            warning_codes=warning_codes,
            rejected_config_items=rejected,
            raw_output=text,
            repaired_json=repaired_json,
        )

    repaired_config = replace(
        repaired_config,
        repair_warning_codes=warning_codes,
        repair_warnings=warnings,
        rejected_config_items=rejected,
    )
    return HarnessConfigParseRepair(
        config=repaired_config,
        errors=warnings,
        warnings=warnings,
        warning_codes=warning_codes,
        rejected_config_items=rejected,
        raw_output=text,
        repaired_json=repaired_json,
    )


def _parse_expected_steps(raw: object) -> int:
    """Advisory step-budget expectation; never a runtime gate."""
    try:
        value = int(float(raw))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return value if 0 < value <= 500 else 0

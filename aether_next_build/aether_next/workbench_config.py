"""HarnessConfigIR v1: typed workbench architecture emitted by vNext architect.

This module is intentionally non-invasive for the first implementation slice:
it defines and validates the target schema without changing the legacy runtime
path until the compiler is ready to consume all fields.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .model_hooks import ModelOutputError, _extract_json_object
from .runtime_manual import ALLOWED_VISIBLE_SMOKE_TEST_TYPES, SUPPORTED_CONTEXT_POLICIES
from .runtime_ir import ACTION_SCHEMA, AUTOMATIC_MEMORY_POLICY_MODES, ContextRecipe, ContextRecipeRecent

ALLOWED_SMOKE_TEST_TYPES = frozenset(ALLOWED_VISIBLE_SMOKE_TEST_TYPES)
UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE = "unsupported_visible_smoke_test_type_quarantined"
RAW_COMMAND_VISIBLE_SMOKE_TEST_CODE = "raw_command_visible_smoke_test_quarantined"
SUPPORTED_TOP_LEVEL_CONFIG_FIELDS = frozenset({
    "schema_version",
    "task_understanding",
    "success_definition",
    "solver_system_prompt",
    "verifier_system_prompt",
    "evidence_requirements",
    "false_positive_risks",
    "minimum_completion_evidence",
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
class ToolPolicySpec:
    enabled_tools: tuple[str, ...]
    disabled_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextPolicySpec:
    mode: str = "default_bounded"
    always_include: tuple[str, ...] = ()
    include_on_failure: tuple[str, ...] = ()
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
    tool_policy: ToolPolicySpec
    verifier_system_prompt: VerifierPromptSpec = field(default_factory=lambda: VerifierPromptSpec(role="Task-specific evidence verifier"))
    evidence_requirements: tuple[str, ...] = ()
    false_positive_risks: tuple[str, ...] = ()
    minimum_completion_evidence: tuple[str, ...] = ()
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
    expected_steps: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def _nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


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
    include_recent_raw = value.get("include_recent", {})
    include_recent: list[ContextRecipeRecent] = []
    if isinstance(include_recent_raw, dict):
        for selector, count in include_recent_raw.items():
            include_recent.append(
                ContextRecipeRecent(
                    selector=str(selector),
                    count=_nonnegative_int(count),
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


def parse_harness_config_ir(text: str) -> HarnessConfigIR:
    """Parse strict JSON model output into HarnessConfigIR v1."""
    data = _load_harness_config_data(text)
    if str(data.get("schema_version", "")) != "harness_config.v1":
        raise ModelOutputError("schema_version must be harness_config.v1")
    unsupported_top_level = sorted(set(data) - SUPPORTED_TOP_LEVEL_CONFIG_FIELDS)
    if unsupported_top_level:
        raise ModelOutputError(
            "unsupported top-level HarnessConfigIR fields: "
            + ", ".join(unsupported_top_level)
        )
    solver_raw = data.get("solver_system_prompt", {})
    if not isinstance(solver_raw, dict) or not str(solver_raw.get("role", "")).strip():
        raise ModelOutputError("solver_system_prompt.role is required")
    verifier_raw = data.get("verifier_system_prompt", {})
    if not isinstance(verifier_raw, dict) or not str(verifier_raw.get("role", "")).strip():
        raise ModelOutputError("verifier_system_prompt.role is required")
    if not str(data.get("task_understanding", "")).strip():
        raise ModelOutputError("task_understanding is required")
    if not str(data.get("success_definition", "")).strip():
        raise ModelOutputError("success_definition is required")
    if not _tuple_str(data.get("evidence_requirements", ())):
        raise ModelOutputError("evidence_requirements must not be empty")
    if not _tuple_str(data.get("minimum_completion_evidence", ())):
        raise ModelOutputError("minimum_completion_evidence must not be empty")
    if not _tuple_str(verifier_raw.get("success_criteria", ())):
        raise ModelOutputError("verifier_system_prompt.success_criteria must not be empty")
    if not _tuple_str(verifier_raw.get("required_evidence", ())):
        raise ModelOutputError("verifier_system_prompt.required_evidence must not be empty")
    tools_raw = data.get("tool_policy", {})
    if not isinstance(tools_raw, dict):
        raise ModelOutputError("tool_policy object is required")
    enabled = _tuple_str(tools_raw.get("enabled_tools", ()))
    if not enabled:
        raise ModelOutputError("tool_policy.enabled_tools must not be empty")
    known_tools = {name for name, _ in ACTION_SCHEMA}
    unknown = sorted(set(enabled) - known_tools)
    if unknown:
        raise ModelOutputError(f"unknown enabled tools: {', '.join(unknown)}")
    ctx_raw = data.get("context_policy", {})
    if not isinstance(ctx_raw, dict):
        ctx_raw = {}
    mode = str(ctx_raw.get("mode", "default_bounded"))
    if mode not in SUPPORTED_CONTEXT_POLICIES:
        raise ModelOutputError(f"unsupported context policy: {mode}")
    mem_raw = data.get("memory_policy", {}) if isinstance(data.get("memory_policy", {}), dict) else {}
    automatic_repeat_mode = str(mem_raw.get("automatic_repeat_mode", "advisory")).strip() or "advisory"
    if automatic_repeat_mode not in AUTOMATIC_MEMORY_POLICY_MODES:
        raise ModelOutputError(f"unsupported automatic memory repeat mode: {automatic_repeat_mode}")
    ver_raw = data.get("verification_policy", {}) if isinstance(data.get("verification_policy", {}), dict) else {}
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
    return HarnessConfigIR(
        schema_version="harness_config.v1",
        task_understanding=str(data.get("task_understanding", "")).strip(),
        expected_steps=_parse_expected_steps(data.get("expected_steps")),
        success_definition=str(data.get("success_definition", "")).strip(),
        solver_system_prompt=SolverPromptSpec(
            role=str(solver_raw.get("role", "")).strip(),
            workflow=_tuple_str(solver_raw.get("workflow", ())),
            self_verification=_tuple_str(solver_raw.get("self_verification", ())),
            memory_use=_tuple_str(solver_raw.get("memory_use", ())),
            stop_conditions=_tuple_str(solver_raw.get("stop_conditions", ())),
            avoid=_tuple_str(solver_raw.get("avoid", ())),
        ),
        verifier_system_prompt=VerifierPromptSpec(
            role=str(verifier_raw.get("role", "")).strip(),
            success_criteria=_tuple_str(verifier_raw.get("success_criteria", ())),
            required_evidence=_tuple_str(verifier_raw.get("required_evidence", ())),
            false_positive_traps=_tuple_str(verifier_raw.get("false_positive_traps", ())),
            verdict_guidance=_tuple_str(verifier_raw.get("verdict_guidance", ())),
            feedback_guidance=_tuple_str(verifier_raw.get("feedback_guidance", ())),
        ),
        evidence_requirements=_tuple_str(data.get("evidence_requirements", ())),
        false_positive_risks=_tuple_str(data.get("false_positive_risks", ())),
        minimum_completion_evidence=_tuple_str(data.get("minimum_completion_evidence", ())),
        tool_policy=ToolPolicySpec(
            enabled_tools=enabled,
            disabled_tools=_tuple_str(tools_raw.get("disabled_tools", ())),
        ),
        context_policy=ContextPolicySpec(
            mode=mode,
            always_include=_tuple_str(ctx_raw.get("always_include", ())),
            include_on_failure=_tuple_str(ctx_raw.get("include_on_failure", ())),
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
        local_verification_limits=_tuple_str(data.get("local_verification_limits", ())),
    )


def parse_workbench_architect_output(text: str) -> HarnessConfigParseRepair:
    """Parse architect output, salvaging only quarantinable visible smoke tests."""
    try:
        config = parse_harness_config_ir(text)
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
        repaired_config = parse_harness_config_ir(repaired_json)
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

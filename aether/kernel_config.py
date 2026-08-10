"""Config resolution logic extracted from kernel.run().

Pure function that resolves a RuntimeConfigIR into a fully-compiled runtime,
handling the architect/validate/repair/fail-closed pipeline.
The kernel records trace/receipts from the returned ``ResolvedRuntime``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, TYPE_CHECKING

from .architect_v3_adapter import architect_v3_runtime_ir
from .architect_v3_model import build_architect_v3_model_request
from .compiler import ConfigCompiler
from .kernel_messages import build_architect_request
from .repair import repair_config
from .persistent_primary import persistent_primary_runtime_ir
from .runtime_ir import (
    CompiledRuntime,
    EnvMap,
    EvalIndex,
    ObjectiveGraph,
    RuntimeConfigIR,
)
from .smoke_compile import compile_visible_smoke_tests
from .workbench_compile import harness_config_to_runtime_ir

if TYPE_CHECKING:
    from .architect_v3_contract import ArchitectV3Contract
    from .architect_v3_model import ArchitectV3Model
    from .workbench_hooks import WorkbenchArchitect


# ---------------------------------------------------------------------------
# Frozen result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResolvedRuntime:
    """Outcome of config resolution: everything the kernel needs to run."""

    runtime_ir: RuntimeConfigIR
    compiled: CompiledRuntime | None
    objective_graph: ObjectiveGraph
    eval_index: EvalIndex
    repair_codes: tuple[str, ...]
    fallback_codes: tuple[str, ...]
    config_invalid_blockers: tuple[str, ...]
    workbench_config: Any | None = None
    architect_v3_contract: "ArchitectV3Contract | None" = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _baseline_resolve(
    envmap: EnvMap,
    compiler: ConfigCompiler,
    hooks: Any,
) -> ResolvedRuntime:
    """Resolve runtime using the standard IR architect path."""
    objective_graph, eval_index = compiler.analyze_envmap(envmap)
    request = build_architect_request(envmap, compiler)
    try:
        runtime_ir = hooks.architect(request)
    except Exception as exc:
        blockers = ("architect_config_parse_failed", str(exc))
        return ResolvedRuntime(
            runtime_ir=_invalid_runtime_ir("architect parse failed"),
            compiled=None,
            objective_graph=objective_graph,
            eval_index=eval_index,
            repair_codes=(),
            fallback_codes=blockers,
            config_invalid_blockers=blockers,
        )

    issues = compiler.validate(
        runtime_ir, envmap,
        objective_graph=objective_graph, eval_index=eval_index,
    )
    fatal_issues = [issue for issue in issues if issue.fatal]
    fallback_codes: tuple[str, ...] = ()
    repair_codes: tuple[str, ...] = ()

    if fatal_issues:
        repaired_ir, rep_codes = repair_config(
            runtime_ir, compiler, envmap,
            objective_graph=objective_graph, eval_index=eval_index,
        )
        post_repair_issues = compiler.validate(
            repaired_ir, envmap,
            objective_graph=objective_graph, eval_index=eval_index,
        )
        post_repair_fatal = [i for i in post_repair_issues if i.fatal]
        if not post_repair_fatal:
            runtime_ir = repaired_ir
            repair_codes = rep_codes
        else:
            fallback_codes = tuple(issue.code for issue in fatal_issues)
            runtime_ir = _invalid_runtime_ir("baseline config validation failed")
            return ResolvedRuntime(
                runtime_ir=runtime_ir,
                compiled=None,
                objective_graph=objective_graph,
                eval_index=eval_index,
                repair_codes=repair_codes,
                fallback_codes=fallback_codes,
                config_invalid_blockers=fallback_codes,
            )

    compiled = compiler.compile(
        runtime_ir, envmap,
        objective_graph=objective_graph, eval_index=eval_index,
    )
    semantic_status = str(compiled.config_realization.get("semantic_evidence_status", ""))
    if semantic_status.startswith("invalid_"):
        blockers = (f"semantic_evidence_{semantic_status}",)
        return ResolvedRuntime(
            runtime_ir=_invalid_runtime_ir("semantic evidence contract invalid"),
            compiled=None,
            objective_graph=objective_graph,
            eval_index=eval_index,
            repair_codes=repair_codes,
            fallback_codes=blockers,
            config_invalid_blockers=blockers,
            workbench_config=None,
        )
    return ResolvedRuntime(
        runtime_ir=runtime_ir,
        compiled=compiled,
        objective_graph=objective_graph,
        eval_index=eval_index,
        repair_codes=repair_codes,
        fallback_codes=fallback_codes,
        config_invalid_blockers=(),
    )


def _invalid_runtime_ir(reason: str) -> RuntimeConfigIR:
    """Non-executable placeholder for failed initialization.

    Failed architect/config output must never be represented as a generic safe
    default. ``ResolvedRuntime`` still carries a RuntimeConfigIR for trace/result
    shape compatibility, but callers must see ``compiled=None`` and
    ``config_invalid_blockers`` and stop before the solver.
    """
    return RuntimeConfigIR(
        architect_summary=f"[invalid config -- {reason}]",
        solver_identity_prompt="",
        selected_capabilities=(),
    )


def _architect_v3_resolve(
    envmap: EnvMap,
    compiler: ConfigCompiler,
    architect: "ArchitectV3Model",
    *,
    reconfigure_context: Mapping[str, Any] | None = None,
) -> ResolvedRuntime:
    """Resolve the certified V3 contract with one call and no semantic repair."""
    objective_graph, eval_index = compiler.analyze_envmap(envmap)
    if reconfigure_context is not None:
        blockers = ("architect_v3_reconfiguration_not_supported",)
        return ResolvedRuntime(
            runtime_ir=_invalid_runtime_ir("Architect v3 reconfiguration is disabled"),
            compiled=None, objective_graph=objective_graph, eval_index=eval_index,
            repair_codes=(), fallback_codes=blockers,
            config_invalid_blockers=blockers, architect_v3_contract=None,
        )
    request = build_architect_v3_model_request(envmap)
    result = architect.configure(request)
    if not result.valid or result.contract is None:
        blockers = (
            "architect_v3_configure_failed",
            *(str(item) for item in result.errors),
        )
        return ResolvedRuntime(
            runtime_ir=_invalid_runtime_ir("Architect v3 configure failed"),
            compiled=None, objective_graph=objective_graph, eval_index=eval_index,
            repair_codes=(), fallback_codes=blockers,
            config_invalid_blockers=blockers, architect_v3_contract=None,
        )
    try:
        runtime_ir = architect_v3_runtime_ir(result.contract, envmap, eval_index)
        issues = compiler.validate(
            runtime_ir, envmap,
            objective_graph=objective_graph, eval_index=eval_index,
        )
        fatal = tuple(issue for issue in issues if issue.fatal)
        if fatal:
            blockers = tuple(
                f"architect_v3_validation:{issue.code}:{issue.message}"
                for issue in fatal
            )
            return ResolvedRuntime(
                runtime_ir=_invalid_runtime_ir("Architect v3 validation failed"),
                compiled=None, objective_graph=objective_graph, eval_index=eval_index,
                repair_codes=(), fallback_codes=blockers,
                config_invalid_blockers=blockers,
                architect_v3_contract=result.contract,
            )
        compiled = compiler.compile(
            runtime_ir, envmap,
            objective_graph=objective_graph, eval_index=eval_index,
        )
    except Exception as exc:
        blockers = (f"architect_v3_compile:{type(exc).__name__}:{exc}",)
        return ResolvedRuntime(
            runtime_ir=_invalid_runtime_ir("Architect v3 compilation failed"),
            compiled=None, objective_graph=objective_graph, eval_index=eval_index,
            repair_codes=(), fallback_codes=blockers,
            config_invalid_blockers=blockers,
            architect_v3_contract=result.contract,
        )
    return ResolvedRuntime(
        runtime_ir=runtime_ir, compiled=compiled,
        objective_graph=objective_graph, eval_index=eval_index,
        repair_codes=(), fallback_codes=(), config_invalid_blockers=(),
        architect_v3_contract=result.contract,
    )


def _persistent_primary_resolve(
    envmap: EnvMap,
    compiler: ConfigCompiler,
    *,
    reconfigure_context: Mapping[str, Any] | None = None,
) -> ResolvedRuntime:
    """Resolve PERSISTENT V0 mechanically with zero Architect model calls."""
    objective_graph, eval_index = compiler.analyze_envmap(envmap)
    if reconfigure_context is not None:
        blockers = ("persistent_primary_reconfiguration_not_supported",)
        return ResolvedRuntime(
            runtime_ir=_invalid_runtime_ir("PERSISTENT V0 reconfiguration is disabled"),
            compiled=None,
            objective_graph=objective_graph,
            eval_index=eval_index,
            repair_codes=(),
            fallback_codes=blockers,
            config_invalid_blockers=blockers,
        )
    try:
        runtime_ir = persistent_primary_runtime_ir(envmap, eval_index)
        issues = compiler.validate(
            runtime_ir,
            envmap,
            objective_graph=objective_graph,
            eval_index=eval_index,
        )
        fatal = tuple(issue for issue in issues if issue.fatal)
        if fatal:
            blockers = tuple(
                f"persistent_primary_validation:{issue.code}:{issue.message}"
                for issue in fatal
            )
            return ResolvedRuntime(
                runtime_ir=_invalid_runtime_ir("PERSISTENT V0 validation failed"),
                compiled=None,
                objective_graph=objective_graph,
                eval_index=eval_index,
                repair_codes=(),
                fallback_codes=blockers,
                config_invalid_blockers=blockers,
            )
        compiled = compiler.compile(
            runtime_ir,
            envmap,
            objective_graph=objective_graph,
            eval_index=eval_index,
        )
    except Exception as exc:
        blockers = (f"persistent_primary_compile:{type(exc).__name__}:{exc}",)
        return ResolvedRuntime(
            runtime_ir=_invalid_runtime_ir("PERSISTENT V0 compilation failed"),
            compiled=None,
            objective_graph=objective_graph,
            eval_index=eval_index,
            repair_codes=(),
            fallback_codes=blockers,
            config_invalid_blockers=blockers,
        )
    return ResolvedRuntime(
        runtime_ir=runtime_ir,
        compiled=compiled,
        objective_graph=objective_graph,
        eval_index=eval_index,
        repair_codes=(),
        fallback_codes=(),
        config_invalid_blockers=(),
    )



def _workbench_resolve(
    envmap: EnvMap,
    compiler: ConfigCompiler,
    hooks: Any,
    workbench_architect: "WorkbenchArchitect",
    *,
    reconfigure_context: Mapping[str, Any] | None = None,
) -> ResolvedRuntime:
    """Resolve vNext config, allowing one model correction before Solver start."""
    objective_graph, base_eval_index = compiler.analyze_envmap(envmap)
    request = build_architect_request(envmap, compiler)
    if reconfigure_context is not None:
        request = dict(request)
        request["reconfigure_context"] = dict(reconfigure_context)
    config, errors = workbench_architect.configure(request)
    if config is None:
        blockers = ("workbench_architect_configure_failed",) + tuple(str(err) for err in errors)
        return ResolvedRuntime(
            runtime_ir=_invalid_runtime_ir("workbench architect configure failed"),
            compiled=None,
            objective_graph=objective_graph,
            eval_index=base_eval_index,
            repair_codes=(), fallback_codes=blockers,
            config_invalid_blockers=blockers, workbench_config=None,
        )

    def materialize(candidate: Any) -> tuple[
        RuntimeConfigIR | None, CompiledRuntime | None, EvalIndex,
        tuple[str, ...], tuple[str, ...]
    ]:
        eval_index = base_eval_index
        smoke_result = compile_visible_smoke_tests(candidate, envmap)
        if smoke_result.checks:
            eval_index = EvalIndex(checks=eval_index.checks + smoke_result.checks)
        runtime_ir = harness_config_to_runtime_ir(candidate, envmap)
        if smoke_result.checks:
            runtime_ir = replace(
                runtime_ir,
                check_plan=runtime_ir.check_plan + tuple(check.check_id for check in smoke_result.checks),
                advisory_notes=runtime_ir.advisory_notes + (
                    f"compiled_visible_smoke_checks={len(smoke_result.checks)}",
                ),
            )
        if smoke_result.rejected:
            runtime_ir = replace(
                runtime_ir,
                advisory_notes=runtime_ir.advisory_notes + (
                    "visible_smoke_compile_rejections=" + str([dict(item) for item in smoke_result.rejected]),
                ),
            )
        issues = compiler.validate(
            runtime_ir, envmap,
            objective_graph=objective_graph, eval_index=eval_index,
        )
        fatal = [issue for issue in issues if issue.fatal]
        repair_codes: tuple[str, ...] = ()
        if fatal:
            repaired_ir, rep_codes = repair_config(
                runtime_ir, compiler, envmap,
                objective_graph=objective_graph, eval_index=eval_index,
            )
            post = compiler.validate(
                repaired_ir, envmap,
                objective_graph=objective_graph, eval_index=eval_index,
            )
            post_fatal = [issue for issue in post if issue.fatal]
            if post_fatal:
                findings = tuple(
                    f"validation:{issue.code}:{issue.message}" for issue in post_fatal
                )
                return None, None, eval_index, (), findings
            runtime_ir = repaired_ir
            repair_codes = tuple(rep_codes)
        try:
            compiled = compiler.compile(
                runtime_ir, envmap,
                objective_graph=objective_graph, eval_index=eval_index,
            )
        except Exception as exc:
            finding = f"compile:{type(exc).__name__}:{exc}"
            return None, None, eval_index, repair_codes, (finding,)
        return runtime_ir, compiled, eval_index, repair_codes, ()

    runtime_ir, compiled, eval_index, repair_codes, findings = materialize(config)
    if compiled is None:
        correct = getattr(workbench_architect, "correct", None)
        if not callable(correct):
            blockers = ("workbench_architect_config_invalid",) + findings
            return ResolvedRuntime(
                runtime_ir=_invalid_runtime_ir("workbench config validation or compilation failed"),
                compiled=None, objective_graph=objective_graph, eval_index=eval_index,
                repair_codes=repair_codes, fallback_codes=blockers,
                config_invalid_blockers=blockers, workbench_config=config,
            )
        corrected, correction_errors = correct(
            request,
            previous_output=str(getattr(workbench_architect, "last_raw_output", "")),
            findings=list(findings),
        )
        if corrected is None:
            blockers = (
                "workbench_architect_correction_failed",
                *findings,
                *(str(err) for err in correction_errors),
            )
            return ResolvedRuntime(
                runtime_ir=_invalid_runtime_ir("workbench architect correction failed"),
                compiled=None, objective_graph=objective_graph, eval_index=eval_index,
                repair_codes=repair_codes, fallback_codes=blockers,
                config_invalid_blockers=blockers, workbench_config=config,
            )
        config = corrected
        runtime_ir, compiled, eval_index, corrected_repairs, second_findings = materialize(config)
        repair_codes = ("workbench_architect_model_correction",) + corrected_repairs
        if compiled is None or runtime_ir is None:
            blockers = ("workbench_architect_corrected_config_invalid",) + second_findings
            return ResolvedRuntime(
                runtime_ir=_invalid_runtime_ir("corrected workbench config invalid"),
                compiled=None, objective_graph=objective_graph, eval_index=eval_index,
                repair_codes=repair_codes, fallback_codes=blockers,
                config_invalid_blockers=blockers, workbench_config=config,
            )

    assert runtime_ir is not None and compiled is not None
    return ResolvedRuntime(
        runtime_ir=runtime_ir, compiled=compiled,
        objective_graph=objective_graph, eval_index=eval_index,
        repair_codes=repair_codes, fallback_codes=(),
        config_invalid_blockers=(), workbench_config=config,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_runtime(
    envmap: EnvMap,
    compiler: ConfigCompiler,
    hooks: Any,
    *,
    workbench_architect: "WorkbenchArchitect | None" = None,
    architect_v3_architect: "ArchitectV3Model | None" = None,
    persistent_primary: bool = False,
    reconfigure_context: Mapping[str, Any] | None = None,
) -> ResolvedRuntime:
    """Resolve a full runtime configuration from an envmap.

    When no architect override is provided, reproduces the original kernel
    baseline path exactly.  ``workbench_architect`` enables the vNext
    HarnessConfigIR path and fails closed on configuration failure.
    ``reconfigure_context``, when set, marks this as a mid-run reconfiguration
    and is folded into the workbench architect request (see
    ``_workbench_resolve``); it is a no-op for the other two paths.
    """
    active_paths = sum((
        workbench_architect is not None,
        architect_v3_architect is not None,
        bool(persistent_primary),
    ))
    if active_paths > 1:
        raise ValueError("only one runtime resolution path may be active")
    if persistent_primary:
        return _persistent_primary_resolve(
            envmap,
            compiler,
            reconfigure_context=reconfigure_context,
        )
    if architect_v3_architect is not None:
        return _architect_v3_resolve(
            envmap, compiler, architect_v3_architect,
            reconfigure_context=reconfigure_context,
        )
    if workbench_architect is not None:
        return _workbench_resolve(
            envmap, compiler, hooks, workbench_architect,
            reconfigure_context=reconfigure_context,
        )
    return _baseline_resolve(envmap, compiler, hooks)

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Iterable

from .analysis import (
    EvalIndexer,
    ObjectiveGraphBuilder,
    _dedupe_preserve,
)
from .runtime_ir import (
    ACTION_SCHEMA,
    ALWAYS_AVAILABLE_ACTION_KINDS,
    MODEL_TIERS,
    WORKFLOW_MODES,
    BootstrapPolicy,
    CapabilityDescriptor,
    CompletionPolicy,
    CompiledRuntime,
    ConfigIssue,
    EnvMap,
    EvalIndex,
    HelperToolPolicy,
    ObjectiveGraph,
    ProcessPolicy,
    RefusalPolicy,
    RuntimeConfigIR,
    WorkflowPolicy,
    normalize_relpath,
    stable_json,
)

_VAGUE_PHRASES = (
    "be careful",
    "verify properly",
    "solve efficiently",
    "use the best tool",
    "do the right thing",
)
_ALLOWED_PROCESS_MODES = {"stateless_shell", "managed_service", "interactive_detachable"}
_MAX_SELECTED_CAPABILITIES = 10

_DEFAULT_CAPABILITY_TOOLS = {
    "shell": ("run_command",),
    "filesystem": ("read_file", "write_file"),
    "managed_process": ("launch_process", "probe_service", "stop_process"),
    "service_probe": ("probe_service",),
    "artifact_inspection": ("inspect_artifact",),
    "network_fetch": ("bootstrap_acquire",),
}


def _context_recipe_view(policy: Any) -> dict[str, Any] | None:
    recipe = getattr(policy, "recipe", None)
    if recipe is None:
        return None
    return {
        "always_include": list(recipe.always_include),
        "include_recent": [
            {"selector": item.selector, "count": int(item.count)}
            for item in recipe.include_recent
        ],
        "include_last_failure": int(recipe.include_last_failure),
        "preserve_exact": list(recipe.preserve_exact),
        "make_queryable_not_inline": list(recipe.make_queryable_not_inline),
        "unsupported_fields": list(recipe.unsupported_fields),
    }


def _solver_prompt_summary(prompt: str) -> str:
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:160]
    return ""


def _raw_state_candidate_paths(envmap: EnvMap, *, limit: int = 8) -> list[dict[str, str]]:
    """Bounded generic file candidates for verifier raw-state inspection."""
    summary = dict(envmap.file_map_summary or {})
    declared_outputs = {
        normalize_relpath(str(path), envmap.workspace_root)
        for key in (
            "prompt_declared_output_paths",
            "prompt_declared_output_visible_paths",
            "instruction_output_paths",
        )
        for path in (summary.get(key, ()) or ())
        if str(path).strip()
    }
    test_or_checker = {
        normalize_relpath(str(path), envmap.workspace_root)
        for path in (summary.get("likely_tests_or_checkers", ()) or ())
        if str(path).strip()
    }
    seen: set[str] = set()
    candidates: list[dict[str, str]] = []
    for source, key in (
        ("envmap.likely_inputs", "likely_inputs"),
        ("envmap.instruction_referenced_visible_paths", "instruction_referenced_visible_paths"),
    ):
        for raw_path in summary.get(key, ()) or ():
            path = normalize_relpath(str(raw_path), envmap.workspace_root)
            if not path or path in seen or path in declared_outputs or path in test_or_checker:
                continue
            seen.add(path)
            candidates.append({"path": path, "source": source, "authority": "candidate_only"})
            if len(candidates) >= limit:
                return candidates
    return candidates


class CapabilityRegistry:
    def __init__(self, capabilities: Iterable[CapabilityDescriptor]) -> None:
        self._capabilities = {cap.capability_id: cap for cap in capabilities}

    @classmethod
    def from_envmap(cls, envmap: EnvMap) -> "CapabilityRegistry":
        return cls(envmap.capabilities.values())

    def get(self, capability_id: str) -> CapabilityDescriptor | None:
        return self._capabilities.get(capability_id)

    def available_ids(self) -> tuple[str, ...]:
        return tuple(
            cid
            for cid, cap in sorted(self._capabilities.items())
            if cap.available
        )

    def metadata_view(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "capability_id": cap.capability_id,
                "summary": cap.summary,
                "available": cap.available,
                "cost_hint": cap.cost_hint,
                "tool_names": list(cap.tool_names),
            }
            for cap in sorted(self._capabilities.values(), key=lambda item: item.capability_id)
        )


class ConfigCompiler:
    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        eval_indexer: EvalIndexer | None = None,
        objective_builder: ObjectiveGraphBuilder | None = None,
    ) -> None:
        self.registry = registry
        self.eval_indexer = eval_indexer or EvalIndexer()
        self.objective_builder = objective_builder or ObjectiveGraphBuilder()

    def analyze_envmap(self, envmap: EnvMap) -> tuple[ObjectiveGraph, EvalIndex]:
        eval_index = self.eval_indexer.build(envmap)
        objective = self.objective_builder.build(envmap, eval_index)
        return objective, eval_index

    def validate(
        self,
        ir: RuntimeConfigIR,
        envmap: EnvMap,
        *,
        objective_graph: ObjectiveGraph | None = None,
        eval_index: EvalIndex | None = None,
    ) -> list[ConfigIssue]:
        objective = objective_graph or self.analyze_envmap(envmap)[0]
        checks = eval_index or self.analyze_envmap(envmap)[1]
        issues: list[ConfigIssue] = []

        if not ir.selected_capabilities:
            issues.append(ConfigIssue("no_capabilities_selected", "At least one capability must be selected."))

        if len(ir.selected_capabilities) > _MAX_SELECTED_CAPABILITIES:
            issues.append(
                ConfigIssue(
                    "too_many_capabilities",
                    f"Selected {len(ir.selected_capabilities)} capabilities; budget is {_MAX_SELECTED_CAPABILITIES}.",
                )
            )

        selected = set(ir.selected_capabilities)
        for capability_id in ir.selected_capabilities:
            cap = self.registry.get(capability_id)
            if cap is None:
                issues.append(
                    ConfigIssue(
                        "unknown_capability",
                        f"Capability '{capability_id}' is not in the registry.",
                        severity="warning",
                        fatal=False,
                    )
                )
                continue
            if not cap.available:
                issues.append(
                    ConfigIssue(
                        "unavailable_capability",
                        f"Capability '{capability_id}' is marked unavailable.",
                        severity="warning",
                        fatal=False,
                    )
                )

        # If ALL selected capabilities are invalid/unavailable, that is fatal.
        valid_caps = [
            cid for cid in ir.selected_capabilities
            if self.registry.get(cid) is not None and self.registry.get(cid).available  # type: ignore[union-attr]
        ]
        if ir.selected_capabilities and not valid_caps:
            issues.append(
                ConfigIssue(
                    "all_capabilities_invalid",
                    "All selected capabilities are unknown or unavailable.",
                )
            )

        if ir.process_policy.mode not in _ALLOWED_PROCESS_MODES:
            issues.append(
                ConfigIssue(
                    "invalid_process_mode",
                    f"Unsupported process mode '{ir.process_policy.mode}'.",
                )
            )

        if ir.process_policy.mode != "stateless_shell" and "managed_process" not in selected:
            issues.append(
                ConfigIssue(
                    "missing_managed_process",
                    "Managed or interactive process modes require the managed_process capability.",
                )
            )

        if ir.process_policy.require_fresh_probe and "service_probe" not in selected:
            issues.append(
                ConfigIssue(
                    "missing_service_probe",
                    "require_fresh_probe requires the service_probe capability.",
                )
            )

        if ir.bootstrap_policy.allow_acquisition and "shell" not in selected:
            issues.append(
                ConfigIssue(
                    "missing_bootstrap_substrate",
                    "Bootstrap acquisition requires the shell capability.",
                )
            )

        if ir.helper_tool_policy.allow_creation and not {"filesystem", "shell"}.issubset(selected):
            issues.append(
                ConfigIssue(
                    "missing_helper_tool_substrate",
                    "Helper tool creation requires both filesystem and shell capabilities.",
                )
            )

        if objective.service_requirements and ir.process_policy.mode == "stateless_shell":
            issues.append(
                ConfigIssue(
                    "service_without_process_mode",
                    "Objective graph includes services but the runtime kept stateless_shell mode.",
                    severity="warning",
                    fatal=False,
                )
            )

        visible_check_ids = {check.check_id for check in checks.checks}
        unknown_check_ids = [check_id for check_id in ir.check_plan if check_id not in visible_check_ids]
        if unknown_check_ids:
            issues.append(
                ConfigIssue(
                    "unknown_check_plan_id",
                    f"Architect check_plan references unknown checks: {', '.join(sorted(unknown_check_ids))}.",
                    severity="warning",
                    fatal=False,
                )
            )

        if checks.authoritative_checks() and not ir.check_plan:
            issues.append(
                ConfigIssue(
                    "missing_explicit_check_plan",
                    "Visible authoritative checks exist but architect did not choose an explicit ordered check plan.",
                    severity="warning",
                    fatal=False,
                )
            )

        if ir.completion_policy.require_authoritative_check and not checks.authoritative_checks():
            issues.append(
                ConfigIssue(
                    "no_authoritative_checks_visible",
                    "No visible authoritative checks were indexed; completion will rely on evidence fallback.",
                    severity="warning",
                    fatal=False,
                )
            )

        if ir.refusal_policy.allowed_local_categories and envmap.network_scope == "open_external_network":
            issues.append(
                ConfigIssue(
                    "unsafe_refusal_boundary",
                    "Local-only benchmark allowances cannot be compiled while external network scope is open.",
                )
            )

        for text in (ir.architect_summary, *ir.advisory_notes):
            lowered = text.lower()
            for phrase in _VAGUE_PHRASES:
                if phrase in lowered:
                    issues.append(
                        ConfigIssue(
                            "vague_language",
                            f"Found vague phrase '{phrase}' in architect output.",
                            severity="warning",
                            fatal=False,
                        )
                    )
                    break

        if ir.workflow_policy.mode not in WORKFLOW_MODES:
            issues.append(
                ConfigIssue(
                    "unknown_workflow_mode",
                    f"Unknown workflow mode '{ir.workflow_policy.mode}'.",
                )
            )

        for tier_name, tier_value in (
            ("architect_model_tier", ir.architect_model_tier),
            ("solver_model_tier", ir.solver_model_tier),
            ("verifier_model_tier", ir.verifier_model_tier),
            ("perception_model_tier", ir.perception_model_tier),
        ):
            if tier_value not in MODEL_TIERS:
                issues.append(
                    ConfigIssue(
                        "unknown_model_tier",
                        f"Unknown {tier_name} '{tier_value}'.",
                    )
                )

        if not ir.inspection_plan:
            issues.append(
                ConfigIssue(
                    "missing_inspection_plan",
                    "Architect should provide an explicit first inspection plan for the mini solver.",
                    severity="warning",
                    fatal=False,
                )
            )
        if not ir.proof_plan:
            issues.append(
                ConfigIssue(
                    "missing_proof_plan",
                    "Architect should provide an explicit proof plan.",
                    severity="warning",
                    fatal=False,
                )
            )

        return issues

    def compile(
        self,
        ir: RuntimeConfigIR,
        envmap: EnvMap,
        *,
        objective_graph: ObjectiveGraph | None = None,
        eval_index: EvalIndex | None = None,
    ) -> CompiledRuntime:
        objective, checks = (objective_graph, eval_index)
        if objective is None or checks is None:
            objective, checks = self.analyze_envmap(envmap)
        if ir.compiler_injected_checks:
            existing_ids = {check.check_id for check in checks.checks}
            injected = tuple(
                check for check in ir.compiler_injected_checks
                if check.check_id not in existing_ids
            )
            if injected:
                checks = EvalIndex(checks=tuple(checks.checks) + injected)

        issues = self.validate(ir, envmap, objective_graph=objective, eval_index=checks)
        fatal_issues = [issue for issue in issues if issue.fatal]
        if fatal_issues:
            message = "; ".join(f"{issue.code}: {issue.message}" for issue in fatal_issues)
            raise ValueError(message)

        # Sanitize: keep only valid and available capabilities.
        selected_capabilities: tuple[CapabilityDescriptor, ...] = tuple(
            self.registry.get(capability_id)
            for capability_id in ir.selected_capabilities
            if self.registry.get(capability_id) is not None
            and self.registry.get(capability_id).available  # type: ignore[union-attr]
        )  # type: ignore[arg-type]

        # Sanitize: drop unknown check_plan ids, keep only valid ones.  Plan
        # membership accepts any indexed check; the authoritative flag carries
        # evidential weight only (shape-only checks stay runnable but must
        # never read as semantic proof).
        visible_check_ids = {check.check_id for check in checks.checks}
        sanitized_check_plan = tuple(
            cid for cid in ir.check_plan if cid in visible_check_ids
        )
        planned_check_ids = sanitized_check_plan or tuple(
            check.check_id for check in checks.authoritative_checks()
        )
        planned_check_ids = _dedupe_preserve(planned_check_ids)

        monitors = ["no_progress", "integrity_guard"]
        if objective.deliverables:
            monitors.append("artifact_accounting")
        if objective.service_requirements or ir.process_policy.require_fresh_probe:
            monitors.append("service_liveness")
        if ir.workflow_policy.mode == "service_stabilize" and "service_liveness" not in monitors:
            monitors.append("service_liveness")

        forbidden_paths = _dedupe_preserve(
            list(objective.protected_paths) + [normalize_relpath(path, envmap.workspace_root) for path in ir.forbidden_paths]
        )

        planned_checks = [
            asdict(check)
            for check in checks.checks
            if check.check_id in set(planned_check_ids)
        ]

        # Filter action schema to only tools granted by selected capabilities,
        # plus explicitly always-available memory/kernel affordances.
        allowed_action_kinds = set(ALWAYS_AVAILABLE_ACTION_KINDS)
        for cap in selected_capabilities:
            allowed_action_kinds.update(cap.tool_names or _DEFAULT_CAPABILITY_TOOLS.get(cap.capability_id, ()))
        action_schema = tuple((name, args) for name, args in ACTION_SCHEMA if name in allowed_action_kinds)
        action_schema_dict = {name: list(args) for name, args in action_schema}
        solver_prompt_hash = sha256(ir.solver_identity_prompt.encode("utf-8")).hexdigest()[:16]
        verifier_prompt_hash = sha256(ir.verifier_identity_prompt.encode("utf-8")).hexdigest()[:16]
        configured_context_policy = {
            "mode": ir.context_policy.mode,
            "include_sections": list(ir.context_policy.include_sections),
            "model_context_window_tokens": ir.context_policy.model_context_window_tokens,
            "compression_trigger_ratio": ir.context_policy.compression_trigger_ratio,
            "recipe": _context_recipe_view(ir.context_policy),
        }
        configured_verification_policy = {
            "check_plan_ids": list(planned_check_ids),
            "planned_checks": planned_checks,
            "model_verifier_tier": ir.verifier_model_tier,
            "model_verifier_policy": asdict(ir.model_verifier_policy),
            "completion_policy": asdict(ir.completion_policy),
            "official_grader_authority": "external_benchmark",
        }
        configured_advisory_notes = list(ir.advisory_notes)
        stable_core_mode = any(note == "tool_policy_mode=stable_core" for note in configured_advisory_notes)
        environment_probe = dict(envmap.task_metadata.get("environment_probe", {}) or {})
        structured_local_verification_limits = [
            {"source": "runtime_config", "statement": item}
            for item in ir.local_verification_limits
            if str(item).strip()
        ]
        config_realization = {
            "tool_policy_mode": "stable_core" if stable_core_mode else "capability_selected",
            "architect_tool_selection_applied": not stable_core_mode,
            "architect_tool_guidance_recorded": stable_core_mode,
            "tools_declared_capabilities": list(ir.selected_capabilities),
            "capabilities_realized": [cap.capability_id for cap in selected_capabilities],
            "tools_visible_to_solver": sorted(action_schema_dict),
            "tools_runtime_allowed": sorted(action_schema_dict),
            "tools_audit_separately": ["register_candidate", "run_experiment", "reconfigure"],
            "context_policy_mode": ir.context_policy.mode,
            "automatic_memory_policy": asdict(ir.automatic_memory_policy),
            "context_sections_declared": list(ir.context_policy.include_sections),
            "context_compression_ratio": ir.context_policy.compression_trigger_ratio,
            "context_recipe_declared": _context_recipe_view(ir.context_policy),
            "context_policy_rendered": True,
            "checks_declared": list(ir.check_plan),
            "checks_compiled": list(planned_check_ids),
            "compiler_injected_checks": [asdict(check) for check in ir.compiler_injected_checks],
            "environment_probe": environment_probe,
            "environment_probe_available": bool(environment_probe),
            "verifier_raw_state_candidates": _raw_state_candidate_paths(envmap),
            "solver_prompt_inserted": bool(ir.solver_identity_prompt.strip()),
            "solver_system_prompt_summary": _solver_prompt_summary(ir.solver_identity_prompt),
            "solver_prompt_hash": solver_prompt_hash,
            "verifier_prompt_inserted": bool(ir.verifier_identity_prompt.strip()),
            "verifier_system_prompt_summary": _solver_prompt_summary(ir.verifier_identity_prompt),
            "verifier_prompt_hash": verifier_prompt_hash,
            "success_definition": ir.success_definition,
            "evidence_requirements": list(ir.evidence_requirements),
            "false_positive_risks": list(ir.false_positive_risks),
            "minimum_completion_evidence": list(ir.minimum_completion_evidence),
            "local_verification_limits": structured_local_verification_limits,
            "local_verification_limits_text": list(ir.local_verification_limits),
            "verification_authority": {
                "model_verifier": "internal_gate" if ir.model_verifier_policy.enabled else "disabled_by_policy",
                "official_grader": "external_benchmark",
            },
            "model_verifier_policy": asdict(ir.model_verifier_policy),
            "advisory_notes": configured_advisory_notes,
            "rendered_sections": [
                "kernel_contract",
                "tool_semantics",
                "automatic_memory_manual",
                "verification_submit_manual",
                "solver_turn_contract",
                "task_prompt",
                "envmap",
                "envmap_file_tree",
                "envmap_file_map_summary",
                "objective_graph",
                "eval_index",
                "architect_summary",
                "inspection_plan",
                "proof_plan",
                "check_plan",
                "forbidden_paths",
                "workflow_mode",
                "solver_identity",
                "verifier_identity",
                "configured_context_policy",
                "configured_verification_policy",
                "configured_advisory_notes",
                "environment_probe",
                "refusal_boundary",
                "selected_capabilities",
                "action_schema",
                "config_realization",
            ],
        }

        prefix_sections: list[tuple[str, str]] = [
            (
                "kernel_contract",
                (
                    "Kernel facts: typed action schema is enforced at dispatch time; receipts are recorded as "
                    "execution evidence; local-only safety and path integrity checks may reject actions; "
                    "submit_outcome asks the runtime to evaluate the current state."
                ),
            ),
            (
                "tool_semantics",
                (
                    "Only action kinds listed in [action_schema] are callable. Disabled tools are rejected before dispatch. "
                    "query_memory, inspect_checks, run_check, query_artifact_history, inspect_diff, and record_observation "
                    "are kernel-owned affordances when present in [action_schema]. Optional action target metadata is used "
                    "for memory matching and does not change tool argument requirements."
                ),
            ),
            (
                "automatic_memory_manual",
                (
                    "Automatic memory compares repeated read_file, write_file, run_command, and run_check actions against prior receipts. "
                    "Stable path, check_id, or command-fingerprint metadata lets the runtime attach matching evidence cheaply. "
                    "automatic_memory_findings, files_already_read, and repeated_actions in context describe prior observations; "
                    "repeat_justification may be required by the active memory policy."
                ),
            ),
            (
                "verification_submit_manual",
                (
                    "Verification facts: inspect_checks and run_check expose harness-visible checks when available; "
                    "submit_outcome requests runtime completion evaluation; active_verifier_findings may appear in later "
                    "context packets after a verifier pass; local checks and local evidence do not prove hidden grader behavior."
                ),
            ),
            (
                "solver_turn_contract",
                stable_json(
                    {
                        "emit_format": "strict_json_only",
                        "turn_kinds": ["act", "submit_outcome"],
                        "required_fields": {
                            "always": ["kind", "summary"],
                            "act": ["actions"],
                            "act_action_fields": ["kind", "arguments"],
                            "recommended_action_fields": [
                                "action_id",
                                "intent",
                                "expected_observation",
                                "if_fail_next",
                            ],
                        },
                        "action_schema_section": "action_schema",
                        "notes": [
                            "Only action kinds listed in action_schema are callable.",
                            "Kernel-owned memory and check affordances are listed in action_schema when available.",
                            "Do not request reconfiguration. Report concrete harness blockers with the report_blocker action.",
                        ],
                    }
                ),
            ),
            ("task_prompt", envmap.task_prompt),
            ("envmap", stable_json(envmap.compact_summary() | {"env_digest": envmap.digest()})),
            ("envmap_file_tree", envmap.file_tree or ""),
            ("envmap_file_map_summary", stable_json(dict(envmap.file_map_summary))),
            ("objective_graph", objective.summary()),
            ("eval_index", checks.summary()),
            ("architect_summary", ir.architect_summary),
            ("inspection_plan", stable_json(list(ir.inspection_plan))),
            ("proof_plan", stable_json(list(ir.proof_plan))),
            ("check_plan", stable_json(planned_checks)),
            ("forbidden_paths", stable_json(list(forbidden_paths))),
            ("workflow_mode", ir.workflow_policy.mode),
            ("solver_identity", ir.solver_identity_prompt),
            ("verifier_identity", ir.verifier_identity_prompt),
            ("configured_context_policy", stable_json(configured_context_policy)),
            ("configured_verification_policy", stable_json(configured_verification_policy)),
            ("configured_advisory_notes", stable_json(configured_advisory_notes)),
            ("environment_probe", stable_json(environment_probe)),
            ("refusal_boundary", self._render_refusal_boundary(ir.refusal_policy)),
            ("selected_capabilities", stable_json([asdict(cap) for cap in selected_capabilities])),
            ("action_schema", stable_json(action_schema_dict)),
            ("config_realization", stable_json(config_realization)),
        ]

        return CompiledRuntime(
            task_prompt=envmap.task_prompt,
            env_digest=envmap.digest(),
            objective_graph=objective,
            eval_index=checks,
            selected_capabilities=selected_capabilities,
            stable_prefix_sections=tuple(prefix_sections),
            context_policy=ir.context_policy,
            automatic_memory_policy=ir.automatic_memory_policy,
            process_policy=ir.process_policy,
            helper_tool_policy=ir.helper_tool_policy,
            bootstrap_policy=ir.bootstrap_policy,
            completion_policy=ir.completion_policy,
            model_verifier_policy=ir.model_verifier_policy,
            refusal_policy=ir.refusal_policy,
            reconfigure_policy=ir.reconfigure_policy,
            enforced_monitors=tuple(monitors),
            check_plan_ids=planned_check_ids,
            forbidden_paths=forbidden_paths,
            workflow_policy=ir.workflow_policy,
            action_schema=action_schema,
            solver_identity_prompt=ir.solver_identity_prompt,
            success_definition=ir.success_definition,
            local_verification_limits=ir.local_verification_limits,
            verifier_identity_prompt=ir.verifier_identity_prompt,
            evidence_requirements=ir.evidence_requirements,
            false_positive_risks=ir.false_positive_risks,
            minimum_completion_evidence=ir.minimum_completion_evidence,
            config_realization=config_realization,
            architect_model_tier=ir.architect_model_tier,
            solver_model_tier=ir.solver_model_tier,
            verifier_model_tier=ir.verifier_model_tier,
            perception_model_tier=ir.perception_model_tier,
        )

    @staticmethod
    def _render_refusal_boundary(policy) -> str:
        if not policy.allowed_local_categories:
            return "No local-only benchmark allowance compiled."
        categories = ", ".join(sorted(policy.allowed_local_categories))
        return (
            f"Local-only benchmark allowance compiled for categories: {categories}. "
            "Allowed scope: workspace files, local processes, and localhost services only. "
            "External targets remain forbidden."
        )

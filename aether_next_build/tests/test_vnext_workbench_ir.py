from __future__ import annotations

import json

import pytest

from aether_next.architect_quality import score_architect_config
from aether_next.compiler import CapabilityRegistry, ConfigCompiler
from aether_next.runtime_manual import ALLOWED_VISIBLE_SMOKE_TEST_TYPES, build_runtime_manual
from aether_next.runtime_ir import CapabilityDescriptor, EnvMap
from aether_next.workbench_compile import (
    TOP_LEVEL_CONFIG_FIELDS,
    config_realization_audit,
    harness_config_to_runtime_ir,
    realization_preview,
)
from aether_next.workbench_config import (
    RAW_COMMAND_VISIBLE_SMOKE_TEST_CODE,
    UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE,
    parse_harness_config_ir,
    parse_workbench_architect_output,
)
from aether_next.workbench_hooks import WORKBENCH_ARCHITECT_SYSTEM_PROMPT, WorkbenchArchitect


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Write out.txt",
        workspace_root="/app",
        capabilities={
            "shell": CapabilityDescriptor("shell", "Run commands", tool_names=("run_command",)),
            "filesystem": CapabilityDescriptor("filesystem", "Files", tool_names=("read_file", "write_file")),
        },
    )


def _raw_config(**overrides):
    base = {
        "schema_version": "harness_config.v1",
        "task_understanding": "Write one output file.",
        "success_definition": "out.txt exists and matches the prompt.",
        "solver_system_prompt": {
            "role": "Careful file task solver",
            "workflow": ["inspect workspace", "write out.txt", "self-verify", "submit candidate"],
            "self_verification": ["read out.txt and compare it to the task prompt"],
            "memory_use": ["automatic memory surfaces repeated reads/checks; use prior evidence or narrow the next action"],
            "stop_conditions": ["submit only after deliverable exists and validation evidence supports completion"],
            "avoid": ["do not submit from source-text-only evidence"],
        },
        "verifier_system_prompt": {
            "role": "Task-specific evidence verifier",
            "success_criteria": ["out.txt exists and matches the requested result"],
            "required_evidence": ["artifact exists", "content was checked against the task"],
            "false_positive_traps": ["syntax or source text alone is not enough"],
            "verdict_guidance": ["completed requires evidence", "uncertain means missing evidence", "no_progress means repeated actions without new evidence"],
            "feedback_guidance": ["name the missing evidence and next concrete check"],
        },
        "evidence_requirements": ["out.txt exists", "out.txt content matches the requested result"],
        "false_positive_risks": ["a file can exist but contain the wrong content"],
        "minimum_completion_evidence": ["file existence and content evidence"],
        "tool_policy": {"enabled_tools": ["read_file", "write_file", "run_command", "query_memory", "run_check"]},
        "context_policy": {"mode": "retrieval_augmented", "always_include": ["recent_progress", "pending_checks"]},
        "verification_policy": {
            "visible_smoke_tests": [
                {"type": "content_assertion", "target": "/app/out.txt", "assertions": [{"contains": "result"}]}
            ]
        },
        "model_verifier_policy": {"enabled": True},
        "failure_feedback_policy": {"persist_until": "resolved_or_superseded"},
        "helper_script_policy": {"enabled": True, "directory": "/app/.aether_tools", "trust_level": "advisory"},
        "local_verification_limits": ["local checks cannot prove hidden expectations"],
    }
    base.update(overrides)
    return json.dumps(base)


def test_workbench_architect_prompt_states_runtime_config_role() -> None:
    assert "configure the harness for task success" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "not to solve the task" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "Visible smoke tests must be typed specs" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "visible_smoke_tests[*].type must be exactly one of: syntax_check | run_deliverable_on_fixture | content_assertion | file_exists | file_size" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "executing a program" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "Filesystem-only guidance is appropriate only" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "Operate like a compiler-backed skill" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "envmap.environment_probe" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "verifier_system_prompt" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "evidence_requirements" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "automatic memory repeat" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "automatic_repeat_mode" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "soft_block_exact_repeat" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "Strict JSON rules" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "Keep the total response compact enough to fit comfortably within the output budget" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "submit_outcome as a true completion claim" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "read-only\ncurrent-state inspector" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "blocked_by_harness_config" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "completed, needs_repair,\nuncertain_missing_evidence, blocked_by_tooling, and blocked_by_harness_config" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "if a local check fails or the verifier returns needs_repair" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT


def test_runtime_manual_allowed_smoke_enum_matches_parser_enum() -> None:
    manual = build_runtime_manual()

    assert manual["verification"]["allowed_visible_smoke_test_types"] == list(ALLOWED_VISIBLE_SMOKE_TEST_TYPES)
    assert manual["tools"]["architect_does_not_choose_tools"] is True
    assert "run_command" in manual["tools"]["stable_core_solver_tools"]
    assert "register_candidate" in manual["tools"]["audit_separately"]
    assert any("local_verification_limits" in item for item in manual["verification"]["check_plan_guidance"])
    assert "architect_skill_spec" in manual
    assert "envmap.environment_probe" in manual["architect_skill_spec"]["required_inputs"]
    assert "file_exists" in manual["verification"]["allowed_visible_smoke_test_types"]
    assert "file_size" in manual["verification"]["allowed_visible_smoke_test_types"]
    assert manual["memory"]["automatic_repeat_modes"] == [
        "off",
        "advisory",
        "require_justification",
        "soft_block_exact_repeat",
    ]
    solver_style = manual["solver_prompt_requirements"]["verification_first_style"]
    verifier_requirements = manual["verifier_prompt_requirements"]["must_include"]
    assert "that submit_outcome is a true completion claim, not a fishing call" in solver_style
    assert "how to respond when local checks fail or verifier findings arrive" in solver_style
    assert "read-only current-state inspection role" in verifier_requirements
    assert "verdict meanings for completed/needs_repair/uncertain_missing_evidence/blocked_by_tooling/blocked_by_harness_config" in verifier_requirements


def test_architect_quality_rewards_verifier_state_inspector_and_repair_guidance() -> None:
    raw = json.loads(_raw_config())
    raw["solver_system_prompt"]["workflow"] = [
        "inspect inputs and exact output path",
        "build the artifact",
        "run the strongest local checks",
        "repair and resubmit only after verifier feedback or failed checks are addressed",
    ]
    raw["solver_system_prompt"]["self_verification"] = [
        "run_check on the visible validator before submit",
        "if a verifier finding or failed check appears, repair the named gap and resubmit only after fresh evidence",
    ]
    raw["solver_system_prompt"]["stop_conditions"] = [
        "Ready to submit only when /app/out.txt matches the requested result and the strongest local evidence is fresh.",
    ]
    raw["verifier_system_prompt"]["role"] = "Read-only current-state inspector for task completion."
    raw["verifier_system_prompt"]["verdict_guidance"] = [
        "Return completed only when the current state satisfies the success definition with evidence.",
        "Return needs_repair when the current state is wrong but repairable.",
        "Return uncertain_missing_evidence when inspection evidence is still missing.",
        "Return blocked_by_tooling when a required tool/runtime surface is unavailable.",
        "Return blocked_by_harness_config when harness configuration makes the run unrealizable.",
    ]
    raw["verifier_system_prompt"]["feedback_guidance"] = [
        "Inspect the current state, cite evidence, and give concrete repair feedback.",
    ]
    config = parse_harness_config_ir(json.dumps(raw))

    scored = score_architect_config(config)

    assert "solver_prompt_handles_failed_checks_or_verifier_feedback" not in scored["solver_prompt"]["missing"]
    assert "verifier_prompt_mentions_read-only" not in scored["verifier_prompt"]["missing"]
    assert "verifier_prompt_mentions_blocked_by_tooling" not in scored["verifier_prompt"]["missing"]
    assert "verifier_prompt_mentions_blocked_by_harness_config" not in scored["verifier_prompt"]["missing"]


def test_fake_architect_execution_pressure_config_realizes_shell_tool() -> None:
    class _ExecutionAwareModel:
        def __call__(self, messages, *, max_output_tokens=8000):
            assert "executing a program" in messages[0]["content"]
            assert "run_command" in messages[1]["content"]
            raw = json.loads(_raw_config())
            raw["task_understanding"] = "Generate cryptographic artifacts using a local command-line tool."
            raw["success_definition"] = "Expected certificate artifacts exist and are inspectable by local tooling."
            raw["solver_system_prompt"]["workflow"] = [
                "inspect requested artifact names",
                "generate artifacts with the available CLI",
                "run local inspection checks",
                "submit only after evidence supports completion",
            ]
            raw["solver_system_prompt"]["self_verification"] = [
                "run the local inspection command on generated artifacts",
                "read output paths and confirm they are non-empty",
            ]
            raw["tool_policy"] = {
                "enabled_tools": ["read_file", "write_file", "run_command", "query_memory", "inspect_checks", "run_check"]
            }
            raw["verification_policy"] = {
                "visible_smoke_tests": [
                    {"type": "file_size", "path": "cert.pem", "min_bytes": 1},
                    {"type": "grader_clone", "path": "notes.txt"},
                ]
            }
            raw["local_verification_limits"] = [
                "local inspection can confirm generated artifact shape but not hidden grader expectations"
            ]
            return json.dumps(raw)

    architect = WorkbenchArchitect(_ExecutionAwareModel())
    config, errors = architect.configure({
        "task_prompt": "Create self-signed certificate artifacts and validate them locally.",
        "runtime_manual": build_runtime_manual(),
    })

    assert config is not None
    assert errors
    assert config.verification_policy.visible_smoke_tests == (
        {"type": "file_size", "path": "cert.pem", "min_bytes": 1},
    )
    ir = harness_config_to_runtime_ir(config, _env())
    audit = config_realization_audit(config, _env())
    assert "shell" in ir.selected_capabilities
    assert "filesystem" in ir.selected_capabilities
    assert "run_command" in audit["dispositions"]["tool_policy"]["runtime_allowed_tools_expected"]
    assert config.local_verification_limits
    assert config.rejected_config_items[0]["status"] == "quarantined"


def test_fake_architect_simple_file_transform_can_remain_filesystem_only() -> None:
    class _FileOnlyModel:
        def __call__(self, messages, *, max_output_tokens=8000):
            raw = json.loads(_raw_config())
            raw["task_understanding"] = "Rewrite one text file using the visible prompt."
            raw["success_definition"] = "out.txt contains the requested transformed text."
            raw["solver_system_prompt"]["workflow"] = [
                "read the input file",
                "write the transformed output file",
                "read the output back before submit",
            ]
            raw["tool_policy"] = {"enabled_tools": ["read_file", "write_file", "query_memory"]}
            raw["verification_policy"] = {
                "visible_smoke_tests": [
                    {"type": "content_assertion", "target": "/app/out.txt", "assertions": [{"contains": "result"}]}
                ]
            }
            raw["local_verification_limits"] = [
                "content assertions cannot prove hidden semantic expectations"
            ]
            return json.dumps(raw)

    architect = WorkbenchArchitect(_FileOnlyModel())
    config, errors = architect.configure({"task_prompt": "Transform input.txt into out.txt."})

    assert config is not None
    assert errors == []
    ir = harness_config_to_runtime_ir(config, _env())
    assert ir.selected_capabilities == ("filesystem", "shell")
    assert "shell" in ir.selected_capabilities
    assert config.local_verification_limits


def test_harness_config_ir_compiles_to_runtime_ir() -> None:
    config = parse_harness_config_ir(_raw_config())
    ir = harness_config_to_runtime_ir(config, _env())

    assert set(ir.selected_capabilities) == {"shell", "filesystem"}
    assert ir.context_policy.mode == "retrieval_augmented"
    assert "Careful file task solver" in ir.solver_identity_prompt
    assert ir.helper_tool_policy.allow_creation is True
    assert any("model_verifier_enabled=True" in note for note in ir.advisory_notes)
    assert ir.verifier_identity_prompt
    assert ir.evidence_requirements


def test_workbench_visible_smoke_checks_become_compiler_injected_checks() -> None:
    raw = json.loads(_raw_config())
    raw["verification_policy"] = {
        "visible_smoke_tests": [
            {"type": "file_exists", "path": "/app/out.txt"},
            {"type": "file_size", "path": "/app/out.txt", "min_bytes": 1},
            {"type": "syntax_check", "path": "/app/check.py", "language": "python"},
        ]
    }
    config = parse_harness_config_ir(json.dumps(raw))
    ir = harness_config_to_runtime_ir(config, _env())

    assert len(ir.compiler_injected_checks) == 3
    assert ir.check_plan == tuple(check.check_id for check in ir.compiler_injected_checks)
    assert any("file_exists" in check.check_id for check in ir.compiler_injected_checks)
    assert any("file_size" in check.check_id for check in ir.compiler_injected_checks)


def test_harness_config_ir_recipe_bridges_to_runtime_context_policy() -> None:
    raw = json.loads(_raw_config())
    raw["context_policy"] = {
        "mode": "retrieval_augmented",
        "recipe": {
            "include_recent": {"tool_results": 2},
            "include_last_failure": 1,
            "preserve_exact": ["pending_checks", "active_verifier_findings"],
            "make_queryable_not_inline": ["command_results"],
            "unsupported_knob": True,
        },
    }

    config = parse_harness_config_ir(json.dumps(raw))
    ir = harness_config_to_runtime_ir(config, _env())

    assert ir.context_policy.recipe is not None
    assert ir.context_policy.recipe.include_recent[0].selector == "tool_results"
    assert ir.context_policy.recipe.include_recent[0].count == 2
    assert ir.context_policy.recipe.include_last_failure == 1
    assert ir.context_policy.recipe.preserve_exact == ("pending_checks", "active_verifier_findings")
    assert ir.context_policy.recipe.make_queryable_not_inline == ("command_results",)
    assert ir.context_policy.recipe.unsupported_fields == ("unsupported_knob",)


def test_realization_preview_explains_configured_architecture() -> None:
    config = parse_harness_config_ir(_raw_config())
    preview = realization_preview(config, _env())

    assert preview["schema_version"] == "harness_config.v1"
    assert preview["context_policy_mode"] == "retrieval_augmented"
    assert preview["solver_prompt_inserted"] is True
    assert "filesystem" in preview["selected_capabilities"]
    assert preview["realization_audit"]["has_silent_ignored_fields"] is False


def test_config_realization_audit_accounts_for_every_top_level_field() -> None:
    config = parse_harness_config_ir(_raw_config())
    audit = config_realization_audit(config, _env())
    dispositions = audit["dispositions"]

    assert audit["missing_dispositions"] == []
    assert set(dispositions) == set(TOP_LEVEL_CONFIG_FIELDS)
    assert dispositions["solver_system_prompt"]["status"] == "realized"
    assert dispositions["tool_policy"]["status"] == "advisory_not_applied_to_core_visibility"
    assert dispositions["tool_policy"]["tool_policy_mode"] == "stable_core"
    assert dispositions["tool_policy"]["architect_tool_selection_applied"] is False
    assert dispositions["context_policy"]["status"] == "realized_partial"
    assert dispositions["memory_policy"]["status"] == "realized_partial"
    assert dispositions["memory_policy"]["automatic_repeat_mode"] == "advisory"
    assert dispositions["verification_policy"]["status"] == "realized_partial"
    assert dispositions["model_verifier_policy"]["status"] == "realized"


def test_config_realization_audit_reports_declared_and_runtime_allowed_tools() -> None:
    config = parse_harness_config_ir(_raw_config())
    audit = config_realization_audit(config, _env())
    tools = audit["dispositions"]["tool_policy"]

    assert "run_command" in tools["enabled_tools_declared"]
    assert "run_command" in tools["runtime_allowed_tools_expected"]
    assert "read_file" in tools["runtime_allowed_tools_expected"]
    assert "query_memory" in tools["runtime_allowed_tools_expected"]
    assert "inspect_checks" in tools["always_available_tools"]


def test_workbench_stable_core_ignores_architect_omitted_run_command() -> None:
    raw = json.loads(_raw_config())
    raw["tool_policy"] = {"enabled_tools": ["read_file", "write_file", "query_memory"]}

    config = parse_harness_config_ir(json.dumps(raw))
    ir = harness_config_to_runtime_ir(config, _env())
    audit = config_realization_audit(config, _env())
    tools = audit["dispositions"]["tool_policy"]

    assert "shell" in ir.selected_capabilities
    assert "filesystem" in ir.selected_capabilities
    assert "run_command" in tools["runtime_allowed_tools_expected"]
    assert tools["architect_tool_selection_applied"] is False
    assert tools["enabled_tools_declared"] == ["read_file", "write_file", "query_memory"]


def test_workbench_stable_core_does_not_expose_internal_experiment_tools() -> None:
    config = parse_harness_config_ir(_raw_config())
    ir = harness_config_to_runtime_ir(config, _env())
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(_env()))
    runtime = compiler.compile(ir, _env())
    tools = dict(runtime.action_schema)

    assert "query_memory" in tools
    assert "query_artifact_history" in tools
    assert "inspect_diff" in tools
    assert "record_observation" in tools
    assert "run_command" in tools
    assert "register_candidate" not in tools
    assert "run_experiment" not in tools
    assert runtime.config_realization["tool_policy_mode"] == "stable_core"
    assert runtime.config_realization["architect_tool_selection_applied"] is False


def test_workbench_memory_policy_mode_compiles_into_runtime_and_receipt() -> None:
    raw = json.loads(_raw_config())
    raw["memory_policy"] = {
        "automatic_repeat_mode": "soft_block_exact_repeat",
        "require_query_before_repeat": True,
        "require_query_before_overwrite": True,
        "index_by": ["path", "action_kind", "check_id", "failure_kind"],
    }
    config = parse_harness_config_ir(json.dumps(raw))
    ir = harness_config_to_runtime_ir(config, _env())
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(_env()))
    runtime = compiler.compile(ir, _env())
    audit = config_realization_audit(config, _env())

    assert ir.automatic_memory_policy.mode == "soft_block_exact_repeat"
    assert runtime.automatic_memory_policy.mode == "soft_block_exact_repeat"
    assert runtime.config_realization["automatic_memory_policy"]["mode"] == "soft_block_exact_repeat"
    assert audit["dispositions"]["memory_policy"]["automatic_repeat_mode"] == "soft_block_exact_repeat"


def test_workbench_rejects_unknown_automatic_memory_mode() -> None:
    raw = json.loads(_raw_config())
    raw["memory_policy"] = {"automatic_repeat_mode": "ask_the_oracle"}

    with pytest.raises(Exception, match="unsupported automatic memory repeat mode"):
        parse_harness_config_ir(json.dumps(raw))


def test_workbench_rejects_unsupported_top_level_fields() -> None:
    raw = json.loads(_raw_config())
    raw["tool_configuration"] = {"made_up": True}
    raw["helper_script_policy_v2"] = {"enabled": True}

    with pytest.raises(Exception, match="unsupported top-level HarnessConfigIR fields"):
        parse_harness_config_ir(json.dumps(raw))


def test_compiler_merges_workbench_injected_checks_into_planned_checks() -> None:
    raw = json.loads(_raw_config())
    raw["verification_policy"] = {
        "visible_smoke_tests": [
            {"type": "file_exists", "path": "/app/out.txt"},
        ]
    }
    config = parse_harness_config_ir(json.dumps(raw))
    ir = harness_config_to_runtime_ir(config, _env())
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(_env()))
    runtime = compiler.compile(ir, _env())

    planned = runtime.planned_checks()
    assert len(planned) == 1
    assert planned[0].origin == "visible_smoke"
    assert runtime.config_realization["checks_compiled"] == [planned[0].check_id]
    assert runtime.config_realization["compiler_injected_checks"][0]["check_id"] == planned[0].check_id


def test_visible_smoke_tests_reject_raw_command_gate() -> None:
    raw = json.loads(_raw_config())
    raw["verification_policy"] = {"visible_smoke_tests": [{"type": "content_assertion", "command": "python hidden.py"}]}

    with pytest.raises(Exception, match="not raw commands"):
        parse_harness_config_ir(json.dumps(raw))


def test_visible_smoke_tests_reject_unknown_type() -> None:
    raw = json.loads(_raw_config())
    raw["verification_policy"] = {"visible_smoke_tests": [{"type": "grader_clone"}]}

    with pytest.raises(Exception, match="unsupported visible smoke test type"):
        parse_harness_config_ir(json.dumps(raw))


def test_model_verifier_runs_on_rejects_non_solver_submit_triggers() -> None:
    raw = json.loads(_raw_config())
    raw["model_verifier_policy"] = {
        "enabled": True,
        "runs_on": ["solver_submit", "deterministic_failure"],
    }

    with pytest.raises(Exception, match="runs_on must be exactly"):
        parse_harness_config_ir(json.dumps(raw))


def test_live_repair_quarantines_raw_command_smoke_test_and_keeps_safe_items() -> None:
    raw = json.loads(_raw_config())
    raw["verification_policy"] = {
        "visible_smoke_tests": [
            {"type": "content_assertion", "command": "python hidden.py", "target": "/app/out.txt"},
            {"type": "content_assertion", "target": "/app/out.txt", "assertions": [{"contains": "result"}]},
        ]
    }

    repaired = parse_workbench_architect_output(json.dumps(raw))

    assert repaired.config is not None
    assert repaired.warning_codes == (RAW_COMMAND_VISIBLE_SMOKE_TEST_CODE,)
    assert repaired.config.verification_policy.visible_smoke_tests == (
        {"type": "content_assertion", "target": "/app/out.txt", "assertions": [{"contains": "result"}]},
    )
    assert repaired.rejected_config_items[0]["status"] == "quarantined"
    assert repaired.rejected_config_items[0]["original_item"]["command"] == "python hidden.py"


def test_live_repair_salvages_unknown_smoke_type_and_records_warning() -> None:
    raw = json.loads(_raw_config())
    raw["verification_policy"] = {
        "visible_smoke_tests": [
            {"type": "grader_clone"},
            {"type": "syntax_check", "target": "/app/main.py"},
        ]
    }

    repaired = parse_workbench_architect_output(json.dumps(raw))

    assert repaired.config is not None
    assert repaired.warning_codes == (UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE,)
    assert repaired.config.repair_warning_codes == (UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE,)
    assert repaired.config.verification_policy.visible_smoke_tests == (
        {"type": "syntax_check", "target": "/app/main.py"},
    )
    assert repaired.rejected_config_items[0]["reason_code"] == UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE


def test_realization_preview_exposes_repair_warnings_and_rejected_items() -> None:
    raw = json.loads(_raw_config())
    raw["verification_policy"] = {"visible_smoke_tests": [{"type": "grader_clone"}]}
    repaired = parse_workbench_architect_output(json.dumps(raw))
    assert repaired.config is not None

    preview = realization_preview(repaired.config, _env())

    assert preview["repair_warning_codes"] == [UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE]
    assert preview["rejected_config_items"][0]["status"] == "quarantined"


def test_workbench_architect_configure_returns_repaired_config_and_warning() -> None:
    class _Model:
        def __call__(self, messages, *, max_output_tokens=8000):
            raw = json.loads(_raw_config())
            raw["verification_policy"] = {"visible_smoke_tests": [{"type": "grader_clone"}]}
            return json.dumps(raw)

    architect = WorkbenchArchitect(_Model())
    config, errors = architect.configure({"task_prompt": "Write out.txt"})

    assert config is not None
    assert errors
    assert architect.last_raw_output
    assert architect.last_warning_codes == [UNSUPPORTED_VISIBLE_SMOKE_TEST_TYPE_CODE]
    assert config.verification_policy.visible_smoke_tests == ()


def test_workbench_architect_retries_once_on_output_budget_exhaustion() -> None:
    class _Model:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def __call__(self, messages, *, max_output_tokens=8000):
            self.calls.append(max_output_tokens)
            if len(self.calls) == 1:
                raise RuntimeError(
                    "background job resp_test incomplete with no usable text: "
                    "IncompleteDetails(reason='max_output_tokens')"
                )
            return _raw_config()

    model = _Model()
    architect = WorkbenchArchitect(model, max_output_tokens=12000)
    config, errors = architect.configure({"task_prompt": "Write out.txt"})

    assert config is not None
    assert errors == []
    assert model.calls == [12000, 24000]

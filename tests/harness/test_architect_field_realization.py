import json
from dataclasses import replace

import pytest

from aether.architect_field_manifest import (
    ARCHITECT_RUNTIME_CONTROL,
    FIELD_REALIZATION_MANIFEST,
    field_realization_manifest_as_dicts,
    validate_field_realization_manifest,
)
import aether.architect_field_manifest as field_manifest
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.runtime_manual import build_runtime_manual
from aether.workbench_prompt import WORKBENCH_ARCHITECT_SYSTEM_PROMPT
from aether.workbench_compile import harness_config_to_runtime_ir
from aether.workbench_config import SUPPORTED_TOP_LEVEL_CONFIG_FIELDS, parse_harness_config_ir


def _raw() -> dict[str, object]:
    return {
        "schema_version": "harness_config.v1",
        "task_understanding": "Create the requested artifact.",
        "visible_contract": [{
            "literal": "output.txt",
            "meaning": "required output path",
            "contrast": "",
        }],
        "success_definition": "The artifact is correct.",
        "solver_system_prompt": {
            "role": "artifact solver",
            "workflow": ["inspect", "act", "verify"],
            "self_verification": ["independently inspect the result"],
            "stop_conditions": ["submit only when complete"],
        },
        "verifier_system_prompt": {
            "role": "state inspector",
            "success_criteria": ["artifact is correct"],
            "required_evidence": ["read the artifact"],
            "false_positive_traps": ["shape-only output"],
        },
        "evidence_requirements": ["artifact contents"],
        "minimum_completion_evidence": ["independent inspection"],
        "context_policy": {
            "mode": "default_bounded",
            "always_include": ["open_obligations"],
            "model_context_window_tokens": 50_000,
            "recipe": {"include_last_failure": 0},
        },
        "memory_policy": {"automatic_repeat_mode": "advisory"},
        "verification_policy": {"visible_smoke_tests": []},
        "model_verifier_policy": {"enabled": True, "runs_on": ["solver_submit"]},
        "reconfigure_policy": {"max_versions": 2, "allowed_owners": ["harness_config"]},
        "helper_script_policy": {"enabled": True, "directory": "/app/.aether_tools"},
        "local_verification_limits": ["checks are advisory"],
    }


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Create the requested artifact.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor("filesystem", "files", tool_names=("read_file", "write_file")),
            "shell": CapabilityDescriptor("shell", "shell", tool_names=("run_command",)),
        },
    )


def _ir(changes: dict[str, object] | None = None):
    raw = _raw()
    for path, value in (changes or {}).items():
        section, field = path.split(".", 1)
        raw.setdefault(section, {})[field] = value  # type: ignore[index]
    return harness_config_to_runtime_ir(parse_harness_config_ir(json.dumps(raw)), _env())


def test_manifest_is_exhaustive_for_supported_top_level_fields() -> None:
    validate_field_realization_manifest()
    roots = {entry.path[2:].split(".", 1)[0] for entry in FIELD_REALIZATION_MANIFEST}
    assert set(SUPPORTED_TOP_LEVEL_CONFIG_FIELDS) <= roots
    assert all(
        entry.authority != ARCHITECT_RUNTIME_CONTROL or entry.runtime_consumer
        for entry in FIELD_REALIZATION_MANIFEST
    )
    assert field_realization_manifest_as_dicts()


def test_model_facing_contract_omits_migration_only_knobs() -> None:
    prompt = WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    for forbidden in (
        '"tool_policy"',
        '"require_query_before_repeat"',
        '"require_query_before_overwrite"',
        '"index_by"',
        '"structural_checks"',
        '"solver_callable_checks"',
        '"failure_feedback_policy"',
        '"trust_level"',
    ):
        assert forbidden not in prompt
    manual = build_runtime_manual()
    assert "memory_policy.automatic_repeat_mode" in manual["hard_configurable"]
    assert "memory_policy" not in manual["hard_configurable"]


@pytest.mark.parametrize(
    "path, baseline, changed, projection",
    [
        ("context_policy.mode", "default_bounded", "rolling_recent", lambda ir: ir.context_policy.mode),
        ("context_policy.always_include", ["open_obligations"], ["live_processes"], lambda ir: ir.context_policy.include_sections),
        ("context_policy.model_context_window_tokens", 50_000, 60_000, lambda ir: ir.context_policy.model_context_window_tokens),
        ("memory_policy.automatic_repeat_mode", "advisory", "soft_block_exact_repeat", lambda ir: ir.automatic_memory_policy.mode),
        ("model_verifier_policy.enabled", True, False, lambda ir: ir.model_verifier_policy.enabled),
        ("helper_script_policy.enabled", True, False, lambda ir: ir.helper_tool_policy.allow_creation),
        ("helper_script_policy.directory", "/app/.aether_tools", "/app/.other_tools", lambda ir: ir.helper_tool_policy.task_local_dir),
        ("reconfigure_policy.max_versions", 2, 4, lambda ir: ir.reconfigure_policy.max_reconfigurations),
        ("reconfigure_policy.allowed_owners", ["harness_config"], ["environment"], lambda ir: ir.reconfigure_policy.allowed_owners),
    ],
)
def test_retained_control_changes_reach_runtime(path, baseline, changed, projection) -> None:
    assert projection(_ir({path: baseline})) != projection(_ir({path: changed}))


def test_visible_smoke_control_changes_compiled_checks() -> None:
    baseline = _raw()
    changed = _raw()
    changed["verification_policy"] = {
        "visible_smoke_tests": [{"type": "file_exists", "path": "/app/output.txt"}],
    }
    base_ir = harness_config_to_runtime_ir(parse_harness_config_ir(json.dumps(baseline)), _env())
    changed_ir = harness_config_to_runtime_ir(parse_harness_config_ir(json.dumps(changed)), _env())
    assert base_ir.check_plan == ()
    assert changed_ir.check_plan


def test_prompt_and_evidence_controls_reach_runtime() -> None:
    baseline = _raw()
    changed = _raw()
    changed["task_understanding"] = "Create a different artifact."
    changed["visible_contract"] = [{
        "literal": "different.txt",
        "meaning": "different required output path",
        "contrast": "output.txt",
    }]
    changed["solver_system_prompt"] = {"role": "different solver", "workflow": ["inspect"]}
    changed["verifier_system_prompt"] = {
        "role": "different inspector",
        "success_criteria": ["different state"],
        "required_evidence": ["different evidence"],
    }
    changed["re_derivable_claims"] = ["sha256(output)"]
    base_ir = harness_config_to_runtime_ir(parse_harness_config_ir(json.dumps(baseline)), _env())
    changed_ir = harness_config_to_runtime_ir(parse_harness_config_ir(json.dumps(changed)), _env())
    assert base_ir.architect_summary != changed_ir.architect_summary
    assert base_ir.visible_contract != changed_ir.visible_contract
    assert base_ir.solver_identity_prompt != changed_ir.solver_identity_prompt
    assert base_ir.verifier_identity_prompt != changed_ir.verifier_identity_prompt
    assert base_ir.re_derivable_claims != changed_ir.re_derivable_claims


def test_context_failure_and_recipe_controls_reach_runtime() -> None:
    baseline = _ir({"context_policy.include_on_failure": ["failure_clusters"]})
    changed = _ir({"context_policy.include_on_failure": ["live_processes"]})
    assert baseline.context_policy.include_sections != changed.context_policy.include_sections

    raw = _raw()
    raw["context_policy"]["recipe"] = {"include_last_failure": 1}  # type: ignore[index]
    recipe_ir = harness_config_to_runtime_ir(parse_harness_config_ir(json.dumps(raw)), _env())
    assert recipe_ir.context_policy.recipe is not None
    assert recipe_ir.context_policy.recipe.include_last_failure == 1


def test_semantic_route_controls_reach_runtime() -> None:
    raw = _raw()
    raw["clause_coverage"] = [{
        "clause_id": "deliverable",
        "solver_handling": "write the artifact",
        "verifier_check": "read the artifact",
    }]
    raw["verifier_strategy"] = {
        "clause_checks": [{
            "clause_id": "deliverable",
            "inspection_route": "overlay_run_command:cat",
            "fallback_route": None,
            "falsification_check": "content is absent",
            "required_evidence_class": "behavioral",
        }],
        "false_positive_traps": ["shape-only output"],
        "return_all_findings": True,
    }
    ir = harness_config_to_runtime_ir(parse_harness_config_ir(json.dumps(raw)), _env())
    assert ir.semantic_clause_coverage
    assert ir.semantic_verifier_checks


def test_model_verifier_trigger_contract_fails_closed_on_different_trigger() -> None:
    raw = _raw()
    raw["model_verifier_policy"] = {"enabled": True, "runs_on": ["deterministic_failure"]}
    with pytest.raises(Exception, match="runs_on must be exactly"):
        parse_harness_config_ir(json.dumps(raw))


def test_deprecated_fields_are_explicitly_migration_only() -> None:
    raw = _raw()
    raw.update({
        "tool_policy": {"enabled_tools": ["read_file"]},
        "memory_policy": {
            "automatic_repeat_mode": "advisory",
            "require_query_before_repeat": False,
            "require_query_before_overwrite": False,
            "index_by": ["path"],
        },
        "verification_policy": {"structural_checks": [], "solver_callable_checks": False},
        "failure_feedback_policy": {
            "persist_until": "never",
            "show_age_steps": False,
            "show_evidence": False,
        },
        "helper_script_policy": {
            "enabled": True,
            "directory": "/app/.aether_tools",
            "trust_level": "trusted",
        },
        "reconfigure_policy": {
            "enabled": False,
            "max_versions": 2,
            "allowed_owners": ["harness_config"],
        },
    })
    config = parse_harness_config_ir(json.dumps(raw))
    assert set(config.deprecated_field_paths) == {
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
    }


def test_manifest_fails_closed_for_unrealized_control(monkeypatch) -> None:
    original = field_manifest.FIELD_REALIZATION_MANIFEST
    monkeypatch.setattr(
        field_manifest,
        "FIELD_REALIZATION_MANIFEST",
        (replace(original[1], runtime_consumer=None),) + original[2:],
    )
    with pytest.raises(RuntimeError, match="controlling Architect field has no runtime consumer"):
        field_manifest.validate_field_realization_manifest()

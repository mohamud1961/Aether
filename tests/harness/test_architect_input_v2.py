from __future__ import annotations

import json

from aether.architect_input import build_architect_input, build_architect_runtime_contract
from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.kernel_messages import build_architect_request
from aether.runtime_ir import CapabilityDescriptor, EnvMap, FIXED_KERNEL_TOOL_SURFACE
from aether.workbench_prompt import WORKBENCH_ARCHITECT_SYSTEM_PROMPT


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Create /app/server.py and serve the required public interface on port 8080.",
        workspace_root="/app",
        visible_files=("README.md", "starter.py"),
        visible_dirs=("fixtures",),
        file_tree="/app\n- README.md\n- starter.py\n- fixtures/\n",
        file_map_summary={
            "top_level": ["README.md", "fixtures", "starter.py"],
            "extension_counts": {".md": 1, ".py": 1},
            "visible_file_count": 2,
            "visible_dir_count": 1,
            "instruction_output_paths": ["/app/server.py"],
            "prompt_declared_output_paths": ["server.py"],
        },
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", available=True, tool_names=("read_file", "write_file")
            ),
            "shell": CapabilityDescriptor(
                "shell", "commands", available=True, tool_names=("run_command",)
            ),
            "managed_process": CapabilityDescriptor(
                "managed_process", "processes", available=True,
                tool_names=("launch_process", "probe_service", "stop_process"),
            ),
        },
        network_scope="loopback_only",
        resource_limits={"agent_timeout_sec": 900, "memory": "4GiB"},
        task_metadata={
            "visible_validation_surfaces": [
                {"kind": "readme", "value": "README.md", "evidence": "visible workspace file"}
            ],
            "declared_assets": [
                {"path": "starter.py", "extension": ".py", "mime_type": "text/x-python"}
            ],
            "visible_examples": [],
            "visible_material_summary": {"visible_file_count": 2},
            "observed_environment_support": {
                "commands": {"python3": "available"},
                "network": {"status": "loopback_only"},
            },
            "reviewer_probe_support": {
                "can_read_files": True,
                "can_probe_http": True,
                "source": "verifier_inspector_schema_and_live_probe_tools",
            },
            "environment_probe": {
                "command_names": {
                    "python3": {"available": True, "path": "/usr/bin/python3", "version": "3.12"},
                    "curl": {"available": True, "path": "/usr/bin/curl"},
                },
                "python": {
                    "preferred": "python3",
                    "interpreters": ["python3"],
                    "modules": {"flask": {"available": True, "version": "3.0"}},
                },
            },
        },
    )


def test_architect_input_has_one_compact_authority_shape() -> None:
    request = build_architect_input(_env())

    assert set(request) == {
        "schema_version", "request_identity", "task", "environment", "runtime_contract"
    }
    assert request["schema_version"] == "architect_request.v2"
    assert request["task"]["prompt"].startswith("Create /app/server.py")
    assert request["environment"]["probe_facts"]["python"]["preferred"] == "python3"
    assert request["runtime_contract"]["output_schema_version"] == "harness_config.v1"


def test_architect_request_contains_no_deterministic_semantic_preanalysis_or_stale_ir_contract() -> None:
    env = _env()
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(env))
    request = build_architect_request(env, compiler)
    encoded = json.dumps(request, sort_keys=True)

    for forbidden in (
        "objective_graph",
        "eval_index",
        "required_ir_fields",
        "runtime_manual",
        "architect_summary",
        "solver_identity_prompt",
        "selected_capabilities",
        "integrity:clean",
    ):
        assert forbidden not in encoded
    assert encoded.count(env.task_prompt) == 1


def test_runtime_contract_exposes_exact_controls_without_tool_selection() -> None:
    contract = build_architect_runtime_contract()
    supported = contract["supported_values"]
    authority = contract["field_authority"]

    assert contract["kernel_invariants"]["architect_selects_tools"] is False
    assert contract["kernel_invariants"]["fixed_solver_action_surface"] == list(FIXED_KERNEL_TOOL_SURFACE)
    assert "clause_coverage" in authority["architect_controls"]
    assert "verifier_strategy" in authority["architect_controls"]
    assert "tool_policy" in authority["migration_only_forbidden_in_output"]
    assert "active_completion_findings" in supported["context_exact_selectors"]
    assert "command_results" in supported["context_recent_selectors"]
    assert supported["verifier_route_ceilings"]["probe_port"] == "metadata_proxy"
    assert supported["verifier_route_ceilings"]["perceive_artifact"] == "independent_semantic"
    assert supported["visible_smoke_test_schemas"]["file_exists"]["required"] == ["type", "path"]
    rules = contract["semantic_contract"]["proof_obligation_route_rules"]
    assert rules["generated_interface_semantics"]["minimum_evidence_class"] == "independent_semantic"
    assert rules["generated_interface_semantics"]["requires_available_route"] is True
    assert "blocked_by_harness_config" in rules["unavailable_required_route"]
    assert "contrast owner" in contract["semantic_contract"]["visible_contract_contrast_rule"]


def test_prompt_is_concise_and_matches_the_typed_contract() -> None:
    prompt = WORKBENCH_ARCHITECT_SYSTEM_PROMPT

    assert len(prompt) < 15_000
    assert '"clause_coverage"' in prompt
    assert '"verifier_strategy"' in prompt
    assert "context selectors are enum names, not paths or prose" in prompt.lower()
    assert "The Architect owns task interpretation" in prompt
    assert "Return exactly one strict JSON object" in prompt
    for stale in (
        '"architect_summary"',
        '"solver_identity_prompt"',
        '"selected_capabilities"',
        '"process_policy"',
        '"bootstrap_policy"',
        '"completion_policy"',
        '"check_plan"',
    ):
        assert stale not in prompt


def test_request_is_substantially_smaller_than_the_previous_dynamic_contract() -> None:
    encoded = json.dumps(build_architect_input(_env()), sort_keys=True, separators=(",", ":"))

    # The audited predecessor averaged ~16k dynamic characters, ~13.9k of
    # which was a duplicated prose runtime manual. This factual request should
    # remain comfortably below half that size for a representative task.
    assert len(encoded) < 8_000


def test_task_specific_paths_are_facts_not_context_selector_values() -> None:
    request = build_architect_input(_env())
    selectors = request["runtime_contract"]["supported_values"]

    assert "/app/server.py" in request["task"]["path_facts"]["instruction_output_paths"]
    assert all("/" not in item for item in selectors["context_exact_selectors"])
    assert all("/" not in item for item in selectors["context_recent_selectors"])

from __future__ import annotations

import pytest

from aether.persistent_runtime import (
    INCUMBENT_PREFIX_RENDERER,
    MINIMAL_REALITY_LOOP_PREFIX_RENDERER,
    build_persistent_runtime,
)
from aether.runtime_ir import CapabilityDescriptor, EnvMap


def _envmap() -> EnvMap:
    probe = {
        "schema_version": "environment_probe.v1",
        "workspace_root": "/app",
        "command_names": {
            "python3": {"available": True, "path": "/usr/bin/python3"},
            "git": {"available": True, "path": "/usr/bin/git"},
        },
        "python": {
            "preferred": "python3",
            "interpreters": ["python3"],
            "modules": {"json": {"available": True, "available_in": ["python3"]}},
        },
        "network": {"status": "available", "value": "available"},
        "task_hints": {},
    }
    return EnvMap(
        task_prompt="Inspect the repository and write /app/answer.txt.",
        workspace_root="/app",
        visible_files=("/app/input.txt", "/app/config.json"),
        visible_dirs=("/app",),
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "filesystem", True, ("read_file", "write_file")
            ),
            "shell": CapabilityDescriptor("shell", "shell", True, ("run_command",)),
        },
        task_metadata={"environment_probe": probe},
        network_scope="available",
        file_tree="/app\n- input.txt\n- config.json",
        file_map_summary={"extension_counts": {".txt": 1, ".json": 1}},
    )


def _sections(resolved) -> dict[str, str]:
    assert resolved.compiled is not None
    return {str(name): str(value) for name, value in resolved.compiled.stable_prefix_sections}


def test_default_renderer_is_exact_explicit_incumbent_renderer() -> None:
    env = _envmap()
    implicit = build_persistent_runtime(env, solver_context_mode="full")
    explicit = build_persistent_runtime(
        env,
        solver_context_mode="full",
        solver_prefix_renderer=INCUMBENT_PREFIX_RENDERER,
    )
    assert implicit.compiled is not None and explicit.compiled is not None
    assert implicit.compiled.stable_prefix_sections == explicit.compiled.stable_prefix_sections
    assert implicit.compiled.config_realization == explicit.compiled.config_realization
    assert "solver_prefix_renderer" not in implicit.compiled.config_realization


def test_minimal_renderer_removes_only_preloaded_inventory_sections() -> None:
    env = _envmap()
    incumbent = build_persistent_runtime(env, solver_context_mode="full")
    minimal = build_persistent_runtime(
        env,
        solver_context_mode="full",
        solver_prefix_renderer=MINIMAL_REALITY_LOOP_PREFIX_RENDERER,
    )
    assert incumbent.compiled is not None and minimal.compiled is not None
    incumbent_sections = _sections(incumbent)
    minimal_sections = _sections(minimal)

    removed = {
        "envmap",
        "envmap_file_tree",
        "envmap_file_map_summary",
        "environment_probe",
    }
    for name in removed:
        assert name in incumbent_sections
        assert name not in minimal_sections

    preserved = {
        "tool_semantics",
        "completion_controls",
        "task_prompt",
        "solver_identity",
        "refusal_boundary",
    }
    for name in preserved:
        assert minimal_sections[name] == incumbent_sections[name]

    assert "environment_discovery" not in minimal_sections
    assert set(incumbent_sections) - set(minimal_sections) == removed


def test_minimal_renderer_preserves_runtime_authority_and_full_custody() -> None:
    env = _envmap()
    incumbent = build_persistent_runtime(env, solver_context_mode="full")
    minimal = build_persistent_runtime(
        env,
        solver_context_mode="full",
        solver_prefix_renderer=MINIMAL_REALITY_LOOP_PREFIX_RENDERER,
    )
    assert incumbent.compiled is not None and minimal.compiled is not None
    i = incumbent.compiled
    m = minimal.compiled

    assert m.task_contract_identity == i.task_contract_identity
    assert m.env_digest == i.env_digest == env.digest()
    assert m.action_schema == i.action_schema
    assert m.selected_capabilities == i.selected_capabilities
    assert m.config_realization["environment_probe"] == i.config_realization["environment_probe"]
    assert m.config_realization["raw_task_semantic_authority"] is True
    assert m.config_realization["solver_context_mode"] == "full"
    assert m.config_realization["solver_prefix_renderer"] == MINIMAL_REALITY_LOOP_PREFIX_RENDERER
    assert m.config_realization["tools_visible_to_solver"] == i.config_realization["tools_visible_to_solver"]


def test_minimal_renderer_does_not_inject_reasoning_or_discovery_guidance() -> None:
    minimal = build_persistent_runtime(
        _envmap(),
        solver_context_mode="full",
        solver_reasoning_mode="control",
        solver_prefix_renderer=MINIMAL_REALITY_LOOP_PREFIX_RENDERER,
    )
    sections = _sections(minimal)
    assert "solver_reasoning_treatment" not in sections
    assert "solver_commitment_contract" not in sections
    assert "environment_discovery" not in sections


def test_unknown_prefix_renderer_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported Solver prefix renderer"):
        build_persistent_runtime(_envmap(), solver_prefix_renderer="mystery")

from __future__ import annotations

import json

from aether.compiler_prefix import (
    persistent_model_environment_probe,
    persistent_model_environment_probe_compact,
    persistent_model_environment_probe_compact_guided,
    persistent_model_environment_probe_compact_scoped,
)
from aether.persistent_runtime import build_persistent_runtime
from aether.runtime_ir import CapabilityDescriptor, EnvMap


def _large_probe() -> dict:
    commands = {
        f"tool{i}": {"available": True, "path": f"/usr/bin/tool{i}"}
        for i in range(180)
    }
    commands.update({
        "python3": {"available": True, "path": "/usr/bin/python3"},
        "grpcurl": {"available": True, "path": "/usr/bin/grpcurl"},
        "workspace-tool-a": {"available": True, "path": "/app/bin/workspace-tool-a"},
        "workspace-tool-b": {"available": True, "path": "/app/tools/workspace-tool-b"},
        "missing-tool": {"available": False, "path": ""},
    })
    modules = {
        f"pkg{i}": {"available": True, "available_in": ["python3"]}
        for i in range(180)
    }
    modules.update({
        "grpc": {"available": True, "available_in": ["python3"]},
        "numpy": {"available": True, "available_in": ["python3"]},
    })
    return {
        "schema_version": "environment_probe.v1",
        "workspace_root": "/app",
        "command_names": commands,
        "resources": {
            "schema_version": "resource_probe.v1",
            "cpu": {"effective_cores": 1.0, "status": "probed"},
            "memory": {"effective_limit_bytes": 2_147_483_648, "status": "probed"},
        },
        "discovered_command_names": sorted(commands)[:128],
        "discovery_policy": {"commands": "bounded", "modules": "bounded"},
        "python": {
            "preferred": "python3",
            "interpreters": ["python3"],
            "interpreter_details": {"python3": {"pip_available": True}},
            "package_contract": {
                "pip_available": True,
                "uv_available": False,
                "network_status": "available",
                "install_available": True,
            },
            "modules": modules,
            "python3": {"executable": "/usr/bin/python3", "version": "3.12.0"},
        },
        "network": {"status": "available", "value": "available"},
        "task_hints": {
            "requested_command_names": ["grpcurl", "missing-tool"],
            "missing_requested_commands": ["missing-tool"],
        },
        "validation_guidance": {"preferred_python": "python3", "missing_commands": ["missing-tool"]},
    }


def _envmap(probe: dict) -> EnvMap:
    return EnvMap(
        task_prompt="Build and validate the requested artifact.",
        workspace_root="/app",
        visible_files=("/app/input.txt", "/app/service.proto"),
        visible_dirs=("/app",),
        capabilities={
            "filesystem": CapabilityDescriptor("filesystem", "filesystem", True, ("read_file", "write_file")),
            "shell": CapabilityDescriptor("shell", "shell", True, ("run_command",)),
        },
        task_metadata={"environment_probe": probe},
        network_scope="available",
        file_tree="/app\n- input.txt\n- service.proto",
        file_map_summary={"extension_counts": {".txt": 1, ".proto": 1}},
    )


def _section_map(compiled) -> dict[str, str]:
    return {str(k): str(v) for k, v in compiled.stable_prefix_sections}


def test_compact_probe_preserves_decision_relevant_facts_not_exhaustive_inventory() -> None:
    probe = _large_probe()
    full = persistent_model_environment_probe(probe)
    compact = persistent_model_environment_probe_compact(probe)

    assert compact["workspace_root"] == "/app"
    assert compact["network"] == probe["network"]
    assert compact["resources"] == probe["resources"]
    assert compact["commands"]["probed_count"] == len(probe["command_names"])
    assert compact["commands"]["available_count"] == len(probe["command_names"]) - 1
    assert compact["commands"]["requested"]["grpcurl"]["available"] is True
    assert compact["commands"]["requested"]["grpcurl"]["path"] == "/usr/bin/grpcurl"
    assert compact["commands"]["requested"]["missing-tool"]["available"] is False
    assert compact["missing_requested_commands"] == ["missing-tool"]
    assert compact["python"]["preferred"] == "python3"
    assert compact["python"]["module_probe_count"] == len(probe["python"]["modules"])
    assert compact["python"]["available_module_count"] == len(probe["python"]["modules"])
    assert compact["python"]["package_install"]["pip_available"] is True
    assert "tool17" not in json.dumps(compact, sort_keys=True)
    assert "pkg17" not in json.dumps(compact, sort_keys=True)

    full_bytes = len(json.dumps(full, sort_keys=True, separators=(",", ":")).encode())
    compact_bytes = len(json.dumps(compact, sort_keys=True, separators=(",", ":")).encode())
    assert compact_bytes * 5 < full_bytes


def test_compact_runtime_changes_model_view_not_runtime_authority_or_custody() -> None:
    probe = _large_probe()
    envmap = _envmap(probe)
    full = build_persistent_runtime(envmap, solver_context_mode="full")
    compact = build_persistent_runtime(envmap, solver_context_mode="compact")
    assert full.compiled is not None and compact.compiled is not None
    f = full.compiled
    c = compact.compiled

    assert f.task_contract_identity == c.task_contract_identity
    assert f.action_schema == c.action_schema
    assert f.selected_capabilities == c.selected_capabilities
    assert f.env_digest == c.env_digest == envmap.digest()
    assert f.config_realization["environment_probe"] == probe
    assert c.config_realization["environment_probe"] == probe
    assert f.config_realization["tools_visible_to_solver"] == c.config_realization["tools_visible_to_solver"]

    fs = _section_map(f)
    cs = _section_map(c)
    assert "envmap_file_tree" in fs and "envmap_file_tree" not in cs
    assert "envmap_file_map_summary" in fs and "envmap_file_map_summary" not in cs
    assert "environment_discovery" not in fs and "environment_discovery" in cs
    assert len(cs["environment_probe"].encode()) * 5 < len(fs["environment_probe"].encode())


def test_compact_probe_tells_solver_how_to_recover_omitted_detail_on_demand() -> None:
    compact = persistent_model_environment_probe_compact(_large_probe())
    discovery = compact["discovery"]
    assert "run_command" in discovery["commands"]
    assert "import/probe" in discovery["python_modules"]
    assert "read_file" in discovery["files"]


def test_compact_guided_probe_adds_generic_first_choice_without_leaking_inventory() -> None:
    guided = persistent_model_environment_probe_compact_guided(_large_probe())
    encoded = json.dumps(guided, sort_keys=True)
    assert guided["schema_version"] == "environment_probe.compact_guided.v1"
    assert guided["guidance_version"] == "demand_loaded_inventory.v1"
    assert "query_history" in guided["discovery"]["first_choice"]
    assert "revalidate" in guided["discovery"]["first_choice"]
    assert "every PATH entry" in guided["discovery"]["bounded_fallback"]
    assert "completion evidence" in guided["discovery"]["evidence_boundary"]
    assert "tool17" not in encoded
    assert "pkg17" not in encoded


def test_compact_guided_runtime_preserves_control_plane_and_is_distinct_model_view() -> None:
    probe = _large_probe()
    envmap = _envmap(probe)
    compact = build_persistent_runtime(envmap, solver_context_mode="compact")
    guided = build_persistent_runtime(envmap, solver_context_mode="compact_guided")
    assert compact.compiled is not None and guided.compiled is not None
    assert compact.compiled.env_digest == guided.compiled.env_digest == envmap.digest()
    assert compact.compiled.config_realization["environment_probe"] == probe
    assert guided.compiled.config_realization["environment_probe"] == probe
    compact_sections = _section_map(compact.compiled)
    guided_sections = _section_map(guided.compiled)
    assert "environment_discovery" in compact_sections
    assert "environment_discovery" in guided_sections
    assert "compact_guided" in guided.compiled.config_realization["solver_context_mode"]
    assert "query_history" in guided_sections["environment_probe"]
    assert len(guided_sections["environment_probe"].encode()) < len(
        _section_map(build_persistent_runtime(envmap, solver_context_mode="full").compiled)["environment_probe"].encode()
    )


def test_compact_scoped_projects_only_task_local_discovery_roots_not_inventory() -> None:
    probe = _large_probe()
    scoped = persistent_model_environment_probe_compact_scoped(probe)
    encoded = json.dumps(scoped, sort_keys=True)
    assert scoped["schema_version"] == "environment_probe.compact_scoped.v1"
    assert scoped["guidance_version"] == "bounded_live_discovery.v1"
    assert scoped["commands"]["workspace_search_roots"] == ["/app/bin", "/app/tools"]
    assert "/usr/bin" not in scoped["commands"]["workspace_search_roots"]
    assert "workspace-tool-a" not in encoded
    assert "workspace-tool-b" not in encoded
    assert "tool17" not in encoded
    assert "pkg17" not in encoded
    assert "one bounded discriminating action" in scoped["discovery"]["behavioral_descriptor"]
    assert "do not assume" in scoped["discovery"]["history_boundary"]


def test_compact_scoped_runtime_keeps_full_probe_in_custody_but_small_model_view() -> None:
    probe = _large_probe()
    envmap = _envmap(probe)
    full = build_persistent_runtime(envmap, solver_context_mode="full")
    scoped = build_persistent_runtime(envmap, solver_context_mode="compact_scoped")
    assert full.compiled is not None and scoped.compiled is not None
    assert scoped.compiled.config_realization["environment_probe"] == probe
    assert scoped.compiled.env_digest == full.compiled.env_digest == envmap.digest()
    sections = _section_map(scoped.compiled)
    full_sections = _section_map(full.compiled)
    assert "envmap_file_tree" not in sections
    assert "envmap_file_map_summary" not in sections
    assert "workspace_search_roots" in sections["environment_probe"]
    assert "query_history with that" not in sections["environment_discovery"]
    assert "completion_freshness_guidance" in sections
    assert "final state-changing action" in sections["completion_freshness_guidance"]
    assert "one bounded current read-only observation" in sections["completion_freshness_guidance"]
    assert len(sections["environment_probe"].encode()) * 5 < len(full_sections["environment_probe"].encode())

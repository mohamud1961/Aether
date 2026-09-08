from __future__ import annotations

import json
from dataclasses import replace

import pytest

from aether.envmap_builder import build_envmap_from_task
from aether.compiler_prefix import pcr_model_environment_probe_compact
from aether.kernel import AetherNextKernel
from aether.pcr_runtime import build_pcr_runtime
from aether.runtime_ir import EnvMap


def _probe() -> dict:
    commands = {
        f"tool{i}": {"available": True, "path": f"/usr/bin/tool{i}", "version": f"{i}.0"}
        for i in range(300)
    }
    commands["git"] = {"available": True, "path": "/usr/bin/git", "version": "2.0"}
    modules = {
        f"pkg{i}": {"available": True, "available_in": ["python3"]}
        for i in range(200)
    }
    return {
        "schema_version": "environment_probe.v1",
        "workspace_root": "/app",
        "command_names": commands,
        "discovered_command_names": sorted(commands)[:256],
        "resources": {
            "cpu": {"effective_cores": 4.0},
            "memory": {"effective_limit_bytes": 8 * 1024**3},
            "gpu": {"device_count": 0},
        },
        "python": {
            "preferred": "python3",
            "interpreters": ["python3"],
            "modules": modules,
            "package_contract": {
                "pip_available": True,
                "uv_available": True,
                "network_status": "available",
                "install_available": True,
            },
        },
        "network": {"status": "available"},
        "task_hints": {
            "requested_command_names": ["git"],
            "missing_requested_commands": [],
        },
        "validation_guidance": {"notes": ["large legacy guidance"]},
    }


def _env(tmp_path) -> EnvMap:
    (tmp_path / "instruction.md").write_text(
        "Implement the requested behavior exactly.", encoding="utf-8"
    )
    (tmp_path / "seed.txt").write_text("seed", encoding="utf-8")
    base = build_envmap_from_task(
        str(tmp_path),
        "Implement the requested behavior exactly.",
        workspace_root="/app",
        projection_mode="factual_only",
    )
    paths = tuple(f"src/path_{i:04d}.py" for i in range(500))
    metadata = dict(base.task_metadata)
    metadata["environment_probe"] = _probe()
    return replace(
        base,
        visible_files=paths,
        visible_dirs=("src",),
        file_tree="\n".join(paths),
        file_map_summary={"files": list(paths), "count": len(paths)},
        task_metadata=metadata,
    )


def _section(compiled, name: str) -> str:
    return next(body for section, body in compiled.stable_prefix_sections if section == name)


def test_compact_context_removes_inventory_bulk_without_changing_task_or_capabilities(tmp_path) -> None:
    env = _env(tmp_path)
    full = build_pcr_runtime(env, solver_context_mode="full").compiled
    compact = build_pcr_runtime(env, solver_context_mode="compact").compiled
    assert full is not None and compact is not None

    assert full.task_prompt == compact.task_prompt == env.task_prompt
    assert full.env_digest == compact.env_digest == env.digest()
    assert full.action_schema == compact.action_schema
    assert full.selected_capability_ids() == compact.selected_capability_ids()
    assert full.task_contract_identity == compact.task_contract_identity
    assert full.config_realization["solver_context_mode"] == "full"
    assert compact.config_realization["solver_context_mode"] == "compact"

    full_sections = dict(full.stable_prefix_sections)
    compact_sections = dict(compact.stable_prefix_sections)
    assert "envmap_file_tree" in full_sections
    assert "envmap_file_tree" not in compact_sections
    assert "envmap_file_map_summary" in full_sections
    assert "envmap_file_map_summary" not in compact_sections
    assert "environment_discovery" in compact_sections

    compact_probe = json.loads(_section(compact, "environment_probe"))
    assert compact_probe["resources"] == _probe()["resources"]
    assert compact_probe["network"] == _probe()["network"]
    assert compact_probe["commands"]["requested"]["git"]["available"] is True
    assert compact_probe["commands"]["probed_count"] == 301
    assert "tool299" not in json.dumps(compact_probe)
    assert "pkg199" not in json.dumps(compact_probe)

    full_chars = sum(len(msg["content"]) for msg in full.prefix_messages())
    compact_chars = sum(len(msg["content"]) for msg in compact.prefix_messages())
    assert compact_chars < full_chars * 0.25


def test_compact_probe_is_factual_summary_with_exact_resources_and_discovery() -> None:
    source = _probe()
    compact = pcr_model_environment_probe_compact(source)
    assert compact["resources"] == source["resources"]
    assert compact["network"] == source["network"]
    assert compact["python"]["preferred"] == "python3"
    assert compact["python"]["module_probe_count"] == 200
    assert "command -v" in compact["discovery"]["commands"]
    assert len(json.dumps(compact)) < len(json.dumps(source)) * 0.15


def test_solver_context_mode_fails_closed_on_unknown_treatment(tmp_path) -> None:
    with pytest.raises(ValueError, match="unsupported Solver context mode"):
        build_pcr_runtime(_env(tmp_path), solver_context_mode="mystery")
    with pytest.raises(ValueError, match="unsupported Solver context mode"):
        AetherNextKernel(solver_context_mode="mystery")

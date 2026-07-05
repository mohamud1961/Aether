"""Message-building helpers extracted from kernel.py to stay under 500 LOC."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Mapping

from .compiler import ConfigCompiler
from .runtime_ir import CompiledRuntime, EnvMap, normalize_relpath
from .runtime_manual import build_runtime_manual


def build_architect_request(
    envmap: EnvMap,
    compiler: ConfigCompiler,
) -> dict[str, Any]:
    """Build the request payload sent to the architect hook."""
    objective_graph, eval_index = compiler.analyze_envmap(envmap)
    return {
        "task_prompt": envmap.task_prompt,
        "envmap_digest": envmap.digest(),
        "envmap": {
            "workspace_root": envmap.workspace_root,
            "visible_files": [
                normalize_relpath(path, envmap.workspace_root)
                for path in envmap.visible_files
            ],
            "visible_dirs": [
                normalize_relpath(path, envmap.workspace_root)
                for path in envmap.visible_dirs
            ],
            "file_tree": envmap.file_tree,
            "file_map_summary": dict(envmap.file_map_summary),
            "services": dict(envmap.services),
            "resource_limits": dict(envmap.resource_limits),
            "permissions": dict(envmap.permissions),
            "grader_hints": dict(envmap.grader_hints),
            "interactive_features": dict(envmap.interactive_features),
            "task_metadata": dict(envmap.task_metadata),
            "environment_probe": dict(envmap.task_metadata.get("environment_probe", {}) or {}),
            "network_scope": envmap.network_scope,
        },
        "capability_index": list(compiler.registry.metadata_view()),
        "runtime_manual": build_runtime_manual(),
        "objective_graph": asdict(objective_graph),
        "eval_index": {
            "checks": [asdict(check) for check in eval_index.checks],
            "authoritative_check_ids": [
                check.check_id for check in eval_index.authoritative_checks()
            ],
        },
        "required_ir_fields": [
            "architect_summary",
            "solver_identity_prompt",
            "selected_capabilities",
            "process_policy",
            "bootstrap_policy",
            "completion_policy",
            "refusal_policy",
            "reconfigure_policy",
            "inspection_plan",
            "proof_plan",
            "check_plan",
            "forbidden_paths",
        ],
    }


def build_solver_messages(
    compiled: CompiledRuntime,
    context_packet: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Build the full message list sent to the solver hook."""
    messages = compiled.prefix_messages()
    messages.append(
        {
            "role": "system",
            "content": "[context_packet]\n"
            + json.dumps(
                context_packet,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        }
    )
    return messages

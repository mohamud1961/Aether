"""Public task resource metadata exposed without benchmark semantics."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Mapping


def _normalize_gpu_types(value: Any) -> list[str]:
    """Normalize an optional public GPU-type declaration without inference."""
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        values = list(value)
    else:
        values = [value]
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def _resource_budget(
    environment: Mapping[str, Any],
    *,
    agent_timeout: Any = None,
    verifier_timeout: Any = None,
) -> dict[str, Any]:
    """Preserve declared public runtime/resource facts exactly enough for EnvMap."""
    return {
        "agent_timeout_sec": agent_timeout,
        "verifier_timeout_sec": verifier_timeout,
        "build_timeout_sec": environment.get("build_timeout_sec"),
        "cpus": environment.get("cpus"),
        "memory": environment.get("memory"),
        "storage": environment.get("storage"),
        "memory_mb": environment.get("memory_mb"),
        "storage_mb": environment.get("storage_mb"),
        "gpus": environment.get("gpus"),
        "gpu_types": _normalize_gpu_types(environment.get("gpu_types")),
        "docker_image": environment.get("docker_image"),
        "network_mode": environment.get("network_mode"),
    }


def _declared_runtime_parity(
    solver_budget: Mapping[str, Any],
    verifier_budget: Mapping[str, Any],
    environment_mode: Any,
) -> dict[str, Any]:
    """Compare only resource facts actually declared on both public surfaces."""
    comparisons: dict[str, bool] = {}
    for key in ("cpus", "memory_mb", "storage_mb", "gpus", "gpu_types"):
        solver_value = solver_budget.get(key)
        verifier_value = verifier_budget.get(key)
        if solver_value is None or verifier_value is None:
            continue
        if key == "gpu_types" and (not solver_value or not verifier_value):
            continue
        comparisons[key] = solver_value == verifier_value

    if not comparisons:
        status = "verifier_resource_budget_not_declared"
    elif all(comparisons.values()):
        status = "declared_resources_match"
    else:
        status = "declared_resource_mismatch"

    mode = str(environment_mode or "unknown")
    return {
        "declared_environment_mode": mode,
        "artifact_transfer_required": mode == "separate",
        "comparable_resource_fields": comparisons,
        "status": status,
    }


def flatten_task_toml(task_toml: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return internal metadata plus model-safe factual runtime/resource budgets.

    Category, difficulty, tags, task names, and image identity remain internal.
    Model-facing callers may select only concrete constraints from the returned
    resource/runtime mappings. No task-family or tool-strategy inference occurs
    here.
    """
    data = dict(task_toml or {})
    metadata = data.get("metadata") if isinstance(data.get("metadata"), Mapping) else {}
    agent = data.get("agent") if isinstance(data.get("agent"), Mapping) else {}
    verifier = data.get("verifier") if isinstance(data.get("verifier"), Mapping) else {}
    environment = data.get("environment") if isinstance(data.get("environment"), Mapping) else {}
    verifier_environment = (
        verifier.get("environment")
        if isinstance(verifier.get("environment"), Mapping)
        else {}
    )
    tags = tuple(str(tag) for tag in metadata.get("tags", ()) if str(tag).strip())

    resource_budget = _resource_budget(
        environment,
        agent_timeout=agent.get("timeout_sec"),
        verifier_timeout=verifier.get("timeout_sec"),
    )
    verifier_resource_budget = _resource_budget(
        verifier_environment,
        verifier_timeout=verifier.get("timeout_sec"),
    )
    environment_mode = verifier.get("environment_mode")

    return {
        "task_version": data.get("version", data.get("schema_version", "")),
        "schema_version": data.get("schema_version", data.get("version", "")),
        "category": str(metadata.get("category", "")),
        "difficulty": str(metadata.get("difficulty", "")),
        "tags": tags,
        "expert_time_estimate_min": metadata.get("expert_time_estimate_min"),
        "junior_time_estimate_min": metadata.get("junior_time_estimate_min"),
        "agent_timeout_sec": agent.get("timeout_sec"),
        "verifier_timeout_sec": verifier.get("timeout_sec"),
        "environment": dict(environment),
        "resource_budget": resource_budget,
        "verifier_resource_budget": verifier_resource_budget,
        "verifier_environment_mode": environment_mode,
        "runtime_parity": _declared_runtime_parity(
            resource_budget,
            verifier_resource_budget,
            environment_mode,
        ),
    }

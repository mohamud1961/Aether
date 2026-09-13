"""Bounded live resource facts for Aether task environments.

This module reports what the current execution world actually exposes. It does
not infer task difficulty, select strategy, or replace task.toml resource
budgets. Declared budgets and live observations stay separate so mismatches are
auditable instead of silently normalized.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .execution import Executor


def _run(executor: Executor, command: str, *, workspace_root: str) -> tuple[int, str, str]:
    result = executor.run_command(command, cwd=workspace_root, timeout_s=10)
    return int(result.exit_code), str(result.stdout or ""), str(result.stderr or "")


def _positive_int(text: str) -> int | None:
    try:
        value = int(str(text).strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _positive_float(text: str) -> float | None:
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _probe_cpu(executor: Executor, *, workspace_root: str) -> dict[str, Any]:
    code, stdout, _stderr = _run(
        executor,
        "getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || true",
        workspace_root=workspace_root,
    )
    logical = _positive_int(stdout.splitlines()[-1] if stdout.splitlines() else "")

    quota_code, quota_out, _quota_err = _run(
        executor,
        "if test -r /sys/fs/cgroup/cpu.max; then cat /sys/fs/cgroup/cpu.max; fi",
        workspace_root=workspace_root,
    )
    quota_cores: float | None = None
    quota_status = "not_observed"
    parts = quota_out.strip().split()
    if quota_code == 0 and len(parts) >= 2:
        if parts[0] == "max":
            quota_status = "unlimited"
        else:
            quota = _positive_float(parts[0])
            period = _positive_float(parts[1])
            if quota is not None and period is not None:
                quota_cores = quota / period
                quota_status = "finite"

    effective: float | int | None = logical
    if quota_cores is not None:
        effective = quota_cores if logical is None else min(float(logical), quota_cores)
    return {
        "status": "probed" if logical is not None or quota_status != "not_observed" else "unknown",
        "logical_cores": logical,
        "cgroup_v2_quota_status": quota_status,
        "cgroup_v2_quota_cores": None if quota_cores is None else round(quota_cores, 6),
        "effective_cores": None if effective is None else round(float(effective), 6),
    }


def _probe_memory(executor: Executor, *, workspace_root: str) -> dict[str, Any]:
    _code, total_out, _err = _run(
        executor,
        "if test -r /proc/meminfo; then awk '/^MemTotal:/ {print $2 * 1024; exit}' /proc/meminfo; "
        "elif command -v sysctl >/dev/null 2>&1; then sysctl -n hw.memsize 2>/dev/null; fi",
        workspace_root=workspace_root,
    )
    visible_total = _positive_int(total_out.splitlines()[-1] if total_out.splitlines() else "")

    _limit_code, limit_out, _limit_err = _run(
        executor,
        "if test -r /sys/fs/cgroup/memory.max; then cat /sys/fs/cgroup/memory.max; fi",
        workspace_root=workspace_root,
    )
    limit_raw = limit_out.strip()
    cgroup_limit = None if not limit_raw or limit_raw == "max" else _positive_int(limit_raw)
    limit_status = (
        "unlimited" if limit_raw == "max" else
        "finite" if cgroup_limit is not None else
        "not_observed"
    )
    effective = visible_total
    if cgroup_limit is not None:
        effective = cgroup_limit if visible_total is None else min(visible_total, cgroup_limit)
    return {
        "status": "probed" if visible_total is not None or limit_status != "not_observed" else "unknown",
        "visible_total_bytes": visible_total,
        "cgroup_v2_limit_status": limit_status,
        "cgroup_v2_limit_bytes": cgroup_limit,
        "effective_limit_bytes": effective,
    }


def _probe_storage(executor: Executor, *, workspace_root: str) -> dict[str, Any]:
    code, stdout, _stderr = _run(
        executor,
        "df -Pk . 2>/dev/null | awk 'NR==2 {print $2, $3, $4}'",
        workspace_root=workspace_root,
    )
    parts = stdout.strip().split()
    if code != 0 or len(parts) != 3:
        return {"status": "unknown"}
    values = [_positive_int(item) for item in parts]
    if any(value is None for value in values):
        return {"status": "unknown"}
    total_kib, used_kib, available_kib = values  # type: ignore[misc]
    return {
        "status": "probed",
        "workspace_total_bytes": int(total_kib) * 1024,
        "workspace_used_bytes": int(used_kib) * 1024,
        "workspace_available_bytes": int(available_kib) * 1024,
    }


def _probe_gpu(
    executor: Executor,
    *,
    workspace_root: str,
    command_names: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    command_row = command_names.get("nvidia-smi", {})
    known_available = command_row.get("available") is True
    known_unavailable = command_row.get("available") is False
    if known_unavailable:
        return {
            "status": "command_unavailable",
            "backend": "nvidia-smi",
            "device_count": None,
            "devices": [],
        }
    command = (
        "nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader,nounits 2>/dev/null"
    )
    code, stdout, stderr = _run(executor, command, workspace_root=workspace_root)
    if code == 127 and not known_available:
        return {
            "status": "command_unavailable",
            "backend": "nvidia-smi",
            "device_count": None,
            "devices": [],
        }
    if code != 0:
        return {
            "status": "probe_failed",
            "backend": "nvidia-smi",
            "device_count": None,
            "devices": [],
            "exit_code": code,
            "stderr_excerpt": stderr[:500],
        }
    devices: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        parts = [part.strip() for part in line.split(",", 2)]
        if len(parts) != 3:
            continue
        gpu_index = int(parts[0]) if parts[0].isdigit() else None
        memory_mib = _positive_int(parts[2])
        if gpu_index is None:
            continue
        devices.append({
            "index": gpu_index,
            "name": parts[1],
            "memory_total_mib": memory_mib,
        })
    return {
        "status": "probed_present" if devices else "probed_no_devices",
        "backend": "nvidia-smi",
        "device_count": len(devices),
        "devices": devices,
    }


def probe_live_resources(
    executor: Executor,
    *,
    workspace_root: str,
    command_names: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return bounded live CPU/memory/storage/GPU observations."""
    commands = dict(command_names or {})
    return {
        "schema_version": "resource_probe.v1",
        "workspace_root": workspace_root,
        "cpu": _probe_cpu(executor, workspace_root=workspace_root),
        "memory": _probe_memory(executor, workspace_root=workspace_root),
        "storage": _probe_storage(executor, workspace_root=workspace_root),
        "gpu": _probe_gpu(
            executor,
            workspace_root=workspace_root,
            command_names=commands,
        ),
        "authority": "live_environment_observation",
    }


__all__ = ["probe_live_resources"]

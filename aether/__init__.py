"""Aether production package surface.

PCR Solver owns strategy; Aether owns execution, factual state, evidence and
lifecycle; the independent Verifier falsifies completion candidates.

Public convenience exports are resolved lazily so importing the Harbor adapter
does not eagerly import the entire execution graph before a task is actually
run. This changes import ownership only; the exported objects are unchanged.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "ActionRequest": (".runtime_ir", "ActionRequest"),
    "AetherNextKernel": (".kernel", "AetherNextKernel"),
    "CompiledRuntime": (".runtime_ir", "CompiledRuntime"),
    "EnvMap": (".runtime_ir", "EnvMap"),
    "KernelHooks": (".kernel", "KernelHooks"),
    "KernelResult": (".kernel", "KernelResult"),
    "MemoryExecutor": (".execution", "MemoryExecutor"),
    "ModelProfile": (".model_profile", "ModelProfile"),
    "PRODUCTION_PROFILE": (".model_profile", "PRODUCTION_PROFILE"),
    "SolverTurn": (".runtime_ir", "SolverTurn"),
    "StableEnvMap": (".world", "StableEnvMap"),
    "TaskClause": (".task_contract", "TaskClause"),
    "TaskContract": (".task_contract", "TaskContract"),
    "WorldState": (".world", "WorldState"),
    "WorldStateDeltaError": (".world", "WorldStateDeltaError"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

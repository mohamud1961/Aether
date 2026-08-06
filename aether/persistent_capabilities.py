"""PERSISTENT V0 capability/action ownership and runtime admission.

The provider schema is intentionally generic, but execution authority is not.
This module derives the exact action-to-capability contract from the compiled
runtime and rejects unknown, unavailable, or mismatched capability IDs before
dispatch. The same mapping is rendered to the Primary Agent context.
"""
from __future__ import annotations

from typing import Any, Mapping

from .persistent_provider_protocol import PERSISTENT_PRIMARY_ACTION_SCHEMA


_KERNEL_OWNED_ACTIONS = frozenset({
    "read_file_page",
    "read_output",
    "grep_output",
    "query_memory",
    "query_artifact_history",
    "inspect_diff",
    "record_observation",
    "report_blocker",
    "inspect_checks",
    "run_check",
})

_DEFAULT_CAPABILITY_OWNERS: Mapping[str, tuple[str, ...]] = {
    "read_file": ("filesystem",),
    "write_file": ("filesystem",),
    "run_command": ("shell",),
    "bootstrap_acquire": ("shell",),
    "launch_process": ("managed_process",),
    "start_job": ("managed_process",),
    "probe_job": ("managed_process",),
    "probe_service": ("service_probe", "managed_process"),
    "stop_process": ("managed_process",),
    "inspect_artifact": ("artifact_inspection", "filesystem"),
}


def persistent_capability_contract(compiled: Any) -> dict[str, tuple[str, ...]]:
    """Return the exact permitted capability IDs for each available action.

    Explicit descriptor ``tool_names`` are authoritative additions. Canonical
    fallback ownership exists for legacy descriptors that omit ``tool_names``.
    Kernel-owned retrieval/control actions use the explicit pseudo-capability
    ``kernel`` and do not borrow authority from an unrelated environment tool.
    """
    selected = tuple(getattr(compiled, "selected_capabilities", ()) or ())
    selected_ids = {
        str(getattr(capability, "capability_id", "")).strip()
        for capability in selected
        if str(getattr(capability, "capability_id", "")).strip()
    }
    explicit: dict[str, set[str]] = {}
    for capability in selected:
        capability_id = str(getattr(capability, "capability_id", "")).strip()
        if not capability_id:
            continue
        for tool_name in tuple(getattr(capability, "tool_names", ()) or ()):
            explicit.setdefault(str(tool_name), set()).add(capability_id)

    contract: dict[str, tuple[str, ...]] = {}
    for action_kind, _arguments in PERSISTENT_PRIMARY_ACTION_SCHEMA:
        owners = set(explicit.get(action_kind, set()))
        if action_kind in _KERNEL_OWNED_ACTIONS:
            owners.add("kernel")
        for default_owner in _DEFAULT_CAPABILITY_OWNERS.get(action_kind, ()):
            if default_owner in selected_ids:
                owners.add(default_owner)
        if owners:
            contract[action_kind] = tuple(sorted(owners))
    return contract


def persistent_capability_violation(action: Any, compiled: Any) -> str:
    """Return a mechanical refusal reason, or an empty string when admitted."""
    action_kind = str(getattr(action, "kind", "")).strip()
    capability_id = str(getattr(action, "capability_id", "")).strip()
    contract = persistent_capability_contract(compiled)
    allowed = contract.get(action_kind, ())
    if not allowed:
        return f"PERSISTENT action {action_kind!r} has no available runtime capability"
    if capability_id not in allowed:
        return (
            f"PERSISTENT capability {capability_id!r} does not own action {action_kind!r}; "
            f"allowed capability IDs: {', '.join(allowed)}"
        )
    return ""

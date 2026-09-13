"""Generic execution bridge for task-declared environment extensions.

V1 supports Harbor-declared MCP servers through an optional exact mode of the
existing ``run_command`` action.  This module owns no server-specific strategy;
it validates transport-neutral arguments, calls the executor's task-world
extension bridge, and emits an ordinary Aether receipt.
"""
from __future__ import annotations

import json
from typing import Any

from .ledger import Receipt
from .runtime_ir import ActionRequest, EnvMap


def _arguments_object(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(str(raw or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"extension_arguments_json is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("extension_arguments_json must encode one JSON object")
    return value


def execute_environment_extension(
    action: ActionRequest,
    step: int,
    executor: Any,
    envmap: EnvMap,
    *,
    timeout_s: int,
    timeout_note: str,
) -> Receipt:
    server = str(action.arguments.get("extension_server") or "").strip()
    operation = str(action.arguments.get("extension_operation") or "").strip()
    tool_name = str(action.arguments.get("extension_tool") or "").strip()
    if operation not in {"tools_list", "tools_call"}:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:extension",
            step=step,
            kind="environment_extension",
            success=False,
            summary=f"unsupported environment extension operation: {operation or 'missing'}",
            failure_class="action_validation",
            payload={
                "server": server,
                "operation": operation,
                "candidate_id": action.candidate_id,
            },
        )
    if operation == "tools_call" and not tool_name:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:extension",
            step=step,
            kind="environment_extension",
            success=False,
            summary="MCP tools_call requires extension_tool",
            failure_class="action_validation",
            payload={
                "server": server,
                "operation": operation,
                "candidate_id": action.candidate_id,
            },
        )
    try:
        arguments = _arguments_object(
            str(action.arguments.get("extension_arguments_json") or "{}")
        ) if operation == "tools_call" else {}
    except ValueError as exc:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:extension",
            step=step,
            kind="environment_extension",
            success=False,
            summary=str(exc),
            failure_class="action_validation",
            payload={
                "server": server,
                "operation": operation,
                "tool_name": tool_name,
                "candidate_id": action.candidate_id,
            },
        )

    call = getattr(executor, "call_environment_extension", None)
    if not callable(call):
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:extension",
            step=step,
            kind="environment_extension",
            success=False,
            summary="executor does not expose task-world environment extensions",
            failure_class="environment_extension_client_unavailable",
            payload={
                "server": server,
                "operation": operation,
                "tool_name": tool_name,
                "candidate_id": action.candidate_id,
            },
        )

    result = call(
        server_name=server,
        operation=operation,
        tool_name=tool_name,
        arguments=arguments,
        timeout_s=timeout_s,
    )
    if not isinstance(result, dict):
        result = {
            "success": False,
            "failure_class": "environment_extension_call_failed",
            "error": f"executor returned {type(result).__name__}, expected object",
        }
    success = result.get("success") is True
    payload = {
        "server": server,
        "operation": operation,
        "tool_name": tool_name,
        "arguments_sha256": __import__("hashlib").sha256(
            json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "timeout_s": timeout_s,
        "timeout_policy": timeout_note,
        "transport": str(result.get("transport") or ""),
        "result": result.get("result"),
        "error": str(result.get("error") or ""),
        "error_type": str(result.get("error_type") or ""),
        "exit_code": result.get("exit_code"),
        "bridge_provenance": str(result.get("bridge_provenance") or ""),
        "mutation_semantics": (
            "unknown_possible_external_state_change"
            if success and operation == "tools_call"
            else "read_only_discovery" if success and operation == "tools_list"
            else "none_failed_call"
        ),
        "state_change_basis": (
            "successful_external_tool_call_conservative_freshness_boundary"
            if success and operation == "tools_call"
            else ""
        ),
        "candidate_id": action.candidate_id,
    }
    modified_paths = tuple(str(p) for p in result.get("modified_paths", ()) or ())
    artifact_paths = tuple(str(p) for p in result.get("artifact_paths", ()) or ())
    removed_paths = tuple(str(p) for p in result.get("removed_paths", ()) or ())
    state_delta = dict(result.get("state_delta", {}) or {})
    if modified_paths:
        payload["modified_paths"] = modified_paths
    if artifact_paths:
        payload["artifact_paths"] = artifact_paths
    if removed_paths:
        payload["removed_paths"] = removed_paths
    if state_delta:
        payload["state_delta"] = state_delta
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:extension",
        step=step,
        kind="environment_extension",
        success=success,
        summary=(
            f"environment extension {server} {operation} succeeded"
            if success else
            f"environment extension {server} {operation} failed"
        ),
        state_change=(success and operation == "tools_call"),
        failure_class="" if success else str(
            result.get("failure_class") or "environment_extension_call_failed"
        ),
        payload={k: v for k, v in payload.items() if v not in (None, "")},
    )


__all__ = ["execute_environment_extension"]

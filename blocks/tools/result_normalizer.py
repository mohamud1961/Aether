"""Packet 05A tool candidate with stricter permission/runtime attribution."""

from __future__ import annotations

import json
from typing import Any

from blocks.tools.raw_bash import get_tools as baseline_get_tools


def get_tools() -> list[dict[str, Any]]:
    tools = baseline_get_tools()
    tool = dict(tools[0])
    tool["description"] = (
        "Execute a bash command with explicit permission-vs-runtime attribution telemetry."
    )
    return [tool]


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    call_class = _classify_tool_call_shape(tool_call)
    payload = _normalized_payload(tool_call)
    case_id = _extract_case_id(tool_call)
    if call_class != "valid_call":
        reason_code = (
            "tool_call_contract_unsupported_tool"
            if call_class == "unsupported_tool"
            else "tool_call_contract_malformed"
        )
        return {
            "tool_name": payload["tool_name"],
            "command": payload["command"],
            "exit_code": 1,
            "stdout": "",
            "stderr": reason_code,
            "timed_out": False,
            "result_class": "contract_error",
            "reason_code": reason_code,
            "permission_denied": False,
            "runtime_error": False,
            "tool_call_contract_class": call_class,
            "raw_tool_call_payload": tool_call,
            "normalized_tool_call_payload": payload,
            "case_id": case_id,
        }

    command = payload["command"]
    result = _normalize_exec_result(sandbox.exec(command))
    result_class, reason_code, attribution_trace = _classify_result(result)
    return {
        "tool_name": "raw_bash",
        "command": command,
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "timed_out": result["timed_out"],
        "result_class": result_class,
        "reason_code": reason_code,
        "permission_denied": result_class == "permission_denied",
        "runtime_error": result_class == "runtime_error",
        "tool_call_contract_class": call_class,
        "raw_tool_call_payload": tool_call,
        "normalized_tool_call_payload": payload,
        "case_id": case_id,
        "attribution_trace": attribution_trace,
    }


def _classify_tool_call_shape(tool_call: Any) -> str:
    if not isinstance(tool_call, dict):
        return "malformed_call"
    if tool_call.get("name") != "raw_bash":
        return "unsupported_tool" if isinstance(tool_call.get("name"), str) else "malformed_call"
    return "valid_call" if payload_command(tool_call) else "malformed_call"


def payload_command(tool_call: dict[str, Any]) -> str:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        command = arguments.get("command")
        return command if isinstance(command, str) and command else ""
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            parsed = {"command": arguments}
        if isinstance(parsed, dict):
            command = parsed.get("command")
            return command if isinstance(command, str) and command else ""
    return ""


def _normalized_payload(tool_call: Any) -> dict[str, Any]:
    if not isinstance(tool_call, dict):
        return {"tool_name": "unknown", "command": ""}
    return {
        "tool_name": tool_call.get("name") if isinstance(tool_call.get("name"), str) else "unknown",
        "command": payload_command(tool_call),
    }


def _normalize_exec_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"exit_code": 1, "stdout": "", "stderr": str(result), "timed_out": False, "error": "sandbox_exec_result_not_mapping"}
    return {
        "exit_code": _normalize_exit_code(result.get("exit_code")),
        "stdout": _text(result.get("stdout")),
        "stderr": _text(result.get("stderr")),
        "timed_out": bool(result.get("timed_out", False)),
        "error": _text(result.get("error")),
    }


def _classify_result(result: dict[str, Any]) -> tuple[str, str, dict[str, bool]]:
    merged = " ".join(part for part in (result["stderr"], result["stdout"], result["error"]) if part).lower()
    permission = any(marker in merged for marker in ("permission denied", "denied by policy", "operation not permitted", "access denied", " eacces", " eperm"))
    missing = any(marker in merged for marker in ("no such file", "not found", "does not exist"))
    trace = {"permission_signal_detected": permission, "runtime_signal_detected": missing or bool(result["error"]) or bool(result["timed_out"]) or result["exit_code"] not in {0, 126}}

    if result["timed_out"]:
        return ("runtime_error", "tool_runtime_timeout", trace)
    if result["error"]:
        return ("runtime_error", "tool_runtime_error_field", trace)
    if permission and missing:
        return ("runtime_error", "tool_runtime_mixed_permission_runtime_signals", trace)
    if result["exit_code"] == 126 or permission:
        return ("permission_denied", "tool_permission_denied", trace)
    if result["exit_code"] != 0:
        return ("runtime_error", "tool_runtime_nonzero_exit", trace)
    return ("success", "tool_success", trace)


def _normalize_exit_code(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 1
    return 1


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return "" if value is None else str(value)


def _extract_case_id(tool_call: Any) -> str | None:
    if not isinstance(tool_call, dict):
        return None
    case_id = tool_call.get("case_id")
    return case_id if isinstance(case_id, str) and case_id else None

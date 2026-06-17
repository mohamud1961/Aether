from __future__ import annotations

import json
from typing import Any


def get_tools() -> list[dict[str, Any]]:
    """Return the minimal tool schema for raw shell execution."""
    return [{
        "name": "raw_bash",
        "description": "Execute a bash command in the sandbox working directory.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    }]


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    """Execute a raw_bash tool call and normalize the result payload."""
    call_class = classify_tool_call_shape(tool_call)
    normalized_payload = _normalized_payload(tool_call)
    raw_case_id = tool_call.get("case_id") if isinstance(tool_call, dict) else None
    case_id = raw_case_id if isinstance(raw_case_id, str) and raw_case_id else None
    if call_class != "valid_call":
        raw_name = tool_call.get("name") if isinstance(tool_call, dict) else None
        tool_name = raw_name if isinstance(raw_name, str) and raw_name else "unknown"
        reason_code = (
            "tool_call_contract_unsupported_tool"
            if call_class == "unsupported_tool"
            else "tool_call_contract_malformed"
        )
        return {
            "tool_name": tool_name,
            "command": normalized_payload.get("command", ""),
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
            "normalized_tool_call_payload": normalized_payload,
            "case_id": case_id,
        }

    command = _extract_command(tool_call)
    result = _normalize_exec_result(sandbox.exec(command))
    result_class, reason_code = _classify_result(result)
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
        "normalized_tool_call_payload": normalized_payload,
        "case_id": case_id,
    }


def classify_tool_call_shape(tool_call: Any) -> str:
    if not isinstance(tool_call, dict):
        return "malformed_call"
    name = tool_call.get("name")
    if name != "raw_bash":
        return "unsupported_tool" if isinstance(name, str) else "malformed_call"
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        command = arguments.get("command")
        return "valid_call" if isinstance(command, str) and command else "malformed_call"
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            parsed = {"command": arguments}
        if isinstance(parsed, dict) and isinstance(parsed.get("command"), str) and parsed["command"]:
            return "valid_call"
    return "malformed_call"


def _extract_command(tool_call: dict[str, Any]) -> str:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        command = arguments.get("command")
        if isinstance(command, str) and command:
            return command
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            parsed = {"command": arguments}
        if isinstance(parsed, dict) and isinstance(parsed.get("command"), str) and parsed["command"]:
            return parsed["command"]
    raise ValueError("raw_bash tool call must include a non-empty command")


def _normalize_exec_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"exit_code": 1, "stdout": "", "stderr": str(result), "timed_out": False,
                "error": "sandbox_exec_result_not_mapping"}
    return {
        "exit_code": _normalize_exit_code(result.get("exit_code")),
        "stdout": _coerce_text(result.get("stdout")),
        "stderr": _coerce_text(result.get("stderr")),
        "timed_out": bool(result.get("timed_out", False)),
        "error": _optional_text(result.get("error")),
    }


def _classify_result(result: dict[str, Any]) -> tuple[str, str]:
    error_text = _coerce_text(result.get("error")).lower()
    merged_text = " ".join(
        part for part in (result["stderr"], result["stdout"], error_text) if part
    ).lower()

    if result["exit_code"] == 126 or _looks_like_permission_denied(merged_text):
        return ("permission_denied", "tool_permission_denied")
    if result["timed_out"]:
        return ("runtime_error", "tool_runtime_timeout")
    if error_text:
        return ("runtime_error", "tool_runtime_error_field")
    if result["exit_code"] != 0:
        return ("runtime_error", "tool_runtime_nonzero_exit")
    return ("success", "tool_success")


def _looks_like_permission_denied(text: str) -> bool:
    if not text:
        return False
    markers = (
        "permission denied",
        "denied by policy",
        "operation not permitted",
        "access denied",
        " eacces",
        " eperm",
    )
    return any(marker in text for marker in markers)


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


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _optional_text(value: Any) -> str | None:
    text = _coerce_text(value).strip()
    return text if text else None


def _normalized_payload(tool_call: Any) -> dict[str, Any]:
    if not isinstance(tool_call, dict):
        return {"tool_name": "unknown", "command": ""}
    name = tool_call.get("name")
    arguments = tool_call.get("arguments")
    command = ""
    if isinstance(arguments, dict):
        raw_command = arguments.get("command")
        if isinstance(raw_command, str):
            command = raw_command
    elif isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            parsed = {"command": arguments}
        if isinstance(parsed, dict) and isinstance(parsed.get("command"), str):
            command = parsed["command"]
    return {
        "tool_name": name if isinstance(name, str) else "unknown",
        "command": command,
    }

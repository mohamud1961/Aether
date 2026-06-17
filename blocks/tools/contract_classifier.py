"""Tool-call contract classifier with structured result attribution receipts."""

from __future__ import annotations

import json
from typing import Any

from blocks.tools.raw_bash import get_tools as baseline_get_tools
from blocks.tools.result_normalizer import _classify_result, _normalize_exec_result


def get_tools() -> list[dict[str, Any]]:
    tools = baseline_get_tools()
    tool = dict(tools[0])
    tool["description"] = (
        "Execute a bash command with strict tool-call contract classification and structured attribution receipts."
    )
    return [tool]


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    call_class = classify_tool_call_shape(tool_call)
    payload = _normalized_payload(tool_call)
    case_id = _extract_case_id(tool_call)
    if call_class != "valid_call":
        reason_code = (
            "tool_call_contract_unsupported_tool"
            if call_class == "unsupported_tool"
            else "tool_call_contract_malformed"
        )
        return _build_result(
            tool_call=tool_call,
            payload=payload,
            case_id=case_id,
            call_class=call_class,
            exit_code=1,
            stdout="",
            stderr=reason_code,
            timed_out=False,
            result_class="contract_error",
            reason_code=reason_code,
            attribution_trace={
                "permission_signal_detected": False,
                "runtime_signal_detected": False,
            },
        )

    result = _normalize_exec_result(sandbox.exec(payload["command"]))
    result_class, reason_code, attribution_trace = _classify_result(result)
    return _build_result(
        tool_call=tool_call,
        payload=payload,
        case_id=case_id,
        call_class=call_class,
        exit_code=result["exit_code"],
        stdout=result["stdout"],
        stderr=result["stderr"],
        timed_out=result["timed_out"],
        result_class=result_class,
        reason_code=reason_code,
        attribution_trace=attribution_trace,
    )


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
            return "malformed_call"
        if isinstance(parsed, dict) and isinstance(parsed.get("command"), str) and parsed["command"]:
            return "valid_call"
    return "malformed_call"


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
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("command"), str):
            command = parsed["command"]
    return {
        "tool_name": name if isinstance(name, str) else "unknown",
        "command": command,
    }


def _build_result(
    *,
    tool_call: dict[str, Any],
    payload: dict[str, Any],
    case_id: str | None,
    call_class: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    timed_out: bool,
    result_class: str,
    reason_code: str,
    attribution_trace: dict[str, bool],
) -> dict[str, Any]:
    receipt = {
        "tool_name": payload["tool_name"],
        "command": payload["command"],
        "tool_call_contract_class": call_class,
        "result_class": result_class,
        "reason_code": reason_code,
        "attribution_trace": dict(attribution_trace),
    }
    return {
        "tool_name": payload["tool_name"],
        "command": payload["command"],
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "result_class": result_class,
        "reason_code": reason_code,
        "permission_denied": result_class == "permission_denied",
        "runtime_error": result_class == "runtime_error",
        "tool_call_contract_class": call_class,
        "raw_tool_call_payload": tool_call,
        "normalized_tool_call_payload": payload,
        "case_id": case_id,
        "attribution_trace": dict(attribution_trace),
        "tool_result_receipt": receipt,
    }


def _extract_case_id(tool_call: Any) -> str | None:
    if not isinstance(tool_call, dict):
        return None
    case_id = tool_call.get("case_id")
    return case_id if isinstance(case_id, str) and case_id else None

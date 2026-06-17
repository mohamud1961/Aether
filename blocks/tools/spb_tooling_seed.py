"""Bounded Phase 3 tooling seed: strict calls plus result attribution receipts."""

from __future__ import annotations

from typing import Any

from blocks.tools.contract_classifier import classify_tool_call_shape
from blocks.tools.result_normalizer import _classify_result, _normalize_exec_result, _normalized_payload
from blocks.tools.raw_bash import get_tools as baseline_get_tools


def get_tools() -> list[dict[str, Any]]:
    tools = baseline_get_tools()
    tool = dict(tools[0])
    tool["description"] = (
        "Execute bash with strict tool-call classification and structured result attribution receipts."
    )
    return [tool]


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    call_class = classify_tool_call_shape(tool_call)
    payload = _normalized_payload(tool_call)
    case_id = _extract_case_id(tool_call)
    call_id = _extract_call_id(tool_call)
    if call_class != "valid_call":
        reason_code = (
            "tool_call_contract_unsupported_tool"
            if call_class == "unsupported_tool"
            else "tool_call_contract_malformed"
        )
        return _receipt_result(
            tool_call=tool_call,
            payload=payload,
            case_id=case_id,
            call_id=call_id,
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
    return _receipt_result(
        tool_call=tool_call,
        payload=payload,
        case_id=case_id,
        call_id=call_id,
        call_class=call_class,
        exit_code=result["exit_code"],
        stdout=result["stdout"],
        stderr=result["stderr"],
        timed_out=result["timed_out"],
        result_class=result_class,
        reason_code=reason_code,
        attribution_trace=attribution_trace,
    )


def _receipt_result(
    *,
    tool_call: dict[str, Any],
    payload: dict[str, Any],
    case_id: str | None,
    call_id: str | None,
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
        "call_id": call_id,
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
        "call_id": call_id,
    }


def _extract_call_id(tool_call: Any) -> str | None:
    if not isinstance(tool_call, dict):
        return None
    call_id = tool_call.get("call_id")
    return call_id if isinstance(call_id, str) and call_id else None


def _extract_case_id(tool_call: Any) -> str | None:
    if not isinstance(tool_call, dict):
        return None
    case_id = tool_call.get("case_id")
    return case_id if isinstance(case_id, str) and case_id else None

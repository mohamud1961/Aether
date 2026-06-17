"""Failure signature extraction and bounded recovery policy for the active kernel."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from runner.action_bus import extract_command
from runner.model_client import ModelClientError


def handle_error(error: Exception, history: list[dict[str, Any]], state: Any | None = None) -> dict[str, Any]:
    """Classify an error and return a truthful recovery action."""
    failure_info = classify_exception(error, history=history, state=state)
    return _apply_recovery_policy(failure_info=failure_info, state=state, history_length=len(history))


def classify_exception(
    error: Exception,
    *,
    history: list[dict[str, Any]] | None = None,
    state: Any | None = None,
) -> dict[str, Any]:
    details = getattr(error, "details", None)
    error_message = str(error)
    error_kind = ""
    if isinstance(details, dict):
        error_kind = str(details.get("error_kind") or "")
        if not error_message:
            error_message = str(details.get("message") or "")
    failure_class = _classify_text(error_message=error_message, details=details)
    if isinstance(error, ModelClientError):
        failure_class = "model_client_error"
    reason_code = _reason_code_for_exception(
        error,
        failure_class=failure_class,
        details=details if isinstance(details, dict) else None,
    )
    signature = _signature_for_exception(error, failure_class=failure_class, reason_code=reason_code)
    failure_info = {
        "failure_class": failure_class,
        "reason_code": reason_code,
        "failure_signature": signature,
        "error_type": type(error).__name__,
        "error_kind": error_kind,
        "error_message": error_message,
        "error_details": dict(details or {}) if isinstance(details, dict) else {},
        "history_length": len(history or []),
        "repair_hint": _repair_hint_for_failure_class(failure_class),
        "required_next_obligation": _required_obligation_for_failure_class(failure_class),
        "stale_facts": list(getattr(state, "stale_facts", [])) if state is not None else [],
    }
    return failure_info


def classify_tool_result(
    *,
    tool_call: dict[str, Any] | None,
    tool_result: dict[str, Any],
    state: Any | None = None,
) -> dict[str, Any]:
    tool_name = _tool_name(tool_call, tool_result)
    command = _tool_command(tool_call, tool_result)
    command_info = _command_summary(command)
    exit_code = _exit_code(tool_result.get("exit_code"))
    timed_out = bool(tool_result.get("timed_out", False))
    stderr = str(tool_result.get("stderr") or "")
    reason_code = str(tool_result.get("reason_code") or "")
    failure_class = _classify_tool_failure(
        tool_name=tool_name,
        command=command,
        exit_code=exit_code,
        timed_out=timed_out,
        stderr=stderr,
        reason_code=reason_code,
        tool_result=tool_result,
    )
    signature = _signature_for_tool_result(
        tool_name=tool_name,
        command_signature=str(command_info.get("command_signature") or ""),
        exit_code=exit_code,
        timed_out=timed_out,
        reason_code=reason_code,
        stderr=stderr,
    )
    failure_info = {
        "failure_class": failure_class,
        "reason_code": _reason_code_for_failure_class(failure_class, tool_result=tool_result),
        "failure_signature": signature,
        "tool_name": tool_name,
        "command_digest": command_info["command_digest"],
        "command_excerpt": command_info["command_excerpt"],
        "command_length": command_info["command_length"],
        "command_signature": command_info["command_signature"],
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stderr": stderr,
        "stdout": str(tool_result.get("stdout") or ""),
        "repair_hint": _repair_hint_for_failure_class(failure_class),
        "required_next_obligation": _required_obligation_for_failure_class(failure_class),
        "stale_facts": list(getattr(state, "stale_facts", [])) if state is not None else [],
    }
    _update_state(state, failure_info)
    return failure_info


def build_recovery_card(
    *,
    failure_info: dict[str, Any],
    repeated_count: int,
    state: Any | None = None,
) -> dict[str, Any]:
    return {
        "failure_class": failure_info.get("failure_class"),
        "reason_code": failure_info.get("reason_code"),
        "failure_signature": failure_info.get("failure_signature"),
        "command_digest": failure_info.get("command_digest"),
        "command_excerpt": failure_info.get("command_excerpt"),
        "command_length": failure_info.get("command_length"),
        "command_signature": failure_info.get("command_signature"),
        "repeated_count": repeated_count,
        "repair_hint": failure_info.get("repair_hint"),
        "required_next_obligation": failure_info.get("required_next_obligation"),
        "stale_facts": list(failure_info.get("stale_facts", [])),
        "history_budget_remaining": _history_budget_remaining(state),
    }


def _apply_recovery_policy(
    *,
    failure_info: dict[str, Any],
    state: Any | None,
    history_length: int,
) -> dict[str, Any]:
    repeated_count = _update_state(state, failure_info)
    recovery_card = build_recovery_card(failure_info=failure_info, repeated_count=repeated_count, state=state)
    action = "replan"
    reason = "recovery_replan_required"
    if _model_client_error_should_stop(failure_info):
        action = "stop"
        reason = "invalid_due_to_environment_model_client"
    elif repeated_count >= 3:
        action = "stop"
        reason = "same_signature_recovery_exhausted"
    elif failure_info["failure_class"] in {"invalid_environment", "native_tool_runtime_unavailable"}:
        action = "stop"
        reason = failure_info["failure_class"]
    recovery_action = {
        "action": action,
        "reason": reason,
        "reason_code": failure_info.get("reason_code"),
        "failure_class": failure_info.get("failure_class"),
        "failure_signature": failure_info.get("failure_signature"),
        "repeated_count": repeated_count,
        "history_length": history_length,
        "repair_hint": failure_info.get("repair_hint"),
        "required_next_obligation": failure_info.get("required_next_obligation"),
        "recovery_card": recovery_card,
        "error_message": failure_info.get("error_message"),
        "error_details": dict(failure_info.get("error_details", {})),
    }
    if state is not None:
        try:
            setattr(state, "recovery_card", dict(recovery_card))
        except Exception:
            pass
    return recovery_action


def _exit_code(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return 1


def _update_state(state: Any | None, failure_info: dict[str, Any]) -> int:
    if state is None:
        return 1
    signature = str(failure_info.get("failure_signature") or "").strip()
    if not signature:
        return 1
    if hasattr(state, "record_failure"):
        try:
            repeated_count = int(state.record_failure(signature, failure_info))
        except Exception:
            repeated_count = 1
    else:
        counts = getattr(state, "failure_signature_counts", None)
        if not isinstance(counts, dict):
            counts = {}
            try:
                setattr(state, "failure_signature_counts", counts)
            except Exception:
                counts = {}
        repeated_count = int(counts.get(signature, 0)) + 1
        counts[signature] = repeated_count
        try:
            failure_signatures = getattr(state, "failure_signatures", None)
            if isinstance(failure_signatures, list):
                failure_signatures.append(signature)
            setattr(state, "last_failure_signature", signature)
            setattr(state, "last_failure", dict(failure_info))
        except Exception:
            pass
    if hasattr(state, "refresh_open_obligations"):
        try:
            state.refresh_open_obligations()
        except Exception:
            pass
    if hasattr(state, "refresh_evidence_capsule"):
        try:
            state.refresh_evidence_capsule()
        except Exception:
            pass
    return repeated_count


def _classify_text(*, error_message: str, details: Any) -> str:
    merged = f"{error_message}\n{details if isinstance(details, str) else ''}".lower()
    if isinstance(details, dict):
        error_kind = str(details.get("error_kind") or "").lower()
        response_body = str(details.get("response_body") or "").lower()
        merged = "\n".join([merged, error_kind, response_body])
        if error_kind in {"native_tool_runtime_unavailable", "native_tool_runtime_invalid_result"}:
            return "native_tool_runtime_unavailable"
        if error_kind in {"schema_error", "parse_error"}:
            return "native_tool_schema_violation"
    if "verifier" in merged:
        return "verifier_failed"
    if "connection refused" in merged or "econnrefused" in merged:
        return "service_not_ready"
    if "permission denied" in merged or "eperm" in merged or "eacces" in merged:
        return "permission_denied"
    if "no such file" in merged or "file not found" in merged or "file exists" in merged:
        return "file_not_found"
    if "command not found" in merged or "not found" in merged and "command" in merged:
        return "command_not_found"
    if "timed out" in merged or "timeout" in merged:
        return "timeout"
    if "native tool" in merged and "schema" in merged:
        return "native_tool_schema_violation"
    if "modelclienterror" in merged or "model client error" in merged:
        return "model_client_error"
    if "invalid environment" in merged or "substrate" in merged:
        return "invalid_environment"
    if merged.strip():
        return "command_failed"
    return "unclear"


def _classify_tool_failure(
    *,
    tool_name: str,
    command: str,
    exit_code: int,
    timed_out: bool,
    stderr: str,
    reason_code: str,
    tool_result: dict[str, Any],
) -> str:
    lower = " ".join(
        value.lower()
        for value in (
            tool_name,
            command,
            stderr,
            reason_code,
            str(tool_result.get("stdout") or ""),
        )
        if value
    )
    if tool_result.get("result_class") == "contract_error":
        if "native" in lower:
            return "native_tool_schema_violation"
        return "command_failed"
    if tool_result.get("native_tool_runtime_active") is False and tool_name != "raw_bash":
        return "native_tool_runtime_unavailable"
    if "verifier" in lower:
        return "verifier_failed"
    if timed_out:
        return "timeout"
    if exit_code == 127 or "command not found" in lower:
        return "command_not_found"
    if exit_code == 126 or "permission denied" in lower or "operation not permitted" in lower:
        return "permission_denied"
    if "connection refused" in lower or "econnrefused" in lower:
        return "service_not_ready"
    if "no such file" in lower or "file not found" in lower:
        return "file_not_found"
    if "schema" in lower and "tool" in lower:
        return "native_tool_schema_violation"
    if exit_code != 0:
        return "command_failed"
    return "unclear"


def _signature_for_exception(error: Exception, *, failure_class: str, reason_code: str) -> str:
    message = str(error).strip()
    return f"{type(error).__name__}|{failure_class}|{reason_code}|{message}"


def _signature_for_tool_result(
    *,
    tool_name: str,
    command_signature: str,
    exit_code: int,
    timed_out: bool,
    reason_code: str,
    stderr: str,
) -> str:
    return "|".join(
        [
            tool_name or "unknown",
            command_signature or "command:unknown",
            reason_code or "unknown",
            str(exit_code),
            "timeout" if timed_out else "no_timeout",
            stderr.strip()[:120],
        ]
    )


def _reason_code_for_failure_class(failure_class: str, tool_result: dict[str, Any] | None = None) -> str:
    mapping = {
        "command_not_found": "command_not_found",
        "file_not_found": "file_not_found",
        "permission_denied": "permission_denied",
        "timeout": "timeout",
        "verifier_failed": "verifier_failed",
        "service_not_ready": "service_not_ready",
        "native_tool_schema_violation": "native_tool_schema_violation",
        "native_tool_runtime_unavailable": "native_tool_runtime_unavailable",
        "invalid_environment": "invalid_environment",
        "model_client_error": "model_client_error",
    }
    if failure_class in mapping:
        return mapping[failure_class]
    if tool_result is not None and bool(tool_result.get("timed_out", False)):
        return "timeout"
    return "command_failed"


def _reason_code_for_exception(
    error: Exception,
    *,
    failure_class: str,
    details: dict[str, Any] | None,
) -> str:
    if failure_class != "model_client_error":
        return _reason_code_for_failure_class(failure_class)
    return _model_client_reason_code(details)


def _model_client_reason_code(details: dict[str, Any] | None) -> str:
    if not isinstance(details, dict):
        return "model_client_error"
    status_code = details.get("status_code")
    if isinstance(status_code, int):
        return f"model_client_http_{status_code}"
    error_kind = str(details.get("error_kind") or "").strip().lower()
    if error_kind:
        normalized = re.sub(r"[^a-z0-9]+", "_", error_kind).strip("_")
        if normalized:
            return f"model_client_{normalized}"
    return "model_client_error"


def _repair_hint_for_failure_class(failure_class: str) -> str:
    hints = {
        "command_not_found": "Check the available commands and path; use a command that exists in the substrate.",
        "file_not_found": "Repair the path or create the missing artifact before retrying.",
        "permission_denied": "Adjust permissions or choose a writable location.",
        "timeout": "Narrow the command, add a bounded wait, or probe the service more directly.",
        "verifier_failed": "Repair the verifier-visible artifact or the contract that the verifier expects.",
        "service_not_ready": "Start or probe the service and confirm liveness before continuing.",
        "native_tool_schema_violation": "Fix the tool arguments to satisfy the declared schema.",
        "native_tool_runtime_unavailable": "The substrate does not expose a native tool runtime; report that truthfully.",
        "invalid_environment": "The environment substrate is not valid for this task; stop and report honestly.",
        "model_client_error": "Stop and report the provider/model-route failure truthfully instead of spending task steps on retries.",
    }
    return hints.get(
        failure_class,
        "Inspect the latest evidence, avoid repeating the same command, and replan.",
    )


def _required_obligation_for_failure_class(failure_class: str) -> str:
    obligations = {
        "command_not_found": "select_existing_command",
        "file_not_found": "repair_missing_path",
        "permission_denied": "choose_writable_path",
        "timeout": "narrow_or_probe",
        "verifier_failed": "repair_verifier_artifact",
        "service_not_ready": "start_or_probe_service",
        "native_tool_schema_violation": "fix_tool_schema_arguments",
        "native_tool_runtime_unavailable": "report_runtime_unavailable",
        "invalid_environment": "stop_with_invalid_environment",
        "model_client_error": "stop_with_invalid_environment",
    }
    return obligations.get(failure_class, "inspect_latest_failure")


def _tool_name(tool_call: dict[str, Any] | None, tool_result: dict[str, Any]) -> str:
    if isinstance(tool_call, dict):
        name = tool_call.get("name")
        if isinstance(name, str) and name:
            return name
    name = tool_result.get("tool_name")
    return name if isinstance(name, str) and name else "unknown"


def _tool_command(tool_call: dict[str, Any] | None, tool_result: dict[str, Any]) -> str:
    if isinstance(tool_call, dict):
        arguments = tool_call.get("arguments")
        command = extract_command(arguments)
        if command:
            return command
    command = tool_result.get("command")
    return command if isinstance(command, str) else ""


def _command_summary(command: str) -> dict[str, Any]:
    normalized = " ".join((command or "").replace("\r\n", "\n").split())
    if not normalized:
        return {
            "command_digest": "",
            "command_excerpt": "",
            "command_length": 0,
            "command_signature": "cmd:empty",
        }
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    excerpt_limit = 64
    if len(normalized) <= excerpt_limit:
        excerpt = normalized
    else:
        excerpt_head = normalized[:excerpt_limit].rstrip()
        excerpt = f"{excerpt_head} ... [truncated {len(normalized) - len(excerpt_head)} chars]"
    return {
        "command_digest": digest,
        "command_excerpt": excerpt,
        "command_length": len(normalized),
        "command_signature": f"cmd_sha256:{digest}|len:{len(normalized)}|preview:{excerpt}",
    }


def _history_budget_remaining(state: Any | None) -> int | None:
    if state is None:
        return None
    max_steps = getattr(state, "max_steps", None)
    model_call_count = int(getattr(state, "model_call_count", 0) or 0)
    if isinstance(max_steps, int) and max_steps >= 0:
        return max(0, max_steps - model_call_count)
    return None


def _model_client_error_should_stop(failure_info: dict[str, Any]) -> bool:
    if failure_info.get("failure_class") != "model_client_error":
        return False
    details = failure_info.get("error_details")
    if not isinstance(details, dict):
        return True
    status_code = details.get("status_code")
    if isinstance(status_code, int):
        return status_code not in {429, 500, 502, 503, 504}
    return True

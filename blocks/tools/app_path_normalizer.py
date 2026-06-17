"""Tool surface that normalizes /app references into the local workspace."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from blocks.tools.raw_bash import (
    _classify_result,
    _extract_command,
    _normalize_exec_result,
    _normalized_payload,
    classify_tool_call_shape,
    get_tools as baseline_get_tools,
)

_LOCAL_SCRIPT_RE = re.compile(r"(^|&&|\|\|)\s*\./([A-Za-z0-9_./-]+\.sh)\b")
_ABS_SCRIPT_RE = re.compile(r"(^|&&|\|\|)\s*(/[^ \n;&|]+\.sh)\b")
_BASH_SCRIPT_RE = re.compile(
    r"bash\s+(?P<quote>['\"]?)(?P<path>(?:/[^'\"\s\n;&|]+\.sh|\.?/[^'\"\s\n;&|]+\.sh|[A-Za-z0-9_.-]+\.sh))(?P=quote)"
)
_APP_ALIAS_RE = re.compile(r"(?:(?<=^)|(?<=[\s'\"=;|&()<>]))/app(?![A-Za-z0-9_.-])")


def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    call_class = classify_tool_call_shape(tool_call)
    normalized_payload = _normalized_payload(tool_call)
    if call_class != "valid_call":
        return {
            "tool_name": normalized_payload.get("tool_name", "unknown"),
            "command": normalized_payload.get("command", ""),
            "exit_code": 1,
            "stdout": "",
            "stderr": "tool_call_contract_malformed",
            "timed_out": False,
            "result_class": "contract_error",
            "reason_code": "tool_call_contract_malformed",
            "permission_denied": False,
            "runtime_error": False,
            "tool_call_contract_class": call_class,
            "raw_tool_call_payload": tool_call,
            "normalized_tool_call_payload": normalized_payload,
            "case_id": None,
        }
    command, cleanup_paths = _normalize_command(_extract_command(tool_call), sandbox)
    result = _normalize_exec_result(sandbox.exec(command))
    for cleanup_path in cleanup_paths:
        cleanup_path.unlink(missing_ok=True)
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
        "normalized_tool_call_payload": {
            **normalized_payload,
            "command": command,
            "path_normalized": command != normalized_payload.get("command", ""),
        },
        "case_id": tool_call.get("case_id") if isinstance(tool_call.get("case_id"), str) else None,
    }


def _normalize_command(command: str, sandbox: Any) -> tuple[str, list[Path]]:
    cwd = getattr(sandbox, "cwd", None)
    cwd_text = str(cwd) if cwd else ""
    normalized = command
    cleanup_paths: list[Path] = []
    if cwd_text and getattr(sandbox, "sandbox_type", "none") == "none":
        normalized = _APP_ALIAS_RE.sub(cwd_text.rstrip("/"), normalized)
    normalized = _LOCAL_SCRIPT_RE.sub(lambda m: f"{m.group(1)} bash ./{m.group(2)}", normalized)
    normalized = _ABS_SCRIPT_RE.sub(lambda m: f"{m.group(1)} bash {m.group(2)}", normalized)
    if cwd_text:
        normalized, cleanup_paths = _rewrite_local_bash_scripts(normalized, Path(cwd_text))
    return normalized, cleanup_paths


def _rewrite_local_bash_scripts(command: str, cwd: Path) -> tuple[str, list[Path]]:
    cwd_resolved = cwd.resolve()
    cleanup_paths: list[Path] = []

    def _replace(match: re.Match[str]) -> str:
        raw_path = match.group("path")
        actual_path = _resolve_script_path(raw_path, cwd_resolved)
        if actual_path is None:
            return match.group(0)
        script_text = actual_path.read_text(encoding="utf-8")
        normalized_text = _APP_ALIAS_RE.sub(cwd_resolved.as_posix().rstrip("/"), script_text)
        if normalized_text == script_text:
            return match.group(0)
        temp_path = _next_temp_script_path(cwd_resolved, actual_path.name)
        temp_path.write_text(normalized_text, encoding="utf-8")
        cleanup_paths.append(temp_path)
        return match.group(0).replace(raw_path, temp_path.as_posix(), 1)

    updated = _BASH_SCRIPT_RE.sub(_replace, command)
    return updated, cleanup_paths


def _resolve_script_path(raw_path: str, cwd: Path) -> Path | None:
    if raw_path.startswith("/"):
        path = Path(raw_path)
    else:
        path = cwd / raw_path.removeprefix("./")
    if not path.exists() or not path.is_file():
        return None
    resolved = path.resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError:
        return None
    return resolved


def _next_temp_script_path(cwd: Path, script_name: str) -> Path:
    index = 0
    while True:
        candidate = cwd / f".phase65_{index}_{script_name}"
        if not candidate.exists():
            return candidate
        index += 1

"""Normalize /app and open-workflow paths, then rewrite artifact evidence paths."""

from __future__ import annotations

import json
import re
from typing import Any

from .app_evidence_projection_normalizer import execute_tool_call as execute_evidence_tool_call
from .app_evidence_projection_normalizer import get_tools as baseline_get_tools

_LETTA_ALIAS_RE = re.compile(r"(?:(?<=^)|(?<=[\s'\"=;|&()<>]))/letta/filesystem(?![A-Za-z0-9_.-])")


def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    rewritten = _rewrite_open_workflow_alias(tool_call, sandbox)
    return execute_evidence_tool_call(rewritten, sandbox)


def _rewrite_open_workflow_alias(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    cwd = getattr(sandbox, "cwd", None)
    if cwd is None or getattr(sandbox, "sandbox_type", "none") != "none":
        return tool_call
    command = _extract_command(tool_call)
    if not command or "/letta/filesystem" not in command:
        return tool_call
    local_root = f"{str(cwd).rstrip('/')}/letta/filesystem"
    rewritten_command = _LETTA_ALIAS_RE.sub(local_root, command)
    if rewritten_command == command:
        return tool_call
    payload = dict(tool_call)
    arguments = payload.get("arguments")
    if isinstance(arguments, dict):
        updated = dict(arguments)
        updated["command"] = rewritten_command
        payload["arguments"] = updated
        return payload
    payload["arguments"] = json.dumps({"command": rewritten_command})
    return payload


def _extract_command(tool_call: dict[str, Any]) -> str:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        command = arguments.get("command")
        return command if isinstance(command, str) else ""
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return arguments
        command = parsed.get("command")
        return command if isinstance(command, str) else ""
    return ""

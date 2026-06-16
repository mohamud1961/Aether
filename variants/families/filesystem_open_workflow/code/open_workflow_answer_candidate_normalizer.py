"""Normalize open-workflow paths and surface answer candidates from compute stdout."""

from __future__ import annotations

import re
from typing import Any

from .app_open_workflow_path_evidence_normalizer import execute_tool_call as execute_open_workflow_tool_call
from .app_open_workflow_path_evidence_normalizer import get_tools as baseline_get_tools

_NAME_ONLY_RE = re.compile(r"^[A-Z][A-Za-z'`-]+(?: [A-Z][A-Za-z'`-]+){1,3}$")
_ID_NAME_RE = re.compile(r"^(?:pers|person|id)[-_]?[A-Za-z0-9]+[: ]+([A-Z][A-Za-z'`-]+(?: [A-Z][A-Za-z'`-]+){1,3})$")
_LABEL_NAME_RE = re.compile(r"^(?:answer|winner|person|name|full_name)\s*[:=]\s*([A-Z][A-Za-z'`-]+(?: [A-Z][A-Za-z'`-]+){1,3})$")


def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    result = execute_open_workflow_tool_call(tool_call, sandbox)
    if result.get("result_class") != "success":
        return result
    candidate = _extract_answer_candidate(str(result.get("stdout", "")))
    if not candidate:
        return result
    stdout = str(result.get("stdout", ""))
    marker = f"ANSWER_CANDIDATE: {candidate}"
    if marker not in stdout:
        result["stdout"] = f"{stdout.rstrip()}\n{marker}\n"
    normalized_payload = dict(result.get("normalized_tool_call_payload") or {})
    normalized_payload["answer_candidate"] = candidate
    result["normalized_tool_call_payload"] = normalized_payload
    return result


def _extract_answer_candidate(stdout: str) -> str | None:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    for line in reversed(lines):
        for matcher in (_match_label_name, _match_id_name, _match_name_only):
            candidate = matcher(line)
            if candidate:
                return candidate
    return None


def _match_name_only(line: str) -> str | None:
    return line if _NAME_ONLY_RE.fullmatch(line) else None


def _match_id_name(line: str) -> str | None:
    match = _ID_NAME_RE.fullmatch(line)
    return match.group(1) if match else None


def _match_label_name(line: str) -> str | None:
    match = _LABEL_NAME_RE.fullmatch(line)
    return match.group(1) if match else None

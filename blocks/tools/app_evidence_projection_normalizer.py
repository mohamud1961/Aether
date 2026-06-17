"""Normalize written artifact evidence paths back to /app aliases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .app_path_normalizer import execute_tool_call as execute_baseline_tool_call
from .app_path_normalizer import get_tools as baseline_get_tools

_TARGET_ARTIFACTS = ("artifacts/work_pocket.json", "artifacts/final_report.json")


def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    result = execute_baseline_tool_call(tool_call, sandbox)
    if result.get("result_class") != "success":
        return result
    cwd = _sandbox_cwd(sandbox)
    if cwd is None:
        return result
    rewrites: list[str] = []
    for relpath in _TARGET_ARTIFACTS:
        artifact_path = cwd / relpath
        if _rewrite_evidence_paths(artifact_path, cwd):
            rewrites.append(relpath)
    normalized_payload = dict(result.get("normalized_tool_call_payload") or {})
    normalized_payload["artifact_evidence_paths_rewritten"] = rewrites
    result["normalized_tool_call_payload"] = normalized_payload
    return result


def _sandbox_cwd(sandbox: Any) -> Path | None:
    raw_cwd = getattr(sandbox, "cwd", None)
    if raw_cwd is None:
        return None
    return Path(str(raw_cwd)).resolve()


def _rewrite_evidence_paths(path: Path, cwd: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    evidence_paths = payload.get("evidence_paths")
    if not isinstance(evidence_paths, list):
        return False
    updated = [_normalize_path(str(item), cwd) for item in evidence_paths]
    if updated == evidence_paths:
        return False
    payload["evidence_paths"] = updated
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def _normalize_path(raw_path: str, cwd: Path) -> str:
    prefix = cwd.as_posix().rstrip("/") + "/"
    if raw_path.startswith(prefix):
        suffix = raw_path[len(prefix):].lstrip("/")
        if suffix.startswith("case/"):
            return f"/app/{suffix}"
    if raw_path.startswith("case/"):
        return f"/app/{raw_path}"
    return raw_path

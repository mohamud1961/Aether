"""Project path-normalized closure and verifier evidence into history."""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation

_WORKSPACE_RE = re.compile(r"Workspace cwd:\s*(?P<cwd>\S+)")
_ABS_PATH_RE = re.compile(r"/Users/[A-Za-z0-9_./-]+")
_APP_PATH_RE = re.compile(r"/app/[A-Za-z0-9_./-]+")
_ARTIFACT_RE = re.compile(r"(?:/app/)?[A-Za-z0-9_./-]+\.(?:json|txt|csv|sh)")


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    content = observation.get("content")
    if isinstance(content, str) and content:
        projection = _projection_line(content, _workspace_cwd(history))
        if projection:
            observation["content"] = f"{content}\n\n[followup2_projection] {projection}"
    return append_observation(history, observation)


def _projection_line(content: str, cwd: str) -> str:
    parts = _aliases(content, cwd)
    artifacts = _artifacts(content)
    if artifacts:
        parts.append(f"artifacts={', '.join(artifacts[:3])}")
    lowered = content.lower()
    if "pass" in lowered:
        parts.append("verifier=pass")
    elif "fail" in lowered or "permission denied" in lowered:
        parts.append("verifier=fail")
    if "not found" in lowered or "no such file" in lowered:
        parts.append("blocker=missing_path")
    return " | ".join(parts)


def _workspace_cwd(history: list[dict[str, Any]]) -> str:
    for row in history:
        content = row.get("content")
        if not isinstance(content, str):
            continue
        match = _WORKSPACE_RE.search(content)
        if match:
            return match.group("cwd")
    return ""


def _aliases(content: str, cwd: str) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    prefix = cwd.rstrip("/")
    if prefix:
        for match in _ABS_PATH_RE.finditer(content):
            path = match.group(0).rstrip(".,;:)]}")
            if not path.startswith(prefix):
                continue
            alias = f"{path}<=>/app/{path[len(prefix):].lstrip('/')}"
            if alias not in seen:
                seen.add(alias)
                aliases.append(alias)
    if prefix:
        for match in _APP_PATH_RE.finditer(content):
            path = match.group(0).rstrip(".,;:)]}")
            alias = f"{path}<=>{prefix}/{path.removeprefix('/app/').lstrip('/')}"
            if alias not in seen:
                seen.add(alias)
                aliases.append(alias)
    return aliases[:3]


def _artifacts(content: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _ARTIFACT_RE.finditer(content):
        path = match.group(0).rstrip(".,;:)]}")
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path if path.startswith("/app/") else f"/app/{path.lstrip('/')}")
    return ordered

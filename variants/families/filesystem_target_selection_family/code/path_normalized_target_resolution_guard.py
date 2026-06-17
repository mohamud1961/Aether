"""Annotate history with path-normalized required-target resolution hints."""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation

_WORKSPACE_RE = re.compile(r"Workspace cwd:\s*(?P<cwd>\S+)")
_REQUIRED_RE = re.compile(r"Required artifact paths:\s*(?P<paths>.+)")
_PATH_RE = re.compile(r"(?:/app/)?[A-Za-z0-9_./-]+\.(?:json|txt|csv|sh|md|html)")


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    content = observation.get("content")
    if not isinstance(content, str) or not content:
        return append_observation(history, observation)
    cwd = _workspace_cwd(history)
    required_paths = _required_targets(history)
    mentioned = _mentioned_app_paths(content, cwd)
    sibling_hits = _sibling_hits(required_paths, mentioned)
    if mentioned or sibling_hits:
        required_summary = ", ".join(required_paths[:3]) if required_paths else "none"
        observed_summary = ", ".join(sorted(mentioned)[:3]) if mentioned else "none"
        sibling_summary = ", ".join(sibling_hits[:3]) if sibling_hits else "none"
        projection = (
            f"required={required_summary} | observed={observed_summary} | sibling_substitutions={sibling_summary}"
        )
        observation["content"] = f"{content}\n\n[followup3_target_resolution] {projection}"
    return append_observation(history, observation)


def _workspace_cwd(history: list[dict[str, Any]]) -> str:
    for row in history:
        content = row.get("content")
        if not isinstance(content, str):
            continue
        match = _WORKSPACE_RE.search(content)
        if match:
            return match.group("cwd")
    return ""


def _required_targets(history: list[dict[str, Any]]) -> list[str]:
    for row in history:
        content = row.get("content")
        if not isinstance(content, str):
            continue
        match = _REQUIRED_RE.search(content)
        if not match:
            continue
        return _normalize_required(match.group("paths"))
    return []


def _normalize_required(raw: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in raw.split(","):
        path = item.strip()
        if not path:
            continue
        if not path.startswith("/app/"):
            path = f"/app/{path.lstrip('/')}"
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def _mentioned_app_paths(content: str, cwd: str) -> set[str]:
    prefix = cwd.rstrip("/")
    mentioned: set[str] = set()
    for match in _PATH_RE.finditer(content):
        token = match.group(0).rstrip(".,;:)]}")
        if token.startswith("/app/"):
            mentioned.add(token)
            continue
        if token.startswith("/") and prefix and token.startswith(prefix):
            rel = token[len(prefix):].lstrip("/")
            mentioned.add(f"/app/{rel}")
            continue
        mentioned.add(f"/app/{token.lstrip('/')}")
    return mentioned


def _sibling_hits(required_paths: list[str], mentioned: set[str]) -> list[str]:
    hits: list[str] = []
    for required in required_paths:
        basename = required.rsplit("/", 1)[-1]
        for path in sorted(mentioned):
            if path == required:
                continue
            if path.rsplit("/", 1)[-1] == basename:
                hits.append(f"{path}!={required}")
    return hits

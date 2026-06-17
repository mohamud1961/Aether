"""Normalize /app and local workspace paths inside history observations.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation

_WORKSPACE_RE = re.compile(r"Workspace cwd:\s*(?P<cwd>\S+)")
_ABS_PATH_RE = re.compile(r"/Users/[A-Za-z0-9_./-]+")
_APP_PATH_RE = re.compile(r"/app/[A-Za-z0-9_./-]+")


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    content = observation.get("content")
    if isinstance(content, str) and content:
        cwd = _workspace_cwd(history)
        aliases = _path_aliases(content, cwd)
        if aliases:
            observation["content"] = f"{content}\n\n[path_normalization] {' | '.join(aliases)}"
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


def _path_aliases(content: str, cwd: str) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    if cwd:
        prefix = cwd.rstrip("/")
        for match in _ABS_PATH_RE.finditer(content):
            path = match.group(0).rstrip(".,;:)]}")
            if not path.startswith(prefix):
                continue
            rel = path[len(prefix):].lstrip("/")
            alias = f"{path}<=>/app/{rel}"
            if alias not in seen:
                seen.add(alias)
                aliases.append(alias)
    if cwd:
        prefix = cwd.rstrip("/")
        for match in _APP_PATH_RE.finditer(content):
            path = match.group(0).rstrip(".,;:)]}")
            rel = path.removeprefix("/app/").lstrip("/")
            alias = f"{path}<=>{prefix}/{rel}"
            if alias not in seen:
                seen.add(alias)
                aliases.append(alias)
    return aliases

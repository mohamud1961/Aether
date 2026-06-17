"""Project closure evidence into history so final answers can cite it.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation

_ARTIFACT_RE = re.compile(r"(?:/app/)?[A-Za-z0-9_./-]+\.(?:json|txt|csv)")


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    content = observation.get("content")
    if isinstance(content, str) and content:
        projection = _projection_line(content)
        if projection:
            observation["content"] = f"{content}\n\n[closure_evidence_projection] {projection}"
    return append_observation(history, observation)


def _projection_line(content: str) -> str:
    artifacts = _artifact_paths(content)
    if not artifacts and "verify" not in content.lower():
        return ""
    parts: list[str] = []
    if artifacts:
        parts.append(f"artifacts={', '.join(artifacts[:3])}")
    if "pass" in content.lower():
        parts.append("verifier=pass")
    elif "fail" in content.lower():
        parts.append("verifier=fail")
    return " | ".join(parts)


def _artifact_paths(content: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _ARTIFACT_RE.finditer(content):
        path = match.group(0).rstrip(".,;:)]}")
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered

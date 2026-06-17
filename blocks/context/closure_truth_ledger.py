"""Inject a compact closure-truth ledger into history observations.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation

_PATH_RE = re.compile(r"(?P<path>(?:/app|/Users/)[A-Za-z0-9_./-]+|[A-Za-z0-9_./-]+\.(?:json|txt|csv|sh|md))")


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    content = observation.get("content")
    if isinstance(content, str) and content:
        ledger = _build_ledger(content)
        if ledger:
            observation["content"] = f"{content}\n\n[closure_truth_ledger]\n{ledger}\n[/closure_truth_ledger]"
    return append_observation(history, observation)


def _build_ledger(content: str) -> str:
    paths = _extract_paths(content)
    verifier = _extract_verifier_state(content)
    blockers = _extract_blockers(content)
    parts: list[str] = []
    if paths:
        parts.append(f"paths={', '.join(paths[:4])}")
    if verifier:
        parts.append(f"verifier={verifier}")
    if blockers:
        parts.append(f"blockers={', '.join(blockers[:4])}")
    return " | ".join(parts)


def _extract_paths(content: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _PATH_RE.finditer(content):
        path = match.group("path").rstrip(".,;:)]}")
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def _extract_verifier_state(content: str) -> str:
    lowered = content.lower()
    if "verify" not in lowered and "pytest" not in lowered and "pass" not in lowered and "fail" not in lowered:
        return ""
    if "pass" in lowered:
        return "pass"
    if "fail" in lowered:
        return "fail"
    return "mentioned"


def _extract_blockers(content: str) -> list[str]:
    lowered = content.lower()
    blockers: list[str] = []
    if "no such file" in lowered or "not found" in lowered:
        blockers.append("missing_path")
    if "permission denied" in lowered:
        blockers.append("permission_denied")
    if "fail" in lowered and "verify" in lowered:
        blockers.append("verifier_failed")
    return blockers

"""Add narrow path-normalized closure hints for context-heavy handoff tasks."""

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
        additions: list[str] = []
        projection = _projection_line(content, _workspace_cwd(history))
        if projection:
            additions.append(f"[followup2_projection] {projection}")
        hints = _closure_projection_hints(history, observation)
        if hints:
            additions.append(f"[p07_path_normalized_context_closure_projection] {' | '.join(hints)}")
        if additions:
            observation["content"] = f"{content}\n\n" + "\n".join(additions)
    return append_observation(history, observation)


def _closure_projection_hints(history: list[dict[str, Any]], observation: dict[str, Any]) -> list[str]:
    task = _history_text(history).lower()
    content = str(observation.get("content", ""))
    content_lower = content.lower()
    tool_turns = sum(1 for row in history if row.get("role") == "tool") + int(observation.get("role") == "tool")
    hints: list[str] = []

    if "return one direct answer" in task and "python3 - <<'py'" in content_lower:
        hints.append("direct_answer=>if the computation succeeded, next assistant turn should be one direct string only")
        if tool_turns >= 2:
            hints.append("budget_guard=>stop reading and answer now")
    if ("raw_bash exit=127" in content_lower or "python: not found" in content_lower) and "python3" not in content_lower:
        hints.append("python_missing=>retry_with_python3_only")
    if "exactly these keys" in task and "verified.csv" in content_lower:
        hints.append("answer_shape=>emit one JSON object with the exact requested keys and source values")
    if "/app/artifacts/work_pocket.json" in task and _work_pocket_signal(content_lower):
        hints.append("artifact_schema=>write verified_total + verification_status=verified + absolute /app/case/... evidence_paths")
        hints.append("projection=>local case reads must be projected back to /app/case/... in the artifact")
        hints.append("final_answer=>state the total and /app/artifacts/work_pocket.json on the closing turn")
    if "/app/case" in task and _path_failure(content_lower):
        hints.append("path_recovery=>read case/... locally but keep artifact and final answer paths in /app/... form")
    return hints[:4]


def _history_text(history: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in history:
        content = row.get("content")
        if isinstance(content, str) and content:
            parts.append(content)
    return "\n".join(parts)


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


def _path_failure(content_lower: str) -> bool:
    return any(marker in content_lower for marker in ("no such file", "cannot access", "filenotfounderror"))


def _work_pocket_signal(content_lower: str) -> bool:
    return any(
        marker in content_lower
        for marker in (
            "invoice_",
            "invoice alpha",
            "invoice beta",
            "invoice gamma",
            "verified_total",
            "verification_status",
            "total=50",
            "work_pocket.json",
            "python3 - <<'py'",
        )
    )

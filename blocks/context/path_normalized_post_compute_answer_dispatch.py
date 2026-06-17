"""Add narrow post-compute answer-dispatch hints on top of path normalization."""

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
        hints = _dispatch_hints(history, observation)
        if hints:
            additions.append(f"[p07_post_compute_answer_dispatch] {' | '.join(hints)}")
        if additions:
            observation["content"] = f"{content}\n\n" + "\n".join(additions)
    return append_observation(history, observation)


def _dispatch_hints(history: list[dict[str, Any]], observation: dict[str, Any]) -> list[str]:
    task = _history_text(history)
    task_lower = task.lower()
    content = str(observation.get("content", ""))
    content_lower = content.lower()
    hints: list[str] = []
    if _is_direct_answer_task(task_lower):
        hints.append("answer_shape=>closing turn should be the direct answer only")
    if "/app/artifacts/work_pocket.json" in task and _work_pocket_compute_ready(content_lower):
        hints.append("artifact_closeout=>next assistant turn should report the total and /app/artifacts/work_pocket.json")
        hints.append("no_extra_tool=>do not spend another tool step after the artifact write succeeded")
    if _looks_like_block_records(content):
        hints.append("record_format=>plain-text ### records should be parsed as blocks, not csv tables")
    answer = _tool_answer_candidate(content)
    if _is_direct_answer_task(task_lower) and answer:
        hints.append(f"post_compute_dispatch=>next assistant turn should answer exactly: {answer}")
        hints.append("no_extra_tool=>do not spend another tool step after the decisive compute result")
    if ("csv.dictreader" in content_lower or "import csv" in content_lower) and (_looks_like_block_records(task) or _looks_like_block_records(content)):
        hints.append("record_format=>switch from csv parsing to ### block parsing")
    return hints[:4]


def _is_direct_answer_task(task_lower: str) -> bool:
    return "provide a direct, concise answer" in task_lower or "return one direct answer" in task_lower


def _looks_like_block_records(text: str) -> bool:
    lowered = text.lower()
    return "### " in text and "owner:" in lowered and any(token in lowered for token in ("name:", "state:", "license_plate:", "dob:"))


def _tool_answer_candidate(content: str) -> str | None:
    if "exit=0" not in content or "stdout:" not in content:
        return None
    stdout = content.split("stdout:\n", 1)[1]
    stdout = stdout.split("\nstderr:\n", 1)[0]
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    candidate = lines[-1]
    if len(candidate) > 80 or any(mark in candidate for mark in ("owners", "states", "maxv", "winner", "cands", "{", "}", "[", "]", ":")):
        return None
    if candidate.count(" ") > 4:
        return None
    return candidate


def _work_pocket_compute_ready(content_lower: str) -> bool:
    return "exit=0" in content_lower and ("work_pocket.json" in content_lower or "verified_total" in content_lower or "/app/case/" in content_lower or "stdout:\n50" in content_lower)


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

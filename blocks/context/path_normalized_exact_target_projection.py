"""Combine /app alias projection with exact-target sibling-path guard hints."""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation
from .structured_observation_register import apply_structured_observation_register

_WORKSPACE_RE = re.compile(r"Workspace cwd:\s*(?P<cwd>\S+)")
_REQUIRED_RE = re.compile(r"Required artifact paths:\s*(?P<paths>.+)")
_ABS_PATH_RE = re.compile(r"/Users/[A-Za-z0-9_./-]+")
_APP_PATH_RE = re.compile(r"/app/[A-Za-z0-9_./-]+")
_PATH_RE = re.compile(r"(?:/app/)?[A-Za-z0-9_./-]+\.(?:json|txt|csv|sh|md|html)")
_NO_CALL_POLICY_RE = re.compile(
    r"(do_not_call_external_tools_until_identity_verified|customer_verified.*false|identity_not_verified|no_call policy|no-call policy)",
    re.IGNORECASE,
)
_AUTH_RECORDS_RE = re.compile(r"(current authoritative records|authoritative records|stale distractors|reports/final\.json)", re.IGNORECASE)


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = apply_structured_observation_register(history, new_observation)
    content = observation.get("content")
    if not isinstance(content, str) or not content:
        return append_observation(history, observation)
    cwd = _workspace_cwd(history)
    required_paths = _required_targets(history)
    mentioned = _mentioned_app_paths(content, cwd)
    sibling_hits = _sibling_hits(required_paths, mentioned)
    aliases = _path_aliases(content, cwd)
    hints = _projection_hints(history, content)
    if mentioned or sibling_hits or aliases or hints:
        required_summary = ", ".join(required_paths[:3]) if required_paths else "none"
        observed_summary = ", ".join(sorted(mentioned)[:3]) if mentioned else "none"
        sibling_summary = ", ".join(sibling_hits[:3]) if sibling_hits else "none"
        alias_summary = " | ".join(aliases[:3]) if aliases else "none"
        projection = (
            f"required={required_summary} | observed={observed_summary} | "
            f"sibling_substitutions={sibling_summary} | aliases={alias_summary}"
        )
        if hints:
            projection = f"{projection} | hints={' ; '.join(hints[:3])}"
        observation["content"] = f"{content}\n\n[followup4_exact_target_projection] {projection}"
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
        seen: set[str] = set()
        ordered: list[str] = []
        for item in match.group("paths").split(","):
            path = item.strip()
            if not path:
                continue
            if not path.startswith("/app/"):
                path = f"/app/{path.lstrip('/')}"
            if path not in seen:
                seen.add(path)
                ordered.append(path)
        return ordered
    return []


def _mentioned_app_paths(content: str, cwd: str) -> set[str]:
    prefix = cwd.rstrip("/")
    mentioned: set[str] = set()
    for match in _PATH_RE.finditer(content):
        token = match.group(0).rstrip(".,;:)]}")
        if token.startswith("/app/"):
            mentioned.add(token)
        elif token.startswith("/") and prefix and token.startswith(prefix):
            rel = token[len(prefix):].lstrip("/")
            mentioned.add(f"/app/{rel}")
        else:
            mentioned.add(f"/app/{token.lstrip('/')}")
    return mentioned


def _sibling_hits(required_paths: list[str], mentioned: set[str]) -> list[str]:
    hits: list[str] = []
    for required in required_paths:
        basename = required.rsplit("/", 1)[-1]
        for path in sorted(mentioned):
            if path != required and path.rsplit("/", 1)[-1] == basename:
                hits.append(f"{path}!={required}")
    return hits


def _path_aliases(content: str, cwd: str) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    prefix = cwd.rstrip("/")
    if prefix:
        for match in _ABS_PATH_RE.finditer(content):
            path = match.group(0).rstrip(".,;:)]}")
            if path.startswith(prefix):
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
    return aliases


def _projection_hints(history: list[dict[str, Any]], content: str) -> list[str]:
    task_text = "\n".join(
        row.get("content")
        for row in history
        if isinstance(row.get("content"), str) and row.get("content")
    )
    text = f"{task_text}\n{content}"
    hints: list[str] = []
    if _NO_CALL_POLICY_RE.search(text):
        hints.append("no_call_exact=>status=no_call_required | reason_code=identity_not_verified | tool_calls=[]")
    if _AUTH_RECORDS_RE.search(text):
        hints.append("authoritative_records=>inspect source records before writing final artifact")
        hints.append("artifact_exactness=>avoid placeholder or zeroed outputs")
    if "reports/final.json" in text and "records/current.tsv" in text:
        hints.append("record_selection=>prefer records/current.tsv over stale or archive data")
    return hints

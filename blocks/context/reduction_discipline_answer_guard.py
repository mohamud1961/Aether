"""Narrow late-stage guard for direct-answer reduction discipline."""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation

_WORKSPACE_RE = re.compile(r"Workspace cwd:\s*(?P<cwd>\S+)")
_ABS_PATH_RE = re.compile(r"/Users/[A-Za-z0-9_./-]+")
_APP_PATH_RE = re.compile(r"/app/[A-Za-z0-9_./-]+")
_BROAD_READ_RE = re.compile(r"\b(cat|rg|grep|awk|sed|find)\b", re.IGNORECASE)


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    content = observation.get("content")
    if isinstance(content, str) and content:
        additions: list[str] = []
        projection = _projection_line(content, _workspace_cwd(history))
        if projection:
            additions.append(f"[followup2_projection] {projection}")
        hints = _reduction_guard_hints(history, content)
        if hints:
            additions.append(f"[p07_reduction_discipline_guard] {' | '.join(hints)}")
        if additions:
            observation["content"] = f"{content}\n\n" + "\n".join(additions)
    return append_observation(history, observation)


def _reduction_guard_hints(history: list[dict[str, Any]], content: str) -> list[str]:
    task = _history_text(history).lower()
    if not _is_direct_answer_task(task):
        return []
    lowered = content.lower()
    if not (_successful_compute(lowered) or _broad_evidence_read(content)):
        return []
    hints = [
        "candidate_set=>identify the selected candidate set or winner before final closeout",
        "reduction_op=>state the exact reduction operation (filter/join/count/sum/min/max) in one line",
        "focused_recount=>recompute the final scalar/value in one focused recount step from the selected set",
        "answer_gate=>answer only after the focused recount confirms the scalar/value",
    ]
    if _weak_scalar_signal(content):
        hints.append("weak_scalar_guard=>empty or zero scalar without a grounded reduced set should trigger one focused recount, not immediate closure")
    return hints[:5]


def _is_direct_answer_task(task_lower: str) -> bool:
    return any(
        token in task_lower
        for token in (
            "return one direct answer",
            "direct, concise answer",
            "answer only",
            "final answer only",
        )
    )


def _successful_compute(content_lower: str) -> bool:
    return "exit=0" in content_lower and "stdout:" in content_lower


def _broad_evidence_read(content: str) -> bool:
    if not _BROAD_READ_RE.search(content):
        return False
    txt_hits = content.lower().count(".txt")
    return txt_hits >= 2 or ("filesystem" in content.lower() and txt_hits >= 1)


def _weak_scalar_signal(content: str) -> bool:
    lowered = content.lower()
    if "stdout:" not in lowered:
        return False
    stdout = content.split("stdout:\n", 1)[1] if "stdout:\n" in content else content
    stdout = stdout.split("\nstderr:\n", 1)[0]
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return True
    last = lines[-1]
    if last in {"0", "0.0", ""}:
        grounded_tokens = ("winner", "candidate", "selected", "reduced set", "grounded")
        return not any(token in lowered for token in grounded_tokens)
    return False


def _history_text(history: list[dict[str, Any]]) -> str:
    return "\n".join(content for row in history if isinstance((content := row.get("content")), str) and content)


def _projection_line(content: str, cwd: str) -> str:
    aliases = _aliases(content, cwd)
    lowered = content.lower()
    if "pass" in lowered:
        aliases.append("verifier=pass")
    elif "fail" in lowered or "permission denied" in lowered:
        aliases.append("verifier=fail")
    return " | ".join(aliases)


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
    if not prefix:
        return aliases
    for pattern, transform in (
        (_ABS_PATH_RE, lambda path: f"{path}<=>/app/{path[len(prefix):].lstrip('/')}"),
        (_APP_PATH_RE, lambda path: f"{path}<=>{prefix}/{path.removeprefix('/app/').lstrip('/')}"),
    ):
        for match in pattern.finditer(content):
            path = match.group(0).rstrip(".,;:)]}")
            if pattern is _ABS_PATH_RE and not path.startswith(prefix):
                continue
            alias = transform(path)
            if alias not in seen:
                seen.add(alias)
                aliases.append(alias)
    return aliases[:3]

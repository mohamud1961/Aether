"""Carry forward grounded answer-ready state from machine-readable tool markers."""

from __future__ import annotations

import json
import re
from typing import Any

from .full_history import append_observation

_STATE_KEY = "grounded_answer_ready_state"
_STATE_TAG = "[grounded_answer_ready_state]"
_STATE_VERSION = "p07_grounded_answer_ready_state.v1"
_STATE_RE = re.compile(r"\[grounded_answer_ready_state\]\s*(\{.*\})")
_STDOUT_RE = re.compile(r"stdout:\n(?P<stdout>.*?)(?:\nstderr:\n|\Z)", re.DOTALL)
_ANSWER_RE = re.compile(r"ANSWER_CANDIDATE:\s*(?P<answer>[^\n]+)")
_TOTAL_RE = re.compile(r"(?:verified_total|total)\s*[:=]\s*(?P<value>-?\d+(?:\.\d+)?)", re.IGNORECASE)
_STATUS_RE = re.compile(r"(?:verification_status|verifier)\s*[:=]\s*(?P<status>[A-Za-z_ -]+)", re.IGNORECASE)
_PATH_RE = re.compile(r"(?:/app|/Users)/[A-Za-z0-9_./-]+")
_ARTIFACT_RE = re.compile(r"/app/[A-Za-z0-9_./-]+\.(?:json|txt|csv|md|sh)")


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    state = _next_state(history, observation)
    if state:
        observation[_STATE_KEY] = state
        marker = f"{_STATE_TAG} {json.dumps(state, sort_keys=True, ensure_ascii=True)}"
        content = observation.get("content")
        observation["content"] = f"{content}\n\n{marker}" if isinstance(content, str) and content else marker
    return append_observation(history, observation)


def _next_state(history: list[dict[str, Any]], observation: dict[str, Any]) -> dict[str, Any]:
    prior = _latest_state(history)
    task_text = _history_text(history).lower()
    parsed = _parse_markers(observation.get("content"))
    state = {
        "version": _STATE_VERSION,
        "direct_answer_task": _is_direct_answer_task(task_text),
        "answer_ready": False,
        "answer": "",
        "reason_code": "not_ready",
        "evidence_paths": [],
        "artifact_paths": [],
        "verification_status": "",
        "facts": {},
    }
    if prior:
        state.update(
            {
                "direct_answer_task": bool(prior.get("direct_answer_task")) or state["direct_answer_task"],
                "answer_ready": bool(prior.get("answer_ready")),
                "answer": str(prior.get("answer") or ""),
                "reason_code": str(prior.get("reason_code") or "not_ready"),
                "evidence_paths": _clean_paths(prior.get("evidence_paths")),
                "artifact_paths": _clean_paths(prior.get("artifact_paths")),
                "verification_status": str(prior.get("verification_status") or ""),
                "facts": dict(prior.get("facts") or {}),
            }
        )
    if observation.get("role") != "tool" and not prior:
        return {}
    state["evidence_paths"] = _merge_paths(state["evidence_paths"], parsed["evidence_paths"])
    state["artifact_paths"] = _merge_paths(state["artifact_paths"], parsed["artifact_paths"])
    if parsed["verification_status"]:
        state["verification_status"] = parsed["verification_status"]
        state["facts"]["verification_status"] = parsed["verification_status"]
    if parsed["verified_total"] is not None:
        state["facts"]["verified_total"] = parsed["verified_total"]
    if parsed["answer"]:
        state["facts"]["answer_candidate"] = parsed["answer"]
    if parsed["success"] and parsed["answer"]:
        state["answer"] = parsed["answer"]
        state["reason_code"] = "answer_candidate"
        state["answer_ready"] = state["direct_answer_task"]
    elif _is_artifact_ready(task_text, state):
        state["reason_code"] = "artifact_ready"
        state["answer_ready"] = True
    elif not state["answer_ready"] and parsed["answer"]:
        state["reason_code"] = "answer_candidate_pending"
    if not prior and not _state_has_signal(state):
        return {}
    return state


def _latest_state(history: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(history):
        state = row.get(_STATE_KEY)
        if isinstance(state, dict):
            return dict(state)
        content = row.get("content")
        if not isinstance(content, str):
            continue
        for line in reversed(content.splitlines()):
            match = _STATE_RE.search(line.strip())
            if not match:
                continue
            try:
                parsed = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def _parse_markers(content: Any) -> dict[str, Any]:
    text = content if isinstance(content, str) else ""
    stdout_match = _STDOUT_RE.search(text)
    stdout = stdout_match.group("stdout") if stdout_match else text
    answer_match = _ANSWER_RE.search(stdout)
    total_match = _TOTAL_RE.search(stdout)
    status_match = _STATUS_RE.search(stdout)
    return {
        "success": " exit=0" in f" {text.lower()}",
        "answer": answer_match.group("answer").strip() if answer_match else "",
        "verified_total": float(total_match.group("value")) if total_match else None,
        "verification_status": status_match.group("status").strip().lower().replace(" ", "_") if status_match else "",
        "artifact_paths": [match.group(0).rstrip(".,;:)]}") for match in _ARTIFACT_RE.finditer(text)],
        "evidence_paths": [match.group(0).rstrip(".,;:)]}") for match in _PATH_RE.finditer(text)],
    }


def _is_direct_answer_task(task_lower: str) -> bool:
    return any(
        marker in task_lower
        for marker in ("provide a direct, concise answer", "return one direct answer", "direct answer only")
    )


def _is_artifact_ready(task_lower: str, state: dict[str, Any]) -> bool:
    if "/app/artifacts/work_pocket.json" not in task_lower:
        return False
    verified_total = state.get("facts", {}).get("verified_total")
    verification_status = str(state.get("verification_status") or "")
    return verified_total is not None and bool(state.get("artifact_paths")) and verification_status in {"verified", "pass"}


def _state_has_signal(state: dict[str, Any]) -> bool:
    return bool(
        state.get("direct_answer_task")
        or state.get("answer")
        or state.get("artifact_paths")
        or state.get("evidence_paths")
        or state.get("facts")
    )


def _history_text(history: list[dict[str, Any]]) -> str:
    return "\n".join(content for row in history if isinstance((content := row.get("content")), str) and content)


def _clean_paths(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str) and item] if isinstance(value, list) else []


def _merge_paths(existing: list[str], new_paths: list[str]) -> list[str]:
    merged, seen = [], set()
    for path in [*existing, *new_paths]:
        if path in seen:
            continue
        seen.add(path)
        merged.append(path)
    return merged[:6]

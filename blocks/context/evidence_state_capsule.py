"""Carry a compact evidence-state capsule for freshness-sensitive context work."""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation
from .structured_observation_register import apply_structured_observation_register

_CAPSULE_KEY = "evidence_state_capsule"
_CAPSULE_VERSION = "evidence_state_capsule.v1"
_PATH_RE = re.compile(r"(?:/app|/Users)[A-Za-z0-9_./-]+")
_HASH_RE = re.compile(r"\b[a-f0-9]{64}\b", re.IGNORECASE)

_CAPTURE_KEYS = (
    "call_id",
    "state_ref",
    "refresh_evidence",
    "tool_result",
    "post_state",
    "verified_facts",
    "facts",
    "evidence_paths",
    "artifact_paths",
    "verification_status",
    "reason_code",
    "status",
    "answer",
)


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Append observations with a compact, freshness-aware evidence capsule."""
    observation = apply_structured_observation_register(history, dict(new_observation))
    capsule = _build_capsule(observation)
    if capsule:
        observation[_CAPSULE_KEY] = capsule
        summary = _summarize_capsule(capsule)
        if summary:
            content = observation.get("content")
            marker = f"[evidence_state_capsule] {summary}"
            observation["content"] = f"{content}\n\n{marker}" if isinstance(content, str) and content else marker
    return append_observation(history, observation)


def _build_capsule(observation: dict[str, Any]) -> dict[str, Any]:
    capsule: dict[str, Any] = {"version": _CAPSULE_VERSION}
    for key in _CAPTURE_KEYS:
        value = observation.get(key)
        if isinstance(value, dict):
            capsule[key] = dict(value)
        elif isinstance(value, list):
            capsule[key] = [item for item in value if isinstance(item, (str, int, float, bool)) or item is None]
        elif isinstance(value, str) and value:
            capsule[key] = value
    content = observation.get("content")
    if isinstance(content, str) and content:
        paths = _extract_unique(_PATH_RE, content)
        hashes = _extract_unique(_HASH_RE, content)
        if paths:
            capsule["evidence_paths"] = _merge_lists(capsule.get("evidence_paths"), paths)
        if hashes:
            capsule["content_hashes"] = hashes[:4]
        freshness = _freshness_markers(content)
        if freshness:
            capsule["freshness"] = freshness
    if "verified_facts" not in capsule and isinstance(observation.get("facts"), dict):
        facts = dict(observation["facts"])
        if facts:
            capsule["verified_facts"] = facts
    if "evidence_paths" in capsule or "artifact_paths" in capsule or "verification_status" in capsule or "state_ref" in capsule:
        return capsule
    if any(
        key in capsule
        for key in (
            "call_id",
            "refresh_evidence",
            "tool_result",
            "post_state",
            "reason_code",
            "answer",
            "verified_facts",
            "content_hashes",
            "freshness",
        )
    ):
        return capsule
    return {}


def _summarize_capsule(capsule: dict[str, Any]) -> str:
    parts: list[str] = [f"version={capsule.get('version', '')}"]
    state_ref = capsule.get("state_ref")
    if isinstance(state_ref, str) and state_ref:
        parts.append(f"state_ref={state_ref}")
    verification_status = capsule.get("verification_status")
    if isinstance(verification_status, str) and verification_status:
        parts.append(f"verification_status={verification_status}")
    freshness = capsule.get("freshness")
    if isinstance(freshness, dict):
        markers = [key for key, value in freshness.items() if value]
        if markers:
            parts.append(f"freshness={','.join(markers[:4])}")
    evidence_paths = capsule.get("evidence_paths")
    if isinstance(evidence_paths, list) and evidence_paths:
        parts.append(f"paths={len(evidence_paths)}")
    artifact_paths = capsule.get("artifact_paths")
    if isinstance(artifact_paths, list) and artifact_paths:
        parts.append(f"artifacts={len(artifact_paths)}")
    reason_code = capsule.get("reason_code")
    if isinstance(reason_code, str) and reason_code:
        parts.append(f"reason={reason_code}")
    return " | ".join(parts)


def _freshness_markers(content: str) -> dict[str, bool]:
    lowered = content.lower()
    return {
        "tool_result_seen": any(marker in lowered for marker in ("tool result", "tool_result", "call_id")),
        "state_refreshed": any(marker in lowered for marker in ("refresh", "refreshed", "post_state")),
        "mutation_seen": any(marker in lowered for marker in ("mutat", "write", "update", "changed")),
        "stale_state_rejected": any(marker in lowered for marker in ("stale", "outdated", "old state")),
    }


def _extract_unique(pattern: re.Pattern[str], content: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in pattern.finditer(content):
        value = match.group(0).rstrip(".,;:)]}")
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _merge_lists(existing: Any, new_items: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, str) and item and item not in seen:
                seen.add(item)
                merged.append(item)
    for item in new_items:
        if item not in seen:
            seen.add(item)
            merged.append(item)
    return merged[:6]

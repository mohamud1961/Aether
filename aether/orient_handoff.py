from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping

from .artifact_store import ArtifactStore


_TASK_TYPES = {"coding", "system-admin", "debugging", "data-processing", "math", "other"}


@dataclass(frozen=True)
class OrientHandoff:
    handoff_id: str
    task_type: str
    goal_statement: str
    success_definition: str
    key_constraints: List[str]
    tools_likely_needed: List[str]
    suggested_first_actions: List[str]
    risk_assessment: str
    intent_contract_ref: str


def _normalize_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    normalized: List[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip() if item is not None else ""
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_task_type(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in _TASK_TYPES:
        return candidate
    return "other"


def _digest_payload(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_orient_handoff_from_model(
    *,
    prompt: str,
    model_payload: Mapping[str, Any],
    intent_contract_ref: str,
) -> OrientHandoff:
    normalized_prompt = (prompt or "").strip()
    fallback_goal = (
        normalized_prompt if normalized_prompt else "Clarify the requested task and produce required outputs."
    )

    goal_statement = str(model_payload.get("goal_statement", "")).strip() or fallback_goal
    success_definition = str(model_payload.get("success_definition", "")).strip() or (
        "Task is complete when requested outputs are produced and relevant checks pass."
    )
    constraints = _normalize_string_list(model_payload.get("key_constraints"))
    tools = _normalize_string_list(model_payload.get("tools_likely_needed"))
    first_actions = _normalize_string_list(model_payload.get("suggested_first_actions"))
    if not first_actions:
        first_actions = [
            "Inspect repository structure and entrypoints.",
            "Identify files and commands most likely tied to the requested outcome.",
        ]

    risk_assessment = str(model_payload.get("risk_assessment", "")).strip() or "MED: standard task uncertainty."
    payload_for_id = {
        "task_type": _normalize_task_type(model_payload.get("task_type")),
        "goal_statement": goal_statement,
        "success_definition": success_definition,
        "key_constraints": constraints,
        "tools_likely_needed": tools,
        "suggested_first_actions": first_actions,
        "risk_assessment": risk_assessment,
        "intent_contract_ref": intent_contract_ref,
    }

    return OrientHandoff(
        handoff_id=_digest_payload(payload_for_id),
        task_type=payload_for_id["task_type"],
        goal_statement=goal_statement,
        success_definition=success_definition,
        key_constraints=constraints,
        tools_likely_needed=tools,
        suggested_first_actions=first_actions,
        risk_assessment=risk_assessment,
        intent_contract_ref=intent_contract_ref,
    )


def derive_task_items_from_model(raw_items: Any) -> List[str]:
    extracted: List[str] = []

    if isinstance(raw_items, list):
        for item in raw_items:
            title = ""
            if isinstance(item, Mapping):
                title = str(item.get("title", "")).strip()
            else:
                title = str(item).strip()
            if title:
                extracted.append(title)

    normalized: List[str] = []
    seen: set[str] = set()
    for item in extracted:
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def derive_task_items_from_prompt(prompt: str) -> List[str]:
    normalized = (prompt or "").strip()
    if not normalized:
        return ["Clarify requirements", "Implement requested changes"]

    clauses = [part.strip() for part in re.split(r"[.;\n]+", normalized) if part.strip()]
    if len(clauses) == 1:
        words = clauses[0].split()
        if len(words) > 10 and " and " in clauses[0].lower():
            clauses = [part.strip() for part in re.split(r"\band\b", clauses[0], flags=re.IGNORECASE) if part.strip()]

    task_items: List[str] = []
    for clause in clauses:
        cleaned = clause[:120].strip()
        if not cleaned:
            continue
        task_items.append(cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper())

    if not task_items:
        task_items = ["Clarify requirements", "Implement requested changes"]
    elif len(task_items) == 1:
        task_items.append("Validate and verify requested outcomes")

    return task_items[:7]


def persist_orient_handoff(
    *,
    handoff: OrientHandoff,
    artifact_store: ArtifactStore,
) -> Dict[str, str]:
    artifact_ref, content_hash = artifact_store.write_json_canonical(asdict(handoff))
    return {
        "artifact_id": artifact_ref.artifact_id,
        "content_hash": content_hash,
    }

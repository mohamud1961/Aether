from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping, Optional

from .artifact_store import ArtifactStore
from .enum_registry import EnumRegistry, load_enum_registry
from .event_log import EventLog


@dataclass(frozen=True)
class IntentContract:
    intent_contract_id: str
    goal_statement: str
    deliverables: List[str]
    constraints: List[str]
    environment_assumptions: Dict[str, Any]
    acceptance_criteria: List[str]
    risk_profile: str
    clarifications_resolved: List[Dict[str, str]]
    clarifications_remaining: List[str]
    default_assumptions_if_unanswered: List[str]


def intent_contract_id_from_prompt(prompt: str) -> str:
    normalized = (prompt or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _default_environment_assumptions() -> Dict[str, Any]:
    return {
        "repo_present": True,
        "network_allowed": False,
        "credentials_expected": False,
        "sandbox_type": "workspace-write",
    }


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


def _normalize_clarifications_resolved(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: List[Dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not question and not answer:
            continue
        normalized.append({"question": question, "answer": answer})
    return normalized


def _normalize_risk_profile(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"LOW", "MED", "HIGH"}:
        return normalized
    return "MED"


def build_intent_contract_from_prompt(prompt: str) -> IntentContract:
    normalized = (prompt or "").strip()
    digest = intent_contract_id_from_prompt(normalized)
    goal = normalized if normalized else "Clarify the requested task and produce required outputs."
    return IntentContract(
        intent_contract_id=digest,
        goal_statement=goal,
        deliverables=["Implemented code changes in workspace"],
        constraints=[],
        environment_assumptions=_default_environment_assumptions(),
        acceptance_criteria=["Changes compile and tests pass for modified behavior."],
        risk_profile="MED",
        clarifications_resolved=[],
        clarifications_remaining=[],
        default_assumptions_if_unanswered=[],
    )


def build_intent_contract_from_model(
    *,
    prompt: str,
    model_payload: Mapping[str, Any],
) -> IntentContract:
    normalized_prompt = (prompt or "").strip()
    digest = intent_contract_id_from_prompt(normalized_prompt)
    default_contract = build_intent_contract_from_prompt(prompt)

    goal_statement = str(model_payload.get("goal_statement", "")).strip() or default_contract.goal_statement
    deliverables = _normalize_string_list(model_payload.get("deliverables")) or default_contract.deliverables
    constraints = _normalize_string_list(model_payload.get("constraints"))
    acceptance_criteria = (
        _normalize_string_list(model_payload.get("acceptance_criteria"))
        or default_contract.acceptance_criteria
    )

    assumptions_raw = model_payload.get("environment_assumptions")
    assumptions: Dict[str, Any]
    if isinstance(assumptions_raw, Mapping):
        assumptions = dict(assumptions_raw)
    else:
        assumptions = _default_environment_assumptions()

    return IntentContract(
        intent_contract_id=digest,
        goal_statement=goal_statement,
        deliverables=deliverables,
        constraints=constraints,
        environment_assumptions=assumptions,
        acceptance_criteria=acceptance_criteria,
        risk_profile=_normalize_risk_profile(model_payload.get("risk_profile")),
        clarifications_resolved=_normalize_clarifications_resolved(
            model_payload.get("clarifications_resolved")
        ),
        clarifications_remaining=_normalize_string_list(
            model_payload.get("clarifications_remaining")
        ),
        default_assumptions_if_unanswered=_normalize_string_list(
            model_payload.get("default_assumptions_if_unanswered")
        ),
    )


def persist_intent_contract(
    *,
    contract: IntentContract,
    artifact_store: ArtifactStore,
    event_log: EventLog,
    timestamp: str,
    cwd: str,
) -> Dict[str, str]:
    payload = asdict(contract)
    artifact_ref, content_hash = artifact_store.write_json_canonical(payload)
    event_log.append_event(
        {
            "event_type": "INTENT_CONTRACT_DEFINED",
            "timestamp": timestamp,
            "cwd": cwd,
            "intent_contract_id": contract.intent_contract_id,
            "intent_digest": content_hash,
            "intent_contract": payload,
            "artifact_refs": [artifact_ref.artifact_id],
        }
    )
    return {
        "artifact_id": artifact_ref.artifact_id,
        "content_hash": content_hash,
    }


def run_intent_completeness_check(
    *,
    contract: IntentContract,
    artifact_store: ArtifactStore,
    event_log: EventLog,
    timestamp: str,
    cwd: str,
    enum_registry: Optional[EnumRegistry] = None,
) -> Dict[str, Any]:
    active_registry = enum_registry or load_enum_registry()

    blocking_reasons: List[str] = []
    missing_fields: List[str] = []

    goal = (contract.goal_statement or "").strip()
    if len(goal.split()) < 2:
        blocking_reasons.append("goal_statement_not_actionable")
        missing_fields.append("goal_statement")

    if not contract.deliverables:
        blocking_reasons.append("deliverables_missing")
        missing_fields.append("deliverables")

    if not contract.acceptance_criteria:
        blocking_reasons.append("acceptance_criteria_missing")
        missing_fields.append("acceptance_criteria")

    if not active_registry.validate_enum("risk_class", contract.risk_profile):
        blocking_reasons.append("invalid_risk_profile")
        missing_fields.append("risk_profile")

    passed = len(blocking_reasons) == 0
    signal_payload = {
        "goal_statement": contract.goal_statement,
        "deliverables": contract.deliverables,
        "acceptance_criteria": contract.acceptance_criteria,
        "risk_profile": contract.risk_profile,
    }
    signal_hash = hashlib.sha256(
        json.dumps(signal_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    check_payload = {
        "intent_contract_id": contract.intent_contract_id,
        "pass": passed,
        "blocking_reasons": blocking_reasons,
        "missing_fields": sorted(set(missing_fields)),
        "signal_hash": signal_hash,
    }

    artifact_ref, content_hash = artifact_store.write_json_canonical(check_payload)
    event_log.append_event(
        {
            "event_type": "INTENT_COMPLETENESS_CHECK",
            "timestamp": timestamp,
            "cwd": cwd,
            "intent_contract_id": contract.intent_contract_id,
            "intent_digest": hashlib.sha256(
                json.dumps(asdict(contract), sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "pass": passed,
            "blocking_reasons": blocking_reasons,
            "missing_fields": check_payload["missing_fields"],
            "signal_hash": signal_hash,
            "artifact_refs": [artifact_ref.artifact_id],
            "content_hash": content_hash,
        }
    )
    return {
        "pass": passed,
        "blocking_reasons": blocking_reasons,
        "missing_fields": check_payload["missing_fields"],
        "signal_hash": signal_hash,
        "artifact_id": artifact_ref.artifact_id,
        "content_hash": content_hash,
    }

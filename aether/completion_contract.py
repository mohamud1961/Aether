from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

from .artifact_store import ArtifactStore
from .enum_registry import EnumRegistry, load_enum_registry
from .event_log import EventLog
from .policy_config import PolicyConfig


ORIENT_BOOTSTRAP_LOW_RISK_TOOLS = {"read_file", "list_paths", "stat", "run_command", "run"}


@dataclass(frozen=True)
class CompletionContract:
    completion_contract_id: str
    intent_contract_ref: str
    success_criteria: List[Dict[str, Any]]
    required_verifiers: List[str]
    required_artifacts: List[str]
    risk_class: str
    timestamp: str


def build_completion_contract(
    *,
    intent_contract_ref: str,
    required_verifiers: Sequence[str],
    required_artifacts: Sequence[str],
    risk_class: str,
    timestamp: str,
) -> CompletionContract:
    seed = {
        "intent_contract_ref": intent_contract_ref,
        "required_verifiers": sorted(str(item) for item in required_verifiers),
        "required_artifacts": sorted(str(item) for item in required_artifacts),
        "risk_class": risk_class,
        "timestamp": timestamp,
    }
    contract_id = hashlib.sha256(
        json.dumps(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CompletionContract(
        completion_contract_id=contract_id,
        intent_contract_ref=intent_contract_ref,
        success_criteria=[{"criterion_id": "default_success", "description": "Requested task is completed."}],
        required_verifiers=[str(item) for item in required_verifiers],
        required_artifacts=[str(item) for item in required_artifacts],
        risk_class=str(risk_class).upper(),
        timestamp=timestamp,
    )


def validate_completion_contract(
    *,
    contract: CompletionContract,
    verifier_ids: Sequence[str],
    enum_registry: Optional[EnumRegistry] = None,
) -> List[str]:
    registry = enum_registry or load_enum_registry()
    errors: List[str] = []
    known = {str(item) for item in verifier_ids}
    for verifier_id in contract.required_verifiers:
        if verifier_id not in known:
            errors.append(f"missing_verifier:{verifier_id}")
    if not registry.validate_enum("risk_class", contract.risk_class):
        errors.append("invalid_risk_class")
    return errors


def persist_completion_contract(
    *,
    contract: CompletionContract,
    artifact_store: ArtifactStore,
    event_log: EventLog,
    timestamp: str,
    cwd: str,
) -> Dict[str, str]:
    payload = asdict(contract)
    artifact_ref, content_hash = artifact_store.write_json_canonical(payload)
    event_log.append_event(
        {
            "event_type": "CONTRACT_DEFINED",
            "timestamp": timestamp,
            "cwd": cwd,
            "completion_contract_id": contract.completion_contract_id,
            "completion_contract": payload,
            "artifact_refs": [artifact_ref.artifact_id],
            "content_hash": content_hash,
        }
    )
    return {
        "artifact_id": artifact_ref.artifact_id,
        "content_hash": content_hash,
    }


def tool_call_allowed_without_completion_contract(
    *,
    phase: str,
    tool_name: str,
    tool_args: Dict[str, Any],
    risk_class: str = "LOW",
) -> bool:
    if phase != "Orient":
        return False
    if str(risk_class).upper() != "LOW":
        return False
    if tool_name not in ORIENT_BOOTSTRAP_LOW_RISK_TOOLS:
        return False
    if tool_name not in {"run", "run_command"}:
        return True

    command = tool_args.get("command")
    if not isinstance(command, list) or not command:
        return False
    joined = " ".join(str(item) for item in command).lower()
    version_markers = ("--version", "-v", " version", " -vv")
    return any(marker in joined for marker in version_markers)


def bootstrap_completion_contract(
    *,
    intent_contract_ref: str,
    verifier_ids: Sequence[str],
    policy: PolicyConfig,
    timestamp: str,
) -> CompletionContract:
    risk = "MED" if policy.policy_profile == "prod" else "LOW"
    return build_completion_contract(
        intent_contract_ref=intent_contract_ref,
        required_verifiers=verifier_ids,
        required_artifacts=[],
        risk_class=risk,
        timestamp=timestamp,
    )

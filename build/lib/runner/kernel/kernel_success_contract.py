"""Pure success-contract substrate helpers for model-led runs."""

from __future__ import annotations

import copy
import json
from typing import Any

ALLOWED_SUCCESS_CONTRACT_KEYS = {
    "status",
    "contract_id",
    "source_receipt_id",
    "criteria",
    "required_artifacts",
    "required_checks",
    "authority_hierarchy",
    "known_uncertainty",
    "suspected_decoy_classes",
    "done_checklist",
    "revision",
    "visible_evidence_refs",
}
SUCCESS_CONTRACT_LIST_KEYS = {
    "criteria",
    "required_artifacts",
    "required_checks",
    "authority_hierarchy",
    "known_uncertainty",
    "suspected_decoy_classes",
    "done_checklist",
    "visible_evidence_refs",
}
SUCCESS_CONTRACT_STRING_KEYS = {"status", "contract_id", "source_receipt_id"}
ALLOWED_SUCCESS_CONTRACT_STATUSES = {"not_declared", "proposed", "frozen", "revised"}
FORBIDDEN_MARKERS = ("hidden://", "/reviewer_pack", "hidden_truth", "benchmark data should never")

__all__ = (
    "empty_success_contract",
    "extract_success_contract",
    "validate_success_contract",
    "freeze_success_contract",
    "propose_success_contract_revision",
    "render_success_contract",
    "audit_success_contract_consistency",
)


def empty_success_contract() -> dict[str, Any]:
    return {
        "status": "not_declared",
        "contract_id": "",
        "source_receipt_id": "",
        "criteria": [],
        "required_artifacts": [],
        "required_checks": [],
        "authority_hierarchy": [],
        "known_uncertainty": [],
        "suspected_decoy_classes": [],
        "done_checklist": [],
        "revision": 0,
        "visible_evidence_refs": [],
    }


def extract_success_contract(completion: Any) -> dict[str, Any] | None:
    payloads: list[dict[str, Any]] = []
    if isinstance(completion, dict):
        payloads.append(completion)
        text = completion.get("text")
        if isinstance(text, str) and text.strip():
            parsed = _parse_json_like_text(text)
            if isinstance(parsed, dict):
                payloads.append(parsed)
    elif isinstance(completion, str) and completion.strip():
        parsed = _parse_json_like_text(completion)
        if isinstance(parsed, dict):
            payloads.append(parsed)
    for payload in payloads:
        extracted = _extract_success_contract_from_payload(payload)
        if extracted is not None:
            return extracted
    return None


def validate_success_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, dict):
        return {"status": "rejected", "reason_codes": ["invalid_success_contract_shape"]}
    unknown_keys = sorted(key for key in contract if key not in ALLOWED_SUCCESS_CONTRACT_KEYS)
    if unknown_keys:
        return {
            "status": "rejected",
            "reason_codes": ["unknown_success_contract_fields", *unknown_keys],
        }
    normalized: dict[str, Any] = empty_success_contract()
    reason_codes: list[str] = []
    for key in SUCCESS_CONTRACT_STRING_KEYS:
        value = contract.get(key, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            return {
                "status": "rejected",
                "reason_codes": [f"{key}_must_be_string"],
            }
        normalized[key] = value.strip()
    status = normalized["status"] or "proposed"
    if status not in ALLOWED_SUCCESS_CONTRACT_STATUSES:
        return {
            "status": "rejected",
            "reason_codes": ["invalid_success_contract_status", status],
        }
    normalized["status"] = status
    revision = contract.get("revision", 0)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        return {
            "status": "rejected",
            "reason_codes": ["revision_must_be_non_negative_integer"],
        }
    normalized["revision"] = revision
    for key in SUCCESS_CONTRACT_LIST_KEYS:
        value = contract.get(key, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            return {
                "status": "rejected",
                "reason_codes": [f"{key}_must_be_list_of_strings"],
            }
        normalized[key] = _normalize_string_list(value)
    if not normalized["criteria"]:
        reason_codes.append("criteria_must_not_be_empty")
    forbidden = _scan_forbidden_strings(normalized)
    if forbidden:
        reason_codes.extend(["forbidden_marker_detected", *forbidden])
    if reason_codes:
        return {"status": "rejected", "reason_codes": _dedupe_preserve_order(reason_codes)}
    return {"status": "accepted", "reason_codes": [], "contract": normalized}


def freeze_success_contract(
    *,
    state: Any,
    contract: dict[str, Any],
    receipt_id: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return _commit_success_contract(
        state=state,
        contract=contract,
        receipt_id=receipt_id,
        evidence_refs=evidence_refs,
        require_existing_contract=False,
    )


def propose_success_contract_revision(
    *,
    state: Any,
    proposed: dict[str, Any],
    receipt_id: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return _commit_success_contract(
        state=state,
        contract=proposed,
        receipt_id=receipt_id,
        evidence_refs=evidence_refs,
        require_existing_contract=True,
    )


def render_success_contract(contract: dict[str, Any]) -> str:
    validated = validate_success_contract(contract)
    payload = validated["contract"] if validated["status"] == "accepted" else {
        "status": "rejected",
        "reason_codes": list(validated["reason_codes"]),
        "contract_redacted": True,
    }
    return "[success_contract]\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def audit_success_contract_consistency(
    *,
    task_prompt: str,
    success_contract: dict[str, Any],
    final_state: dict[str, Any],
) -> dict[str, Any]:
    contract_validation = validate_success_contract(success_contract)
    if contract_validation["status"] != "accepted":
        return {
            "status": "fail",
            "reason_codes": ["invalid_success_contract", *contract_validation["reason_codes"]],
            "mismatches": ["success_contract"],
            "missing_evidence": [],
        }
    contract = contract_validation["contract"]
    final_state = dict(final_state or {})
    mismatches: list[str] = []
    missing_evidence: list[str] = []
    reason_codes: list[str] = []

    final_task_prompt = str(final_state.get("task_prompt") or "").strip()
    if final_task_prompt and final_task_prompt != str(task_prompt or "").strip():
        mismatches.append("task_prompt")
        reason_codes.append("task_prompt_mismatch")

    final_contract_raw = final_state.get("success_contract")
    if isinstance(final_contract_raw, dict):
        final_contract_validation = validate_success_contract(final_contract_raw)
        if final_contract_validation["status"] != "accepted":
            mismatches.append("success_contract")
            reason_codes.append("final_success_contract_invalid")
        elif _contract_signature(final_contract_validation["contract"]) != _contract_signature(contract):
            mismatches.append("success_contract")
            reason_codes.append("success_contract_mismatch")

    artifact_refs = _collect_artifact_refs(final_state)
    verifier_checks = _collect_verifier_checks(final_state)

    required_artifacts = list(contract.get("required_artifacts", []))
    required_checks = list(contract.get("required_checks", []))

    if required_artifacts:
        if artifact_refs:
            missing_artifacts = [item for item in required_artifacts if item not in artifact_refs]
            if missing_artifacts:
                mismatches.append("required_artifacts")
                reason_codes.append("missing_required_artifacts")
        else:
            missing_evidence.append("artifact_refs")
            reason_codes.append("missing_artifact_evidence")

    if required_checks:
        if verifier_checks:
            missing_checks = [item for item in required_checks if item not in verifier_checks]
            if missing_checks:
                mismatches.append("required_checks")
                reason_codes.append("missing_required_checks")
        else:
            missing_evidence.append("verifier_checks")
            reason_codes.append("missing_verifier_evidence")

    if mismatches:
        status = "fail"
    elif missing_evidence:
        status = "unclear"
    else:
        status = "pass"

    return {
        "status": status,
        "reason_codes": _dedupe_preserve_order(reason_codes),
        "mismatches": _dedupe_preserve_order(mismatches),
        "missing_evidence": _dedupe_preserve_order(missing_evidence),
        "contract_id": str(contract.get("contract_id") or ""),
        "revision": int(contract.get("revision", 0) or 0),
        "task_prompt": str(task_prompt or ""),
    }


def _commit_success_contract(
    *,
    state: Any,
    contract: dict[str, Any],
    receipt_id: str,
    evidence_refs: list[str],
    require_existing_contract: bool,
) -> dict[str, Any]:
    current_contract = _state_get(state, "success_contract", empty_success_contract())
    if not isinstance(current_contract, dict):
        current_contract = empty_success_contract()
    current_declared = _is_declared_success_contract(current_contract)
    if require_existing_contract and not current_declared:
        return {
            "status": "rejected",
            "reason_codes": ["success_contract_revision_requires_existing_contract"],
            "contract": empty_success_contract(),
        }

    contract_validation = validate_success_contract(contract)
    if contract_validation["status"] != "accepted":
        return {
            "status": "rejected",
            "reason_codes": list(contract_validation["reason_codes"]),
            "contract": dict(contract or {}),
        }

    if evidence_refs is None:
        evidence_refs = []
    if not isinstance(evidence_refs, list):
        return {
            "status": "rejected",
            "reason_codes": ["evidence_refs_must_be_list_of_strings"],
            "contract": contract_validation["contract"],
        }

    merged_refs = _normalize_string_list(list(contract_validation["contract"].get("visible_evidence_refs", [])) + list(evidence_refs))
    merged_candidate = dict(contract_validation["contract"])
    merged_candidate["visible_evidence_refs"] = merged_refs
    validation = validate_success_contract(merged_candidate)
    if validation["status"] != "accepted":
        return {
            "status": "rejected",
            "reason_codes": list(validation["reason_codes"]),
            "contract": merged_candidate,
        }
    if current_declared and not merged_refs:
        return {
            "status": "rejected",
            "reason_codes": ["success_contract_revision_requires_visible_evidence_refs"],
            "contract": validation["contract"],
        }

    current_revision = int(current_contract.get("revision", 0) or 0) if current_declared else -1
    revision = current_revision + 1 if current_declared else 0
    stored_contract = copy.deepcopy(validation["contract"])
    stored_contract["revision"] = revision
    stored_contract["status"] = "revised" if revision > 0 else "frozen"
    stored_contract["contract_id"] = f"success_contract_r{revision:04d}"
    stored_contract["source_receipt_id"] = str(receipt_id or stored_contract.get("source_receipt_id") or "")
    stored_contract["visible_evidence_refs"] = merged_refs

    history = _state_history(state)
    if current_declared:
        history.append(copy.deepcopy(current_contract))
    _state_set(state, "success_contract", stored_contract)
    _state_set(state, "success_contract_history", history)

    return {
        "status": "accepted",
        "reason_codes": [],
        "contract": copy.deepcopy(stored_contract),
        "revision": revision,
        "history_length": len(history),
    }


def _extract_success_contract_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    direct = payload.get("success_contract")
    if isinstance(direct, dict):
        return copy.deepcopy(direct)
    if isinstance(direct, str) and direct.strip():
        parsed = _parse_json_like_text(direct)
        if isinstance(parsed, dict):
            return copy.deepcopy(parsed)
    if _looks_like_success_contract(payload):
        return copy.deepcopy(payload)
    proposed = _proposed_success_contract(payload)
    if proposed is not None:
        return proposed
    control_plane_update = payload.get("control_plane_update")
    if isinstance(control_plane_update, dict):
        nested = _extract_success_contract_from_payload(control_plane_update)
        if nested is not None:
            return nested
        semantic_state = control_plane_update.get("semantic_state")
        if isinstance(semantic_state, dict):
            proposed = _proposed_success_contract(semantic_state)
            if proposed is not None:
                return proposed
    semantic_state = payload.get("semantic_state")
    if isinstance(semantic_state, dict):
        proposed = _proposed_success_contract(semantic_state)
        if proposed is not None:
            return proposed
    return None


def _proposed_success_contract(payload: dict[str, Any]) -> dict[str, Any] | None:
    proposed = payload.get("proposed_success_criteria")
    if proposed is None:
        proposed = payload.get("criteria")
    criteria = _normalize_string_list(proposed if isinstance(proposed, list) else [])
    if not criteria:
        return None
    contract = empty_success_contract()
    contract["status"] = "proposed"
    contract["criteria"] = criteria
    for key in ("required_artifacts", "required_checks", "authority_hierarchy", "known_uncertainty", "suspected_decoy_classes", "done_checklist", "visible_evidence_refs"):
        value = payload.get(key)
        if isinstance(value, list):
            contract[key] = _normalize_string_list(value)
    return contract


def _looks_like_success_contract(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ALLOWED_SUCCESS_CONTRACT_KEYS)


def _parse_json_like_text(text: str) -> Any:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        stripped: list[str] = []
        inside = False
        for line in lines:
            if line.startswith("```"):
                if inside:
                    break
                inside = True
                continue
            if inside:
                stripped.append(line)
        candidate = "\n".join(stripped).strip()
    try:
        return json.loads(candidate)
    except Exception:
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except Exception:
            return None
    return None


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append(text)
    return _dedupe_preserve_order(normalized)


def _scan_forbidden_strings(value: Any, path: str = "success_contract") -> list[str]:
    hits: list[str] = []
    if isinstance(value, str):
        lowered = value.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker in lowered:
                hits.append(f"{path}:{marker}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_scan_forbidden_strings(item, f"{path}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            hits.extend(_scan_forbidden_strings(item, f"{path}.{key}"))
    return hits


def _collect_artifact_refs(final_state: dict[str, Any]) -> list[str]:
    refs = _normalize_string_list(final_state.get("artifact_refs"))
    refs.extend(_normalize_string_list(final_state.get("visible_artifact_refs")))
    artifact_state = final_state.get("artifact_state")
    if isinstance(artifact_state, dict):
        refs.extend(_normalize_string_list(artifact_state.get("artifact_refs")))
        refs.extend(_normalize_string_list(artifact_state.get("captured_paths")))
        refs.extend(_normalize_string_list(artifact_state.get("observed_paths")))
        observed_hashes = artifact_state.get("observed_hashes")
        if isinstance(observed_hashes, dict):
            refs.extend([key for key in observed_hashes if isinstance(key, str) and key.strip()])
    return _dedupe_preserve_order(refs)


def _collect_verifier_checks(final_state: dict[str, Any]) -> list[str]:
    refs = _normalize_string_list(final_state.get("verifier_checks"))
    refs.extend(_normalize_string_list(final_state.get("visible_checks")))
    verifier_state = final_state.get("verifier_state")
    if isinstance(verifier_state, dict):
        refs.extend(_normalize_string_list(verifier_state.get("checks")))
        refs.extend(_normalize_string_list(verifier_state.get("observed_checks")))
    return _dedupe_preserve_order(refs)


def _contract_signature(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "criteria": list(contract.get("criteria", [])),
        "required_artifacts": list(contract.get("required_artifacts", [])),
        "required_checks": list(contract.get("required_checks", [])),
        "authority_hierarchy": list(contract.get("authority_hierarchy", [])),
        "known_uncertainty": list(contract.get("known_uncertainty", [])),
        "suspected_decoy_classes": list(contract.get("suspected_decoy_classes", [])),
        "done_checklist": list(contract.get("done_checklist", [])),
    }


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _state_get(state: Any, key: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _state_set(state: Any, key: str, value: Any) -> None:
    if isinstance(state, dict):
        state[key] = value
    else:
        setattr(state, key, value)


def _state_history(state: Any) -> list[dict[str, Any]]:
    history = _state_get(state, "success_contract_history", None)
    if isinstance(history, list):
        return history
    history = []
    _state_set(state, "success_contract_history", history)
    return history


def _is_declared_success_contract(contract: dict[str, Any]) -> bool:
    if not isinstance(contract, dict):
        return False
    if str(contract.get("status") or "") in {"frozen", "revised"}:
        return True
    if contract.get("criteria"):
        return True
    return False

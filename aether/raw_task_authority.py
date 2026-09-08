"""Independent raw-task authority for Solver and Verifier packets.

The Architect contract is additive.  It may structure task facts and proof
expectations, but it is never the sole representation of the user's task.
This module keeps that boundary in one place so every packet path can bind the
exact task bytes and the separately hashed compiled contract.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


RAW_TASK_SCHEMA_VERSION = "aether.raw_task_authority.v1"
RAW_TASK_LABEL = "raw_user_task"


class RawTaskAuthorityError(ValueError):
    """Raised when a packet cannot prove the raw task was preserved."""


def text_sha256(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise RawTaskAuthorityError("raw user task must be a non-empty string")
    return sha256(text.encode("utf-8", "surrogateescape")).hexdigest()


def canonical_hash(value: Any) -> str:
    """Hash canonical JSON bytes without applying task-text normalization."""
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def task_contract_payload(compiled: Any, contract: Any | None = None) -> dict[str, Any]:
    """Return the exact contract payload bound to a compiled runtime.

    Typed contracts are authoritative.  Older V1 runtimes may have no typed
    contract, so the helper reads the compiled task-contract section when it
    exists and otherwise creates the same minimal compatibility payload that
    the Verifier packet historically used.
    """
    selected = contract if contract is not None else getattr(compiled, "task_contract", None)
    if selected is not None:
        payload = selected.as_payload()
    else:
        payload = None
        contract_sections: list[str] = []
        for name, body in getattr(compiled, "stable_prefix_sections", ()):
            if name != "task_contract":
                continue
            contract_sections.append(str(body))
        if len(contract_sections) > 1:
            raise RawTaskAuthorityError(
                "compiled runtime contains duplicate task contract sections"
            )
        for body in contract_sections:
            try:
                candidate = json.loads(body)
            except (TypeError, json.JSONDecodeError) as exc:
                raise RawTaskAuthorityError(
                    "compiled task contract is not valid canonical JSON"
                ) from exc
            if not isinstance(candidate, Mapping):
                raise RawTaskAuthorityError("compiled task contract must be a JSON object")
            payload = dict(candidate)
            break
        if payload is None:
            clauses: list[dict[str, Any]] = []
            for obligation in getattr(getattr(compiled, "objective_graph", None), "obligations", ()):
                clauses.append({
                    "clause_id": str(obligation.obligation_id),
                    "text": str(obligation.description),
                    "exact_atoms": [str(obligation.target)]
                    if str(obligation.target).strip()
                    else [],
                })
            if not clauses:
                clauses.append({
                    "clause_id": "compiled:objective",
                    "text": str(getattr(compiled, "success_definition", "") or "compiled objective"),
                    "exact_atoms": [],
                })
            payload = {"raw_task_prompt": str(getattr(compiled, "task_prompt", "")), "clauses": clauses}

    raw_task = str(getattr(compiled, "task_prompt", ""))
    text_sha256(raw_task)
    contract_raw = payload.get("raw_task_prompt")
    if not isinstance(contract_raw, str) or not contract_raw:
        raise RawTaskAuthorityError("task contract is missing raw_task_prompt")
    if contract_raw != raw_task:
        raise RawTaskAuthorityError(
            "task contract raw_task_prompt differs from the independent raw user task"
        )
    return dict(payload)


def build_binding(raw_task: str, contract_payload: Mapping[str, Any]) -> dict[str, str]:
    """Build the compact hash binding placed beside the raw task."""
    raw_hash = text_sha256(raw_task)
    contract_hash = canonical_hash(contract_payload)
    schema_version = str(contract_payload.get("schema_version", "") or "")
    relationship = (
        "raw_task_is_sole_semantic_authority"
        if schema_version == "pcr_v11_raw"
        else "contract_is_additive_not_replacement"
    )
    return {
        "schema_version": RAW_TASK_SCHEMA_VERSION,
        "label": RAW_TASK_LABEL,
        "raw_task_sha256": raw_hash,
        "contract_sha256": contract_hash,
        "relationship": relationship,
    }


def validate_solver_messages(
    messages: list[Mapping[str, Any]],
    *,
    expected_raw_task: str,
    expected_contract_sha256: str,
) -> None:
    """Fail closed unless the model-facing Solver packet binds raw task bytes."""
    if not expected_contract_sha256:
        raise RawTaskAuthorityError("Solver packet requires a non-empty contract hash")
    raw_header = f"[{RAW_TASK_LABEL}]\n"
    raw_matches = [
        message.get("content")
        for message in messages
        if message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and message["content"].startswith(raw_header)
    ]
    if len(raw_matches) != 1:
        raise RawTaskAuthorityError(
            f"Solver packet must contain exactly one independent {RAW_TASK_LABEL} section"
        )
    actual_raw = raw_matches[0][len(raw_header):]
    if actual_raw != expected_raw_task:
        raise RawTaskAuthorityError("Solver packet raw task bytes were changed or truncated")
    if any(
        message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and message["content"].startswith("[task_prompt]\n")
        for message in messages
    ):
        raise RawTaskAuthorityError(
            "Solver packet contains a legacy task_prompt section beside the independent raw task"
        )

    binding_header = "[raw_task_binding]\n"
    binding_matches = [
        message.get("content")
        for message in messages
        if message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and message["content"].startswith(binding_header)
    ]
    if len(binding_matches) != 1:
        raise RawTaskAuthorityError("Solver packet is missing its raw-task hash binding")
    try:
        binding = json.loads(binding_matches[0][len(binding_header):])
    except json.JSONDecodeError as exc:
        raise RawTaskAuthorityError("Solver raw-task binding is not valid JSON") from exc
    if not isinstance(binding, Mapping):
        raise RawTaskAuthorityError("Solver raw-task binding must be a JSON object")
    if binding.get("schema_version") != RAW_TASK_SCHEMA_VERSION:
        raise RawTaskAuthorityError("Solver raw-task binding has the wrong schema version")
    if binding.get("label") != RAW_TASK_LABEL:
        raise RawTaskAuthorityError("Solver raw-task binding has the wrong label")
    if binding.get("relationship") not in {
        "contract_is_additive_not_replacement",
        "raw_task_is_sole_semantic_authority",
    }:
        raise RawTaskAuthorityError("Solver raw-task binding has the wrong authority relationship")
    if binding.get("raw_task_sha256") != text_sha256(expected_raw_task):
        raise RawTaskAuthorityError("Solver raw-task hash does not match the visible task")
    if binding.get("contract_sha256") != expected_contract_sha256:
        raise RawTaskAuthorityError("Solver contract hash binding does not match the packet")


def validate_verifier_packet(packet: Mapping[str, Any], *, expected_raw_task: str) -> None:
    """Fail closed unless a Verifier packet carries independent raw-task proof."""
    if packet.get("raw_user_task") != expected_raw_task:
        raise RawTaskAuthorityError("Verifier packet raw user task is missing or changed")
    expected_raw_hash = text_sha256(expected_raw_task)
    if packet.get("raw_task_sha256") != expected_raw_hash:
        raise RawTaskAuthorityError("Verifier packet raw task hash does not match its text")
    contract = packet.get("task_contract")
    if not isinstance(contract, Mapping):
        raise RawTaskAuthorityError("Verifier packet is missing its task contract")
    expected_contract_hash = canonical_hash(contract)
    if packet.get("task_contract_sha256") != expected_contract_hash:
        raise RawTaskAuthorityError("Verifier packet contract hash does not match its contract")
    binding = packet.get("raw_task_binding")
    if not isinstance(binding, Mapping):
        raise RawTaskAuthorityError("Verifier packet is missing raw_task_binding")
    if binding.get("schema_version") != RAW_TASK_SCHEMA_VERSION:
        raise RawTaskAuthorityError("Verifier raw-task binding has the wrong schema version")
    if binding.get("label") != RAW_TASK_LABEL:
        raise RawTaskAuthorityError("Verifier raw-task binding has the wrong label")
    if binding.get("relationship") not in {
        "contract_is_additive_not_replacement",
        "raw_task_is_sole_semantic_authority",
    }:
        raise RawTaskAuthorityError("Verifier raw-task binding has the wrong authority relationship")
    if binding.get("raw_task_sha256") != expected_raw_hash:
        raise RawTaskAuthorityError("Verifier raw-task binding does not match its text")
    if binding.get("contract_sha256") != packet.get("task_contract_sha256"):
        raise RawTaskAuthorityError("Verifier raw-task binding has the wrong contract hash")

"""Deterministic H1 review control with zero task-semantic authority.

This module exists only for the preregistered H1 causal experiment.  It keeps
Aether's normal Verifier protocol/inspection lifecycle but replaces the
semantic Verifier model call with a deterministic currentness check over
Primary-cited evidence.  It never reads or interprets the raw task text to
select an inspection and never invents a test, edge case, or repair.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


H1_REVIEW_ARM_ENV = "AETHER_RESEARCH_H1_REVIEW_ARM"
H1_MECHANICAL_ARM = "mechanical"
H1_SEMANTIC_ARM = "semantic"


def _json_user_payloads(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for message in messages:
        if str(message.get("role") or "") != "user":
            continue
        try:
            value = json.loads(str(message.get("content") or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            payloads.append(value)
    return payloads


def _latest_inspection_result(payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    for payload in reversed(payloads):
        rows = payload.get("verifier_inspection_results")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            inspection_id = str(row.get("inspection_id") or "").strip()
            if not inspection_id or row.get("error") not in (None, ""):
                continue
            if row.get("observation_valid") is not True:
                continue
            return dict(row)
    return None


def _verifier_packet(payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    for payload in payloads:
        packet = payload.get("verifier_packet")
        if isinstance(packet, Mapping):
            return dict(packet)
    return None


def _nonempty_strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _first_primary_cited_route(packet: Mapping[str, Any]) -> dict[str, Any] | None:
    """Select one task-agnostic re-observation route from Primary-cited evidence."""
    submission = packet.get("primary_submission")
    if not isinstance(submission, Mapping):
        return None
    cited = submission.get("cited_evidence")
    if not isinstance(cited, (list, tuple)):
        cited = submission.get("cited_evidence_index")
    if not isinstance(cited, (list, tuple)):
        return None

    # Frozen priority from H1_MECHANICAL_BASELINE_SHIM_CONTRACT.md.
    # Pass 1: exact/current workspace path already present in a cited receipt.
    for row in cited:
        if not isinstance(row, Mapping):
            continue
        projection = row.get("current_payload_projection")
        if not isinstance(projection, Mapping):
            continue
        candidates: list[str] = []
        candidates.extend(_nonempty_strings(projection.get("path")))
        for field in (
            "modified_paths", "artifact_paths", "produced_artifacts", "created_paths",
        ):
            candidates.extend(_nonempty_strings(projection.get(field)))
        if candidates:
            return {
                "request_id": "h1-mechanical-read-primary-cited-path",
                "kind": "read_file",
                "path": candidates[0],
                "proof_ids": [],
            }

    # Pass 2: immutable output handle already named by cited evidence.
    for row in cited:
        if not isinstance(row, Mapping):
            continue
        projection = row.get("current_payload_projection")
        if not isinstance(projection, Mapping):
            continue
        handle = str(projection.get("handle") or "").strip()
        if handle:
            return {
                "request_id": "h1-mechanical-read-primary-cited-output",
                "kind": "read_output",
                "handle": handle,
                "proof_ids": [],
            }

    # No semantic fallback: an unavailable mechanical route is itself an H1
    # tooling-boundary outcome rather than permission to invent a new test.
    return None


def _raw_task_clause_ids(packet: Mapping[str, Any]) -> list[str]:
    contract = packet.get("task_contract")
    if not isinstance(contract, Mapping):
        return []
    clauses = contract.get("clauses")
    if not isinstance(clauses, (list, tuple)):
        return []
    return [
        str(row.get("clause_id") or "").strip()
        for row in clauses
        if isinstance(row, Mapping) and str(row.get("clause_id") or "").strip()
    ]


def _compiled_proof_ids(packet: Mapping[str, Any]) -> list[str]:
    rows = packet.get("compiled_proof_requirements")
    if not isinstance(rows, (list, tuple)):
        return []
    return [
        str(row.get("proof_id") or "").strip()
        for row in rows
        if isinstance(row, Mapping) and str(row.get("proof_id") or "").strip()
    ]


class H1MechanicalReviewVerifier:
    """ModelCallable-compatible deterministic control for the H1 baseline arm."""

    is_h1_mechanical_review_control = True

    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int | None = None,
    ) -> str:
        del max_output_tokens
        self.calls += 1
        payloads = _json_user_payloads(messages)
        packet = _verifier_packet(payloads) or {}
        observed = _latest_inspection_result(payloads)
        if observed is not None:
            inspection_id = str(observed["inspection_id"])
            actual_class = str(
                observed.get("actual_evidence_class")
                or observed.get("evidence_ceiling")
                or "metadata_proxy"
            ).strip()
            return json.dumps({
                "verdict": "completed",
                "confidence": "high",
                "summary": (
                    "H1 mechanical control re-observed Primary-cited current evidence; "
                    "no task-semantic correctness judgment was performed."
                ),
                "findings": [],
                "missing_evidence_requests": [],
                "completion_evidence": [{
                    "requirement": "mechanical currentness of Primary-cited completion evidence",
                    "observed": "one Primary-cited evidence boundary was re-observed successfully",
                    "inspection_refs": [inspection_id],
                    "clause_ids": _raw_task_clause_ids(packet),
                    "proof_ids": _compiled_proof_ids(packet),
                    "evidence_class": actual_class,
                    "risk_refs": [],
                    "requirement_status": "satisfied",
                    "falsification_check": (
                        "route failure, stale/unavailable evidence, or a non-current observation "
                        "would falsify this mechanical currentness check"
                    ),
                }],
                "method_validity": None,
            }, sort_keys=True)

        route = _first_primary_cited_route(packet)
        if route is not None:
            return json.dumps({
                "kind": "inspect",
                "requests": [route],
            }, sort_keys=True)

        return json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "high",
            "summary": (
                "H1 mechanical control found no mechanically re-observable Primary-cited route; "
                "it did not substitute a semantic inspection."
            ),
            "findings": [],
            "missing_evidence_requests": [],
            "completion_evidence": [],
            "method_validity": None,
        }, sort_keys=True)

"""Solver-facing completion projection boundary.

Internal verifier state (findings, receipts, evidence kinds) carries provenance
vocabulary — owner names, route identifiers, receipt kinds — that must never
reach the Primary's model surface.  The Primary should see only neutral factual
task state: what is unresolved, what evidence exists, what needs attention.
It should NOT be able to infer that any independent judging process exists.

This module owns that single projection seam. Internal trace/ledger terminology
remains truthful (``model_verifier_result``, ``run_verifier_command``, etc.);
only the model-facing Primary view is neutralized.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

# Fields whose VALUES may embed Verifier-identity vocabulary.  These are
# dropped from the Solver-facing finding rows entirely.
_FIELDS_DROPPED = frozenset({
    "owner",
    "required_evidence_route",
    "supporting_inspection_ids",
    "lifecycle_origin",
    "keep_until",
    "repair_condition",
})

# Receipt/evidence kind substrings that reveal independent-review identity.
_IDENTITY_PATTERNS = re.compile(
    r"model_verifier|verifier_result|verifier_inspection|reviewer_tool|"
    r"reviewer_capability|run_verifier",
    re.IGNORECASE,
)

_NEUTRAL_EVIDENCE_TYPE = {
    "model_verifier_inspection": "completion_evidence_inspection",
    "model_verifier_result": "completion_review_outcome",
    "verifier_result_evidence": "completion_outcome_evidence",
}


def neutralize_text(text: str) -> str:
    """Replace Verifier-identity vocabulary in a rendered string."""
    text = _IDENTITY_PATTERNS.sub("completion_review", text)
    text = text.replace("run_verifier_command", "derived_execution")
    text = text.replace("model_verifier", "completion_review")
    return text


def _neutralize_value(value: str) -> str:
    if _IDENTITY_PATTERNS.search(value):
        return neutralize_text(value)
    return value


def solver_facing_completion_projection(
    raw_findings: list[Mapping[str, Any]],
    *,
    current_step: int,
) -> list[dict[str, Any]]:
    """Project internal findings into neutral Solver-facing rows.

    Drops provenance fields, neutralizes identity vocabulary in remaining
    values, and preserves the factual epistemic content (what is unresolved,
    what evidence exists, what repair would address it).
    """
    out = []
    for f in raw_findings:
        row: dict[str, Any] = {}
        for key, val in f.items():
            if key in _FIELDS_DROPPED:
                continue
            if key == "finding_id":
                # Neutralize vf-* style prefixes without losing uniqueness.
                clean_id = re.sub(r"^(vf-|verifier[-_])", "cf-", str(val))
                row["finding_id"] = clean_id
            elif key == "summary" or key == "repair_instruction":
                row[key] = _neutralize_value(str(val))
            elif key == "verdict":
                # Map verdict values to observation-status language.
                v = str(val)
                if v == "uncertain_missing_evidence":
                    row[key] = "observation_unavailable"
                elif v == "needs_repair":
                    row[key] = "defect_identified"
                else:
                    row[key] = _neutralize_value(v)
            else:
                row[key] = val
        out.append(row)
    return out


def _factualize_text(text: str) -> str:
    """Remove independent-review identity while preserving the observed defect."""

    value = neutralize_text(str(text or ""))
    value = re.sub(
        r"\b(?:verifier|reviewer|completion[_ ]review)\b",
        "current-state observation",
        value,
        flags=re.IGNORECASE,
    )
    return value


def solver_facing_factual_defect_projection(
    raw_findings: list[Mapping[str, Any]],
    *,
    current_step: int,
    current_task_state_generation: int | None = None,
    witness_handles: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Expose grounded review claims without turning reviewer judgment into fact.

    The Solver receives the factual witness and its candidate generation, but not
    reviewer-authored repair strategy.  A review claim remains explicitly a
    review claim so Luna can challenge an unsupported interpretation against the
    raw task and current world state.
    """
    witness_handles = dict(witness_handles or {})
    projected = solver_facing_completion_projection(
        raw_findings, current_step=current_step
    )
    out: list[dict[str, Any]] = []
    for raw_finding, finding in zip(raw_findings, projected):
        row: dict[str, Any] = {"source": "independent_review"}
        finding_id = str(finding.get("finding_id", "") or "").strip()
        if finding_id:
            row["finding_id"] = finding_id
        verdict = str(finding.get("verdict", "") or "").strip().lower()
        supporting = raw_finding.get("supporting_inspection_ids")
        supporting_ids = [
            str(item) for item in supporting
            if str(item).strip()
        ] if isinstance(supporting, (list, tuple)) else []
        if verdict in {"needs_repair", "violated", "defect_identified"}:
            row["state"] = "review_claim_needs_repair"
            row["epistemic_status"] = (
                "review_claim_with_inspection_support"
                if supporting_ids
                else "review_interpretation_without_direct_witness"
            )
        elif verdict in {"uncertain_missing_evidence", "observation_unavailable"}:
            row["state"] = "review_evidence_incomplete"
            row["epistemic_status"] = "missing_or_inconclusive_evidence"
        elif verdict:
            row["state"] = _factualize_text(verdict)
            row["epistemic_status"] = "review_claim"
        row["semantic_authority"] = "raw_user_task"
        row["challenged_requirement_status"] = "review_interpretation_against_raw_user_task"
        row["observed_precondition_status"] = "not_separately_reported_by_reviewer"
        row["expected_result_status"] = "not_separately_task_grounded_by_reviewer"
        row["coverage_status"] = (
            "explicit_support_refs_present" if supporting_ids else "no_explicit_support_refs"
        )
        row["supporting_observation_count"] = len(supporting_ids)
        summary = str(finding.get("summary", "") or "").strip()
        if summary:
            row["summary"] = _factualize_text(summary)
        evidence = finding.get("evidence")
        if isinstance(evidence, (list, tuple)):
            observations = [
                _factualize_text(str(item)) for item in evidence if str(item).strip()
            ]
            if observations:
                row["observations"] = observations
                row["actual_observed_result_status"] = (
                    "inspection_linked_review_observation"
                    if supporting_ids
                    else "review_reported_observation_without_explicit_inspection_ref"
                )
            else:
                row["actual_observed_result_status"] = "not_reported_by_reviewer"
        applies_to = finding.get("applies_to")
        if isinstance(applies_to, (list, tuple)):
            values = [str(item) for item in applies_to if str(item).strip()]
            if values:
                row["applies_to"] = values
        observed_generation = finding.get("observed_task_state_generation")
        try:
            generation = int(observed_generation)
        except (TypeError, ValueError):
            generation = -1
        if generation >= 0:
            row["candidate_generation"] = generation
            if current_task_state_generation is not None:
                row["currentness"] = (
                    "current_candidate"
                    if generation == int(current_task_state_generation)
                    else "historical_candidate"
                )
        raw_finding_id = str(raw_finding.get("finding_id", "") or "").strip()
        handle = witness_handles.get(raw_finding_id) or witness_handles.get(finding_id)
        if handle:
            row["witness_handle"] = handle
            row["witness_access"] = "read_output"
        if row:
            out.append(row)
    return out


def neutralize_evidence_type(evidence_type: str) -> str:
    """Map internal evidence kind to a Solver-neutral label."""
    return _NEUTRAL_EVIDENCE_TYPE.get(evidence_type, evidence_type)


def is_internal_review_receipt_kind(kind: str) -> bool:
    """True when a receipt kind belongs to the independent review lane."""
    return _IDENTITY_PATTERNS.search(kind) is not None

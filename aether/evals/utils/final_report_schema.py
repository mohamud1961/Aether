from __future__ import annotations

from typing import Dict, List, Mapping, Tuple


FINAL_REPORT_SCHEMA_VERSION = "v1.1.0"

REQUIRED_TOP_LEVEL_FIELDS = (
    "schema_version",
    "run_id",
    "terminal_outcome",
    "claims",
)

REQUIRED_CLAIM_FIELDS = (
    "claim_id",
    "statement",
    "evidence_refs",
)


def validate_final_report_schema(report: Mapping[str, object]) -> Tuple[List[str], List[Dict[str, object]]]:
    missing_top = [field for field in REQUIRED_TOP_LEVEL_FIELDS if report.get(field) in (None, "")]
    claim_errors: List[Dict[str, object]] = []

    claims = report.get("claims")
    if not isinstance(claims, list) or not claims:
        claim_errors.append({"code": "claims_missing_or_empty"})
        return missing_top, claim_errors

    for idx, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            claim_errors.append({"code": "claim_not_object", "index": idx})
            continue

        missing_claim = [field for field in REQUIRED_CLAIM_FIELDS if claim.get(field) in (None, "")]
        if missing_claim:
            claim_errors.append({"code": "claim_missing_fields", "index": idx, "fields": missing_claim})
            continue

        evidence_refs = claim.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            claim_errors.append({"code": "claim_evidence_refs_empty", "index": idx})
            continue

        invalid_refs = [ref for ref in evidence_refs if not isinstance(ref, str) or not ref]
        if invalid_refs:
            claim_errors.append({"code": "claim_evidence_refs_invalid", "index": idx})

    return missing_top, claim_errors

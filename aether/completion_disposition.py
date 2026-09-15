"""Mechanical completion-finding disposition gate.

This research-only module never adjudicates whether a completion finding is
true.  It only requires Primary to explicitly account for every currently
open finding before final completion when the treatment is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

CONTROL = "control"
COMPLETION_DISPOSITION_V1 = "completion_disposition_v1"
SUPPORTED_MODES = frozenset({CONTROL, COMPLETION_DISPOSITION_V1})
_ALLOWED_DISPOSITIONS = frozenset({"resolved", "not_applicable", "override"})


@dataclass(frozen=True)
class CompletionDispositionDecision:
    allowed: bool
    reason: str
    required_finding_ids: tuple[str, ...]
    dispositions: tuple[dict[str, Any], ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "required_finding_ids": list(self.required_finding_ids),
            "dispositions": [dict(item) for item in self.dispositions],
            "semantic_authority": "primary_solver_against_raw_task_and_observed_reality",
            "harness_role": "mechanical_disposition_coverage_only",
        }


def current_completion_finding_ids(packet: Mapping[str, Any]) -> tuple[str, ...]:
    """Return active finding IDs that still apply to the current candidate.

    The Solver-facing projection explicitly labels findings from an older task
    state generation as ``historical_candidate``.  Those rows remain useful
    context, but P1 must not turn them into a current completion obligation or
    mutate the provider finish schema merely because history is still visible.
    Rows without a currentness label remain included for backward-compatible
    active-finding custody.
    """
    raw = packet.get("open_completion_findings")
    if not isinstance(raw, list):
        return ()
    result: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("currentness") or "").strip().lower() == "historical_candidate":
            continue
        finding_id = str(item.get("finding_id") or "").strip()
        if finding_id and finding_id not in result:
            result.append(finding_id)
    return tuple(result)


def evaluate_completion_dispositions(
    turn: Any,
    packet: Mapping[str, Any],
    *,
    mode: str = CONTROL,
) -> CompletionDispositionDecision:
    """Mechanically validate Primary-authored dispositions for current findings.

    No task semantics are interpreted.  The function checks only that every
    current finding ID is accounted for exactly once and that the selected
    disposition carries the minimal model-authored fields promised by the
    protocol.  Evidence references are checked only for syntactic consistency
    with the final completion turn; their semantic adequacy remains Primary's
    responsibility and may still be challenged by independent evaluation.
    """
    selected = str(mode or CONTROL).strip().lower()
    if selected not in SUPPORTED_MODES:
        raise ValueError(f"unsupported completion disposition mode: {mode}")

    required_ids = current_completion_finding_ids(packet)
    raw_dispositions = getattr(turn, "finding_dispositions", ()) or ()
    dispositions = tuple(
        dict(item) for item in raw_dispositions if isinstance(item, Mapping)
    )

    if selected == CONTROL:
        return CompletionDispositionDecision(True, "control_mode", required_ids, dispositions)
    if not required_ids:
        if dispositions:
            return CompletionDispositionDecision(
                False, "unexpected_disposition_without_open_finding", required_ids, dispositions,
            )
        return CompletionDispositionDecision(True, "no_open_findings", required_ids, ())
    if len(dispositions) != len(raw_dispositions):
        return CompletionDispositionDecision(
            False, "disposition_not_object", required_ids, dispositions,
        )

    by_id: dict[str, dict[str, Any]] = {}
    final_evidence_refs = {
        str(ref).strip() for ref in (getattr(turn, "evidence_refs", ()) or ())
        if str(ref).strip()
    }
    for item in dispositions:
        finding_id = str(item.get("finding_id") or "").strip()
        disposition = str(item.get("disposition") or "").strip().lower()
        explanation = str(item.get("explanation") or "").strip()
        residual_uncertainty = str(item.get("residual_uncertainty") or "").strip()
        refs_raw = item.get("evidence_refs", ())
        if isinstance(refs_raw, str):
            refs_raw = (refs_raw,)
        if not isinstance(refs_raw, (list, tuple)):
            return CompletionDispositionDecision(
                False, "disposition_evidence_refs_invalid", required_ids, dispositions,
            )
        refs = tuple(str(ref).strip() for ref in refs_raw if str(ref).strip())

        if not finding_id:
            return CompletionDispositionDecision(False, "finding_id_missing", required_ids, dispositions)
        if finding_id in by_id:
            return CompletionDispositionDecision(False, "duplicate_finding_disposition", required_ids, dispositions)
        if finding_id not in required_ids:
            return CompletionDispositionDecision(False, "unknown_finding_disposition", required_ids, dispositions)
        if disposition not in _ALLOWED_DISPOSITIONS:
            return CompletionDispositionDecision(False, "unsupported_disposition", required_ids, dispositions)
        if disposition in {"not_applicable", "override"} and not explanation:
            return CompletionDispositionDecision(False, "disposition_explanation_missing", required_ids, dispositions)
        if refs and not set(refs).issubset(final_evidence_refs):
            return CompletionDispositionDecision(False, "disposition_evidence_not_in_finish_refs", required_ids, dispositions)
        if disposition == "resolved" and not refs:
            return CompletionDispositionDecision(False, "resolved_disposition_requires_evidence", required_ids, dispositions)
        if disposition == "override" and not residual_uncertainty:
            return CompletionDispositionDecision(False, "override_requires_residual_uncertainty", required_ids, dispositions)
        by_id[finding_id] = item

    if set(by_id) != set(required_ids):
        return CompletionDispositionDecision(False, "open_finding_not_dispositioned", required_ids, dispositions)
    return CompletionDispositionDecision(True, "all_open_findings_dispositioned", required_ids, dispositions)


__all__ = [
    "COMPLETION_DISPOSITION_V1",
    "CONTROL",
    "SUPPORTED_MODES",
    "CompletionDispositionDecision",
    "current_completion_finding_ids",
    "evaluate_completion_dispositions",
]

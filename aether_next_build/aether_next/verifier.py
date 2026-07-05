"""Model-verifier data structures and active finding lifecycle."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import re
from typing import Any

VERIFIER_VERDICTS = frozenset({
    "completed",
    "needs_repair",
    "uncertain_missing_evidence",
    "blocked_by_tooling",
    "blocked_by_harness_config",
})


@dataclass(frozen=True)
class VerifierFinding:
    finding_id: str
    created_step: int
    verdict: str
    priority: str
    summary: str
    evidence: tuple[str, ...] = ()
    repair_instruction: str = ""
    applies_to: tuple[str, ...] = ()
    keep_until: str = "resolved_or_superseded"
    status: str = "active"
    superseded_by: str = ""
    # Number of verifier calls since this finding was created (or last
    # re-mentioned/superseded) where the verifier's result did not touch it at
    # all -- i.e. a non-completed verdict that simply left it sitting there
    # unchanged. A verdict of e.g. uncertain_missing_evidence with an empty
    # findings list does not resolve, supersede, or even reconsider prior
    # findings; without tracking this, a stale finding can block completion
    # forever even after the solver has provided exactly the evidence requested.
    stale_cycles: int = 0

    def as_context(self, *, current_step: int) -> dict[str, Any]:
        data = asdict(self)
        data["age_steps"] = max(0, current_step - self.created_step)
        return data


@dataclass(frozen=True)
class ModelVerifierResult:
    verdict: str
    confidence: str = "medium"
    summary: str = ""
    findings: tuple[VerifierFinding, ...] = ()
    missing_evidence_requests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.verdict not in VERIFIER_VERDICTS:
            raise ValueError(f"unknown verifier verdict: {self.verdict}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "summary": self.summary,
            "findings": [asdict(finding) for finding in self.findings],
            "missing_evidence_requests": list(self.missing_evidence_requests),
        }


@dataclass
class ActiveFindingStore:
    active: dict[str, VerifierFinding] = field(default_factory=dict)
    archived: dict[str, VerifierFinding] = field(default_factory=dict)

    def apply_result(
        self,
        result: ModelVerifierResult,
        *,
        step: int,
        resolve_stale_by_evidence: bool = False,
    ) -> None:
        if result.verdict == "completed":
            for finding in list(self.active.values()):
                self.archive(finding.finding_id, status="resolved")
            return
        touched_ids: set[str] = set()
        for finding in result.findings:
            updated = VerifierFinding(
                finding_id=finding.finding_id,
                created_step=finding.created_step or step,
                verdict=finding.verdict,
                priority=finding.priority,
                summary=finding.summary,
                evidence=finding.evidence,
                repair_instruction=finding.repair_instruction,
                applies_to=finding.applies_to,
                keep_until=finding.keep_until,
            )
            touched_ids |= self._supersede_overlapping(updated)
            touched_ids.add(updated.finding_id)
            self.active[updated.finding_id] = updated
        # A non-completed verdict that doesn't mention a prior finding at all
        # (e.g. uncertain_missing_evidence with an empty findings list) leaves
        # it completely untouched by the loop above. Track that explicitly so
        # staleness is visible and, when the runtime has independently
        # confirmed the requested evidence category exists (resolve_stale_by_
        # evidence=True), a finding predating this call can be cleared instead
        # of blocking completion indefinitely on a verdict that never revisits it.
        for finding_id, finding in list(self.active.items()):
            if finding_id in touched_ids:
                continue
            if resolve_stale_by_evidence and finding.created_step < step:
                self.archive(finding_id, status="resolved_by_evidence")
                continue
            self.active[finding_id] = replace(finding, stale_cycles=finding.stale_cycles + 1)

    def archive(self, finding_id: str, *, status: str, superseded_by: str = "") -> None:
        finding = self.active.pop(finding_id, None)
        if finding is None:
            return
        self.archived[finding_id] = VerifierFinding(
            finding_id=finding.finding_id,
            created_step=finding.created_step,
            verdict=finding.verdict,
            priority=finding.priority,
            summary=finding.summary,
            evidence=finding.evidence,
            repair_instruction=finding.repair_instruction,
            applies_to=finding.applies_to,
            keep_until=finding.keep_until,
            status=status,
            superseded_by=superseded_by,
        )

    def invalidate(self, finding_id: str) -> None:
        self.archive(finding_id, status="invalidated")

    def context(self, *, current_step: int, limit: int = 4) -> list[dict[str, Any]]:
        ordered = sorted(self.active.values(), key=lambda item: (item.priority != "blocking", item.created_step))
        return [finding.as_context(current_step=current_step) for finding in ordered[:limit]]

    def _supersede_overlapping(self, new: VerifierFinding) -> set[str]:
        new_targets = set(new.applies_to)
        superseded: set[str] = set()
        for old in list(self.active.values()):
            if old.verdict == new.verdict and set(old.applies_to) == new_targets:
                self.archive(old.finding_id, status="superseded", superseded_by=new.finding_id)
                superseded.add(old.finding_id)
        return superseded


def parse_model_verifier_result(value: Any) -> ModelVerifierResult:
    """Normalize a model-verifier return value into ``ModelVerifierResult``.

    The kernel accepts the existing Python object for tests and also model-like
    JSON strings/dicts for the real verifier lane. The parser is deliberately
    evidence-bound: completed verdicts must carry summary/evidence, and repair
    verdicts must carry at least one finding or missing-evidence request.
    """
    if isinstance(value, ModelVerifierResult):
        return value
    data = _load_result_mapping(value)
    verdict = str(data.get("verdict", "")).strip()
    if verdict not in VERIFIER_VERDICTS:
        raise ValueError(f"unknown verifier verdict: {verdict}")
    findings = _parse_findings(data, default_verdict=verdict)
    missing = _string_tuple(data.get("missing_evidence_requests", ()))
    if verdict == "completed" and not _has_completion_evidence(data, findings):
        raise ValueError("completed verifier verdict requires summary or evidence")
    if verdict == "needs_repair" and not findings:
        raise ValueError("needs_repair verifier verdict requires at least one finding")
    if verdict == "uncertain_missing_evidence" and not missing:
        raise ValueError("uncertain_missing_evidence requires missing_evidence_requests")
    if verdict == "uncertain_missing_evidence" and missing and not findings:
        findings = _findings_from_missing_evidence_requests(missing)
    return ModelVerifierResult(
        verdict=verdict,
        confidence=str(data.get("confidence", "medium")).strip() or "medium",
        summary=str(data.get("summary", "")).strip(),
        findings=findings,
        missing_evidence_requests=missing,
    )


def _load_result_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("empty verifier result")
        parsed = _parse_lenient_json_object(text)
        if isinstance(parsed, dict):
            return parsed
    raise TypeError("verifier result must be ModelVerifierResult, dict, or JSON object string")


def _parse_lenient_json_object(text: str) -> Any:
    """Parse a verifier JSON object from plain, fenced, or prose-wrapped text.

    The verifier is still fail-closed: it never fabricates a verdict.  This
    helper only extracts an actual JSON object when one is present.
    """
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            inner = "\n".join(lines[1:-1]).strip()
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                stripped = inner
    decoder = json.JSONDecoder()
    for idx, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(stripped[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("invalid verifier JSON: no JSON object found")


def _parse_findings(data: dict[str, Any], *, default_verdict: str) -> tuple[VerifierFinding, ...]:
    raw = data.get("findings") or data.get("blocking_findings") or data.get("blocking_issues") or ()
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return ()
    parsed: list[VerifierFinding] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or item.get("issue") or item.get("description") or "").strip()
        evidence = _string_tuple(item.get("evidence", ()))
        repair = str(item.get("repair_instruction") or item.get("next_action") or "").strip()
        if not summary and not evidence and not repair:
            continue
        parsed.append(VerifierFinding(
            finding_id=str(item.get("finding_id") or item.get("id") or f"vf-model-{idx}").strip(),
            created_step=_nonnegative_int(item.get("created_step", 0)),
            verdict=str(item.get("verdict") or default_verdict).strip(),
            priority=str(item.get("priority", "blocking")).strip() or "blocking",
            summary=summary or repair or "verifier finding",
            evidence=evidence,
            repair_instruction=repair,
            applies_to=_string_tuple(item.get("applies_to") or item.get("targets") or item.get("paths") or ()),
            keep_until=str(item.get("keep_until", "resolved_or_superseded")).strip() or "resolved_or_superseded",
        ))
    return tuple(parsed)


def _findings_from_missing_evidence_requests(
    missing: tuple[str, ...],
) -> tuple[VerifierFinding, ...]:
    findings: list[VerifierFinding] = []
    for idx, request in enumerate(missing):
        clean = re.sub(r"\s+", " ", request).strip()
        digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:12]
        findings.append(VerifierFinding(
            finding_id=f"vf-missing-evidence-{idx}-{digest}",
            created_step=0,
            verdict="uncertain_missing_evidence",
            priority="blocking",
            summary=f"Missing verifier evidence: {clean}",
            evidence=(clean,),
            repair_instruction=(
                "Produce fresh current-state evidence that directly satisfies "
                "this verifier request before submitting again."
            ),
            applies_to=("verifier_evidence", f"missing_request:{digest}"),
        ))
    return tuple(findings)


def _has_completion_evidence(data: dict[str, Any], findings: tuple[VerifierFinding, ...]) -> bool:
    if str(data.get("summary", "")).strip():
        return True
    if _string_tuple(data.get("evidence", ())):
        return True
    return any(finding.evidence for finding in findings)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)

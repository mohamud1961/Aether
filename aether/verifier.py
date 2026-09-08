"""Model-verifier data structures and active finding lifecycle."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import re
from typing import Any, Mapping

VERIFIER_VERDICTS = frozenset({
    "completed",
    "needs_repair",
    "uncertain_missing_evidence",
    "blocked_by_tooling",
    "blocked_by_harness_config",
    "incomplete_state_wrong",
    "incomplete_missing_required_artifact",
    "incomplete_semantic_mismatch",
    "insufficient_inspectable_evidence",
    "reviewer_tool_execution_failed",
    "reviewer_capability_missing",
    "probe_inconclusive",
    "environment_blocked",
    "timeout_or_budget_blocked",
})

SOLVER_REPAIR_VERDICTS = frozenset({
    "needs_repair",
    "incomplete_state_wrong",
    "incomplete_missing_required_artifact",
    "incomplete_semantic_mismatch",
})

METHOD_VALIDITY_REQUIRED_FIELDS = (
    "observed_structure",
    "executed_rule",
    "method_alignment",
    "authoritative_source_refs",
    "execution_ref",
)

METHOD_VALIDITY_SHAPE = {
    "observed_structure": "the directly observed authoritative structure used by the method",
    "executed_rule": "the rule the derived execution actually applied",
    "method_alignment": "why that rule measures the semantic determinant rather than a descriptive proxy",
    "authoritative_source_refs": ["earlier successful inspection_id values used as authoritative inputs"],
    "execution_ref": (
        "the verdict-eligible derived execution inspection_id, or null when the verdict "
        "relies only on direct admissible observations"
    ),
}


class MethodValidityShapeError(ValueError):
    """A verdict parsed as JSON but its method-validity record is incomplete."""

    def __init__(
        self,
        *,
        missing: tuple[str, ...] = (),
        invalid: tuple[str, ...] = (),
    ) -> None:
        self.missing = missing
        self.invalid = invalid
        parts: list[str] = []
        if missing:
            parts.append("missing required fields: " + ", ".join(missing))
        if invalid:
            parts.append("invalid fields: " + ", ".join(invalid))
        super().__init__("method_validity " + "; ".join(parts))


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
    owner: str = "solver_state"
    observed_task_state_generation: int = -1
    supporting_inspection_ids: tuple[str, ...] = ()
    repair_condition: str = ""
    required_evidence_route: str = ""
    # Number of verifier calls since this finding was created (or last
    # re-mentioned/superseded) where the verifier's result did not touch it at
    # all -- i.e. a non-completed verdict that simply left it sitting there
    # unchanged. A verdict of e.g. uncertain_missing_evidence with an empty
    # findings list does not resolve, supersede, or even reconsider prior
    # findings; without tracking this, a stale finding can block completion
    # forever even after the solver has provided exactly the evidence requested.
    stale_cycles: int = 0
    # Kernel-internal provenance distinguishes parser-generated missing-evidence
    # findings from explicit model-authored findings without trusting IDs/text.
    lifecycle_origin: str = "model_provided"

    def as_context(self, *, current_step: int) -> dict[str, Any]:
        data = asdict(self)
        data.pop("lifecycle_origin", None)
        data["age_steps"] = max(0, current_step - self.created_step)
        return data


class CompletionEvidenceShapeError(ValueError):
    """A completed verdict named a completion_evidence record with an invalid shape.

    Distinguished from a generic ``ValueError`` so the runtime loop
    (``model_hooks.verify_with_inspector``) can route a present-but-malformed
    record to the completion_evidence_shape retry instead of the generic
    "not valid protocol JSON" retry: the model's output DID parse as JSON and
    named the field, only this one field's shape is wrong. Still a
    ``ValueError`` subtype so existing ``except ValueError`` / ``pytest.raises
    (ValueError)`` call sites keep working unchanged.
    """


@dataclass(frozen=True)
class CompletionEvidenceEntry:
    """One requirement -> observed-evidence mapping backing a completed verdict.

    The runtime checks presence, non-emptiness, and that ``inspection_refs``
    resolve to inspections actually performed in the verification round.
    It never evaluates the reasoning content -- that stays the model's job.
    """

    requirement: str
    observed: str
    falsification_check: str
    inspection_refs: tuple[str, ...] = ()
    # Optional compiled semantic metadata.  Legacy verifier responses omit
    # these fields and continue to use requirement text; V5-wired responses
    # provide clause coverage and an evidence class for the runtime gate.
    clause_ids: tuple[str, ...] = ()
    # Shadow-v2 proof IDs are kernel-owned requirement references.  Empty
    # keeps legacy verifier result serialization unchanged.
    proof_ids: tuple[str, ...] = ()
    evidence_class: str = ""
    # The Architect's false-positive risks are task-specific contract data.
    # A completed verdict must explicitly say which of those risks this
    # evidence entry addresses; the kernel checks only exact contract
    # membership, never whether the model's explanation is semantically true.
    risk_refs: tuple[str, ...] = ()
    # F94 PCR-only structured coherence signal. Generic/ASV provider schemas do
    # not advertise or require it; empty keeps legacy serialization unchanged.
    # The kernel never derives this value from prose or task content.
    requirement_status: str = ""


@dataclass(frozen=True)
class MethodValidityRecord:
    """Model-authored link from an executed verifier method to prior evidence.

    The runtime validates only populated fields and reference identity.  It
    never decides whether the model's extraction rule is semantically correct.
    """

    observed_structure: str
    executed_rule: str
    method_alignment: str
    authoritative_source_refs: tuple[str, ...]
    execution_ref: str


@dataclass(frozen=True)
class ModelVerifierResult:
    verdict: str
    confidence: str = "medium"
    summary: str = ""
    findings: tuple[VerifierFinding, ...] = ()
    missing_evidence_requests: tuple[str, ...] = ()
    completion_evidence: tuple[CompletionEvidenceEntry, ...] = ()
    method_validity: MethodValidityRecord | None = None
    # PCR-only typed direct inspections requested by an uncertain verdict.
    # Appended after the historical fields so older positional constructors keep
    # their meaning. These are routing data, not semantic evidence.
    missing_inspection_requests: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.verdict not in VERIFIER_VERDICTS:
            raise ValueError(f"unknown verifier verdict: {self.verdict}")

    def as_dict(self) -> dict[str, Any]:
        completion_evidence = []
        for entry in self.completion_evidence:
            encoded = asdict(entry)
            if not entry.proof_ids:
                encoded.pop("proof_ids", None)
            if not entry.requirement_status:
                encoded.pop("requirement_status", None)
            completion_evidence.append(encoded)
        serialized_findings: list[dict[str, Any]] = []
        for finding in self.findings:
            encoded = asdict(finding)
            encoded.pop("lifecycle_origin", None)
            serialized_findings.append(encoded)
        data = {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "summary": self.summary,
            "findings": serialized_findings,
            "missing_evidence_requests": list(self.missing_evidence_requests),
            "completion_evidence": completion_evidence,
            "method_validity": asdict(self.method_validity) if self.method_validity else None,
        }
        if self.missing_inspection_requests:
            data["missing_inspection_requests"] = [dict(item) for item in self.missing_inspection_requests]
        return data


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
        task_state_generation: int = -1,
        resolved_finding_ids: set[str] | None = None,
    ) -> None:
        if result.verdict == "completed":
            resolved = set(resolved_finding_ids or ())
            for finding_id, finding in list(self.active.items()):
                if finding_id in resolved:
                    self.archive(finding_id, status="resolved_by_current_evidence")
                else:
                    self.active[finding_id] = replace(
                        finding, stale_cycles=finding.stale_cycles + 1,
                    )
            return
        touched_ids: set[str] = set()
        generated_current = tuple(
            finding for finding in result.findings
            if finding.lifecycle_origin == "generated_missing_evidence"
        )
        if generated_current:
            current_generated_ids = {finding.finding_id for finding in generated_current}
            replacement_id = generated_current[0].finding_id
            for finding_id, prior in list(self.active.items()):
                if prior.lifecycle_origin != "generated_missing_evidence":
                    continue
                if finding_id in current_generated_ids:
                    touched_ids.add(finding_id)
                    continue
                self.archive(finding_id, status="superseded", superseded_by=replacement_id)
                touched_ids.add(finding_id)
        for finding in result.findings:
            updated = VerifierFinding(
                finding_id=finding.finding_id,
                # Activation time and generation are kernel lifecycle authority.
                created_step=int(step),
                verdict=finding.verdict,
                priority=finding.priority,
                summary=finding.summary,
                evidence=finding.evidence,
                repair_instruction=finding.repair_instruction,
                applies_to=finding.applies_to,
                keep_until=finding.keep_until,
                owner=finding.owner,
                observed_task_state_generation=int(task_state_generation),
                supporting_inspection_ids=finding.supporting_inspection_ids,
                repair_condition=finding.repair_condition or finding.repair_instruction,
                required_evidence_route=finding.required_evidence_route,
                lifecycle_origin=finding.lifecycle_origin,
            )
            is_generated_refresh = (
                updated.lifecycle_origin == "generated_missing_evidence"
                and updated.finding_id in self.active
                and self.active[updated.finding_id].lifecycle_origin == "generated_missing_evidence"
            )
            if not is_generated_refresh:
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
            owner=finding.owner,
            observed_task_state_generation=finding.observed_task_state_generation,
            supporting_inspection_ids=finding.supporting_inspection_ids,
            repair_condition=finding.repair_condition,
            required_evidence_route=finding.required_evidence_route,
            lifecycle_origin=finding.lifecycle_origin,
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
    missing_inspections = _mapping_tuple(data.get("missing_inspection_requests", ()))
    if verdict != "uncertain_missing_evidence" and missing_inspections:
        raise ValueError("missing_inspection_requests is only valid for uncertain_missing_evidence")
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
        missing_inspection_requests=missing_inspections,
        completion_evidence=_parse_completion_evidence(data),
        method_validity=_parse_method_validity(data),
    )


def _parse_method_validity(data: Mapping[str, Any]) -> MethodValidityRecord | None:
    raw = data.get("method_validity")
    if raw in (None, "", ()):
        return None
    if not isinstance(raw, Mapping):
        raise MethodValidityShapeError(
            invalid=("method_validity must be an object",),
        )
    unknown = tuple(
        f"method_validity.{field} is not accepted"
        for field in raw
        if field not in METHOD_VALIDITY_REQUIRED_FIELDS
    )
    refs_raw = raw.get("authoritative_source_refs", ())
    if isinstance(refs_raw, str):
        refs_raw = [refs_raw]
    if not isinstance(refs_raw, (list, tuple)):
        invalid = unknown + ("method_validity.authoritative_source_refs must be a list",)
        refs = ()
    else:
        invalid = unknown
        refs = tuple(str(ref or "").strip() for ref in refs_raw if str(ref or "").strip())
    observed = str(raw.get("observed_structure") or "").strip()
    rule = str(raw.get("executed_rule") or "").strip()
    alignment = str(raw.get("method_alignment") or "").strip()
    execution_ref = str(raw.get("execution_ref") or "").strip()
    # execution_ref is conditionally required by the runtime only when the
    # verdict relies on a derived execution.  Direct-observation-only verdicts
    # may emit null here; normalize that optional audit prose away rather than
    # forcing the model to invent a derived inspection identifier.  All other
    # method-validity fields remain strict, and any actual overlay execution is
    # still gated below by verify_completion_protocol.
    missing = tuple(
        field
        for field, value in (
            ("observed_structure", observed),
            ("executed_rule", rule),
            ("method_alignment", alignment),
            ("authoritative_source_refs", refs),
        )
        if not value
    )
    if missing or invalid:
        raise MethodValidityShapeError(missing=missing, invalid=invalid)
    if not execution_ref:
        return None
    return MethodValidityRecord(observed, rule, alignment, refs, execution_ref)


def _parse_completion_evidence(data: Mapping[str, Any]) -> tuple[CompletionEvidenceEntry, ...]:
    """Normalize the completed-verdict evidence record.

    Absence is tolerated here: the runtime loop owns the retry-then-refuse
    protocol for a completed verdict without a record (it is the only layer
    that can check inspection_refs against inspections actually performed).
    Present-but-malformed entries are a protocol error, same as malformed
    findings.
    """
    raw = data.get("completion_evidence", ())
    if raw in (None, "", ()):
        return ()
    if isinstance(raw, Mapping):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raise CompletionEvidenceShapeError("completion_evidence must be a list of entries")
    entries: list[CompletionEvidenceEntry] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise CompletionEvidenceShapeError(f"completion_evidence[{idx}] must be an object")
        refs_raw = item.get("inspection_refs", ())
        if isinstance(refs_raw, str):
            refs_raw = [refs_raw]
        if not isinstance(refs_raw, (list, tuple)):
            raise CompletionEvidenceShapeError(f"completion_evidence[{idx}].inspection_refs must be a list")
        refs = tuple(str(ref).strip() for ref in refs_raw if str(ref).strip())
        clause_raw = item.get("clause_ids", item.get("clauses", ()))
        if isinstance(clause_raw, str):
            clause_raw = [clause_raw]
        if not isinstance(clause_raw, (list, tuple)):
            raise CompletionEvidenceShapeError(f"completion_evidence[{idx}].clause_ids must be a list")
        clause_ids = tuple(str(value).strip() for value in clause_raw if str(value).strip())
        risk_raw = item.get("risk_refs", ())
        if isinstance(risk_raw, str):
            risk_raw = [risk_raw]
        if not isinstance(risk_raw, (list, tuple)):
            raise CompletionEvidenceShapeError(f"completion_evidence[{idx}].risk_refs must be a list")
        risk_refs = tuple(str(value).strip() for value in risk_raw if str(value).strip())
        proof_raw = item.get("proof_ids", ())
        if isinstance(proof_raw, str):
            proof_raw = [proof_raw]
        if not isinstance(proof_raw, (list, tuple)):
            raise CompletionEvidenceShapeError(f"completion_evidence[{idx}].proof_ids must be a list")
        proof_ids = tuple(str(value).strip() for value in proof_raw if str(value).strip())
        requirement_status = str(item.get("requirement_status", "")).strip()
        entries.append(
            CompletionEvidenceEntry(
                requirement=str(item.get("requirement", "")).strip(),
                observed=str(item.get("observed", "")).strip(),
                falsification_check=str(item.get("falsification_check", "")).strip(),
                inspection_refs=refs,
                clause_ids=clause_ids,
                proof_ids=proof_ids,
                evidence_class=str(item.get("evidence_class", "")).strip(),
                risk_refs=risk_refs,
                requirement_status=requirement_status,
            )
        )
    return tuple(entries)



_TOOL_FAILURE_WORDS = ("not found", "no such", "failed", "unavailable", "missing", "timed out", "timeout", "permission")
_INCONCLUSIVE_WORDS = ("inconclusive", "ambiguous", "cannot determine", "unable to determine")
_MISSING_ARTIFACT_WORDS = ("missing file", "file not found", "required artifact", "does not exist")
_SEMANTIC_WORDS = ("wrong", "mismatch", "incorrect", "not within", "invalid value", "semantic")


def classify_verifier_outcome(
    result: ModelVerifierResult,
    *,
    inspection_summary: dict[str, Any] | None = None,
) -> str:
    """Return a precise audit classification for a verifier result.

    This does not change the model's raw verdict. It gives result rows and
    traces a sharper root-cause label than legacy ``blocked_by_tooling``.
    """
    if result.verdict == "completed":
        return "completed"
    text = " ".join(
        [result.verdict, result.summary]
        + [finding.summary for finding in result.findings]
        + [" ".join(finding.evidence) for finding in result.findings]
        + list(result.missing_evidence_requests)
    ).lower()
    inspection_summary = inspection_summary or {}
    error_count = int(inspection_summary.get("inspection_error_count", 0) or 0)
    tools_used = inspection_summary.get("inspection_tools_used", ()) or ()
    if result.verdict in {"reviewer_tool_execution_failed", "reviewer_capability_missing", "probe_inconclusive", "environment_blocked", "timeout_or_budget_blocked"}:
        return result.verdict
    if result.verdict == "blocked_by_harness_config":
        return "reviewer_capability_missing"
    if result.verdict == "blocked_by_tooling":
        if error_count:
            return "reviewer_tool_execution_failed"
        if any(word in text for word in _INCONCLUSIVE_WORDS):
            return "probe_inconclusive"
        if not tools_used:
            return "reviewer_capability_missing"
        return "probe_inconclusive"
    if any(word in text for word in _MISSING_ARTIFACT_WORDS):
        return "incomplete_missing_required_artifact"
    if any(word in text for word in _SEMANTIC_WORDS):
        return "incomplete_semantic_mismatch"
    if result.verdict == "uncertain_missing_evidence":
        return "insufficient_inspectable_evidence"
    if any(word in text for word in _TOOL_FAILURE_WORDS) and error_count:
        return "reviewer_tool_execution_failed"
    return "incomplete_state_wrong" if result.verdict == "needs_repair" else result.verdict

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
        requested_finding_id = str(
            item.get("finding_id") or item.get("id") or f"vf-model-{idx}"
        ).strip()
        if requested_finding_id.startswith("vf-missing-evidence-"):
            digest = hashlib.sha256(requested_finding_id.encode("utf-8")).hexdigest()[:12]
            requested_finding_id = f"vf-model-{idx}-{digest}"
        parsed.append(VerifierFinding(
            finding_id=requested_finding_id,
            created_step=_nonnegative_int(item.get("created_step", 0)),
            verdict=str(item.get("verdict") or default_verdict).strip(),
            priority=str(item.get("priority", "blocking")).strip() or "blocking",
            summary=summary or repair or "completion finding",
            evidence=evidence,
            repair_instruction=repair,
            applies_to=_string_tuple(item.get("applies_to") or item.get("targets") or item.get("paths") or ()),
            keep_until=str(item.get("keep_until", "resolved_or_superseded")).strip() or "resolved_or_superseded",
            owner=str(item.get("owner", "solver_state")).strip() or "solver_state",
            observed_task_state_generation=_signed_int(item.get("observed_task_state_generation", -1), default=-1),
            supporting_inspection_ids=_string_tuple(item.get("supporting_inspection_ids") or item.get("inspection_refs") or ()),
            repair_condition=str(item.get("repair_condition", "")).strip(),
            required_evidence_route=str(item.get("required_evidence_route", "")).strip(),
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
            summary=f"Missing inspectable completion evidence: {clean}",
            evidence=(clean,),
            repair_instruction=(
                "Produce fresh current-state evidence that directly satisfies "
                "this completion-evidence request before submitting again."
            ),
            applies_to=("completion_evidence", f"missing_request:{digest}"),
            lifecycle_origin="generated_missing_evidence",
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


def _mapping_tuple(value: Any) -> tuple[Mapping[str, Any], ...]:
    if value in (None, "", ()):
        return ()
    if isinstance(value, Mapping):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise ValueError("missing_inspection_requests must be a list of objects")
    rows: list[Mapping[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"missing_inspection_requests[{idx}] must be an object")
        rows.append(dict(item))
    return tuple(rows)


def _signed_int(value: Any, *, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)

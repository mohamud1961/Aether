"""Fresh-context verification and replay checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import json
import re

from harness.aether2.traces.redaction import _clean_hidden_refs
from harness.aether2.runtime.verify_evidence import (
    _classify_evidence_provenance,
    _classify_evidence_strength,
    _finalize_evidence_refs,
    _has_clean_support,
    _normalize_provenance_labels,
)
from harness.aether2.runtime.verify_report import (
    _CONSTRAINT_SIGNAL_TOKENS,
    _assistant_message,
    _build_evidence_source_catalog,
    _call_model,
    _constraint_coverage_tokens,
    _extract_text,
    _extract_tool_calls,
    _inspection_payload,
    _looks_like_constraint,
    _normalize_requirement_item,
    _normalize_verdict,
    _parse_report,
    _parse_tool_call_arguments,
    _read_error_field,
    _read_field,
    _strip_transcript_fields,
    _tool_call_name,
    _verifier_output_failure,
)


@dataclass(frozen=True)
class CheckResult:
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    cwd: str
    duration_sec: float
    timed_out: bool = False
    error_kind: str | None = None
    error_reason_code: str | None = None


@dataclass(frozen=True)
class RequirementResult:
    requirement: str
    verdict: str
    evidence: str
    evidence_strength: str = "weak"
    evidence_strength_reasons: tuple[str, ...] = ()
    evidence_provenance: tuple[str, ...] = ()
    confidence: str = "low"
    evidence_refs: tuple[str, ...] = ()
    unresolved: bool = False


@dataclass(frozen=True)
class DiscrepancyReport:
    requirements: tuple[RequirementResult, ...]
    reason_codes: tuple[str, ...]
    summary: str
    raw_response: str

    @property
    def unresolved_requirements(self) -> tuple[RequirementResult, ...]:
        return tuple(
            item
            for item in self.requirements
            if item.unresolved or item.verdict in {"unsatisfied", "unverifiable"}
        )

    @property
    def has_unresolved_gaps(self) -> bool:
        """True when verification still has any unresolved requirement or parse failure."""
        if "verifier_parse_failed" in self.reason_codes:
            return True
        return any(
            item.unresolved or item.verdict in {"unsatisfied", "unverifiable"}
            for item in self.requirements
        )

    @property
    def has_discrepancies(self) -> bool:
        """Compatibility alias for unresolved-gap semantics."""
        return self.has_unresolved_gaps


VERIFIER_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a read-only inspection command in the live task environment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string"},
                    "timeout_sec": {"type": "integer", "default": 120},
                    "cwd": {"type": ["string", "null"]},
                },
                "required": ["cmd"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the live task workspace without modifying it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": ["integer", "null"]},
                    "limit": {"type": ["integer", "null"]},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "job_status",
            "description": "Inspect a detached job without modifying it.",
            "parameters": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "session_read",
            "description": "Read the current contents of a session without sending input.",
            "parameters": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
                "additionalProperties": False,
            },
        },
    },
]


def replay_checks(checks: list[str], executor: Any) -> list[CheckResult]:
    results: list[CheckResult] = []
    for command in checks:
        raw = executor.run(command, timeout_sec=120, cwd=None)
        results.append(
            CheckResult(
                command=command,
                exit_code=_read_field(raw, "exit_code"),
                stdout=str(_read_field(raw, "stdout", "")),
                stderr=str(_read_field(raw, "stderr", "")),
                cwd=str(_read_field(raw, "cwd", "")),
                duration_sec=float(_read_field(raw, "duration_sec", _read_field(raw, "duration", 0.0))),
                timed_out=bool(_read_field(raw, "timed_out", False)),
                error_kind=_read_error_field(raw, "kind"),
                error_reason_code=_read_error_field(raw, "reason_code"),
            )
        )
    return results


def verify_fresh_context(
    task: str,
    orientation: Mapping[str, Any],
    diff: Mapping[str, Any],
    claim: Mapping[str, Any],
    checks_results: list[CheckResult],
    action_digest: Mapping[str, Any],
    model_client: Any,
    inspection_ctx: Any | None = None,
    record_exchange: Any | None = None,
    stated_requirements: list[str] | None = None,
) -> DiscrepancyReport:
    clean_orientation = _strip_transcript_fields(_clean_hidden_refs(dict(orientation)))
    clean_diff = _strip_transcript_fields(_clean_hidden_refs(dict(diff)))
    clean_claim = _strip_transcript_fields(_clean_hidden_refs(dict(claim)))
    clean_checks = [
        _strip_transcript_fields(_clean_hidden_refs(result.__dict__))
        for result in checks_results
    ]
    clean_action_digest = _strip_transcript_fields(_clean_hidden_refs(dict(action_digest)))
    clean_stated_requirements = [
        str(item).strip() for item in (stated_requirements or []) if str(item).strip()
    ]
    payload = {
        "task": task,
        "orientation": clean_orientation,
        "workspace_diff": clean_diff,
        "claim": clean_claim,
        "checks_results": clean_checks,
        "action_digest": clean_action_digest,
    }
    if clean_stated_requirements:
        payload["stated_requirements"] = clean_stated_requirements
    messages = [
        {
            "role": "system",
            "content": (
                "You are a fresh-context verifier. Evaluate the claim requirement by requirement, "
                "using only the provided task, orientation, workspace diff, replayed checks, and action digest. "
                "Do not assume access to any executor transcript.\n\n"
                "Respond with a single JSON object and nothing else, using EXACTLY this schema "
                "(no other top-level keys are allowed):\n"
                "{\n"
                '  "requirements": [\n'
                '    {"requirement": "<short description of one task requirement>", '
                '"verdict": "satisfied" | "unsatisfied" | "unverifiable", '
                '"evidence": "<evidence for this verdict>", '
                '"evidence_refs": ["<source ref such as checks_results[0], workspace_diff, '
                'action_digest.tool_calls[1], inspection.run_command[0]>", "..."]}\n'
                "    ... one entry per distinct requirement implied by the task ...\n"
                "  ],\n"
                '  "reason_codes": [<list of short machine-readable strings; empty list if no problems>],\n'
                '  "summary": "<one or two sentence overall summary>"\n'
                "}\n"
                'Do NOT use alternative keys such as "claim_satisfied", "verdict" at the top level, or "overall_evidence". '
                'Every requirement entry must use exactly the keys "requirement", "verdict", "evidence", and "evidence_refs". '
                '"evidence_refs" must be grounded in the provided payload or read-only inspection results, '
                'and "verdict" must be exactly one of "satisfied", "unsatisfied", or "unverifiable". '
                "For service or persistence claims, treat a running process, open port, or single startup probe as weak evidence; "
                "prefer bounded survival checks, correct-environment client probes, response/state validation, and any crash/restart/replacement evidence.\n\n"
                "If the payload includes \"stated_requirements\", your \"requirements\" list MUST include at least one entry "
                "for each stated requirement (positive behavior, negative/forbidden side-effect constraints, required "
                "artifact/install paths, final-state/directory invariants, and persistence/service requirements). "
                "Do not invent constraints beyond the provided task text or stated_requirements; cite the exact stated "
                "requirement text in the requirement field."
            ),
        },
        {"role": "user", "content": json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)},
    ]
    response = _call_model(
        model_client,
        messages,
        VERIFIER_TOOL_SCHEMAS if inspection_ctx is not None else [],
    )
    if record_exchange is not None:
        record_exchange(
            messages,
            response,
            VERIFIER_TOOL_SCHEMAS if inspection_ctx is not None else [],
            call_role="verifier",
        )
    messages_for_parse = list(messages)
    inspection_records: list[dict[str, Any]] = []
    tool_calls = _extract_tool_calls(response)
    if inspection_ctx is not None and tool_calls:
        messages_for_parse.append(_assistant_message(response))
        for tool_call in tool_calls:
            tool_name = _tool_call_name(tool_call)
            if tool_name is None:
                continue
            arguments = _parse_tool_call_arguments(tool_call)
            handler = getattr(inspection_ctx, tool_name, None)
            if handler is None:
                continue
            result = handler(**arguments)
            sanitized_result = _inspection_payload(result)
            inspection_records.append(
                {
                    "tool_name": tool_name,
                    "arguments": dict(arguments),
                    "result": sanitized_result,
                }
            )
            messages_for_parse.append(
                {
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tool_call.get("id"),
                    "content": json.dumps(
                        sanitized_result,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ),
                }
            )
        response = _call_model(model_client, messages_for_parse, [])
        if record_exchange is not None:
            record_exchange(
                messages_for_parse,
                response,
                [],
                call_role="verifier",
            )
    raw_text = _extract_text(response)
    parsed = _parse_report(raw_text)
    source_catalog = _build_evidence_source_catalog(
        clean_orientation,
        clean_diff,
        clean_claim,
        clean_checks,
        clean_action_digest,
        inspection_records,
        raw_response=raw_text,
        parsed_report=parsed,
    )
    requirements = tuple(
        _requirement_result_from_report_item(
            item,
            reason_codes=parsed.get("reason_codes", []),
            source_catalog=source_catalog,
        )
        for item in parsed.get("requirements", [])
        if str(item.get("requirement", "")).strip()
    )
    requirements = requirements + _uncovered_constraint_results(
        clean_stated_requirements, requirements
    )
    return DiscrepancyReport(
        requirements=requirements,
        reason_codes=tuple(str(code) for code in parsed.get("reason_codes", [])),
        summary=str(parsed.get("summary", "")),
        raw_response=raw_text,
    )


def _requirement_result_from_report_item(
    item: Mapping[str, Any],
    *,
    reason_codes: list[str],
    source_catalog: Mapping[str, Any],
) -> RequirementResult:
    requirement = str(item.get("requirement", ""))
    verdict = _normalize_verdict(str(item.get("verdict", "unverifiable")))
    evidence = str(item.get("evidence", ""))
    evidence_refs = _finalize_evidence_refs(item.get("evidence_refs"), evidence, source_catalog)
    evidence_provenance = _normalize_provenance_labels(item.get("evidence_provenance"))
    assessment = _classify_evidence_strength(
        requirement=requirement,
        verdict=verdict,
        evidence=evidence,
        evidence_refs=evidence_refs,
        source_catalog=source_catalog,
        report_reason_codes=reason_codes,
    )
    if not evidence_provenance:
        evidence_provenance = _classify_evidence_provenance(
            requirement=requirement,
            verdict=verdict,
            evidence=evidence,
            evidence_refs=evidence_refs,
            source_catalog=source_catalog,
            report_reason_codes=reason_codes,
            assessment=assessment,
        )
    return RequirementResult(
        requirement=requirement,
        verdict=verdict,
        evidence=evidence,
        evidence_strength=assessment["strength"],
        evidence_strength_reasons=tuple(assessment["reasons"]),
        evidence_provenance=tuple(evidence_provenance),
        confidence=assessment["confidence"],
        evidence_refs=evidence_refs,
        unresolved=verdict in {"unsatisfied", "unverifiable"} or not _has_clean_support(
            verdict=verdict,
            strength=assessment["strength"],
            evidence_provenance=tuple(evidence_provenance),
            evidence_strength_reasons=tuple(assessment["reasons"]),
        ),
    )


def _uncovered_constraint_results(
    stated_requirements: list[str],
    requirements: tuple[RequirementResult, ...],
) -> tuple[RequirementResult, ...]:
    """W5.2: stated task constraints / final-state requirements that the verifier
    did not address at all become explicit unresolved gaps, so a verifier that
    only inspects shape/proxy evidence for the obvious requirement cannot
    silently leave declared constraints (final-state, forbidden side effects,
    install paths, persistence) uncovered and still report `verifier_clean=true`.
    """
    if not stated_requirements:
        return ()
    covered_tokens: set[str] = set()
    for item in requirements:
        covered_tokens |= _constraint_coverage_tokens(item.requirement)
        covered_tokens |= _constraint_coverage_tokens(item.evidence)
    extras: list[RequirementResult] = []
    for stated in stated_requirements:
        if not _looks_like_constraint(stated):
            continue
        stated_tokens = _constraint_coverage_tokens(stated)
        if not stated_tokens:
            continue
        overlap = stated_tokens & covered_tokens
        if len(overlap) >= max(1, len(stated_tokens) // 2):
            continue
        extras.append(
            RequirementResult(
                requirement=stated,
                verdict="unverifiable",
                evidence=(
                    "Stated task requirement/constraint was not addressed by any "
                    "verifier requirement entry."
                ),
                evidence_strength="weak",
                evidence_strength_reasons=("uncovered_stated_requirement",),
                evidence_provenance=("unknown",),
                confidence="low",
                evidence_refs=("claim",),
                unresolved=True,
            )
        )
    return tuple(extras)

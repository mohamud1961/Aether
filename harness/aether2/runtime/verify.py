"""Fresh-context verification and replay checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import json
import re

from harness.aether2.traces.redaction import _clean_hidden_refs


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


def _call_model(model_client: Any, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
    if hasattr(model_client, "call"):
        return model_client.call(messages, tools, cache_prefix_len=0)
    raise TypeError("model_client must define call(messages, tools, *, cache_prefix_len)")


def _read_field(raw: Any, name: str, default: Any = None) -> Any:
    if isinstance(raw, Mapping):
        return raw.get(name, default)
    return getattr(raw, name, default)


def _extract_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, Mapping):
        for key in ("output_text", "text", "content"):
            value = response.get(key)
            if isinstance(value, str) and value:
                return value
    if hasattr(response, "output_text") and isinstance(response.output_text, str):
        return response.output_text
    if hasattr(response, "text") and isinstance(response.text, str):
        return response.text
    if hasattr(response, "content") and isinstance(response.content, str):
        return response.content
    return json.dumps(response, sort_keys=True, default=str, ensure_ascii=True)


def _extract_tool_calls(response: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(response, Mapping):
        tool_calls = response.get("tool_calls")
        if isinstance(tool_calls, list):
            return tuple(dict(item) for item in tool_calls if isinstance(item, Mapping))
    value = getattr(response, "tool_calls", ())
    if isinstance(value, tuple):
        return tuple(dict(item) for item in value if isinstance(item, Mapping))
    if isinstance(value, list):
        return tuple(dict(item) for item in value if isinstance(item, Mapping))
    return ()


def _assistant_message(response: Any) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": _extract_text(response)}
    tool_calls = _extract_tool_calls(response)
    if tool_calls:
        message["tool_calls"] = [dict(item) for item in tool_calls]
    return message


def _parse_report(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except Exception:
        return _verifier_output_failure(
            requirement="verification_output_parse",
            evidence="Verifier output was not valid JSON for the required verification schema.",
            reason_codes=("verifier_parse_failed", "verifier_output_not_json"),
            summary="Verifier output could not be parsed.",
            evidence_refs=("verifier.raw_response",),
        )
    if not isinstance(parsed, dict):
        return _verifier_output_failure(
            requirement="verification_output_schema",
            evidence="Verifier output JSON was not an object matching the required top-level schema.",
            reason_codes=("verifier_parse_failed", "verifier_schema_invalid"),
            summary="Verifier output could not be normalized to the required schema.",
            evidence_refs=("verifier.raw_response", "verifier.parsed_output"),
        )
    if "requirements" not in parsed or "reason_codes" not in parsed or "summary" not in parsed:
        return _verifier_output_failure(
            requirement="verification_output_schema",
            evidence="Verifier output JSON was missing one or more required top-level keys: requirements, reason_codes, summary.",
            reason_codes=("verifier_parse_failed", "verifier_schema_invalid"),
            summary="Verifier output could not be normalized to the required schema.",
            evidence_refs=("verifier.raw_response", "verifier.parsed_output"),
        )
    requirements = parsed.get("requirements", [])
    reason_codes = parsed.get("reason_codes", [])
    summary = parsed.get("summary", "")
    if not isinstance(requirements, list) or not isinstance(reason_codes, list) or not isinstance(summary, str):
        return _verifier_output_failure(
            requirement="verification_output_schema",
            evidence="Verifier output JSON used invalid top-level value types for requirements, reason_codes, or summary.",
            reason_codes=("verifier_parse_failed", "verifier_schema_invalid"),
            summary="Verifier output could not be normalized to the required schema.",
            evidence_refs=("verifier.raw_response", "verifier.parsed_output"),
        )
    normalized_requirements: list[dict[str, Any]] = []
    schema_issues: list[str] = []
    for index, item in enumerate(requirements):
        normalized_item, item_issues = _normalize_requirement_item(item, index=index)
        schema_issues.extend(item_issues)
        if normalized_item is not None:
            normalized_requirements.append(normalized_item)
    if schema_issues:
        normalized_requirements.append(
            {
                "requirement": "verification_output_schema",
                "verdict": "unverifiable",
                "evidence": (
                    "Verifier output violated the required requirement schema: "
                    + "; ".join(schema_issues[:4])
                ),
                "evidence_refs": ["verifier.raw_response", "verifier.parsed_output"],
            }
        )
        reason_codes = _dedupe([*(str(item) for item in reason_codes), "verifier_parse_failed", "verifier_schema_invalid"])
    else:
        reason_codes = [str(item) for item in reason_codes]
    parsed["requirements"] = normalized_requirements
    parsed["reason_codes"] = reason_codes
    parsed["summary"] = summary
    return parsed


def _verifier_output_failure(
    *,
    requirement: str,
    evidence: str,
    reason_codes: tuple[str, ...],
    summary: str,
    evidence_refs: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "requirements": [
            {
                "requirement": requirement,
                "verdict": "unverifiable",
                "evidence": evidence,
                "evidence_refs": list(evidence_refs),
            }
        ],
        "reason_codes": list(reason_codes),
        "summary": summary,
    }


def _normalize_requirement_item(item: Any, *, index: int) -> tuple[dict[str, Any] | None, list[str]]:
    label = f"requirements[{index}]"
    if not isinstance(item, Mapping):
        return None, [f"{label} must be an object"]
    requirement = item.get("requirement")
    evidence = item.get("evidence")
    verdict = item.get("verdict")
    raw_evidence_refs = item.get("evidence_refs")
    issues: list[str] = []
    if not isinstance(requirement, str) or not requirement.strip():
        issues.append(f"{label}.requirement must be a non-empty string")
    if not isinstance(evidence, str) or not evidence.strip():
        issues.append(f"{label}.evidence must be a non-empty string")
    if not isinstance(verdict, str) or _normalize_verdict(verdict) != verdict.strip().lower():
        issues.append(f'{label}.verdict must be "satisfied", "unsatisfied", or "unverifiable"')
    evidence_refs: list[str] = []
    if raw_evidence_refs is None:
        issues.append(f"{label}.evidence_refs must be a list")
    elif not isinstance(raw_evidence_refs, list):
        issues.append(f"{label}.evidence_refs must be a list")
    else:
        evidence_refs = [str(ref) for ref in raw_evidence_refs if str(ref).strip()]
        if not evidence_refs:
            issues.append(f"{label}.evidence_refs must contain at least one non-empty reference")
    if not isinstance(requirement, str) or not requirement.strip():
        return None, issues
    normalized = {
        "requirement": requirement.strip(),
        "verdict": _normalize_verdict(str(verdict if verdict is not None else "")),
        "evidence": str(evidence if evidence is not None else ""),
        "evidence_refs": evidence_refs,
    }
    return normalized, issues


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


def _constraint_coverage_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 4}


# W5.2: only stated requirements that read as constraints, final-state, or
# side-effect/path requirements are checked for verifier coverage. Plain
# positive-outcome restatements are left alone -- they are already covered by
# the verifier's own free-form requirement enumeration, and flagging every
# stated line as a separate coverage requirement would make short, single-line
# tasks spuriously unresolved.
_CONSTRAINT_SIGNAL_TOKENS = (
    "not ",
    "must not",
    "only",
    "without",
    "forbidden",
    "must remain",
    "do not",
    "don't",
    "never",
    "final",
    "remain unchanged",
    "preserve",
    "outside",
    "/",
)


def _looks_like_constraint(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _CONSTRAINT_SIGNAL_TOKENS)


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


def _normalize_verdict(verdict: str) -> str:
    normalized = verdict.strip().lower()
    if normalized in {"satisfied", "unsatisfied", "unverifiable"}:
        return normalized
    return "unverifiable"


def _strip_transcript_fields(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if "transcript" in str(key).lower():
                continue
            cleaned[str(key)] = _strip_transcript_fields(value)
        return cleaned
    if isinstance(payload, list):
        return [_strip_transcript_fields(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(_strip_transcript_fields(item) for item in payload)
    return payload


def _read_error_field(raw: Any, name: str) -> str | None:
    error = _read_field(raw, "error", None)
    if error is None:
        return None
    if isinstance(error, Mapping):
        value = error.get(name)
    else:
        value = getattr(error, name, None)
    if value is None:
        return None
    return str(value)


def _tool_call_name(tool_call: Mapping[str, Any]) -> str | None:
    name = tool_call.get("name")
    if isinstance(name, str) and name:
        return name
    function = tool_call.get("function")
    if isinstance(function, Mapping):
        nested_name = function.get("name")
        if isinstance(nested_name, str) and nested_name:
            return nested_name
    return None


def _parse_tool_call_arguments(tool_call: Mapping[str, Any]) -> dict[str, Any]:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, Mapping):
        return dict(arguments)
    if isinstance(arguments, str):
        if not arguments.strip():
            return {}
        try:
            parsed = json.loads(arguments)
        except (TypeError, ValueError):
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _inspection_payload(result: Any) -> dict[str, Any]:
    payload = {
        "exit_code": _read_field(result, "exit_code"),
        "cwd": _read_field(result, "cwd", ""),
        "stdout_head": _read_field(result, "stdout_head", _read_field(result, "stdout", "")),
        "stdout_tail": _read_field(result, "stdout_tail", ""),
        "stderr_head": _read_field(result, "stderr_head", _read_field(result, "stderr", "")),
        "stderr_tail": _read_field(result, "stderr_tail", ""),
    }
    error = _read_field(result, "error", None)
    if error is not None:
        if isinstance(error, Mapping):
            payload["error"] = dict(error)
        else:
            payload["error"] = getattr(error, "__dict__", {"message": str(error)})
    return payload


def _build_evidence_source_catalog(
    orientation: Mapping[str, Any],
    diff: Mapping[str, Any],
    claim: Mapping[str, Any],
    checks_results: list[Mapping[str, Any]],
    action_digest: Mapping[str, Any],
    inspection_records: list[Mapping[str, Any]],
    *,
    raw_response: str,
    parsed_report: Mapping[str, Any],
) -> dict[str, Any]:
    catalog: dict[str, Any] = {
        "orientation": orientation,
        "workspace_diff": diff,
        "claim": claim,
        "checks_results": checks_results,
        "action_digest": action_digest,
        "verifier.raw_response": raw_response,
        "verifier.parsed_output": parsed_report,
    }
    tool_calls = action_digest.get("tool_calls")
    if isinstance(tool_calls, list):
        catalog["action_digest.tool_calls"] = tool_calls
        for index, tool_call in enumerate(tool_calls):
            catalog[f"action_digest.tool_calls[{index}]"] = tool_call
    for index, result in enumerate(checks_results):
        catalog[f"checks_results[{index}]"] = result
    inspection_by_tool: dict[str, list[Mapping[str, Any]]] = {}
    for record in inspection_records:
        tool_name = str(record.get("tool_name", "")).strip()
        if not tool_name:
            continue
        inspection_by_tool.setdefault(tool_name, []).append(record)
    for tool_name, records in inspection_by_tool.items():
        catalog[f"inspection.{tool_name}"] = records
        for index, record in enumerate(records):
            catalog[f"inspection.{tool_name}[{index}]"] = record
    return catalog


def _finalize_evidence_refs(raw_refs: Any, evidence: str, source_catalog: Mapping[str, Any]) -> tuple[str, ...]:
    refs = _normalize_evidence_refs(raw_refs)
    if not refs:
        refs = _extract_inline_refs(evidence, source_catalog)
    if not refs:
        refs = _infer_evidence_refs(evidence, source_catalog)
    return refs


def _normalize_evidence_refs(raw_refs: Any) -> tuple[str, ...]:
    if not isinstance(raw_refs, list):
        return ()
    seen: set[str] = set()
    refs: list[str] = []
    for raw_ref in raw_refs:
        ref = str(raw_ref).strip()
        if not ref or ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return tuple(refs)


def _normalize_provenance_labels(raw_labels: Any) -> tuple[str, ...]:
    if not isinstance(raw_labels, list):
        return ()
    seen: set[str] = set()
    labels: list[str] = []
    for raw_label in raw_labels:
        label = str(raw_label).strip().lower()
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return tuple(labels)


def _extract_inline_refs(evidence: str, source_catalog: Mapping[str, Any]) -> tuple[str, ...]:
    refs = [ref for ref in source_catalog if ref and ref in evidence]
    return tuple(refs)


def _infer_evidence_refs(evidence: str, source_catalog: Mapping[str, Any]) -> tuple[str, ...]:
    lower = evidence.lower()
    inferred: list[str] = []
    if any(token in lower for token in ("check", "command", "pytest", "test", "exit code", "returned")) and "checks_results" in source_catalog:
        inferred.append("checks_results")
    if any(token in lower for token in ("workspace", "artifact", "file", "diff", "content")) and "workspace_diff" in source_catalog:
        inferred.append("workspace_diff")
    if any(token in lower for token in ("inspect", "inspection", "session", "job", "port", "service")):
        inspection_ref = _first_catalog_key(source_catalog, prefix="inspection.")
        if inspection_ref is not None:
            inferred.append(inspection_ref)
    if any(token in lower for token in ("tool", "action", "ran", "executed")) and "action_digest.tool_calls" in source_catalog:
        inferred.append("action_digest.tool_calls")
    if not inferred and "claim" in source_catalog:
        inferred.append("claim")
    return tuple(dict.fromkeys(inferred))


def _first_catalog_key(source_catalog: Mapping[str, Any], *, prefix: str) -> str | None:
    matches = sorted(key for key in source_catalog if key.startswith(prefix))
    if not matches:
        return None
    return matches[0]


def _classify_evidence_strength(
    *,
    requirement: str,
    verdict: str,
    evidence: str,
    evidence_refs: tuple[str, ...],
    source_catalog: Mapping[str, Any],
    report_reason_codes: list[str],
) -> dict[str, Any]:
    ref_texts = [_stringify_source(source_catalog.get(ref)) for ref in evidence_refs if ref in source_catalog]
    corpus = "\n".join(part for part in [requirement, evidence, *ref_texts] if part).lower()
    weak_reasons: list[str] = []
    strong_reasons: list[str] = []

    if "verifier_parse_failed" in report_reason_codes:
        weak_reasons.append("parse_or_schema_failure")
    if _contains_any(corpus, ("--help", "--version", "usage:", "version output")):
        weak_reasons.append("help_or_version_only")
    if _contains_any(corpus, ("command -v", "which ", "type -p", "type -a")):
        weak_reasons.append("command_presence_only")
    if _contains_any(corpus, ('python -c "import', "python3 -c \"import", "import-only", "import pass", "imports successfully")):
        weak_reasons.append("import_only")
    if _contains_any(corpus, ("schema", "shape", "count", "row count", "column count", "field count", "line count", "regex match", "matched pattern")):
        weak_reasons.append("shape_count_or_schema_only")
    if _contains_any(corpus, ("process alive", "pgrep", "pid", "port open", "listening on", "netstat", "lsof -i", "ss -l", "service alive")):
        weak_reasons.append("process_or_port_open_only")
    if _contains_any(corpus, ("startup probe", "startup-only", "first probe", "initial probe", "ready once", "boot probe", "initial readiness")):
        weak_reasons.append("startup_probe_only")
    if _contains_any(corpus, ("pythonpath", "path=", "ld_library_path", "virtual_env", "source venv", "sys.path", "export path", "export pythonpath")):
        weak_reasons.append("environment_or_path_mutation")
    if _contains_any(corpus, ("pytest -k", "::test", "::", "partial test", "selected test", "single test")):
        weak_reasons.append("partial_test_selection_only")
    if _contains_any(corpus, ("|| true", "|| :", "set +e", "ignored failure", "ignored exit code", "swallowed failure")):
        weak_reasons.append("swallowed_failure")
    if _contains_any(corpus, ("exists", "present", "contains", "found", "read-only", "read file", "ls ", "cat ", "head ", "tail ", "grep ")):
        weak_reasons.append("existence_or_read_only_observation")

    if _contains_any(corpus, ("exit code 0", "exited 0", "returned 0", "completed successfully", "passed cleanly", "no errors")):
        strong_reasons.append("clean_execution")
    if _contains_any(corpus, ("input", "output", "stdout", "stderr", "response body", "round-trip", "produced", "returned value")):
        strong_reasons.append("representative_io")
    if _contains_any(corpus, ("expected", "actual", "matches expected", "compared", "diff", "checksum", "hash", "invariant", "equal to", "validated against")):
        strong_reasons.append("independent_value_or_invariant_comparison")
    if _contains_any(corpus, ("parsed", "loaded", "decoded", "rendered", "opened and used", "deserialized", "compiled")):
        strong_reasons.append("artifact_parse_and_use")
    if _contains_any(corpus, ("curl", "http", "request", "response", "client", "connected to", "queried", "handshake")):
        strong_reasons.append("client_interaction")
    if _contains_any(corpus, ("session_read", "screen", "ui", "pane", "prompt appeared", "rendered page", "visible in session")):
        strong_reasons.append("observable_ui_or_session_behavior")
    if _contains_any(corpus, ("pytest", "cargo test", "go test", "npm test", "make test", "declared check", "provided check", "verification command")) and "environment_or_path_mutation" not in weak_reasons:
        strong_reasons.append("provided_checks_without_environment_hacks")

    service_signals = _service_monitoring_signals(corpus)
    weak_reasons.extend(service_signals["weak"])
    strong_reasons.extend(service_signals["strong"])

    weak_reasons = _dedupe(weak_reasons)
    strong_reasons = _dedupe(strong_reasons)
    dominant_weak_reasons = {
        "help_or_version_only",
        "command_presence_only",
        "import_only",
        "shape_count_or_schema_only",
        "process_or_port_open_only",
        "startup_probe_only",
        "service_probe_without_survival_window",
        "environment_or_path_mutation",
        "partial_test_selection_only",
        "swallowed_failure",
        "existence_or_read_only_observation",
    }
    lightweight_strong_reasons = {"clean_execution", "representative_io", "client_interaction"}
    service_positive_bundle = _service_positive_bundle(strong_reasons)
    instability_detected = "crash_or_replacement_detected" in strong_reasons
    if verdict in {"unsatisfied", "unverifiable"} and instability_detected:
        strength = "strong"
    elif service_positive_bundle and not instability_detected:
        strength = "strong"
    elif strong_reasons and weak_reasons and (
        set(weak_reasons) & dominant_weak_reasons
    ) and set(strong_reasons).issubset(lightweight_strong_reasons):
        strength = "weak"
    elif strong_reasons and weak_reasons:
        strength = "mixed"
    elif strong_reasons:
        strength = "strong"
    else:
        strength = "weak"

    reasons = strong_reasons + weak_reasons
    if not reasons:
        reasons = ["generic_assertion_only" if verdict == "satisfied" else "unresolved_without_decisive_evidence"]

    return {
        "strength": strength,
        "reasons": tuple(reasons),
        "confidence": _evidence_strength_confidence(strength, reasons, evidence_refs),
    }


def _classify_evidence_provenance(
    *,
    requirement: str,
    verdict: str,
    evidence: str,
    evidence_refs: tuple[str, ...],
    source_catalog: Mapping[str, Any],
    report_reason_codes: list[str],
    assessment: Mapping[str, Any],
) -> tuple[str, ...]:
    corpus = "\n".join(
        part for part in [requirement, evidence, *(_stringify_source(source_catalog.get(ref)) for ref in evidence_refs if ref in source_catalog)] if part
    ).lower()
    labels: list[str] = []

    if not evidence_refs or all(ref.startswith(("claim", "action_digest")) for ref in evidence_refs):
        labels.append("model_authored")
    if _contains_any(
        corpus,
        (
            "same method",
            "same heuristic",
            "same raw-byte",
            "same raw byte",
            "self-check",
            "self check",
            "self-authored",
            "self authored",
            "circular",
            "replayed",
            "same client",
        ),
    ):
        labels.append("same_method")
    if _contains_any(
        corpus,
        (
            "read back",
            "readback",
            "cat ",
            "head ",
            "tail ",
            "ls ",
            "exists",
            "present",
            "read-only observation",
            "read only observation",
            "file exists",
        ),
    ):
        labels.append("readback")
    if _contains_any(
        corpus,
        (
            "shape",
            "schema",
            "count",
            "row count",
            "column count",
            "field count",
            "tuple",
            "matrix",
            "dimensions",
        ),
    ):
        labels.append("shape")
    if _contains_any(
        corpus,
        (
            "command -v",
            "which ",
            "type -p",
            "type -a",
            "--help",
            "--version",
            "import ",
            "imports successfully",
            "startup probe",
            "first probe",
            "partial test",
            "selected test",
            "|| true",
        ),
    ):
        labels.append("proxy")

    strong_reasons = {str(reason) for reason in (assessment.get("reasons", ()) or ())}
    if strong_reasons & {
        "independent_value_or_invariant_comparison",
        "client_interaction",
        "provided_checks_without_environment_hacks",
        "bounded_survival_window",
        "response_or_state_validation",
        "crash_or_replacement_detected",
    }:
        labels.append("independent")

    if not labels:
        if verdict == "satisfied":
            labels.append("model_authored")
        else:
            labels.append("proxy")

    return tuple(_dedupe(labels))


def _has_clean_support(
    *,
    verdict: str,
    strength: str,
    evidence_provenance: tuple[str, ...],
    evidence_strength_reasons: tuple[str, ...],
) -> bool:
    if verdict != "satisfied":
        return False
    if strength == "strong":
        return True
    if strength == "mixed":
        return "independent" in evidence_provenance
    return False


def _stringify_source(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str, ensure_ascii=True)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _service_monitoring_signals(corpus: str) -> dict[str, tuple[str, ...]]:
    weak: list[str] = []
    strong: list[str] = []
    if not _looks_like_service_or_persistence_claim(corpus):
        return {"weak": (), "strong": ()}
    if _contains_any(corpus, ("curl", "http", "request", "response", "client", "probe")) and not _has_bounded_survival_signal(corpus) and not _has_response_or_state_validation(corpus):
        weak.append("service_probe_without_survival_window")
    if _has_bounded_survival_signal(corpus):
        strong.append("bounded_survival_window")
    if _has_correct_environment_probe(corpus):
        strong.append("correct_environment_client_probe")
    if _has_response_or_state_validation(corpus):
        strong.append("response_or_state_validation")
    if _has_crash_or_replacement_signal(corpus):
        strong.append("crash_or_replacement_detected")
    return {"weak": tuple(weak), "strong": tuple(strong)}


def _looks_like_service_or_persistence_claim(corpus: str) -> bool:
    return _contains_any(
        corpus,
        (
            "service",
            "server",
            "daemon",
            "port",
            "socket",
            "listen",
            "listening",
            "startup probe",
            "health endpoint",
            "healthcheck",
            "pid",
            "process alive",
            "remained up",
            "stayed up",
            "survived",
            "restart",
            "replacement",
            "state persisted",
            "session still alive",
        ),
    )


def _has_bounded_survival_signal(corpus: str) -> bool:
    if _contains_any(
        corpus,
        (
            "survived for",
            "remained up for",
            "stayed up for",
            "rechecked after",
            "still running after",
            "still listening after",
            "across 2 probes",
            "across two probes",
            "across 3 probes",
            "across three probes",
            "over a 30s window",
            "over a 60s window",
            "bounded window",
            "second probe",
            "third probe",
            "later probe",
        ),
    ):
        return True
    return bool(re.search(r"\b(after|over)\s+\d+\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes)\b", corpus))


def _has_correct_environment_probe(corpus: str) -> bool:
    return _contains_any(
        corpus,
        (
            "same workspace",
            "same working tree",
            "same cwd",
            "same container",
            "same environment",
            "same virtualenv",
            "same venv",
            "inside the project env",
            "inside the app env",
            "from the project env",
            "using the repo client",
            "using the project client",
            "using the app client",
            "from the workspace root",
        ),
    )


def _has_response_or_state_validation(corpus: str) -> bool:
    return _contains_any(
        corpus,
        (
            "response matched expected",
            "response body matched",
            "returned expected payload",
            "returned expected json",
            "validated response body",
            "validated service state",
            "state persisted",
            "wrote then read",
            "created then fetched",
            "same record",
            "same counter",
            "same value after restart check",
            "health response contained",
            "state endpoint matched",
        ),
    )


def _has_crash_or_replacement_signal(corpus: str) -> bool:
    return _contains_any(
        corpus,
        (
            "pid changed",
            "new pid",
            "different pid",
            "replacement pid",
            "replacement process",
            "restarted",
            "restart detected",
            "crashed",
            "died",
            "respawned",
            "replaced",
            "exit code",
            "restart count",
        ),
    )


def _service_positive_bundle(strong_reasons: list[str]) -> bool:
    strong_reason_set = set(strong_reasons)
    return "bounded_survival_window" in strong_reason_set and bool(
        strong_reason_set
        & {
            "correct_environment_client_probe",
            "response_or_state_validation",
            "client_interaction",
        }
    )


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _evidence_strength_confidence(strength: str, reasons: list[str], evidence_refs: tuple[str, ...]) -> str:
    high_signal_reasons = {
        "help_or_version_only",
        "command_presence_only",
        "import_only",
        "environment_or_path_mutation",
        "partial_test_selection_only",
        "swallowed_failure",
        "clean_execution",
        "independent_value_or_invariant_comparison",
        "artifact_parse_and_use",
        "client_interaction",
        "provided_checks_without_environment_hacks",
        "parse_or_schema_failure",
    }
    if any(reason in high_signal_reasons for reason in reasons):
        return "high"
    if strength == "mixed" or len(reasons) >= 2 or evidence_refs:
        return "medium"
    return "low"

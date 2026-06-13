"""Layer 2 Success Audit implementation for model-led completion checking."""

from __future__ import annotations

import json
from typing import Any


def _clean_hidden_refs(data: Any) -> Any:
    """Recursively removes keys containing words like expected, hidden, secret, grader, ground_truth from dictionaries."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            k_lower = k.lower()
            if any(word in k_lower for word in ("expected", "hidden", "secret", "grader", "ground_truth")):
                continue
            cleaned[k] = _clean_hidden_refs(v)
        return cleaned
    elif isinstance(data, list):
        return [_clean_hidden_refs(item) for item in data]
    return data


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def normalize_layer2_audit_state(audit_state: Any) -> dict[str, Any]:
    """Canonicalize Layer 2 audit results into a single status/verdict shape.

    The model-led parser emits verdict-shaped payloads while the static success
    contract audit emits status-shaped payloads. This helper makes both shapes
    safe to consume by downstream gates.
    """
    if not isinstance(audit_state, dict):
        return {
            "status": "not_run",
            "verdict": "unknown",
            "reason_codes": [],
            "mismatches": [],
            "missing_evidence": [],
            "repair_instruction": "",
        }

    normalized = dict(audit_state)
    status_raw = str(normalized.get("status") or "").strip().lower()
    verdict_raw = str(normalized.get("verdict") or "").strip().upper()

    def _severity(status_value: str, verdict_value: str) -> int:
        if status_value == "fail" or verdict_value == "FAIL":
            return 2
        if status_value == "unclear" or verdict_value == "UNCLEAR":
            return 1
        if status_value == "pass" or verdict_value == "PASS":
            return 0
        return -1

    severity = _severity(status_raw, verdict_raw)
    if severity == 2:
        status_raw = "fail"
        verdict_raw = "FAIL"
    elif severity == 1:
        status_raw = "unclear"
        verdict_raw = "UNCLEAR"
    elif severity == 0:
        status_raw = "pass"
        verdict_raw = "PASS"
    else:
        if not status_raw and verdict_raw in {"PASS", "FAIL", "UNCLEAR"}:
            status_raw = verdict_raw.lower()
        if not verdict_raw and status_raw in {"pass", "fail", "unclear"}:
            verdict_raw = status_raw.upper()

    normalized["status"] = status_raw or str(normalized.get("status") or "")
    normalized["verdict"] = verdict_raw or str(normalized.get("verdict") or "")
    normalized["reason_codes"] = _string_list(normalized.get("reason_codes"))
    normalized["mismatches"] = _string_list(normalized.get("mismatches"))
    normalized["missing_evidence"] = _string_list(normalized.get("missing_evidence"))
    if "confidence" in normalized and not isinstance(normalized["confidence"], str):
        normalized["confidence"] = str(normalized["confidence"])
    if "repair_instruction" in normalized and not isinstance(normalized["repair_instruction"], str):
        normalized["repair_instruction"] = str(normalized["repair_instruction"])
    return normalized


def build_layer2_audit_prompt(
    *,
    task_prompt: str,
    success_contract: dict[str, Any],
    context_pack: dict[str, Any],
    finalization_gate: dict[str, Any],
) -> list[dict[str, str]]:
    """Builds the messages prompt for the Layer 2 completion audit.

    Filters out hidden expected answers and grader variables to ensure no contamination.
    """
    cleaned_contract = _clean_hidden_refs(success_contract)
    cleaned_context = _clean_hidden_refs(context_pack)
    cleaned_gate = _clean_hidden_refs(finalization_gate)

    system_content = (
        "You are an independent Layer 2 Completion Auditor.\n"
        "Your task is to analyze the task prompt, success contract, context pack, "
        "and finalization gate status to verify if the task has been fully completed.\n"
        "You must evaluate whether the success contract criteria are satisfied and "
        "whether all required artifacts exist and are non-empty.\n\n"
        "Return your audit verdict in JSON format with the following keys:\n"
        '- "verdict": "PASS" | "FAIL" | "UNCLEAR"\n'
        '- "confidence": "low" | "medium" | "high"\n'
        '- "mismatches": list of strings detailing any mismatch between criteria and evidence\n'
        '- "missing_evidence": list of strings detailing any missing files/artifacts or evidence\n'
        '- "reason_codes": list of string reason codes for your verdict\n'
        '- "repair_instruction": string with explanation of what needs to be repaired or checked next if verdict is not PASS\n\n'
        "Do not override the deterministic verifier. If the finalization gate or verifier state "
        "shows a failure, your verdict MUST be FAIL.\n"
        "Respond ONLY with the raw JSON object. Do not include markdown code block styling."
    )

    user_content = {
        "task_prompt": task_prompt,
        "success_contract": cleaned_contract,
        "context_pack": cleaned_context,
        "finalization_gate": cleaned_gate,
    }

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(user_content, indent=2)},
    ]


def parse_layer2_audit_response(response: Any) -> dict[str, Any]:
    """Parses the response from the Layer 2 Completion Auditor model.

    Ensures standard keys are present and types are correct.
    """
    text = ""
    if isinstance(response, dict):
        text = response.get("text") or response.get("content") or ""
    elif isinstance(response, str):
        text = response
    elif hasattr(response, "text"):
        text = getattr(response, "text") or ""
    elif hasattr(response, "content"):
        text = getattr(response, "content") or ""

    text = text.strip()

    # Remove markdown codeblock formatting if present
    if text.startswith("```"):
        lines = text.splitlines()
        start_idx = 1
        if lines and ("json" in lines[0].lower() or "```" in lines[0]):
            start_idx = 1
        end_idx = len(lines)
        for i in range(len(lines) - 1, start_idx - 1, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[start_idx:end_idx]).strip()

    fallback = {
        "verdict": "UNCLEAR",
        "confidence": "low",
        "mismatches": [],
        "missing_evidence": [],
        "reason_codes": ["layer2_parse_failed"],
        "repair_instruction": "Failed to parse the auditor's JSON response.",
    }

    if not text:
        return fallback

    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return fallback

        # Normalize fields
        verdict = str(parsed.get("verdict") or "UNCLEAR").upper()
        if verdict not in {"PASS", "FAIL", "UNCLEAR"}:
            verdict = "UNCLEAR"

        confidence = str(parsed.get("confidence") or "low").lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "low"

        def _to_string_list(v: Any) -> list[str]:
            if isinstance(v, list):
                return [str(x) for x in v if x]
            return []

        return {
            "verdict": verdict,
            "confidence": confidence,
            "mismatches": _to_string_list(parsed.get("mismatches")),
            "missing_evidence": _to_string_list(parsed.get("missing_evidence")),
            "reason_codes": _to_string_list(parsed.get("reason_codes")),
            "repair_instruction": str(parsed.get("repair_instruction") or ""),
        }
    except Exception as e:
        fallback["repair_instruction"] = f"JSON parse error: {str(e)}\nRaw text: {text}"
        return fallback


def deterministic_layer2_fallback(
    *,
    finalization_gate: dict[str, Any],
    success_contract: dict[str, Any],
) -> dict[str, Any]:
    """Fallback when Layer 2 Completion Auditor is unavailable or deterministic logic applies.

    Ensures the deterministic verifier / hidden grader cannot be overridden.
    """
    _ = success_contract
    governed_status = finalization_gate.get("governed_status") or finalization_gate.get("status")
    reason_codes = list(finalization_gate.get("reason_codes") or [])

    if governed_status == "governed_pass":
        return {
            "verdict": "PASS",
            "confidence": "high",
            "mismatches": [],
            "missing_evidence": [],
            "reason_codes": ["deterministic_pass"],
            "repair_instruction": "",
        }

    mismatches = []
    if finalization_gate.get("open_obligations"):
        mismatches.append(f"Open obligations remaining: {list(finalization_gate['open_obligations'].keys())}")

    return {
        "verdict": "FAIL",
        "confidence": "high",
        "mismatches": mismatches,
        "missing_evidence": [f"Deterministic gate status: {governed_status}"],
        "reason_codes": reason_codes or ["deterministic_gate_failed"],
        "repair_instruction": f"Deterministic finalization gate failed with status '{governed_status}' and reason codes: {reason_codes}.",
    }


def should_run_layer2(
    *,
    route_manifest: dict[str, Any],
    finalization_gate: dict[str, Any],
) -> bool:
    """Determines whether the Layer 2 Success Audit should execute.

    It runs only if feature-flagged and the deterministic finalization gate passes.
    """
    flags = route_manifest.get("feature_flags", {})
    if not (flags.get("layer2_success_audit") or route_manifest.get("layer2_success_audit")):
        return False

    status = finalization_gate.get("governed_status") or finalization_gate.get("status")
    if status != "governed_pass":
        return False

    return True

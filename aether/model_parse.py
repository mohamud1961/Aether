"""Strict model-output parsing for Solver turns."""
from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any, Mapping

from .runtime_ir import ActionRequest, SolverTurn


class _ParseError(Exception):
    pass


def _model_output_error(message: str) -> Exception:
    from .model_hooks import ModelOutputError
    return ModelOutputError(message)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _ParseError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise _ParseError(f"non-standard JSON constant: {value}")


def _parse_exact_solver_object(text: str) -> dict[str, Any]:
    """Parse exactly one Solver JSON object, with one optional enclosing fence."""
    raw = str(text or "").strip()
    if not raw:
        raise _model_output_error("solver output is empty")
    if raw.startswith("```"):
        match = re.fullmatch(
            r"```(?:json)?[ \t]*\r?\n(?P<body>.*)\r?\n```",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match is None:
            raise _model_output_error(
                "solver output must contain one optional complete JSON fence and no trailing text"
            )
        raw = match.group("body").strip()
    elif "```" in raw:
        raise _model_output_error("solver output contains a partial or embedded markdown fence")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonstandard_constant,
        )
    except (_ParseError, json.JSONDecodeError) as exc:
        raise _model_output_error(f"invalid strict Solver JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise _model_output_error("Solver output must be exactly one JSON object")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    *,
    required: set[str],
    allowed: set[str],
    location: str,
) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - allowed)
    if missing:
        raise _model_output_error(f"{location} missing required fields: {', '.join(missing)}")
    if unknown:
        raise _model_output_error(f"{location} has unsupported fields: {', '.join(unknown)}")


def _strict_string(value: Any, location: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise _model_output_error(f"{location} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        raise _model_output_error(f"{location} must be non-empty")
    return result


def _strict_string_array(value: Any, location: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _model_output_error(f"{location} must be an array of strings")
    rows: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise _model_output_error(f"{location}[{index}] must be a string")
        rows.append(item)
    return tuple(rows)


_FENCE_RE = re.compile(r"```(?:json)?\s*\n?", re.IGNORECASE)


def _extract_json_object(text: str) -> str:
    """First balanced ``{...}`` from *text*; tolerates fences and prose."""
    cleaned = _FENCE_RE.sub("", text)
    start = cleaned.find("{")
    if start == -1:
        raise _model_output_error("no JSON object found in model output")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : i + 1]
    raise _model_output_error("unbalanced braces in model output")



def _parse_pcr_v0_turn(text: str) -> SolverTurn:
    """Parse the minimal persistent-Primary-Agent decision contract."""
    from .pcr_provider_protocol import (
        PCRProviderProtocolError,
        validate_pcr_inner_turn,
    )

    data = _parse_exact_solver_object(text)
    try:
        data = validate_pcr_inner_turn(data)
    except PCRProviderProtocolError as exc:
        raise _model_output_error(str(exc)) from exc

    kind = str(data["kind"])
    if kind == "act":
        raw_action = data["action"]
        action_kind = str(raw_action["kind"])
        # Native PCR production deliberately removes capability_id from the
        # model-authored schema.  Restore only an internal mechanical owner for
        # execution custody; no semantic choice is delegated to the model.
        capability_id = str(raw_action.get("capability_id", "")).strip()
        if not capability_id:
            capability_id = {
                "read_file": "filesystem",
                "read_file_page": "kernel",
                "read_output": "kernel",
                "grep_output": "kernel",
                "write_file": "filesystem",
                "run_command": "shell",
                "start_terminal_session": "persistent_terminal",
                "terminal_send": "persistent_terminal",
                "terminal_read": "persistent_terminal",
                "terminal_wait": "persistent_terminal",
                "terminal_interrupt": "persistent_terminal",
                "terminal_close": "persistent_terminal",
                "bootstrap_acquire": "shell",
                "launch_process": "managed_process",
                "start_job": "managed_process",
                "probe_job": "managed_process",
                "probe_service": "service_probe",
                "stop_process": "managed_process",
                "inspect_artifact": "artifact_inspection",
                "computer_action": "computer_control",
                "report_blocker": "kernel",
                "query_history": "kernel",
                "query_artifact_history": "kernel",
                "inspect_diff": "kernel",
            }.get(action_kind, "")
        if not capability_id:
            raise _model_output_error(
                f"no mechanical capability owner for PCR action {action_kind!r}"
            )
        arguments = dict(raw_action["arguments"])
        identity_payload = json.dumps(
            {
                "kind": action_kind,
                "capability_id": capability_id,
                "arguments": arguments,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        action_id = "pcr-" + sha256(identity_payload.encode("utf-8")).hexdigest()[:16]
        return SolverTurn(
            kind="act",
            summary=f"Primary Agent requested {action_kind}",
            actions=(ActionRequest(
                action_id=action_id,
                kind=action_kind,
                capability_id=capability_id,
                arguments=arguments,
                intent="",
                expected_observation="",
                if_fail_next="",
            ),),
        )

    claim = str(data["claim"])
    evidence_refs = tuple(str(item) for item in data["evidence_refs"])
    internal_kind = {
        "finish_intent": "finish_intent",
        "finish": "finish_outcome",
        "submit": "submit_outcome",  # legacy trace/test compatibility
    }[kind]
    return SolverTurn(
        kind=internal_kind,
        summary=claim,
        claim=claim,
        evidence_refs=evidence_refs,
    )


def parse_solver_turn(text: str) -> SolverTurn:
    """Parse exactly one turn under Aether's sole implicit PCR contract."""
    return _parse_pcr_v0_turn(text)

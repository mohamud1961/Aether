"""Strict model-output parsing for Solver turns."""
from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any, Mapping

from .edit_file_tool import EDIT_FILE_ACTION_SCHEMA_ENTRY
from .persistent_capabilities import KERNEL_OWNED_ACTION_KINDS
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



def _parse_persistent_v0_turn(
    text: str,
    *,
    action_schema: Any = (),
    capability_ids: Any = (),
) -> SolverTurn:
    """Parse the minimal persistent-Primary-Agent decision contract."""
    from .persistent_provider_protocol import (
        PCRProviderProtocolError,
        validate_persistent_inner_turn,
    )

    # Zoom is a context-tree capability, not a general PERSISTENT action.  Both the
    # compiled action contract and the selected mechanical owner must be
    # present; either one alone leaves the control grammar unchanged.
    allow_m_tree_zoom = (
        ("zoom", ("id", "n")) in tuple(action_schema or ())
        and "context_tree" in {str(item) for item in (capability_ids or ())}
    )
    # edit_context is the context-file arm's only addition; same two-key rule.
    allow_edit_context = (
        ("edit_context", ()) in tuple(action_schema or ())
        and "context_file" in {str(item) for item in (capability_ids or ())}
    )
    # edit_file is the opt-in static_kernel_edit_v1 surface's only addition.
    allow_edit_file = EDIT_FILE_ACTION_SCHEMA_ENTRY in tuple(action_schema or ())
    data = _parse_exact_solver_object(text)
    try:
        data = validate_persistent_inner_turn(
            data, include_m_tree_zoom=allow_m_tree_zoom,
            include_edit_context=allow_edit_context,
            include_edit_file=allow_edit_file,
        )
    except PCRProviderProtocolError as exc:
        raise _model_output_error(str(exc)) from exc

    kind = str(data["kind"])
    if kind == "act":
        raw_action = data["action"]
        action_kind = str(raw_action["kind"])
        # Native PERSISTENT production deliberately removes capability_id from the
        # model-authored schema.  Restore only an internal mechanical owner for
        # execution custody; no semantic choice is delegated to the model.
        capability_id = str(raw_action.get("capability_id", "")).strip()
        if not capability_id:
            # Native PERSISTENT production deliberately removes capability_id from the
            # model-authored schema.  Restore only an internal mechanical owner
            # for execution custody; no semantic choice is delegated to the
            # model. Kernel-owned actions are derived from the same public set
            # used by persistent_capabilities so parse/ownership cannot drift.
            capability_id = {
                "read_file": "filesystem",
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
                "job_output": "managed_process",
                "job_wait": "managed_process",
                "job_stop": "managed_process",
                "probe_service": "service_probe",
                "stop_process": "managed_process",
                "inspect_artifact": "artifact_inspection",
                "computer_action": "computer_control",
            }
            for kernel_kind in KERNEL_OWNED_ACTION_KINDS:
                capability_id.setdefault(kernel_kind, "kernel")
            if allow_m_tree_zoom:
                capability_id["zoom"] = "context_tree"
            if allow_edit_context:
                capability_id["edit_context"] = "context_file"
            if allow_edit_file:
                capability_id["edit_file"] = "filesystem"
            capability_id = capability_id.get(action_kind, "")
        if not capability_id:
            raise _model_output_error(
                f"no mechanical capability owner for PERSISTENT action {action_kind!r}"
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
        action_id = "persistent-" + sha256(identity_payload.encode("utf-8")).hexdigest()[:16]
        raw_action = data["action"]
        return SolverTurn(
            kind="act",
            summary=str(data.get("summary") or f"Primary Agent requested {action_kind}"),
            evidence_gap=str(data.get("evidence_gap") or ""),
            actions=(ActionRequest(
                action_id=action_id,
                kind=action_kind,
                capability_id=capability_id,
                arguments=arguments,
                intent=str(raw_action.get("intent") or ""),
                expected_observation=str(raw_action.get("expected_observation") or ""),
                if_fail_next=str(raw_action.get("if_fail_next") or ""),
            ),),
        )

    claim = str(data["claim"])
    evidence_refs = tuple(str(item) for item in data["evidence_refs"])
    finding_dispositions = tuple(
        dict(item) for item in data.get("finding_dispositions", ())
        if isinstance(item, dict)
    )
    finish_metadata = (
        dict(data["finish_metadata"])
        if isinstance(data.get("finish_metadata"), dict) else None
    )
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
        finding_dispositions=finding_dispositions,
        finish_metadata=finish_metadata,
    )


def parse_solver_turn(
    text: str,
    *,
    action_schema: Any = (),
    capability_ids: Any = (),
) -> SolverTurn:
    """Parse exactly one turn under Aether's sole implicit PERSISTENT contract."""
    return _parse_persistent_v0_turn(
        text, action_schema=action_schema, capability_ids=capability_ids,
    )

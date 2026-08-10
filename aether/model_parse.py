"""Model-output parsing for architect configs and solver turns.

Extracted from model_hooks.py for the 500-LOC cap.  Tolerant where the
payload implies intent (fences, prose wrap, missing act label), hard-failing
where inference would fabricate meaning (submission is never inferred).
"""
from __future__ import annotations

import json
import re
from hashlib import sha256
from dataclasses import fields as dc_fields
from typing import Any, Mapping

from .runtime_ir import (
    ActionRequest,
    BootstrapPolicy,
    CompletionPolicy,
    ContextPolicy,
    HelperToolPolicy,
    ProcessPolicy,
    ReconfigurePolicy,
    RefusalPolicy,
    RuntimeConfigIR,
    SolverTurn,
    WorkflowPolicy,
)


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



def _accepted_fields(cls: type) -> set[str]:
    return {f.name for f in dc_fields(cls)}


def _coerce_tuple(value: Any) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, str):
        return (value,)
    return ()


def _build_frozen(cls: type, raw: Mapping[str, Any]) -> Any:
    accepted = _accepted_fields(cls)
    kwargs: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in accepted:
            continue
        field_obj = next(f for f in dc_fields(cls) if f.name == key)
        if field_obj.type in ("tuple[str, ...]", "tuple[str, ...] | None"):
            value = _coerce_tuple(value)
        kwargs[key] = value
    return cls(**kwargs)

_POLICY_MAP: dict[str, type] = {
    "context_policy": ContextPolicy,
    "process_policy": ProcessPolicy,
    "helper_tool_policy": HelperToolPolicy,
    "bootstrap_policy": BootstrapPolicy,
    "completion_policy": CompletionPolicy,
    "refusal_policy": RefusalPolicy,
    "reconfigure_policy": ReconfigurePolicy,
    "workflow_policy": WorkflowPolicy,
}


def parse_runtime_config_ir(text: str, *, capability_index: Any = None) -> RuntimeConfigIR:
    """Parse raw model text into a ``RuntimeConfigIR``."""
    raw_json = _extract_json_object(text)
    try:
        data: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise _model_output_error(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise _model_output_error("expected a JSON object at top level")

    # Required scalars
    if "architect_summary" not in data:
        raise _model_output_error("missing required field: architect_summary")
    if "solver_identity_prompt" not in data:
        raise _model_output_error("missing required field: solver_identity_prompt")

    accepted = _accepted_fields(RuntimeConfigIR)
    kwargs: dict[str, Any] = {}

    for key, value in data.items():
        if key not in accepted:
            continue
        # Policy sub-objects
        if key in _POLICY_MAP and isinstance(value, dict):
            kwargs[key] = _build_frozen(_POLICY_MAP[key], value)
            continue
        # Tuple fields
        field_obj = next((f for f in dc_fields(RuntimeConfigIR) if f.name == key), None)
        if field_obj is not None and "tuple" in str(field_obj.type):
            kwargs[key] = _coerce_tuple(value)
            continue
        kwargs[key] = value

    # selected_capabilities must be a tuple of strings
    if "selected_capabilities" in kwargs:
        kwargs["selected_capabilities"] = tuple(
            str(cap_id) for cap_id in kwargs["selected_capabilities"]
        )
    else:
        kwargs["selected_capabilities"] = ()

    return RuntimeConfigIR(**kwargs)


def _parse_solver_v1_turn(text: str) -> SolverTurn:
    """Parse one exact, fully specified Solver protocol state."""
    data = _parse_exact_solver_object(text)
    if "kind" not in data:
        raise _model_output_error("solver turn missing required fields: kind")
    kind = _strict_string(data["kind"], "solver.kind")
    common = {"kind", "summary", "requested_check_ids", "claimed_artifacts", "evidence_gap"}
    if kind == "act":
        _require_exact_keys(
            data,
            required=common | {"actions"},
            allowed=common | {"actions"},
            location="solver act turn",
        )
    elif kind == "submit_outcome":
        _require_exact_keys(
            data,
            required=common,
            allowed=common,
            location="solver submit_outcome turn",
        )
    else:
        raise _model_output_error(f"unknown Solver turn kind: {kind}")

    summary = _strict_string(data["summary"], "solver.summary")
    requested_check_ids = _strict_string_array(
        data["requested_check_ids"], "solver.requested_check_ids"
    )
    claimed_artifacts = _strict_string_array(
        data["claimed_artifacts"], "solver.claimed_artifacts"
    )
    evidence_gap = _strict_string(
        data["evidence_gap"],
        "solver.evidence_gap",
        allow_empty=(kind == "submit_outcome"),
    )

    actions: list[ActionRequest] = []
    if kind == "act":
        raw_actions = data["actions"]
        if not isinstance(raw_actions, list) or len(raw_actions) != 1:
            raise _model_output_error("solver act turn actions must contain exactly one action")
        raw_action = raw_actions[0]
        if not isinstance(raw_action, dict):
            raise _model_output_error("solver.actions[0] must be an object")
        action_fields = {
            "action_id", "kind", "capability_id", "arguments",
            "intent", "expected_observation", "if_fail_next",
        }
        _require_exact_keys(
            raw_action,
            required=action_fields,
            allowed=action_fields,
            location="solver.actions[0]",
        )
        arguments = raw_action["arguments"]
        if not isinstance(arguments, dict):
            raise _model_output_error("solver.actions[0].arguments must be an object")
        action_kind = _strict_string(raw_action["kind"], "solver.actions[0].kind")
        if action_kind == "observe_batch":
            raise _model_output_error(
                "observe_batch is not part of Solver Closed-Loop Control V1; choose one action"
            )
        actions.append(ActionRequest(
            action_id=_strict_string(raw_action["action_id"], "solver.actions[0].action_id"),
            kind=action_kind,
            capability_id=_strict_string(
                raw_action["capability_id"], "solver.actions[0].capability_id"
            ),
            arguments=dict(arguments),
            intent=_strict_string(raw_action["intent"], "solver.actions[0].intent"),
            expected_observation=_strict_string(
                raw_action["expected_observation"],
                "solver.actions[0].expected_observation",
            ),
            if_fail_next=_strict_string(
                raw_action["if_fail_next"], "solver.actions[0].if_fail_next"
            ),
        ))

    return SolverTurn(
        kind=kind,
        summary=summary,
        actions=tuple(actions),
        requested_check_ids=requested_check_ids,
        claimed_artifacts=claimed_artifacts,
        evidence_gap=evidence_gap,
    )


def _parse_persistent_v0_turn(text: str) -> SolverTurn:
    """Parse the minimal persistent-Primary-Agent decision contract."""
    from .persistent_provider_protocol import (
        PCRProviderProtocolError,
        validate_persistent_inner_turn,
    )

    data = _parse_exact_solver_object(text)
    try:
        data = validate_persistent_inner_turn(data)
    except PCRProviderProtocolError as exc:
        raise _model_output_error(str(exc)) from exc

    kind = str(data["kind"])
    if kind == "act":
        raw_action = data["action"]
        action_kind = str(raw_action["kind"])
        capability_id = str(raw_action["capability_id"])
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
        return SolverTurn(
            kind="act",
            summary=f"Primary Agent requested {action_kind}",
            working_state=dict(data.get("working_state", {}) or {}),
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
    return SolverTurn(
        kind="submit_outcome",
        summary=claim,
        claim=claim,
        evidence_refs=evidence_refs,
        working_state=dict(data.get("working_state", {}) or {}),
    )


def parse_solver_turn(text: str, *, protocol: str = "solver_v1") -> SolverTurn:
    """Parse exactly one turn under the selected provider/runtime contract."""
    if protocol == "persistent_v0":
        return _parse_persistent_v0_turn(text)
    if protocol == "solver_v1":
        return _parse_solver_v1_turn(text)
    raise _model_output_error(f"unknown solver turn protocol: {protocol}")

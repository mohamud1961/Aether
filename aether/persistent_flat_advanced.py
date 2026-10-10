"""Flat provider shape for the helper/capture/extension run-command tool.

Chat-compatible providers sometimes serialize a nested ``arguments`` object as
a JSON string, and that extra string layer is easily corrupted by shell
quoting.  The flat shape removes the wrapper: every field sits at the top level
and the server canonicalizes it into the same ``run_command`` action the nested
form produces.  Canonical PERSISTENT validation remains the only authority on which
field combinations are legal.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

PROVIDER_TOOL_SHAPE_NESTED = "nested_v1"
PROVIDER_TOOL_SHAPE_FLAT = "flat_v1"
PROVIDER_TOOL_SHAPES = frozenset({PROVIDER_TOOL_SHAPE_NESTED, PROVIDER_TOOL_SHAPE_FLAT})

FLAT_ACTION_FIELDS = (
    "command", "timeout_s", "helper_path", "helper_mode", "source_path",
    "output_path", "capture_surface", "extension_server", "extension_operation",
    "extension_tool", "extension_arguments_json",
)
COMMITMENT_FIELDS = (
    "summary", "evidence_gap", "intent", "expected_observation", "if_fail_next",
)
FLAT_SHAPE_EXAMPLES = {
    "run_command": '{"command": "<shell command>", "timeout_s": 60}',
    "run_command_advanced": (
        '{"command": "<shell command>", "timeout_s": 60, "helper_path": "<path>", '
        '"helper_mode": "smoke_test"}'
    ),
}


def flat_advanced_parameters(*, commitment_v1: bool) -> dict[str, Any]:
    """Flat object schema; all optional but ``command`` (+ commitment fields)."""
    nonempty = {"type": "string", "pattern": r"\S"}
    properties: dict[str, Any] = {
        "command": dict(nonempty),
        "timeout_s": {"type": "integer", "minimum": 1},
        "helper_path": dict(nonempty),
        "helper_mode": {"type": "string", "enum": ["smoke_test", "execute"]},
        "source_path": dict(nonempty),
        "output_path": dict(nonempty),
        "capture_surface": dict(nonempty),
        "extension_server": dict(nonempty),
        "extension_operation": {"type": "string", "enum": ["tools_list", "tools_call"]},
        "extension_tool": dict(nonempty),
        "extension_arguments_json": {"type": "string"},
    }
    required = ["command"]
    if commitment_v1:
        commitment = {
            "summary": "Concise current subgoal; not chain-of-thought.",
            "evidence_gap": "The unresolved factual uncertainty this action addresses.",
            "intent": "Why this action is relevant to that evidence gap.",
            "expected_observation": "A concise falsifiable observation expected from the action.",
            "if_fail_next": "A concise pivot if the action fails or contradicts the expectation.",
        }
        properties = {
            **{k: {**nonempty, "description": v} for k, v in commitment.items()},
            **properties,
        }
        required = [*COMMITMENT_FIELDS, "command"]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


FLAT_ADVANCED_DESCRIPTION = (
    "Execute a run_command variant that requires helper/path/capture/extension metadata. "
    "Provide command and the other fields directly at the top level; do not wrap them in an "
    "arguments field. Put all shell quoting inside the command string value. "
    "Ordinary shell verification should use run_command instead."
)


def is_flat_advanced_payload(payload: Mapping[str, Any]) -> bool:
    keys = set(payload)
    return (
        "arguments" not in keys
        and "command" in keys
        and keys <= {*FLAT_ACTION_FIELDS, *COMMITMENT_FIELDS}
        and (not (keys & set(COMMITMENT_FIELDS)) or set(COMMITMENT_FIELDS) <= keys)
    )


def arguments_string_error_detail(tool_name: str) -> str:
    """Model-visible detail for an ``arguments`` string that is not one JSON object."""
    example = FLAT_SHAPE_EXAMPLES.get(tool_name)
    if example is not None:
        shape = (
            f"Send the fields directly as one flat JSON object, for example {example}, "
            "with no arguments wrapper."
        )
    else:
        shape = (
            'Send arguments as a JSON object (not a string), for example {"arguments": {...}}.'
        )
    return (
        'the "arguments" field was a string that does not decode to exactly one JSON object. '
        f"{shape} Shell quoting and escaping belong inside the command string value, "
        "not in an extra serialized layer."
    )


def flat_field_error_detail(payload: Mapping[str, Any], canonical_error: str) -> str:
    """Precise detail for a flat payload rejected by canonical validation."""
    present = sorted(k for k in payload if k in FLAT_ACTION_FIELDS)
    unknown = sorted(k for k in payload if k not in {*FLAT_ACTION_FIELDS, *COMMITMENT_FIELDS})
    return (
        f"fields_present={json.dumps(present)} unknown_fields={json.dumps(unknown)}; "
        "legal combinations: command[+timeout_s]; command+helper_path+helper_mode[+timeout_s]; "
        "command+source_path+output_path[+timeout_s]; command+capture_surface+output_path[+timeout_s]; "
        "command=environment_extension+extension_server+extension_operation=tools_list[+timeout_s]; "
        "command=environment_extension+extension_server+extension_operation=tools_call+"
        f"extension_tool+extension_arguments_json[+timeout_s]. canonical_error={canonical_error}"
    )


def decode_error_note(tool_name: str, raw_arguments: str) -> str:
    """Locate the JSON decode failure of a rejected call, or '' if none applies."""
    def locate(text: str, label: str) -> str:
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            lo, hi = max(0, exc.pos - 24), min(len(text), exc.pos + 24)
            return (
                f"JSON decode error in {label}: {exc.msg} at line {exc.lineno} column "
                f"{exc.colno} (char {exc.pos}), near {text[lo:hi]!r}."
            )
        return ""
    outer = locate(raw_arguments, "the tool arguments")
    if outer:
        return outer
    try:
        payload = json.loads(raw_arguments)
    except ValueError:
        return ""
    inner = payload.get("arguments") if isinstance(payload, dict) else None
    return locate(inner, 'the "arguments" string') if isinstance(inner, str) else ""

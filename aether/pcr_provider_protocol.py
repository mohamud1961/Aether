"""Strict provider and deterministic contract for the PCR V0 Primary Agent.

One action-specific argument authority generates the provider JSON schema, the
deterministic validator, and the model-visible action catalogue. This prevents
both hidden post-schema invariants and accidental loss of optional capability
arguments such as paging, command timeouts, filtered retrieval, and
manager-specific bootstrap inputs.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .runtime_ir import ACTION_SCHEMA, FIXED_KERNEL_TOOL_SURFACE

PCR_PRIMARY_TURN_PROTOCOL = "pcr_v0"
PCR_PRIMARY_STRUCTURED_OUTPUT_NAME = "aether_pcr_v0_primary_turn"
def pcr_primary_turn_response_instruction() -> str:
    return (
        "Return exactly one strict provider object with the sole key turn. turn is "
        "either one act containing exactly one action, one finish_intent requesting the "
        "single advisory independent review for the current candidate generation, or one "
        "finish making the final semantic completion decision. Both completion turns require "
        "supporting evidence references. finish actually finishes and never implicitly starts "
        "review. Do not use completion turns to report known incompleteness. Do not emit action "
        "IDs, plans, predictions, reflections, "
        "hidden reasoning, future turns, working_state, markdown, or prose."
    )


PCR_PRIMARY_TURN_RESPONSE_INSTRUCTION = pcr_primary_turn_response_instruction()

PCR_PRIMARY_ACTION_SCHEMA = tuple(
    (kind, arguments)
    for kind, arguments in ACTION_SCHEMA
    if kind in FIXED_KERNEL_TOOL_SURFACE
)

_NONEMPTY_STRING: dict[str, Any] = {"type": "string", "pattern": r"\S"}
_STRING: dict[str, Any] = {"type": "string"}
_NONNEGATIVE_INTEGER: dict[str, Any] = {"type": "integer", "minimum": 0}
_POSITIVE_INTEGER: dict[str, Any] = {"type": "integer", "minimum": 1}
_NONNEGATIVE_NUMBER: dict[str, Any] = {"type": "number", "minimum": 0}
_BOOLEAN: dict[str, Any] = {"type": "boolean"}
_STRING_ARRAY: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
_COMPUTER_POINT: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["x", "y"],
    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
}
_INSPECT_ARTIFACT_PATH: dict[str, Any] = {
    "type": "string",
    "pattern": r"\S",
    "description": "Path of the artifact to inspect.",
}
_INSPECT_ARTIFACT_MODE: dict[str, Any] = {
    "type": "string",
    "pattern": r"\S",
    "description": (
        "Inspection mode. For supported image artifacts, a semantic image mode can "
        "stage the exact artifact bytes for same-Primary native image perception; "
        "the resulting perception is an observation, not automatic proof."
    ),
}

_EVIDENCE_REF_ARRAY: dict[str, Any] = {
    "type": "array",
    "maxItems": 8,
    "uniqueItems": True,
    "items": {"type": "string", "pattern": r"^evidence:[0-9a-f]{16}$"},
}

def _enum(*values: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


def _object(properties: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Create one exact argument-object variant.

    Every listed property is required in that variant. Optional capability
    arguments are represented by a second exact variant, not a hidden runtime
    allowance or nullable boilerplate.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": {key: dict(value) for key, value in properties.items()},
    }


def _computer_action_schema() -> dict[str, Any]:
    keys = {"type": "array", "items": {"type": "string"}}
    xy = {"x": {"type": "integer"}, "y": {"type": "integer"}}
    variants = [
        _object({"type": _enum("screenshot")}),
        _object({"type": _enum("wait")}),
        _object({"type": _enum("type"), "text": _STRING}),
        _object({"type": _enum("keypress"), "keys": keys}),
        _object({"type": _enum("click"), "button": _enum("left", "right", "wheel", "back", "forward"), **xy}),
        _object({"type": _enum("click"), "button": _enum("left", "right", "wheel", "back", "forward"), **xy, "keys": keys}),
        _object({"type": _enum("double_click"), **xy}),
        _object({"type": _enum("double_click"), **xy, "keys": keys}),
        _object({"type": _enum("move"), **xy}),
        _object({"type": _enum("move"), **xy, "keys": keys}),
        _object({"type": _enum("scroll"), **xy, "scroll_x": {"type": "integer"}, "scroll_y": {"type": "integer"}}),
        _object({"type": _enum("scroll"), **xy, "scroll_x": {"type": "integer"}, "scroll_y": {"type": "integer"}, "keys": keys}),
        _object({"type": _enum("drag"), "path": {"type": "array", "minItems": 1, "items": _COMPUTER_POINT}}),
        _object({"type": _enum("drag"), "path": {"type": "array", "minItems": 1, "items": _COMPUTER_POINT}, "keys": keys}),
    ]
    return {"anyOf": variants}


_COMPUTER_ACTION_SCHEMA = _computer_action_schema()


# Exact accepted argument variants for every Primary-Agent-visible action.
# Kernel-internal experiment administration is intentionally absent.
PCR_ACTION_ARGUMENT_VARIANTS: dict[str, tuple[dict[str, Any], ...]] = {
    "read_file": (_object({"path": _NONEMPTY_STRING}),),
    "read_file_page": (
        _object({"path": _NONEMPTY_STRING}),
        _object({
            "path": _NONEMPTY_STRING,
            "offset": _NONNEGATIVE_INTEGER,
            "span": _POSITIVE_INTEGER,
        }),
    ),
    "read_output": (
        _object({"handle": _NONEMPTY_STRING}),
        _object({
            "handle": _NONEMPTY_STRING,
            "offset": _NONNEGATIVE_INTEGER,
            "span": _POSITIVE_INTEGER,
        }),
    ),
    "grep_output": (_object({
        "handle": _NONEMPTY_STRING,
        "pattern": _STRING,
    }),),
    "write_file": (_object({
        "path": _NONEMPTY_STRING,
        "content": _STRING,
    }),),
    "run_command": (
        _object({"command": _NONEMPTY_STRING}),
        _object({
            "command": _NONEMPTY_STRING,
            "timeout_s": _POSITIVE_INTEGER,
        }),
        _object({
            "command": _NONEMPTY_STRING,
            "helper_path": _NONEMPTY_STRING,
            "helper_mode": _enum("smoke_test", "execute"),
        }),
        _object({
            "command": _NONEMPTY_STRING,
            "timeout_s": _POSITIVE_INTEGER,
            "helper_path": _NONEMPTY_STRING,
            "helper_mode": _enum("smoke_test", "execute"),
        }),
        _object({
            "command": _NONEMPTY_STRING,
            "source_path": _NONEMPTY_STRING,
            "output_path": _NONEMPTY_STRING,
        }),
        _object({
            "command": _NONEMPTY_STRING,
            "source_path": _NONEMPTY_STRING,
            "output_path": _NONEMPTY_STRING,
            "timeout_s": _POSITIVE_INTEGER,
        }),
        _object({
            "command": _NONEMPTY_STRING,
            "capture_surface": _NONEMPTY_STRING,
            "output_path": _NONEMPTY_STRING,
        }),
        _object({
            "command": _NONEMPTY_STRING,
            "capture_surface": _NONEMPTY_STRING,
            "output_path": _NONEMPTY_STRING,
            "timeout_s": _POSITIVE_INTEGER,
        }),
        _object({
            "command": _enum("environment_extension"),
            "extension_server": _NONEMPTY_STRING,
            "extension_operation": _enum("tools_list"),
        }),
        _object({
            "command": _enum("environment_extension"),
            "extension_server": _NONEMPTY_STRING,
            "extension_operation": _enum("tools_list"),
            "timeout_s": _POSITIVE_INTEGER,
        }),
        _object({
            "command": _enum("environment_extension"),
            "extension_server": _NONEMPTY_STRING,
            "extension_operation": _enum("tools_call"),
            "extension_tool": _NONEMPTY_STRING,
            "extension_arguments_json": _STRING,
        }),
        _object({
            "command": _enum("environment_extension"),
            "extension_server": _NONEMPTY_STRING,
            "extension_operation": _enum("tools_call"),
            "extension_tool": _NONEMPTY_STRING,
            "extension_arguments_json": _STRING,
            "timeout_s": _POSITIVE_INTEGER,
        }),
    ),
    "start_terminal_session": (
        _object({
            "session_name": _NONEMPTY_STRING,
            "command": _NONEMPTY_STRING,
        }),
        _object({
            "session_name": _NONEMPTY_STRING,
            "command": _NONEMPTY_STRING,
            "cwd": _NONEMPTY_STRING,
        }),
    ),
    "terminal_send": (
        _object({
            "session_id": _NONEMPTY_STRING,
            "data": _STRING,
        }),
        _object({
            "session_id": _NONEMPTY_STRING,
            "data": _STRING,
            "append_newline": _BOOLEAN,
        }),
    ),
    "terminal_read": (
        _object({"session_id": _NONEMPTY_STRING}),
        _object({
            "session_id": _NONEMPTY_STRING,
            "max_bytes": _POSITIVE_INTEGER,
        }),
        _object({
            "session_id": _NONEMPTY_STRING,
            "wait_ms": _NONNEGATIVE_INTEGER,
        }),
        _object({
            "session_id": _NONEMPTY_STRING,
            "max_bytes": _POSITIVE_INTEGER,
            "wait_ms": _NONNEGATIVE_INTEGER,
        }),
    ),
    "terminal_wait": (
        _object({"session_id": _NONEMPTY_STRING}),
        _object({
            "session_id": _NONEMPTY_STRING,
            "timeout_s": _NONNEGATIVE_NUMBER,
        }),
    ),
    "terminal_interrupt": (_object({"session_id": _NONEMPTY_STRING}),),
    "terminal_close": (_object({"session_id": _NONEMPTY_STRING}),),
    "bootstrap_acquire": (
        _object({
            "manager": _enum("apt", "pip", "uv", "npm", "cargo", "opam", "hf"),
            "target": _NONEMPTY_STRING,
        }),
        _object({
            "manager": _enum("git"),
            "source": _NONEMPTY_STRING,
        }),
        _object({
            "manager": _enum("wget", "curl"),
            "source": _NONEMPTY_STRING,
        }),
        _object({
            "manager": _enum("wget", "curl"),
            "source": _NONEMPTY_STRING,
            "output": _NONEMPTY_STRING,
        }),
    ),
    "launch_process": (_object({
        "service_name": _NONEMPTY_STRING,
        "command": _NONEMPTY_STRING,
    }),),
    "start_job": (_object({
        "service_name": _NONEMPTY_STRING,
        "command": _NONEMPTY_STRING,
    }),),
    "probe_job": (_object({"target": _NONEMPTY_STRING}),),
    "probe_service": (_object({"target": _NONEMPTY_STRING}),),
    "stop_process": (_object({"target": _NONEMPTY_STRING}),),
    "inspect_artifact": (_object({
        "path": _INSPECT_ARTIFACT_PATH,
        "mode": _INSPECT_ARTIFACT_MODE,
    }),),
    "computer_action": (_object({
        "actions": {"type": "array", "minItems": 1, "items": _COMPUTER_ACTION_SCHEMA},
    }),),
    "query_history": (
        _object({"query": _STRING}),
        _object({
            "query": _STRING,
            "offset": _NONNEGATIVE_INTEGER,
            "limit": _POSITIVE_INTEGER,
        }),
    ),
    "query_artifact_history": (_object({"path": _NONEMPTY_STRING}),),
    "inspect_diff": (_object({"path": _NONEMPTY_STRING}),),
    "report_blocker": (
        _object({
            "blocker": _NONEMPTY_STRING,
            "evidence": _NONEMPTY_STRING,
        }),
        _object({
            "blocker": _NONEMPTY_STRING,
            "evidence": _NONEMPTY_STRING,
            "harness_constraint": _NONEMPTY_STRING,
        }),
        _object({
            "blocker": _NONEMPTY_STRING,
            "evidence": _NONEMPTY_STRING,
            "possible_missing_capability": _NONEMPTY_STRING,
        }),
        _object({
            "blocker": _NONEMPTY_STRING,
            "evidence": _NONEMPTY_STRING,
            "harness_constraint": _NONEMPTY_STRING,
            "possible_missing_capability": _NONEMPTY_STRING,
        }),
    ),
}

_EXPECTED_ACTIONS = {kind for kind, _arguments in PCR_PRIMARY_ACTION_SCHEMA}
if set(PCR_ACTION_ARGUMENT_VARIANTS) != _EXPECTED_ACTIONS:
    missing = sorted(_EXPECTED_ACTIONS - set(PCR_ACTION_ARGUMENT_VARIANTS))
    extra = sorted(set(PCR_ACTION_ARGUMENT_VARIANTS) - _EXPECTED_ACTIONS)
    raise RuntimeError(
        f"PCR action argument authority drifted: missing={missing}, extra={extra}"
    )


class PCRProviderProtocolError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(self.code if not self.detail else f"{self.code}: {self.detail}")


def _act_variant(kind: str, arguments_schema: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "action"],
        "properties": {
            "kind": {"type": "string", "enum": ["act"]},
            "action": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "arguments"],
                "properties": {
                    "kind": {"type": "string", "enum": [kind]},
                    "arguments": dict(arguments_schema),
                },
            },
        },
    }


def pcr_primary_turn_schema() -> dict[str, Any]:
    """Return the one exact production PCR turn schema."""
    act_variants = [
        _act_variant(kind, arguments_schema)
        for kind, variants in PCR_ACTION_ARGUMENT_VARIANTS.items()
        for arguments_schema in variants
    ]
    def completion_variant(kind: str) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "claim", "evidence_refs"],
            "properties": {
                "kind": {"type": "string", "enum": [kind]},
                "claim": dict(_NONEMPTY_STRING),
                "evidence_refs": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_NONEMPTY_STRING),
                },
            },
        }
    # `submit` remains parser-compatible for old stored traces/test doubles, but
    # production native tools expose only finish_intent and finish.
    completions = [
        completion_variant("finish_intent"),
        completion_variant("finish"),
        completion_variant("submit"),
    ]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["turn"],
        "properties": {"turn": {"anyOf": [*act_variants, *completions]}},
    }


PCR_PRIMARY_TURN_SCHEMA = pcr_primary_turn_schema()


def _pcr_provider_schema_node(value: Any) -> Any:
    """Project canonical PCR schema onto provider-supported JSON Schema keywords."""
    if isinstance(value, list):
        return [_pcr_provider_schema_node(item) for item in value]
    if not isinstance(value, Mapping):
        return value
    return {
        str(key): _pcr_provider_schema_node(item)
        for key, item in value.items()
        if key not in {"$schema", "$id", "uniqueItems"}
    }


def pcr_primary_provider_schema() -> dict[str, Any]:
    rendered = _pcr_provider_schema_node(PCR_PRIMARY_TURN_SCHEMA)
    if not isinstance(rendered, dict):
        raise TypeError("PCR provider schema must be an object")
    return rendered


PCR_PRIMARY_PROVIDER_SCHEMA = pcr_primary_provider_schema()
Draft202012Validator.check_schema(PCR_PRIMARY_TURN_SCHEMA)
Draft202012Validator.check_schema(PCR_PRIMARY_PROVIDER_SCHEMA)
_PCR_DIRECT_SUBMIT_NAME = "submit"  # legacy parser compatibility; not provider-visible
_PCR_DIRECT_FINISH_INTENT_NAME = "finish_intent"
_PCR_DIRECT_FINISH_NAME = "finish"


def _provider_object_for_variants(variants: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Nest exact canonical variants below an Azure-admissible object root.

    Azure rejects ``anyOf``/``oneOf``/``allOf`` at the function-parameter root,
    but accepts them below a named property. Keeping the unchanged canonical
    variants under ``arguments`` preserves their mutual exclusivity instead of
    flattening variant-specific fields into a nullable superset that can teach
    the model illegal cross-variant combinations.
    """
    if not variants:
        raise ValueError("direct provider tool requires at least one argument variant")
    exact = [dict(variant) for variant in variants]
    arguments_schema: dict[str, Any] = (
        exact[0] if len(exact) == 1 else {"anyOf": exact}
    )
    parameters = {
        "type": "object",
        "additionalProperties": False,
        "required": ["arguments"],
        "properties": {"arguments": arguments_schema},
    }
    Draft202012Validator.check_schema(parameters)
    return parameters

_DIRECT_TOOL_DESCRIPTIONS = {
    "read_file": (
        "Read one text file in the task workspace. Large model-visible excerpts remain exactly "
        "retrievable from the resulting receipt."
    ),
    "read_file_page": (
        "Read one bounded character-range from a text file; the result states total characters, "
        "returned characters, UTF-8 byte size, and whether more content remains."
    ),
    "read_output": (
        "Read one bounded character-range from an exact receipt/stdout/stderr handle; the result "
        "states total characters, UTF-8 byte size, and whether more content remains."
    ),
    "grep_output": (
        "Literal substring search over an exact captured output handle. Returns at most the first "
        "200 matching lines and explicitly reports total matches and whether more matches exist."
    ),
    "inspect_diff": (
        "Inspect Aether-recorded read/write history for one exact path. "
        "This is not a current filesystem diff and does not recursively inspect directories."
    ),
    "query_artifact_history": (
        "Retrieve up to the 12 most recent Aether-recorded artifact events for one exact path; "
        "the result reports the total event count and whether older events remain."
    ),
    "query_history": (
        "Search recorded receipt summaries and selected fields by literal substring."
    ),
}


def pcr_direct_provider_tools() -> tuple[dict[str, Any], ...]:
    """Render one Azure-strict provider-native function per PCR action plus explicit completion controls.

    Every provider function has a top-level object schema. Action arguments
    remain the unchanged canonical exact variants nested under one required
    ``arguments`` field, so the provider sees the same mutually exclusive
    grammar that Aether later revalidates locally.
    """
    tools: list[dict[str, Any]] = []
    for kind, variants in PCR_ACTION_ARGUMENT_VARIANTS.items():
        if kind == "computer_action":
            continue
        parameters = _provider_object_for_variants(variants)
        tools.append({
            "type": "function",
            "name": kind,
            "description": _DIRECT_TOOL_DESCRIPTIONS.get(
                kind, f"Execute the single current PCR action: {kind}."
            ),
            "parameters": parameters,
            "strict": True,
        })
    completion_parameters = {
        "type": "object",
        "additionalProperties": False,
        "required": ["claim", "evidence_refs"],
        "properties": {
            "claim": dict(_NONEMPTY_STRING),
            "evidence_refs": {
                "type": "array",
                "minItems": 1,
                "items": dict(_NONEMPTY_STRING),
            },
        },
    }
    Draft202012Validator.check_schema(completion_parameters)
    tools.extend((
        {
            "type": "function",
            "name": _PCR_DIRECT_FINISH_INTENT_NAME,
            "description": (
                "State that the current candidate is believed complete and request the one "
                "advisory independent review for this candidate generation. This does not finish."
            ),
            "parameters": completion_parameters,
            "strict": True,
        },
        {
            "type": "function",
            "name": _PCR_DIRECT_FINISH_NAME,
            "description": (
                "Finish the task using the current evidence. This is Luna's final semantic "
                "completion decision and never implicitly starts independent review."
            ),
            "parameters": completion_parameters,
            "strict": True,
        },
    ))
    return tuple(tools)


PCR_DIRECT_PROVIDER_TOOLS = pcr_direct_provider_tools()
_PCR_PRIMARY_VALIDATOR = Draft202012Validator(PCR_PRIMARY_TURN_SCHEMA)


def pcr_action_contract_view() -> dict[str, list[dict[str, Any]]]:
    """Return the single mechanical action catalogue rendered to the Primary Agent."""
    result: dict[str, list[dict[str, Any]]] = {}
    for kind, variants in PCR_ACTION_ARGUMENT_VARIANTS.items():
        rows: list[dict[str, Any]] = []
        for variant in variants:
            properties = variant.get("properties", {})
            constants = {
                name: list(schema.get("enum", ()))
                for name, schema in properties.items()
                if isinstance(schema, Mapping) and schema.get("enum")
            }
            row: dict[str, Any] = {"arguments": list(properties)}
            if constants:
                row["constants"] = constants
            rows.append(row)
        result[kind] = rows
    return result


def _reject_constant(value: str) -> None:
    raise PCRProviderProtocolError("provider_pcr_v0_nonstandard_json_constant", value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PCRProviderProtocolError("provider_pcr_v0_duplicate_key", str(key))
        result[key] = value
    return result


def _object_sequence(text: str) -> list[tuple[str, dict[str, Any]]]:
    raw = str(text or "").strip()
    if not raw:
        raise PCRProviderProtocolError("provider_pcr_v0_empty")
    decoder = json.JSONDecoder(
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )
    values: list[tuple[str, dict[str, Any]]] = []
    cursor = 0
    while cursor < len(raw):
        while cursor < len(raw) and raw[cursor].isspace():
            cursor += 1
        if cursor >= len(raw):
            break
        start = cursor
        try:
            value, cursor = decoder.raw_decode(raw, cursor)
        except PCRProviderProtocolError:
            raise
        except json.JSONDecodeError as exc:
            raise PCRProviderProtocolError(
                "provider_pcr_v0_invalid_json", str(exc),
            ) from exc
        if not isinstance(value, dict):
            raise PCRProviderProtocolError("provider_pcr_v0_top_level_not_object")
        values.append((raw[start:cursor], value))
    if not values:
        raise PCRProviderProtocolError("provider_pcr_v0_empty")
    return values


def _validation_detail(error: Any) -> str:
    path = ".".join(str(item) for item in error.absolute_path)
    return f"{path or 'root'}:{error.message}"


def validate_pcr_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and mechanically normalise one provider envelope."""
    errors = sorted(
        _PCR_PRIMARY_VALIDATOR.iter_errors(dict(envelope)),
        key=lambda item: (tuple(str(part) for part in item.absolute_path), item.message),
    )
    if errors:
        raise PCRProviderProtocolError(
            "provider_pcr_v0_schema_validation",
            _validation_detail(errors[0]),
        )
    turn = envelope["turn"]
    # JSON round-trip produces an immutable-by-convention plain copy and keeps
    # normalisation strictly mechanical; no semantic graph or task inference.
    return json.loads(json.dumps(turn, ensure_ascii=False, allow_nan=False))


def validate_pcr_inner_turn(turn: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one direct/stub inner turn against the exact production schema."""
    return validate_pcr_envelope({"turn": dict(turn)})


def canonicalize_pcr_direct_tool_call(name: str, arguments_text: str) -> tuple[str, dict[str, Any]]:
    """Convert one direct native function call into the canonical PCR turn.

    The direct transport is independently fail-closed: exactly one JSON object
    is accepted, wrapper keys are exact, unknown action names are rejected, and
    the reconstructed turn passes the unchanged canonical PCR validator.
    """
    candidates = _object_sequence(arguments_text)
    if len(candidates) != 1:
        raise PCRProviderProtocolError(
            "provider_pcr_v0_direct_arguments_object_count_invalid",
            f"expected=1 actual={len(candidates)}",
        )
    _raw, payload = candidates[0]
    tool_name = str(name or "")
    if tool_name in {
        _PCR_DIRECT_SUBMIT_NAME, _PCR_DIRECT_FINISH_INTENT_NAME, _PCR_DIRECT_FINISH_NAME
    }:
        if set(payload) != {"claim", "evidence_refs"}:
            raise PCRProviderProtocolError(
                "provider_pcr_v0_direct_completion_fields_invalid",
                json.dumps(sorted(payload), separators=(",", ":")),
            )
        kind = (
            "submit" if tool_name == _PCR_DIRECT_SUBMIT_NAME
            else "finish_intent" if tool_name == _PCR_DIRECT_FINISH_INTENT_NAME
            else "finish"
        )
        turn = {
            "turn": {
                "kind": kind,
                "claim": payload["claim"],
                "evidence_refs": payload["evidence_refs"],
            }
        }
    elif tool_name in PCR_ACTION_ARGUMENT_VARIANTS:
        if set(payload) != {"arguments"} or not isinstance(payload.get("arguments"), Mapping):
            raise PCRProviderProtocolError(
                "provider_pcr_v0_direct_action_fields_invalid",
                json.dumps(sorted(payload), separators=(",", ":")),
            )
        turn = {
            "turn": {
                "kind": "act",
                "action": {
                    "kind": tool_name,
                    "arguments": dict(payload["arguments"]),
                },
            }
        }
    else:
        raise PCRProviderProtocolError(
            "provider_pcr_v0_direct_tool_name_invalid", tool_name or "missing",
        )
    canonical, receipt = canonicalize_pcr_primary_turn(
        json.dumps(turn, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    )
    receipt = dict(receipt)
    receipt["provider_turn_arguments_transport"] = "direct_native_function"
    receipt["provider_direct_tool_name"] = tool_name
    return canonical, receipt


def canonicalize_pcr_primary_turn(text: str) -> tuple[str, dict[str, Any]]:
    """Decode exactly one complete PCR turn from one assistant message.

    Provider-level duplication is handled one layer above, where separate
    assistant message items can be proven semantically identical. Inside a
    single assistant message, more than one complete JSON object is always an
    atomic-turn violation, even when the objects are identical. This preserves
    the causal boundary: one model message authorises at most one current turn.
    """
    candidates = _object_sequence(text)
    if len(candidates) != 1:
        candidate_rows: list[dict[str, Any]] = []
        for raw_candidate, envelope in candidates:
            row: dict[str, Any] = {
                "raw_sha256": hashlib.sha256(raw_candidate.encode("utf-8")).hexdigest(),
            }
            try:
                normalized = validate_pcr_envelope(envelope)
                canonical = json.dumps(
                    normalized,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
                row.update({
                    "turn_kind": str(normalized.get("kind", "")),
                    "semantic_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                })
            except PCRProviderProtocolError as exc:
                row.update({
                    "turn_kind": "invalid",
                    "validation_error": exc.code,
                })
            candidate_rows.append(row)
        raise PCRProviderProtocolError(
            "provider_pcr_v0_multiple_objects_in_message",
            json.dumps({
                "candidate_count": len(candidates),
                "candidates": candidate_rows,
            }, sort_keys=True, separators=(",", ":")),
        )

    raw_candidate, envelope = candidates[0]
    normalized = validate_pcr_envelope(envelope)
    kind = str(normalized["kind"])
    canonical = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    raw_hash = hashlib.sha256(raw_candidate.encode("utf-8")).hexdigest()
    semantic_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return canonical, {
        "provider_turn_contract": PCR_PRIMARY_TURN_PROTOCOL,
        "provider_turn_kind": kind,
        "provider_turn_wrapper_sha256": hashlib.sha256(
            str(text).encode("utf-8")
        ).hexdigest(),
        "provider_turn_payload_sha256": semantic_hash,
        "provider_turn_candidate_count": 1,
        "provider_turn_raw_candidate_hashes": [raw_hash],
        "provider_turn_semantic_candidate_hashes": [semantic_hash],
        "provider_turn_duplicate_output": False,
        "provider_turn_duplicate_equivalent": False,
        "provider_turn_arguments_transport": "direct_json_object",
    }

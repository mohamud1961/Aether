"""Strict provider and deterministic contract for the PERSISTENT V0 Primary Agent.

One action-specific argument authority generates the provider JSON schema, the
deterministic validator, and the model-visible action catalogue. This prevents
both hidden post-schema invariants and accidental loss of optional capability
arguments such as paging, command timeouts, filtered retrieval, and
manager-specific bootstrap inputs.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from .edit_file_tool import (
    EDIT_FILE_ACTION,
    edit_file_argument_variants,
    edit_file_arguments_error,
    edit_file_provider_tool,
)
from .runtime_ir import ACTION_SCHEMA, FIXED_KERNEL_TOOL_SURFACE
from .persistent_flat_advanced import (
    COMMITMENT_FIELDS,
    FLAT_ACTION_FIELDS,
    FLAT_ADVANCED_DESCRIPTION,
    PROVIDER_TOOL_SHAPE_FLAT,
    PROVIDER_TOOL_SHAPE_NESTED,
    PROVIDER_TOOL_SHAPES,
    arguments_string_error_detail,
    flat_advanced_parameters,
    flat_field_error_detail,
    is_flat_advanced_payload,
)

PERSISTENT_PRIMARY_TURN_PROTOCOL = "persistent_v0"
PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME = "aether_persistent_v0_primary_turn"
def persistent_primary_turn_response_instruction() -> str:
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


PERSISTENT_PRIMARY_TURN_RESPONSE_INSTRUCTION = persistent_primary_turn_response_instruction()

PERSISTENT_PRIMARY_ACTION_SCHEMA = tuple(
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
_COMPLETION_SOURCE_REF: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["task_hash", "start_byte", "end_byte"],
    "properties": {
        "task_hash": {"type": "string", "pattern": r"^sha256:[0-9a-fA-F]{64}$"},
        "start_byte": dict(_NONNEGATIVE_INTEGER),
        "end_byte": dict(_POSITIVE_INTEGER),
    },
}
_COMPLETION_EVIDENCE_REF: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["receipt_id", "artifact_hash"],
    "properties": {
        "receipt_id": dict(_NONEMPTY_STRING),
        "artifact_hash": {"type": "string", "pattern": r"^(?:sha256:)?[0-9a-fA-F]{64}$"},
    },
}
_COMPLETION_CONDITION: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    # Azure strict schemas require every declared property in every nested
    # object to be required. ``retirement_reason`` is therefore represented
    # as a required nullable field; runtime validation requires a non-empty
    # string only when Frontier marks the condition retired.
    "required": [
        "id", "outcome", "source_refs", "kind", "proof_needed",
        "evidence_refs", "assessment", "uncertainty", "retirement_reason",
    ],
    "properties": {
        "id": dict(_NONEMPTY_STRING),
        "outcome": dict(_NONEMPTY_STRING),
        "source_refs": {"type": "array", "minItems": 1, "items": _COMPLETION_SOURCE_REF},
        "kind": {"type": "string", "enum": ["explicit", "derived"]},
        "proof_needed": dict(_NONEMPTY_STRING),
        "evidence_refs": {"type": "array", "items": _COMPLETION_EVIDENCE_REF},
        "assessment": {"type": "string", "enum": ["open", "supported", "contradicted", "retired"]},
        "uncertainty": dict(_STRING),
        "retirement_reason": {
            "anyOf": [dict(_NONEMPTY_STRING), {"type": "null"}],
        },
    },
}
_COMPLETION_RECORD: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "revision", "task_hash", "conditions", "revision_reason"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [1]},
        "revision": dict(_POSITIVE_INTEGER),
        "task_hash": {"type": "string", "pattern": r"^sha256:[0-9a-fA-F]{64}$"},
        "conditions": {"type": "array", "maxItems": 24, "items": _COMPLETION_CONDITION},
        "revision_reason": dict(_NONEMPTY_STRING),
    },
}
_COMPLETION_FINISH_METADATA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["reviewed_revision", "remaining_uncertainties", "completion_basis"],
    "properties": {
        "reviewed_revision": dict(_NONNEGATIVE_INTEGER),
        "remaining_uncertainties": {"type": "array", "items": dict(_STRING)},
        "completion_basis": dict(_NONEMPTY_STRING),
    },
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
PERSISTENT_ACTION_ARGUMENT_VARIANTS: dict[str, tuple[dict[str, Any], ...]] = {
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
    "start_job": (
        _object({
            "service_name": _NONEMPTY_STRING,
            "command": _NONEMPTY_STRING,
        }),
        _object({
            "service_name": _NONEMPTY_STRING,
            "command": _NONEMPTY_STRING,
            "relevance": _enum("required", "optional"),
            "reason": _NONEMPTY_STRING,
        }),
    ),
    "probe_job": (_object({"target": _NONEMPTY_STRING}),),
    "probe_service": (_object({"target": _NONEMPTY_STRING}),),
    "stop_process": (_object({"target": _NONEMPTY_STRING}),),
    "set_job_disposition": (
        _object({
            "job_id": _NONEMPTY_STRING,
            "relevance": _enum("required", "optional", "superseded", "abandoned"),
            "reason": _NONEMPTY_STRING,
        }),
        _object({
            "job_id": _NONEMPTY_STRING,
            "relevance": _enum("required", "optional", "superseded", "abandoned"),
            "reason": _NONEMPTY_STRING,
            "replacement_job_id": _NONEMPTY_STRING,
        }),
    ),
    "update_completion_record": (_object({
        "expected_revision": _NONNEGATIVE_INTEGER,
        "replacement_record": _COMPLETION_RECORD,
    }),),
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

_EXPECTED_ACTIONS = {kind for kind, _arguments in PERSISTENT_PRIMARY_ACTION_SCHEMA}
if set(PERSISTENT_ACTION_ARGUMENT_VARIANTS) != _EXPECTED_ACTIONS:
    missing = sorted(_EXPECTED_ACTIONS - set(PERSISTENT_ACTION_ARGUMENT_VARIANTS))
    extra = sorted(set(PERSISTENT_ACTION_ARGUMENT_VARIANTS) - _EXPECTED_ACTIONS)
    raise RuntimeError(
        f"PERSISTENT action argument authority drifted: missing={missing}, extra={extra}"
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
            "summary": dict(_NONEMPTY_STRING),
            "evidence_gap": dict(_NONEMPTY_STRING),
            "action": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "arguments"],
                "properties": {
                    "kind": {"type": "string", "enum": [kind]},
                    "arguments": dict(arguments_schema),
                    "intent": dict(_NONEMPTY_STRING),
                    "expected_observation": dict(_NONEMPTY_STRING),
                    "if_fail_next": dict(_NONEMPTY_STRING),
                },
            },
        },
    }


def _finding_disposition_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "finding_id", "disposition", "explanation", "evidence_refs",
            "residual_uncertainty",
        ],
        "properties": {
            "finding_id": dict(_NONEMPTY_STRING),
            "disposition": {
                "type": "string",
                "enum": ["resolved", "not_applicable", "override"],
            },
            "explanation": {"type": "string"},
            "evidence_refs": {
                "type": "array",
                "items": dict(_NONEMPTY_STRING),
            },
            "residual_uncertainty": {"type": "string"},
        },
    }


def persistent_primary_turn_schema() -> dict[str, Any]:
    """Return the one exact production PERSISTENT turn schema."""
    act_variants = [
        _act_variant(kind, arguments_schema)
        for kind, variants in PERSISTENT_ACTION_ARGUMENT_VARIANTS.items()
        for arguments_schema in variants
    ]
    def completion_variant(kind: str) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "kind": {"type": "string", "enum": [kind]},
            "claim": dict(_NONEMPTY_STRING),
            "evidence_refs": {
                "type": "array",
                "minItems": 1,
                "description": (
                    "Use only canonical evidence_ref aliases from the current evidence_index "
                    "(values shaped evidence:<16 hex>). Do not use receipt_id values."
                ),
                "items": {
                    "type": "string",
                    "pattern": r"^evidence:[0-9a-f]{16}$",
                },
            },
        }
        if kind == "finish":
            properties["finding_dispositions"] = {
                "type": "array",
                "minItems": 1,
                "items": _finding_disposition_schema(),
            }
            properties["finish_metadata"] = dict(_COMPLETION_FINISH_METADATA)
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "claim", "evidence_refs"],
            "properties": properties,
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


def persistent_m_tree_primary_turn_schema() -> dict[str, Any]:
    """Return the control turn schema plus the isolated M-TREE zoom action."""
    schema = persistent_primary_turn_schema()
    zoom_arguments = _object({
        "id": _NONNEGATIVE_INTEGER,
        "n": _POSITIVE_INTEGER,
    })
    schema["properties"]["turn"]["anyOf"].append(
        _act_variant("zoom", zoom_arguments)
    )
    return schema


def persistent_context_file_primary_turn_schema() -> dict[str, Any]:
    """Return the control turn schema plus the isolated context-file edit action."""
    schema = persistent_primary_turn_schema()
    edit_arguments = {"anyOf": [
        _object({"old": {"type": "string", "minLength": 1}, "new": _STRING}),
        _object({"replace_all_text": _STRING}),
    ]}
    schema["properties"]["turn"]["anyOf"].append(_act_variant("edit_context", edit_arguments))
    return schema


PERSISTENT_PRIMARY_TURN_SCHEMA = persistent_primary_turn_schema()
PERSISTENT_M_TREE_PRIMARY_TURN_SCHEMA = persistent_m_tree_primary_turn_schema()
PERSISTENT_CONTEXT_FILE_PRIMARY_TURN_SCHEMA = persistent_context_file_primary_turn_schema()


def _persistent_provider_schema_node(value: Any) -> Any:
    """Project canonical PERSISTENT schema onto provider-supported JSON Schema keywords."""
    if isinstance(value, list):
        return [_persistent_provider_schema_node(item) for item in value]
    if not isinstance(value, Mapping):
        return value
    return {
        str(key): _persistent_provider_schema_node(item)
        for key, item in value.items()
        if key not in {"$schema", "$id", "uniqueItems"}
    }


def persistent_primary_provider_schema() -> dict[str, Any]:
    rendered = _persistent_provider_schema_node(PERSISTENT_PRIMARY_TURN_SCHEMA)
    if not isinstance(rendered, dict):
        raise TypeError("PERSISTENT provider schema must be an object")
    return rendered


PERSISTENT_PRIMARY_PROVIDER_SCHEMA = persistent_primary_provider_schema()
Draft202012Validator.check_schema(PERSISTENT_PRIMARY_TURN_SCHEMA)
Draft202012Validator.check_schema(PERSISTENT_M_TREE_PRIMARY_TURN_SCHEMA)
Draft202012Validator.check_schema(PERSISTENT_CONTEXT_FILE_PRIMARY_TURN_SCHEMA)
Draft202012Validator.check_schema(PERSISTENT_PRIMARY_PROVIDER_SCHEMA)
_PERSISTENT_DIRECT_SUBMIT_NAME = "submit"  # legacy parser compatibility; not provider-visible
_PERSISTENT_DIRECT_FINISH_INTENT_NAME = "finish_intent"
_PERSISTENT_DIRECT_FINISH_NAME = "finish"
_COMPLETION_RECORD_ACTION_KIND = "update_completion_record"


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

def _commitment_string(description: str) -> dict[str, Any]:
    schema = dict(_NONEMPTY_STRING)
    schema["description"] = str(description)
    return schema


def _provider_object_for_variants_commitment_v1(
    variants: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Provider-native action schema with compact model-authored commitments.

    This is research-only and default-off. The canonical action arguments remain
    unchanged; Frontier additionally states a concise subgoal/evidence gap and one
    falsifiable expectation/contingency for the current causal action.
    """
    base = _provider_object_for_variants(variants)
    arguments_schema = dict(base["properties"]["arguments"])
    parameters = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary", "evidence_gap", "intent", "expected_observation",
            "if_fail_next", "arguments",
        ],
        "properties": {
            "summary": _commitment_string("Concise current subgoal; not chain-of-thought."),
            "evidence_gap": _commitment_string("The unresolved factual uncertainty this action addresses."),
            "intent": _commitment_string("Why this action is relevant to that evidence gap."),
            "expected_observation": _commitment_string("A concise falsifiable observation expected from the action."),
            "if_fail_next": _commitment_string("A concise pivot if the action fails or contradicts the expectation."),
            "arguments": arguments_schema,
        },
    }
    Draft202012Validator.check_schema(parameters)
    return parameters


_DIRECT_TOOL_DESCRIPTIONS = {
    "read_file": (
        "Read one text file in the task workspace. Relative paths are anchored at the current "
        "workspace root named in task context; do not prefix that workspace root again. "
        "Absolute paths are accepted only when they remain inside the workspace. Large "
        "model-visible excerpts remain exactly retrievable from the resulting receipt."
    ),
    "write_file": (
        "Write one text file in the task workspace. Relative paths are anchored at the current "
        "workspace root named in task context; do not prefix that workspace root again. "
        "Absolute paths are accepted only when they remain inside the workspace."
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
        "Search recorded receipt metadata, captured content, and the bounded immutable preflight "
        "command/Python-module environment inventory by literal substring. Matches are historical "
        "and source-linked; revalidate mutable availability with a live action before relying on it."
    ),
}


def persistent_direct_provider_tools(
    *,
    commitment_v1: bool = False,
    completion_disposition_v1: bool = False,
    include_completion_record: bool = True,
) -> tuple[dict[str, Any], ...]:
    """Render one Azure-strict provider-native function per PERSISTENT action plus explicit completion controls.

    Every provider function has a top-level object schema. Action arguments
    remain the unchanged canonical exact variants nested under one required
    ``arguments`` field, so the provider sees the same mutually exclusive
    grammar that Aether later revalidates locally.

    ``include_completion_record=False`` hides the structured ``update_completion_record``
    control from the provider surface while ``completion_record_mode`` is off; the
    kernel still mechanically validates any historical call that somehow arrives.
    """
    tools: list[dict[str, Any]] = []
    for kind, variants in PERSISTENT_ACTION_ARGUMENT_VARIANTS.items():
        if kind == "computer_action":
            continue
        if kind == _COMPLETION_RECORD_ACTION_KIND and not include_completion_record:
            continue
        parameters = (
            _provider_object_for_variants_commitment_v1(variants)
            if commitment_v1 else _provider_object_for_variants(variants)
        )
        tools.append({
            "type": "function",
            "name": kind,
            "description": _DIRECT_TOOL_DESCRIPTIONS.get(
                kind, f"Execute the single current PERSISTENT action: {kind}."
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
                "description": (
                    "Use only canonical evidence_ref aliases from the current evidence_index "
                    "(values shaped evidence:<16 hex>). Do not use receipt_id values."
                ),
                "items": {
                    "type": "string",
                    "pattern": r"^evidence:[0-9a-f]{16}$",
                },
            },
        },
    }
    finish_parameters = {
        "type": "object",
        "additionalProperties": False,
        # Azure strict function schemas require every root property to be
        # required. Nullable metadata preserves one identical provider surface
        # across control/treatment without turning metadata into a semantic veto.
        "required": ["claim", "evidence_refs", "finish_metadata"],
        "properties": {
            **dict(completion_parameters["properties"]),
            "finish_metadata": {
                "anyOf": [dict(_COMPLETION_FINISH_METADATA), {"type": "null"}],
            },
        },
    }
    if completion_disposition_v1:
        finish_parameters["required"] = [
            "claim", "evidence_refs", "finish_metadata", "finding_dispositions"
        ]
        finish_parameters["properties"]["finding_dispositions"] = {
            "type": "array",
            "minItems": 1,
            "items": _finding_disposition_schema(),
        }
    Draft202012Validator.check_schema(completion_parameters)
    Draft202012Validator.check_schema(finish_parameters)
    tools.extend((
        {
            "type": "function",
            "name": _PERSISTENT_DIRECT_FINISH_INTENT_NAME,
            "description": (
                "State that the current candidate is believed complete and request the one "
                "advisory independent review for this candidate generation. This does not finish. "
                "Cite canonical evidence_ref aliases from evidence_index, never receipt_id values."
            ),
            "parameters": completion_parameters,
            "strict": True,
        },
        {
            "type": "function",
            "name": _PERSISTENT_DIRECT_FINISH_NAME,
            "description": (
                "Finish the task using the current evidence. This is your final semantic "
                "completion decision and never implicitly starts independent review. Cite "
                "canonical evidence_ref aliases from evidence_index, never receipt_id values."
            ),
            "parameters": finish_parameters,
            "strict": True,
        },
    ))
    return tuple(tools)


PERSISTENT_DIRECT_PROVIDER_TOOLS = persistent_direct_provider_tools()
PERSISTENT_DIRECT_PROVIDER_TOOLS_COMMITMENT_V1 = persistent_direct_provider_tools(commitment_v1=True)
PERSISTENT_DIRECT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1 = persistent_direct_provider_tools(
    completion_disposition_v1=True
)
PERSISTENT_DIRECT_PROVIDER_TOOLS_COMMITMENT_AND_DISPOSITION_V1 = persistent_direct_provider_tools(
    commitment_v1=True, completion_disposition_v1=True
)

_PERSISTENT_CHAT_RUN_COMMAND_ADVANCED_NAME = "run_command_advanced"


_FINISH_COMPLETION_CARD_DESCRIPTION = (
    "One entry per separate acceptance criterion stated in the task (do not merge or omit any): "
    "the evidence_refs that show it holds now ([] if none) and the shell command that demonstrates it."
)


def finish_completion_card_schema() -> dict[str, Any]:
    """Strict-mode schema of the completion card carried by the finish call (challenger_v4)."""
    check = {
        "type": "object", "additionalProperties": False, "required": ["description", "command"],
        "properties": {"description": dict(_NONEMPTY_STRING), "command": dict(_NONEMPTY_STRING)},
    }
    criterion = {
        "type": "object", "additionalProperties": False,
        "required": ["id", "text", "evidence_refs", "check"],
        "properties": {
            "id": dict(_NONEMPTY_STRING), "text": dict(_NONEMPTY_STRING),
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "pattern": r"^evidence:[0-9a-f]{16}$"},
            },
            "check": check,
        },
    }
    return {
        "type": "object", "additionalProperties": False, "required": ["criteria"],
        "description": _FINISH_COMPLETION_CARD_DESCRIPTION,
        "properties": {"criteria": {"type": "array", "minItems": 1, "maxItems": 8, "items": criterion}},
    }


def with_finish_completion_card(tools: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Add the required ``completion_card`` object to the finish tool only (idempotent).

    Accepts the direct or the Chat-nested tool shape and returns the same shape. Every other
    tool is returned unchanged, so no other claim-ledger mode sees any difference.
    """
    out: list[dict[str, Any]] = []
    for tool in tools:
        row = deepcopy(dict(tool))
        function = row["function"] if isinstance(row.get("function"), dict) else row
        if function.get("name") == _PERSISTENT_DIRECT_FINISH_NAME:
            parameters = function["parameters"]
            parameters["properties"]["completion_card"] = finish_completion_card_schema()
            if "completion_card" not in parameters["required"]:
                parameters["required"] = [*parameters["required"], "completion_card"]
            Draft202012Validator.check_schema(parameters)
        out.append(row)
    return tuple(out)


def persistent_chat_provider_tools(
    *,
    commitment_v1: bool = False,
    completion_disposition_v1: bool = False,
    include_completion_record: bool = True,
    advanced_tool_shape: str = PROVIDER_TOOL_SHAPE_NESTED,
    include_m_tree_zoom: bool = False,
    finish_completion_card: bool = False,
    include_background_jobs: bool = False,
) -> tuple[dict[str, Any], ...]:
    """Render a Chat-Completions PERSISTENT surface with a flat common run-command path.

    ``advanced_tool_shape="flat_v1"`` also removes the ``arguments`` wrapper from
    run_command_advanced (see persistent_flat_advanced); the default keeps the nested
    form byte-identical.

    Chat-compatible GLM providers have repeatedly serialized the nested
    arguments object for ordinary run_command calls as a JSON string. Complex
    shell quoting can corrupt that extra string layer before Aether can validate
    the intended command.

    Keep the canonical action grammar unchanged. Only the common
    command+timeout provider surface is flattened. Rare helper/path/extension
    variants remain available through run_command_advanced using the existing
    exact nested grammar. Both transports canonicalize back to the same
    run_command action and are revalidated locally.
    """
    base=list(persistent_direct_provider_tools(
        commitment_v1=commitment_v1,
        completion_disposition_v1=completion_disposition_v1,
        include_completion_record=include_completion_record,
    ))
    index=next(i for i,row in enumerate(base) if row.get("name")=="run_command")
    if commitment_v1:
        standard_properties={
            "summary":_commitment_string("Concise current subgoal; not chain-of-thought."),
            "evidence_gap":_commitment_string("The unresolved factual uncertainty this action addresses."),
            "intent":_commitment_string("Why this action is relevant to that evidence gap."),
            "expected_observation":_commitment_string("A concise falsifiable observation expected from the action."),
            "if_fail_next":_commitment_string("A concise pivot if the action fails or contradicts the expectation."),
            "command":_NONEMPTY_STRING,
            "timeout_s":_POSITIVE_INTEGER,
        }
    else:
        standard_properties={
            "command":_NONEMPTY_STRING,
            "timeout_s":_POSITIVE_INTEGER,
        }
    standard={
        "type":"function",
        "name":"run_command",
        "description":(
            "Execute one ordinary shell command with an explicit positive timeout. "
            "Provide command and timeout_s directly; do not wrap them in an arguments field. "
            "Use run_command_advanced only when helper/path/capture/extension metadata is required."
        ),
        "parameters":_object(standard_properties),
        "strict":True,
    }
    advanced_variants=tuple(PERSISTENT_ACTION_ARGUMENT_VARIANTS["run_command"][2:])
    advanced_parameters=(
        _provider_object_for_variants_commitment_v1(advanced_variants)
        if commitment_v1 else _provider_object_for_variants(advanced_variants)
    )
    advanced={
        "type":"function",
        "name":_PERSISTENT_CHAT_RUN_COMMAND_ADVANCED_NAME,
        "description":(
            "Execute a run_command variant that requires helper/path/capture/extension metadata. "
            "Ordinary shell verification should use run_command instead."
        ),
        "parameters":advanced_parameters,
        "strict":True,
    }
    if advanced_tool_shape not in PROVIDER_TOOL_SHAPES:
        raise ValueError(f"unsupported provider tool shape: {advanced_tool_shape!r}")
    if advanced_tool_shape == PROVIDER_TOOL_SHAPE_FLAT:
        advanced["description"]=FLAT_ADVANCED_DESCRIPTION
        advanced["parameters"]=flat_advanced_parameters(commitment_v1=commitment_v1)
        advanced["strict"]=False
    base[index:index+1]=[standard,advanced]
    if include_m_tree_zoom:
        from .context_tree.epoch import ZOOM_TOOL

        base.append(deepcopy(ZOOM_TOOL))
    if include_background_jobs:
        base.extend(persistent_chat_background_job_tools(commitment_v1=commitment_v1))
    if finish_completion_card:
        return with_finish_completion_card(base)
    return tuple(base)


def persistent_chat_edit_file_tool(*, commitment_v1: bool = False) -> dict[str, Any]:
    """Flat provider function for the opt-in edit_file action (edit surface only)."""
    commitment = {
        "summary": _commitment_string("Concise current subgoal; not chain-of-thought."),
        "evidence_gap": _commitment_string("The unresolved factual uncertainty this action addresses."),
        "intent": _commitment_string("Why this action is relevant to that evidence gap."),
        "expected_observation": _commitment_string("A concise falsifiable observation expected from the action."),
        "if_fail_next": _commitment_string("A concise pivot if the action fails or contradicts the expectation."),
    } if commitment_v1 else None
    tool = edit_file_provider_tool(commitment_fields=commitment)
    Draft202012Validator.check_schema(tool["parameters"])
    return tool


def persistent_flat_tool_parameters(parameters: Mapping[str, Any]) -> dict[str, Any]:
    """Remove the nested action-arguments envelope from a provider function schema."""
    source = deepcopy(dict(parameters))
    def remove_nullable(value: Any) -> Any:
        if isinstance(value, list):
            return [remove_nullable(item) for item in value]
        if not isinstance(value, Mapping):
            return value
        result = {str(key): remove_nullable(item) for key, item in value.items()}
        branches = result.get("anyOf")
        if isinstance(branches, list):
            branches = [item for item in branches if not (isinstance(item, Mapping) and item.get("type") == "null")]
            if len(branches) == 1:
                result.pop("anyOf", None)
                result.update(branches[0])
            else:
                result["anyOf"] = branches
        return result
    source = remove_nullable(source)
    properties = source.get("properties")
    if not isinstance(properties, Mapping) or "arguments" not in properties:
        if isinstance(properties, Mapping) and "finish_metadata" in properties:
            properties = dict(properties)
            properties.pop("finish_metadata", None)
            source["properties"] = properties
            source["required"] = [key for key in source.get("required", ()) if key != "finish_metadata"]
        return source
    arguments = properties["arguments"]
    variants = arguments.get("anyOf", ()) if isinstance(arguments, Mapping) else ()
    if not variants:
        variants = (arguments,)
    commitment_fields = {
        key: properties[key] for key in COMMITMENT_FIELDS if key in properties
    }
    commitment_required = [key for key in COMMITMENT_FIELDS if key in source.get("required", ())]
    flat_variants = []
    for variant in variants:
        if not isinstance(variant, Mapping):
            continue
        row = deepcopy(dict(variant))
        row_properties = dict(row.get("properties", {}))
        row_properties.update(deepcopy(commitment_fields))
        row["properties"] = row_properties
        row["required"] = [
            *list(row.get("required", ())),
            *[key for key in commitment_required if key not in row.get("required", ())],
        ]
        flat_variants.append(row)
    if len(flat_variants) == 1:
        result = flat_variants[0]
    else:
        union_properties: dict[str, Any] = {}
        for variant in flat_variants:
            union_properties.update(variant.get("properties", {}))
        result = {
            "type": "object",
            "additionalProperties": False,
            "properties": union_properties,
            "anyOf": flat_variants,
        }
    # Nullable completion metadata is advisory transport detail and is omitted
    # from this surface; the canonical finish action remains unchanged.
    if "finish_metadata" in result.get("properties", {}):
        result["properties"].pop("finish_metadata", None)
        result["required"] = [key for key in result.get("required", ()) if key != "finish_metadata"]
    Draft202012Validator.check_schema(result)
    return result


PERSISTENT_CHAT_PROVIDER_TOOLS = persistent_chat_provider_tools()
PERSISTENT_CHAT_PROVIDER_TOOLS_COMMITMENT_V1 = persistent_chat_provider_tools(commitment_v1=True)
PERSISTENT_CHAT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1 = persistent_chat_provider_tools(
    completion_disposition_v1=True
)
PERSISTENT_CHAT_PROVIDER_TOOLS_COMMITMENT_AND_DISPOSITION_V1 = persistent_chat_provider_tools(
    commitment_v1=True, completion_disposition_v1=True
)
# T1 filters these names from the canonical schema objects. Their arguments
# and execution semantics remain owned by the existing protocol and dispatcher.
PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES = (
    "read_file",
    "write_file",
    "run_command",
    "read_output",
    "query_history",
    "inspect_diff",
    "finish_intent",
    "finish",
)
# Chat Completions flattens ordinary run_command and moves the canonical
# helper/path/capture/extension variants behind a provider-only alias.  Static
# kernel must retain that alias whenever canonical run_command is exposed;
# otherwise the model is instructed to call a tool that the provider request
# silently omits.
PERSISTENT_CHAT_STATIC_TOOL_KERNEL_V1_NAMES = (
    *PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES,
    _PERSISTENT_CHAT_RUN_COMMAND_ADVANCED_NAME,
)
# Hard service-lifecycle diagnostics showed that the 8-tool kernel can remove
# the only non-blocking process primitive.  This treatment restores just the
# managed background-job lifecycle while keeping the rest of the rare surface
# absent.  It is opt-in until live evidence earns promotion.
PERSISTENT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES = (
    *PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES,
    "start_job",
    "probe_job",
    "stop_process",
)
PERSISTENT_CHAT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES = (
    *PERSISTENT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES,
    _PERSISTENT_CHAT_RUN_COMMAND_ADVANCED_NAME,
)
# static_kernel_v1 plus the opt-in partial-edit action (aether/edit_file_tool.py).
# finish_intent is dropped on this surface: it requests an advisory independent
# review and these arms configure no reviewer, so each call only returned the
# packet.  finish is kept; the Thin loop's completion path treats both alike.
PERSISTENT_STATIC_TOOL_KERNEL_EDIT_V1_NAMES = (
    *(name for name in PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES if name != "finish_intent"),
    EDIT_FILE_ACTION,
)
PERSISTENT_CHAT_STATIC_TOOL_KERNEL_EDIT_V1_NAMES = (
    *(name for name in PERSISTENT_CHAT_STATIC_TOOL_KERNEL_V1_NAMES if name != "finish_intent"),
    EDIT_FILE_ACTION,
)
PERSISTENT_TOOL_SURFACE_CONTROL = "control"
PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_V1 = "static_kernel_v1"
PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_JOBS_V1 = "static_kernel_jobs_v1"
PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1 = "static_kernel_edit_v1"
PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1 = "static_kernel_edit_flat_v1"
PERSISTENT_TOOL_SURFACE_MODES = frozenset({
    PERSISTENT_TOOL_SURFACE_CONTROL,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_JOBS_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1,
})
# Surfaces on which every callable tool is named by the provider request.
PERSISTENT_STATIC_TOOL_SURFACE_MODES = frozenset({
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_JOBS_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1,
})


def persistent_exposed_action_names(mode: str) -> frozenset[str] | None:
    """Return the callable action names for a tool-surface mode (None = all)."""
    if mode == PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_V1:
        return frozenset(PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES)
    if mode == PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_JOBS_V1:
        return frozenset(PERSISTENT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES)
    if mode in {PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1, PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1}:
        return frozenset(PERSISTENT_STATIC_TOOL_KERNEL_EDIT_V1_NAMES)
    return None


PERSISTENT_SHELL_SENTENCE = "The working directory and exported variables persist between commands."


def persistent_persistent_shell(mode: str) -> bool:
    """Whether run_command keeps cwd and exported variables across calls (edit surface only)."""
    return mode in {PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1, PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1}


def persistent_finish_intent_exposed(mode: str) -> bool:
    """Whether the surface callable-tool set includes the advisory-review finish_intent."""
    exposed = persistent_exposed_action_names(mode)
    return exposed is None or "finish_intent" in exposed


def persistent_filter_context_for_tool_surface(
    context: Mapping[str, Any], mode: str,
) -> Mapping[str, Any]:
    """Make model-visible context packet text truthful for the exposed tools.

    Control mode returns the input object unchanged (byte-identical request).
    """
    exposed = persistent_exposed_action_names(mode)
    if exposed is None:
        return context
    result = dict(context)
    available = dict(result.get("available_capabilities") or {})
    if "action_kinds" in available:
        available["action_kinds"] = [
            str(kind) for kind in available["action_kinds"] if str(kind) in exposed
        ]
        result["available_capabilities"] = available
    history = result.get("history_access")
    if isinstance(history, Mapping):
        if "query_history" not in exposed:
            result.pop("history_access")
        elif "read_output" not in exposed:
            result["history_access"] = {
                key: value for key, value in history.items()
                if not key.startswith("exact_")
            }
    return result


_PERSISTENT_PRIMARY_VALIDATOR = Draft202012Validator(PERSISTENT_PRIMARY_TURN_SCHEMA)
_PERSISTENT_M_TREE_PRIMARY_VALIDATOR = Draft202012Validator(PERSISTENT_M_TREE_PRIMARY_TURN_SCHEMA)
_PERSISTENT_CONTEXT_FILE_PRIMARY_VALIDATOR = Draft202012Validator(PERSISTENT_CONTEXT_FILE_PRIMARY_TURN_SCHEMA)

BACKGROUND_JOB_ACTION_ARGUMENTS: dict[str, tuple[dict[str, Any], ...]] = {
    "job_output": (_object({"job_id": _NONEMPTY_STRING, "tail_lines": _POSITIVE_INTEGER}),),
    "job_wait": (_object({"job_id": _NONEMPTY_STRING, "timeout_s": _NONNEGATIVE_NUMBER}),),
    "job_stop": (_object({"job_id": _NONEMPTY_STRING}),),
}
_BACKGROUND_JOB_VALIDATOR: Draft202012Validator | None = None


def persistent_background_job_primary_turn_schema() -> dict[str, Any]:
    schema = persistent_primary_turn_schema()
    schema["properties"]["turn"]["anyOf"].extend(
        _act_variant(kind, variants[0]) for kind, variants in BACKGROUND_JOB_ACTION_ARGUMENTS.items()
    )
    return schema


def persistent_chat_background_job_tools(*, commitment_v1: bool = False) -> tuple[dict[str, Any], ...]:
    tools = []
    for name, variants in BACKGROUND_JOB_ACTION_ARGUMENTS.items():
        properties = dict(variants[0]["properties"])
        if commitment_v1:
            properties = {
                "summary": _commitment_string("Concise current subgoal; not chain-of-thought."),
                "evidence_gap": _commitment_string("The unresolved factual uncertainty this action addresses."),
                "intent": _commitment_string("Why this action is relevant to that evidence gap."),
                "expected_observation": _commitment_string("A concise falsifiable observation expected from the action."),
                "if_fail_next": _commitment_string("A concise pivot if this observation fails."),
                **properties,
            }
        # These read/stop calls have one exact argument shape, so expose it
        # directly. This composes with edit_flat without reintroducing the
        # arguments wrapper after the main surface has been flattened.
        params = _object(properties)
        tools.append({
            "type": "function", "name": name,
            "description": {
                "job_output": "Read the latest output tail for a managed job.",
                "job_wait": "Wait briefly for a managed job and return its latest status.",
                "job_stop": "Stop a managed job that should no longer continue.",
            }[name],
            "parameters": params, "strict": True,
        })
    return tuple(tools)


def persistent_edit_file_primary_turn_schema(*, include_m_tree_zoom: bool = False) -> dict[str, Any]:
    """Control turn schema (optionally plus zoom) plus the opt-in edit_file action."""
    schema = persistent_m_tree_primary_turn_schema() if include_m_tree_zoom else persistent_primary_turn_schema()
    schema["properties"]["turn"]["anyOf"].append(
        _act_variant(EDIT_FILE_ACTION, {"anyOf": list(edit_file_argument_variants())})
    )
    return schema


_PERSISTENT_EDIT_FILE_VALIDATORS: dict[bool, Draft202012Validator] = {}


def _persistent_edit_file_validator(include_m_tree_zoom: bool) -> Draft202012Validator:
    if include_m_tree_zoom not in _PERSISTENT_EDIT_FILE_VALIDATORS:
        schema = persistent_edit_file_primary_turn_schema(include_m_tree_zoom=include_m_tree_zoom)
        Draft202012Validator.check_schema(schema)
        _PERSISTENT_EDIT_FILE_VALIDATORS[include_m_tree_zoom] = Draft202012Validator(schema)
    return _PERSISTENT_EDIT_FILE_VALIDATORS[include_m_tree_zoom]


def persistent_action_contract_view() -> dict[str, list[dict[str, Any]]]:
    """Return the single mechanical action catalogue rendered to the Primary Agent."""
    result: dict[str, list[dict[str, Any]]] = {}
    for kind, variants in PERSISTENT_ACTION_ARGUMENT_VARIANTS.items():
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
    raise PCRProviderProtocolError("provider_persistent_v0_nonstandard_json_constant", value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PCRProviderProtocolError("provider_persistent_v0_duplicate_key", str(key))
        result[key] = value
    return result


def _object_sequence(text: str) -> list[tuple[str, dict[str, Any]]]:
    raw = str(text or "").strip()
    if not raw:
        raise PCRProviderProtocolError("provider_persistent_v0_empty")
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
                "provider_persistent_v0_invalid_json", str(exc),
            ) from exc
        if not isinstance(value, dict):
            raise PCRProviderProtocolError("provider_persistent_v0_top_level_not_object")
        values.append((raw[start:cursor], value))
    if not values:
        raise PCRProviderProtocolError("provider_persistent_v0_empty")
    return values


def _validation_detail(error: Any) -> str:
    path = ".".join(str(item) for item in error.absolute_path)
    return f"{path or 'root'}:{error.message}"


def validate_persistent_envelope(
    envelope: Mapping[str, Any], *, include_m_tree_zoom: bool = False,
    include_edit_context: bool = False, include_edit_file: bool = False,
    include_background_jobs: bool = False,
) -> dict[str, Any]:
    """Validate and mechanically normalise one provider envelope."""
    if include_m_tree_zoom and include_edit_context:
        raise ValueError("one context mechanism per run: zoom and edit_context are exclusive")
    if include_edit_file and include_edit_context:
        raise ValueError("edit_file and edit_context are not combined")
    global _BACKGROUND_JOB_VALIDATOR
    validator = (
        _persistent_edit_file_validator(include_m_tree_zoom) if include_edit_file
        else _PERSISTENT_M_TREE_PRIMARY_VALIDATOR if include_m_tree_zoom
        else _PERSISTENT_CONTEXT_FILE_PRIMARY_VALIDATOR if include_edit_context
        else _BACKGROUND_JOB_VALIDATOR if include_background_jobs and _BACKGROUND_JOB_VALIDATOR is not None
        else _PERSISTENT_PRIMARY_VALIDATOR
    )
    if include_background_jobs and _BACKGROUND_JOB_VALIDATOR is None:
        schema = persistent_background_job_primary_turn_schema()
        Draft202012Validator.check_schema(schema)
        _BACKGROUND_JOB_VALIDATOR = Draft202012Validator(schema)
        validator = _BACKGROUND_JOB_VALIDATOR
    errors = sorted(
        validator.iter_errors(dict(envelope)),
        key=lambda item: (tuple(str(part) for part in item.absolute_path), item.message),
    )
    if errors:
        raise PCRProviderProtocolError(
            "provider_persistent_v0_schema_validation",
            _validation_detail(errors[0]),
        )
    turn = envelope["turn"]
    # JSON round-trip produces an immutable-by-convention plain copy and keeps
    # normalisation strictly mechanical; no semantic graph or task inference.
    return json.loads(json.dumps(turn, ensure_ascii=False, allow_nan=False))


def validate_persistent_inner_turn(
    turn: Mapping[str, Any], *, include_m_tree_zoom: bool = False,
    include_edit_context: bool = False, include_edit_file: bool = False,
    include_background_jobs: bool = False,
) -> dict[str, Any]:
    """Validate one direct/stub inner turn against the exact production schema."""
    return validate_persistent_envelope(
        {"turn": dict(turn)}, include_m_tree_zoom=include_m_tree_zoom,
        include_edit_context=include_edit_context, include_edit_file=include_edit_file,
        include_background_jobs=include_background_jobs,
    )


def canonicalize_persistent_direct_tool_call(
    name: str,
    arguments_text: str,
    *,
    allow_m_tree_zoom: bool = False,
    allow_edit_context: bool = False,
    allow_completion_card: bool = False,
    allow_edit_file: bool = False,
    allow_flat_tool_surface: bool = False,
    allow_background_jobs: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Convert one direct native function call into the canonical PERSISTENT turn.

    The direct transport is independently fail-closed: exactly one JSON object
    is accepted, wrapper keys are exact, unknown action names are rejected, and
    the reconstructed turn passes the unchanged canonical PERSISTENT validator.
    """
    candidates = _object_sequence(arguments_text)
    if len(candidates) != 1:
        raise PCRProviderProtocolError(
            "provider_persistent_v0_direct_arguments_object_count_invalid",
            f"expected=1 actual={len(candidates)}",
        )
    _raw, payload = candidates[0]
    tool_name = str(name or "")
    canonical_action_tool_name = (
        "run_command" if tool_name == _PERSISTENT_CHAT_RUN_COMMAND_ADVANCED_NAME else tool_name
    )
    direct_action_arguments_normalization = ""
    m_tree_zoom = canonical_action_tool_name == "zoom"
    edit_context = canonical_action_tool_name == "edit_context"
    completion_card: dict[str, Any] | None = None
    edit_file = canonical_action_tool_name == EDIT_FILE_ACTION
    if tool_name in {
        _PERSISTENT_DIRECT_SUBMIT_NAME, _PERSISTENT_DIRECT_FINISH_INTENT_NAME, _PERSISTENT_DIRECT_FINISH_NAME
    }:
        allowed_fields = {"claim", "evidence_refs"}
        if tool_name == _PERSISTENT_DIRECT_FINISH_NAME:
            if allow_completion_card and "completion_card" in payload:
                # Side channel: the card never enters the canonical turn. A card that is not an
                # object is dropped here; the claim-ledger consumer falls back to a card turn.
                completion_card = _completion_card_object(payload["completion_card"])
                payload = {k: v for k, v in payload.items() if k != "completion_card"}
            allowed_shapes = {
                frozenset(allowed_fields),
                frozenset({*allowed_fields, "finding_dispositions"}),
                frozenset({*allowed_fields, "finish_metadata"}),
                frozenset({*allowed_fields, "finding_dispositions", "finish_metadata"}),
            }
        else:
            allowed_shapes = {frozenset(allowed_fields)}
        if frozenset(payload) not in allowed_shapes:
            raise PCRProviderProtocolError(
                "provider_persistent_v0_direct_completion_fields_invalid",
                json.dumps(sorted(payload), separators=(",", ":")),
            )
        kind = (
            "submit" if tool_name == _PERSISTENT_DIRECT_SUBMIT_NAME
            else "finish_intent" if tool_name == _PERSISTENT_DIRECT_FINISH_INTENT_NAME
            else "finish"
        )
        inner_completion = {
            "kind": kind,
            "claim": payload["claim"],
            "evidence_refs": payload["evidence_refs"],
        }
        if tool_name == _PERSISTENT_DIRECT_FINISH_NAME and "finding_dispositions" in payload:
            inner_completion["finding_dispositions"] = payload["finding_dispositions"]
        if (
            tool_name == _PERSISTENT_DIRECT_FINISH_NAME
            and isinstance(payload.get("finish_metadata"), Mapping)
        ):
            inner_completion["finish_metadata"] = payload["finish_metadata"]
        turn = {"turn": inner_completion}
    elif m_tree_zoom and allow_m_tree_zoom:
        if set(payload) != {"id", "n"}:
            raise PCRProviderProtocolError(
                "provider_persistent_v0_direct_action_fields_invalid",
                json.dumps(sorted(payload), separators=(",", ":")),
            )
        if (
            type(payload.get("id")) is not int or payload["id"] < 0
            or type(payload.get("n")) is not int or payload["n"] < 1
        ):
            raise PCRProviderProtocolError(
                "provider_persistent_v0_schema_validation",
                "turn.action.arguments:zoom requires integer id >= 0 and n >= 1",
            )
        action_arguments = {"id": payload["id"], "n": payload["n"]}
        direct_action_arguments_normalization = "m_tree_zoom_v1"
        payload_fields = frozenset()
        turn = {"turn": {"kind": "act", "action": {"kind": "zoom", "arguments": action_arguments}}}
    elif edit_file and allow_edit_file:
        commitment_present = frozenset(payload) & frozenset(COMMITMENT_FIELDS)
        if commitment_present and commitment_present != frozenset(COMMITMENT_FIELDS):
            raise PCRProviderProtocolError(
                "provider_persistent_v0_direct_action_fields_invalid",
                json.dumps(sorted(payload), separators=(",", ":")),
            )
        action_arguments = {k: v for k, v in payload.items() if k not in COMMITMENT_FIELDS}
        edit_error = edit_file_arguments_error(action_arguments)
        if edit_error:
            raise PCRProviderProtocolError(
                "provider_persistent_v0_schema_validation", f"turn.action.arguments:{edit_error}",
            )
        direct_action_arguments_normalization = "chat_flat_edit_file_v1"
        payload_fields = frozenset()
        inner_edit: dict[str, Any] = {
            "kind": "act", "action": {"kind": EDIT_FILE_ACTION, "arguments": action_arguments},
        }
        if commitment_present:
            inner_edit["summary"] = payload["summary"]
            inner_edit["evidence_gap"] = payload["evidence_gap"]
            inner_edit["action"].update({
                "intent": payload["intent"],
                "expected_observation": payload["expected_observation"],
                "if_fail_next": payload["if_fail_next"],
            })
        turn = {"turn": inner_edit}
    elif edit_context and allow_edit_context:
        edit_error = _context_file_edit_error(payload)
        if edit_error:
            raise PCRProviderProtocolError(
                "provider_persistent_v0_schema_validation", f"turn.action.arguments:{edit_error}",
            )
        direct_action_arguments_normalization = "context_file_edit_v1"
        payload_fields = frozenset()
        turn = {"turn": {"kind": "act", "action": {"kind": "edit_context", "arguments": dict(payload)}}}
    elif canonical_action_tool_name in PERSISTENT_ACTION_ARGUMENT_VARIANTS or (
        allow_background_jobs and canonical_action_tool_name in BACKGROUND_JOB_ACTION_ARGUMENTS
    ):
        v0_fields = {"arguments"}
        v1_fields = {
            "summary", "evidence_gap", "intent", "expected_observation",
            "if_fail_next", "arguments",
        }
        payload_fields = frozenset(payload)
        flat_chat_fields = frozenset({"command", "timeout_s"})
        flat_chat_commitment_fields = frozenset({
            "summary", "evidence_gap", "intent", "expected_observation",
            "if_fail_next", "command", "timeout_s",
        })
        flat_chat_run_command = (
            tool_name == "run_command"
            and payload_fields in {flat_chat_fields, flat_chat_commitment_fields}
        )
        if flat_chat_run_command:
            action_arguments = {
                "command": payload["command"],
                "timeout_s": payload["timeout_s"],
            }
            direct_action_arguments_normalization = "chat_flat_run_command_v1"
        elif tool_name == _PERSISTENT_CHAT_RUN_COMMAND_ADVANCED_NAME and is_flat_advanced_payload(payload):
            action_arguments = {k: payload[k] for k in FLAT_ACTION_FIELDS if k in payload}
            direct_action_arguments_normalization = "chat_flat_run_command_advanced_v1"
            if frozenset(payload) & frozenset(COMMITMENT_FIELDS):
                payload_fields = frozenset({*v1_fields})
                payload = {**payload, "arguments": action_arguments}
        elif (
            allow_background_jobs
            and canonical_action_tool_name in BACKGROUND_JOB_ACTION_ARGUMENTS
            and payload_fields in {
                frozenset(BACKGROUND_JOB_ACTION_ARGUMENTS[canonical_action_tool_name][0]["properties"]),
                frozenset({*BACKGROUND_JOB_ACTION_ARGUMENTS[canonical_action_tool_name][0]["properties"], *COMMITMENT_FIELDS}),
            }
        ):
            action_arguments = {
                key: value for key, value in payload.items() if key not in COMMITMENT_FIELDS
            }
            direct_action_arguments_normalization = "chat_flat_background_job_v1"
        else:
            action_arguments = payload.get("arguments")
            if allow_flat_tool_surface and "arguments" not in payload:
                commitment_present = frozenset(payload) & frozenset(COMMITMENT_FIELDS)
                if commitment_present and commitment_present != frozenset(COMMITMENT_FIELDS):
                    raise PCRProviderProtocolError(
                        "provider_persistent_v0_direct_action_fields_invalid",
                        json.dumps(sorted(payload), separators=(",", ":")),
                    )
                action_arguments = {
                    key: value for key, value in payload.items()
                    if key not in COMMITMENT_FIELDS
                }
                payload_fields = frozenset({"arguments"})
                if commitment_present:
                    payload = {**payload, "arguments": dict(action_arguments)}
                    payload_fields = frozenset(v1_fields)
            # Some Chat-Completions-compatible providers occasionally serialize the
            # nested arguments object one extra time. Normalize only the exact v0
            # wrapper shape and only when that string is itself one complete JSON
            # object. Canonical PERSISTENT validation below remains the authority.
            if payload_fields == frozenset(v0_fields) and isinstance(action_arguments, str):
                try:
                    decoded_arguments = json.loads(action_arguments)
                except (TypeError, ValueError):
                    decoded_arguments = None
                if isinstance(decoded_arguments, Mapping):
                    action_arguments = decoded_arguments
                    direct_action_arguments_normalization = "single_json_object_string_to_object"
            if (
                payload_fields in {frozenset(v0_fields), frozenset(v1_fields)}
                and isinstance(action_arguments, str)
            ):
                raise PCRProviderProtocolError(
                    "provider_persistent_v0_direct_arguments_string_not_object",
                    arguments_string_error_detail(tool_name),
                )
            if payload_fields not in {frozenset(v0_fields), frozenset(v1_fields)} or not isinstance(action_arguments, Mapping):
                raise PCRProviderProtocolError(
                    "provider_persistent_v0_direct_action_fields_invalid",
                    json.dumps(sorted(payload), separators=(",", ":")),
                )
        inner: dict[str, Any] = {
            "kind": "act",
            "action": {
                "kind": canonical_action_tool_name,
                "arguments": dict(action_arguments),
            },
        }
        if payload_fields == frozenset(v1_fields) or (
            flat_chat_run_command and payload_fields == flat_chat_commitment_fields
        ):
            inner["summary"] = payload["summary"]
            inner["evidence_gap"] = payload["evidence_gap"]
            inner["action"].update({
                "intent": payload["intent"],
                "expected_observation": payload["expected_observation"],
                "if_fail_next": payload["if_fail_next"],
            })
        turn = {"turn": inner}
    else:
        raise PCRProviderProtocolError(
            "provider_persistent_v0_direct_tool_name_invalid", tool_name or "missing",
        )
    try:
        canonical, receipt = canonicalize_persistent_primary_turn(
            json.dumps(turn, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False),
            include_m_tree_zoom=allow_m_tree_zoom,
            include_edit_context=allow_edit_context,
            include_edit_file=allow_edit_file,
            include_background_jobs=allow_background_jobs,
        )
    except PCRProviderProtocolError as exc:
        if direct_action_arguments_normalization != "chat_flat_run_command_advanced_v1":
            raise
        raise PCRProviderProtocolError(
            exc.code, flat_field_error_detail(payload, exc.detail),
        ) from exc
    receipt = dict(receipt)
    receipt["provider_turn_arguments_transport"] = "direct_native_function"
    receipt["provider_direct_tool_name"] = tool_name
    if tool_name == _PERSISTENT_DIRECT_FINISH_NAME and completion_card is not None:
        receipt["challenger_completion_card"] = completion_card
    if canonical_action_tool_name != tool_name:
        receipt["provider_canonical_action_kind"] = canonical_action_tool_name
    if direct_action_arguments_normalization:
        receipt["provider_direct_action_arguments_normalization"] = direct_action_arguments_normalization
    return canonical, receipt


def _completion_card_object(value: Any) -> dict[str, Any] | None:
    """The card as an object; some chat providers serialize a nested object as a JSON string."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return dict(value) if isinstance(value, Mapping) else None


def _context_file_edit_error(payload: Mapping[str, Any]) -> str:
    from .context_file.tools import edit_arguments_error

    return edit_arguments_error(payload)


def canonicalize_persistent_primary_turn(
    text: str, *, include_m_tree_zoom: bool = False, include_edit_context: bool = False,
    include_edit_file: bool = False, include_background_jobs: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Decode exactly one complete PERSISTENT turn from one assistant message.

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
                normalized = validate_persistent_envelope(
                    envelope, include_m_tree_zoom=include_m_tree_zoom,
                    include_edit_context=include_edit_context, include_edit_file=include_edit_file,
                    include_background_jobs=include_background_jobs,
                )
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
            "provider_persistent_v0_multiple_objects_in_message",
            json.dumps({
                "candidate_count": len(candidates),
                "candidates": candidate_rows,
            }, sort_keys=True, separators=(",", ":")),
        )

    raw_candidate, envelope = candidates[0]
    normalized = validate_persistent_envelope(
        envelope, include_m_tree_zoom=include_m_tree_zoom,
        include_edit_context=include_edit_context, include_edit_file=include_edit_file,
        include_background_jobs=include_background_jobs,
    )
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
        "provider_turn_contract": PERSISTENT_PRIMARY_TURN_PROTOCOL,
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

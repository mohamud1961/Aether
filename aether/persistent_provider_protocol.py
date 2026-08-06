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
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .runtime_ir import ACTION_SCHEMA, FIXED_KERNEL_TOOL_SURFACE

PERSISTENT_PRIMARY_TURN_PROTOCOL = "persistent_v0"
PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME = "aether_persistent_v0_primary_turn"
PERSISTENT_WORKING_STATE_POLICIES = frozenset({"optional", "disabled"})


def normalize_persistent_working_state_policy(value: str = "optional") -> str:
    policy = str(value or "optional").strip().lower()
    if policy not in PERSISTENT_WORKING_STATE_POLICIES:
        raise PCRProviderProtocolError(
            "provider_persistent_v0_working_state_policy_invalid", policy or "missing",
        )
    return policy


def persistent_primary_turn_response_instruction(
    *, working_state_policy: str = "optional",
) -> str:
    policy = normalize_persistent_working_state_policy(working_state_policy)
    base = (
        "Return exactly one strict provider object with the sole key turn. turn is "
        "either one act containing exactly one action, or one submit containing a "
        "completion claim and evidence references. Do not emit action IDs, plans, "
        "predictions, reflections, hidden reasoning, future turns, markdown, or prose."
    )
    if policy == "disabled":
        return base + " This provider contract has no working_state or checkpoint field."
    return (
        base
        + " You may optionally include one bounded working_state checkpoint containing "
        "only concise externalized continuity fields; it is not task evidence."
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

_EVIDENCE_REF_ARRAY: dict[str, Any] = {
    "type": "array",
    "maxItems": 8,
    "uniqueItems": True,
    "items": {"type": "string", "pattern": r"^evidence:[0-9a-f]{16}$"},
}

PERSISTENT_WORKING_STATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "current_objective",
        "established_facts",
        "open_questions",
        "active_hypotheses",
        "current_approach",
        "rejected_approaches",
        "pending_external_state",
        "completion_gaps",
    ],
    "properties": {
        "current_objective": {"type": "string", "pattern": r"\S", "maxLength": 800},
        "established_facts": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["fact", "evidence_refs"],
                "properties": {
                    "fact": {"type": "string", "pattern": r"\S", "maxLength": 800},
                    "evidence_refs": {
                        **_EVIDENCE_REF_ARRAY,
                        "minItems": 1,
                    },
                },
            },
        },
        "open_questions": {
            "type": "array", "maxItems": 12,
            "items": {"type": "string", "pattern": r"\S", "maxLength": 800},
        },
        "active_hypotheses": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["hypothesis", "status"],
                "properties": {
                    "hypothesis": {"type": "string", "pattern": r"\S", "maxLength": 800},
                    "status": {
                        "type": "string",
                        "enum": ["unconfirmed", "supported", "disconfirmed"],
                    },
                },
            },
        },
        "current_approach": {"type": "string", "pattern": r"\S", "maxLength": 1200},
        "rejected_approaches": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["approach", "reason", "evidence_refs"],
                "properties": {
                    "approach": {"type": "string", "pattern": r"\S", "maxLength": 600},
                    "reason": {"type": "string", "pattern": r"\S", "maxLength": 1000},
                    "evidence_refs": dict(_EVIDENCE_REF_ARRAY),
                },
            },
        },
        "pending_external_state": {
            "type": "array", "maxItems": 8,
            "items": {"type": "string", "pattern": r"\S", "maxLength": 800},
        },
        "completion_gaps": {
            "type": "array", "maxItems": 12,
            "items": {"type": "string", "pattern": r"\S", "maxLength": 800},
        },
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


_MEMORY_FILTERS = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "event_type",
        "kind",
        "path",
        "check_id",
        "failure_kind",
        "since_step",
    ],
    "properties": {
        "event_type": dict(_STRING_ARRAY),
        "kind": dict(_STRING_ARRAY),
        "path": dict(_STRING),
        "check_id": dict(_STRING),
        "failure_kind": dict(_STRING),
        "since_step": dict(_NONNEGATIVE_INTEGER),
    },
}

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
        "path": _NONEMPTY_STRING,
        "mode": _NONEMPTY_STRING,
    }),),
    "query_memory": (
        _object({"query": _STRING}),
        _object({
            "query": _STRING,
            "filters": _MEMORY_FILTERS,
        }),
    ),
    "query_artifact_history": (_object({"path": _NONEMPTY_STRING}),),
    "inspect_diff": (_object({"path": _NONEMPTY_STRING}),),
    "record_observation": (
        _object({"observation": _NONEMPTY_STRING}),
        _object({
            "observation": _NONEMPTY_STRING,
            "source": _STRING,
            "confidence": _STRING,
            "tags": _STRING_ARRAY,
            "path": _STRING,
        }),
    ),
    "report_blocker": (_object({
        "blocked_component": _NONEMPTY_STRING,
        "observed_evidence": _NONEMPTY_STRING,
        "attempted_actions": _NONEMPTY_STRING,
        "why_current_tools_or_config_prevent_progress": _NONEMPTY_STRING,
        "requested_harness_change": _NONEMPTY_STRING,
    }),),
    "inspect_checks": (_object({}),),
    "run_check": (_object({"check_id": _NONEMPTY_STRING}),),
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


def _act_variant(
    kind: str,
    arguments_schema: Mapping[str, Any],
    *,
    include_working_state: bool,
) -> dict[str, Any]:
    required = ["kind", "action"]
    properties: dict[str, Any] = {
        "kind": {"type": "string", "enum": ["act"]},
        "action": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "capability_id", "arguments"],
            "properties": {
                "kind": {"type": "string", "enum": [kind]},
                "capability_id": dict(_NONEMPTY_STRING),
                "arguments": dict(arguments_schema),
            },
        },
    }
    if include_working_state:
        required.append("working_state")
        properties["working_state"] = PERSISTENT_WORKING_STATE_SCHEMA
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def persistent_primary_turn_schema(
    *, working_state_policy: str = "optional",
) -> dict[str, Any]:
    """Return the exact strict schema for one working-state policy."""
    policy = normalize_persistent_working_state_policy(working_state_policy)
    working_state_variants = (False, True) if policy == "optional" else (False,)
    act_variants = [
        _act_variant(
            kind, arguments_schema, include_working_state=include_working_state,
        )
        for kind, variants in PERSISTENT_ACTION_ARGUMENT_VARIANTS.items()
        for arguments_schema in variants
        for include_working_state in working_state_variants
    ]
    submit_variants: list[dict[str, Any]] = []
    for include_working_state in working_state_variants:
        required = ["kind", "claim", "evidence_refs"]
        properties: dict[str, Any] = {
            "kind": {"type": "string", "enum": ["submit"]},
            "claim": dict(_NONEMPTY_STRING),
            "evidence_refs": {
                "type": "array",
                "minItems": 1,
                "items": dict(_NONEMPTY_STRING),
            },
        }
        if include_working_state:
            required.append("working_state")
            properties["working_state"] = PERSISTENT_WORKING_STATE_SCHEMA
        submit_variants.append({
            "type": "object",
            "additionalProperties": False,
            "required": required,
            "properties": properties,
        })
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["turn"],
        "properties": {
            "turn": {"anyOf": [*act_variants, *submit_variants]},
        },
    }


PERSISTENT_PRIMARY_TURN_SCHEMA = persistent_primary_turn_schema()


def _persistent_provider_schema_node(value: Any) -> Any:
    """Project the canonical PERSISTENT schema onto the provider-supported subset.

    Local validation remains authoritative and may enforce invariants, such as
    array uniqueness, that Azure/OpenAI strict structured-output schemas do not
    accept. Provider projection removes only transport-unsupported schema
    keywords; returned payloads are still validated against the canonical
    schema before execution.
    """
    if isinstance(value, list):
        return [_persistent_provider_schema_node(item) for item in value]
    if not isinstance(value, Mapping):
        return value
    return {
        str(key): _persistent_provider_schema_node(item)
        for key, item in value.items()
        if key not in {"$schema", "$id", "uniqueItems"}
    }


_PERSISTENT_PROVIDER_WORKING_STATE_DEF = "persistent_working_state"


def _factor_provider_working_state(
    value: Any,
    target: Mapping[str, Any],
) -> tuple[Any, int]:
    """Replace exact repeated provider working-state subtrees with one $ref.

    This changes only schema serialization. The generated model output shape is
    unchanged and every returned turn is still validated against the full
    canonical PERSISTENT_PRIMARY_TURN_SCHEMA before execution.
    """
    if isinstance(value, list):
        result: list[Any] = []
        count = 0
        for item in value:
            projected, child_count = _factor_provider_working_state(item, target)
            result.append(projected)
            count += child_count
        return result, count
    if not isinstance(value, Mapping):
        return value, 0
    if dict(value) == dict(target):
        return {"$ref": f"#/$defs/{_PERSISTENT_PROVIDER_WORKING_STATE_DEF}"}, 1
    result: dict[str, Any] = {}
    count = 0
    for key, item in value.items():
        projected, child_count = _factor_provider_working_state(item, target)
        result[str(key)] = projected
        count += child_count
    return result, count


def persistent_primary_provider_schema(
    *, working_state_policy: str = "optional",
) -> dict[str, Any]:
    """Return the strict provider projection for one working-state policy.

    Azure/OpenAI structured outputs support JSON Schema definitions and $ref.
    Keep the canonical local schema fully expanded, but serialize the identical
    optional working-state subtree once for the provider instead of dozens of
    times across action variants.
    """
    policy = normalize_persistent_working_state_policy(working_state_policy)
    rendered = _persistent_provider_schema_node(
        persistent_primary_turn_schema(working_state_policy=policy)
    )
    if not isinstance(rendered, dict):
        raise TypeError("PERSISTENT provider schema must be an object")
    if policy == "disabled":
        return rendered
    working_state = _persistent_provider_schema_node(PERSISTENT_WORKING_STATE_SCHEMA)
    if not isinstance(working_state, dict):
        raise TypeError("PERSISTENT provider working-state schema must be an object")
    factored, replacement_count = _factor_provider_working_state(
        rendered, working_state,
    )
    if not isinstance(factored, dict):
        raise TypeError("PERSISTENT factored provider schema must be an object")
    if replacement_count <= 0:
        raise RuntimeError("PERSISTENT provider schema contains no working-state subtree to factor")
    factored["$defs"] = {_PERSISTENT_PROVIDER_WORKING_STATE_DEF: working_state}
    return factored


PERSISTENT_PRIMARY_PROVIDER_SCHEMA = persistent_primary_provider_schema()
Draft202012Validator.check_schema(PERSISTENT_PRIMARY_TURN_SCHEMA)
Draft202012Validator.check_schema(PERSISTENT_PRIMARY_PROVIDER_SCHEMA)
Draft202012Validator.check_schema(PERSISTENT_WORKING_STATE_SCHEMA)
for _policy in PERSISTENT_WORKING_STATE_POLICIES:
    Draft202012Validator.check_schema(
        persistent_primary_turn_schema(working_state_policy=_policy)
    )
    Draft202012Validator.check_schema(
        persistent_primary_provider_schema(working_state_policy=_policy)
    )
_PERSISTENT_PRIMARY_VALIDATORS = {
    policy: Draft202012Validator(
        persistent_primary_turn_schema(working_state_policy=policy)
    )
    for policy in PERSISTENT_WORKING_STATE_POLICIES
}
_PERSISTENT_WORKING_STATE_VALIDATOR = Draft202012Validator(PERSISTENT_WORKING_STATE_SCHEMA)
PERSISTENT_PRIMARY_CHAT_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME,
        "strict": True,
        "schema": PERSISTENT_PRIMARY_PROVIDER_SCHEMA,
    },
}


def persistent_action_contract_view() -> dict[str, list[dict[str, Any]]]:
    """Return a compact mechanical catalogue rendered to the Primary Agent."""
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
            if "filters" in properties:
                row["filters"] = list(
                    properties["filters"].get("properties", {})
                )
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
    envelope: Mapping[str, Any],
    *,
    working_state_policy: str = "optional",
) -> dict[str, Any]:
    """Validate and mechanically normalise one provider envelope."""
    policy = normalize_persistent_working_state_policy(working_state_policy)
    errors = sorted(
        _PERSISTENT_PRIMARY_VALIDATORS[policy].iter_errors(dict(envelope)),
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
    turn: Mapping[str, Any],
    *,
    working_state_policy: str = "optional",
) -> dict[str, Any]:
    """Validate a direct/stub inner turn against one policy."""
    return validate_persistent_envelope(
        {"turn": dict(turn)}, working_state_policy=working_state_policy
    )


def validate_persistent_working_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one direct/manual working-state checkpoint exactly."""
    errors = sorted(
        _PERSISTENT_WORKING_STATE_VALIDATOR.iter_errors(dict(state)),
        key=lambda item: (
            tuple(str(part) for part in item.absolute_path), item.message
        ),
    )
    if errors:
        raise PCRProviderProtocolError(
            "provider_persistent_v0_working_state_validation",
            _validation_detail(errors[0]),
        )
    return json.loads(json.dumps(state, ensure_ascii=False, allow_nan=False))


def canonicalize_persistent_primary_turn(
    text: str,
    *,
    working_state_policy: str = "optional",
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
                    envelope, working_state_policy=working_state_policy
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
        envelope, working_state_policy=working_state_policy
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

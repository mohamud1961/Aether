from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from aether.persistent_provider_protocol import (
    PERSISTENT_ACTION_ARGUMENT_VARIANTS,
    PERSISTENT_PRIMARY_PROVIDER_SCHEMA,
    PERSISTENT_PRIMARY_TURN_SCHEMA,
    PERSISTENT_WORKING_STATE_SCHEMA,
    _persistent_provider_schema_node,
)


def _example(name: str, schema: Mapping[str, Any]) -> Any:
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    kind = schema.get("type")
    if kind == "string":
        return "x" if name not in {"content", "data"} else ""
    if kind == "integer":
        return 0 if name in {"offset", "wait_ms", "since_step"} else 1
    if kind == "number":
        return 1.0
    if kind == "boolean":
        return True
    if kind == "array":
        return []
    if kind == "object":
        properties = schema.get("properties", {})
        return {
            key: _example(key, child)
            for key, child in properties.items()
            if isinstance(child, Mapping)
        }
    raise AssertionError((name, schema))


def _working_state() -> dict[str, Any]:
    return {
        "current_objective": "Do the task.",
        "established_facts": [],
        "open_questions": [],
        "active_hypotheses": [],
        "current_approach": "Inspect current reality.",
        "rejected_approaches": [],
        "pending_external_state": [],
        "completion_gaps": ["Need current evidence."],
    }


def _inline_provider_schema() -> dict[str, Any]:
    rendered = _persistent_provider_schema_node(PERSISTENT_PRIMARY_TURN_SCHEMA)
    assert isinstance(rendered, dict)
    return rendered


def _valid_envelopes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for action_kind, variants in PERSISTENT_ACTION_ARGUMENT_VARIANTS.items():
        for variant in variants:
            properties = variant.get("properties", {})
            arguments = {
                key: _example(key, child)
                for key, child in properties.items()
                if isinstance(child, Mapping)
            }
            turn = {
                "kind": "act",
                "action": {
                    "kind": action_kind,
                    "capability_id": "kernel" if action_kind.startswith("query_") else "filesystem",
                    "arguments": arguments,
                },
            }
            rows.append({"turn": deepcopy(turn)})
            with_state = deepcopy(turn)
            with_state["working_state"] = _working_state()
            rows.append({"turn": with_state})
    rows.append({
        "turn": {
            "kind": "submit",
            "claim": "done",
            "evidence_refs": ["evidence:0123456789abcdef"],
        }
    })
    rows.append({
        "turn": {
            "kind": "submit",
            "claim": "done",
            "evidence_refs": ["evidence:0123456789abcdef"],
            "working_state": _working_state(),
        }
    })
    return rows


def test_factoring_uses_one_definition_without_changing_canonical_schema() -> None:
    Draft202012Validator.check_schema(PERSISTENT_PRIMARY_PROVIDER_SCHEMA)
    assert "$defs" in PERSISTENT_PRIMARY_PROVIDER_SCHEMA
    defs = PERSISTENT_PRIMARY_PROVIDER_SCHEMA["$defs"]
    assert list(defs) == ["persistent_working_state"]
    assert defs["persistent_working_state"] == _persistent_provider_schema_node(PERSISTENT_WORKING_STATE_SCHEMA)
    assert "$defs" not in PERSISTENT_PRIMARY_TURN_SCHEMA

    text = str(PERSISTENT_PRIMARY_PROVIDER_SCHEMA)
    assert text.count("#/$defs/persistent_working_state") == 43
    assert len(str(PERSISTENT_PRIMARY_PROVIDER_SCHEMA)) < len(str(_inline_provider_schema()))


def test_factored_and_inline_provider_schemas_accept_same_valid_envelopes() -> None:
    inline = Draft202012Validator(_inline_provider_schema())
    factored = Draft202012Validator(PERSISTENT_PRIMARY_PROVIDER_SCHEMA)
    rows = _valid_envelopes()
    assert len(rows) == 86
    for index, envelope in enumerate(rows):
        assert not list(inline.iter_errors(envelope)), index
        assert not list(factored.iter_errors(envelope)), index


def test_factored_and_inline_provider_schemas_reject_same_bad_shapes() -> None:
    inline = Draft202012Validator(_inline_provider_schema())
    factored = Draft202012Validator(PERSISTENT_PRIMARY_PROVIDER_SCHEMA)
    bad = [
        {},
        {"turn": {"kind": "act"}},
        {"turn": {"kind": "submit", "claim": "done", "evidence_refs": []}},
        {"turn": {"kind": "act", "action": {"kind": "read_file", "capability_id": "filesystem", "arguments": {}}}},
        {"turn": {"kind": "act", "action": {"kind": "unknown", "capability_id": "filesystem", "arguments": {}}}},
        {"turn": {"kind": "submit", "claim": "done", "evidence_refs": ["evidence:0123456789abcdef"], "extra": True}},
    ]
    for envelope in bad:
        assert list(inline.iter_errors(envelope))
        assert list(factored.iter_errors(envelope))

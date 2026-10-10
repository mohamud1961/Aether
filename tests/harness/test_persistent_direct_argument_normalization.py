from __future__ import annotations

import json

import pytest

from aether.persistent_provider_protocol import (
    PCRProviderProtocolError,
    canonicalize_persistent_direct_tool_call,
)


def test_direct_action_accepts_one_extra_json_string_layer_for_v0_arguments() -> None:
    canonical, receipt = canonicalize_persistent_direct_tool_call(
        "read_file",
        json.dumps({"arguments": json.dumps({"path": "/app/a.txt"})}),
    )

    assert json.loads(canonical) == {
        "kind": "act",
        "action": {"kind": "read_file", "arguments": {"path": "/app/a.txt"}},
    }
    assert (
        receipt["provider_direct_action_arguments_normalization"]
        == "single_json_object_string_to_object"
    )


@pytest.mark.parametrize("nested", ["not-json", "42", "null", "[1,2,3]"])
def test_direct_action_rejects_non_object_nested_argument_strings(nested: str) -> None:
    with pytest.raises(PCRProviderProtocolError, match="direct_(action_fields_invalid|arguments_string_not_object)"):
        canonicalize_persistent_direct_tool_call(
            "read_file",
            json.dumps({"arguments": nested}),
        )


def test_direct_action_decoded_object_still_uses_canonical_action_schema() -> None:
    with pytest.raises(PCRProviderProtocolError, match="schema_validation"):
        canonicalize_persistent_direct_tool_call(
            "read_file",
            json.dumps(
                {
                    "arguments": json.dumps(
                        {"path": "/app/a.txt", "unexpected": True}
                    )
                }
            ),
        )


def test_direct_action_does_not_relax_richer_v1_wrapper_shape() -> None:
    with pytest.raises(PCRProviderProtocolError, match="direct_(action_fields_invalid|arguments_string_not_object)"):
        canonicalize_persistent_direct_tool_call(
            "read_file",
            json.dumps(
                {
                    "summary": "read current artifact",
                    "evidence_gap": "need current bytes",
                    "intent": "inspect",
                    "expected_observation": "file contents",
                    "if_fail_next": "report blocker",
                    "arguments": json.dumps({"path": "/app/a.txt"}),
                }
            ),
        )


def test_direct_action_still_rejects_empty_payload() -> None:
    with pytest.raises(PCRProviderProtocolError, match="direct_action_fields_invalid"):
        canonicalize_persistent_direct_tool_call("run_command", "{}")

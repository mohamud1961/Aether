from __future__ import annotations

import json
import pytest

from aether.model_hooks import ModelOutputError, parse_solver_turn


def _act() -> dict:
    return {
        "kind": "act",
        "summary": "Inspect current config",
        "requested_check_ids": [],
        "claimed_artifacts": [],
        "evidence_gap": "The active config is unknown.",
        "actions": [{
            "action_id": "read-config",
            "kind": "read_file",
            "capability_id": "filesystem",
            "arguments": {"path": "config.json"},
            "intent": "Read the authoritative current config.",
            "expected_observation": "The exact config.json bytes.",
            "if_fail_next": "Locate the active config path or report the blocker.",
        }],
    }


def test_exact_object_and_one_optional_fence_are_accepted() -> None:
    raw = json.dumps(_act())
    assert parse_solver_turn(raw).kind == "act"
    assert parse_solver_turn(f"```json\n{raw}\n```").kind == "act"


@pytest.mark.parametrize("raw", [
    lambda body: "leading prose " + body,
    lambda body: body + " trailing prose",
    lambda body: body + json.dumps({"kind": "submit_outcome"}),
    lambda body: "[" + body + "]",
    lambda body: "```json\n" + body + "\n```\ntrailing",
])
def test_non_single_object_solver_output_fails_closed(raw) -> None:
    with pytest.raises(ModelOutputError):
        parse_solver_turn(raw(json.dumps(_act())))


def test_duplicate_keys_fail_closed() -> None:
    raw = json.dumps(_act())
    duplicate = raw.replace('"kind": "act"', '"kind": "act", "kind": "submit_outcome"', 1)
    with pytest.raises(ModelOutputError, match="duplicate JSON key"):
        parse_solver_turn(duplicate)


@pytest.mark.parametrize("field", [
    "kind", "summary", "requested_check_ids", "claimed_artifacts", "evidence_gap", "actions",
])
def test_act_requires_every_protocol_field(field: str) -> None:
    payload = _act(); payload.pop(field)
    with pytest.raises(ModelOutputError, match="missing required fields"):
        parse_solver_turn(json.dumps(payload))


@pytest.mark.parametrize("field", [
    "action_id", "kind", "capability_id", "arguments", "intent", "expected_observation", "if_fail_next",
])
def test_action_requires_every_commitment_field(field: str) -> None:
    payload = _act(); payload["actions"][0].pop(field)
    with pytest.raises(ModelOutputError, match="missing required fields"):
        parse_solver_turn(json.dumps(payload))


@pytest.mark.parametrize("field", ["evidence_gap"])
def test_act_commitment_strings_must_be_nonempty(field: str) -> None:
    payload = _act(); payload[field] = ""
    with pytest.raises(ModelOutputError, match="must be non-empty"):
        parse_solver_turn(json.dumps(payload))


@pytest.mark.parametrize("field", ["capability_id", "intent", "expected_observation", "if_fail_next"])
def test_action_commitment_strings_must_be_nonempty(field: str) -> None:
    payload = _act(); payload["actions"][0][field] = ""
    with pytest.raises(ModelOutputError, match="must be non-empty"):
        parse_solver_turn(json.dumps(payload))


def test_submit_is_separate_and_has_zero_actions() -> None:
    payload = {
        "kind": "submit_outcome",
        "summary": "Observed evidence supports completion.",
        "requested_check_ids": [],
        "claimed_artifacts": ["result.json"],
        "evidence_gap": "",
    }
    assert parse_solver_turn(json.dumps(payload)).actions == ()
    payload["actions"] = []
    with pytest.raises(ModelOutputError, match="unsupported fields"):
        parse_solver_turn(json.dumps(payload))

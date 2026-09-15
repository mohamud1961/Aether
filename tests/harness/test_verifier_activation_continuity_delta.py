from __future__ import annotations

from copy import deepcopy

import pytest

from aether.verifier_activation_continuity import (
    PREFIX,
    REPRESENTATION_CONTRACT,
    SCHEMA,
    apply_delta,
    delta_envelope,
    render_delta,
    snapshot_sha256,
)


def _view(turn: int) -> list[dict]:
    base = [{"role": "user", "content": {"authority": "fixed", "checks": ["alpha"]}}]
    if turn >= 2:
        base.append({
            "role": "user",
            "content": {
                "verifier_inspection_results": [
                    {"inspection_id": "inspection:1", "stdout": "ok"},
                ] + (
                    [{"inspection_id": "inspection:2", "stdout": "later"}]
                    if turn >= 3 else []
                ),
                "available_authoritative_source_refs": [
                    "inspection:1",
                    *( ["inspection:2"] if turn >= 3 else [] ),
                ],
                "instruction": "continue",
            },
        })
    return base


def test_no_change_delta_is_empty_and_lossless() -> None:
    previous = _view(1)
    envelope = delta_envelope(previous, deepcopy(previous))
    assert envelope["schema"] == SCHEMA
    assert envelope["representation_contract"] == REPRESENTATION_CONTRACT
    assert envelope["operations"] == []
    assert envelope["operation_count"] == 0
    assert apply_delta(previous, envelope) == previous


def test_monotonic_nested_lists_use_append_not_whole_list_replace() -> None:
    previous = _view(2)
    current = _view(3)
    envelope = delta_envelope(previous, current)
    assert apply_delta(previous, envelope) == current
    ops = envelope["operations"]
    assert any(
        row["op"] == "add"
        and row["path"].endswith("/verifier_inspection_results/-")
        for row in ops
    )
    assert any(
        row["op"] == "add"
        and row["path"].endswith("/available_authoritative_source_refs/-")
        for row in ops
    )
    assert not any(
        row["op"] == "replace"
        and "verifier_inspection_results" in row["path"]
        for row in ops
    )


def test_same_length_list_change_uses_exact_positional_replace() -> None:
    previous = {"items": [1, 2, 3]}
    current = {"items": [1, 9, 3]}
    envelope = delta_envelope(previous, current)
    assert envelope["operations"] == [
        {"op": "replace", "path": "/items/1", "value": 9}
    ]
    assert apply_delta(previous, envelope) == current


def test_add_remove_replace_and_pointer_escaping_round_trip() -> None:
    previous = {"a/b": {"~key": 1, "remove": True}, "same": "x"}
    current = {"a/b": {"~key": 2, "added": [1, 2]}, "same": "x"}
    envelope = delta_envelope(previous, current)
    assert apply_delta(previous, envelope) == current
    paths = {row["path"] for row in envelope["operations"]}
    assert "/a~1b/~0key" in paths
    assert "/a~1b/remove" in paths
    assert "/a~1b/added" in paths


def test_render_delta_self_verifies_and_uses_explicit_prefix() -> None:
    previous = _view(2)
    current = _view(3)
    rendered, envelope = render_delta(previous, current)
    assert rendered.startswith(PREFIX)
    assert envelope["base_snapshot_sha256"] == snapshot_sha256(previous)
    assert envelope["result_snapshot_sha256"] == snapshot_sha256(current)
    assert apply_delta(previous, envelope) == current


def test_tampered_base_result_contract_and_operation_fail_closed() -> None:
    previous = _view(2)
    current = _view(3)
    envelope = delta_envelope(previous, current)

    tampered = deepcopy(envelope)
    tampered["base_snapshot_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="base snapshot mismatch"):
        apply_delta(previous, tampered)

    tampered = deepcopy(envelope)
    tampered["result_snapshot_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="result snapshot mismatch"):
        apply_delta(previous, tampered)

    tampered = deepcopy(envelope)
    tampered["representation_contract"] = "guess from context"
    with pytest.raises(ValueError, match="representation contract drift"):
        apply_delta(previous, tampered)

    tampered = deepcopy(envelope)
    tampered["operations"] = [{"op": "invent", "path": "/x"}]
    tampered["operation_count"] = 1
    with pytest.raises(ValueError, match="unsupported"):
        apply_delta(previous, tampered)


def test_inputs_are_not_mutated() -> None:
    previous = _view(2)
    current = _view(3)
    before_previous = deepcopy(previous)
    before_current = deepcopy(current)
    envelope = delta_envelope(previous, current)
    apply_delta(previous, envelope)
    assert previous == before_previous
    assert current == before_current

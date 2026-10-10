from __future__ import annotations

from copy import deepcopy

import pytest

from aether.persistent_reality_delta import (
    DELTA_MODE,
    FULL_MODE,
    REPRESENTATION_CONTRACT,
    delta_snapshot_envelope,
    full_snapshot_envelope,
    reconstruct_snapshot,
    snapshot_sha256,
    transport_envelope,
)
from aether.persistent_reanchor import continuity_fresh_delta_reanchor


def _packet(step: int = 1) -> dict:
    latest = {
        "status": "succeeded",
        "action_id": f"action-{step}",
        "action_kind": "run_command",
        "outcome_receipts": [{
            "evidence_ref": f"evidence:{step}",
            "receipt_id": f"step-{step}:action-{step}:cmd",
            "evidence_type": "run_command",
            "originating_action_id": f"action-{step}",
            "mechanical_description": f"command step {step}",
            "success": True,
            "state_change": False,
            "failure_class": "",
            "step": step,
            "currentness": "latest_primary_result",
            "completion_evidence_eligible": True,
            "exact_access": {
                "state": "receipt_handle_exact",
                "handle": f"receipt:step-{step}:action-{step}:cmd",
                "sha256": str(step) * 64,
                "bytes": 100 + step,
            },
        }],
        "missing_outcome_receipt_ids": [],
        "exact_access_state": "available",
    }
    return {
        "latest_primary_result": latest,
        "runtime_identity": {
            "task_id": "task-a", "run_id": "run-a",
            "primary_agent_id": "primary:run-a", "workspace_id": "/app",
            "environment_id": "env-a",
        },
        "available_capabilities": {"action_kinds": ["read_file", "run_command"]},
        "budgets": {
            "max_kernel_steps": 10,
            "used_solver_provider_turns": step,
            "remaining_kernel_steps": 10 - step,
        },
        "evidence_index": [deepcopy(latest["outcome_receipts"][0])],
        "linked_history": {"artifacts_present": [f"artifact-{step}.txt"]},
        "unresolved_runtime_facts": [],
        "self_extension": {
            "enabled": True,
            "task_local_dir": ".aether/tools",
            "smoke_test_required": True,
            "trust_for_completion": False,
        },
    }


def test_representation_contract_is_self_describing_transport_semantics_only() -> None:
    assert "previous projected snapshot" in REPRESENTATION_CONTRACT
    assert "top-level keys in set" in REPRESENTATION_CONTRACT
    assert "top-level keys in clear" in REPRESENTATION_CONTRACT
    assert "omitted_unchanged_top_level_keys are unchanged" in REPRESENTATION_CONTRACT
    assert "strategy" not in REPRESENTATION_CONTRACT.lower()
    assert "action" not in REPRESENTATION_CONTRACT.lower()


def test_full_snapshot_round_trip_is_exact_and_does_not_mutate_input() -> None:
    current = continuity_fresh_delta_reanchor(_packet(1))
    original = deepcopy(current)
    envelope = full_snapshot_envelope(current)
    reconstructed = reconstruct_snapshot(None, envelope)
    assert envelope["mode"] == FULL_MODE
    assert reconstructed == current
    assert snapshot_sha256(reconstructed) == envelope["result_snapshot_sha256"]
    assert current == original


def test_delta_only_round_trip_reconstructs_exact_existing_v1_projection() -> None:
    previous = continuity_fresh_delta_reanchor(_packet(1))
    current = continuity_fresh_delta_reanchor(_packet(2))
    envelope = delta_snapshot_envelope(previous, current)
    reconstructed = reconstruct_snapshot(previous, envelope)
    assert envelope["mode"] == DELTA_MODE
    assert reconstructed == current
    assert reconstructed == continuity_fresh_delta_reanchor(_packet(2))
    assert envelope["base_snapshot_sha256"] == snapshot_sha256(previous)
    assert envelope["result_snapshot_sha256"] == snapshot_sha256(current)


def test_delta_represents_set_clear_and_unchanged_without_nested_compaction() -> None:
    previous = {
        "same": {"nested": [1, 2, 3]},
        "changed": {"value": "old", "keep_shape": True},
        "deleted": {"must": "clear"},
    }
    current = {
        "same": {"nested": [1, 2, 3]},
        "changed": {"value": "new", "keep_shape": True},
        "added": {"full": ["section", "preserved"]},
    }
    envelope = delta_snapshot_envelope(previous, current)
    assert envelope["set"] == {
        "added": current["added"],
        "changed": current["changed"],
    }
    assert envelope["clear"] == ["deleted"]
    assert envelope["omitted_unchanged_top_level_keys"] == ["same"]
    assert reconstruct_snapshot(previous, envelope) == current


def test_transport_forces_full_on_first_turn_and_explicit_parent_loss_reanchor() -> None:
    first = continuity_fresh_delta_reanchor(_packet(1))
    second = continuity_fresh_delta_reanchor(_packet(2))
    assert transport_envelope(first, previous=None)["mode"] == FULL_MODE
    assert transport_envelope(second, previous=first)["mode"] == DELTA_MODE
    forced = transport_envelope(second, previous=first, force_full=True)
    assert forced["mode"] == FULL_MODE
    assert reconstruct_snapshot(None, forced) == second


def test_delta_rejects_stale_base_and_tampered_result() -> None:
    previous = continuity_fresh_delta_reanchor(_packet(1))
    current = continuity_fresh_delta_reanchor(_packet(2))
    envelope = delta_snapshot_envelope(previous, current)
    stale = continuity_fresh_delta_reanchor(_packet(3))
    with pytest.raises(ValueError, match="base snapshot mismatch"):
        reconstruct_snapshot(stale, envelope)

    tampered = deepcopy(envelope)
    tampered["set"]["budgets"]["remaining_kernel_steps"] = 999
    with pytest.raises(ValueError, match="result snapshot hash mismatch"):
        reconstruct_snapshot(previous, tampered)


def test_delta_rejects_hidden_or_ambiguous_transport_fields() -> None:
    previous = {"same": 1, "deleted": 2}
    current = {"same": 1, "added": 3}
    envelope = delta_snapshot_envelope(previous, current)

    extra = deepcopy(envelope)
    extra["semantic_summary"] = "not transport authority"
    with pytest.raises(ValueError, match="shape mismatch"):
        reconstruct_snapshot(previous, extra)

    ambiguous = deepcopy(envelope)
    ambiguous["omitted_unchanged_top_level_keys"].append("added")
    ambiguous["omitted_unchanged_top_level_keys"].sort()
    with pytest.raises(ValueError, match="cannot be transmitted changes"):
        reconstruct_snapshot(previous, ambiguous)


def test_delta_envelope_is_deep_copy_isolated_from_later_snapshot_mutation() -> None:
    previous = {"same": {"v": 1}}
    current = {"same": {"v": 1}, "new": {"values": [1, 2]}}
    envelope = delta_snapshot_envelope(previous, current)
    current["new"]["values"].append(3)
    assert envelope["set"]["new"] == {"values": [1, 2]}
    assert reconstruct_snapshot(previous, envelope) == {
        "same": {"v": 1}, "new": {"values": [1, 2]}
    }

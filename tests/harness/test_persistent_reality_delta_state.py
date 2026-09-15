from __future__ import annotations

import pytest

from aether.persistent_reality_delta import DELTA_MODE, FULL_MODE
from aether.persistent_reality_delta_state import RealityDeltaTransportState


def _snapshot(turn: int) -> dict:
    return {
        "runtime_identity": {"task_id": "task-a", "run_id": "run-a"},
        "latest_primary_result": {"action_id": f"action-{turn}", "status": "succeeded"},
        "budgets": {"remaining_kernel_steps": 10 - turn},
        "stable": {"capabilities": ["read_file", "run_command"]},
    }


def _commit(
    state: RealityDeltaTransportState,
    *,
    turn: int,
    previous_response_id: str | None,
    response_id: str,
) -> str:
    prepared = state.prepare(
        _snapshot(turn), run_id="run-a", task_id="task-a",
        previous_response_id=previous_response_id,
    )
    state.stage_candidate(prepared, response_id=response_id)
    state.commit_candidate(run_id="run-a", task_id="task-a", response_id=response_id)
    return prepared.mode


def test_first_turn_full_then_exact_parent_uses_delta_only() -> None:
    state = RealityDeltaTransportState()
    assert _commit(
        state, turn=1, previous_response_id=None, response_id="resp-1"
    ) == FULL_MODE
    prepared = state.prepare(
        _snapshot(2), run_id="run-a", task_id="task-a",
        previous_response_id="resp-1",
    )
    assert prepared.mode == DELTA_MODE
    assert prepared.envelope["base_snapshot_sha256"] == state.committed_identity(
        run_id="run-a", task_id="task-a"
    )["snapshot_sha256"]


def test_mismatched_or_missing_provider_parent_forces_full_reanchor() -> None:
    state = RealityDeltaTransportState()
    _commit(state, turn=1, previous_response_id=None, response_id="resp-1")
    mismatched = state.prepare(
        _snapshot(2), run_id="run-a", task_id="task-a",
        previous_response_id="different-parent",
    )
    missing = state.prepare(
        _snapshot(2), run_id="run-a", task_id="task-a",
        previous_response_id=None,
    )
    assert mismatched.mode == FULL_MODE
    assert missing.mode == FULL_MODE


def test_rejected_candidate_does_not_advance_committed_delta_base() -> None:
    state = RealityDeltaTransportState()
    _commit(state, turn=1, previous_response_id=None, response_id="resp-1")
    before = state.committed_identity(run_id="run-a", task_id="task-a")

    prepared = state.prepare(
        _snapshot(2), run_id="run-a", task_id="task-a",
        previous_response_id="resp-1",
    )
    assert prepared.mode == DELTA_MODE
    state.stage_candidate(prepared, response_id="resp-rejected")
    state.reject_candidate(
        run_id="run-a", task_id="task-a", response_id="resp-rejected"
    )
    assert state.committed_identity(run_id="run-a", task_id="task-a") == before

    retry = state.prepare(
        _snapshot(3), run_id="run-a", task_id="task-a",
        previous_response_id="resp-1",
    )
    assert retry.mode == DELTA_MODE


def test_explicit_parent_loss_clear_forces_next_full_snapshot() -> None:
    state = RealityDeltaTransportState()
    _commit(state, turn=1, previous_response_id=None, response_id="resp-1")
    state.clear_scope(run_id="run-a", task_id="task-a")
    assert state.committed_identity(run_id="run-a", task_id="task-a") is None
    prepared = state.prepare(
        _snapshot(2), run_id="run-a", task_id="task-a",
        previous_response_id=None,
    )
    assert prepared.mode == FULL_MODE


def test_scope_isolation_prevents_cross_task_delta_reuse() -> None:
    state = RealityDeltaTransportState()
    _commit(state, turn=1, previous_response_id=None, response_id="resp-1")
    other = state.prepare(
        _snapshot(2), run_id="run-b", task_id="task-b",
        previous_response_id="resp-1",
    )
    assert other.mode == FULL_MODE
    assert state.committed_identity(run_id="run-b", task_id="task-b") is None


def test_pending_candidate_blocks_second_prepare_until_admitted_or_rejected() -> None:
    state = RealityDeltaTransportState()
    first = state.prepare(
        _snapshot(1), run_id="run-a", task_id="task-a", previous_response_id=None
    )
    state.stage_candidate(first, response_id="resp-1")
    with pytest.raises(RuntimeError, match="pending candidate"):
        state.prepare(
            _snapshot(2), run_id="run-a", task_id="task-a", previous_response_id=None
        )
    state.reject_candidate(run_id="run-a", task_id="task-a", response_id="resp-1")
    assert state.prepare(
        _snapshot(2), run_id="run-a", task_id="task-a", previous_response_id=None
    ).mode == FULL_MODE


def test_stage_fails_if_provider_parent_drifts_after_prepare() -> None:
    state = RealityDeltaTransportState()
    _commit(state, turn=1, previous_response_id=None, response_id="resp-1")
    prepared = state.prepare(
        _snapshot(2), run_id="run-a", task_id="task-a", previous_response_id="resp-1"
    )
    # Simulate an explicit recovery reset between request preparation and response staging.
    state.clear_scope(run_id="run-a", task_id="task-a")
    with pytest.raises(RuntimeError, match="lost its committed base"):
        state.stage_candidate(prepared, response_id="resp-2")


def test_commit_and_reject_require_exact_candidate_response_identity() -> None:
    state = RealityDeltaTransportState()
    prepared = state.prepare(
        _snapshot(1), run_id="run-a", task_id="task-a", previous_response_id=None
    )
    state.stage_candidate(prepared, response_id="resp-1")
    with pytest.raises(RuntimeError, match="commit response identity mismatch"):
        state.commit_candidate(run_id="run-a", task_id="task-a", response_id="wrong")
    with pytest.raises(RuntimeError, match="reject response identity mismatch"):
        state.reject_candidate(run_id="run-a", task_id="task-a", response_id="wrong")
    state.commit_candidate(run_id="run-a", task_id="task-a", response_id="resp-1")
    assert state.committed_identity(run_id="run-a", task_id="task-a")["response_id"] == "resp-1"

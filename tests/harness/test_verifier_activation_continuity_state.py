from __future__ import annotations

from copy import deepcopy

import pytest

from aether.verifier_activation_continuity import (
    FRESH_CONTROL,
    PREVIOUS_RESPONSE_V1,
    PREFIX,
    VerifierActivationContinuityState,
    apply_delta,
)


def _snapshot(turn: int) -> list[dict]:
    rows = [
        {"role": "system", "content": "verifier authority"},
        {"role": "user", "content": {"task": "fixed", "checks": ["alpha"]}},
    ]
    if turn >= 2:
        rows.append({
            "role": "user",
            "content": {
                "verifier_inspection_results": [
                    {"inspection_id": "inspection:1", "stdout": "ok"},
                    *(
                        [{"inspection_id": "inspection:2", "stdout": "later"}]
                        if turn >= 3 else []
                    ),
                ],
                "available_authoritative_source_refs": [
                    "inspection:1",
                    *(["inspection:2"] if turn >= 3 else []),
                ],
            },
        })
    return rows


def _stage_commit(
    state: VerifierActivationContinuityState,
    snapshot,
    *,
    activation: str = "activation-1",
    response: str = "resp-1",
    call: str = "call-1",
    mode: str = PREVIOUS_RESPONSE_V1,
):
    prepared = state.prepare(
        snapshot,
        mode=mode,
        run_id="run-a",
        task_id="task-a",
        activation_id=activation,
    )
    state.stage_candidate(prepared, response_id=response, call_id=call)
    state.commit_candidate(
        run_id="run-a",
        task_id="task-a",
        activation_id=activation,
        response_id=response,
    )
    return prepared


def test_treatment_first_call_is_full_and_second_is_exact_lossless_delta() -> None:
    state = VerifierActivationContinuityState()
    first = _stage_commit(state, _snapshot(1))
    assert first.transport_kind == "full_snapshot"
    assert first.previous_response_id is None
    assert first.previous_call_id is None
    assert first.rendered == _snapshot(1)

    second = state.prepare(
        _snapshot(2),
        mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a",
        task_id="task-a",
        activation_id="activation-1",
    )
    assert second.transport_kind == "delta"
    assert second.previous_response_id == "resp-1"
    assert second.previous_call_id == "call-1"
    assert isinstance(second.rendered, str) and second.rendered.startswith(PREFIX)
    assert second.envelope is not None
    assert apply_delta(_snapshot(1), second.envelope) == _snapshot(2)


def test_control_is_always_fresh_even_after_committed_candidate() -> None:
    state = VerifierActivationContinuityState()
    _stage_commit(state, _snapshot(1), mode=FRESH_CONTROL)
    second = state.prepare(
        _snapshot(2), mode=FRESH_CONTROL,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    assert second.transport_kind == "full_snapshot"
    assert second.previous_response_id is None
    assert second.previous_call_id is None
    assert second.rendered == _snapshot(2)


def test_pending_candidate_blocks_new_prepare_until_admitted() -> None:
    state = VerifierActivationContinuityState()
    prepared = state.prepare(
        _snapshot(1), mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    state.stage_candidate(prepared, response_id="resp-1", call_id="call-1")
    with pytest.raises(ValueError, match="requires admission"):
        state.prepare(
            _snapshot(2), mode=PREVIOUS_RESPONSE_V1,
            run_id="run-a", task_id="task-a", activation_id="activation-1",
        )


def test_reject_does_not_advance_snapshot_base_but_burns_native_ids() -> None:
    state = VerifierActivationContinuityState()
    _stage_commit(state, _snapshot(1))
    second = state.prepare(
        _snapshot(2), mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    state.stage_candidate(second, response_id="resp-2", call_id="call-2")
    assert state.reject_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1", response_id="resp-2"
    ) is True

    third = state.prepare(
        _snapshot(3), mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    assert third.previous_response_id == "resp-1"
    assert third.previous_call_id == "call-1"
    assert third.envelope is not None
    assert apply_delta(_snapshot(1), third.envelope) == _snapshot(3)

    with pytest.raises(ValueError, match="response_id reuse forbidden"):
        state.stage_candidate(third, response_id="resp-2", call_id="call-3")
    with pytest.raises(ValueError, match="call_id reuse forbidden"):
        state.stage_candidate(third, response_id="resp-3", call_id="call-2")


def test_commit_requires_exact_pending_response_id() -> None:
    state = VerifierActivationContinuityState()
    prepared = state.prepare(
        _snapshot(1), mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    state.stage_candidate(prepared, response_id="resp-1", call_id="call-1")
    with pytest.raises(ValueError, match="commit response_id mismatch"):
        state.commit_candidate(
            run_id="run-a", task_id="task-a", activation_id="activation-1", response_id="wrong"
        )
    committed = state.commit_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1", response_id="resp-1"
    )
    assert committed["response_id"] == "resp-1"


def test_new_activation_cannot_see_prior_activation_parent() -> None:
    state = VerifierActivationContinuityState()
    _stage_commit(state, _snapshot(1), activation="activation-1")
    fresh = state.prepare(
        _snapshot(2), mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-2",
    )
    assert fresh.transport_kind == "full_snapshot"
    assert fresh.previous_response_id is None
    assert fresh.previous_call_id is None


def test_same_activation_name_is_still_scoped_by_run_and_task() -> None:
    state = VerifierActivationContinuityState()
    _stage_commit(state, _snapshot(1), activation="activation-1")
    for run_id, task_id in (("run-b", "task-a"), ("run-a", "task-b")):
        fresh = state.prepare(
            _snapshot(2), mode=PREVIOUS_RESPONSE_V1,
            run_id=run_id, task_id=task_id, activation_id="activation-1",
        )
        assert fresh.transport_kind == "full_snapshot"
        assert fresh.previous_response_id is None


def test_clear_forces_full_but_never_releases_seen_native_ids() -> None:
    state = VerifierActivationContinuityState()
    _stage_commit(state, _snapshot(1), activation="activation-1")
    state.clear_activation(run_id="run-a", task_id="task-a", activation_id="activation-1")
    fresh = state.prepare(
        _snapshot(2), mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    assert fresh.transport_kind == "full_snapshot"
    with pytest.raises(ValueError, match="response_id reuse forbidden"):
        state.stage_candidate(fresh, response_id="resp-1", call_id="call-new")
    with pytest.raises(ValueError, match="call_id reuse forbidden"):
        state.stage_candidate(fresh, response_id="resp-new", call_id="call-1")


def test_global_identifier_guard_rejects_cross_activation_reuse() -> None:
    state = VerifierActivationContinuityState()
    _stage_commit(state, _snapshot(1), activation="activation-1")
    fresh = state.prepare(
        _snapshot(1), mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-2",
    )
    with pytest.raises(ValueError, match="response_id reuse forbidden"):
        state.stage_candidate(fresh, response_id="resp-1", call_id="call-2")
    with pytest.raises(ValueError, match="call_id reuse forbidden"):
        state.stage_candidate(fresh, response_id="resp-2", call_id="call-1")


def test_snapshot_inputs_are_deep_copy_isolated_from_later_mutation() -> None:
    state = VerifierActivationContinuityState()
    original = _snapshot(1)
    expected = deepcopy(original)
    prepared = state.prepare(
        original, mode=PREVIOUS_RESPONSE_V1,
        run_id="run-a", task_id="task-a", activation_id="activation-1",
    )
    original.append({"role": "user", "content": {"mutation": True}})
    state.stage_candidate(prepared, response_id="resp-1", call_id="call-1")
    state.commit_candidate(
        run_id="run-a", task_id="task-a", activation_id="activation-1", response_id="resp-1"
    )
    committed = state.committed_identity(
        run_id="run-a", task_id="task-a", activation_id="activation-1"
    )
    assert committed is not None
    assert committed["snapshot"] == expected


def test_unknown_mode_and_empty_scope_fail_closed() -> None:
    state = VerifierActivationContinuityState()
    with pytest.raises(ValueError, match="unsupported"):
        state.prepare(
            _snapshot(1), mode="invented",
            run_id="run-a", task_id="task-a", activation_id="activation-1",
        )
    with pytest.raises(ValueError, match="requires run_id"):
        state.prepare(
            _snapshot(1), mode=PREVIOUS_RESPONSE_V1,
            run_id="", task_id="task-a", activation_id="activation-1",
        )

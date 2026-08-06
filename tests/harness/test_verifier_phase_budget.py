"""Deterministic checks for the generic verifier phase budget."""
from __future__ import annotations

import pytest

from aether.verifier_budget import (
    VerifierBudgetError,
    VerifierPhaseBudget,
    VerifierPhaseState,
)
from aether.verifier_inspector import VerifierInspectionRequest


def _read(index: int) -> VerifierInspectionRequest:
    return VerifierInspectionRequest(request_id=f"read-{index}", kind="read_file", path=f"input-{index}.txt")


def _derived() -> VerifierInspectionRequest:
    return VerifierInspectionRequest(
        request_id="derive", kind="overlay_run_command", command="python3 check.py",
        evidence_mode="derived", basis_refs=("inspection:source",),
        bound_input_refs=("inspection:source",),
    )


def test_eight_independent_reads_fit_one_investigation_batch_then_leave_verify_available() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget())

    assert state.classify_and_reserve(tuple(_read(index) for index in range(8))) == "INVESTIGATE"
    assert state.investigation_batches == 1
    assert state.classify_and_reserve((_derived(),)) == "VERIFY"
    assert state.derived_execution_batches == 1


def test_mixed_direct_and_dependent_derived_requests_are_rejected() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget())

    with pytest.raises(VerifierBudgetError, match="either independent direct observations or derived executions"):
        state.classify_and_reserve((_read(1), _derived()))


def test_byte_and_time_budget_fail_precisely() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget(max_result_bytes_per_request=64, max_result_bytes_per_batch=96, max_tool_execution_s_per_batch=2))
    state.classify_and_reserve((VerifierInspectionRequest(request_id="read-1", kind="read_file", path="input.txt", span=64),))

    with pytest.raises(VerifierBudgetError, match="per-result byte budget"):
        state.validate_results(({"request_id": "read-1", "excerpt": "x" * 128},), elapsed_s=0.1)
    with pytest.raises(VerifierBudgetError, match="tool-execution budget"):
        state.validate_results(({"request_id": "read-1", "excerpt": "ok"},), elapsed_s=3)


def test_revisions_and_protocol_correction_have_independent_buckets() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget(max_investigation_batches=2, max_derived_execution_batches=2, max_protocol_corrections=1))
    state.reserve_protocol_correction()
    assert state.classify_and_reserve((_read(1),)) == "INVESTIGATE"
    assert state.classify_and_reserve((_read(2),)) == "INVESTIGATE"
    assert state.classify_and_reserve((_derived(),)) == "VERIFY"
    second = VerifierInspectionRequest(
        request_id="derive-2", kind="overlay_run_command", command="python3 check-again.py",
        evidence_mode="derived", basis_refs=("inspection:source",),
        bound_input_refs=("inspection:source",),
    )
    assert state.classify_and_reserve((second,)) == "VERIFY"
    with pytest.raises(VerifierBudgetError, match="investigation-batch budget"):
        state.classify_and_reserve((_read(3),))
    with pytest.raises(VerifierBudgetError, match="protocol-correction budget"):
        state.reserve_protocol_correction()


def test_default_investigation_ceiling_allows_initial_batch_plus_two_revisions() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget())

    assert state.classify_and_reserve((_read(1),)) == "INVESTIGATE"
    assert state.classify_and_reserve((_read(2),)) == "INVESTIGATE"
    assert state.classify_and_reserve((_read(3),)) == "INVESTIGATE"
    with pytest.raises(VerifierBudgetError, match="investigation-batch budget"):
        state.classify_and_reserve((_read(4),))


def test_structural_budget_corrections_have_a_separate_bounded_bucket() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget(max_protocol_corrections=1, max_budget_corrections=2))

    state.reserve_protocol_correction()
    state.reserve_budget_correction()
    state.reserve_budget_correction()
    with pytest.raises(VerifierBudgetError, match="budget-correction budget"):
        state.reserve_budget_correction()


def test_provider_and_model_protocol_corrections_have_separate_buckets() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget(
        max_protocol_corrections=1,
        max_provider_corrections=1,
    ))

    state.reserve_protocol_correction()
    state.reserve_provider_correction()

    with pytest.raises(VerifierBudgetError, match="protocol-correction budget"):
        state.reserve_protocol_correction()
    with pytest.raises(VerifierBudgetError, match="provider-correction budget"):
        state.reserve_provider_correction()


def test_equivalent_requests_and_model_calls_are_bounded_but_verdict_has_no_inspection_slot() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget(max_model_calls=2))
    reads = (_read(1),)
    state.classify_and_reserve(reads)
    with pytest.raises(VerifierBudgetError, match="equivalent"):
        state.classify_and_reserve(reads)
    state.reserve_model_call()
    state.reserve_model_call()
    assert state.has_model_call_capacity is False
    # A verdict consumes no investigation or verification batch; its model
    # call is bounded separately above.
    assert state.investigation_batches == 1
    assert state.derived_execution_batches == 0

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
    with pytest.raises(VerifierBudgetError, match="duplicate_inspection_no_new_information"):
        state.classify_and_reserve(reads)
    state.reserve_model_call()
    state.reserve_model_call()
    assert state.has_model_call_capacity is False
    # A verdict consumes no investigation or verification batch; its model
    # call is bounded separately above.
    assert state.investigation_batches == 1
    assert state.derived_execution_batches == 0


def test_renamed_direct_read_is_neutrally_bounded_as_no_new_information() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget())
    first = VerifierInspectionRequest(
        request_id="read-first", kind="read_file", path="current.txt",
        span=512, clause_ids=("one",), proof_ids=("proof-one",),
        claim="the first narrative claim", method_summary="first method",
        proxy_risk="first proxy risk",
    )
    renamed = VerifierInspectionRequest(
        request_id="read-renamed", kind="read_file", path="current.txt",
        span=512, clause_ids=("two",), proof_ids=("proof-two",),
        claim="a different narrative claim", method_summary="different method",
        proxy_risk="different proxy risk",
    )
    assert state.classify_and_reserve((first,)) == "INVESTIGATE"
    with pytest.raises(VerifierBudgetError, match="duplicate_inspection_no_new_information"):
        state.classify_and_reserve((renamed,))
    assert state.investigation_batches == 1


def test_reordered_direct_batch_is_information_equivalent() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget())
    first = VerifierInspectionRequest(
        request_id="read-a", kind="read_file", path="a.txt", span=128,
        claim="claim a", proof_ids=("proof-a",), clause_ids=("clause-a",),
    )
    second = VerifierInspectionRequest(
        request_id="read-b", kind="read_file", path="b.txt", span=256,
        claim="claim b", proof_ids=("proof-b",), clause_ids=("clause-b",),
    )
    reordered_first = VerifierInspectionRequest(
        request_id="renamed-b", kind="read_file", path="b.txt", span=256,
        claim="another claim b", proof_ids=("other-proof-b",), clause_ids=("other-clause-b",),
    )
    reordered_second = VerifierInspectionRequest(
        request_id="renamed-a", kind="read_file", path="a.txt", span=128,
        claim="another claim a", proof_ids=("other-proof-a",), clause_ids=("other-clause-a",),
    )
    assert state.classify_and_reserve((first, second)) == "INVESTIGATE"
    with pytest.raises(VerifierBudgetError, match="duplicate_inspection_no_new_information"):
        state.classify_and_reserve((reordered_first, reordered_second))
    assert state.investigation_batches == 1


def test_changed_execution_bound_is_not_suppressed_as_duplicate() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget())
    first = VerifierInspectionRequest(
        request_id="read", kind="read_file", path="current.txt", span=128,
    )
    larger = VerifierInspectionRequest(
        request_id="read-renamed", kind="read_file", path="current.txt", span=256,
        claim="different claim is irrelevant, span is not",
    )
    assert state.classify_and_reserve((first,)) == "INVESTIGATE"
    assert state.classify_and_reserve((larger,)) == "INVESTIGATE"
    assert state.investigation_batches == 2


def test_production_verifier_phase_is_bounded_to_empirically_qualified_four_calls() -> None:
    from aether.verifier_budget import PRODUCTION_VERIFIER_PHASE_BUDGET
    state = VerifierPhaseState(PRODUCTION_VERIFIER_PHASE_BUDGET)
    for _ in range(4):
        state.reserve_model_call()
    assert state.model_calls == 4
    assert state.has_model_call_capacity is False
    with pytest.raises(VerifierBudgetError, match="model-call budget exhausted"):
        state.reserve_model_call()


def test_production_verifier_admits_third_and_later_distinct_derived_batches() -> None:
    from aether.verifier_budget import PRODUCTION_VERIFIER_PHASE_BUDGET
    state = VerifierPhaseState(PRODUCTION_VERIFIER_PHASE_BUDGET)
    for index in range(5):
        request = VerifierInspectionRequest(
            request_id=f"derive-{index}",
            kind="overlay_run_command",
            command=f"printf %s {index}",
            evidence_mode="derived",
            basis_refs=("inspection:source",),
            bound_input_refs=("inspection:source",),
        )
        assert state.classify_and_reserve((request,)) == "VERIFY"
    assert state.derived_execution_batches == 5

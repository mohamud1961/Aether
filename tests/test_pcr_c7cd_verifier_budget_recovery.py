"""Regressions for C7CD verifier-budget invalidity discovered in live PCR pairs."""
from __future__ import annotations

import json
import tempfile

import pytest

from aether.verifier_budget import VerifierBudgetError, VerifierPhaseBudget, VerifierPhaseState
from aether.verifier_inspector import VerifierInspectionRequest
from aether.verifier_overlay import VerifierOverlay
from aether.real_executor import SubprocessExecutor
from aether.verify_completion_protocol import _budget_correction_payload


def _read(span: int = 8192) -> VerifierInspectionRequest:
    return VerifierInspectionRequest(request_id="read-max", kind="read_file", path="graph.ttl", span=span)


def _read_result(excerpt: str, **extra):
    row = {
        "request_id": "read-max",
        "kind": "read_file",
        "path": "graph.ttl",
        "requested_path": "graph.ttl",
        "bytes": len(excerpt),
        "offset": 0,
        "span": len(excerpt),
        "anchor": "offset",
        "content_hash": "a" * 16,
        "excerpt": excerpt,
        "observation_origin": "executor_read",
        "read_only": True,
    }
    row.update(extra)
    return row


def test_legal_max_span_read_with_provenance_metadata_is_admissible() -> None:
    """A request advertised as legal must not fail merely because metadata adds bytes."""
    budget = VerifierPhaseBudget()
    state = VerifierPhaseState(budget)
    state.classify_and_reserve((_read(budget.max_result_bytes_per_request),))
    row = _read_result("x" * budget.max_result_bytes_per_request)
    assert len(json.dumps(row, sort_keys=True).encode("utf-8")) > budget.max_result_bytes_per_request
    state.validate_results((row,), elapsed_s=0.1)


def test_content_over_request_limit_remains_rejected() -> None:
    budget = VerifierPhaseBudget()
    state = VerifierPhaseState(budget)
    row = _read_result("x" * (budget.max_result_bytes_per_request + 1))
    with pytest.raises(VerifierBudgetError, match="content byte budget"):
        state.validate_results((row,), elapsed_s=0.1)


def test_serialized_envelope_is_still_independently_bounded() -> None:
    budget = VerifierPhaseBudget(max_result_envelope_bytes_per_request=9000)
    state = VerifierPhaseState(budget)
    row = _read_result("x" * 8000, unexpected_metadata="y" * 4000)
    with pytest.raises(VerifierBudgetError, match="envelope byte budget"):
        state.validate_results((row,), elapsed_s=0.1)


def test_batch_serialized_envelope_budget_remains_bounded() -> None:
    budget = VerifierPhaseBudget(
        max_result_bytes_per_request=8192,
        max_result_envelope_bytes_per_request=16384,
        max_result_bytes_per_batch=10000,
    )
    state = VerifierPhaseState(budget)
    rows = (_read_result("x" * 4900), _read_result("y" * 4900, request_id="read-2"))
    with pytest.raises(VerifierBudgetError, match="aggregate byte budget"):
        state.validate_results(rows, elapsed_s=0.1)


def test_overlay_command_budget_excludes_custody_overhead_when_execution_time_is_reported() -> None:
    budget = VerifierPhaseBudget(max_tool_execution_s_per_batch=30, max_tool_lifecycle_s_per_batch=120)
    state = VerifierPhaseState(budget)
    row = {
        "request_id": "verify",
        "kind": "overlay_run_command",
        "stdout": "PASS",
        "stderr": "",
        "success": True,
        "tool_execution_elapsed_s": 0.5,
    }
    # Reproduces the C7CD shape: inspector wall time can exceed 30 seconds
    # even when the actual verifier-authored check is cheap.
    state.validate_results((row,), elapsed_s=35.0)


def test_overlay_command_actual_execution_still_obeys_30_second_bound() -> None:
    budget = VerifierPhaseBudget(max_tool_execution_s_per_batch=30, max_tool_lifecycle_s_per_batch=120)
    state = VerifierPhaseState(budget)
    row = {
        "request_id": "verify",
        "kind": "overlay_run_command",
        "stdout": "",
        "stderr": "",
        "success": True,
        "tool_execution_elapsed_s": 30.01,
    }
    with pytest.raises(VerifierBudgetError, match="tool-execution budget"):
        state.validate_results((row,), elapsed_s=35.0)


def test_overlay_lifecycle_remains_fail_closed_under_separate_wall_bound() -> None:
    budget = VerifierPhaseBudget(max_tool_execution_s_per_batch=30, max_tool_lifecycle_s_per_batch=120)
    state = VerifierPhaseState(budget)
    row = {
        "request_id": "verify",
        "kind": "overlay_run_command",
        "stdout": "PASS",
        "stderr": "",
        "success": True,
        "tool_execution_elapsed_s": 0.5,
    }
    with pytest.raises(VerifierBudgetError, match="tool-lifecycle budget"):
        state.validate_results((row,), elapsed_s=120.01)


def test_real_overlay_reports_command_only_execution_elapsed_time() -> None:
    with tempfile.TemporaryDirectory() as root:
        overlay = VerifierOverlay(SubprocessExecutor(root), root)
        try:
            row = overlay.run_command("python3 -c \"print('PASS')\"")
            assert row["success"] is True
            assert isinstance(row.get("tool_execution_elapsed_s"), float)
            assert 0 <= row["tool_execution_elapsed_s"] <= 30
            VerifierPhaseState(VerifierPhaseBudget()).validate_results((row,), elapsed_s=35.0)
        finally:
            overlay.teardown()


def test_envelope_budget_correction_names_separate_envelope_ceiling() -> None:
    budget = VerifierPhaseBudget()
    payload = _budget_correction_payload(
        VerifierBudgetError("verifier inspection result envelope exceeded per-result envelope byte budget"),
        budget,
    )
    assert payload["budget_limits"]["max_result_bytes_per_request"] == 8192
    assert payload["budget_limits"]["max_result_envelope_bytes_per_request"] == 16384
    assert payload["budget_limits"]["max_result_bytes_per_batch"] == 65536


def test_lifecycle_budget_correction_is_distinct_from_command_execution_limit() -> None:
    budget = VerifierPhaseBudget()
    payload = _budget_correction_payload(
        VerifierBudgetError("verifier inspection batch exceeded tool-lifecycle budget"),
        budget,
    )
    assert payload["budget_limits"] == {"max_tool_lifecycle_s_per_batch": 120}
    assert "setup and teardown" in payload["instruction"]


def test_duplicate_inspection_correction_is_factual_not_strategic() -> None:
    payload = _budget_correction_payload(
        VerifierBudgetError("duplicate_inspection_no_new_information"),
        VerifierPhaseBudget(),
    )
    assert payload["duplicate_inspection_no_new_information"] is True
    assert "not a semantic verdict" in payload["instruction"]


def test_pcr_provider_batch_cardinality_matches_aggregate_envelope_budget() -> None:
    """PCR must not advertise a batch that can be runtime-invalid by size alone."""
    from aether.providers.azure_model import _PCR_VERIFIER_DIRECT_TURN_SCHEMA, _VERIFIER_DIRECT_TURN_SCHEMA
    from aether.verifier_budget import PRODUCTION_VERIFIER_PHASE_BUDGET

    budget = PRODUCTION_VERIFIER_PHASE_BUDGET
    max_by_envelope = budget.max_result_bytes_per_batch // budget.max_result_envelope_bytes_per_request
    assert max_by_envelope == 4

    pcr_defs = _PCR_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    assert pcr_defs["direct_inspect_turn"]["properties"]["requests"]["maxItems"] == max_by_envelope
    assert pcr_defs["derived_inspect_turn"]["properties"]["requests"]["maxItems"] == max_by_envelope
    assert pcr_defs["verdict_turn"]["properties"]["missing_inspection_requests"]["maxItems"] == max_by_envelope

    # Generic/ASV transport remains unchanged; this repair is PCR-only.
    generic_defs = _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    assert generic_defs["direct_inspect_turn"]["properties"]["requests"]["maxItems"] == 12
    assert generic_defs["derived_inspect_turn"]["properties"]["requests"]["maxItems"] == 12

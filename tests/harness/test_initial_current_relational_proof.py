from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger
from aether.proof_contract import CompiledProofRequirement, evaluate_compiled_proof_requirements
from aether.providers.azure_model import _PERSISTENT_VERIFIER_DIRECT_TURN_SCHEMA, _VERIFIER_DIRECT_TURN_SCHEMA
from aether.runners.docker_exec_executor import DockerExecExecutor
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.verifier_budget import VerifierPhaseBudget, VerifierPhaseState
from aether.verifier_inspector import VerifierInspectionRequest, execute_verifier_inspection_requests, parse_verifier_inspection_requests


class _RelationalExecutor:
    def compare_initial_path(self, path: str):
        assert path == "out.txt"
        return {
            "path": "out.txt",
            "initial": {"present": True, "kind": "file", "bytes": 3, "sha256": "a" * 64, "stable": True},
            "current": {"present": True, "kind": "file", "bytes": 3, "sha256": "a" * 64, "stable": True},
            "relation": "equal",
            "equal": True,
            "current_stable": True,
            "initial_snapshot_digest": "b" * 64,
            "relation_digest": "c" * 64,
        }


def _compiled():
    env = EnvMap(
        task_prompt="Preserve out.txt.", workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor("filesystem", "Files"),
            "shell": CapabilityDescriptor("shell", "Shell"),
        },
    )
    ir = RuntimeConfigIR(
        architect_summary="relational test", solver_identity_prompt="solver",
        verifier_identity_prompt="verifier", selected_capabilities=("filesystem", "shell"),
    )
    return env, ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(ir, env)


def _requirement() -> CompiledProofRequirement:
    return CompiledProofRequirement(
        proof_id="proof-rel", obligation_ids=("preserve",), risk_ids=("accidental_change",),
        proof_kind="independent_comparison",
        acceptance_observation="initial and current exact identity are equal",
        falsification_observation="initial and current exact identity differ",
        minimum_evidence_class="exact_contract", verifier_origin_required=True,
        independent_derivation_required=True, direct_perception_required=False,
    )


def test_generic_and_persistent_provider_schema_expose_initial_current_comparator() -> None:
    generic_kinds = _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["inspection_request"]["properties"]["kind"]["enum"]
    assert "compare_initial_path" in generic_kinds
    persistent_kind_enum = _PERSISTENT_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["persistent_direct_locator_request"]["properties"]["kind"]["enum"]
    assert "compare_initial_path" in persistent_kind_enum
    parsed = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{"request_id": "rel", "kind": "compare_initial_path", "path": "out.txt", "proof_ids": ["proof-rel"]}],
    })
    assert parsed == (VerifierInspectionRequest(request_id="rel", kind="compare_initial_path", path="out.txt", proof_ids=("proof-rel",)),)


def test_comparator_is_direct_budget_not_derived_shell_budget() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget())
    phase = state.classify_and_reserve((VerifierInspectionRequest(request_id="rel", kind="compare_initial_path", path="out.txt"),))
    assert phase == "INVESTIGATE"
    assert state.investigation_batches == 1
    assert state.derived_execution_batches == 0


def test_typed_comparator_is_verdict_eligible_independent_exact_proof() -> None:
    env, compiled = _compiled()
    ledger = ExecutionLedger()
    request = VerifierInspectionRequest(request_id="rel", kind="compare_initial_path", path="out.txt", proof_ids=("proof-rel",))
    raw = execute_verifier_inspection_requests((request,), compiled=compiled, ledger=ledger, executor=_RelationalExecutor(), envmap=env)
    rows = register_inspection_results(
        (request,), raw, ledger=ledger, step=1, requester="model_verifier",
        executor=_RelationalExecutor(), overlay=None, packet_signature="packet-rel",
    )
    assert len(rows) == 1
    assert rows[0]["admissibility"] == "verdict_eligible"
    assert rows[0]["actual_evidence_class"] == "exact_contract"
    assert rows[0]["observation_type"] == "relational_comparison"
    assert rows[0]["target_generation"].startswith("relation_digest:")
    decision = evaluate_compiled_proof_requirements((_requirement(),), ledger, {"proof-rel": (rows[0]["inspection_id"],)})[0]
    assert decision.admitted is True
    assert decision.code == "proof_evidence_admitted"


def test_docker_executor_comparator_uses_frozen_generation_zero_copy() -> None:
    with tempfile.TemporaryDirectory() as current, tempfile.TemporaryDirectory() as initial:
        Path(current, "out.txt").write_text("ABC")
        Path(initial, "out.txt").write_text("ABC")
        executor = DockerExecExecutor("unused-container-id", current, initial_snapshot_host_root=initial)
        equal = executor.compare_initial_path("/app/out.txt")
        assert equal["relation"] == "equal"
        assert equal["current_stable"] is True
        assert len(equal["initial_snapshot_digest"]) == 64
        assert len(equal["relation_digest"]) == 64
        assert equal["initial"]["sha256"] == equal["current"]["sha256"]
        Path(current, "out.txt").write_text("XYZ")
        changed = executor.compare_initial_path("out.txt")
        assert changed["relation"] == "different"
        assert changed["initial"]["sha256"] != changed["current"]["sha256"]
        assert Path(initial, "out.txt").read_text() == "ABC"


def test_docker_executor_comparator_reports_created_and_removed() -> None:
    with tempfile.TemporaryDirectory() as current, tempfile.TemporaryDirectory() as initial:
        Path(initial, "removed.txt").write_text("OLD")
        Path(current, "created.txt").write_text("NEW")
        executor = DockerExecExecutor("unused-container-id", current, initial_snapshot_host_root=initial)
        assert executor.compare_initial_path("removed.txt")["relation"] == "removed"
        assert executor.compare_initial_path("created.txt")["relation"] == "created"
        assert executor.compare_initial_path("never.txt")["relation"] == "absent_both"


def test_docker_executor_comparator_rejects_escape_and_missing_baseline() -> None:
    with tempfile.TemporaryDirectory() as current, tempfile.TemporaryDirectory() as initial:
        executor = DockerExecExecutor("unused-container-id", current, initial_snapshot_host_root=initial)
        with pytest.raises(ValueError, match="normalized"):
            executor.compare_initial_path("../outside.txt")
        with pytest.raises(ValueError, match="inside the task workspace"):
            executor.compare_initial_path("/etc/passwd")
    with tempfile.TemporaryDirectory() as current:
        executor = DockerExecExecutor("unused-container-id", current)
        with pytest.raises(RuntimeError, match="initial workspace snapshot is unavailable"):
            executor.compare_initial_path("x.txt")


def test_h2_preservation_proof_survives_post_repair_without_solver_preread() -> None:
    """Regression for r9 H2_AB_M0's missing pre-repair baseline deadlock.

    The Solver is allowed to mutate the intended implementation file first.
    Protected files are never pre-read by the Solver.  The immutable generation-0
    snapshot must still let the Verifier establish their preservation afterward.
    """
    with tempfile.TemporaryDirectory() as current, tempfile.TemporaryDirectory() as initial:
        for root in (current, initial):
            Path(root, "codec.py").write_text("old-codec")
            Path(root, "protected_contract.py").write_text("DO NOT CHANGE")
            Path(root, "protected_schema.json").write_text('{"version":1}')
        # The task repair happens before the preservation proof.  No historical
        # read receipt is needed because generation-0 custody is harness-owned.
        Path(current, "codec.py").write_text("repaired-codec")
        executor = DockerExecExecutor(
            "unused-container-id", current, initial_snapshot_host_root=initial,
        )
        assert executor.compare_initial_path("codec.py")["relation"] == "different"
        for protected in ("protected_contract.py", "protected_schema.json"):
            proof = executor.compare_initial_path(protected)
            assert proof["relation"] == "equal"
            assert proof["equal"] is True
            assert proof["current_stable"] is True
            assert proof["initial"]["sha256"] == proof["current"]["sha256"]

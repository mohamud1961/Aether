from __future__ import annotations

import tempfile
from pathlib import Path

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.inspection_registry import admissible_verdict_refs, register_inspection_results
from aether.ledger import ExecutionLedger
from aether.verifier_inspector import (
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
    invalid_authoritative_source_refs,
)
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.verifier_overlay import VerifierOverlay
from aether.verify_inspection_requests import _bound_input_refs_from_inspections


class _Executor:
    pass


def _register(
    ledger: ExecutionLedger,
    request: VerifierInspectionRequest,
    result: dict,
    *,
    step: int,
) -> dict:
    return register_inspection_results(
        (request,),
        (result,),
        ledger=ledger,
        step=step,
        requester="model_verifier",
        executor=_Executor(),
        overlay=_Executor(),
        packet_signature="packet",
    )[0]


def test_overlay_fixture_is_causal_input_but_never_proof_authority() -> None:
    ledger = ExecutionLedger()
    source_request = VerifierInspectionRequest(
        request_id="source-filter",
        kind="read_file",
        path="filter.py",
    )
    source_row = _register(
        ledger,
        source_request,
        {
            "request_id": "source-filter",
            "kind": "read_file",
            "path": "filter.py",
            "content_hash": "source-v1",
            "excerpt": "def main(): pass",
            "observation_origin": "executor_read",
        },
        step=7,
    )
    source_ref = source_row["inspection_id"]

    fixture_request = VerifierInspectionRequest(
        request_id="fixture-safe-boundary",
        kind="overlay_write_fixture",
        path="tmp/filter_verify.html",
        content="<p>safe</p>",
    )
    fixture_row = _register(
        ledger,
        fixture_request,
        {
            "request_id": "fixture-safe-boundary",
            "kind": "overlay_write_fixture",
            "path": "tmp/filter_verify.html",
            "executed_in": "verifier_overlay",
            "success": True,
        },
        step=7,
    )
    fixture_ref = fixture_row["inspection_id"]

    direct, derived = admissible_verdict_refs(ledger)
    assert source_ref in direct
    assert fixture_ref not in direct
    assert fixture_ref not in derived
    assert fixture_row["admissibility"] == "exploratory"
    assert fixture_row["eligible_for_proof"] is False
    assert fixture_ref in _bound_input_refs_from_inspections(
        (fixture_request,), (fixture_row,)
    )


def test_prior_overlay_fixture_can_bind_execution_without_entering_basis() -> None:
    ledger = ExecutionLedger()
    source_request = VerifierInspectionRequest(
        request_id="source-filter", kind="read_file", path="filter.py"
    )
    source_row = _register(
        ledger,
        source_request,
        {
            "request_id": "source-filter",
            "kind": "read_file",
            "path": "filter.py",
            "content_hash": "source-v1",
            "excerpt": "source",
            "observation_origin": "executor_read",
        },
        step=7,
    )
    source_ref = source_row["inspection_id"]

    fixture_request = VerifierInspectionRequest(
        request_id="fixture-safe-boundary",
        kind="overlay_write_fixture",
        path="tmp/filter_verify.html",
        content="<p>safe</p>",
    )
    fixture_row = _register(
        ledger,
        fixture_request,
        {
            "request_id": "fixture-safe-boundary",
            "kind": "overlay_write_fixture",
            "path": "tmp/filter_verify.html",
            "executed_in": "verifier_overlay",
            "success": True,
        },
        step=7,
    )
    fixture_ref = fixture_row["inspection_id"]

    request = VerifierInspectionRequest(
        request_id="verify-untouched-identity",
        kind="overlay_run_command",
        command="python3 verify.py tmp/filter_verify.html filter.py",
        evidence_mode="derived",
        basis_refs=(source_ref,),
        bound_input_refs=(source_ref, fixture_ref),
    )
    assert invalid_authoritative_source_refs(
        (request,),
        available_refs={source_ref},
        available_input_refs={source_ref, fixture_ref},
    ) == ()

    execution_row = _register(
        ledger,
        request,
        {
            "request_id": "verify-untouched-identity",
            "kind": "overlay_run_command",
            "executed_in": "verifier_overlay",
            "observation_origin": "verifier_overlay",
            "exit_code": 0,
            "success": True,
            "stdout": "identity preserved",
        },
        step=7,
    )
    execution_ref = execution_row["inspection_id"]
    direct, derived = admissible_verdict_refs(ledger)
    assert source_ref in direct
    assert fixture_ref not in direct
    assert fixture_ref not in derived
    assert execution_ref in derived
    assert execution_row["admissibility"] == "verdict_eligible"
    assert execution_row["eligible_for_proof"] is True


def test_overlay_fixture_remains_illegal_as_authoritative_basis() -> None:
    request = VerifierInspectionRequest(
        request_id="verify-untouched-identity",
        kind="overlay_run_command",
        command="python3 verify.py",
        evidence_mode="derived",
        basis_refs=("inspection:7:0:source-filter", "inspection:7:2:fixture-safe-boundary"),
        bound_input_refs=("inspection:7:0:source-filter", "inspection:7:2:fixture-safe-boundary"),
    )
    errors = invalid_authoritative_source_refs(
        (request,),
        available_refs={"inspection:7:0:source-filter"},
        available_input_refs={
            "inspection:7:0:source-filter",
            "inspection:7:2:fixture-safe-boundary",
        },
    )
    assert errors == (
        "verify-untouched-identity: unavailable authoritative basis refs inspection:7:2:fixture-safe-boundary",
    )


def test_unregistered_fixture_cannot_bind_execution_input() -> None:
    request = VerifierInspectionRequest(
        request_id="derive",
        kind="overlay_run_command",
        command="python3 verify.py",
        evidence_mode="derived",
        basis_refs=("inspection:source",),
        bound_input_refs=("inspection:source", "inspection:missing-fixture"),
    )
    errors = invalid_authoritative_source_refs(
        (request,),
        available_refs={"inspection:source"},
        available_input_refs={"inspection:source"},
    )
    assert errors == (
        "derive: unknown or not-yet-observed bound input refs inspection:missing-fixture",
    )


def test_bound_fixture_receipt_materializes_only_in_the_derived_command_child() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "source.txt").write_text("authoritative", encoding="utf-8")
        env = EnvMap(
            task_prompt="Use source.txt and an independent verifier fixture.",
            workspace_root=root,
            capabilities={
                "shell": CapabilityDescriptor("shell", "Run commands"),
                "filesystem": CapabilityDescriptor("filesystem", "Files"),
            },
        )
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(env))
        compiled = compiler.compile(
            RuntimeConfigIR(
                architect_summary="fixture binding",
                solver_identity_prompt="solver",
                verifier_identity_prompt="verifier",
                selected_capabilities=("shell", "filesystem"),
            ),
            env,
        )
        ledger = ExecutionLedger()
        executor = SubprocessExecutor(root)
        overlay = VerifierOverlay(executor, root)
        try:
            source_request = VerifierInspectionRequest(
                request_id="source", kind="read_file", path="source.txt",
            )
            source_raw = execute_verifier_inspection_requests(
                (source_request,), compiled=compiled, ledger=ledger,
                executor=executor, envmap=env, overlay=overlay,
            )
            source_row = register_inspection_results(
                (source_request,), source_raw, ledger=ledger, step=3,
                requester="model_verifier", executor=executor, overlay=overlay,
                packet_signature="packet",
            )[0]
            source_ref = source_row["inspection_id"]

            fixture_request = VerifierInspectionRequest(
                request_id="fixture", kind="overlay_write_fixture",
                path="fixtures/input.txt", content="BOUND",
            )
            fixture_raw = execute_verifier_inspection_requests(
                (fixture_request,), compiled=compiled, ledger=ledger,
                executor=executor, envmap=env, overlay=overlay,
            )
            fixture_row = register_inspection_results(
                (fixture_request,), fixture_raw, ledger=ledger, step=3,
                requester="model_verifier", executor=executor, overlay=overlay,
                packet_signature="packet",
            )[0]
            fixture_ref = fixture_row["inspection_id"]
            assert fixture_raw[0]["success"] is True
            assert fixture_ref in _bound_input_refs_from_inspections(
                (fixture_request,), (fixture_row,)
            )

            derived = VerifierInspectionRequest(
                request_id="derive", kind="overlay_run_command",
                command="cat fixtures/input.txt",
                evidence_mode="derived", basis_refs=(source_ref,),
                bound_input_refs=(source_ref, fixture_ref),
            )
            derived_raw = execute_verifier_inspection_requests(
                (derived,), compiled=compiled, ledger=ledger,
                executor=executor, envmap=env, overlay=overlay,
            )
            assert derived_raw[0]["success"] is True, derived_raw[0]
            assert derived_raw[0]["stdout"] == "BOUND"
            assert derived_raw[0]["materialized_fixture_paths"] == ["fixtures/input.txt"]
            derived_row = register_inspection_results(
                (derived,), derived_raw, ledger=ledger, step=3,
                requester="model_verifier", executor=executor, overlay=overlay,
                packet_signature="packet",
            )[0]
            assert derived_row["admissibility"] == "verdict_eligible"

            # The same registered fixture is not ambient state. A command that
            # omits its fixture ref starts from pristine task state and cannot
            # see the fixture.
            unbound = VerifierInspectionRequest(
                request_id="unbound", kind="overlay_run_command",
                command="test ! -e fixtures/input.txt",
                evidence_mode="derived", basis_refs=(source_ref,),
                bound_input_refs=(source_ref,),
            )
            unbound_raw = execute_verifier_inspection_requests(
                (unbound,), compiled=compiled, ledger=ledger,
                executor=executor, envmap=env, overlay=overlay,
            )
            assert unbound_raw[0]["success"] is True, unbound_raw[0]
            assert unbound_raw[0]["materialized_fixture_paths"] == []
            assert not Path(root, "fixtures").exists()
        finally:
            overlay.teardown()
            executor.close()

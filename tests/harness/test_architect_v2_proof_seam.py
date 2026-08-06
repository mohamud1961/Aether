from __future__ import annotations

from typing import Any

from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger, Receipt
from aether.proof_contract import (
    CompiledProofRequirement,
    compile_proof_requirements,
    evaluate_compiled_proof_requirements,
)
from aether.runtime_ir import RuntimeConfigIR
from aether.verifier_inspector import VerifierInspectionRequest


class _Executor:
    pass


def _requirements(*, proof_kind: str = "exact_state", proof_id: str = "proof-a", obligation_ids: tuple[str, ...] = ("obligation-a",)) -> tuple[CompiledProofRequirement, ...]:
    return compile_proof_requirements(({
        "proof_id": proof_id,
        "obligation_refs": list(obligation_ids),
        "proof_kind": proof_kind,
        "acceptance_observation": "The selected current observation establishes the obligation.",
        "falsification_observation": "A contradictory selected observation disproves the obligation.",
    },))


def _register(
    ledger: ExecutionLedger,
    request: VerifierInspectionRequest,
    result: dict[str, Any],
    *,
    step: int = 1,
    requester: str = "model_verifier",
) -> str:
    return register_inspection_results(
        (request,), (result,), ledger=ledger, step=step, requester=requester,
        executor=_Executor(), overlay=_Executor(), packet_signature="packet",
    )[0]["inspection_id"]


def test_compiled_requirement_is_route_independent_and_mechanically_typed() -> None:
    requirement = _requirements(proof_kind="independent_comparison")[0]
    assert requirement.minimum_evidence_class == "exact_contract"
    assert requirement.verifier_origin_required is True
    assert requirement.independent_derivation_required is True
    assert requirement.direct_perception_required is False
    encoded = requirement.as_dict()
    assert "inspection_route" not in encoded
    assert "route" not in encoded
    assert "acceptance_observation" in encoded


def test_current_verifier_origin_exact_state_receipt_is_admitted() -> None:
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="read-state", kind="read_file", path="result.json",
            proof_ids=("proof-a",),
        ),
        {"request_id": "read-state", "kind": "read_file", "path": "result.json", "bytes": 5, "offset": 0, "span": 4000, "excerpt": "state", "content_hash": "a" * 16, "observation_origin": "executor_read"},
    )
    decision = evaluate_compiled_proof_requirements(
        _requirements(), ledger, {"proof-a": (inspection_id,)},
    )[0]
    assert decision.admitted is True
    assert decision.code == "proof_evidence_admitted"


def test_solver_only_claim_is_not_a_verifier_origin_receipt() -> None:
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="solver-read", kind="read_file", path="result.json",
            proof_ids=("proof-a",),
        ),
        {"request_id": "solver-read", "kind": "read_file", "path": "result.json", "bytes": 5, "offset": 0, "span": 4000, "excerpt": "state", "content_hash": "a" * 16, "observation_origin": "executor_read"},
        requester="solver",
    )
    decision = evaluate_compiled_proof_requirements(
        _requirements(), ledger, {"proof-a": (inspection_id,)},
    )[0]
    assert decision.admitted is False
    assert decision.code == "proof_evidence_not_admitted"


def test_stale_verifier_receipt_is_rejected() -> None:
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="read-state", kind="read_file", path="result.json",
            proof_ids=("proof-a",),
        ),
        {"request_id": "read-state", "kind": "read_file", "path": "result.json", "bytes": 5, "offset": 0, "span": 4000, "excerpt": "state", "content_hash": "a" * 16, "observation_origin": "executor_read"},
    )
    ledger.record(Receipt(
        receipt_id="mutation", step=2, kind="write_file", success=True,
        summary="changed state", state_change=True, payload={"modified_paths": ["result.json"]},
    ))
    decision = evaluate_compiled_proof_requirements(
        _requirements(), ledger, {"proof-a": (inspection_id,)},
    )[0]
    assert decision.admitted is False
    assert decision.code == "stale_proof_evidence"


def test_insufficient_evidence_class_is_rejected() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="weak", step=1, kind="inspection_record", success=True,
        summary="weak observation", payload={
            "inspection_id": "weak",
            "requester": "model_verifier",
            "route_kind": "read_file",
            "route_parameters": {"proof_ids": ["proof-a"]},
            "admissibility": "direct_admissible",
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "metadata_proxy",
            "task_state_generation": ledger.task_state_generation(),
        },
    ))
    decision = evaluate_compiled_proof_requirements(
        _requirements(), ledger, {"proof-a": ("weak",)},
    )[0]
    assert decision.admitted is False
    assert decision.code == "proof_evidence_not_admitted"


def test_unsupported_mutating_inspection_action_is_rejected() -> None:
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="write-fixture", kind="overlay_write_fixture", path="result.json",
            proof_ids=("proof-a",),
        ),
        {
            "request_id": "write-fixture", "kind": "overlay_write_fixture",
            "executed_in": "verifier_overlay", "success": True,
        },
    )
    decision = evaluate_compiled_proof_requirements(
        _requirements(), ledger, {"proof-a": (inspection_id,)},
    )[0]
    assert decision.admitted is False


def test_unregistered_inspection_receipt_is_rejected() -> None:
    decision = evaluate_compiled_proof_requirements(
        _requirements(), ExecutionLedger(), {"proof-a": ("missing",)},
    )[0]
    assert decision.admitted is False
    assert decision.code == "unregistered_inspection"


def test_public_behavior_cannot_use_arbitrary_solver_output() -> None:
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="solver-output", kind="read_output", handle="solver-output",
            proof_ids=("proof-behavior",),
        ),
        {
            "request_id": "solver-output", "kind": "read_output",
            "handle": "solver-output", "excerpt": "HTTP 200",
            "source_receipt_id": "solver-output", "content_hash": "v1",
            "observation_origin": "ledger_output",
        },
    )
    decision = evaluate_compiled_proof_requirements(
        _requirements(proof_kind="public_behavior", proof_id="proof-behavior"),
        ledger,
        {"proof-behavior": (inspection_id,)},
    )[0]
    assert decision.admitted is False


def test_public_behavior_accepts_fresh_verifier_http_observation() -> None:
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="http", kind="probe_http", target="http://127.0.0.1:5328",
            proof_ids=("proof-behavior",),
        ),
        {
            "request_id": "http", "kind": "probe_http",
            "url": "http://127.0.0.1:5328", "status_code": 200,
            "response_observed": True, "observation_origin": "executor_probe",
        },
    )
    decision = evaluate_compiled_proof_requirements(
        _requirements(proof_kind="public_behavior", proof_id="proof-behavior"),
        ledger,
        {"proof-behavior": (inspection_id,)},
    )[0]
    assert decision.admitted is True


def test_independent_comparison_requires_bound_derived_execution() -> None:
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="input.dat"),
        {"request_id": "source", "kind": "read_file", "path": "input.dat", "bytes": 5, "offset": 0, "span": 4000, "excerpt": "state", "content_hash": "a" * 16, "observation_origin": "executor_read"},
    )
    direct = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="direct", kind="read_file", path="output.dat",
            proof_ids=("proof-compare",),
        ),
        {"request_id": "direct", "kind": "read_file", "path": "output.dat", "bytes": 5, "offset": 0, "span": 4000, "excerpt": "state", "content_hash": "a" * 16, "observation_origin": "executor_read"},
    )
    direct_decision = evaluate_compiled_proof_requirements(
        _requirements(proof_kind="independent_comparison", proof_id="proof-compare"),
        ledger,
        {"proof-compare": (direct,)},
    )[0]
    assert direct_decision.admitted is False

    derived = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command", command="python3 compare.py",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
            proof_ids=("proof-compare",),
        ),
        {
            "request_id": "derive", "kind": "overlay_run_command",
            "executed_in": "verifier_overlay", "stdout": "match", "exit_code": 0,
            "success": True, "observation_origin": "verifier_overlay",
        },
        step=2,
    )
    derived_decision = evaluate_compiled_proof_requirements(
        _requirements(proof_kind="independent_comparison", proof_id="proof-compare"),
        ledger,
        {"proof-compare": (derived,)},
    )[0]
    assert derived_decision.admitted is True


def test_direct_perception_requires_perceptual_route_and_evidence() -> None:
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="perception", kind="perceive_artifact", path="frame.png",
            proof_ids=("proof-vision",),
        ),
        {
            "request_id": "perception", "kind": "perceive_artifact",
            "path": "frame.png", "content_hash": "frame-v1",
            "transcription": "independent visual observation",
            "observation_origin": "vision_executor",
        },
    )
    decision = evaluate_compiled_proof_requirements(
        _requirements(proof_kind="direct_perception", proof_id="proof-vision"),
        ledger,
        {"proof-vision": (inspection_id,)},
    )[0]
    assert decision.admitted is True


def test_one_requirement_can_cover_multiple_obligations() -> None:
    requirement = _requirements(
        proof_kind="public_behavior", proof_id="proof-shared",
        obligation_ids=("obligation-a", "obligation-b"),
    )[0]
    assert requirement.obligation_ids == ("obligation-a", "obligation-b")
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="http", kind="probe_http", target="http://127.0.0.1:80",
            proof_ids=("proof-shared",),
        ),
        {"request_id": "http", "kind": "probe_http", "url": "http://127.0.0.1:80", "status_code": 200,
         "response_observed": True, "observation_origin": "executor_probe"},
    )
    decision = evaluate_compiled_proof_requirements(
        (requirement,), ledger, {"proof-shared": (inspection_id,)},
    )[0]
    assert decision.admitted is True


def test_v1_runtime_has_empty_optional_seam_by_default() -> None:
    ir = RuntimeConfigIR(
        architect_summary="legacy",
        solver_identity_prompt="legacy solver",
        selected_capabilities=("filesystem",),
    )
    assert ir.proof_requirements == ()


def test_v1_inspection_receipts_do_not_gain_empty_seam_metadata() -> None:
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="legacy-read", kind="read_file", path="result.json",
        ),
        {"request_id": "legacy-read", "kind": "read_file", "path": "result.json", "content_hash": "v1"},
    )
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection_id)
    assert "proof_ids" not in receipt.payload
    assert "execution_scope" not in receipt.payload
    assert "proof_ids" not in receipt.payload["route_parameters"]



def test_f79_exact_route_ceiling_cannot_launder_metadata_actual_strength() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="weak-actual", step=1, kind="inspection_record", success=True,
        summary="partial read from an exact-capable route", payload={
            "inspection_id": "weak-actual",
            "requester": "model_verifier",
            "route_kind": "read_file",
            "route_parameters": {"proof_ids": ["proof-a"]},
            "admissibility": "direct_admissible",
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "metadata_proxy",
            "task_state_generation": ledger.task_state_generation(),
        },
    ))
    decision = evaluate_compiled_proof_requirements(
        _requirements(), ledger, {"proof-a": ("weak-actual",)},
    )[0]
    assert decision.admitted is False
    assert decision.code == "proof_evidence_not_admitted"

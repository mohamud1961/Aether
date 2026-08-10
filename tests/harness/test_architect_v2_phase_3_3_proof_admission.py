from __future__ import annotations

from dataclasses import replace
from typing import Any

from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger
from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.proof_contract import (
    PROOF_REGISTRY_DIGEST,
    PROOF_REGISTRY_VERSION,
    compile_proof_requirements,
    evaluate_compiled_proof_requirements,
    evaluate_shadow_proof_evidence_admission,
    proof_requirements_identity,
)
from aether.verifier import CompletionEvidenceEntry, MethodValidityRecord, ModelVerifierResult
from aether.verifier_inspector import VerifierInspectionRequest
from aether.verify_completion_gates import _completion_record_problem
from aether.verify_completion_protocol import _invalid_shadow_proof_bindings
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.verifier_packets import build_verifier_packet


class _Executor:
    pass


def _requirements():
    return compile_proof_requirements(({
        "proof_id": "proof-a",
        "obligation_refs": ["obligation-a"],
        "proof_kind": "exact_state",
        "acceptance_observation": "The current observation establishes the obligation.",
        "falsification_observation": "A contradictory observation disproves the obligation.",
    },))


def _register(
    ledger: ExecutionLedger,
    request: VerifierInspectionRequest,
    result: dict[str, Any],
    *,
    packet_signature: str = "packet-current",
    proof_contract_identity: str = "",
    step: int = 1,
) -> str:
    return register_inspection_results(
        (request,), (result,), ledger=ledger, step=step,
        requester="model_verifier", executor=_Executor(), overlay=_Executor(),
        packet_signature=packet_signature,
        proof_contract_identity=proof_contract_identity,
    )[0]["inspection_id"]


def _completed(proof_ids=("proof-a",), refs=("inspection:1:0:read",)) -> ModelVerifierResult:
    return ModelVerifierResult(
        verdict="completed",
        summary="current state observed",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="the obligation is satisfied",
            observed="the verifier observed the required current state",
            falsification_check="a contradictory current observation would disprove it",
            inspection_refs=tuple(refs),
            proof_ids=tuple(proof_ids),
        ),),
    )


def test_registry_identity_is_stable_and_embedded_in_requirements() -> None:
    requirement = _requirements()[0]
    assert requirement.registry_version == PROOF_REGISTRY_VERSION
    assert requirement.registry_digest == PROOF_REGISTRY_DIGEST
    assert proof_requirements_identity(_requirements()) == proof_requirements_identity(_requirements())
    assert requirement.as_dict()["registry_digest"] == PROOF_REGISTRY_DIGEST


def test_nonzero_exit_is_not_success_even_when_success_flag_is_true() -> None:
    ledger = ExecutionLedger()
    requirements = _requirements()
    identity = proof_requirements_identity(requirements)
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="failed-command", kind="overlay_run_command", command="check",
            evidence_mode="derived", basis_refs=("source",), bound_input_refs=("source",),
            proof_ids=("proof-a",),
        ),
        {
            "request_id": "failed-command", "kind": "overlay_run_command",
            "executed_in": "verifier_overlay", "observation_origin": "verifier_overlay",
            "success": True, "exit_code": 1, "stdout": "failure",
        },
        proof_contract_identity=identity,
    )
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection_id)
    assert receipt.success is False
    decision = evaluate_compiled_proof_requirements(
        requirements, ledger, {"proof-a": (inspection_id,)},
        packet_signature="packet-current", proof_contract_identity=identity,
    )[0]
    assert decision.admitted is False


def test_shadow_proof_admission_requires_completed_verifier_verdict() -> None:
    requirements = _requirements()
    result = ModelVerifierResult(verdict="needs_repair", summary="not complete")
    evaluation = evaluate_shadow_proof_evidence_admission(
        result, requirements, ExecutionLedger(),
        packet_signature="packet-current",
        proof_contract_identity=proof_requirements_identity(requirements),
    )
    assert evaluation.admitted is False
    assert any("completed Verifier verdict" in problem for problem in evaluation.problems)


def test_shadow_completion_requires_exact_proof_id_coverage() -> None:
    requirements = _requirements()
    ledger = ExecutionLedger()
    result = _completed(proof_ids=())
    evaluation = evaluate_shadow_proof_evidence_admission(
        result, requirements, ledger,
        packet_signature="packet-current",
        proof_contract_identity=proof_requirements_identity(requirements),
    )
    assert evaluation.admitted is False
    assert any("proof_ids is empty" in problem for problem in evaluation.problems)


def test_shadow_completion_rejects_unknown_and_duplicate_proof_ids() -> None:
    requirements = _requirements()
    class _Entry:
        proof_ids = ("proof-a", "proof-a", "unknown-proof")
        inspection_refs = ("inspection:1:0:read",)
        observed = "observed"
        falsification_check = "falsifier"
    result = ModelVerifierResult(verdict="completed", summary="x", completion_evidence=(_Entry(),))
    evaluation = evaluate_shadow_proof_evidence_admission(
        result, requirements, ExecutionLedger(), packet_signature="packet-current",
        proof_contract_identity=proof_requirements_identity(requirements),
    )
    assert evaluation.admitted is False
    assert any("duplicates" in problem for problem in evaluation.problems)
    assert any("unknown proof_id" in problem for problem in evaluation.problems)


def test_proof_id_request_validation_is_fail_closed_before_execution() -> None:
    requirement = _requirements()[0]
    request = VerifierInspectionRequest(
        request_id="bad-proof", kind="read_file", path="result.json",
        proof_ids=("proof-a", "proof-a", "unknown-proof"),
    )
    assert _invalid_shadow_proof_bindings((request,), type("Compiled", (), {
        "proof_requirements": (requirement,),
    })())


def test_typed_shadow_read_requires_executor_origin() -> None:
    requirements = _requirements()
    identity = proof_requirements_identity(requirements)
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(request_id="read", kind="read_file", path="result.json", proof_ids=("proof-a",)),
        {"request_id": "read", "kind": "read_file", "path": "result.json", "content_hash": "v1"},
        proof_contract_identity=identity,
    )
    decision = evaluate_compiled_proof_requirements(
        requirements, ledger, {"proof-a": (inspection_id,)},
        packet_signature="packet-current", proof_contract_identity=identity,
    )[0]
    assert decision.admitted is False


def test_current_round_and_contract_identity_are_required() -> None:
    requirements = _requirements()
    identity = proof_requirements_identity(requirements)
    ledger = ExecutionLedger()
    inspection_id = _register(
        ledger,
        VerifierInspectionRequest(request_id="read", kind="read_file", path="result.json", proof_ids=("proof-a",)),
        {"request_id": "read", "kind": "read_file", "path": "result.json", "content_hash": "v1", "observation_origin": "executor_read"},
        packet_signature="old-packet", proof_contract_identity=identity,
    )
    decision = evaluate_compiled_proof_requirements(
        requirements, ledger, {"proof-a": (inspection_id,)},
        packet_signature="new-packet", proof_contract_identity=identity,
    )[0]
    assert decision.admitted is False


def test_registry_mismatch_is_not_compatibility_admission() -> None:
    requirements = _requirements()
    mismatched = replace(requirements[0], registry_digest="old-digest")
    decision = evaluate_compiled_proof_requirements(
        (mismatched,), ExecutionLedger(), {"proof-a": ()},
    )[0]
    assert decision.code == "proof_registry_mismatch"
    assert decision.admitted is False


def test_independent_comparison_requires_method_validity_to_bind_current_receipts() -> None:
    requirements = compile_proof_requirements(({
        "proof_id": "proof-compare",
        "obligation_refs": ["obligation-a"],
        "proof_kind": "independent_comparison",
        "acceptance_observation": "the independent execution agrees",
        "falsification_observation": "a disagreement disproves the claim",
    },))
    identity = proof_requirements_identity(requirements)
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="input.dat"),
        {"request_id": "source", "kind": "read_file", "path": "input.dat",
         "bytes": 5, "offset": 0, "span": 4000, "excerpt": "state",
         "content_hash": "a" * 16, "observation_origin": "executor_read"},
    )
    derived = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command", command="compare",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
            proof_ids=("proof-compare",),
        ),
        {"request_id": "derive", "kind": "overlay_run_command",
         "executed_in": "verifier_overlay", "observation_origin": "verifier_overlay",
         "success": True, "exit_code": 0, "stdout": "match"},
        proof_contract_identity=identity, step=2,
    )
    result = ModelVerifierResult(
        verdict="completed", summary="independent execution observed",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="the obligation is satisfied", observed="match",
            falsification_check="a mismatch would disprove it",
            inspection_refs=(derived,), proof_ids=("proof-compare",),
        ),),
        method_validity=MethodValidityRecord(
            observed_structure="source observed", executed_rule="compare",
            method_alignment="the rule measures the determinant",
            authoritative_source_refs=(source,), execution_ref=derived,
        ),
    )
    evaluation = evaluate_shadow_proof_evidence_admission(
        result, requirements, ledger, packet_signature="packet-current",
        proof_contract_identity=identity,
    )
    assert evaluation.admitted is True


def test_shadow_completion_record_problem_preserves_model_text_boundary() -> None:
    result = _completed()
    problem = _completion_record_problem(
        result,
        {"inspection:1:0:read"},
        packet={"compiled_proof_requirements": [{"proof_id": "proof-a"}]},
    )
    assert problem == ""
    assert result.completion_evidence[0].observed == "the verifier observed the required current state"


def test_shadow_requirements_are_visible_only_when_compiled() -> None:
    envmap = EnvMap(
        task_prompt="write the deliverable",
        workspace_root="/app",
        visible_files=("input.txt",),
        capabilities={
            "filesystem": CapabilityDescriptor(capability_id="filesystem", summary="read files"),
            "shell": CapabilityDescriptor(capability_id="shell", summary="run commands"),
        },
    )
    compiled = ConfigCompiler(CapabilityRegistry.from_envmap(envmap)).compile(
        RuntimeConfigIR(
            architect_summary="summary",
            solver_identity_prompt="solver",
            selected_capabilities=("filesystem", "shell"),
            proof_requirements=_requirements(),
        ),
        envmap,
    )
    packet = build_verifier_packet(compiled, ExecutionLedger(), envmap=envmap)
    assert packet["compiled_proof_requirements"][0]["proof_id"] == "proof-a"
    assert packet["proof_requirements_identity"] == compiled.proof_requirements_identity

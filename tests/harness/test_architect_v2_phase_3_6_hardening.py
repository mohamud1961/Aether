from __future__ import annotations

from aether.completion import CompletionGate
from aether.ledger import ExecutionLedger, Receipt
from aether.proof_contract import (
    PROOF_REGISTRY_DIGEST,
    PROOF_REGISTRY_VERSION,
    compile_proof_requirements,
    proof_requirements_identity,
)
from aether.runtime_ir import (
    BootstrapPolicy,
    CompiledRuntime,
    CompletionPolicy,
    ContextPolicy,
    EvalIndex,
    HelperToolPolicy,
    ObjectiveGraph,
    ProcessPolicy,
    ReconfigurePolicy,
    RefusalPolicy,
)


def _requirements():
    return compile_proof_requirements(({
        "proof_id": "proof-a",
        "obligation_refs": ["obligation-a"],
        "proof_kind": "exact_state",
        "acceptance_observation": "Current state matches the obligation.",
        "falsification_observation": "A current mismatch disproves it.",
    },))


def _compiled() -> CompiledRuntime:
    requirements = _requirements()
    return CompiledRuntime(
        task_prompt="test task",
        env_digest="env",
        objective_graph=ObjectiveGraph(),
        eval_index=EvalIndex(),
        selected_capabilities=(),
        stable_prefix_sections=(),
        context_policy=ContextPolicy(),
        process_policy=ProcessPolicy(),
        helper_tool_policy=HelperToolPolicy(),
        bootstrap_policy=BootstrapPolicy(),
        completion_policy=CompletionPolicy(
            require_authoritative_check=False,
            allow_evidence_fallback=True,
            require_all_obligations=False,
            require_recent_progress=False,
            require_clean_integrity=False,
        ),
        refusal_policy=RefusalPolicy(),
        reconfigure_policy=ReconfigurePolicy(),
        enforced_monitors=(),
        check_plan_ids=(),
        forbidden_paths=(),
        proof_requirements=requirements,
        proof_requirements_identity=proof_requirements_identity(requirements),
    )


def _record_shadow_pair(
    ledger: ExecutionLedger,
    compiled: CompiledRuntime,
    *,
    verdict: str = "completed",
    packet_signature: str = "packet-current",
) -> None:
    verifier_id = "step-2:model_verifier"
    common = {
        "packet_signature": packet_signature,
        "task_state_generation": ledger.task_state_generation(),
        "proof_contract_identity": compiled.proof_requirements_identity,
        "proof_registry_version": PROOF_REGISTRY_VERSION,
        "proof_registry_digest": PROOF_REGISTRY_DIGEST,
    }
    ledger.record(Receipt(
        receipt_id="step-2:proof_evidence_admission",
        step=2,
        kind="proof_evidence_admission",
        success=True,
        summary="kernel proof evidence admitted",
        payload={
            **common,
            "admitted": True,
            "verifier_result_receipt_id": verifier_id,
            "verifier_verdict": verdict,
        },
    ))
    ledger.record(Receipt(
        receipt_id=verifier_id,
        step=2,
        kind="model_verifier_result",
        success=verdict == "completed",
        summary=f"model verifier verdict: {verdict}",
        payload={**common, "verdict": verdict},
    ))


def test_current_completed_verdict_and_admission_pass_gate() -> None:
    compiled = _compiled()
    ledger = ExecutionLedger()
    _record_shadow_pair(ledger, compiled)
    assert CompletionGate().evaluate(compiled, ledger, []).ready is True


def test_state_mutation_after_admission_invalidates_gate() -> None:
    compiled = _compiled()
    ledger = ExecutionLedger()
    _record_shadow_pair(ledger, compiled)
    ledger.record(Receipt(
        receipt_id="step-3:mutation",
        step=3,
        kind="run_command",
        success=True,
        summary="state changed after verification",
        state_change=True,
        payload={"command": "touch later"},
    ))
    decision = CompletionGate().evaluate(compiled, ledger, [])
    assert decision.ready is False
    assert "proof_evidence_not_admitted" in {item.code for item in decision.blockers}


def test_noncompleted_verifier_result_cannot_use_successful_admission() -> None:
    compiled = _compiled()
    ledger = ExecutionLedger()
    _record_shadow_pair(ledger, compiled, verdict="needs_repair")
    decision = CompletionGate().evaluate(compiled, ledger, [])
    assert decision.ready is False
    assert "proof_evidence_not_admitted" in {item.code for item in decision.blockers}


def test_packet_signature_mismatch_invalidates_gate() -> None:
    compiled = _compiled()
    ledger = ExecutionLedger()
    _record_shadow_pair(ledger, compiled)
    verifier = ledger.latest_receipt("model_verifier_result")
    assert verifier is not None
    verifier.payload["packet_signature"] = "different-packet"
    decision = CompletionGate().evaluate(compiled, ledger, [])
    assert decision.ready is False
    assert "proof_evidence_not_admitted" in {item.code for item in decision.blockers}

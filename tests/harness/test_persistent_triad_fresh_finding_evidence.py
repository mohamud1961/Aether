from __future__ import annotations

from aether.ledger import ExecutionLedger, Receipt
from aether.verifier import CompletionEvidenceEntry, ModelVerifierResult, VerifierFinding


def _finding() -> VerifierFinding:
    return VerifierFinding(
        finding_id="wrong-result", created_step=1, verdict="needs_repair", priority="blocking",
        summary="current result is wrong", evidence=("inspection disagreed",),
        repair_instruction="repair and re-inspect", applies_to=("out.txt",),
    )


def _activate(ledger: ExecutionLedger, *, step: int = 1) -> None:
    ledger.apply_verifier_result(ModelVerifierResult(verdict="needs_repair", findings=(_finding(),)), step=step)


def _inspection(ledger: ExecutionLedger, inspection_id: str, *, packet_signature: str) -> None:
    ledger.record(Receipt(
        receipt_id=inspection_id, step=2, kind="inspection_record", success=True,
        summary="inspected out.txt",
        payload={
            "inspection_id": inspection_id,
            "route_kind": "read_file",
            "route": "read_file:out.txt",
            "target_identity": "path:out.txt",
            "target_generation": "content_hash:out",
            "task_state_generation": ledger.task_state_generation(),
            "tool_identity": "test.inspector",
            "result_hash": "result",
            "evidence_ceiling": "exact_contract",
            "eligible_for_proof": True,
            "packet_signature": packet_signature,
        },
    ))


def _completed(inspection_id: str) -> ModelVerifierResult:
    return ModelVerifierResult(
        verdict="completed", summary="current inspection supports completion",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="result is correct", observed="current result matches",
            falsification_check="different content would contradict",
            inspection_refs=(inspection_id,), evidence_class="exact_contract",
        ),),
    )


def test_pre_finding_same_generation_evidence_cannot_clear_new_finding() -> None:
    ledger = ExecutionLedger()
    _inspection(ledger, "inspection:pre", packet_signature="same-state")
    _activate(ledger)
    ledger.apply_verifier_result(_completed("inspection:pre"), step=2, packet_signature="same-state")
    assert "wrong-result" in ledger.findings.active
    assert ledger.findings.active["wrong-result"].stale_cycles == 1


def test_previous_verifier_round_evidence_cannot_clear_current_finding() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    _inspection(ledger, "inspection:old-round", packet_signature="round-old")
    ledger.apply_verifier_result(_completed("inspection:old-round"), step=2, packet_signature="round-current")
    assert "wrong-result" in ledger.findings.active
    assert ledger.findings.active["wrong-result"].stale_cycles == 1


def test_same_current_verifier_round_fresh_inspection_can_clear_finding() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    _inspection(ledger, "inspection:current", packet_signature="round-current")
    ledger.apply_verifier_result(_completed("inspection:current"), step=2, packet_signature="round-current")
    assert "wrong-result" not in ledger.findings.active
    assert ledger.findings.archived["wrong-result"].status == "resolved_by_current_evidence"

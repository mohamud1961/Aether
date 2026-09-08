"""Target- and generation-bound Verifier finding lifecycle tests."""
from __future__ import annotations

from aether.finding_evidence import active_findings_need_relevant_evidence
from aether.ledger import ExecutionLedger, Receipt
from aether.verifier import (
    CompletionEvidenceEntry,
    ModelVerifierResult,
    VerifierFinding,
    parse_model_verifier_result,
)


def _finding(*, target: str = "out.txt") -> VerifierFinding:
    return VerifierFinding(
        finding_id="wrong-result",
        created_step=1,
        verdict="needs_repair",
        priority="blocking",
        summary="current result is wrong",
        evidence=("independent inspection disagreed",),
        repair_instruction="repair out.txt and re-inspect it",
        applies_to=(target,),
        required_evidence_route="read_file:out.txt",
    )


def _activate(ledger: ExecutionLedger, *, target: str = "out.txt") -> None:
    ledger.apply_verifier_result(
        ModelVerifierResult(verdict="needs_repair", findings=(_finding(target=target),)),
        step=1,
    )


def _inspection(
    ledger: ExecutionLedger,
    *,
    inspection_id: str,
    path: str,
    generation: int | None = None,
) -> None:
    ledger.record(Receipt(
        receipt_id=inspection_id,
        step=2,
        kind="inspection_record",
        success=True,
        summary=f"inspected {path}",
        payload={
            "inspection_id": inspection_id,
            "route_kind": "read_file",
            "route": f"read_file:{path}",
            "target_identity": f"path:{path}",
            "target_generation": f"content_hash:{path}-hash",
            "task_state_generation": (
                ledger.task_state_generation() if generation is None else generation
            ),
            "tool_identity": "test.inspector",
            "result_hash": f"{path}-result",
            "evidence_ceiling": "exact_contract",
            "eligible_for_proof": True,
        },
    ))


def _completed(inspection_id: str, *, clause_ids: tuple[str, ...] = ()) -> ModelVerifierResult:
    return ModelVerifierResult(
        verdict="completed",
        summary="current inspection supports completion",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="result is correct",
            observed="current result matches",
            falsification_check="different content would contradict",
            inspection_refs=(inspection_id,),
            clause_ids=clause_ids,
            evidence_class="exact_contract",
        ),),
    )


def test_finding_binds_owner_target_and_observed_generation() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    finding = ledger.findings.active["wrong-result"]
    assert finding.owner == "solver_state"
    assert finding.applies_to == ("out.txt",)
    assert finding.observed_task_state_generation == 0
    assert finding.repair_condition == "repair out.txt and re-inspect it"
    assert finding.required_evidence_route == "read_file:out.txt"


def test_control_plane_prose_and_unrelated_read_do_not_unlock_resubmission() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    ledger.record(Receipt(
        receipt_id="solver-state",
        step=2,
        kind="solver_decision_state",
        success=True,
        summary="model-authored control-plane prose exists",
        payload={"current_subgoal": "continue"},
    ))
    ledger.record(Receipt(
        receipt_id="accounting",
        step=2,
        kind="runtime_accounting",
        success=True,
        summary="administrative bookkeeping exists",
        payload={"event": "accepted_for_dispatch"},
    ))
    ledger.record(Receipt(
        receipt_id="unrelated-read",
        step=2,
        kind="read_file",
        success=True,
        summary="read notes.txt",
        payload={"path": "notes.txt"},
    ))
    assert active_findings_need_relevant_evidence(ledger) is True


def test_relevant_current_read_unlocks_reverification_without_clearing_finding() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    ledger.record(Receipt(
        receipt_id="relevant-read",
        step=2,
        kind="read_file",
        success=True,
        summary="read repaired out.txt",
        payload={"path": "out.txt", "content_hash": "new"},
    ))
    assert active_findings_need_relevant_evidence(ledger) is False
    assert "wrong-result" in ledger.findings.active


def test_clause_finding_requires_explicit_nomination_for_behavioral_receipt() -> None:
    """A current behavioral check may be nominated without Kernel adjudication."""
    ledger = ExecutionLedger()
    _activate(ledger, target="clause:output-behaves-correctly")
    ledger.record(Receipt(
        receipt_id="behavioral-check",
        step=2,
        kind="run_command",
        success=True,
        summary="behavioral check passed",
        payload={"command": "python verify_behavior.py", "exit_code": 0},
    ))

    # The ordinary target matcher cannot infer a clause from a command string.
    assert active_findings_need_relevant_evidence(ledger) is True
    # A validated PCR submission can nominate this exact fresh receipt. The
    # finding remains active; the Verifier must decide semantic sufficiency.
    assert active_findings_need_relevant_evidence(
        ledger,
        nominated_evidence_receipts=("behavioral-check",),
    ) is False
    assert "wrong-result" in ledger.findings.active


def test_finding_reentry_nomination_rejects_stale_failed_and_control_receipts() -> None:
    stale = ExecutionLedger()
    stale.record(Receipt(
        receipt_id="stale-behavior",
        step=0,
        kind="run_command",
        success=True,
        summary="old behavioral check",
        payload={"command": "python verify_behavior.py", "exit_code": 0},
    ))
    _activate(stale, target="clause:output-behaves-correctly")
    assert active_findings_need_relevant_evidence(
        stale,
        nominated_evidence_receipts=("stale-behavior",),
    ) is True

    failed = ExecutionLedger()
    _activate(failed, target="clause:output-behaves-correctly")
    failed.record(Receipt(
        receipt_id="failed-behavior",
        step=2,
        kind="run_command",
        success=False,
        summary="behavioral check failed",
        failure_class="command_failed",
        payload={"command": "python verify_behavior.py", "exit_code": 1},
    ))
    assert active_findings_need_relevant_evidence(
        failed,
        nominated_evidence_receipts=("failed-behavior",),
    ) is True

    control = ExecutionLedger()
    _activate(control, target="clause:output-behaves-correctly")
    control.record(Receipt(
        receipt_id="control-only",
        step=2,
        kind="runtime_accounting",
        success=True,
        summary="provider accounting",
    ))
    assert active_findings_need_relevant_evidence(
        control,
        nominated_evidence_receipts=("control-only", "unknown"),
    ) is True


def test_completed_with_unrelated_inspection_does_not_clear_finding() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    _inspection(ledger, inspection_id="inspection:other", path="other.txt")
    ledger.apply_verifier_result(_completed("inspection:other"), step=2)
    assert "wrong-result" in ledger.findings.active
    assert ledger.findings.active["wrong-result"].stale_cycles == 1


def test_completed_with_relevant_current_inspection_clears_only_matching_finding() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    ledger.findings.active["other-finding"] = VerifierFinding(
        finding_id="other-finding",
        created_step=1,
        verdict="needs_repair",
        priority="blocking",
        summary="other target wrong",
        applies_to=("other.txt",),
        observed_task_state_generation=0,
    )
    _inspection(ledger, inspection_id="inspection:out", path="out.txt")
    ledger.apply_verifier_result(_completed("inspection:out"), step=2)
    assert "wrong-result" not in ledger.findings.active
    assert ledger.findings.archived["wrong-result"].status == "resolved_by_current_evidence"
    assert "other-finding" in ledger.findings.active


def test_older_conflicting_same_generation_inspection_cannot_clear_finding() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    _inspection(ledger, inspection_id="inspection:old", path="out.txt")
    # Same task generation, but a newer independent observation saw different
    # target state. The older favorable read may no longer retire the finding.
    ledger.record(Receipt(
        receipt_id="inspection:new",
        step=2,
        kind="inspection_record",
        success=True,
        summary="newer conflicting out.txt observation",
        payload={
            "inspection_id": "inspection:new", "requester": "model_verifier",
            "route_kind": "read_file", "route": "read_file:out.txt",
            "target_identity": "path:out.txt", "target_generation": "content_hash:new-hash",
            "task_state_generation": ledger.task_state_generation(),
            "tool_identity": "test.inspector", "result_hash": "new-result",
            "evidence_ceiling": "exact_contract", "actual_evidence_class": "exact_contract",
            "eligible_for_proof": True, "observation_valid": True,
        },
    ))
    ledger.apply_verifier_result(_completed("inspection:old"), step=2)
    assert "wrong-result" in ledger.findings.active


def test_stale_relevant_inspection_cannot_clear_finding_after_mutation() -> None:
    ledger = ExecutionLedger()
    _activate(ledger)
    _inspection(ledger, inspection_id="inspection:old", path="out.txt", generation=0)
    ledger.record(Receipt(
        receipt_id="mutation",
        step=2,
        kind="write_file",
        success=True,
        summary="rewrote out.txt after inspection",
        state_change=True,
        payload={"modified_paths": ["out.txt"]},
    ))
    assert ledger.task_state_generation() == 1
    ledger.apply_verifier_result(_completed("inspection:old"), step=3)
    assert "wrong-result" in ledger.findings.active


def test_parser_accepts_structured_finding_binding_fields() -> None:
    parsed = parse_model_verifier_result({
        "verdict": "needs_repair",
        "findings": [{
            "finding_id": "f1",
            "summary": "wrong result",
            "evidence": ["inspection disagreed"],
            "repair_instruction": "repair and re-inspect",
            "applies_to": ["result-clause", "out.txt"],
            "owner": "solver_state",
            "observed_task_state_generation": 4,
            "supporting_inspection_ids": ["inspection:4"],
            "repair_condition": "current out.txt passes exact read",
            "required_evidence_route": "read_file:out.txt",
        }],
    })
    finding = parsed.findings[0]
    assert finding.observed_task_state_generation == 4
    assert finding.supporting_inspection_ids == ("inspection:4",)
    assert finding.required_evidence_route == "read_file:out.txt"



def test_same_basename_nested_path_does_not_unlock_finding_reverification() -> None:
    ledger = ExecutionLedger()
    _activate(ledger, target="out.txt")
    ledger.record(Receipt(
        receipt_id="nested-read",
        step=2,
        kind="read_file",
        success=True,
        summary="read a different nested artifact",
        payload={"path": "nested/out.txt", "content_hash": "nested"},
    ))
    assert active_findings_need_relevant_evidence(ledger) is True


def test_same_basename_nested_inspection_does_not_clear_finding() -> None:
    ledger = ExecutionLedger()
    _activate(ledger, target="out.txt")
    _inspection(ledger, inspection_id="inspection:nested", path="nested/out.txt")
    ledger.apply_verifier_result(_completed("inspection:nested"), step=2)
    assert "wrong-result" in ledger.findings.active
    assert ledger.findings.active["wrong-result"].stale_cycles == 1


def test_workspace_absolute_path_still_matches_normalized_finding_target() -> None:
    ledger = ExecutionLedger()
    _activate(ledger, target="out.txt")
    ledger.record(Receipt(
        receipt_id="absolute-read",
        step=2,
        kind="read_file",
        success=True,
        summary="read exact workspace artifact",
        payload={"path": "/app/out.txt", "content_hash": "current"},
    ))
    assert active_findings_need_relevant_evidence(ledger) is False



def test_external_absolute_path_is_not_equivalent_to_workspace_relative_path() -> None:
    ledger = ExecutionLedger()
    _activate(ledger, target="etc/app.conf")
    ledger.record(Receipt(
        receipt_id="external-read",
        step=2,
        kind="read_file",
        success=True,
        summary="read host-style absolute path",
        payload={"path": "/etc/app.conf", "content_hash": "external"},
    ))
    assert active_findings_need_relevant_evidence(ledger) is True


def test_dot_relative_workspace_path_matches_canonical_workspace_target() -> None:
    ledger = ExecutionLedger()
    _activate(ledger, target="./out.txt")
    ledger.record(Receipt(
        receipt_id="canonical-read",
        step=2,
        kind="read_file",
        success=True,
        summary="read canonical workspace path",
        payload={"path": "out.txt", "content_hash": "same"},
    ))
    assert active_findings_need_relevant_evidence(ledger) is False

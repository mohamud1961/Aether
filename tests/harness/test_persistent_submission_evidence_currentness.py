from __future__ import annotations

from aether.ledger import TASK_STATE_SNAPSHOT_BINDING_VERSION, ExecutionLedger, Receipt
from aether.persistent_context import evidence_alias
from aether.persistent_submission import validate_persistent_submission_binding
from aether.runtime_ir import SolverTurn


def _ledger() -> ExecutionLedger:
    ledger = ExecutionLedger()
    ledger.install_runtime_identity({
        "task_id": "task",
        "run_id": "run",
        "workspace_id": "workspace",
    })
    return ledger


def _row(receipt: Receipt, ledger: ExecutionLedger) -> dict[str, object]:
    identity = ledger.runtime_identity
    return {
        "evidence_ref": evidence_alias(receipt.receipt_id),
        "completion_evidence_eligible": True,
        "task_evidence_candidate": True,
        "receipt_id": receipt.receipt_id,
        "evidence_type": receipt.kind,
        "task_id": identity["task_id"],
        "run_id": identity["run_id"],
        "workspace_id": identity["workspace_id"],
    }


def _context(ledger: ExecutionLedger, rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "runtime_identity": dict(ledger.runtime_identity),
        "snapshot_binding_version": TASK_STATE_SNAPSHOT_BINDING_VERSION,
        "task_state_generation": ledger.task_state_generation(),
        "task_state_snapshot_digest": ledger.task_state_snapshot_digest(),
        "evidence_index": rows,
    }


def test_old_validation_becomes_historical_support_after_candidate_mutation() -> None:
    ledger = _ledger()
    validation = Receipt(
        receipt_id="validation-ok",
        step=1,
        kind="check_result",
        success=True,
        summary="representative validation passed",
        payload={"check_id": "validation", "passed": True},
    )
    ledger.record(validation)
    assert ledger.receipt_task_state_generation(validation.receipt_id) == 0

    ledger.record(Receipt(
        receipt_id="candidate-mutation",
        step=2,
        kind="write_file",
        success=True,
        summary="candidate changed",
        state_change=True,
        payload={"path": "/app/candidate.py", "modified_paths": ["candidate.py"]},
    ))
    current = Receipt(
        receipt_id="current-read",
        step=3,
        kind="read_file",
        success=True,
        summary="current candidate observed",
        payload={"path": "/app/candidate.py"},
    )
    ledger.record(current)
    assert ledger.task_state_generation() == 1
    assert ledger.receipt_task_state_generation(current.receipt_id) == 1

    old_ref = evidence_alias(validation.receipt_id)
    current_ref = evidence_alias(current.receipt_id)
    turn = SolverTurn(
        kind="finish_intent",
        summary="submit",
        claim="candidate is ready",
        evidence_refs=(old_ref, current_ref),
    )
    decision, binding = validate_persistent_submission_binding(
        turn,
        _context(ledger, [_row(validation, ledger), _row(current, ledger)]),
        ledger,
        current_step=4,
        strict_snapshot_binding=True,
    )

    assert decision.allowed is True
    assert binding is not None
    assert binding.evidence_generations == (0, 1)
    assert binding.evidence_roles == ("historical_support", "current_anchor")


def test_submission_rejects_only_stale_validation_after_candidate_mutation() -> None:
    ledger = _ledger()
    validation = Receipt(
        receipt_id="validation-ok",
        step=1,
        kind="check_result",
        success=True,
        summary="representative validation passed",
        payload={"check_id": "validation", "passed": True},
    )
    ledger.record(validation)
    ledger.record(Receipt(
        receipt_id="candidate-mutation",
        step=2,
        kind="write_file",
        success=True,
        summary="candidate changed",
        state_change=True,
        payload={"path": "/app/candidate.py", "modified_paths": ["candidate.py"]},
    ))

    old_ref = evidence_alias(validation.receipt_id)
    turn = SolverTurn(
        kind="finish_intent",
        summary="submit",
        claim="candidate is ready",
        evidence_refs=(old_ref,),
    )
    decision, binding = validate_persistent_submission_binding(
        turn,
        _context(ledger, [_row(validation, ledger)]),
        ledger,
        current_step=3,
        strict_snapshot_binding=True,
    )

    assert decision.allowed is False
    assert decision.reason_code == "evidence_stale"
    assert binding is None


# ---------------------------------------------------------------------------
# F05 durable-alias sentinels: packet-absent aliases resolve by ledger
# provenance; forged/canceled/wrong-generation/withdrawn aliases fail closed.
# ---------------------------------------------------------------------------


def test_packet_absent_alias_resolves_durably() -> None:
    """A valid evicted receipt still resolves by durable ledger provenance."""
    ledger = _ledger()
    old = Receipt(
        receipt_id="old-validation", step=1, kind="check_result", success=True,
        summary="old validation passed",
        payload={"check_id": "validation", "passed": True},
    )
    ledger.record(old)
    ledger.record(Receipt(
        receipt_id="mutation", step=2, kind="write_file", success=True,
        summary="candidate changed", state_change=True,
        payload={"path": "candidate.py", "modified_paths": ["candidate.py"]},
    ))
    current = Receipt(
        receipt_id="current-read", step=3, kind="read_file", success=True,
        summary="current read", payload={"path": "candidate.py"},
    )
    ledger.record(current)
    old_ref = evidence_alias(old.receipt_id)
    current_ref = evidence_alias(current.receipt_id)
    # old_ref is omitted from visible rows (evicted from compact packet).
    turn = SolverTurn(
        kind="finish_intent",
        summary="submit",
        claim="ready",
        evidence_refs=(old_ref, current_ref),
    )
    decision, binding = validate_persistent_submission_binding(
        turn,
        _context(ledger, [_row(current, ledger)]),  # only current visible
        ledger,
        current_step=4,
        strict_snapshot_binding=True,
    )
    assert decision.allowed is True
    assert binding is not None
    assert binding.evidence_generations == (0, 1)
    assert binding.evidence_roles == ("historical_support", "current_anchor")


def test_forged_alias_not_in_ledger_rejected() -> None:
    """An alias absent from both packet and ledger fails closed."""
    ledger = _ledger()
    current = Receipt(
        receipt_id="current-read", step=1, kind="read_file", success=True,
        summary="current read", payload={"path": "candidate.py"},
    )
    ledger.record(current)
    turn = SolverTurn(
        kind="finish_intent",
        summary="submit",
        claim="ready",
        evidence_refs=("evidence:" + "a" * 16,),
    )
    decision, binding = validate_persistent_submission_binding(
        turn,
        _context(ledger, [_row(current, ledger)]),
        ledger,
        current_step=2,
        strict_snapshot_binding=True,
    )
    assert decision.allowed is False
    assert decision.reason_code == "evidence_reference_not_current_context"
    assert binding is None


def test_canceled_evidence_rejected_after_later_disposition() -> None:
    """Evicted receipt for an abandoned job is rejected through durable provenance."""
    ledger = _ledger()
    # Register the process and its launch BEFORE the evidence receipt.
    ledger.record(Receipt(
        receipt_id="launch-proc-1", step=0, kind="process_launch", success=True,
        summary="started", state_change=True,
        payload={
            "process_id": "proc-1", "service_name": "diag",
            "command": "python diag.py", "process_generation": "gen-1",
        },
    ))
    evidence = Receipt(
        receipt_id="probe-evidence", step=1, kind="check_result", success=True,
        summary="observed diagnostic output",
        payload={"check_id": "diag", "passed": True, "job_id": "proc-1"},
    )
    ledger.record(evidence)
    # Later disposition abandons the job.
    disposition_receipt = ledger.set_job_disposition(
        "proc-1", "abandoned", "no longer relevant", step=2,
    )
    assert disposition_receipt.success is True
    # A current anchor keeps the visible packet current; the old evidence is
    # evicted so it must resolve through durable provenance.
    current = Receipt(
        receipt_id="current-read", step=3, kind="read_file", success=True,
        summary="current read", payload={"path": "out.txt"},
    )
    ledger.record(current)
    turn = SolverTurn(
        kind="finish_intent",
        summary="submit",
        claim="ready",
        evidence_refs=(evidence_alias(evidence.receipt_id),),
    )
    decision, binding = validate_persistent_submission_binding(
        turn,
        _context(ledger, [_row(current, ledger)]),
        ledger,
        current_step=4,
        strict_snapshot_binding=True,
    )
    assert decision.allowed is False
    assert decision.reason_code == "evidence_canceled"
    assert binding is None


def test_explicitly_withdrawn_evidence_rejected() -> None:
    """Evicted receipt payload marked withdrawn is treated as canceled."""
    ledger = _ledger()
    evidence = Receipt(
        receipt_id="withdrawn-read", step=1, kind="read_file", success=True,
        summary="read artifact",
        payload={"path": "out.txt", "content_sha256": "a" * 64, "withdrawn": True},
    )
    ledger.record(evidence)
    current = Receipt(
        receipt_id="current-read", step=2, kind="read_file", success=True,
        summary="current read", payload={"path": "out.txt"},
    )
    ledger.record(current)
    turn = SolverTurn(
        kind="finish_intent",
        summary="submit",
        claim="ready",
        evidence_refs=(evidence_alias(evidence.receipt_id),),
    )
    decision, binding = validate_persistent_submission_binding(
        turn,
        _context(ledger, [_row(current, ledger)]),
        ledger,
        current_step=3,
        strict_snapshot_binding=True,
    )
    assert decision.allowed is False
    assert decision.reason_code == "evidence_canceled"
    assert binding is None


def test_wrong_process_generation_rejected() -> None:
    """Evicted evidence from a superseded process generation fails closed."""
    ledger = _ledger()
    ledger.record(Receipt(
        receipt_id="launch-proc-1-v1", step=0, kind="process_launch", success=True,
        summary="old generation launched", state_change=True,
        payload={
            "process_id": "proc-1", "service_name": "validation",
            "command": "python validate.py", "process_generation": "gen-old",
        },
    ))
    evidence = Receipt(
        receipt_id="old-gen-evidence", step=1, kind="check_result", success=True,
        summary="old generation check passed",
        payload={
            "check_id": "validation",
            "passed": True,
            "job_id": "proc-1",
            "process_generation": "gen-old",
        },
    )
    ledger.record(evidence)
    # A later launch supersedes the registered generation.
    ledger.record(Receipt(
        receipt_id="launch-proc-1-v2", step=2, kind="process_launch", success=True,
        summary="new generation launched", state_change=True,
        payload={
            "process_id": "proc-1", "service_name": "validation",
            "command": "python validate.py", "process_generation": "gen-new",
        },
    ))
    current = Receipt(
        receipt_id="current-read", step=3, kind="read_file", success=True,
        summary="current read", payload={"path": "out.txt"},
    )
    ledger.record(current)
    turn = SolverTurn(
        kind="finish_intent",
        summary="submit",
        claim="ready",
        evidence_refs=(evidence_alias(evidence.receipt_id),),
    )
    decision, binding = validate_persistent_submission_binding(
        turn,
        _context(ledger, [_row(current, ledger)]),
        ledger,
        current_step=4,
        strict_snapshot_binding=True,
    )
    assert decision.allowed is False
    assert decision.reason_code == "evidence_wrong_process_generation"
    assert binding is None

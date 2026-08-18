from __future__ import annotations

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.context_compiler import ContextCompiler
from aether.envmap_builder import build_envmap_from_task
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_submission import validate_persistent_submission_binding
from aether.persistent_primary import persistent_primary_runtime_ir
from aether.runtime_ir import SolverTurn
from aether.submission_coherence import evaluate_submission_coherence


def _compiled(tmp_path, prompt: str):
    envmap = build_envmap_from_task(str(tmp_path), prompt, workspace_root=str(tmp_path))
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
    objective, eval_index = compiler.analyze_envmap(envmap)
    return compiler.compile(
        persistent_primary_runtime_ir(envmap, eval_index), envmap,
        objective_graph=objective, eval_index=eval_index,
    )


def _identity(tmp_path):
    return {
        "task_id": "completion-mode-task",
        "run_id": "completion-mode-run",
        "primary_agent_id": "primary-agent:completion-mode-run",
        "workspace_id": str(tmp_path),
        "environment_id": "completion-mode-env",
        "source_commit": "a" * 40,
        "source_commit_state": "provided",
        "runtime_manifest_sha256": "b" * 64,
        "runtime_manifest_state": "provided",
        "source_custody_complete": True,
        "budgets": {"max_kernel_steps": 8},
    }


def _record_read_evidence(ledger: ExecutionLedger, *, step: int, path: str, content: str) -> Receipt:
    receipt = Receipt(
        receipt_id=f"step-{step}:read:{path}", step=step, kind="read_file", success=True,
        summary=f"read {path}", state_change=False,
        payload={"path": path, "bytes": len(content), "excerpt": content, "content_hash": "c" * 64},
    )
    ledger.record(receipt)
    ledger.record(Receipt(
        receipt_id=f"step-{step}:progress", step=step, kind="solver_progress_assessment", success=True,
        summary="read-only observation produced current evidence",
        payload={
            "classification": "successful_result_no_state_change",
            "progress_signals": ["new_evidence"],
            "dispatch_performed": True,
        },
    ))
    return receipt


def _submit_from_receipt(compiled, ledger, receipt, *, current_step: int, claim: str):
    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    alias = next(
        row["evidence_ref"] for row in packet["evidence_index"]
        if row["receipt_id"] == receipt.receipt_id
    )
    turn = SolverTurn(
        kind="submit_outcome", summary=claim, claim=claim, evidence_refs=(alias,),
    )
    return validate_persistent_submission_binding(turn, packet, ledger, current_step=current_step)


def test_persistent_read_only_task_can_submit_without_any_state_change(tmp_path) -> None:
    compiled = _compiled(tmp_path, "Inspect status.txt and report whether it says READY. Do not modify files.")
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    receipt = _record_read_evidence(ledger, step=1, path="status.txt", content="READY")

    assert ledger.task_state_generation() == 0
    coherence = evaluate_submission_coherence(ledger, current_step=2)
    assert coherence.allowed is True
    decision, binding = _submit_from_receipt(
        compiled, ledger, receipt, current_step=2,
        claim="status.txt already reports READY; no mutation was required.",
    )
    assert decision.allowed is True
    assert binding is not None
    assert binding.task_state_generation == 0
    assert binding.evidence_roles == ("current_anchor",)


def test_persistent_noop_already_correct_task_can_complete_from_observation_only(tmp_path) -> None:
    compiled = _compiled(tmp_path, "Ensure config.txt contains ENABLED. If it is already correct, make no change.")
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    receipt = _record_read_evidence(ledger, step=1, path="config.txt", content="ENABLED")

    # An already-correct task is not forced through a synthetic write merely to
    # manufacture state-change evidence.
    assert ledger.task_state_generation() == 0
    assert not any(r.state_change for r in ledger.all_receipts())
    assert evaluate_submission_coherence(ledger, current_step=2).allowed is True
    decision, binding = _submit_from_receipt(
        compiled, ledger, receipt, current_step=2,
        claim="config.txt already contains ENABLED; the correct action was no-op.",
    )
    assert decision.allowed is True
    assert binding is not None
    assert binding.task_state_generation == 0


def test_persistent_failed_read_only_observation_does_not_authorize_submission(tmp_path) -> None:
    compiled = _compiled(tmp_path, "Inspect status.txt and report its value without modifying anything.")
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    failed = Receipt(
        receipt_id="step-1:read:failed", step=1, kind="read_file", success=False,
        summary="status.txt could not be read", state_change=False,
        failure_class="missing_file", payload={"path": "status.txt"},
    )
    ledger.record(failed)
    ledger.record(Receipt(
        receipt_id="step-1:progress", step=1, kind="solver_progress_assessment", success=True,
        summary="read failed", payload={
            "classification": "unsuccessful_result_no_state_change",
            "progress_signals": ["failure"], "dispatch_performed": True,
        },
    ))
    assert evaluate_submission_coherence(ledger, current_step=2).allowed is False
    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    assert all(row["receipt_id"] != failed.receipt_id for row in packet["evidence_index"])
    # Failure truth stays in the ledger, but cannot acquire a completion-evidence
    # alias or be promoted into a completion claim.
    assert any(r.receipt_id == failed.receipt_id and r.success is False for r in ledger.all_receipts())
    turn = SolverTurn(
        kind="submit_outcome", summary="unsupported claim", claim="status.txt has a valid value",
        evidence_refs=("evidence:step-1:read:failed",),
    )
    decision, binding = validate_persistent_submission_binding(turn, packet, ledger, current_step=2)
    assert decision.allowed is False
    assert decision.reason_code == "evidence_reference_not_current_context"
    assert binding is None

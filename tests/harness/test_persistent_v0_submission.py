"""Mechanical PERSISTENT V0 claim/evidence binding and Verifier packet tests."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.context_compiler import ContextCompiler
from aether.kernel import AetherNextKernel
from aether.persistent_context import evidence_alias
from aether.envmap_builder import build_envmap_from_task
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_submission import (
    record_persistent_submission_claim,
    validate_persistent_submission_binding,
)
from aether.persistent_primary import persistent_primary_runtime_ir
from aether.runtime_ir import CheckSpec, EvalIndex, SolverTurn
from aether.verifier import ModelVerifierResult, VerifierFinding
from aether.verifier_packets import build_verifier_packet, packet_state_signature


def _compiled(tmp_path):
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Create out.txt containing hello.",
        workspace_root=str(tmp_path),
    )
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
    objective, eval_index = compiler.analyze_envmap(envmap)
    compiled = compiler.compile(
        persistent_primary_runtime_ir(envmap, eval_index),
        envmap,
        objective_graph=objective,
        eval_index=eval_index,
    )
    return envmap, compiled


def _identity(tmp_path) -> dict[str, object]:
    return {
        "task_id": "task-claim",
        "run_id": "run-claim",
        "primary_agent_id": "primary-agent:run-claim",
        "workspace_id": str(tmp_path),
        "environment_id": "env-claim",
        "source_commit": "a" * 40,
        "source_commit_state": "provided",
        "runtime_manifest_sha256": "b" * 64,
        "runtime_manifest_state": "provided",
        "source_custody_complete": True,
        "budgets": {"max_kernel_steps": 8},
    }


def _ledger_and_packet(tmp_path, compiled):
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    result = Receipt(
        receipt_id="step-1:persistent-write:write",
        step=1,
        kind="write_file",
        success=True,
        summary="wrote out.txt",
        state_change=True,
        payload={
            "path": "out.txt",
            "bytes": 5,
            "after_content_hash": "c" * 64,
            "excerpt": "hello",
            "file_handle": "file:out.txt",
        },
    )
    uncited = Receipt(
        receipt_id="step-1:persistent-read:read",
        step=1,
        kind="read_file",
        success=True,
        summary="read unrelated.txt",
        payload={
            "path": "unrelated.txt",
            "bytes": 7,
            "excerpt": "private",
            "file_handle": "file:unrelated.txt",
        },
    )
    ledger.record(result)
    ledger.record(uncited)
    ledger.record(Receipt(
        receipt_id="step-1:persistent-write:primary_action_result_index",
        step=1,
        kind="primary_action_result_index",
        success=True,
        summary="indexed write result",
        payload={
            "action_id": "persistent-write",
            "action_kind": "write_file",
            "status": "observed",
            "outcome_receipt_ids": [result.receipt_id],
            "outcome_kinds": [result.kind],
        },
    ))
    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    alias = next(
        row["evidence_ref"]
        for row in packet["evidence_index"]
        if row["receipt_id"] == result.receipt_id
    )
    return ledger, packet, result, uncited, alias


def test_current_context_alias_resolves_to_same_run_receipt(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, packet, result, _uncited, alias = _ledger_and_packet(tmp_path, compiled)
    turn = SolverTurn(
        kind="submit_outcome",
        summary="out.txt is complete",
        claim="out.txt contains hello.",
        evidence_refs=(alias,),
    )

    decision, binding = validate_persistent_submission_binding(
        turn, packet, ledger, current_step=2,
    )
    assert decision.allowed is True
    assert binding is not None
    assert binding.receipt_ids == (result.receipt_id,)
    assert binding.context_identity == ledger.runtime_identity

    claim_receipt = record_persistent_submission_claim(ledger, step=2, binding=binding)
    assert claim_receipt.kind == "primary_submission_claim"
    assert claim_receipt.payload["evidence_receipt_ids"] == [result.receipt_id]
    assert claim_receipt.payload["semantic_sufficiency_judged_by_kernel"] is False


def test_validated_submission_binding_reopens_clause_finding_for_verifier(tmp_path) -> None:
    envmap, compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    ledger.apply_verifier_result(
        ModelVerifierResult(
            verdict="needs_repair",
            findings=(VerifierFinding(
                finding_id="behavior-clause",
                created_step=1,
                verdict="needs_repair",
                priority="blocking",
                summary="behavioral clause needs fresh evidence",
                repair_instruction="run the independent behavioral check",
                applies_to=("clause:behavioral-contract",),
            ),),
        ),
        step=1,
    )
    receipt = Receipt(
        receipt_id="step-2:behavior-check",
        step=2,
        kind="run_command",
        success=True,
        summary="independent behavioral check passed",
        payload={"command": "python verify_behavior.py", "exit_code": 0},
    )
    ledger.record(receipt)
    context = ContextCompiler().compile(compiled, ledger, alerts=[])
    alias = next(
        row["evidence_ref"]
        for row in context["evidence_index"]
        if row["receipt_id"] == receipt.receipt_id
    )
    turn = SolverTurn(
        kind="submit_outcome",
        summary="nominate the current behavioral check",
        claim="the behavioral contract is satisfied",
        evidence_refs=(alias,),
    )

    decision, binding = validate_persistent_submission_binding(
        turn, context, ledger, current_step=3,
    )
    assert decision.allowed is True
    assert binding is not None
    assert AetherNextKernel._active_findings_need_intervening_evidence(ledger) is True
    assert AetherNextKernel._active_findings_need_intervening_evidence(
        ledger,
        nominated_evidence_receipt_ids=binding.receipt_ids,
    ) is False
    assert "behavior-clause" in ledger.findings.active
    assert envmap.workspace_root == str(tmp_path)


def test_completion_claim_without_evidence_is_rejected(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, packet, _result, _uncited, _alias = _ledger_and_packet(tmp_path, compiled)
    turn = SolverTurn(
        kind="submit_outcome",
        summary="claim without proof",
        claim="the task is complete",
        evidence_refs=(),
    )

    decision, binding = validate_persistent_submission_binding(
        turn, packet, ledger, current_step=2,
    )

    assert decision.allowed is False
    assert decision.reason_code == "submission_evidence_missing"
    assert binding is None


def test_unknown_stale_and_cross_lineage_aliases_fail_closed(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, packet, _result, _uncited, alias = _ledger_and_packet(tmp_path, compiled)

    unknown = SolverTurn(
        kind="submit_outcome",
        summary="claim",
        claim="claim",
        evidence_refs=("evidence:not-visible",),
    )
    decision, binding = validate_persistent_submission_binding(
        unknown, packet, ledger, current_step=2,
    )
    assert decision.allowed is False
    assert decision.reason_code == "evidence_reference_not_current_context"
    assert binding is None

    tampered = deepcopy(packet)
    row = next(row for row in tampered["evidence_index"] if row["evidence_ref"] == alias)
    row["run_id"] = "different-run"
    cross_lineage = SolverTurn(
        kind="submit_outcome",
        summary="claim",
        claim="claim",
        evidence_refs=(alias,),
    )
    decision, binding = validate_persistent_submission_binding(
        cross_lineage, tampered, ledger, current_step=2,
    )
    assert decision.allowed is False
    assert decision.reason_code == "evidence_lineage_mismatch"
    assert binding is None


def test_evidence_observed_before_later_task_mutation_is_rejected(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, _packet, _result, _uncited, alias = _ledger_and_packet(tmp_path, compiled)
    ledger.record(Receipt(
        receipt_id="step-2:persistent-write:later-mutation",
        step=2,
        kind="write_file",
        success=True,
        summary="mutated the task state after the cited observation",
        state_change=True,
        payload={"path": "out.txt", "bytes": 7},
    ))
    current_packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    turn = SolverTurn(
        kind="submit_outcome",
        summary="claim stale state",
        claim="out.txt contains hello.",
        evidence_refs=(alias,),
    )

    decision, binding = validate_persistent_submission_binding(
        turn, current_packet, ledger, current_step=3,
    )

    assert decision.allowed is False
    assert decision.reason_code == "evidence_stale"
    assert binding is None


def test_bookkeeping_receipt_cannot_enter_completion_evidence(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, _packet, _result, _uncited, _alias = _ledger_and_packet(tmp_path, compiled)
    bookkeeping = ledger.record_accounting(
        receipt_id="step-2:runtime-accounting",
        step=2,
        counter="solver_provider_turns",
        event="completed",
    )
    current_packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    assert all(
        row["receipt_id"] != bookkeeping.receipt_id
        for row in current_packet["evidence_index"]
    )
    turn = SolverTurn(
        kind="submit_outcome",
        summary="claim bookkeeping",
        claim="the task is complete",
        evidence_refs=(evidence_alias(bookkeeping.receipt_id),),
    )

    decision, binding = validate_persistent_submission_binding(
        turn, current_packet, ledger, current_step=3,
    )

    assert decision.allowed is False
    assert decision.reason_code == "evidence_reference_not_current_context"
    assert binding is None


def test_duplicate_aliases_and_raw_receipt_ids_are_not_accepted(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger, packet, result, _uncited, alias = _ledger_and_packet(tmp_path, compiled)

    duplicate = SolverTurn(
        kind="submit_outcome",
        summary="claim",
        claim="claim",
        evidence_refs=(alias, alias),
    )
    decision, _binding = validate_persistent_submission_binding(
        duplicate, packet, ledger, current_step=2,
    )
    assert decision.reason_code == "duplicate_evidence_reference"

    raw_id = SolverTurn(
        kind="submit_outcome",
        summary="claim",
        claim="claim",
        evidence_refs=(result.receipt_id,),
    )
    decision, _binding = validate_persistent_submission_binding(
        raw_id, packet, ledger, current_step=2,
    )
    assert decision.reason_code == "evidence_reference_not_current_context"


def test_persistent_verifier_receives_exact_claim_and_only_cited_evidence(tmp_path) -> None:
    envmap, compiled = _compiled(tmp_path)
    ledger, context, result, uncited, alias = _ledger_and_packet(tmp_path, compiled)
    turn = SolverTurn(
        kind="submit_outcome",
        summary="out.txt is complete",
        claim="out.txt contains hello.",
        evidence_refs=(alias,),
    )
    decision, binding = validate_persistent_submission_binding(
        turn, context, ledger, current_step=2,
    )
    assert decision.allowed and binding is not None
    record_persistent_submission_claim(ledger, step=2, binding=binding)

    verifier_packet = build_verifier_packet(
        compiled,
        ledger,
        step=2,
        reason="solver_submit",
        envmap=envmap,
    )
    submission = verifier_packet["primary_submission"]
    assert submission["claim"] == "out.txt contains hello."
    assert submission["evidence_refs"] == [alias]
    assert submission["evidence_receipt_ids"] == [result.receipt_id]
    assert [row["receipt_id"] for row in submission["cited_evidence"]] == [result.receipt_id]
    assert uncited.receipt_id not in str(submission)
    assert submission["cited_evidence"][0]["exact_receipt_handle"] == f"receipt:{result.receipt_id}"
    assert verifier_packet["runtime_identity"] == ledger.runtime_identity


def test_verifier_state_signature_changes_when_external_claim_changes(tmp_path) -> None:
    envmap, compiled = _compiled(tmp_path)
    ledger, context, _result, _uncited, alias = _ledger_and_packet(tmp_path, compiled)

    first_turn = SolverTurn(
        kind="submit_outcome",
        summary="first claim",
        claim="out.txt contains hello.",
        evidence_refs=(alias,),
    )
    _decision, first_binding = validate_persistent_submission_binding(
        first_turn, context, ledger, current_step=2,
    )
    assert first_binding is not None
    record_persistent_submission_claim(ledger, step=2, binding=first_binding)
    first_packet = build_verifier_packet(
        compiled, ledger, step=2, reason="solver_submit", envmap=envmap,
    )

    second_turn = SolverTurn(
        kind="submit_outcome",
        summary="second claim",
        claim="out.txt exists but its content is unverified.",
        evidence_refs=(alias,),
    )
    _decision, second_binding = validate_persistent_submission_binding(
        second_turn, context, ledger, current_step=3,
    )
    assert second_binding is not None
    record_persistent_submission_claim(ledger, step=3, binding=second_binding)
    second_packet = build_verifier_packet(
        compiled, ledger, step=3, reason="solver_submit", envmap=envmap,
    )

    assert packet_state_signature(first_packet) != packet_state_signature(second_packet)


def test_current_anchor_plus_historical_same_run_evidence_is_admitted(tmp_path) -> None:
    envmap, compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    before = Receipt(
        receipt_id="step-1:persistent-before:read",
        step=1, kind="read_file", success=True, summary="read pre-edit out.txt",
        payload={"path": "out.txt", "bytes": 5, "excerpt": "hello", "content_hash": "1" * 64},
    )
    mutation = Receipt(
        receipt_id="step-2:persistent-write:write",
        step=2, kind="write_file", success=True, summary="updated out.txt", state_change=True,
        payload={"path": "out.txt", "bytes": 6, "excerpt": "hello!", "after_content_hash": "2" * 64},
    )
    after = Receipt(
        receipt_id="step-3:persistent-after:read",
        step=3, kind="read_file", success=True, summary="read current out.txt",
        payload={"path": "out.txt", "bytes": 6, "excerpt": "hello!", "content_hash": "2" * 64},
    )
    ledger.record(before)
    ledger.record(mutation)
    ledger.record(after)
    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    by_id = {row["receipt_id"]: row["evidence_ref"] for row in packet["evidence_index"]}
    turn = SolverTurn(
        kind="submit_outcome",
        summary="current result preserves the prior prefix",
        claim="out.txt changed from hello to hello! while preserving the prior content as a prefix.",
        evidence_refs=(by_id[after.receipt_id], by_id[before.receipt_id]),
    )

    decision, binding = validate_persistent_submission_binding(turn, packet, ledger, current_step=4)
    assert decision.allowed is True
    assert binding is not None
    assert binding.evidence_roles == ("current_anchor", "historical_support")
    assert binding.evidence_generations == (1, 0)
    claim_receipt = record_persistent_submission_claim(ledger, step=4, binding=binding)
    assert claim_receipt.payload["current_anchor_count"] == 1
    assert claim_receipt.payload["historical_support_count"] == 1

    verifier_packet = build_verifier_packet(
        compiled, ledger, step=4, reason="solver_submit", envmap=envmap,
    )
    submission = verifier_packet["primary_submission"]
    roles = {row["receipt_id"]: row["evidence_role"] for row in submission["cited_evidence"]}
    assert roles[after.receipt_id] == "current_anchor"
    assert roles[before.receipt_id] == "historical_support"
    before_row = next(row for row in submission["cited_evidence"] if row["receipt_id"] == before.receipt_id)
    after_row = next(row for row in submission["cited_evidence"] if row["receipt_id"] == after.receipt_id)
    assert before_row["current_payload_projection"]["excerpt"] == "hello"
    assert after_row["current_payload_projection"]["excerpt"] == "hello!"
    assert submission["current_anchor_count"] == 1
    assert submission["historical_support_count"] == 1


def test_historical_evidence_without_current_anchor_remains_rejected(tmp_path) -> None:
    _envmap, compiled = _compiled(tmp_path)
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(_identity(tmp_path))
    before = Receipt(
        receipt_id="step-1:persistent-before:read", step=1, kind="read_file", success=True,
        summary="read pre-edit out.txt", payload={"path": "out.txt", "excerpt": "hello"},
    )
    ledger.record(before)
    ledger.record(Receipt(
        receipt_id="step-2:persistent-write:write", step=2, kind="write_file", success=True,
        summary="mutated out.txt", state_change=True, payload={"path": "out.txt", "bytes": 6},
    ))
    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    alias = next(row["evidence_ref"] for row in packet["evidence_index"] if row["receipt_id"] == before.receipt_id)
    turn = SolverTurn(
        kind="submit_outcome", summary="stale-only claim", claim="out.txt is complete",
        evidence_refs=(alias,),
    )
    decision, binding = validate_persistent_submission_binding(turn, packet, ledger, current_step=3)
    assert decision.allowed is False
    assert decision.reason_code == "evidence_stale"
    assert binding is None


def test_persistent_verifier_packet_exposes_exact_authoritative_check_namespace(tmp_path) -> None:
    envmap, compiled = _compiled(tmp_path)
    ledger, context, result, _uncited, alias = _ledger_and_packet(tmp_path, compiled)
    turn = SolverTurn(
        kind="submit_outcome", summary="claim", claim="out.txt contains hello.", evidence_refs=(alias,),
    )
    decision, binding = validate_persistent_submission_binding(turn, context, ledger, current_step=2)
    assert decision.allowed and binding is not None
    record_persistent_submission_claim(ledger, step=2, binding=binding)

    empty_packet = build_verifier_packet(compiled, ledger, step=2, reason="solver_submit", envmap=envmap)
    assert empty_packet["authoritative_check_ids"] == []

    checks = (
        CheckSpec("check-a", "authoritative a", "true", "eval", authoritative=True),
        CheckSpec("check-b", "authoritative b", "true", "eval", authoritative=True),
        CheckSpec("internal-smoke", "internal smoke", "true", "visible_smoke", authoritative=False),
    )
    with_checks = replace(
        compiled,
        check_plan_ids=("check-a", "internal-smoke", "check-b"),
        eval_index=EvalIndex(checks=checks),
    )
    packet = build_verifier_packet(with_checks, ledger, step=2, reason="solver_submit", envmap=envmap)
    assert packet["authoritative_check_ids"] == ["check-a", "check-b"]
    assert "internal-smoke" not in str(packet)
    assert packet_state_signature(packet) != packet_state_signature(empty_packet)

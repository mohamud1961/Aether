from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aether.envmap_builder import build_envmap_from_task
from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.runtime_ir import ActionRequest, SolverTurn
from aether.verifier_inspector import VerifierInspectionRequest


def _action(action_id: str, kind: str, capability_id: str, arguments: dict[str, Any]) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id=capability_id,
        arguments=arguments,
        intent="",
        expected_observation="",
        if_fail_next="",
    )


def _context(messages: list[dict[str, str]]) -> dict[str, Any]:
    assert messages[-1]["content"].startswith("[context_packet]\n")
    return json.loads(messages[-1]["content"].split("\n", 1)[1])


class _NeedsRepairHooks:
    def __init__(self) -> None:
        self.solve_messages: list[list[dict[str, str]]] = []
        self.solve_calls = 0
        self.verify_calls = 0

    def architect(self, _request: Any) -> Any:
        raise AssertionError("Thin persistent-primary path must not call Architect")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        self.solve_messages.append(messages)
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write initial candidate",
                actions=(_action("write", "write_file", "filesystem", {"path": "out.txt", "content": "bad\n"}),),
            )
        if self.solve_calls == 2:
            return SolverTurn(
                kind="act",
                summary="observe candidate",
                actions=(_action("read", "read_file", "filesystem", {"path": "out.txt"}),),
            )
        if self.solve_calls == 3:
            packet = _context(messages)
            evidence_ref = packet["latest_primary_result"]["outcome_receipts"][0]["evidence_ref"]
            return SolverTurn(
                kind="submit_outcome",
                summary="submit candidate",
                claim="out.txt is complete",
                evidence_refs=(evidence_ref,),
            )
        return SolverTurn(
            kind="act",
            summary="post-feedback observation",
            actions=(_action("read-after-feedback", "read_file", "filesystem", {"path": "out.txt"}),),
        )

    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        self.verify_calls += 1
        return json.dumps({
            "verdict": "needs_repair",
            "confidence": "high",
            "summary": "The current artifact is wrong.",
            "findings": [{
                "finding_id": "wrong-content",
                "summary": "out.txt contains bad but the raw task requires good.",
                "evidence": ["current out.txt contains bad"],
                "repair_instruction": "Rewrite out.txt to good using this prescribed strategy.",
                "applies_to": ["out.txt"],
            }],
        })


def test_thin_kernel_routes_neutral_factual_defect_to_first_post_verifier_solver_turn(tmp_path: Path) -> None:
    (tmp_path / "seed.txt").write_text("seed", encoding="utf-8")
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Create /app/out.txt containing good.",
        workspace_root="/app",
        projection_mode="factual_only",
    )
    executor = MemoryExecutor(files={"seed.txt": "seed"})
    hooks = _NeedsRepairHooks()
    kernel = AetherNextKernel(
        max_steps=4,
                solver_reanchor_mode="refined_m",
        runtime_identity={"task_id": "feedback-test", "run_id": "feedback-run", "primary_agent_id": "primary"},
    )

    result = kernel.run(envmap, executor, hooks)

    assert hooks.verify_calls == 1
    assert hooks.solve_calls == 4
    assert result.status == "incomplete"
    post_feedback = _context(hooks.solve_messages[3])
    findings = post_feedback["open_completion_findings"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["state"] == "review_claim_needs_repair"
    assert finding["epistemic_status"] == "review_interpretation_without_direct_witness"
    assert finding["source"] == "independent_review"
    assert finding["semantic_authority"] == "raw_user_task"
    assert finding["challenged_requirement_status"] == "review_interpretation_against_raw_user_task"
    assert finding["observed_precondition_status"] == "not_separately_reported_by_reviewer"
    assert finding["expected_result_status"] == "not_separately_task_grounded_by_reviewer"
    assert finding["coverage_status"] == "no_explicit_support_refs"
    assert finding["supporting_observation_count"] == 0
    assert finding["actual_observed_result_status"] == "review_reported_observation_without_explicit_inspection_ref"
    assert finding["summary"] == "out.txt contains bad but the raw task requires good."
    assert finding["observations"] == ["current out.txt contains bad"]
    assert finding["applies_to"] == ["out.txt"]
    assert finding["currentness"] == "current_candidate"
    assert finding["witness_handle"] == "receipt:step-2:completion_finding_witness:0"
    assert finding["witness_access"] == "read_output"
    witness = next(
        r for r in result.receipts if r.receipt_id == "step-2:completion_finding_witness:0"
    )
    assert witness.payload["observations"] == ["current out.txt contains bad"]
    assert witness.payload["semantic_authority"] == "raw_user_task"
    assert witness.payload["challenged_requirement_status"] == "review_interpretation_against_raw_user_task"
    assert witness.payload["coverage_status"] == "no_explicit_support_refs"
    assert witness.payload["actual_observed_result_status"] == "review_reported_observation_without_explicit_inspection_ref"
    assert witness.payload["expected_result_status"] == "not_separately_task_grounded_by_reviewer"
    assert witness.payload["repair_strategy_included"] is False
    assert "repair_instruction" not in witness.payload
    assert "prescribed strategy" not in json.dumps(witness.payload, sort_keys=True)
    rendered = json.dumps(post_feedback, sort_keys=True)
    assert "prescribed strategy" not in rendered
    assert "repair_instruction" not in rendered
    assert "model_verifier" not in rendered
    assert "verifier" not in rendered.lower()


class _IncoherentSubmitHooks:
    """Submit immediately after a mutation to reproduce A5's false-block path."""

    def __init__(self) -> None:
        self.solve_calls = 0
        self.verify_calls = 0
        self.solve_messages: list[list[dict[str, str]]] = []

    def architect(self, _request: Any) -> Any:
        raise AssertionError("Thin persistent-primary path must not call Architect")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        self.solve_messages.append(messages)
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write candidate",
                actions=(_action("write", "write_file", "filesystem", {"path": "out.txt", "content": "bad\n"}),),
            )
        if self.solve_calls == 2:
            packet = _context(messages)
            evidence_ref = packet["latest_primary_result"]["outcome_receipts"][0]["evidence_ref"]
            return SolverTurn(
                kind="submit_outcome",
                summary="candidate ready",
                claim="out.txt is complete",
                evidence_refs=(evidence_ref,),
            )
        return SolverTurn(
            kind="act",
            summary="continue from factual review result",
            actions=(_action("read-after-review", "read_file", "filesystem", {"path": "out.txt"}),),
        )

    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        self.verify_calls += 1
        return json.dumps({
            "verdict": "needs_repair",
            "confidence": "high",
            "summary": "Current bytes violate the raw task.",
            "findings": [{
                "finding_id": "wrong-content",
                "verdict": "needs_repair",
                "priority": "high",
                "summary": "out.txt contains bad but the raw task requires good.",
                "evidence": ["current out.txt contains bad"],
                "repair_instruction": "Replace the bytes.",
                "applies_to": ["out.txt"],
            }],
        })


def test_thin_incoherent_candidate_still_activates_independent_verifier_without_success(tmp_path: Path) -> None:
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Create /app/out.txt containing good.",
        workspace_root="/app",
        projection_mode="factual_only",
    )
    executor = MemoryExecutor(files={})
    hooks = _IncoherentSubmitHooks()
    kernel = AetherNextKernel(
        max_steps=3,
                solver_reanchor_mode="refined_m",
        runtime_identity={"task_id": "coherence-feedback", "run_id": "coherence-run", "primary_agent_id": "primary"},
    )

    result = kernel.run(envmap, executor, hooks)

    assert hooks.verify_calls == 1
    assert result.status != "completed"
    coherence = [r for r in result.receipts if r.kind == "submission_coherence_blocked"]
    assert coherence and coherence[-1].failure_class == "unobserved_state_change"
    assert any(r.kind == "model_verifier_result" for r in result.receipts)
    assert not any(
        r.kind == "model_verifier_skipped"
        and (r.payload or {}).get("reason") == "submission_coherence_blocked"
        for r in result.receipts
    )
    assert hooks.solve_calls == 3
    post_review = _context(hooks.solve_messages[2])
    finding = post_review["open_completion_findings"][0]
    assert finding["state"] == "review_claim_needs_repair"
    assert finding["epistemic_status"] == "review_interpretation_without_direct_witness"
    assert finding["observations"] == ["current out.txt contains bad"]
    assert finding["witness_handle"] == "receipt:step-1:completion_finding_witness:0"
    assert finding["currentness"] == "current_candidate"


class _CompletedIncoherentSubmitHooks:
    """Verifier independently observes the exact post-mutation snapshot and completes."""

    def __init__(self) -> None:
        self.solve_calls = 0
        self.verify_calls = 0

    def architect(self, _request: Any) -> Any:
        raise AssertionError("PCR production must not call Architect")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write complete candidate",
                actions=(_action("write-good", "write_file", "filesystem", {"path": "out.txt", "content": "good\n"}),),
            )
        packet = _context(messages)
        evidence_ref = packet["latest_primary_result"]["outcome_receipts"][0]["evidence_ref"]
        return SolverTurn(
            kind="submit_outcome",
            summary="candidate ready",
            claim="out.txt contains good",
            evidence_refs=(evidence_ref,),
        )

    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        raise AssertionError("verify_with_inspector should be selected")

    def verify_with_inspector(
        self,
        _packet: dict[str, Any],
        _compiled: Any,
        _ledger: Any,
        inspector: Any,
    ) -> str:
        self.verify_calls += 1
        rows = inspector((VerifierInspectionRequest(
            request_id="confirm-current",
            kind="read_file",
            path="out.txt",
            limit=4,
        ),))
        inspection_id = rows[0]["inspection_id"]
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "Current out.txt bytes satisfy the raw task.",
            "findings": [],
            "completion_evidence": [{
                "requirement": "out.txt contains good",
                "observed": "Direct current-state inspection returned good.",
                "inspection_refs": [inspection_id],
                "falsification_check": "Different bytes would falsify completion.",
            }],
        })


def test_reviewable_incoherent_submit_completes_after_verifier_establishes_current_observation(tmp_path: Path) -> None:
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Create /app/out.txt containing good.",
        workspace_root="/app",
        projection_mode="factual_only",
    )
    executor = MemoryExecutor(files={})
    hooks = _CompletedIncoherentSubmitHooks()
    kernel = AetherNextKernel(
        max_steps=3,
        solver_reanchor_mode="refined_m",
        runtime_identity={"task_id": "coherence-complete", "run_id": "coherence-complete-run", "primary_agent_id": "primary"},
    )

    result = kernel.run(envmap, executor, hooks)

    assert result.status == "completed"
    assert hooks.solve_calls == 2
    assert hooks.verify_calls == 1
    coherence = [r for r in result.receipts if r.kind == "submission_coherence_blocked"]
    assert coherence and coherence[-1].failure_class == "unobserved_state_change"
    assert any(r.kind == "inspection_record" and r.success for r in result.receipts)
    recovered = [
        r for r in result.receipts
        if r.kind == "submission_coherence_recovered_by_verifier_observation"
    ]
    assert recovered and recovered[-1].success is True
    assert not any(r.kind == "solver_submit_stalemate" for r in result.receipts)


class _CorrectedEvidenceAliasHooks:
    """Reject one malformed evidence alias, then retry the same snapshot correctly."""

    def __init__(self) -> None:
        self.solve_calls = 0
        self.verify_calls = 0

    def architect(self, _request: Any) -> Any:
        raise AssertionError("PCR production must not call Architect")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write complete candidate",
                actions=(_action("write-good", "write_file", "filesystem", {"path": "out.txt", "content": "good\n"}),),
            )
        if self.solve_calls == 2:
            return SolverTurn(
                kind="act",
                summary="observe complete candidate",
                actions=(_action("read-good", "read_file", "filesystem", {"path": "out.txt"}),),
            )
        packet = _context(messages)
        evidence_ref = packet["latest_primary_result"]["outcome_receipts"][0]["evidence_ref"]
        if self.solve_calls == 3:
            evidence_ref = evidence_ref[:-1]
        return SolverTurn(
            kind="submit_outcome",
            summary="candidate ready",
            claim="out.txt contains good",
            evidence_refs=(evidence_ref,),
        )

    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        raise AssertionError("verify_with_inspector should be selected")

    def verify_with_inspector(
        self,
        _packet: dict[str, Any],
        _compiled: Any,
        _ledger: Any,
        inspector: Any,
    ) -> str:
        self.verify_calls += 1
        rows = inspector((VerifierInspectionRequest(
            request_id="confirm-corrected-submit",
            kind="read_file",
            path="out.txt",
            limit=4,
        ),))
        inspection_id = rows[0]["inspection_id"]
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "Current out.txt bytes satisfy the raw task.",
            "findings": [],
            "completion_evidence": [{
                "requirement": "out.txt contains good",
                "observed": "Direct current-state inspection returned good.",
                "inspection_refs": [inspection_id],
                "falsification_check": "Different bytes would falsify completion.",
            }],
        })


def test_corrected_evidence_alias_can_resubmit_same_observed_snapshot(tmp_path: Path) -> None:
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Create /app/out.txt containing good.",
        workspace_root="/app",
        projection_mode="factual_only",
    )
    executor = MemoryExecutor(files={})
    hooks = _CorrectedEvidenceAliasHooks()
    kernel = AetherNextKernel(
        max_steps=5,
        solver_reanchor_mode="refined_m",
        runtime_identity={"task_id": "alias-retry", "run_id": "alias-retry-run", "primary_agent_id": "primary"},
    )

    result = kernel.run(envmap, executor, hooks)

    assert result.status == "completed"
    assert hooks.solve_calls == 4
    assert hooks.verify_calls == 1
    blocks = [r for r in result.receipts if r.kind == "submission_coherence_blocked"]
    assert len(blocks) == 1
    assert blocks[0].failure_class == "evidence_reference_not_current_context"
    assert not any(
        r.kind == "submission_coherence_blocked"
        and r.failure_class == "unchanged_resubmission"
        for r in result.receipts
    )
    claims = [r for r in result.receipts if r.kind == "primary_submission_claim"]
    assert len(claims) == 1

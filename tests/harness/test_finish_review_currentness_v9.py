from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aether.envmap_builder import build_envmap_from_task
from aether.execution import MemoryExecutor
from aether.ledger import Receipt
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


def _latest_evidence_ref(messages: list[dict[str, str]]) -> str:
    packet = _context(messages)
    refs = packet["latest_primary_result"]["outcome_receipts"]
    assert refs
    return refs[0]["evidence_ref"]


class _SameGenerationVerifierHooks:
    def __init__(self) -> None:
        self.solve_calls = 0
        self.verify_calls = 0
        self.write_ref = ""

    def architect(self, _request: Any) -> Any:
        raise AssertionError("PERSISTENT production must not call Architect")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write candidate",
                actions=(_action("write", "write_file", "filesystem", {"path": "out.txt", "content": "good\n"}),),
            )
        if not self.write_ref:
            self.write_ref = _latest_evidence_ref(messages)
        if self.solve_calls == 2:
            return SolverTurn(
                kind="finish_intent",
                summary="candidate is complete; request current-state review",
                claim="out.txt contains good",
                evidence_refs=(self.write_ref,),
            )
        return SolverTurn(
            kind="finish_outcome",
            summary="finish unchanged reviewed candidate",
            claim="out.txt contains good",
            evidence_refs=(self.write_ref,),
        )

    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        self.verify_calls += 1
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "Independent inspection confirms the unchanged candidate satisfies the task.",
            "findings": [],
        })


class _StaleGenerationVerifierHooks:
    def __init__(self) -> None:
        self.solve_calls = 0
        self.verify_calls = 0
        self.first_ref = ""
        self.second_ref = ""
        self.completion_modes: list[str] = []

    def configure_primary_completion_mode(self, mode: str) -> None:
        self.completion_modes.append(str(mode))

    def architect(self, _request: Any) -> Any:
        raise AssertionError("PERSISTENT production must not call Architect")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write first candidate",
                actions=(_action("write-1", "write_file", "filesystem", {"path": "out.txt", "content": "good\n"}),),
            )
        if self.solve_calls == 2:
            self.first_ref = _latest_evidence_ref(messages)
            return SolverTurn(
                kind="finish_intent",
                summary="review first candidate",
                claim="out.txt contains good",
                evidence_refs=(self.first_ref,),
            )
        if self.solve_calls == 3:
            return SolverTurn(
                kind="act",
                summary="mutate after completed review",
                actions=(_action("write-2", "write_file", "filesystem", {"path": "out.txt", "content": "changed\n"}),),
            )
        self.second_ref = _latest_evidence_ref(messages)
        return SolverTurn(
            kind="finish_outcome",
            summary="attempt finish after unreviewed mutation",
            claim="out.txt is final",
            evidence_refs=(self.second_ref,),
        )

    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        self.verify_calls += 1
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "The first candidate generation is complete.",
            "findings": [],
        })


class _UncertainObservationVerifierHooks:
    def __init__(self, *, content: str = "good\n", malformed: bool = False, bad_verdict: bool = False, invalid_observation: str = "") -> None:
        self.solve_calls = 0
        self.verify_calls = 0
        self.write_ref = ""
        self.content = content
        self.malformed = malformed
        self.bad_verdict = bad_verdict
        self.invalid_observation = invalid_observation

    def architect(self, _request: Any) -> Any:
        raise AssertionError("PERSISTENT production must not call Architect")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write candidate",
                actions=(_action("write", "write_file", "filesystem", {"path": "out.txt", "content": self.content}),),
            )
        if not self.write_ref:
            self.write_ref = _latest_evidence_ref(messages)
        if self.solve_calls == 2:
            return SolverTurn(
                kind="finish_intent",
                summary="candidate is complete; request current-state review",
                claim="out.txt contains good",
                evidence_refs=(self.write_ref,),
            )
        return SolverTurn(
            kind="finish_outcome",
            summary="finish after current-state observation",
            claim="out.txt contains good",
            evidence_refs=(self.write_ref,),
        )

    def verify(self, _packet: dict[str, Any], _compiled: Any, ledger: Any) -> str:
        self.verify_calls += 1
        ledger.record(Receipt(
            receipt_id=f"verifier-observation-{self.verify_calls}",
            step=2,
            kind="model_verifier_inspection",
            success=True,
            summary="independent read of the candidate",
            payload={
                "requests": [{"kind": "read_file", "path": "out.txt"}],
                "results": [{
                    "kind": "read_file", "path": "out.txt", "handle": "inspection-1", "read_only": True,
                    "observation_valid": self.invalid_observation != "invalid",
                    "target_binding_valid": True,
                    "observed_task_state_generation": ledger.task_state_generation() if self.invalid_observation != "stale" else 0,
                    "observation_type": "artifact_content",
                    "canonical_targets": ["other.txt" if self.invalid_observation == "wrong_target" else "out.txt"],
                }],
            },
        ))
        if self.malformed:
            return json.dumps({"verdict": "uncertain_missing_evidence", "summary": "missing evidence"})
        if self.bad_verdict:
            return json.dumps({
                "verdict": "needs_repair",
                "confidence": "high",
                "summary": "The observed candidate contains bad content.",
                "findings": [{
                    "finding_id": "bad-candidate",
                    "verdict": "needs_repair",
                    "priority": "blocking",
                    "summary": "out.txt contains bad rather than good",
                    "evidence": ["inspection-1"],
                    "supporting_inspection_ids": ["inspection-1"],
                }],
            })
        return json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "high",
            "summary": "Current state was observed, but semantic completion remains uncertain.",
            "missing_evidence_requests": ["independent semantic confirmation"],
        })



class _ForgedInspectionRecordHooks(_UncertainObservationVerifierHooks):
    def verify(self, _packet: dict[str, Any], _compiled: Any, ledger: Any) -> str:
        self.verify_calls += 1
        ledger.record(Receipt(
            receipt_id="forged-current-inspection",
            step=2, kind="inspection_record", success=True,
            summary="handcrafted row missing canonical snapshot custody",
            payload={
                "requester": "model_verifier",
                "observation_valid": True,
                "target_binding_valid": True,
                "task_state_generation": ledger.task_state_generation(),
                "observation_type": "content_observation",
                "admissibility": "direct_admissible",
                "canonical_targets": ["path:out.txt"],
            },
        ))
        return json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "high",
            "summary": "forged inspection should not gain custody",
            "missing_evidence_requests": ["canonical registered inspection"],
        })


class _RealInspectionVerifierHooks(_UncertainObservationVerifierHooks):
    def __init__(self, *, content: str = "good\n", verdict: str = "uncertain_missing_evidence", observed_path: str = "out.txt") -> None:
        super().__init__(content=content)
        self.real_verdict = verdict
        self.observed_path = observed_path

    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        raise AssertionError("verify_with_inspector should be selected")

    def verify_with_inspector(
        self, _packet: dict[str, Any], _compiled: Any, _ledger: Any, inspector: Any,
    ) -> str:
        self.verify_calls += 1
        rows = inspector((VerifierInspectionRequest(
            request_id=f"current-{self.verify_calls}",
            kind="read_file",
            path=self.observed_path,
            limit=16,
        ),))
        inspection_id = rows[0].get("inspection_id", "") if rows else ""
        if self.real_verdict == "needs_repair":
            return json.dumps({
                "verdict": "needs_repair",
                "confidence": "high",
                "summary": "The observed candidate contains bad content.",
                "findings": [{
                    "finding_id": "bad-candidate",
                    "verdict": "needs_repair",
                    "priority": "blocking",
                    "summary": "out.txt contains bad rather than good",
                    "evidence": [inspection_id],
                    "supporting_inspection_ids": [inspection_id],
                }],
            })
        if self.real_verdict == "completed":
            return json.dumps({
                "verdict": "completed",
                "confidence": "high",
                "summary": "Current candidate was independently observed.",
                "findings": [],
            })
        return json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "high",
            "summary": "Current state was observed, but semantic completion remains uncertain.",
            "missing_evidence_requests": ["independent semantic confirmation"],
        })


class _SuffixCollisionVerifierHooks(_RealInspectionVerifierHooks):
    def __init__(self) -> None:
        super().__init__(observed_path="out.txt")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act", summary="write decoy basename",
                actions=(_action("decoy", "write_file", "filesystem", {"path": "out.txt", "content": "decoy\n"}),),
            )
        if self.solve_calls == 2:
            return SolverTurn(
                kind="act", summary="write actual candidate in another directory",
                actions=(_action("actual", "write_file", "filesystem", {"path": "dir1/out.txt", "content": "good\n"}),),
            )
        if not self.write_ref:
            self.write_ref = _latest_evidence_ref(messages)
        if self.solve_calls == 3:
            return SolverTurn(
                kind="finish_intent", summary="review actual candidate",
                claim="dir1/out.txt contains good", evidence_refs=(self.write_ref,),
            )
        return SolverTurn(
            kind="finish_outcome", summary="attempt finish after decoy inspection",
            claim="dir1/out.txt contains good", evidence_refs=(self.write_ref,),
        )


class _OpaqueNewerMutationVerifierHooks(_RealInspectionVerifierHooks):
    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act", summary="write candidate",
                actions=(_action("write", "write_file", "filesystem", {"path": "out.txt", "content": "good\n"}),),
            )
        if self.solve_calls == 2:
            return SolverTurn(
                kind="act", summary="launch newer opaque task-world process",
                actions=(_action("launch", "launch_process", "managed_process", {"service_name": "worker", "command": "worker"}),),
            )
        if not self.write_ref:
            self.write_ref = _latest_evidence_ref(messages)
        if self.solve_calls == 3:
            return SolverTurn(
                kind="finish_intent", summary="review after opaque mutation",
                claim="current task state is ready", evidence_refs=(self.write_ref,),
            )
        return SolverTurn(
            kind="finish_outcome", summary="attempt finish after file-only review",
            claim="current task state is ready", evidence_refs=(self.write_ref,),
        )

def _env(tmp_path: Path):
    return build_envmap_from_task(
        str(tmp_path),
        "Create /app/out.txt containing good.",
        workspace_root="/app",
        projection_mode="factual_only",
    )


def _kernel(max_steps: int) -> AetherNextKernel:
    return AetherNextKernel(
        max_steps=max_steps,
        solver_reanchor_mode="refined_m",
        runtime_identity={
            "task_id": "finish-review-currentness",
            "run_id": "finish-review-currentness-run",
            "primary_agent_id": "primary",
        },
    )


def test_ready_finish_intent_plus_terminal_pass_completes_without_second_solver_turn(tmp_path: Path) -> None:
    hooks = _SameGenerationVerifierHooks()
    result = _kernel(4).run(_env(tmp_path), MemoryExecutor(files={}), hooks)

    assert result.status == "completed"
    assert hooks.solve_calls == 2, "finish_intent already carries Frontier's terminal semantic decision"
    assert hooks.verify_calls == 1
    finishes = [r for r in result.receipts if r.kind == "frontier_finish"]
    assert len(finishes) == 1
    assert finishes[0].payload["completion_source"] == "finish_intent_plus_terminal_verifier_pass"
    assert finishes[0].payload["semantic_authority"] == "frontier_and_independent_terminal_review"
    assert not any(
        r.kind == "runtime_accounting"
        and (r.payload or {}).get("counter") == "solver_finish_turns"
        for r in result.receipts
    )


class _OpaqueUnknownCompletedReviewHooks(_OpaqueNewerMutationVerifierHooks):
    def __init__(self) -> None:
        super().__init__()
        self.real_verdict = "completed"


def test_terminal_pass_cannot_complete_unknown_boundary_without_exact_review_observation(tmp_path: Path) -> None:
    hooks = _OpaqueUnknownCompletedReviewHooks()
    envmap = build_envmap_from_task(
        str(tmp_path), "Create /app/out.txt containing good and keep a worker process running.",
        workspace_root="/app", projection_mode="factual_only",
    )
    result = _kernel(6).run(envmap, MemoryExecutor(files={}), hooks)

    assert result.status != "completed"
    assert hooks.verify_calls == 1
    assert not any(
        r.kind == "frontier_finish"
        and (r.payload or {}).get("completion_source") == "finish_intent_plus_terminal_verifier_pass"
        for r in result.receipts
    )


def test_completed_verdict_without_registered_inspection_can_close_already_ready_boundary(tmp_path: Path) -> None:
    hooks = _SameGenerationVerifierHooks()
    result = _kernel(4).run(_env(tmp_path), MemoryExecutor(files={}), hooks)

    assert result.status == "completed"
    assert hooks.verify_calls == 1
    # No inspection authority is manufactured: it is unnecessary because the
    # finish-intent boundary was already mechanically current before review.
    assert not any(
        r.kind == "submission_coherence_recovered_by_prior_verifier_observation"
        for r in result.receipts
    )
    finishes = [r for r in result.receipts if r.kind == "frontier_finish"]
    assert len(finishes) == 1
    assert finishes[0].payload["completion_source"] == "finish_intent_plus_terminal_verifier_pass"


def test_terminal_pass_closes_before_any_redundant_later_mutation_turn(tmp_path: Path) -> None:
    hooks = _StaleGenerationVerifierHooks()
    result = _kernel(4).run(_env(tmp_path), MemoryExecutor(files={}), hooks)

    assert result.status == "completed"
    assert hooks.verify_calls == 1
    assert hooks.solve_calls == 2
    assert not any(
        r.kind == "write_file" and (r.payload or {}).get("content") == "changed\n"
        for r in result.receipts
    )


def test_same_generation_observation_is_currentness_only_and_frontier_can_finish(tmp_path: Path) -> None:
    hooks = _RealInspectionVerifierHooks()
    result = _kernel(4).run(_env(tmp_path), MemoryExecutor(files={}), hooks)

    assert result.status == "completed"
    assert hooks.verify_calls == 1
    recovered = [
        r for r in result.receipts
        if r.kind == "submission_coherence_recovered_by_prior_verifier_observation"
    ]
    assert len(recovered) == 1
    assert recovered[0].payload["semantic_authority"] == "frontier"
    assert recovered[0].payload["verifier_observation_status"] == "current_generation_observed"


def test_advisory_bad_candidate_observation_does_not_replace_frontier_authority(tmp_path: Path) -> None:
    hooks = _RealInspectionVerifierHooks(content="bad\n", verdict="needs_repair")
    result = _kernel(4).run(_env(tmp_path), MemoryExecutor(files={}), hooks)

    # The advisory finding is not promoted to semantic authority.  The only
    # reason this fixture may finish is Frontier's own final decision; currentness
    # alone does not turn the observed bad candidate into a successful verdict.
    assert result.status == "completed"
    assert hooks.verify_calls == 1
    write_receipt = next(r for r in result.receipts if r.kind == "write_file")
    assert write_receipt.payload["content"] == "bad\n"
    assert any(r.kind == "completion_finding_witness" for r in result.receipts)
    recovered = [
        r for r in result.receipts
        if r.kind == "submission_coherence_recovered_by_prior_verifier_observation"
    ]
    assert len(recovered) == 1
    assert recovered[0].payload["semantic_authority"] == "frontier"
    assert recovered[0].payload["verifier_observation_status"] == "current_generation_observed"


def test_invalid_same_generation_observation_remains_blocking(tmp_path: Path) -> None:
    for invalid_observation in ("invalid", "stale", "wrong_target"):
        hooks = _UncertainObservationVerifierHooks(invalid_observation=invalid_observation)
        result = _kernel(4).run(_env(tmp_path / invalid_observation), MemoryExecutor(files={}), hooks)

        assert result.status != "completed"
        assert hooks.verify_calls == 1
        assert not any(
            r.kind == "submission_coherence_recovered_by_prior_verifier_observation"
            for r in result.receipts
        )


def test_malformed_uncertain_review_evidence_remains_blocking(tmp_path: Path) -> None:
    hooks = _UncertainObservationVerifierHooks(malformed=True)
    result = _kernel(4).run(_env(tmp_path), MemoryExecutor(files={}), hooks)

    assert result.status != "completed"
    assert hooks.verify_calls == 1
    assert not any(
        r.kind == "submission_coherence_recovered_by_prior_verifier_observation"
        for r in result.receipts
    )
    assert not any(r.kind == "frontier_finish" for r in result.receipts)


def test_suffix_collision_does_not_alias_different_workspace_paths(tmp_path: Path) -> None:
    hooks = _SuffixCollisionVerifierHooks()
    envmap = build_envmap_from_task(
        str(tmp_path), "Create /app/dir1/out.txt containing good.",
        workspace_root="/app", projection_mode="factual_only",
    )
    result = _kernel(6).run(envmap, MemoryExecutor(files={}), hooks)

    assert result.status != "completed"
    assert hooks.verify_calls == 1
    inspections = [r for r in result.receipts if r.kind == "inspection_record" and r.success]
    assert inspections
    assert inspections[-1].payload["canonical_targets"] == ["path:out.txt"]
    assert not any(
        r.kind == "submission_coherence_recovered_by_prior_verifier_observation"
        for r in result.receipts
    )


def test_newer_unknown_target_mutation_cannot_be_skipped_by_file_review(tmp_path: Path) -> None:
    hooks = _OpaqueNewerMutationVerifierHooks()
    envmap = build_envmap_from_task(
        str(tmp_path), "Create /app/out.txt containing good and keep a worker process running.",
        workspace_root="/app", projection_mode="factual_only",
    )
    result = _kernel(6).run(envmap, MemoryExecutor(files={}), hooks)

    assert result.status != "completed"
    assert hooks.verify_calls == 1
    assert any(r.kind == "process_launch" and r.state_change for r in result.receipts)
    assert any(r.kind == "inspection_record" and r.payload.get("canonical_targets") == ["path:out.txt"] for r in result.receipts)
    assert not any(
        r.kind == "submission_coherence_recovered_by_prior_verifier_observation"
        for r in result.receipts
    )


def test_handcrafted_inspection_record_without_snapshot_binding_cannot_supply_currentness(tmp_path: Path) -> None:
    hooks = _ForgedInspectionRecordHooks()
    result = _kernel(4).run(_env(tmp_path), MemoryExecutor(files={}), hooks)

    assert result.status != "completed"
    forged = next(r for r in result.receipts if r.receipt_id == "forged-current-inspection")
    assert forged.payload["canonical_targets"] == ["path:out.txt"]
    assert not any(
        r.kind == "submission_coherence_recovered_by_prior_verifier_observation"
        for r in result.receipts
    )


class _LiveFiniteJobFinishIntentHooks:
    def __init__(self) -> None:
        self.solve_calls = 0
        self.verify_calls = 0
        self.launch_ref = ""

    def architect(self, _request: Any) -> Any:
        raise AssertionError("PERSISTENT production must not call Architect")

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="start finite validation",
                actions=(_action(
                    "validation",
                    "start_job",
                    "managed_process",
                    {"service_name": "validation", "command": "sleep 100"},
                ),),
            )
        if not self.launch_ref:
            self.launch_ref = _latest_evidence_ref(messages)
        return SolverTurn(
            kind="finish_intent",
            summary="attempt completion while validation is live",
            claim="validation work is complete",
            evidence_refs=(self.launch_ref,),
        )

    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        self.verify_calls += 1
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "should not be called while finite validation is live",
            "findings": [],
        })


def test_live_finite_job_defers_terminal_review_before_verifier(tmp_path: Path) -> None:
    hooks = _LiveFiniteJobFinishIntentHooks()
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Start one finite background validation job and do not finish until it completes.",
        workspace_root="/app",
        projection_mode="factual_only",
    )
    result = _kernel(3).run(envmap, MemoryExecutor(files={}), hooks)

    assert result.status != "completed"
    assert hooks.verify_calls == 0
    deferred = [
        receipt for receipt in result.receipts
        if receipt.kind == "advisory_review_deferred_mechanical_readiness"
    ]
    assert deferred
    assert "live_finite_background_job" in deferred[-1].payload["blocker_codes"]
    assert not any(receipt.kind == "model_verifier_packet" for receipt in result.receipts)


class _StoppedFiniteJobFinishIntentHooks(_LiveFiniteJobFinishIntentHooks):
    def __init__(self) -> None:
        super().__init__()
        self.stop_ref = ""

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="start finite validation",
                actions=(_action(
                    "validation",
                    "start_job",
                    "managed_process",
                    {"service_name": "validation", "command": "sleep 100"},
                ),),
            )
        if self.solve_calls == 2:
            return SolverTurn(
                kind="act",
                summary="stop validation without a successful terminal result",
                actions=(_action(
                    "stop-validation",
                    "stop_process",
                    "managed_process",
                    {"target": "validation"},
                ),),
            )
        if not self.stop_ref:
            self.stop_ref = _latest_evidence_ref(messages)
        return SolverTurn(
            kind="finish_intent",
            summary="attempt completion after merely stopping validation",
            claim="validation work is complete",
            evidence_refs=(self.stop_ref,),
        )


def test_stopped_finite_job_debt_defers_terminal_review_before_verifier(tmp_path: Path) -> None:
    hooks = _StoppedFiniteJobFinishIntentHooks()
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Start one finite background validation job. If needed stop it, but do not finish unless its work succeeded.",
        workspace_root="/app",
        projection_mode="factual_only",
    )
    result = _kernel(4).run(envmap, MemoryExecutor(files={}), hooks)

    assert result.status != "completed"
    assert hooks.verify_calls == 0
    deferred = [
        receipt for receipt in result.receipts
        if receipt.kind == "advisory_review_deferred_mechanical_readiness"
    ]
    assert deferred
    assert "unsuccessful_finite_background_job" in deferred[-1].payload["blocker_codes"]
    assert not any(receipt.kind == "model_verifier_packet" for receipt in result.receipts)


class _LiveFiniteJobLegacySubmitHooks(_LiveFiniteJobFinishIntentHooks):
    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="start finite validation",
                actions=(_action(
                    "validation",
                    "start_job",
                    "managed_process",
                    {"service_name": "validation", "command": "sleep 100"},
                ),),
            )
        if not self.launch_ref:
            self.launch_ref = _latest_evidence_ref(messages)
        return SolverTurn(
            kind="submit_outcome",
            summary="legacy submit while validation is live",
            claim="validation work is complete",
            evidence_refs=(self.launch_ref,),
        )


def test_legacy_submit_outcome_cannot_bypass_terminal_review_preflight(tmp_path: Path) -> None:
    hooks = _LiveFiniteJobLegacySubmitHooks()
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Start one finite background validation job and do not finish until it completes.",
        workspace_root="/app",
        projection_mode="factual_only",
    )
    result = _kernel(3).run(envmap, MemoryExecutor(files={}), hooks)

    assert result.status != "completed"
    assert hooks.verify_calls == 0
    deferred = [
        receipt for receipt in result.receipts
        if receipt.kind == "advisory_review_deferred_mechanical_readiness"
    ]
    assert deferred
    assert "live_finite_background_job" in deferred[-1].payload["blocker_codes"]
    assert not any(receipt.kind == "model_verifier_packet" for receipt in result.receipts)


class _RepeatedSameGenerationFinishIntentHooks(_SameGenerationVerifierHooks):
    def verify(self, _packet: dict[str, Any], _compiled: Any, _ledger: Any) -> str:
        self.verify_calls += 1
        return json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "high",
            "summary": "review attempted but terminal semantic confirmation is not established",
            "missing_evidence_requests": ["independent semantic confirmation"],
        })

    def solve(self, messages: list[dict[str, str]], _compiled: Any) -> SolverTurn:
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write candidate",
                actions=(_action("write", "write_file", "filesystem", {"path": "out.txt", "content": "good\n"}),),
            )
        if not self.write_ref:
            self.write_ref = _latest_evidence_ref(messages)
        if self.solve_calls in {2, 3}:
            return SolverTurn(
                kind="finish_intent",
                summary="repeat finish intent without changing task state",
                claim="out.txt contains good",
                evidence_refs=(self.write_ref,),
            )
        return SolverTurn(
            kind="finish_outcome",
            summary="finish unchanged reviewed candidate",
            claim="out.txt contains good",
            evidence_refs=(self.write_ref,),
        )


def test_repeated_finish_intent_same_generation_does_not_reinvoke_verifier(tmp_path: Path) -> None:
    hooks = _RepeatedSameGenerationFinishIntentHooks()
    result = _kernel(5).run(_env(tmp_path), MemoryExecutor(files={}), hooks)

    assert hooks.verify_calls == 1
    skipped = [
        receipt for receipt in result.receipts
        if receipt.kind == "advisory_review_skipped"
        and receipt.payload.get("reason") == "already_reviewed_generation"
    ]
    assert len(skipped) == 1
    assert not any(
        receipt.kind == "advisory_review_deferred_mechanical_readiness"
        for receipt in result.receipts
    )

from __future__ import annotations

from pathlib import Path

from aether.envmap_builder import build_envmap_from_task
from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.pcr_context import evidence_alias
from aether.runtime_ir import ActionRequest, SolverTurn


def _env(tmp_path: Path):
    return build_envmap_from_task(
        str(tmp_path),
        "Create /app/out.txt containing OK.",
        workspace_root="/app",
        projection_mode="factual_only",
    )


def _write() -> SolverTurn:
    return SolverTurn(
        kind="act",
        summary="write",
        actions=(ActionRequest(
            action_id="write", kind="write_file", capability_id="filesystem",
            arguments={"path": "out.txt", "content": "OK"}, intent="",
            expected_observation="", if_fail_next="",
        ),),
    )


def _read() -> SolverTurn:
    return SolverTurn(
        kind="act",
        summary="read",
        actions=(ActionRequest(
            action_id="read", kind="read_file", capability_id="filesystem",
            arguments={"path": "out.txt"}, intent="",
            expected_observation="", if_fail_next="",
        ),),
    )


def _complete(kind: str) -> SolverTurn:
    return SolverTurn(
        kind=kind,
        summary="out.txt contains OK",
        claim="out.txt contains OK",
        evidence_refs=(evidence_alias("step-1:read:read"),),
    )


class _Hooks:
    def __init__(self, turns: list[SolverTurn], review_verdict: str = "completed") -> None:
        self.turns = list(turns)
        self.verify_calls = 0
        self.review_verdict = review_verdict

    def solve(self, _messages, _compiled):
        return self.turns.pop(0)

    def verify(self, _packet, _compiled, _ledger):
        self.verify_calls += 1
        if self.review_verdict == "needs_repair":
            return {
                "verdict": "needs_repair",
                "confidence": "high",
                "summary": "review challenge",
                "findings": [{
                    "finding_id": "challenge",
                    "verdict": "needs_repair",
                    "priority": "high",
                    "summary": "Review claims the content needs another check.",
                    "evidence": ["observed out.txt=OK but reviewer interpretation remains skeptical"],
                    "repair_instruction": "change the file",
                    "applies_to": ["out.txt"],
                    "keep_until": "resolved_or_superseded",
                    "owner": "solver_state",
                    "supporting_inspection_ids": [],
                    "repair_condition": "",
                    "required_evidence_route": "",
                }],
            }
        return {"verdict": "completed", "confidence": "high", "summary": "review complete"}


def test_finish_intent_reviews_once_then_luna_finish_has_final_semantic_authority(tmp_path: Path) -> None:
    hooks = _Hooks(
        [_write(), _read(), _complete("finish_intent"), _complete("finish_outcome")],
        review_verdict="needs_repair",
    )
    result = AetherNextKernel(max_steps=4).run(
        _env(tmp_path), MemoryExecutor(files={}), hooks,
    )

    assert result.status == "completed"
    assert hooks.verify_calls == 1
    assert any(r.kind == "advisory_review_result" for r in result.receipts)
    finish = [r for r in result.receipts if r.kind == "luna_finish"]
    assert len(finish) == 1
    assert finish[0].payload["review_invoked_by_finish"] is False
    assert finish[0].payload["semantic_authority"] == "luna"
    # The reviewer challenge remains preserved evidence; it is not a hidden veto.
    assert any(r.kind == "completion_finding_witness" for r in result.receipts)


def test_finish_intent_does_not_repeat_review_for_unchanged_candidate_generation(tmp_path: Path) -> None:
    hooks = _Hooks([
        _write(), _read(), _complete("finish_intent"), _complete("finish_intent")
    ])
    result = AetherNextKernel(max_steps=4).run(
        _env(tmp_path), MemoryExecutor(files={}), hooks,
    )

    assert result.status != "completed"
    assert hooks.verify_calls == 1
    skipped = [r for r in result.receipts if r.kind == "advisory_review_skipped"]
    assert len(skipped) == 1
    assert skipped[0].payload["reason"] == "already_reviewed_generation"


def test_finish_never_implicitly_invokes_review(tmp_path: Path) -> None:
    hooks = _Hooks([_write(), _read(), _complete("finish_outcome")])
    result = AetherNextKernel(max_steps=3).run(
        _env(tmp_path), MemoryExecutor(files={}), hooks,
    )

    assert result.status == "completed"
    assert hooks.verify_calls == 0
    assert not any(r.kind.startswith("model_verifier") for r in result.receipts)
    finish = next(r for r in result.receipts if r.kind == "luna_finish")
    assert finish.payload["review_invoked_by_finish"] is False


def test_finish_intent_review_unavailable_does_not_create_candidate_defect(tmp_path: Path) -> None:
    class Unavailable(_Hooks):
        def verify(self, _packet, _compiled, _ledger):
            self.verify_calls += 1
            raise RuntimeError("review backend unavailable")

    hooks = Unavailable([
        _write(), _read(), _complete("finish_intent"), _complete("finish_outcome")
    ])
    result = AetherNextKernel(max_steps=4).run(
        _env(tmp_path), MemoryExecutor(files={}), hooks,
    )

    assert result.status == "completed"
    assert hooks.verify_calls == 1
    unavailable = [r for r in result.receipts if r.kind == "advisory_review_unavailable"]
    assert len(unavailable) == 1
    assert "does not establish a candidate defect" in unavailable[0].summary


def test_review_unavailable_finish_can_bridge_prior_opaque_command_with_fresh_typed_read(tmp_path: Path) -> None:
    from aether.execution import CommandResult

    command_turn = SolverTurn(
        kind="act", summary="validate externally",
        actions=(ActionRequest(
            action_id="cmd", kind="run_command", capability_id="shell",
            arguments={"command": "validate"}, intent="",
            expected_observation="", if_fail_next="",
        ),),
    )

    class Unavailable(_Hooks):
        def verify(self, _packet, _compiled, _ledger):
            self.verify_calls += 1
            raise RuntimeError("review backend unavailable")

    hooks = Unavailable([
        command_turn, _read(), _complete("finish_intent"), _complete("finish_outcome")
    ])
    executor = MemoryExecutor(files={"out.txt": "OK"})
    executor.register_command(
        "validate",
        lambda _executor, command: CommandResult(command=command, exit_code=0, stdout="validated\n"),
    )

    result = AetherNextKernel(max_steps=4).run(
        _env(tmp_path), executor, hooks,
    )

    assert result.status == "completed"
    assert hooks.verify_calls == 1
    assert any(r.kind == "run_command" for r in result.receipts)
    assert any(r.kind == "advisory_review_unavailable" for r in result.receipts)
    assert any(r.kind == "luna_finish" for r in result.receipts)
    assert not any(r.kind == "luna_finish_blocked" for r in result.receipts)


def test_review_unavailable_finish_can_bridge_opaque_command_with_current_service_probe(tmp_path: Path) -> None:
    from aether.execution import CommandResult

    launch = SolverTurn(
        kind="act", summary="launch service",
        actions=(ActionRequest(
            action_id="launch", kind="start_job", capability_id="managed_process",
            arguments={"service_name": "health-server", "command": "serve"}, intent="",
            expected_observation="", if_fail_next="",
        ),),
    )
    validate = SolverTurn(
        kind="act", summary="validate service",
        actions=(ActionRequest(
            action_id="curl", kind="run_command", capability_id="shell",
            arguments={"command": "curl-health"}, intent="",
            expected_observation="", if_fail_next="",
        ),),
    )
    probe = SolverTurn(
        kind="act", summary="observe managed service",
        actions=(ActionRequest(
            action_id="probe", kind="probe_service", capability_id="service_probe",
            arguments={"target": "health-server"}, intent="",
            expected_observation="", if_fail_next="",
        ),),
    )
    service_evidence = evidence_alias("step-2:probe:probe")
    finish_intent = SolverTurn(
        kind="finish_intent", summary="service is ready", claim="service is ready",
        evidence_refs=(service_evidence,),
    )
    finish = SolverTurn(
        kind="finish_outcome", summary="service is ready", claim="service is ready",
        evidence_refs=(service_evidence,),
    )

    class Unavailable(_Hooks):
        def verify(self, _packet, _compiled, _ledger):
            self.verify_calls += 1
            raise RuntimeError("review backend unavailable")

    hooks = Unavailable([launch, validate, probe, finish_intent, finish])
    executor = MemoryExecutor(files={})
    executor.register_command(
        "curl-health",
        lambda _executor, command: CommandResult(command=command, exit_code=0, stdout="READY\n"),
    )
    result = AetherNextKernel(max_steps=5).run(_env(tmp_path), executor, hooks)

    assert result.status == "completed"
    assert hooks.verify_calls == 1
    assert any(r.kind == "service_probe" and r.success for r in result.receipts)
    assert any(r.kind == "advisory_review_unavailable" for r in result.receipts)
    assert any(r.kind == "luna_finish" for r in result.receipts)
    assert not any(r.kind == "luna_finish_blocked" for r in result.receipts)
    # The global task-world boundary remains explicitly unknown; only the exact
    # current claim is admitted through its cited typed observation.
    claim = [r for r in result.receipts if r.kind == "primary_submission_claim"][-1]
    assert claim.payload["task_state_snapshot_known"] is False

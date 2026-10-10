from __future__ import annotations

import json
from pathlib import Path

from aether.envmap_builder import build_envmap_from_task
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import ActionRequest, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop
from aether.verifier import ModelVerifierResult, VerifierFinding, parse_model_verifier_result


def _packet(messages):
    for message in messages:
        content = str(message.get("content", ""))
        if content.startswith("[context_packet]\n"):
            return json.loads(content[len("[context_packet]\n"):])
    raise AssertionError("context packet missing")


def _latest(messages, evidence_type: str) -> str:
    rows = [
        row for row in _packet(messages).get("evidence_index", [])
        if isinstance(row, dict)
        and row.get("evidence_type") == evidence_type
        and row.get("evidence_ref")
        and row.get("completion_evidence_eligible", True)
    ]
    assert rows
    return str(rows[0]["evidence_ref"])


def _action(index: int, kind: str, capability_id: str, arguments: dict) -> ActionRequest:
    return ActionRequest(
        action_id=f"a{index}",
        kind=kind,
        capability_id=capability_id,
        arguments=arguments,
        intent="resolve evidence gap",
        expected_observation="one exact result",
        if_fail_next="inspect",
    )


class _Hooks:
    def __init__(self) -> None:
        self.solve_calls = 0
        self.verify_calls = 0
        self.messages = []

    def solve(self, messages, _compiled):
        self.solve_calls += 1
        self.messages.append(messages)
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act", summary="observe candidate", evidence_gap="need state",
                actions=(_action(1, "read_file", "filesystem", {"path": "app.py"}),),
            )
        if self.solve_calls == 2:
            return SolverTurn(
                kind="finish_intent", summary="finish candidate", claim="candidate complete",
                evidence_refs=(_latest(messages, "read_file"),),
            )
        findings = _packet(messages).get("open_completion_findings") or []
        if self.solve_calls == 3:
            assert len(findings) == 1
            assert findings[0]["finding_id"] == "vf1-gap"
            assert findings[0]["source"] == "independent_review"
            return SolverTurn(
                kind="act", summary="repair review finding", evidence_gap="review found defect",
                actions=(_action(3, "write_file", "filesystem", {"path": "app.py", "content": "x=2\n"}),),
            )
        if self.solve_calls == 4:
            assert findings
            return SolverTurn(
                kind="act", summary="observe repaired candidate", evidence_gap="need current evidence",
                actions=(_action(4, "read_file", "filesystem", {"path": "app.py"}),),
            )
        return SolverTurn(
            kind="finish_intent",
            summary="finish repaired candidate",
            claim="candidate repaired and observed current",
            evidence_refs=(_latest(messages, "read_file"),),
        )

    def verify(self, packet, _compiled, _ledger):
        self.verify_calls += 1
        if self.verify_calls == 1:
            return ModelVerifierResult(
                verdict="needs_repair",
                confidence="high",
                summary="production value is still old",
                findings=(VerifierFinding(
                    finding_id="vf1-gap",
                    created_step=0,
                    verdict="needs_repair",
                    priority="blocking",
                    summary="app.py still contains the old value",
                    evidence=("current file inspection",),
                    applies_to=("app.py",),
                    owner="model_verifier",
                    observed_task_state_generation=int(
                        packet.get("task_state_generation", 0) or 0
                    ),
                ),),
            )
        return ModelVerifierResult(
            verdict="completed",
            confidence="high",
            summary="repaired candidate is current",
            completion_evidence=(),
        )


def test_vf1_rejection_is_visible_then_solver_repairs_and_reviewer_reruns(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ws"
    root.mkdir(parents=True)
    (root / "app.py").write_text("x=1\n")
    env = build_envmap_from_task(
        str(tmp_path / "none"),
        "Change app.py to the correct value and finish.",
        workspace_root=str(root),
        projection_mode="factual_only",
    )
    hooks = _Hooks()
    result = run_thin_loop(
        env,
        SubprocessExecutor(str(root)),
        hooks,
        config=ThinLoopConfig(
            max_steps=8,
            max_solver_turns=8,
            max_accepted_task_actions=4,
            runtime_identity={
                "task_id": "vf1-reentry",
                "run_id": "vf1-reentry-run",
                "primary_agent_id": "primary",
                "budgets": {
                    "max_kernel_steps": 8,
                    "max_solver_turns": 8,
                    "max_accepted_task_actions": 4,
                },
            },
            completion_record_mode="off",
            terminal_verifier_mode="terminal_verifier_v1",
        ),
    )
    assert result.status == "submitted"
    assert hooks.solve_calls == 5
    assert hooks.verify_calls == 2
    assert any(
        _packet(messages).get("open_completion_findings")
        for messages in hooks.messages[2:]
    )
    hooks_receipts = [r for r in result.receipts if r.kind == "thin_terminal_verifier_hook"]
    assert [r.payload["cycle"] for r in hooks_receipts] == [1, 2]
    assert any(r.kind == "thin_submitted" for r in result.receipts)


class _MissingEvidenceHooks:
    def __init__(self) -> None:
        self.solve_calls = 0
        self.verify_calls = 0
        self.messages = []

    def solve(self, messages, _compiled):
        self.solve_calls += 1
        self.messages.append(messages)
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="observe candidate before first finish",
                evidence_gap="need current state",
                actions=(
                    _action(1, "read_file", "filesystem", {"path": "app.py"}),
                ),
            )
        if self.solve_calls == 2:
            return SolverTurn(
                kind="finish_intent",
                summary="first finish",
                claim="candidate complete",
                evidence_refs=(_latest(messages, "read_file"),),
            )

        findings = _packet(messages).get("open_completion_findings") or []
        if self.solve_calls == 3:
            assert findings
            assert "missing-evidence" in str(findings[0]["finding_id"])
            assert findings[0]["source"] == "independent_review"
            # Deliberately try to resubmit without producing post-review
            # evidence. The existing finding/evidence gate must block this
            # before a second Verifier call.
            return SolverTurn(
                kind="finish_intent",
                summary="blind resubmit should be blocked",
                claim="candidate still complete",
                evidence_refs=(_latest(messages, "read_file"),),
            )
        if self.solve_calls == 4:
            assert findings
            return SolverTurn(
                kind="act",
                summary="gather fresh evidence requested by reviewer",
                evidence_gap="review needs current evidence",
                actions=(
                    _action(4, "read_file", "filesystem", {"path": "app.py"}),
                ),
            )
        return SolverTurn(
            kind="finish_intent",
            summary="finish after fresh evidence",
            claim="candidate complete with post-review evidence",
            evidence_refs=(_latest(messages, "read_file"),),
        )

    def verify(self, packet, _compiled, _ledger):
        self.verify_calls += 1
        if self.verify_calls == 1:
            return parse_model_verifier_result({
                "verdict": "uncertain_missing_evidence",
                "confidence": "medium",
                "summary": "fresh current-state evidence is still required",
                "missing_evidence_requests": [
                    "Read current candidate state after this review before submitting again."
                ],
            })
        return ModelVerifierResult(
            verdict="completed",
            confidence="high",
            summary="fresh post-review evidence is now present",
            completion_evidence=(),
        )


def test_uncertain_missing_evidence_reenters_for_evidence_without_becoming_repair(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ws-uncertain"
    root.mkdir(parents=True)
    (root / "app.py").write_text("x=1\n")
    env = build_envmap_from_task(
        str(tmp_path / "none-uncertain"),
        "Confirm app.py is current and finish.",
        workspace_root=str(root),
        projection_mode="factual_only",
    )
    hooks = _MissingEvidenceHooks()
    result = run_thin_loop(
        env,
        SubprocessExecutor(str(root)),
        hooks,
        config=ThinLoopConfig(
            max_steps=9,
            max_solver_turns=9,
            max_accepted_task_actions=4,
            runtime_identity={
                "task_id": "judge-evidence-reentry",
                "run_id": "judge-evidence-reentry-run",
                "primary_agent_id": "primary",
                "budgets": {
                    "max_kernel_steps": 9,
                    "max_solver_turns": 9,
                    "max_accepted_task_actions": 4,
                },
            },
            completion_record_mode="off",
            terminal_verifier_mode="terminal_verifier_v1",
        ),
    )

    assert result.status == "submitted"
    assert hooks.solve_calls == 5
    assert hooks.verify_calls == 2

    reentries = [
        row for row in result.receipts
        if row.kind == "thin_terminal_verifier_evidence_reentry"
    ]
    assert len(reentries) == 1
    assert reentries[0].payload["verdict"] == "uncertain_missing_evidence"
    assert reentries[0].payload["semantic_role"] == (
        "evidence_gathering_not_production_repair"
    )

    # The deliberately blind finish after review never reached Verifier.
    assert len([
        row for row in result.receipts
        if row.kind == "thin_terminal_verifier_hook"
    ]) == 2
    assert any(
        row.kind == "thin_submission_blocked"
        for row in result.receipts
    )
    assert any(row.kind == "thin_submitted" for row in result.receipts)

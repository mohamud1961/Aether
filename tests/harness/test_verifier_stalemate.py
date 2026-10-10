"""Bounded verifier-disagreement protocol.

Repeated Verifier disagreement is recorded diagnostically but never terminates
the task. The official task timeout remains the execution authority.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from aether.classifier import HarnessLimiterClassifier
from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.kernel_stalemate import check_verifier_stalemate
from aether.ledger import ExecutionLedger, Receipt
from aether.verifier import ModelVerifierResult
from aether.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    EnvMap,
    SolverTurn,
)


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Write /app/out.txt",
        workspace_root="/app",
        capabilities={
            "shell": CapabilityDescriptor("shell", "Run commands", tool_names=("run_command",)),
            "filesystem": CapabilityDescriptor("filesystem", "Files", tool_names=("read_file", "write_file")),
        },
    )


def _finding(fid: str) -> dict[str, Any]:
    return {
        "finding_id": fid,
        "summary": f"unresolved issue {fid}",
        "evidence": ["observed state contradicts the claim"],
        "repair_instruction": "fix the artifact",
        "applies_to": ["out.txt"],
        "priority": "blocking",
    }


class _StubbornHooks:
    """Solver alternates evidence-producing acts and submits; verifier keeps
    returning the configured finding sets."""

    def __init__(self, finding_sets: list[list[dict[str, Any]]]) -> None:
        self._finding_sets = list(finding_sets)
        self.verify_calls = 0
        self._turn = 0
        self._attempt = 0

    def solve(self, messages: list[dict[str, str]], compiled) -> SolverTurn:
        # Each verifier round has a fresh mutation and a separate observation.
        self._turn += 1
        phase = (self._turn - 1) % 3
        if phase == 0:
            self._attempt += 1
            return SolverTurn(kind="act", summary=f"rewrite attempt {self._attempt}", actions=(ActionRequest(
                action_id=f"write-{self._attempt}", kind="write_file", capability_id="filesystem",
                arguments={"path": "out.txt", "content": f"attempt {self._attempt}"},
                intent="address finding", expected_observation="file updated",
                if_fail_next="report blocker",
            ),), evidence_gap="The artifact must be changed before the next verification round")
        if phase == 1:
            return SolverTurn(kind="act", summary=f"observe attempt {self._attempt}", actions=(ActionRequest(
                action_id=f"read-{self._attempt}", kind="read_file", capability_id="filesystem",
                arguments={"path": "out.txt"},
                intent="observe current artifact evidence before resubmission",
                expected_observation=f"out.txt contains attempt {self._attempt}",
                if_fail_next="repair or report blocker",
            ),), evidence_gap="The latest mutation has not yet been observed")
        evidence_refs: tuple[str, ...] = ()
        for message in reversed(messages):
            content = str(message.get("content", ""))
            if not content.startswith("[context_packet]\n"):
                continue
            try:
                packet = json.loads(content.split("\n", 1)[1])
            except (ValueError, TypeError, json.JSONDecodeError):
                break
            latest = packet.get("latest_primary_result", {}) if isinstance(packet, dict) else {}
            rows = latest.get("outcome_receipts", ()) if isinstance(latest, dict) else ()
            refs = [
                str(row.get("evidence_ref", "")).strip()
                for row in rows
                if isinstance(row, dict) and str(row.get("evidence_ref", "")).strip()
            ]
            evidence_refs = tuple(refs)
            break
        return SolverTurn(
            kind="submit_outcome",
            summary="resubmitting after observed repair",
            claim="out.txt is complete",
            evidence_refs=evidence_refs,
        )

    def verify(self, packet, compiled, ledger):
        self.verify_calls += 1
        if self._finding_sets:
            findings = self._finding_sets.pop(0)
        else:
            findings = [_finding("f-stuck")]
        return json.dumps({
            "verdict": "needs_repair",
            "confidence": "high",
            "summary": "state still contradicts the requirement",
            "findings": findings,
        })


def test_identical_findings_across_rounds_record_diagnostic_without_terminating() -> None:
    hooks = _StubbornHooks([[_finding("f-stuck")]] * 10)
    result = AetherNextKernel(max_steps=20).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )

    assert result.status != "verifier_stalemate"
    assert hooks.verify_calls > AetherNextKernel.STALEMATE_ROUNDS
    stalemate = next(r for r in result.receipts if r.kind == "verifier_stalemate_observed")
    assert stalemate.success is True
    assert stalemate.payload["diagnostic_only"] is True
    assert stalemate.payload["task_termination_authority"] is False
    assert stalemate.payload["finding_ids"] == ["f-stuck"]
    assert stalemate.payload["rounds"] == AetherNextKernel.STALEMATE_ROUNDS
    assert stalemate.payload["final_verifier_verdict"]["verdict"] == "needs_repair"
    assert stalemate.payload["owner_attribution"]["classification"] == "solver_state"
    assert stalemate.payload["owner_attribution"]["correctness_adjudicated"] is False


def test_changing_findings_are_progress_not_stalemate() -> None:
    # Each round resolves the prior finding and raises a new one: disagreement
    # is moving, so the bounded protocol must not fire.
    sets = [
        [_finding("f-1")],
        [_finding("f-2")],
        [_finding("f-3")],
        [_finding("f-4")],
    ]
    hooks = _StubbornHooks(sets)
    result = AetherNextKernel(max_steps=8).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )
    assert result.status != "verifier_stalemate"


def _record_empty_verdict(ledger: ExecutionLedger, *, step: int, verdict_name: str) -> ModelVerifierResult:
    verdict = ModelVerifierResult(
        verdict=verdict_name,
        confidence="high",
        summary=f"{verdict_name} without actionable findings",
    )
    ledger.record(Receipt(
        receipt_id=f"step-{step}:model_verifier_result",
        step=step,
        kind="model_verifier_result",
        success=False,
        summary=f"model verifier verdict: {verdict_name}",
        payload=verdict.as_dict(),
    ))
    return verdict


def test_changing_empty_verdict_classes_do_not_false_stalemate() -> None:
    kernel = AetherNextKernel(max_steps=8)
    compiled = SimpleNamespace(env_digest="env")
    ledger = ExecutionLedger()
    history: list[frozenset[str]] = []
    verdicts = (
        "blocked_by_tooling",
        "uncertain_missing_evidence",
        "blocked_by_harness_config",
    )
    for step, name in enumerate(verdicts, start=1):
        verdict = _record_empty_verdict(ledger, step=step, verdict_name=name)
        terminal = check_verifier_stalemate(
            kernel, verdict, step, 0, compiled, ledger, history,
        )
        assert terminal is None


def test_same_empty_verdict_class_records_nonterminal_diagnostic() -> None:
    kernel = AetherNextKernel(max_steps=8)
    compiled = SimpleNamespace(env_digest="env")
    ledger = ExecutionLedger()
    history: list[frozenset[str]] = []
    terminal = None
    for step in range(1, kernel.STALEMATE_ROUNDS + 1):
        verdict = _record_empty_verdict(
            ledger, step=step, verdict_name="uncertain_missing_evidence",
        )
        terminal = check_verifier_stalemate(
            kernel, verdict, step, 0, compiled, ledger, history,
        )
    assert terminal is None
    observed = [r for r in ledger.all_receipts() if r.kind == "verifier_blocked_stalemate_observed"]
    assert len(observed) == 1
    assert observed[0].payload["diagnostic_only"] is True


def test_stalemate_diagnostic_does_not_create_terminal_verification_status() -> None:
    hooks = _StubbornHooks([[_finding("f-stuck")]] * 10)
    result = AetherNextKernel(max_steps=20).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )
    assert result.status not in {"verifier_stalemate", "verifier_blocked_stalemate"}
    assert any(r.kind == "verifier_stalemate_observed" for r in result.receipts)

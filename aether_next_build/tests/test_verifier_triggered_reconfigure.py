"""Verifier-triggered single-shot reconfiguration.

Only a verifier ``blocked_by_harness_config`` verdict may trigger a mid-run
reconfiguration; it re-invokes the real workbench architect with the verdict
as evidence, happens at most once per run, and is ALWAYS recorded as an
architect defect -- even when the task subsequently passes.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from aether_next.execution import MemoryExecutor
from aether_next.kernel import AetherNextKernel
from aether_next.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    EnvMap,
    SolverTurn,
)
from aether_next.workbench_config import parse_harness_config_ir


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Write /app/out.txt",
        workspace_root="/app",
        capabilities={
            "shell": CapabilityDescriptor("shell", "Run commands", tool_names=("run_command",)),
            "filesystem": CapabilityDescriptor("filesystem", "Files", tool_names=("read_file", "write_file")),
        },
    )


def _config_json(understanding: str) -> str:
    return json.dumps({
        "schema_version": "harness_config.v1",
        "task_understanding": understanding,
        "success_definition": "out.txt exists.",
        "solver_system_prompt": {
            "role": "Workbench file solver",
            "workflow": ["write output", "submit"],
            "self_verification": ["check output"],
            "memory_use": ["none"],
            "stop_conditions": ["submit after writing"],
        },
        "verifier_system_prompt": {
            "role": "State verifier",
            "success_criteria": ["out.txt exists"],
            "required_evidence": ["current file state"],
            "false_positive_traps": ["presence is not correctness"],
            "verdict_guidance": ["judge current state"],
            "feedback_guidance": ["be concrete"],
        },
        "evidence_requirements": ["current out.txt state"],
        "false_positive_risks": ["file present but wrong content"],
        "minimum_completion_evidence": ["out.txt current state"],
        "tool_policy": {"enabled_tools": ["read_file", "write_file", "run_command"]},
        "context_policy": {"mode": "retrieval_augmented"},
        "model_verifier_policy": {"enabled": True},
    })


class RecordingWorkbenchArchitect:
    def __init__(self) -> None:
        self.configure_calls: list[Mapping[str, Any]] = []

    def configure(self, request: Mapping[str, Any]):
        self.configure_calls.append(dict(request))
        tag = "reconfigured" if "reconfigure_context" in request else "initial"
        return parse_harness_config_ir(_config_json(f"{tag} config")), []


class BlockedThenCompletedHooks:
    """Solver writes then submits repeatedly; verifier: blocked -> completed."""

    def __init__(self, verdicts: list[dict[str, Any]]) -> None:
        self._verdicts = list(verdicts)
        self.verify_calls = 0
        self._acted = False

    def architect(self, request: Mapping[str, Any]):
        raise AssertionError("workbench mode must not call hooks.architect")

    def solve(self, messages: list[dict[str, str]], compiled) -> SolverTurn:
        if not self._acted:
            self._acted = True
            return SolverTurn(kind="act", summary="write out", actions=(ActionRequest(
                action_id="a-w", kind="write_file", capability_id="filesystem",
                arguments={"path": "out.txt", "content": "data"},
                intent="produce deliverable", expected_observation="file",
                if_fail_next="report blocker",
            ),))
        return SolverTurn(kind="submit_outcome", summary="submit")

    def verify(self, packet, compiled, ledger):
        self.verify_calls += 1
        if self._verdicts:
            return json.dumps(self._verdicts.pop(0))
        return json.dumps({
            "verdict": "completed", "confidence": "high",
            "summary": "state confirmed", "completion_evidence": ["out.txt state"],
        })


_BLOCKED = {
    "verdict": "blocked_by_harness_config",
    "confidence": "high",
    "summary": "solver lacks a required generic tool for this task",
    "findings": [{
        "finding_id": "cfg-1",
        "summary": "tool policy omits run_command needed to validate the artifact",
        "evidence": ["packet config_realization shows run_command missing"],
        "repair_instruction": "enable run_command",
        "applies_to": ["config"],
        "priority": "blocking",
    }],
}


def test_blocked_verdict_triggers_single_reconfigure_recorded_as_architect_defect() -> None:
    architect = RecordingWorkbenchArchitect()
    hooks = BlockedThenCompletedHooks([_BLOCKED])
    result = AetherNextKernel(max_steps=6, workbench_architect=architect).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )

    assert result.status == "completed"
    assert result.reconfigurations == 1
    assert result.architect_defect is True
    assert "verifier_triggered_reconfigure" in result.architect_defect_reasons

    # The workbench architect was re-invoked with the verdict as evidence.
    assert len(architect.configure_calls) == 2
    ctx = architect.configure_calls[1]["reconfigure_context"]
    assert ctx["reason"] == "verifier_blocked_by_harness_config"
    assert ctx["verifier_verdict"]["verdict"] == "blocked_by_harness_config"

    receipt = next(r for r in result.receipts if r.kind == "verifier_triggered_reconfigure")
    assert receipt.payload["architect_defect"] is True


def test_second_blocked_verdict_is_exhausted_not_a_second_reconfigure() -> None:
    architect = RecordingWorkbenchArchitect()
    hooks = BlockedThenCompletedHooks([_BLOCKED, dict(_BLOCKED)])
    result = AetherNextKernel(max_steps=8, workbench_architect=architect).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )

    assert result.reconfigurations == 1
    assert len(architect.configure_calls) == 2  # initial + one reconfigure only
    assert any(r.kind == "verifier_reconfigure_exhausted" for r in result.receipts)


def test_clean_run_has_no_architect_defect() -> None:
    architect = RecordingWorkbenchArchitect()
    hooks = BlockedThenCompletedHooks([])
    result = AetherNextKernel(max_steps=4, workbench_architect=architect).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )
    assert result.status == "completed"
    assert result.architect_defect is False
    assert result.architect_defect_reasons == ()

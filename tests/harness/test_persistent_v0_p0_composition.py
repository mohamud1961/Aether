"""Production-composition regressions for the PERSISTENT V0 P0 audit findings."""
from __future__ import annotations

import json
import os
import re
import tempfile

from aether.execution import CommandResult, MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.run_adapter import run_task
from aether.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    EnvMap,
    SolverTurn,
)
from aether.tracing import RunTrace


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Create out.txt containing hello.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files",
                tool_names=("read_file", "write_file"),
            ),
            "shell": CapabilityDescriptor(
                "shell", "local commands",
                tool_names=("run_command",),
            ),
        },
    )


def _action(
    kind: str,
    arguments: dict[str, object],
    *,
    action_id: str,
    capability_id: str,
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id=capability_id,
        arguments=arguments,
        intent="",
        expected_observation="",
        if_fail_next="",
    )


class _DirectHooks:
    def __init__(self, turns: list[SolverTurn]) -> None:
        self.turns = list(turns)

    def solve(self, messages, compiled):
        del messages, compiled
        return self.turns.pop(0)

    verify = None


def test_production_result_index_excludes_accounting_and_repeat_metadata() -> None:
    command = "printf hello"
    executor = MemoryExecutor(workspace_root="/app")
    executor.register_command(
        command,
        lambda _executor, cmd: CommandResult(cmd, 0, stdout="hello"),
    )
    hooks = _DirectHooks([
        SolverTurn(
            kind="act",
            summary="run one command",
            actions=(_action(
                "run_command", {"command": command},
                action_id="persistent-result", capability_id="shell",
            ),),
        ),
        SolverTurn(
            kind="act",
            summary="record next observation boundary",
            actions=(_action(
                "record_observation", {"observation": "second turn"},
                action_id="persistent-second", capability_id="kernel",
            ),),
        ),
    ])
    trace = RunTrace()

    AetherNextKernel(
        max_steps=2,
        persistent_primary=True,
    ).run(_env(), executor, hooks, trace=trace)

    context = trace.steps[1]["context_seen"]
    latest = context["latest_primary_result"]
    assert latest["outcome_receipts"]
    assert {row["evidence_type"] for row in latest["outcome_receipts"]} == {"run_command"}
    evidence_types = {row["evidence_type"] for row in context["evidence_index"]}
    assert "run_command" in evidence_types
    assert "runtime_accounting" not in evidence_types
    assert "persistent_repeat_observation" not in evidence_types
    assert "solver_progress_assessment" not in evidence_types


def test_nonexistent_capability_id_is_refused_before_dispatch() -> None:
    command = "printf should-not-run"
    executor = MemoryExecutor(workspace_root="/app")
    executor.register_command(
        command,
        lambda _executor, cmd: CommandResult(cmd, 0, stdout="executed"),
    )
    hooks = _DirectHooks([
        SolverTurn(
            kind="act",
            summary="attempt mismatched capability",
            actions=(_action(
                "run_command", {"command": command},
                action_id="persistent-fake-cap", capability_id="capability-that-does-not-exist",
            ),),
        ),
    ])

    result = AetherNextKernel(
        max_steps=1,
        persistent_primary=True,
    ).run(_env(), executor, hooks)

    assert executor.command_history == []
    refused = [
        receipt for receipt in result.receipts
        if receipt.failure_class == "capability_contract_mismatch"
    ]
    assert len(refused) == 1
    assert refused[0].kind == "action_validation"
    indexes = [
        receipt for receipt in result.receipts
        if receipt.kind == "primary_action_result_index"
    ]
    assert indexes[-1].payload["outcome_kinds"] == ["action_validation"]


class _ForbiddenArchitect:
    def __call__(self, messages, *, max_output_tokens=8000):
        del messages, max_output_tokens
        raise AssertionError("PERSISTENT V0 must not call the Architect")


class _PCRHappyPathSolver:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, *, max_output_tokens=8000):
        del max_output_tokens
        self.calls += 1
        if self.calls == 1:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "write_file",
                    "capability_id": "filesystem",
                    "arguments": {"path": "out.txt", "content": "hello"},
                },
            })
        if self.calls == 2:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "read_file",
                    "capability_id": "filesystem",
                    "arguments": {"path": "out.txt"},
                },
            })
        aliases: list[str] = []
        for message in messages:
            aliases.extend(re.findall(r"evidence:[0-9a-f]{16}", str(message.get("content", ""))))
        aliases = list(dict.fromkeys(aliases))
        assert aliases, "PERSISTENT context did not expose task evidence aliases"
        return json.dumps({
            "kind": "submit",
            "claim": "out.txt contains hello",
            "evidence_refs": aliases,
        })


class _PCRNeverSubmitSolver:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, *, max_output_tokens=8000):
        del messages, max_output_tokens
        self.calls += 1
        return json.dumps({
            "kind": "act",
            "action": {
                "kind": "record_observation",
                "capability_id": "kernel",
                "arguments": {"observation": f"still working turn {self.calls}"},
            },
        })


class _ForbiddenVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, *, max_output_tokens=12000):
        del messages, max_output_tokens
        self.calls += 1
        raise AssertionError("Verifier must not run before a PERSISTENT submission")


class _InspectingPCRVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, *, max_output_tokens=12000):
        del max_output_tokens
        self.calls += 1
        if len(messages) <= 2:
            return json.dumps({
                "kind": "inspect",
                "requests": [{
                    "request_id": "read-current-out",
                    "kind": "read_file",
                    "path": "out.txt",
                    "proof_ids": [],
                }],
            })
        inspection_ids: list[str] = []
        for message in reversed(messages):
            try:
                payload = json.loads(str(message.get("content", "")))
            except json.JSONDecodeError:
                continue
            rows = payload.get("verifier_inspection_results") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                continue
            inspection_ids = [
                str(row.get("inspection_id", ""))
                for row in rows
                if isinstance(row, dict) and row.get("inspection_id")
            ]
            if inspection_ids:
                break
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "independent read confirmed the exact PERSISTENT claim",
            "findings": [],
            "missing_evidence_requests": [],
            "completion_evidence": [{
                "requirement": "out.txt contains hello",
                "observed": "independent read_file returned hello",
                "inspection_refs": inspection_ids,
                "clause_ids": ["task:raw"],
                "proof_ids": [],
                "evidence_class": "exact_contract",
                "risk_refs": [],
                "requirement_status": "satisfied",
                "falsification_check": "different or missing bytes would refute the claim",
            }],
            "method_validity": None,
        })


def test_persistent_run_task_reaches_independent_verifier_and_completes() -> None:
    solver = _PCRHappyPathSolver()
    verifier = _InspectingPCRVerifier()
    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        with open(os.path.join(task_dir, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("PERSISTENT composition test")

        record = run_task(
            task_dir=task_dir,
            instruction_text="Create out.txt containing hello.",
            architect_model=_ForbiddenArchitect(),
            solver_model=solver,
            verifier_model=verifier,
            workspace_root=workspace,
            max_steps=6,
            architect_mode="persistent_v0",
            runtime_identity={
                "task_id": "persistent-p0-composition",
                "run_id": "persistent-p0-run",
                "primary_agent_id": "persistent-primary",
                "source_commit": "a" * 40,
                "runtime_manifest_sha256": "b" * 64,
            },
        )

    assert verifier.calls >= 2
    assert record["status"] == "completed", json.dumps(record["receipt_summary"], indent=2)
    errors = [
        row for row in record["receipt_summary"]
        if "architect-authored verifier prompt is required" in row["summary"]
    ]
    assert errors == []
    assert any(row["kind"] == "primary_submission_claim" for row in record["receipt_summary"])
    assert any(row["kind"] == "model_verifier_result" and row["success"] for row in record["receipt_summary"])


def test_persistent_run_task_max_steps_is_production_path_incomplete() -> None:
    solver = _PCRNeverSubmitSolver()
    verifier = _ForbiddenVerifier()
    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        with open(os.path.join(task_dir, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("PERSISTENT incomplete composition test")

        record = run_task(
            task_dir=task_dir,
            instruction_text="Create out.txt containing hello.",
            architect_model=_ForbiddenArchitect(),
            solver_model=solver,
            verifier_model=verifier,
            workspace_root=workspace,
            max_steps=2,
            architect_mode="persistent_v0",
            runtime_identity={
                "task_id": "persistent-p0-incomplete",
                "run_id": "persistent-p0-incomplete-run",
                "primary_agent_id": "persistent-primary",
                "source_commit": "a" * 40,
                "runtime_manifest_sha256": "b" * 64,
            },
        )

    assert record["architect_mode"] == "persistent_v0"
    assert record["status"] == "incomplete"
    assert record["step"] == 2
    assert solver.calls == 2
    assert verifier.calls == 0
    config_rows = [row for row in record["receipt_summary"] if row["kind"] == "config_realization"]
    assert config_rows
    assert all(row["success"] for row in config_rows)

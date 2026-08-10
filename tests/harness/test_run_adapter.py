"""End-to-end test for run_adapter with stub models against a real temp workspace."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from aether.run_adapter import (
    ensure_certified_architect_mode,
    run_task,
    workbench_architect_for,
)


class _StubArchitectModel:
    """Architect: selects shell + filesystem, disables checks and progress requirement."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return json.dumps({
            "architect_summary": "test architect: direct_build with shell+filesystem",
            "solver_identity_prompt": "You are a test solver.",
            "selected_capabilities": ["shell", "filesystem"],
            "workflow_policy": {"mode": "direct_build"},
            "process_policy": {"mode": "stateless_shell"},
            "completion_policy": {
                "require_authoritative_check": False,
                "allow_evidence_fallback": True,
                "require_all_obligations": False,
                "require_recent_progress": False,
                "require_clean_integrity": False,
            },
        })


class _StubArchitectV3Model:
    """Certified V3 Architect for the offline end-to-end adapter test."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 5000,
    ) -> str:
        return json.dumps({
            "schema_version": "aether_architect.v3",
            "outcomes": [{
                "outcome_id": "out-file",
                "description": "out.txt exists with content satisfying the request.",
                "parameters": [{
                    "parameter_id": "output_path",
                    "value": "out.txt",
                    "source_text": "out.txt",
                    "source_refs": ["user_task"],
                }],
                "source_refs": ["user_task"],
            }],
            "constraints": [],
            "proof_facets": [{
                "proof_id": "proof-out-file",
                "target_type": "outcome",
                "target_id": "out-file",
                "proof_kind": "exact_state",
                "acceptance_observation": "Current out.txt bytes contain content satisfying the request.",
                "falsification_observation": "out.txt is missing or its current content does not satisfy the request.",
            }],
            "solver_strategy": {
                "approach": [{
                    "strategy_id": "resolve-current-output-state",
                    "guidance": "Treat current file content as decisive and observe it before submitting completion.",
                    "uncertainty": "Whether current out.txt bytes satisfy the requested output rather than merely existing.",
                    "outcome_refs": ["out-file"],
                    "constraint_refs": [],
                    "proof_refs": ["proof-out-file"],
                }]
            },
        })


class _StubWorkbenchArchitectModel:
    """Workbench architect: configures filesystem-only tools."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return json.dumps({
            "schema_version": "harness_config.v1",
            "task_understanding": "Create out.txt.",
            "success_definition": "out.txt exists.",
            "solver_system_prompt": {
                "role": "Workbench run adapter solver",
                "workflow": ["write out.txt", "submit"],
                "self_verification": ["read or check visible output before submitting"],
                "memory_use": ["query_memory before repeating work"],
            },
            "verifier_system_prompt": {
                "role": "Read-only verifier for out.txt",
                "success_criteria": ["out.txt exists and satisfies the task request"],
                "required_evidence": ["current file state confirms completion"],
                "false_positive_traps": ["submitting before checking the file"],
                "verdict_guidance": ["completed requires current evidence"],
                "feedback_guidance": ["name the missing file or evidence"],
            },
            "evidence_requirements": ["out.txt exists in the current workspace"],
            "false_positive_risks": ["out.txt may exist with irrelevant content"],
            "minimum_completion_evidence": ["current out.txt file evidence"],
            "clause_coverage": [{
                "clause_id": "out-file",
                "solver_handling": "Create out.txt with content satisfying the task prompt.",
                "verifier_check": "Read the current out.txt and confirm it satisfies the task prompt.",
            }],
            "verifier_strategy": {
                "clause_checks": [{
                    "clause_id": "out-file",
                    "inspection_route": "read_file:out.txt",
                    "fallback_route": None,
                    "falsification_check": "A missing file or irrelevant content disproves completion.",
                    "required_evidence_class": "exact_contract",
                }],
                "false_positive_traps": ["file existence alone is not semantic proof"],
                "return_all_findings": True,
            },
            "tool_policy": {"enabled_tools": ["read_file", "write_file", "query_memory"]},
            "context_policy": {"mode": "retrieval_augmented"},
            "model_verifier_policy": {"enabled": True},
        })


class _StubSolverModel:
    """Scripted solver: write, inspect, then submit across real boundaries."""

    def __init__(self) -> None:
        self._call_count = 0

    def __call__(self, messages: list[dict[str, str]], *, max_output_tokens: int = 8000) -> str:
        self._call_count += 1
        if self._call_count == 1:
            return json.dumps({
                "kind": "act", "summary": "Write out.txt",
                "requested_check_ids": [], "claimed_artifacts": [],
                "evidence_gap": "The required output file does not exist yet.",
                "actions": [{
                    "action_id": "write-out", "kind": "write_file", "capability_id": "filesystem",
                    "arguments": {"path": "out.txt", "content": "hello from solver"},
                    "intent": "Create the required output file.",
                    "expected_observation": "out.txt is written.",
                    "if_fail_next": "Inspect the workspace path or report the write blocker.",
                }],
            })
        if self._call_count == 2:
            return json.dumps({
                "kind": "act", "summary": "Inspect out.txt",
                "requested_check_ids": [], "claimed_artifacts": ["out.txt"],
                "evidence_gap": "The exact written content has not been observed.",
                "actions": [{
                    "action_id": "read-out", "kind": "read_file", "capability_id": "filesystem",
                    "arguments": {"path": "out.txt"},
                    "intent": "Observe the current output before submission.",
                    "expected_observation": "out.txt contains hello from solver.",
                    "if_fail_next": "Rewrite the file or report the read blocker.",
                }],
            })
        return json.dumps({
            "kind": "submit_outcome", "summary": "out.txt written and observed",
            "requested_check_ids": [], "claimed_artifacts": ["out.txt"], "evidence_gap": "",
        })


class _WorkbenchSolverModel:
    """Scripted workbench solver: write, read, then submit."""

    def __init__(self) -> None:
        self._call_count = 0

    def __call__(self, messages: list[dict[str, str]], *, max_output_tokens: int = 8000) -> str:
        self._call_count += 1
        if self._call_count == 1:
            return json.dumps({
                "kind": "act", "summary": "Write out.txt",
                "requested_check_ids": [], "claimed_artifacts": [],
                "evidence_gap": "The required output file does not exist yet.",
                "actions": [{
                    "action_id": "write-out", "kind": "write_file", "capability_id": "filesystem",
                    "arguments": {"path": "out.txt", "content": "hello from workbench"},
                    "intent": "Create the required output file.",
                    "expected_observation": "out.txt is written.",
                    "if_fail_next": "Inspect the workspace or report the write blocker.",
                }],
            })
        if self._call_count == 2:
            return json.dumps({
                "kind": "act", "summary": "Inspect out.txt",
                "requested_check_ids": [], "claimed_artifacts": ["out.txt"],
                "evidence_gap": "The written file has not been observed yet.",
                "actions": [{
                    "action_id": "read-out", "kind": "read_file", "capability_id": "filesystem",
                    "arguments": {"path": "out.txt"},
                    "intent": "Read the current output before submitting.",
                    "expected_observation": "out.txt contains hello from workbench.",
                    "if_fail_next": "Rewrite out.txt or report the read blocker.",
                }],
            })
        return json.dumps({
            "kind": "submit_outcome", "summary": "out.txt written and observed",
            "requested_check_ids": [], "claimed_artifacts": ["out.txt"], "evidence_gap": "",
        })


class _StubVerifierModel:
    """Simulates a well-behaved verifier: it inspects the actual workspace at
    least once before returning completed, matching the runtime's requirement
    that a completed verdict be backed by real independent inspection rather
    than accepted straight from the packet's narrative. A fresh verifier
    invocation always starts with exactly [system, user] messages; anything
    longer means an inspection round already happened in this conversation --
    checking message count (not a persistent counter) correctly re-arms this
    per verifier call, since a single run can invoke the verifier several
    times across different steps."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        if len(messages) <= 2:
            return json.dumps({
                "kind": "inspect",
                "requests": [{
                    "request_id": "r1",
                    "kind": "read_file",
                    "path": "out.txt",
                    "proof_ids": ["proof-out-file"],
                }],
            })
        inspection_ids: list[str] = []
        for message in reversed(messages):
            try:
                payload = json.loads(message.get("content", ""))
            except (TypeError, json.JSONDecodeError):
                continue
            rows = payload.get("verifier_inspection_results") if isinstance(payload, dict) else None
            if isinstance(rows, list):
                inspection_ids = [
                    str(row.get("inspection_id", "")).strip()
                    for row in rows
                    if isinstance(row, dict) and str(row.get("inspection_id", "")).strip()
                ]
                if inspection_ids:
                    break
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "stub verifier saw enough evidence",
            "findings": [],
            "missing_evidence_requests": [],
            "completion_evidence": [{
                "requirement": "out.txt contains the requested result",
                "observed": "read_file inspection of out.txt showed the requested content",
                "inspection_refs": inspection_ids,
                "clause_ids": ["out-file"],
                "proof_ids": ["proof-out-file"],
                "evidence_class": "exact_contract",
                "risk_refs": [
                    "out.txt is missing or its current content does not satisfy the request."
                ],
                "falsification_check": "differing file content would have contradicted completion",
            }],
            "method_validity": None,
        })


class TestRunAdapter:
    def test_certified_runtime_modes_are_v3_and_persistent_v0(self) -> None:
        ensure_certified_architect_mode("architect_v3")
        ensure_certified_architect_mode("persistent_v0")
        for mode in ("workbench", "ir", "contract", "bogus"):
            with pytest.raises(ValueError, match="quarantined"):
                ensure_certified_architect_mode(mode)

    def test_workbench_architect_for_builds_workbench_architect(self) -> None:
        architect = workbench_architect_for(_StubWorkbenchArchitectModel())
        assert type(architect).__name__ == "WorkbenchArchitect"

    def test_end_to_end_stub(self) -> None:
        with tempfile.TemporaryDirectory() as task_dir, \
             tempfile.TemporaryDirectory() as workspace:
            # Create a minimal task file so envmap has something to scan.
            with open(os.path.join(task_dir, "README.md"), "w") as fh:
                fh.write("Test task")

            architect = _StubArchitectV3Model()
            solver = _WorkbenchSolverModel()

            record = run_task(
                task_dir=task_dir,
                instruction_text="Create out.txt containing any text.",
                architect_model=architect,
                solver_model=solver,
                verifier_model=_StubVerifierModel(),
                workspace_root=workspace,
                max_steps=6,
            )

            # Verify the run record shape.
            assert "status" in record
            assert "step" in record
            assert "classifier_label" in record
            assert "classifier_confidence" in record
            assert "classifier_evidence" in record
            assert "classifier_detail" in record
            assert "receipt_summary" in record
            assert isinstance(record["receipt_summary"], list)
            assert record["architect_mode"] == "architect_v3"
            assert record["model_interface_manifests"]
            assert record["model_interface_captures"]
            roles = [row["model_role"] for row in record["model_interface_manifests"]]
            assert "architect" in roles
            assert "solver" in roles
            assert "verifier" in roles
            for capture, manifest in zip(
                record["model_interface_captures"],
                record["model_interface_manifests"],
            ):
                assert capture["manifest"] == manifest
                assert capture["messages"]

            # The run should complete successfully.
            assert record["status"] == "completed", (
                f"Expected completed but got {record['status']}; "
                f"receipts: {json.dumps(record['receipt_summary'], indent=2)}"
            )
            assert record["classifier_label"] == "none"
            realization = [
                r for r in record["receipt_summary"]
                if r["kind"] == "config_realization"
            ]
            assert realization

            # The file should actually exist in the workspace.
            assert os.path.isfile(os.path.join(workspace, "out.txt"))

    def test_persistent_v0_bypasses_architect_model(self) -> None:
        class ForbiddenArchitect:
            def __call__(
                self,
                messages: list[dict[str, str]],
                *,
                max_output_tokens: int = 8000,
            ) -> str:
                raise AssertionError("PERSISTENT V0 must not invoke the Architect model")

        class PCRSolver:
            def __call__(
                self,
                messages: list[dict[str, str]],
                *,
                max_output_tokens: int = 8000,
            ) -> str:
                del messages, max_output_tokens
                return json.dumps({
                    "kind": "act",
                    "action": {
                        "kind": "write_file",
                        "capability_id": "filesystem",
                        "arguments": {
                            "path": "out.txt",
                            "content": "hello from persistent primary",
                        },
                    },
                })

        with tempfile.TemporaryDirectory() as task_dir, \
             tempfile.TemporaryDirectory() as workspace:
            with open(os.path.join(task_dir, "README.md"), "w") as fh:
                fh.write("Test task")

            record = run_task(
                task_dir=task_dir,
                instruction_text="Create out.txt containing any text.",
                architect_model=ForbiddenArchitect(),
                solver_model=PCRSolver(),
                verifier_model=_StubVerifierModel(),
                workspace_root=workspace,
                max_steps=1,
                architect_mode="persistent_v0",
            )

            assert record["architect_mode"] == "persistent_v0"
            assert record["status"] == "incomplete"
            roles = [row["model_role"] for row in record["model_interface_manifests"]]
            assert roles == ["solver"]
            assert os.path.isfile(os.path.join(workspace, "out.txt"))

    def test_workbench_mode_is_rejected_by_certified_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as task_dir, \
             tempfile.TemporaryDirectory() as workspace:
            with pytest.raises(ValueError, match="quarantined"):
                run_task(
                    task_dir=task_dir,
                    instruction_text="Create out.txt containing any text.",
                    architect_model=_StubWorkbenchArchitectModel(),
                    solver_model=_WorkbenchSolverModel(),
                    verifier_model=_StubVerifierModel(),
                    workspace_root=workspace,
                    max_steps=5,
                    architect_mode="workbench",
                )

    def test_receipt_summary_structure(self) -> None:
        with tempfile.TemporaryDirectory() as task_dir, \
             tempfile.TemporaryDirectory() as workspace:
            with open(os.path.join(task_dir, "prompt.txt"), "w") as fh:
                fh.write("Prompt text")

            architect = _StubArchitectV3Model()
            solver = _WorkbenchSolverModel()

            record = run_task(
                task_dir=task_dir,
                instruction_text="Create out.txt.",
                architect_model=architect,
                solver_model=solver,
                verifier_model=_StubVerifierModel(),
                workspace_root=workspace,
                max_steps=6,
            )

            for entry in record["receipt_summary"]:
                assert "receipt_id" in entry
                assert "kind" in entry
                assert "success" in entry
                assert "failure_class" in entry
                assert "summary" in entry



def test_workbench_architect_finalizer_has_separate_large_output_budget() -> None:
    from aether.run_adapter import workbench_architect_for

    def model(messages, *, max_output_tokens):
        return "{}"

    architect = workbench_architect_for(model, architect_reviewer_model=model)
    assert architect._max_output_tokens == 24000
    assert architect._review_max_output_tokens == 24000
    assert architect._finalizer_max_output_tokens == 64000

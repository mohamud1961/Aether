"""Small, falsifiable qualification checks for the post-V5 candidate.

These checks exercise the production contracts locally.  They deliberately
label what they prove: the provider-free Harbor records remain a scripted
runtime diagnostic, while the kernel-level checks cover mechanical custody,
context projection, deadline cleanup, and the finish protocol.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import time
from typing import Any

import pytest

from aether.execution import MemoryExecutor
from aether.harbor_executor import HarborEnvironmentExecutor
from aether.persistent_context_budget import finalize_persistent_context_budget
from aether.persistent_reanchor import continuity_fresh_delta_reanchor
from aether.run_adapter import run_task
from aether.run_deadline import (
    KernelRunTimeout,
    raise_if_run_deadline_exceeded,
    run_deadline,
)
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.verifier import parse_model_verifier_result
from aether.verify_completion_protocol import _verdict_admissibility_problem


REPO_ROOT = Path(__file__).resolve().parents[2]


def _completed_result(ref: str, *, evidence_class: str = "exact_contract") -> Any:
    return parse_model_verifier_result({
        "verdict": "completed",
        "confidence": "high",
        "summary": "current candidate was reviewed",
        "findings": [],
        "completion_evidence": [{
            "requirement": "the current candidate satisfies the task",
            "observed": "the registered current inspection was returned",
            "falsification_check": "a contradictory current observation must refuse completion",
            "inspection_refs": [ref],
            "clause_ids": ["task:raw"],
            "evidence_class": evidence_class,
            "risk_refs": [],
            "requirement_status": "satisfied",
        }],
    })


def test_completed_verdict_rejects_wrong_identity_and_weak_contradictory_evidence() -> None:
    """A completion claim cannot cite a missing or too-weak inspection.

    The second assertion is intentionally mechanical.  The runtime checks
    evidence identity and declared class; it does not pretend to judge the
    truth of the model's prose or content interpretation.
    """
    wrong_ref = _completed_result("inspection:wrong-generation")
    problem = _verdict_admissibility_problem(
        wrong_ref,
        direct_refs={"inspection:current"},
        derived_refs=set(),
    )
    assert problem == (
        "completed cites non-admissible evidence: inspection:wrong-generation"
    )

    weak_ref = _completed_result("inspection:metadata", evidence_class="behavioral")
    problem = _verdict_admissibility_problem(
        weak_ref,
        direct_refs={"inspection:metadata"},
        derived_refs=set(),
        actual_classes={"inspection:metadata": "metadata_proxy"},
    )
    assert "below required evidence class behavioral" in problem
    assert "inspection:metadata=metadata_proxy" in problem

    # A current exact-contract identity is mechanically admissible.  Whether
    # its bytes satisfy the raw task remains a semantic/model or independent
    # grader question, and is not silently promoted by this helper.
    assert _verdict_admissibility_problem(
        _completed_result("inspection:current"),
        direct_refs={"inspection:current"},
        derived_refs=set(),
        actual_classes={"inspection:current": "exact_contract"},
    ) == ""


def _transition_packet() -> dict[str, Any]:
    current = {
        "evidence_ref": "evidence:current",
        "receipt_id": "step-7:read-current",
        "evidence_type": "read_file",
        "originating_action_id": "action-7",
        "mechanical_description": "current candidate observation",
        "success": True,
        "state_change": False,
        "step": 7,
        "currentness": "current",
        "completion_evidence_eligible": True,
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": "receipt:step-7:read-current",
            "sha256": "a" * 64,
            "bytes": 6,
        },
        "bounded_view": {"stdout": "ready\n"},
    }
    historical = {
        "evidence_ref": "evidence:historical",
        "receipt_id": "step-2:read-old",
        "evidence_type": "read_file",
        "originating_action_id": "action-2",
        "mechanical_description": "older candidate observation",
        "success": True,
        "state_change": False,
        "step": 2,
        "currentness": "historical_task_evidence",
        "completion_evidence_eligible": True,
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": "receipt:step-2:read-old",
            "sha256": "b" * 64,
            "bytes": 5,
        },
    }
    return {
        "runtime_identity": {
            "task_id": "qualification-task",
            "run_id": "qualification-run",
            "primary_agent_id": "primary:qualification-run",
            "source_commit": "c" * 40,
        },
        "latest_primary_result": {
            "status": "succeeded",
            "decision": "candidate is ready after the current observation",
            "outcome_receipts": [deepcopy(current)],
        },
        "evidence_index": [deepcopy(historical), deepcopy(current)],
        "linked_history": {
            "command_results": [
                {"receipt_id": f"old-command-{i}", "stdout": "x" * 2_000}
                for i in range(16)
            ],
            "open_obligations": [{"obligation_id": "task:raw", "status": "open"}],
            "persistent_context_boundary": {"provider_native_continuity": True},
        },
        "open_completion_findings": [{
            "finding_id": "finding:current",
            "summary": "the current candidate still needs final semantic judgment",
        }],
        "submit_reentry_gate": {
            "active_finding_count": 1,
            "submit_reentry_gate": "awaiting_relevant_evidence",
        },
    }


def test_context_transition_preserves_task_decision_open_work_and_exact_handle() -> None:
    packet = _transition_packet()
    before = deepcopy(packet)

    transitioned = continuity_fresh_delta_reanchor(packet)
    assert packet == before
    assert transitioned["runtime_identity"]["task_id"] == "qualification-task"
    assert transitioned["runtime_identity"]["run_id"] == "qualification-run"
    assert transitioned["latest_primary_result"]["decision"].startswith("candidate is ready")
    assert transitioned["open_completion_findings"] == packet["open_completion_findings"]
    assert transitioned["submit_reentry_gate"] == packet["submit_reentry_gate"]
    assert [row["evidence_ref"] for row in transitioned["evidence_index"]] == [
        "evidence:current"
    ]
    assert transitioned["evidence_index"][0]["exact_access"]["handle"] == (
        "receipt:step-7:read-current"
    )

    # The context-budget transition operates on the canonical packet before
    # the narrower fresh-delta projection is handed to the provider.  Running
    # it on the canonical packet proves that duplicate history may be
    # externalized while the current decision remains inline.
    rendered = finalize_persistent_context_budget(
        packet,
        SimpleNamespace(
            context_policy=SimpleNamespace(
                model_context_window_tokens=10_000,
                compression_trigger_ratio=0.8,
            )
        ),
    )
    assert rendered["runtime_identity"]["task_id"] == "qualification-task"
    assert rendered["latest_primary_result"]["decision"].startswith("candidate is ready")
    assert rendered["open_completion_findings"] == packet["open_completion_findings"]
    assert rendered["submit_reentry_gate"] == packet["submit_reentry_gate"]
    assert rendered["latest_primary_result"]["outcome_receipts"][0]["exact_access"]["handle"] == (
        "receipt:step-7:read-current"
    )
    assert rendered["context_budget"]["provider_context_authority"] is True
    assert rendered["context_budget"]["preferred_hot_context"]["semantic_summarization_used"] is False


def test_shared_deadline_terminates_downloads_and_cleans_owned_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The task deadline owns termination, output retrieval, and cleanup order."""
    class DummyEnvironment:
        pass

    loop = asyncio.new_event_loop()
    executor = HarborEnvironmentExecutor(
        DummyEnvironment(),
        event_loop=loop,
        workspace_root=str(tmp_path / "workspace"),
        local_state_dir=tmp_path / "state",
    )
    record = SimpleNamespace(container_id="", remote_dir="/tmp/qualification")
    events: list[str] = []

    monkeypatch.setattr(executor, "_launch_supervised_foreground_command", lambda _command, cwd=None: record)

    def status(_record: Any) -> tuple[bool, int | None, str]:
        time.sleep(0.02)
        raise_if_run_deadline_exceeded()
        return True, None, "still running"

    monkeypatch.setattr(executor, "_remote_status", status)
    monkeypatch.setattr(
        executor,
        "_terminate_supervised_foreground",
        lambda _record: (events.append("terminate") or (True, "terminated")),
    )
    monkeypatch.setattr(
        executor,
        "_download_remote_process_streams",
        lambda _record: (events.append("download") or ("partial-out", "partial-err")),
    )
    monkeypatch.setattr(
        executor,
        "_cleanup_supervised_foreground",
        lambda _record: events.append("cleanup"),
    )
    try:
        with run_deadline(time.monotonic() + 0.005):
            with pytest.raises(KernelRunTimeout, match="task run deadline exceeded"):
                executor.run_command("ignored", timeout_s=30)
    finally:
        loop.close()

    assert events == ["terminate", "download", "cleanup"]


class _FinishSolver:
    def __init__(self) -> None:
        self.calls = 0

    @staticmethod
    def _latest_ref(messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            content = str(message.get("content", ""))
            if not content.startswith("[context_packet]\n"):
                continue
            packet = json.loads(content.split("\n", 1)[1])
            rows = packet.get("latest_primary_result", {}).get("outcome_receipts", ())
            if rows:
                return str(rows[0]["evidence_ref"])
        raise AssertionError("production context did not expose a current evidence alias")

    def __call__(self, messages: list[dict[str, str]], *, max_output_tokens: int | None = None) -> str:
        del max_output_tokens
        self.calls += 1
        if self.calls == 1:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "write_file",
                    "arguments": {"path": "out.txt", "content": "good\n"},
                },
            })
        ref = self._latest_ref(messages)
        if self.calls == 2:
            return json.dumps({
                "kind": "finish_intent",
                "claim": "out.txt contains good",
                "evidence_refs": [ref],
            })
        return json.dumps({
            "kind": "finish",
            "claim": "out.txt contains good",
            "evidence_refs": [ref],
        })


class _FinishVerifier:
    def __init__(self) -> None:
        self.calls = 0

    @staticmethod
    def _inspection_ref(messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            try:
                value = json.loads(str(message.get("content", "")))
            except json.JSONDecodeError:
                continue
            rows = value.get("verifier_inspection_results") if isinstance(value, dict) else None
            if isinstance(rows, list) and rows:
                ref = str(rows[0].get("inspection_id", ""))
                if ref:
                    return ref
        raise AssertionError("verifier did not receive a registered inspection result")

    def __call__(self, messages: list[dict[str, str]], *, max_output_tokens: int | None = None) -> str:
        del max_output_tokens
        self.calls += 1
        if self.calls == 1:
            return json.dumps({
                "kind": "inspect",
                "requests": [{
                    "request_id": "current-output",
                    "kind": "read_file",
                    "path": "out.txt",
                    "limit": 16,
                }],
            })
        ref = self._inspection_ref(messages)
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "the current output was independently observed",
            "findings": [],
            "completion_evidence": [{
                "requirement": "out.txt contains good",
                "observed": "the registered read returned the current output",
                "falsification_check": "a contradictory output must refuse completion",
                "inspection_refs": [ref],
                "clause_ids": ["task:raw"],
                "evidence_class": "exact_contract",
                "risk_refs": [],
                "requirement_status": "satisfied",
            }],
        })


def test_run_adapter_executes_finish_intent_verifier_and_finish_path() -> None:
    envmap = EnvMap(
        task_prompt="Create /app/out.txt containing good.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "workspace files", tool_names=("read_file", "write_file"),
            ),
            "shell": CapabilityDescriptor(
                "shell", "local commands", tool_names=("run_command",),
            ),
        },
    )
    solver = _FinishSolver()
    verifier = _FinishVerifier()
    record = run_task(
        task_dir=str(REPO_ROOT / "evals" / "provider_free_integration_v1" / "ordinary_clean_finish"),
        instruction_text=envmap.task_prompt,
        solver_model=solver,
        verifier_model=verifier,
        workspace_root="/app",
        max_steps=6,
        envmap_override=envmap,
        executor=MemoryExecutor(workspace_root="/app", files={}),
        close_executor=False,
    )

    assert record["status"] == "completed"
    assert solver.calls == 2
    assert verifier.calls == 2
    claims = [
        row["payload"]
        for row in record["receipt_records"]
        if row["kind"] == "primary_submission_claim"
    ]
    assert [row["submission_mode"] for row in claims] == ["finish_intent"]
    assert any(row["kind"] == "model_verifier_inspection" for row in record["receipt_records"])
    assert any(row["kind"] == "frontier_finish" for row in record["receipt_records"])

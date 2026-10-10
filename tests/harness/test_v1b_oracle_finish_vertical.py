from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aether.envmap_builder import build_envmap_from_task
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import ActionRequest, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop

VERIFY_FAIL = "import sys\nprint('[FAIL] case')\nsys.exit(1)\n"
VERIFY_PASS = "print('ALL PASS')\n"
RUN_VERIFY = "python3 verify.py"


def _packet(messages: list[dict[str, Any]]) -> dict[str, Any]:
    for message in messages:
        content = str(message.get("content", ""))
        if content.startswith("[context_packet]\n"):
            return json.loads(content[len("[context_packet]\n"):])
    raise AssertionError("context packet missing")


def _action(index: int, kind: str, arguments: dict[str, Any]) -> ActionRequest:
    return ActionRequest(
        action_id=f"a-{index}",
        kind=kind,
        capability_id="shell" if kind == "run_command" else "filesystem",
        arguments=arguments,
        intent="advance current task",
        expected_observation="current result",
        if_fail_next="inspect failure",
    )


def _latest_ref(packet: dict[str, Any], evidence_type: str) -> str:
    rows = [
        row for row in packet.get("evidence_index", [])
        if isinstance(row, dict)
        and row.get("evidence_type") == evidence_type
        and row.get("evidence_ref")
        and row.get("completion_evidence_eligible", True)
    ]
    assert rows, f"no {evidence_type} evidence in current packet"
    return str(rows[0]["evidence_ref"])


def _run(tmp_path: Path, hooks: Any):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "verify.py").write_text(VERIFY_FAIL)
    (root / "app.py").write_text("VALUE = 1\n")
    envmap = build_envmap_from_task(
        str(tmp_path / "missing-task"),
        "Repair the production program and finish only from current evidence.",
        workspace_root=str(root),
        projection_mode="factual_only",
    )
    result = run_thin_loop(
        envmap,
        SubprocessExecutor(str(root)),
        hooks,
        config=ThinLoopConfig(
            max_steps=9,
            max_solver_turns=9,
            max_accepted_task_actions=6,
            runtime_identity={
                "task_id": "v1b-vertical",
                "run_id": "v1b-vertical-run",
                "primary_agent_id": "primary",
                "budgets": {
                    "max_kernel_steps": 9,
                    "max_solver_turns": 9,
                    "max_accepted_task_actions": 6,
                },
            },
            solver_completion_signal_mode="verification_oracle_guard_v1",
            oracle_finish_response_mode="oracle_hold_once_v1",
            completion_record_mode="off",
        ),
    )
    return root, result


class _RepairPathHooks:
    def __init__(self) -> None:
        self.calls = 0

    def solve(self, messages, _compiled):
        self.calls += 1
        packet = _packet(messages)
        if self.calls == 1:
            return SolverTurn(
                kind="act", summary="run current check", evidence_gap="status unknown",
                actions=(_action(1, "run_command", {"command": RUN_VERIFY}),),
            )
        if self.calls == 2:
            return SolverTurn(
                kind="act", summary="edit check only", evidence_gap="check failed",
                actions=(_action(2, "write_file", {"path": "verify.py", "content": VERIFY_PASS}),),
            )
        if self.calls == 3:
            return SolverTurn(
                kind="act", summary="rerun edited check", evidence_gap="need result",
                actions=(_action(3, "run_command", {"command": RUN_VERIFY}),),
            )
        if self.calls == 4:
            return SolverTurn(
                kind="finish_intent",
                summary="finish after edited check",
                claim="the edited check passes",
                evidence_refs=(_latest_ref(packet, "run_command"),),
            )
        if self.calls == 5:
            assert packet["oracle_finish_hold"]["required_finding_ids"]
            return SolverTurn(
                kind="act", summary="repair production code",
                evidence_gap="oracle-edit obligation requires repair or explanation",
                actions=(_action(5, "write_file", {"path": "app.py", "content": "VALUE = 2\n"}),),
            )
        if self.calls == 6:
            return SolverTurn(
                kind="act", summary="observe repaired production code",
                evidence_gap="need current production evidence",
                actions=(_action(6, "read_file", {"path": "app.py"}),),
            )
        if self.calls == 7:
            finding_id = str(packet["oracle_finish_hold"]["required_finding_ids"][0])
            evidence_ref = _latest_ref(packet, "read_file")
            return SolverTurn(
                kind="finish_outcome",
                summary="finish after production repair",
                claim="production code was repaired after the oracle-edit observation",
                evidence_refs=(evidence_ref,),
                finding_dispositions=({
                    "finding_id": finding_id,
                    "disposition": "resolved",
                    "explanation": "production code changed after the held oracle-edit incident",
                    "evidence_refs": [evidence_ref],
                    "residual_uncertainty": "",
                },),
            )
        raise AssertionError(f"unexpected solver call {self.calls}")


class _CheckDefectHooks:
    def __init__(self) -> None:
        self.calls = 0

    def solve(self, messages, _compiled):
        self.calls += 1
        packet = _packet(messages)
        if self.calls == 1:
            return SolverTurn(
                kind="act", summary="run current check", evidence_gap="status unknown",
                actions=(_action(1, "run_command", {"command": RUN_VERIFY}),),
            )
        if self.calls == 2:
            return SolverTurn(
                kind="act", summary="repair defective check", evidence_gap="check itself is wrong",
                actions=(_action(2, "write_file", {"path": "verify.py", "content": VERIFY_PASS}),),
            )
        if self.calls == 3:
            return SolverTurn(
                kind="act", summary="rerun corrected check", evidence_gap="need result",
                actions=(_action(3, "run_command", {"command": RUN_VERIFY}),),
            )
        if self.calls == 4:
            return SolverTurn(
                kind="finish_intent",
                summary="first finish",
                claim="the corrected local check passes",
                evidence_refs=(_latest_ref(packet, "run_command"),),
            )
        if self.calls == 5:
            finding_id = str(packet["oracle_finish_hold"]["required_finding_ids"][0])
            evidence_ref = _latest_ref(packet, "run_command")
            return SolverTurn(
                kind="finish_outcome",
                summary="explain check defect",
                claim="the earlier failure came from a defective local check",
                evidence_refs=(evidence_ref,),
                finding_dispositions=({
                    "finding_id": finding_id,
                    "disposition": "not_applicable",
                    "explanation": (
                        "the earlier local check encoded a synthetic expectation not present "
                        "in the raw task; the corrected check exercises only the task-stated condition"
                    ),
                    "evidence_refs": [],
                    "residual_uncertainty": "",
                },),
            )
        raise AssertionError(f"unexpected solver call {self.calls}")


def test_v1b_hold_once_then_production_repair_resolves(tmp_path: Path) -> None:
    hooks = _RepairPathHooks()
    root, result = _run(tmp_path, hooks)
    kinds = [receipt.kind for receipt in result.receipts]

    assert result.status == "submitted"
    assert hooks.calls == 7
    assert kinds.count("v1b_oracle_finish_hold") == 1
    assert kinds.count("v1b_oracle_finish_reentry") == 1
    assert kinds.count("v1b_oracle_disposition") == 1
    disposition = next(r for r in result.receipts if r.kind == "v1b_oracle_disposition")
    assert disposition.payload["routes"][0]["route"] == "production_repair"
    assert (root / "app.py").read_text() == "VALUE = 2\n"


def test_v1b_hold_once_allows_specific_check_defect_disposition(tmp_path: Path) -> None:
    hooks = _CheckDefectHooks()
    root, result = _run(tmp_path, hooks)
    kinds = [receipt.kind for receipt in result.receipts]

    assert result.status == "submitted"
    assert hooks.calls == 5
    assert kinds.count("v1b_oracle_finish_hold") == 1
    disposition = next(r for r in result.receipts if r.kind == "v1b_oracle_disposition")
    assert disposition.payload["routes"][0]["route"] == "check_defect_explanation"
    assert disposition.payload["routes"][0]["explanation"]
    assert (root / "app.py").read_text() == "VALUE = 1\n"


class _RetentionHooks:
    def __init__(self) -> None:
        self.calls = 0
        self.saw_retained_obligation = False

    def solve(self, messages, _compiled):
        self.calls += 1
        packet = _packet(messages)
        if self.calls == 1:
            return SolverTurn(
                kind="act", summary="run current check", evidence_gap="status unknown",
                actions=(_action(1, "run_command", {"command": RUN_VERIFY}),),
            )
        if self.calls == 2:
            return SolverTurn(
                kind="act", summary="edit check only", evidence_gap="check failed",
                actions=(_action(2, "write_file", {"path": "verify.py", "content": VERIFY_PASS}),),
            )
        if self.calls == 3:
            return SolverTurn(
                kind="act", summary="rerun edited check", evidence_gap="need result",
                actions=(_action(3, "run_command", {"command": RUN_VERIFY}),),
            )
        if self.calls == 4:
            return SolverTurn(
                kind="finish_intent", summary="first finish",
                claim="the edited local check passes",
                evidence_refs=(_latest_ref(packet, "run_command"),),
            )
        if self.calls in {5, 6}:
            hold = packet.get("oracle_finish_hold")
            assert hold and hold["required_finding_ids"]
            if self.calls == 6:
                self.saw_retained_obligation = True
            finding_id = str(hold["required_finding_ids"][0])
            good_ref = _latest_ref(packet, "run_command")
            finish_ref = "evidence:deadbeefdeadbeef" if self.calls == 5 else good_ref
            return SolverTurn(
                kind="finish_outcome", summary="explain check defect",
                claim="the earlier local check was defective",
                evidence_refs=(finish_ref,),
                finding_dispositions=({
                    "finding_id": finding_id,
                    "disposition": "not_applicable",
                    "explanation": (
                        "the earlier local check asserted a condition not present "
                        "in the raw task"
                    ),
                    "evidence_refs": [],
                    "residual_uncertainty": "",
                },),
            )
        raise AssertionError(f"unexpected solver call {self.calls}")


def test_v1b_disposition_is_not_consumed_before_submission_admission(tmp_path: Path) -> None:
    hooks = _RetentionHooks()
    _root, result = _run(tmp_path, hooks)

    assert result.status == "submitted"
    assert hooks.saw_retained_obligation is True
    blocks = [r for r in result.receipts if r.kind == "thin_submission_blocked"]
    assert blocks
    dispositions = [r for r in result.receipts if r.kind == "v1b_oracle_disposition"]
    assert len(dispositions) == 1
    assert dispositions[0].step > blocks[0].step
    assert dispositions[0].payload["consumed_only_after_completion_gate_ready"] is True

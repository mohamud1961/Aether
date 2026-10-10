from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from aether.envmap_builder import build_envmap_from_task
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import ActionRequest, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop

VERIFY_FAIL = "import sys\nprint('[FAIL] case')\nsys.exit(1)\n"
VERIFY_PASS = "print('ALL PASS')\n"


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
        intent="resolve current evidence gap",
        expected_observation="one exact result",
        if_fail_next="inspect the contradiction",
    )


def _env(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir(parents=True)
    (root / "verify.py").write_text(VERIFY_FAIL)
    (root / "app.py").write_text("x=1\n")
    return root, build_envmap_from_task(
        str(tmp_path / "none"),
        "Repair the task and finish only when current evidence supports completion.",
        workspace_root=str(root),
        projection_mode="factual_only",
    )


def _config(*, treatment: bool) -> ThinLoopConfig:
    return ThinLoopConfig(
        max_steps=10,
        max_solver_turns=10,
        max_accepted_task_actions=6,
        runtime_identity={
            "task_id": "v1b-vertical",
            "run_id": "v1b-vertical-run",
            "primary_agent_id": "primary",
            "budgets": {
                "max_kernel_steps": 10,
                "max_solver_turns": 10,
                "max_accepted_task_actions": 6,
            },
        },
        completion_record_mode="off",
        solver_completion_signal_mode="verification_oracle_guard_v1",
        oracle_finish_response_mode="oracle_hold_once_v1" if treatment else "control",
    )


class _CheckDefectHooks:
    def __init__(self, *, treatment: bool) -> None:
        self.treatment = treatment
        self.calls = 0
        self.messages = []

    def solve(self, messages, _compiled):
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return SolverTurn(
                kind="act", summary="run current check", evidence_gap="behavior unknown",
                actions=(_action(1, "run_command", "shell", {"command": "python3 verify.py"}),),
            )
        if self.calls == 2:
            return SolverTurn(
                kind="act", summary="edit only check", evidence_gap="check failed",
                actions=(_action(2, "write_file", "filesystem", {"path": "verify.py", "content": VERIFY_PASS}),),
            )
        if self.calls == 3:
            return SolverTurn(
                kind="act", summary="rerun edited check", evidence_gap="edited check not rerun",
                actions=(_action(3, "run_command", "shell", {"command": "python3 verify.py"}),),
            )
        ref = _latest(messages, "run_command")
        if not self.treatment:
            return SolverTurn(
                kind="finish_intent", summary="finish", claim="candidate complete",
                evidence_refs=(ref,),
            )
        hold = _packet(messages).get("oracle_finish_hold") or {}
        finding_ids = tuple(str(x) for x in hold.get("required_finding_ids", ()) if str(x))
        if not finding_ids:
            return SolverTurn(
                kind="finish_intent", summary="first finish", claim="candidate complete",
                evidence_refs=(ref,),
            )
        return SolverTurn(
            kind="finish_outcome",
            summary="finish with check-defect explanation",
            claim="candidate complete; earlier check failure was a defect in that self-authored check",
            evidence_refs=(ref,),
            finding_dispositions=({
                "finding_id": finding_ids[0],
                "disposition": "not_applicable",
                "explanation": (
                    "The earlier failure came from the self-authored verification file "
                    "itself, not from a task requirement or production behavior."
                ),
                "evidence_refs": [],
                "residual_uncertainty": "",
            },),
        )


def test_v1b_holds_exactly_once_and_allows_specific_check_defect_explanation(tmp_path: Path) -> None:
    root, env = _env(tmp_path / "control")
    control_hooks = _CheckDefectHooks(treatment=False)
    control = run_thin_loop(
        env, SubprocessExecutor(str(root)), control_hooks, config=_config(treatment=False)
    )
    assert control.status == "submitted"
    assert control_hooks.calls == 4
    assert not any(r.kind == "v1b_oracle_finish_hold" for r in control.receipts)

    root, env = _env(tmp_path / "treatment")
    hooks = _CheckDefectHooks(treatment=True)
    treated = run_thin_loop(
        env, SubprocessExecutor(str(root)), hooks, config=_config(treatment=True)
    )
    assert treated.status == "submitted"
    assert hooks.calls == 5
    holds = [r for r in treated.receipts if r.kind == "v1b_oracle_finish_hold"]
    assert len(holds) == 1
    dispositions = [r for r in treated.receipts if r.kind == "v1b_oracle_disposition"]
    assert len(dispositions) == 1
    assert dispositions[0].payload["routes"][0]["route"] == "check_defect_explanation"
    visible = [_packet(messages) for messages in hooks.messages]
    assert any((p.get("oracle_finish_hold") or {}).get("required_finding_ids") for p in visible)
    factual = [
        finding
        for p in visible
        for finding in (p.get("open_completion_findings") or [])
    ]
    assert factual and all(item.get("source") == "mechanical_observation" for item in factual)


class _ProductionRepairHooks(_CheckDefectHooks):
    def solve(self, messages, _compiled):
        if self.calls < 4:
            return super().solve(messages, _compiled)
        self.calls += 1
        self.messages.append(messages)
        hold = _packet(messages).get("oracle_finish_hold") or {}
        finding_ids = tuple(str(x) for x in hold.get("required_finding_ids", ()) if str(x))
        if self.calls == 5:
            assert len(finding_ids) == 1
            return SolverTurn(
                kind="act", summary="repair production", evidence_gap="held oracle observation",
                actions=(_action(5, "write_file", "filesystem", {"path": "app.py", "content": "x=2\n"}),),
            )
        if self.calls == 6:
            return SolverTurn(
                kind="act", summary="observe production repair", evidence_gap="need current evidence",
                actions=(_action(6, "read_file", "filesystem", {"path": "app.py"}),),
            )
        ref = _latest(messages, "read_file")
        return SolverTurn(
            kind="finish_outcome",
            summary="finish repaired production",
            claim="production code repaired and observed current",
            evidence_refs=(ref,),
            finding_dispositions=({
                "finding_id": finding_ids[0],
                "disposition": "resolved",
                "explanation": "Production code changed after the held observation and is current.",
                "evidence_refs": [ref],
                "residual_uncertainty": "",
            },),
        )


def test_v1b_resolved_route_requires_real_nonverification_change(tmp_path: Path) -> None:
    root, env = _env(tmp_path)
    hooks = _ProductionRepairHooks(treatment=True)
    result = run_thin_loop(
        env, SubprocessExecutor(str(root)), hooks, config=_config(treatment=True)
    )
    assert result.status == "submitted"
    dispositions = [r for r in result.receipts if r.kind == "v1b_oracle_disposition"]
    assert len(dispositions) == 1
    assert dispositions[0].payload["routes"][0]["route"] == "production_repair"
    hold_step = next(r.step for r in result.receipts if r.kind == "v1b_oracle_finish_hold")
    assert any(
        r.kind == "write_file"
        and r.step > hold_step
        and (r.payload or {}).get("path") == "app.py"
        for r in result.receipts
    )


class _RejectedDispositionHooks(_CheckDefectHooks):
    """A valid disposition rides on a finish made stale by a later production write."""

    def solve(self, messages, _compiled):
        if self.calls < 4:
            return super().solve(messages, _compiled)
        self.calls += 1
        self.messages.append(messages)
        hold = _packet(messages).get("oracle_finish_hold") or {}
        finding_ids = tuple(
            str(x) for x in hold.get("required_finding_ids", ()) if str(x)
        )
        if self.calls == 5:
            assert len(finding_ids) == 1
            return SolverTurn(
                kind="act",
                summary="mutate production without observing it",
                evidence_gap="held oracle observation",
                actions=(_action(
                    5,
                    "write_file",
                    "filesystem",
                    {"path": "app.py", "content": "x=3\n"},
                ),),
            )
        if self.calls == 6:
            assert len(finding_ids) == 1
            # The disposition itself is valid, but this cited verification is
            # older than the production mutation at call 5. PERSISTENT binding/currentness
            # must reject the finish. That rejection must not consume V1b.
            ref = _latest(messages, "run_command")
            return SolverTurn(
                kind="finish_outcome",
                summary="premature disposition",
                claim="candidate complete",
                evidence_refs=(ref,),
                finding_dispositions=({
                    "finding_id": finding_ids[0],
                    "disposition": "not_applicable",
                    "explanation": "The earlier self-authored check was defective.",
                    "evidence_refs": [],
                    "residual_uncertainty": "",
                },),
            )
        assert len(finding_ids) == 1, "V1b obligation disappeared after rejected finish"
        return SolverTurn(
            kind="act",
            summary="observe current production after rejected finish",
            evidence_gap="submission was stale",
            actions=(_action(7, "read_file", "filesystem", {"path": "app.py"}),),
        )


def test_v1b_rejected_finish_does_not_consume_obligation(tmp_path: Path) -> None:
    root, env = _env(tmp_path)
    hooks = _RejectedDispositionHooks(treatment=True)
    config = replace(
        _config(treatment=True),
        max_steps=7,
        max_solver_turns=7,
        max_accepted_task_actions=7,
    )
    result = run_thin_loop(
        env, SubprocessExecutor(str(root)), hooks, config=config,
    )
    assert hooks.calls == 7
    assert not any(r.kind == "v1b_oracle_disposition" for r in result.receipts)
    assert any(r.kind == "thin_submission_blocked" for r in result.receipts)
    final_packet = _packet(hooks.messages[-1])
    required = (
        (final_packet.get("oracle_finish_hold") or {}).get("required_finding_ids")
        or []
    )
    assert len(required) == 1

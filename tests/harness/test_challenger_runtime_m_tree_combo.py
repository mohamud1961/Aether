"""CHALLENGER + M-TREE: feedback and card turns enter the tree as ordinary events and stay within its limits."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from aether.challenger_runtime.controller import ChallengerController
from aether.challenger_runtime.judge_client import JudgeClient
from aether.context_tree.adapter import ContextTreeAdapter, _tree_request_estimate
from aether.envmap_builder import build_envmap_from_task
from aether.execution import CommandResult, MemoryExecutor
from aether.thin_loop import ThinLoopConfig, run_thin_loop
from tests.harness.test_challenger_runtime_loop import (
    CHECK_CMD, STATE_DELTA, TASK, VERIFY_CMD, FakeJudge, ScriptedGLM, hold_none, all_direct, make_card_model,
)

REQUEST_LIMIT = 100_000
VIEW_BYTES = 20_000


class TreeGLM(ScriptedGLM):
    def reset_solver_continuity_for_recovery(self) -> bool:
        return True


def _compactor(_request: dict[str, Any], *, route: str, limiter: Any, deadline_monotonic: float) -> str:
    assert deadline_monotonic > time.monotonic()
    return "synthetic summary"


_compactor.supports_finite_deadline = True


def test_challenger_with_m_tree_carries_feedback_in_the_view_within_limits(tmp_path: Path) -> None:
    tree = ContextTreeAdapter(
        raw_task=TASK, evidence_root=tmp_path / "tree", run_id="combo", compactor_provider=_compactor,
        compactor_route="fake-route", compactor_limiter_path=tmp_path / "limiter.json",
        epoch_steps=3, request_limit=REQUEST_LIMIT, view_bytes=VIEW_BYTES, jobs=2, retry_s=0.01)
    card_requests: list[list[dict[str, str]]] = []
    inner = make_card_model([])

    def card_model(messages: list[dict[str, str]]) -> str:
        card_requests.append(json.loads(json.dumps(messages)))
        return inner(messages)

    judge = FakeJudge(lambda n, cid: hold_none(n, cid) if n <= 2 else all_direct(n, cid))
    controller = ChallengerController(
        card_model=card_model, evaluator=JudgeClient(judge, model="judge-1.13.0", raw_task=TASK),
        evidence_dir=tmp_path / "challenger", run_id="combo", task_text=TASK)
    executor = MemoryExecutor(workspace_root="/app", files={"src/parser.py": "x.split(',')"})
    for cmd, out in ((CHECK_CMD, "12: x.split(',')"), (VERIFY_CMD, "verified"), ("grep -n strip src/parser.py", "")):
        executor.register_command(cmd, lambda _e, c, out=out: CommandResult(c, 0, stdout=out, state_delta=dict(STATE_DELTA)))
    hooks = TreeGLM(2)
    envmap = build_envmap_from_task("/tmp/aether-empty-task-dir", TASK, workspace_root="/app", projection_mode="factual_only")
    result = run_thin_loop(envmap, executor, hooks, config=ThinLoopConfig(
        max_steps=30, max_solver_turns=30, probe_runtime_capabilities=False,
        runtime_identity={"task_id": "t", "run_id": "combo", "primary_agent_id": "p"},
        context_tree_adapter=tree, claim_ledger_controller=controller))
    assert result.status == "submitted", [(r.kind, r.summary) for r in result.receipts][-5:]

    # Feedback and card turns are ordinary tree events.
    notes = [json.loads(line) for line in (tmp_path / "tree" / "combo" / "log" / "events.jsonl").read_text().splitlines()]
    note_text = [row["text"] for row in notes if row["kind"] == "note"]
    assert any(t.startswith("CHALLENGER diagnosis review") for t in note_text)
    assert any(t.startswith("CHALLENGER completion hold 1 of 3") for t in note_text)
    assert any(t.startswith("Your diagnosis card:") for t in note_text)
    assert any(t.startswith("Your completion card:") for t in note_text)

    # The model sees the feedback: in the packet on the next turn, and in the view after an epoch boundary.
    packets = [m["content"] for req in hooks.requests for m in req if m["content"].startswith("[context_packet]")]
    assert any("Diagnosis review" in p for p in packets)
    views = [m["content"] for req in hooks.requests for m in req if m["role"] == "user" and m["content"].startswith("<chat>")]
    assert tree.telemetry()["epoch_boundaries"], "scenario must cross an epoch boundary"
    assert any("CHALLENGER diagnosis review: ranking H1>H2" in v and "exit_code=0" in v for v in views), "feedback must be carried verbatim by the M-TREE view"
    assert all(len(t.encode()) <= 512 for t in note_text if t.startswith("CHALLENGER "))

    # Budgets: every solver request, every card request, and every view stays within the M-TREE limits.
    assert all(_tree_request_estimate({"messages": req}) <= REQUEST_LIMIT for req in hooks.requests + card_requests)
    assert all(len(v.encode()) <= VIEW_BYTES for v in views)
    assert max(tree.telemetry()["view_bytes_per_epoch_start"]) <= VIEW_BYTES
    # Card requests are the bounded epoch request (task + view + packet) plus the instruction, not a raw replay.
    assert len(card_requests) == 3
    for req in card_requests:
        assert any(m["content"] == TASK for m in req) and any(m["content"].startswith("<chat>") for m in req)
        assert "card as ONE JSON object" in req[-1]["content"]
    assert tree.telemetry()["solver_requests"] == len(hooks.requests) + len(card_requests)


def test_t2_refresh_enters_the_tree_and_is_accounted_like_t1(tmp_path: Path) -> None:
    from tests.harness.test_challenger_runtime_triggers import ListGLM, cmd, write

    class TreeList(ListGLM):
        def reset_solver_continuity_for_recovery(self) -> bool:
            return True

    tree = ContextTreeAdapter(
        raw_task=TASK, evidence_root=tmp_path / "tree", run_id="t2", compactor_provider=_compactor,
        compactor_route="fake-route", compactor_limiter_path=tmp_path / "limiter.json",
        epoch_steps=50, request_limit=REQUEST_LIMIT, view_bytes=VIEW_BYTES, jobs=2, retry_s=0.01)
    card_requests: list[list[dict[str, str]]] = []
    inner = make_card_model([])

    def card_model(messages: list[dict[str, str]]) -> str:
        card_requests.append(json.loads(json.dumps(messages)))
        return inner(messages)

    judge = FakeJudge(all_direct, progress=("test_only_change", 0.9))
    controller = ChallengerController(
        card_model=card_model, evaluator=JudgeClient(judge, model="judge-1.13.0", raw_task=TASK),
        evidence_dir=tmp_path / "challenger", run_id="t2", task_text=TASK)
    executor = MemoryExecutor(workspace_root="/app", files={"src/parser.py": "old"})
    for c in (CHECK_CMD, "grep -n strip src/parser.py", *(f"echo read {i}" for i in range(10))):
        executor.register_command(c, lambda _e, command: CommandResult(command, 0, stdout="ok", state_delta=dict(STATE_DELTA)))
    turns = [write("w", "src/parser.py")] + [cmd(f"r{i}", f"echo read {i}") for i in range(8)]
    hooks = TreeList(turns)
    envmap = build_envmap_from_task("/tmp/aether-empty-task-dir", TASK, workspace_root="/app", projection_mode="factual_only")
    run_thin_loop(envmap, executor, hooks, config=ThinLoopConfig(
        max_steps=len(turns), max_solver_turns=len(turns), probe_runtime_capabilities=False,
        runtime_identity={"task_id": "t", "run_id": "t2", "primary_agent_id": "p"},
        context_tree_adapter=tree, claim_ledger_controller=controller))
    notes = [json.loads(line)["text"] for line in (tmp_path / "tree" / "t2" / "log" / "events.jsonl").read_text().splitlines()
             if json.loads(line)["kind"] == "note"]
    assert any(t.startswith("Your refreshed diagnosis card:") for t in notes)
    refresh = [t for t in notes if t.startswith("CHALLENGER diagnosis refresh:")]
    assert refresh and all(len(t.encode()) <= 512 for t in refresh)
    assert len(card_requests) == 2  # T1 card and the T2 card, both through the tree's request accounting
    assert all(_tree_request_estimate({"messages": r}) <= REQUEST_LIMIT for r in card_requests)
    assert tree.telemetry()["solver_requests"] == len(hooks.turns[:hooks.calls]) + 2

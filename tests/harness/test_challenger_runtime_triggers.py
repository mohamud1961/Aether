"""T1 trigger rule: first of write_file, clear shell write, or the action-count fallback."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aether.challenger_runtime.config import T1_FALLBACK_ACTIONS
from aether.challenger_runtime.controller import ChallengerController
from aether.challenger_runtime.judge_client import JudgeClient
from aether.challenger_runtime.shell_writes import command_write_targets
from aether.envmap_builder import build_envmap_from_task
from aether.execution import CommandResult, MemoryExecutor
from aether.runtime_ir import SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop
from tests.harness.test_challenger_runtime_loop import (
    CHECK_CMD, STATE_DELTA, TASK, FakeJudge, _action, all_direct, make_card_model,
)

HEREDOC = "cat <<'EOF' > src/parser.py\nx = a > b\nEOF"


def cmd(i: str, command: str) -> SolverTurn:
    return SolverTurn(kind="act", summary=f"run {i}", actions=(_action(i, "run_command", "shell", {"command": command}),))


def write(i: str, path: str) -> SolverTurn:
    return SolverTurn(kind="act", summary=f"write {i}", actions=(
        _action(i, "write_file", "filesystem", {"path": path, "content": i}),))


class ListGLM:
    def __init__(self, turns: list[SolverTurn]) -> None:
        self.turns, self.calls = turns, 0

    def solve(self, messages, _compiled) -> SolverTurn:
        self.calls += 1
        return self.turns[self.calls - 1]


def drive(tmp_path: Path, turns: list[SolverTurn], commands: tuple[str, ...] = (), judge: FakeJudge | None = None,
          card_model=None):
    executor = MemoryExecutor(workspace_root="/app", files={"src/parser.py": "old"})
    for c in (CHECK_CMD, "grep -n strip src/parser.py", *commands):
        executor.register_command(c, lambda _e, command: CommandResult(command, 0, stdout="ok", state_delta=dict(STATE_DELTA)))
    controller = ChallengerController(
        card_model=card_model or make_card_model([]),
        evaluator=JudgeClient(judge or FakeJudge(all_direct), model="judge-1.13.0", raw_task=TASK),
        evidence_dir=tmp_path / "challenger", run_id="t-run", task_text=TASK)
    envmap = build_envmap_from_task("/tmp/aether-empty-task-dir", TASK, workspace_root="/app", projection_mode="factual_only")
    result = run_thin_loop(envmap, executor, ListGLM(turns), config=ThinLoopConfig(
        max_steps=len(turns), max_solver_turns=len(turns),
        runtime_identity={"task_id": "t", "run_id": "t-run", "primary_agent_id": "p"},
        claim_ledger_controller=controller))
    path = tmp_path / "challenger" / "challenger_events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    drive.controller = controller
    return result, executor, [e for e in events if e["event"] == "trigger"], events


@pytest.mark.parametrize("command,targets", [
    ("echo hi > src/a.py", ("src/a.py",)),
    (HEREDOC, ("src/parser.py",)),
    ("make 2>&1 | tee -a build.log", ("build.log",)),
    ("sed -i 's/a/b/' src/c.py", ("src/c.py",)),
    ("cmd >> out.txt", ("out.txt",)),
    ("python -c 'print(1>0)'", ()),
    ("ls 2>&1; foo 2>/dev/null; echo x >&2", ()),
    ("python - <<'PY'\nprint(a > b)\nPY", ()),
    ("echo x > $OUT", ()),
    ("sed 's/a/b/' src/c.py", ()),
])
def test_shell_write_detection_is_conservative(command: str, targets: tuple[str, ...]) -> None:
    assert command_write_targets(command) == targets


def test_t1_via_write_file_records_its_source(tmp_path: Path) -> None:
    _, _, triggers, _ = drive(tmp_path, [write("w0", "scratch_x.py"), write("w1", "src/parser.py"), write("w2", "src/other.py")])
    assert [(t["source"], t["path"]) for t in triggers if t["kind"] == "first_production_write"] == [("write_file", "src/parser.py")]


def test_t1_via_shell_write_runs_check_before_the_pending_command(tmp_path: Path) -> None:
    result, executor, triggers, events = drive(
        tmp_path, [cmd("c0", "echo hi > /tmp/note.txt"), cmd("c1", HEREDOC), write("w2", "src/other.py")], commands=(HEREDOC,))
    t1 = [t for t in triggers if t["kind"] == "first_production_write"]
    assert [(t["source"], t["path"]) for t in t1] == [("command_write", "src/parser.py")]
    ids = [r.receipt_id for r in result.receipts]
    check = next(i for i in ids if ":challenger-check-" in i and i.endswith(":cmd"))
    pending = next(i for i in ids if i.endswith(":c1:cmd"))
    assert ids.index(check) < ids.index(pending)
    assert executor.command_history.index(CHECK_CMD) < executor.command_history.index(HEREDOC)
    assert any(e["event"] == "feedback" and e["kind"] == "diagnosis" for e in events)


@pytest.mark.parametrize("command", [
    "echo x > /tmp/a.txt", "echo x > scratch_notes.txt", "echo x > test_repro.py", "ls 2>&1", "python -c 'print(1>0)'",
    "cat src/parser.py",
])
def test_scratch_or_unclear_shell_commands_do_not_trigger(tmp_path: Path, command: str) -> None:
    _, _, triggers, _ = drive(tmp_path, [cmd("c0", command)], commands=(command,))
    assert triggers == []


def test_t1_fallback_fires_after_n_accepted_actions_once(tmp_path: Path) -> None:
    reads = [cmd(f"r{i}", f"echo read {i}") for i in range(T1_FALLBACK_ACTIONS)]
    cmds = tuple(f"echo read {i}" for i in range(T1_FALLBACK_ACTIONS + 3))
    _, _, none_yet, _ = drive(tmp_path / "a", reads, commands=cmds)
    assert none_yet == []  # exactly N read-only actions: not yet
    turns = reads + [cmd("r8", "echo read 8"), write("w", "src/parser.py"), cmd("r9", "echo read 9")]
    result, _, triggers, events = drive(tmp_path / "b", turns, commands=cmds)
    t1 = [t for t in triggers if t["kind"] == "first_production_write"]
    assert len(t1) == 1 and t1[0]["source"] == "fallback" and t1[0]["step"] == T1_FALLBACK_ACTIONS
    assert sum(1 for e in events if e["event"] == "card" and e["card"] == "diagnosis") == 1
    assert any(i.endswith(":cmd") and ":challenger-check-" in i for i in (r.receipt_id for r in result.receipts))


def test_a_real_write_before_the_fallback_wins_and_fallback_never_refires(tmp_path: Path) -> None:
    turns = [write("w", "src/parser.py")] + [cmd(f"r{i}", f"echo read {i}") for i in range(T1_FALLBACK_ACTIONS + 2)]
    _, _, triggers, _ = drive(tmp_path, turns, commands=tuple(f"echo read {i}" for i in range(12)))
    assert [t["source"] for t in triggers if t["kind"] == "first_production_write"] == ["write_file"]

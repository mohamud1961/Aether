"""T2: JUDGE progress question per 6 actions after T1; a stalled window triggers a refreshed diagnosis."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aether.challenger_runtime.config import LEDGER_MAX_CYCLES, T2_FLAG_THRESHOLD, T2_MAX_REFRESHES, T2_WINDOW_ACTIONS
from aether.challenger_runtime.progress_question import PROGRESS_CHOICES
from tests.harness.test_challenger_runtime_loop import FakeJudge, all_direct
from tests.harness.test_challenger_runtime_triggers import cmd, drive, write

N_READS = 3 * T2_WINDOW_ACTIONS + 2
READS = tuple(f"echo read {i}" for i in range(40))


def script(n: int = N_READS):
    return [write("w", "src/parser.py")] + [cmd(f"r{i}", f"echo read {i}") for i in range(n)]


def progress_judge(choice: str, prob: float, **kw: Any) -> FakeJudge:
    return FakeJudge(all_direct, progress=(choice, prob), **kw)


def progress_requests(judge: FakeJudge) -> list[dict[str, Any]]:
    return [r for r in judge.requests if "progress:window" in r["questions"]]


def test_flagged_window_triggers_a_refreshed_diagnosis_that_runs_a_check(tmp_path: Path) -> None:
    judge = progress_judge("no_material_change", 0.85)
    result, executor, triggers, events = drive(tmp_path, script(T2_WINDOW_ACTIONS + 2), commands=READS, judge=judge)
    t2 = [t for t in triggers if t.get("source") == "judge_progress"]
    assert len(t2) == 1 and t2[0]["choice"] == "no_material_change" and t2[0]["refresh"] == 1
    # the question is the replay question: same choices, a latest window (w*) and a previous one (p*)
    req = progress_requests(judge)[0]
    q = req["questions"]["progress:window"]
    assert list(q["criteria"]) == list(PROGRESS_CHOICES)
    refs = set(req["state"]["visible_evidence"])
    assert {r for r in refs if r.startswith("w")} and len([r for r in refs if r.startswith("w")]) == T2_WINDOW_ACTIONS
    cards = [e for e in events if e["event"] == "card" and e["card"] == "diagnosis"]
    assert len(cards) == 2 and cards[1]["card_id"] != cards[0]["card_id"]
    fb = next(e for e in events if e["event"] == "feedback" and e["kind"] == "diagnosis_refresh")
    assert fb["text"].startswith("Progress review: the last 6 actions were judged no material change (0.85).")
    assert "Result: exit_code=0" in fb["text"]
    ids = [r.receipt_id for r in result.receipts]
    assert sum(1 for i in ids if ":challenger-check-" in i and i.endswith(":cmd")) == 2  # T1 check + T2 check
    assert drive.controller.ledger.verify_repair_cycles == 2


@pytest.mark.parametrize("choice,prob,flagged", [
    ("no_material_change", T2_FLAG_THRESHOLD - 0.01, False),   # below threshold
    ("advanced_criterion", 0.99, False),                        # confident but not a stall
    ("symptom_moved", 0.95, False),
    ("regression", 0.95, False),
    ("test_only_change", T2_FLAG_THRESHOLD, True),              # boundary is inclusive
    ("no_material_change", 0.95, True),
])
def test_flag_rule(tmp_path: Path, choice: str, prob: float, flagged: bool) -> None:
    judge = progress_judge(choice, prob)
    _, _, triggers, events = drive(tmp_path, script(T2_WINDOW_ACTIONS + 2), commands=READS, judge=judge)
    assert len(progress_requests(judge)) == 1
    assert bool([t for t in triggers if t.get("source") == "judge_progress"]) is flagged
    assert any(e["event"] == ("judge_answer" if flagged else "progress_ok") for e in events)


def test_no_progress_question_before_a_full_window_after_t1(tmp_path: Path) -> None:
    judge = progress_judge("no_material_change", 0.99)
    drive(tmp_path, script(T2_WINDOW_ACTIONS - 2), commands=READS, judge=judge)
    assert progress_requests(judge) == []


def test_at_most_two_refreshes_and_no_questions_after_the_cap(tmp_path: Path) -> None:
    judge = progress_judge("no_material_change", 0.99)
    _, _, triggers, events = drive(tmp_path, script(), commands=READS, judge=judge)
    assert len([t for t in triggers if t.get("source") == "judge_progress"]) == T2_MAX_REFRESHES == 2
    assert len(progress_requests(judge)) == 2  # the third window is not even asked
    assert drive.controller.ledger.verify_repair_cycles == 1 + T2_MAX_REFRESHES <= LEDGER_MAX_CYCLES


def test_progress_error_is_skipped_silently_and_the_run_continues(tmp_path: Path) -> None:
    judge = progress_judge("no_material_change", 0.99, fail_progress=True)
    result, _, triggers, events = drive(tmp_path, script(2 * T2_WINDOW_ACTIONS + 1), commands=READS, judge=judge)
    errors = [e for e in events if e["event"] == "progress_error"]
    assert len(errors) == 2 and errors[0]["error_type"] == "TimeoutError"
    assert not [t for t in triggers if t.get("source") == "judge_progress"]
    assert not [e for e in events if e["event"] == "degraded"]
    assert result.status == "step_budget_exhausted"


def test_refresh_card_failure_degrades_without_spending_a_cycle(tmp_path: Path) -> None:
    from tests.harness.test_challenger_runtime_loop import make_card_model
    inner = make_card_model([])
    calls = {"diagnosis": 0}

    def card_model(messages):
        text = " ".join(m["content"] for m in messages[-3:])
        if "diagnosis card" in text:
            calls["diagnosis"] += 1
            if calls["diagnosis"] > 1:  # T1's card is fine; the T2 card and its repair turn are garbage
                return "garbage"
        return inner(messages)

    judge = progress_judge("no_material_change", 0.99)
    _, _, _, events = drive(tmp_path, script(T2_WINDOW_ACTIONS + 2), commands=READS, judge=judge, card_model=card_model)
    assert [e["where"] for e in events if e["event"] == "degraded"] == ["T2"]
    assert drive.controller.ledger.verify_repair_cycles == 1  # only T1 ran a card turn that reached JUDGE


def test_t2_does_nothing_without_t1_and_never_fires_in_control(tmp_path: Path) -> None:
    judge = progress_judge("no_material_change", 0.99)
    _, _, triggers, _ = drive(tmp_path, [cmd(f"r{i}", f"echo read {i}") for i in range(7)], commands=READS, judge=judge)
    assert triggers == [] and progress_requests(judge) == []  # < 8 actions: neither T1 nor a T2 window

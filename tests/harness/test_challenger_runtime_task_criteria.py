"""T4 task-text criteria merge and the 2000-char check bound (provider-free)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import tests.harness.test_challenger_runtime_loop as loop
from aether.challenger_runtime.cards import CardError, parse_completion, parse_diagnosis
from aether.challenger_runtime.completion import MAX_HELD_CRITERIA_SHOWN
from tests.harness.test_challenger_runtime_loop import FakeJudge, all_direct, events, make_card_model, run_scenario

REQS = ["Fix the parser so parse('a;b') returns ['a', 'b'].",
        "Write a note about the separator in README.md.",
        "Add a unit test for the parser."]
TASK3 = "\n".join(REQS)


def one_criterion_model(text: str = REQS[0]):
    base = make_card_model([])

    def model(messages: list[dict[str, str]]) -> str:
        if "diagnosis card" in messages[-1]["content"]:
            return base(messages)
        ref = next(line.split(" | ")[0] for m in reversed(messages) for line in m["content"].splitlines()
                   if ":cmd | " in line)
        return json.dumps({"criteria": [{"id": "C1", "text": text, "evidence_refs": [ref],
                                         "check": {"description": "run verify", "command": loop.VERIFY_CMD}}]})
    return model


def completeness_asked(judge: FakeJudge) -> list[list[str]]:
    return [[q.split(":")[1] for q in r["questions"] if q.startswith("completeness:")]
            for r in judge.requests if any(q.startswith("completeness:") for q in r["questions"])]


def task_none(conf: float):
    return lambda n, cid: ("none", conf) if cid == "T2" else ("direct_and_current", 0.95)


def test_one_card_criterion_plus_three_task_requirements_reach_judge_without_duplicates(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "TASK", TASK3)
    judge = FakeJudge(all_direct)
    run_scenario(tmp_path, judge, card_model=one_criterion_model())
    first = completeness_asked(judge)[0]
    assert sorted(first) == ["C1", "T1", "T2"]  # requirement 1 is the card's C1: not asked twice
    ev = events(tmp_path)
    card = next(e for e in ev if e["event"] == "card" and e["card"] == "completion")
    by = {c["criterion"]: c for c in card["claims"]}
    assert by["C1"]["source"] == "glm_card"
    assert by["T1"]["source"] == by["T2"]["source"] == "task_text" and by["T1"]["text"] == REQS[1]
    assert by["T1"]["evidence_refs"] == by["C1"]["evidence_refs"]  # asked with the card's cited evidence
    ledger = json.loads((tmp_path / "challenger" / "challenger_claim_ledger.json").read_text())
    claims = {c["criterion_id"]: c for card_ in ledger["cards"] if card_["kind"] == "completion" for c in card_["claims"]}
    assert claims["T2"]["source"] == "task_text"


def test_uncovered_task_criterion_none_at_0_7_holds_and_is_named_verbatim(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "TASK", TASK3)
    run_scenario(tmp_path, FakeJudge(task_none(0.7)), card_model=one_criterion_model())
    ev = events(tmp_path)
    hold = next(e for e in ev if e["event"] == "action" and e["kind"] == "hold_finish")
    assert hold["held"] == ["T2"]
    text = next(e["text"] for e in ev if e["event"] == "feedback" and e["kind"] == "completion_hold")
    assert f'T2: "{REQS[2]}" [taken from the task text; your completion card did not cover it] judged none (confidence 0.70)' in text
    assert "Suggested next step: write and run one command that demonstrates this criterion" in text


def test_uncovered_task_criterion_none_at_0_5_is_advisory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "TASK", TASK3)
    result, *_ = run_scenario(tmp_path, FakeJudge(task_none(0.5)), card_model=one_criterion_model())
    ev = events(tmp_path)
    assert not [e for e in ev if e["event"] == "action" and e["kind"] == "hold_finish"]
    advisory = next(e for e in ev if e["event"] == "action" and e["kind"] == "advisory_only")
    assert any(n.startswith("T2: judged none") for n in advisory["notes"])
    assert result.status == "submitted"


def test_card_wording_wins_on_duplicates_even_with_punctuation_and_case_differences(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "TASK", TASK3)
    judge = FakeJudge(all_direct)
    run_scenario(tmp_path, judge, card_model=one_criterion_model("fix the parser so parse('a;b') RETURNS ['a','b']"))
    assert sorted(completeness_asked(judge)[0]) == ["C1", "T1", "T2"]
    q = next(r for r in judge.requests if "completeness:C1" in r["questions"])
    assert "RETURNS" in json.dumps(q)  # the solver's wording, not the task's, labels C1


def test_total_criteria_capped_at_twelve(monkeypatch: pytest.MonkeyPatch) -> None:
    from aether.challenger_claim_types import CompletionCard, Criterion, CriterionClaim
    from aether.challenger_runtime.task_criteria import merge_task_criteria
    card = CompletionCard("c", "t", tuple(CriterionClaim(f"C{i}", ("r",), ("none",)) for i in range(1, 9)))
    criteria = tuple(Criterion(f"C{i}", f"card criterion number {i}") for i in range(1, 9))
    task = "\n".join(f"Implement requirement number {i} of the task." for i in range(20))
    merged_card, merged, added = merge_task_criteria(card, criteria, task)
    assert len(merged) == 12 and len(added) == 4 and len(merged_card.claims) == 12


def test_no_extra_criteria_leaves_card_unchanged() -> None:
    from aether.challenger_claim_types import CompletionCard, Criterion, CriterionClaim
    from aether.challenger_runtime.task_criteria import merge_task_criteria
    card = CompletionCard("c", "t", (CriterionClaim("C1", ("r",), ("none",)),))
    same, criteria, added = merge_task_criteria(card, (Criterion("C1", "Fix the parser."),), "Fix the parser.")
    assert same is card and added == ()


def _card(command: str) -> str:
    return json.dumps({"criteria": [{"id": "C1", "text": "t", "evidence_refs": [],
                                     "check": {"description": "d", "command": command}}]})


def test_check_command_bound_is_2000_for_t4_and_t1() -> None:
    ok = "echo " + "x" * 1495
    assert len(ok) == 1500
    parse_completion(_card(ok), card_id="c", trigger_id="t", known_refs=set())
    diag = json.dumps({"symptom": "s", "hypotheses": [
        {"id": f"H{i}", "statement": "s", "check": {"description": "d", "command": ok}} for i in (1, 2)]})
    parse_diagnosis(diag, card_id="c", trigger_id="t")
    big = "echo " + "x" * 2495
    assert len(big) == 2500
    with pytest.raises(CardError, match="longer than 2000 characters"):
        parse_completion(_card(big), card_id="c", trigger_id="t", known_refs=set())
    with pytest.raises(CardError, match="longer than 2000 characters"):
        parse_diagnosis(diag.replace(ok, big), card_id="c", trigger_id="t")


def test_oversized_check_takes_the_repair_path_then_is_accepted(tmp_path: Path) -> None:
    seen: list[str] = []
    base = one_criterion_model()

    def model(messages: list[dict[str, str]]) -> str:
        prompt = messages[-1]["content"]
        if "diagnosis card" in prompt:
            return base(messages)
        seen.append(prompt)
        if "could not be used" in prompt:
            return base(messages)
        return _card("echo " + "x" * 2495)
    run_scenario(tmp_path, FakeJudge(all_direct), card_model=model)
    ev = events(tmp_path)
    invalid = [e for e in ev if e["event"] == "card_invalid"]
    assert invalid and "longer than 2000 characters" in invalid[0]["error"]
    assert any("longer than 2000 characters" in p for p in seen)
    assert not [e for e in ev if e["event"] == "degraded"]
    assert any(e["event"] == "action" for e in ev)


def test_task_without_requirement_sentences_adds_no_task_criteria():
    # The whole-task fallback must not become a T4 criterion (false-hold risk).
    from aether.challenger_runtime.progress_question import split_criteria
    text = "hello there. this is a vague note without any requirement sentences."
    assert split_criteria(text) and split_criteria(text, fallback=False) == []


def test_descriptive_dont_in_reference_list_is_not_a_criterion():
    # Live false holds: a CWE example bullet ("Sessions don't expire properly") was
    # taken as a requirement and JUDGE correctly found no evidence for it.
    from aether.challenger_runtime.progress_question import split_criteria
    task = ("Fix the vulnerability in the code.\n"
            "- CWE-613: Insufficient Session Expiration - Sessions don't expire properly.\n"
            "- Do not modify the test files.\n")
    texts = [c["text"] for c in split_criteria(task, fallback=False)]
    assert any("Fix the vulnerability" in t for t in texts)
    assert any("Do not modify the test files" in t for t in texts)
    assert not any("CWE-613" in t for t in texts)

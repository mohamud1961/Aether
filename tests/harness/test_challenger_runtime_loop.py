"""Provider-free CHALLENGER runtime tests: scripted fake GLM + fake card model + fake JUDGE through the real thin loop."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

import pytest

from aether.challenger_claim_types import QuestionAnswer
from aether.challenger_runtime.completion import decide_finish
from aether.challenger_runtime.config import MAX_HOLD_CYCLES
from aether.challenger_runtime.controller import ChallengerController
from aether.challenger_runtime.judge_client import JudgeClient
from aether.challenger_claim_types import ActionKind, Criterion
from aether.envmap_builder import build_envmap_from_task
from aether.execution import CommandResult, MemoryExecutor
from aether.runtime_ir import ActionRequest, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop

TASK = ("Fix the parser so parse('a;b') returns ['a', 'b'] (criterion one). "
        "Also document the separator in README.md (criterion two).")
CHECK_CMD = "grep -n split src/parser.py"
VERIFY_CMD = "python verify.py"
STATE_DELTA = {
    "created_paths": [], "removed_paths": [], "content_changed_paths": [], "metadata_changed_paths": [],
    "before_truncated": False, "after_truncated": False,
    "mutation_detection_status": "complete", "path_set_delta_status": "complete",
}


def _action(action_id: str, kind: str, cap: str, args: dict[str, Any]) -> ActionRequest:
    return ActionRequest(action_id=action_id, kind=kind, capability_id=cap, arguments=args,
                         intent="address the current evidence gap", expected_observation="one exact result",
                         if_fail_next="inspect the failure")


def _packet(messages: list[dict[str, str]]) -> dict[str, Any]:
    for message in messages:
        if str(message.get("content", "")).startswith("[context_packet]\n"):
            return json.JSONDecoder().raw_decode(message["content"][len("[context_packet]\n"):])[0]
    raise AssertionError("no context packet")


class ScriptedGLM:
    """Writes scratch, then production, verifies, then keeps trying to finish."""

    def __init__(self, finishes: int = 2) -> None:
        self.calls = 0
        self.requests: list[list[dict[str, str]]] = []
        self.finishes = finishes

    def _ref(self, messages) -> str:
        rows = [r for r in _packet(messages).get("evidence_index", [])
                if isinstance(r, dict) and r.get("evidence_type") == "run_command" and r.get("evidence_ref")]
        current = [r for r in rows if r.get("currentness") == "latest_primary_result"]
        return str((current or rows)[0]["evidence_ref"])

    def solve(self, messages, _compiled) -> SolverTurn:
        self.calls += 1
        self.requests.append(json.loads(json.dumps(messages)))
        n = self.calls
        if n == 1:
            return SolverTurn(kind="act", summary="repro script", actions=(
                _action("w-scratch", "write_file", "filesystem", {"path": "scratch_repro.py", "content": "print(1)"}),))
        if n == 2:
            return SolverTurn(kind="act", summary="patch the parser", actions=(
                _action("w-parser", "write_file", "filesystem", {"path": "src/parser.py", "content": "x.split(',')"}),))
        if n == 3:
            return SolverTurn(kind="act", summary="verify", actions=(
                _action("verify", "run_command", "shell", {"command": VERIFY_CMD}),))
        phase = 2 if n == 4 else (n - 5) % 3
        if phase == 2:
            return SolverTurn(kind="finish_intent", summary="done", claim="parser fixed and documented",
                              evidence_refs=(self._ref(messages),))
        if phase == 0:
            return SolverTurn(kind="act", summary="touch docs", actions=(
                _action(f"w-readme-{n}", "write_file", "filesystem", {"path": "README.md", "content": f"sep ';' {n}"}),))
        return SolverTurn(kind="act", summary="re-verify", actions=(
            _action(f"verify-{n}", "run_command", "shell", {"command": VERIFY_CMD}),))


def make_card_model(log: list[str]) -> Callable[[list[dict[str, str]]], str]:
    def model(messages: list[dict[str, str]]) -> str:
        prompt = messages[-1]["content"]
        log.append(prompt)
        if "diagnosis card" in prompt:
            return json.dumps({"symptom": "parse('a;b') does not split on ';'", "hypotheses": [
                {"id": "H1", "statement": "separator is hard-coded as a comma", "status": "dismissed",
                 "reason": "the code looked plausible", "check": {"description": "inspect split call", "command": CHECK_CMD}},
                {"id": "H2", "statement": "input is stripped before parsing", "status": "considered",
                 "check": {"description": "inspect strip call", "command": "grep -n strip src/parser.py"}}]})
        ref = next(line.split(" | ")[0] for line in prompt.splitlines() if ":cmd | " in line)
        return json.dumps({"criteria": [
            {"id": "C1", "text": "parse('a;b') returns ['a', 'b']", "evidence_refs": [ref],
             "check": {"description": "run verify", "command": VERIFY_CMD}},
            {"id": "C2", "text": "README documents the separator", "evidence_refs": [],
             "check": {"description": "grep README", "command": "grep -n ';' README.md"}}]})
    return model


class FakeJudge:
    """Transport double: answers every wire question per the behaviour table."""

    def __init__(self, completeness: Callable[[int, str], tuple[str, float]], *, fail: bool = False,
                 rank: dict[str, float] | None = None, separating: tuple[str, float] = ("H1", 0.7),
                 progress: tuple[str, float] | Callable[[int], tuple[str, float]] = ("advanced_criterion", 0.9),
                 fail_progress: bool = False) -> None:
        self.progress, self.fail_progress = progress, fail_progress
        self.rank = rank or {"H1": 0.6, "H2": 0.4}
        self.separating = separating
        self.requests: list[dict[str, Any]] = []
        self.completeness = completeness
        self.fail = fail

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(json.loads(json.dumps(request)))
        if self.fail:
            raise TimeoutError("judge down")
        answers = {}
        round_no = len(self.requests)
        for qid, q in request["questions"].items():
            choices = list(q["criteria"])
            if qid.startswith("hypothesis_rank:"):
                assert choices == ["H1", "H2"]  # ONE question; choices are the hypothesis ids
                choice = max(self.rank, key=self.rank.get)
                answers[qid] = {"choice": choice, "probabilities": dict(self.rank)}
                continue
            if qid == "progress:window":
                if self.fail_progress:
                    raise TimeoutError("progress judge down")
                choice, conf = self.progress(len(self.requests)) if callable(self.progress) else self.progress
                answers[qid] = {"choice": choice, "probabilities": {choice: conf, "advanced_criterion": 1 - conf}}
                continue
            if qid.startswith("separating_check:"):
                choice, conf = self.separating
            else:
                choice, conf = self.completeness(round_no, qid.split(":")[1])
            answers[qid] = {"choice": choice, "probabilities": {choice: conf}}
        return {"result": {"answers": answers}}


def run_scenario(tmp_path: Path, judge: FakeJudge | None, *, finishes: int = 2, max_steps: int = 20, card_model=None):
    executor = MemoryExecutor(workspace_root="/app", files={"src/parser.py": "x.split(',')"})
    for cmd, out in ((CHECK_CMD, "12: x.split(',')"), (VERIFY_CMD, "verified"), ("grep -n strip src/parser.py", "")):
        executor.register_command(cmd, lambda _e, c, out=out: CommandResult(c, 0, stdout=out, state_delta=dict(STATE_DELTA)))
    hooks = ScriptedGLM(finishes)
    card_log: list[str] = []
    controller = None
    if judge is not None:
        controller = ChallengerController(
            card_model=card_model or make_card_model(card_log),
            evaluator=JudgeClient(judge, model="judge-1.13.0", raw_task=TASK),
            evidence_dir=tmp_path / "challenger", run_id="t-run", task_text=TASK)
    envmap = build_envmap_from_task("/tmp/aether-empty-task-dir", TASK, workspace_root="/app",
                                    projection_mode="factual_only")
    result = run_thin_loop(envmap, executor, hooks, config=ThinLoopConfig(
        max_steps=max_steps, max_solver_turns=max_steps,
        runtime_identity={"task_id": "t", "run_id": "t-run", "primary_agent_id": "primary"},
        claim_ledger_controller=controller))
    return result, hooks, card_log, controller, executor


def events(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "challenger" / "challenger_events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def hold_none(round_no: int, cid: str) -> tuple[str, float]:
    return ("none", 0.95) if cid == "C2" else ("direct_and_current", 0.95)


def all_direct(round_no: int, cid: str) -> tuple[str, float]:
    return "direct_and_current", 0.95


def test_vertical_t1_then_t4_hold_then_admit(tmp_path: Path) -> None:
    judge = FakeJudge(lambda n, cid: hold_none(n, cid) if n <= 2 else all_direct(n, cid))
    result, hooks, card_log, controller, executor = run_scenario(tmp_path, judge)
    assert result.status == "submitted", [(r.kind, r.summary) for r in result.receipts][-6:]
    ev = events(tmp_path)
    kinds = [e["event"] for e in ev]
    # T1 fires exactly once, on the production write, not on the scratch write.
    triggers = [e for e in ev if e["event"] == "trigger"]
    assert [t["kind"] for t in triggers].count("first_production_write") == 1
    t1 = next(t for t in triggers if t["kind"] == "first_production_write")
    assert t1["path"] == "src/parser.py"
    # Event chain for T1: card -> JUDGE question -> JUDGE answer -> action -> feedback.
    t1_chain = kinds[kinds.index("trigger"):]
    for needed in ("card", "judge_question", "judge_answer", "action", "feedback"):
        assert needed in t1_chain
    # The GLM-written check ran through the ordinary executor before the write, then the write proceeded.
    ids = [r.receipt_id for r in result.receipts]
    check_id = next(i for i in ids if ":challenger-check-" in i and i.endswith(":cmd"))
    write_id = next(i for i in ids if i.endswith(":w-parser:write"))
    assert ids.index(check_id) < ids.index(write_id)
    assert CHECK_CMD in executor.command_history
    assert executor.read_file("src/parser.py") == "x.split(',')"
    # The solver's next request carries the ranking, check and result with its evidence ref.
    fb1 = _packet(hooks.requests[2])["claim_ledger_feedback"]["text"]
    assert "1. H1 (probability 0.60)" in fb1 and "2. H2 (probability 0.40)" in fb1 and "dismissed by the solver" in fb1
    assert CHECK_CMD in fb1 and "exit_code=0" in fb1 and check_id in fb1
    assert "claim_ledger_feedback" not in _packet(hooks.requests[1])
    # T4: the first finish is held on C2, the solver sees the criterion and a check to run.
    holds = [e for e in ev if e["event"] == "action" and e["kind"] == "hold_finish"]
    assert len(holds) == 1 and holds[0]["held"] == ["C2"]
    hold_fb = next(e["text"] for e in ev if e["event"] == "feedback" and e["kind"] == "completion_hold")
    assert "README documents the separator" in hold_fb and "judged none" in hold_fb
    assert "grep -n ';' README.md" in hold_fb and "has not been run" in hold_fb
    assert any(e["event"] == "action" and e["kind"] == "admit_finish" for e in ev)
    assert len(card_log) == 3  # one diagnosis card turn, two completion card turns
    ledger_json = json.loads((tmp_path / "challenger" / "challenger_claim_ledger.json").read_text())
    assert len(ledger_json["cards"]) == 3 and ledger_json["verify_repair_cycles"] == 3
    assert ledger_json["thresholds"]["max_cycles"] == 6
    from aether.challenger_claim_ledger import TaskLocalClaimLedger
    assert TaskLocalClaimLedger.from_dict(ledger_json, expected_identity=controller.ledger.identity).max_cycles == 6
    assert [c["kind"] for c in ledger_json["cards"]] == ["diagnosis", "completion", "completion"]
    # JUDGE saw the task text and solver evidence only.
    sent = json.dumps(judge.requests)
    assert "parse('a;b')" in sent and "hidden" not in sent.lower() and "grader" not in sent.lower()


def test_hold_cap_admits_after_three_holds(tmp_path: Path) -> None:
    judge = FakeJudge(hold_none)
    result, hooks, card_log, *_ = run_scenario(tmp_path, judge, finishes=6, max_steps=40)
    assert result.status == "submitted"
    ev = events(tmp_path)
    holds = [e for e in ev if e["event"] == "action" and e["kind"] == "hold_finish"]
    assert len(holds) == MAX_HOLD_CYCLES == 3
    assert any(e["event"] == "finish_admitted" and e["reason"] == "hold cap reached" for e in ev)
    completion_calls = [r for r in judge.requests if any(q.startswith("completeness:") for q in r["questions"])]
    assert len(completion_calls) == 3  # the fourth finish is admitted without another review


def test_low_confidence_is_advisory_and_finish_is_admitted(tmp_path: Path) -> None:
    judge = FakeJudge(lambda n, cid: ("none", 0.5))
    result, *_ = run_scenario(tmp_path, judge)
    assert result.status == "submitted"
    ev = events(tmp_path)
    assert not [e for e in ev if e["event"] == "action" and e["kind"] == "hold_finish"]
    assert any(e["event"] == "action" and e["kind"] == "advisory_only" for e in ev)


def test_judge_failure_degrades_to_control(tmp_path: Path) -> None:
    judge = FakeJudge(all_direct, fail=True)
    result, hooks, card_log, _, executor = run_scenario(tmp_path, judge)
    assert result.status == "submitted"
    ev = events(tmp_path)
    degraded = [e for e in ev if e["event"] == "degraded"]
    assert {d["where"] for d in degraded} == {"T1", "T4"} and degraded[0]["error_type"] == "TimeoutError"
    assert executor.read_file("src/parser.py") == "x.split(',')"  # the write proceeded
    assert CHECK_CMD not in executor.command_history
    assert not any("claim_ledger_feedback" in _packet(r) for r in hooks.requests)


def test_control_arm_has_no_extra_turns_ledger_or_context(tmp_path: Path) -> None:
    result_none, hooks_none, card_log, controller, _ = run_scenario(tmp_path, None)
    result_def, hooks_def, *_ = run_scenario(tmp_path / "again", None)
    assert controller is None and card_log == []
    assert not (tmp_path / "challenger").exists()
    assert result_none.status == result_def.status
    scrub = lambda reqs: re.sub(r'((?:elapsed|remaining)_run_sec\\*"\s*:\s*)[0-9.]+', r'\g<1>0', json.dumps(reqs))  # wall-clock fields
    assert scrub(hooks_none.requests) == scrub(hooks_def.requests)
    assert not any("claim_ledger_feedback" in _packet(r) for r in hooks_none.requests)
    assert not any(r.kind.startswith("challenger_") or "challenger" in r.receipt_id for r in result_none.receipts)
    assert "challenger_card_turns" not in (result_none.accounting or {})
    assert ThinLoopConfig().claim_ledger_controller is None


def test_decide_finish_table_is_falsifiable() -> None:
    crit = (Criterion("C1", "one"), Criterion("C2", "two"))

    def answers(a, b):
        return {f"completeness:C{i}": QuestionAnswer(f"completeness:C{i}", c, p)
                for i, (c, p) in enumerate((a, b), 1)}

    d = decide_finish(crit, answers(("direct_and_current", .95), ("contradicted", .9)), 0.9)
    assert d.kind == ActionKind.HOLD_FINISH and d.held == ("C2",)
    assert decide_finish(crit, answers(("direct_and_current", .95), ("none", .89)), 0.9).kind == ActionKind.ADVISORY_ONLY
    assert decide_finish(crit, answers(("direct_and_current", .95), ("indirect", .99)), 0.9).kind == ActionKind.ADVISORY_ONLY
    assert decide_finish(crit, answers(("direct_and_current", .95), ("direct_and_current", .9)), 0.9).kind == ActionKind.ADMIT_FINISH


def test_invalid_diagnosis_card_degrades_and_the_write_proceeds(tmp_path: Path) -> None:
    inner = make_card_model([])
    judge = FakeJudge(all_direct)
    result, hooks, _, _, executor = run_scenario(
        tmp_path, judge, card_model=lambda m: "no json here" if "diagnosis card" in m[-1]["content"] else inner(m))
    assert result.status == "submitted"
    ev = events(tmp_path)
    assert [e["where"] for e in ev if e["event"] == "degraded"] == ["T1"]
    assert executor.read_file("src/parser.py") == "x.split(',')"
    assert not any("claim_ledger_feedback" in _packet(r) for r in hooks.requests)
    assert not [r for r in judge.requests if any(q.startswith(("hypothesis_rank", "separating_check")) for q in r["questions"])]


def test_mutating_diagnostic_check_is_not_run_and_says_so(tmp_path: Path) -> None:
    inner = make_card_model([])

    def card(messages):
        text = inner(messages)
        return text.replace(CHECK_CMD, "echo patched > src/parser.py") if "symptom" in text else text

    result, hooks, _, _, executor = run_scenario(tmp_path, FakeJudge(all_direct), card_model=card)
    assert "echo patched > src/parser.py" not in executor.command_history
    fb = _packet(hooks.requests[2])["claim_ledger_feedback"]["text"]
    assert "not run: the command is not read-only" in fb
    assert not any(i.endswith(":cmd") and ":challenger-check-" in i for i in (r.receipt_id for r in result.receipts))


STRIP_CMD = "grep -n strip src/parser.py"


def _t1_feedback(tmp_path: Path, judge: FakeJudge):
    result, hooks, _, _, executor = run_scenario(tmp_path, judge)
    ev = events(tmp_path)
    action = next(e for e in ev if e["event"] == "action" and e["card_id"].startswith("diagnosis"))
    return action, _packet(hooks.requests[2]).get("claim_ledger_feedback", {}).get("text", ""), executor


def test_tied_probabilities_still_run_the_separating_check(tmp_path: Path) -> None:
    # The live failure: near-ties used to force advisory. Only the separating_check answer matters here.
    action, fb, executor = _t1_feedback(tmp_path, FakeJudge(all_direct, rank={"H1": 0.4, "H2": 0.4}, separating=("H2", 0.59)))
    assert action["kind"] == "run_check" and action["check_id"].endswith(":H2")
    assert STRIP_CMD in executor.command_history and CHECK_CMD not in executor.command_history
    assert "(probability 0.40)" in fb and STRIP_CMD in fb


def test_unconfident_separating_check_falls_back_to_the_top_hypothesis(tmp_path: Path) -> None:
    action, fb, executor = _t1_feedback(tmp_path, FakeJudge(all_direct, rank={"H1": 0.3, "H2": 0.7}, separating=("H1", 0.49)))
    assert action["kind"] == "run_check" and action["check_id"].endswith(":H2")
    assert STRIP_CMD in executor.command_history and CHECK_CMD not in executor.command_history


def test_advisory_only_when_nothing_reaches_the_floor(tmp_path: Path) -> None:
    action, fb, executor = _t1_feedback(tmp_path, FakeJudge(all_direct, rank={"H1": 0.45, "H2": 0.45}, separating=("H1", 0.49)))
    assert action["kind"] == "advisory_only"
    assert CHECK_CMD not in executor.command_history and STRIP_CMD not in executor.command_history
    assert "1. H1 (probability 0.45)" in fb and "advisory only" in fb


# ---- card repair, normalization, cycle bound -------------------------------------------------

def _diag_json(check: Any) -> str:
    return json.dumps({"symptom": "s", "hypotheses": [
        {"id": "H1", "statement": "a", "status": "considered", "check": check},
        {"id": "H2", "statement": "b", "status": "considered", "check": {"description": "d", "command": "grep -n strip src/parser.py"}}]})


def _scripted_cards(first_diag: str, second_diag: str | None = None, *, first_completion: str | None = None,
                    second_completion: str | None = None):
    inner = make_card_model([])
    seen: list[list[dict[str, str]]] = []
    queue = {"diagnosis": [first_diag, second_diag], "completion": [first_completion, second_completion]}

    def model(messages):
        seen.append(messages)
        last = messages[-1]["content"]
        kind = "diagnosis" if any("write a diagnosis card" in m["content"] for m in messages[-3:]) else "completion"
        pick = queue[kind].pop(0) if queue[kind] else None
        return pick if pick is not None else inner(messages)

    return model, seen


def test_card_error_gets_exactly_one_repair_turn_with_error_and_schema(tmp_path: Path) -> None:
    good = _diag_json({"description": "d", "command": CHECK_CMD})
    model, seen = _scripted_cards('{"symptom": "s", "hypotheses": [ {"id": "H1",', good)
    result, hooks, _, _, executor = run_scenario(tmp_path, FakeJudge(all_direct), card_model=model)
    ev = events(tmp_path)
    repair = next(m for m in seen if "could not be used" in m[-1]["content"])
    assert "card JSON is invalid" in repair[-1]["content"] and '"hypotheses"' in repair[-1]["content"]
    assert repair[-2]["role"] == "assistant" and repair[-2]["content"].startswith('{"symptom"')
    assert [e["event"] for e in ev if e["event"] in ("card_invalid", "card_response")][:3] == ["card_response", "card_invalid", "card_response"]
    assert not [e for e in ev if e["event"] == "degraded" and e["where"] == "T1"]
    assert CHECK_CMD in executor.command_history  # the corrected card drove the check


def test_second_card_failure_degrades_after_only_one_repair(tmp_path: Path) -> None:
    model, seen = _scripted_cards("not json", "still not json")
    result, hooks, _, _, executor = run_scenario(tmp_path, FakeJudge(all_direct), card_model=model)
    ev = events(tmp_path)
    assert sum(1 for m in seen if "could not be used" in m[-1]["content"]) == 1
    assert [e["where"] for e in ev if e["event"] == "degraded"] == ["T1"]
    assert result.status == "submitted" and executor.read_file("src/parser.py") == "x.split(',')"


@pytest.mark.parametrize("check", ["grep -n split src/parser.py", {"command": "grep -n split src/parser.py"}])
def test_tolerant_check_forms_need_no_repair(tmp_path: Path, check: Any) -> None:
    model, seen = _scripted_cards(_diag_json(check))
    run_scenario(tmp_path, FakeJudge(all_direct), card_model=model)
    assert not any("could not be used" in m[-1]["content"] for m in seen)
    card = next(e for e in events(tmp_path) if e["event"] == "card" and e["card"] == "diagnosis")
    assert card["hypotheses"][0]["check"] == CHECK_CMD


def test_json_extracted_from_fenced_or_prose_responses() -> None:
    from aether.challenger_runtime.cards import CardError, extract_json, parse_diagnosis
    body = _diag_json("echo ok")
    assert extract_json(f"Here is the card:\n```json\n{body}\n```\nDone {{not json}}")["symptom"] == "s"
    assert extract_json("note {oops} then " + body)["symptom"] == "s"
    card = parse_diagnosis(f"```\n{body}\n```", card_id="c", trigger_id="t")
    assert card.hypotheses[0].discriminating_check.description == "check"
    with pytest.raises(CardError, match="non-empty command"):
        parse_diagnosis(_diag_json({"description": "only a description"}), card_id="c", trigger_id="t")
    with pytest.raises(CardError, match="card JSON is invalid"):
        extract_json('{"a": [1, 2 3]}')


def test_completion_card_repair_and_string_check(tmp_path: Path) -> None:
    ref = "step-3:verify:cmd"
    bad = json.dumps({"criteria": [{"id": "C1", "text": "t", "evidence_refs": [ref], "check": {"description": "d"}}]})
    fixed = json.dumps({"criteria": [{"id": "C1", "text": "t", "evidence_refs": [ref], "check": "echo ok"},
                                     {"id": "C2", "text": "u", "evidence_refs": [], "check": "echo ok"}]})
    model, seen = _scripted_cards(_diag_json("echo ok"), None, first_completion=bad, second_completion=fixed)
    run_scenario(tmp_path, FakeJudge(all_direct), card_model=model)
    ev = events(tmp_path)
    invalid = [e for e in ev if e["event"] == "card_invalid"]
    assert invalid and "needs a non-empty command" in invalid[0]["error"]
    assert any("could not be used" in m[-1]["content"] and "criteria" in m[-1]["content"] for m in seen)
    assert any(e["event"] == "card" and e["card"] == "completion" for e in ev)  # repaired card accepted


def test_cycle_bound_admits_finish_instead_of_raising(tmp_path: Path) -> None:
    # Non-holding reviews (advisory) consume ledger cycles too; the controller must admit at the bound, never raise.
    judge = FakeJudge(lambda n, cid: ("indirect", 0.99))
    result, hooks, card_log, controller, _ = run_scenario(tmp_path, judge, finishes=8, max_steps=60)
    ev = events(tmp_path)
    assert not [e for e in ev if e["event"] == "degraded"]
    assert result.status == "submitted"
    # Force the bound directly: after exhausting cycles a finish attempt is admitted without a card turn.
    controller.ledger.verify_repair_cycles = controller.ledger.max_cycles
    before = len(card_log)
    assert controller.on_finish_attempt(SolverTurn(kind="finish_intent", summary="x", claim="c", evidence_refs=("e",)),
                                        messages=[], step=99) is False
    assert len(card_log) == before
    assert events(tmp_path)[-1]["reason"] == "verify/repair cycle bound reached"

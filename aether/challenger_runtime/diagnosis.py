"""T1: diagnosis card at the first production write, JUDGE ranking, one separating check."""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence

from ..challenger_claim_ledger import (
    ActionContext, ActionKind, CheckResult, QuestionnaireContext, QuestionnaireRunner,
    build_questions, choose_action, execute_action,
)
from ..challenger_claim_policy import hypothesis_ranking
from ..challenger_claim_types import Criterion, DiagnosisCard, MAX_CHECK_OUTPUT_CHARS, MechanicalFacts, RunnableCheck
from ..runtime_ir import ActionRequest, SolverTurn
from ..kernel_turns import run_act_turn
from ..persistent_capabilities import persistent_capability_contract
from .card_turn import obtain_card
from .cards import DIAGNOSIS_PROMPT, DIAGNOSIS_SCHEMA, SYMPTOM_CRITERION_ID, parse_diagnosis
from .config import DIAGNOSIS_CONFIDENCE_FLOOR
from .evidence import looks_mutating
from .state import FlowContext

OUTPUT_FEEDBACK_CHARS = 600


def pending_description(turn: SolverTurn) -> str:
    action = turn.actions[0]
    args = {k: (str(v)[:200]) for k, v in action.arguments.items() if k != "content"}
    return f"{action.kind} {args} (reason: {turn.summary[:300]})"


def run_diagnosis(
    fc: FlowContext, turn: SolverTurn, *, messages: Sequence[Mapping[str, Any]],
    step: int, envmap: Any, trigger_id: str, refresh: str = "",
) -> tuple[dict[str, Any] | None, Any]:
    """Return (feedback or None, refreshed envmap or None). Raises only on infra errors the caller degrades."""
    binding = fc.binding
    assert binding is not None
    prompt = DIAGNOSIS_PROMPT.format(pending=pending_description(turn))
    if refresh:
        prompt = (f"A progress review found that your recent actions have not materially advanced the task ({refresh}). "
                  "Write a refreshed diagnosis card.\n") + prompt
    binding.exec_ledger.record_accounting(
        receipt_id=f"step-{step}:challenger_card_turn:diagnosis", step=step,
        counter="challenger_card_turns", event="diagnosis_card",
    )
    card = obtain_card(fc, messages, prompt, "Your refreshed diagnosis card" if refresh else "Your diagnosis card", DIAGNOSIS_SCHEMA,
                       lambda text: parse_diagnosis(text, card_id=f"diagnosis:{step}", trigger_id=trigger_id))
    fc.ledger.record_card(card)
    fc.log.append("card", card="diagnosis", card_id=card.card_id, symptom=card.symptom,
                  hypotheses=[{"id": h.hypothesis_id, "statement": h.statement,
                               "disposition": h.disposition, "check": h.discriminating_check.command}
                              for h in card.hypotheses])
    criteria = (Criterion(SYMPTOM_CRITERION_ID, card.symptom),)
    checks = {h.discriminating_check.check_id: h.discriminating_check for h in card.hypotheses}
    context = QuestionnaireContext(criteria, {})
    questions = build_questions(card, context, checks)
    cycle = fc.ledger.begin_verify_repair_cycle()
    fc.log.append("judge_question", card_id=card.card_id, cycle=cycle,
                  questions={q.question_id: q.to_dict() for q in questions})
    round_ = QuestionnaireRunner().ask_in_cycle(fc.ledger, cycle, card, context, questions, fc.evaluator)
    fc.log.append("judge_answer", card_id=card.card_id, cycle=cycle,
                  answers={k: {"choice": a.choice, "confidence": a.confidence, "probabilities": dict(a.probabilities)}
                           for k, a in round_.answers.items()})
    decision = choose_action(ActionContext(
        card, criteria, checks, round_.answers, MechanicalFacts(),
        confidence_threshold=DIAGNOSIS_CONFIDENCE_FLOOR,
    ))
    fc.log.append("action", card_id=card.card_id, kind=decision.kind.value, reason=decision.reason,
                  check_id=decision.check_id)
    holder: dict[str, Any] = {"envmap": None}

    def runner(check: RunnableCheck) -> CheckResult:
        result, refreshed = _run_check(fc, check, step=step, envmap=envmap, cycle=cycle)
        holder["envmap"] = refreshed
        return result

    result = execute_action(fc.ledger, decision, checks=checks, check_runner=runner)
    feedback = render_diagnosis_feedback(card, round_.answers, decision.kind, result, checks, fc)
    if refresh:
        feedback = {**feedback, "kind": "diagnosis_refresh",
                    "text": f"Progress review: {refresh}.\n" + feedback["text"],
                    "note": feedback["note"].replace("CHALLENGER diagnosis review", "CHALLENGER diagnosis refresh", 1)}
    fc.log.append("feedback", kind=feedback["kind"], text=feedback["text"])
    return feedback, holder["envmap"]


def _run_check(fc: FlowContext, check: RunnableCheck, *, step: int, envmap: Any, cycle: int):
    b = fc.binding
    ref = f"challenger:{check.check_id}:not_run"

    def not_run(why: str) -> tuple[CheckResult, Any]:
        return CheckResult(check.check_id, cycle, False, None, ref,
                           sha256(why.encode()).hexdigest(), why), None

    if looks_mutating(check.command):
        return not_run("not run: the command is not read-only")
    contract = persistent_capability_contract(b.compiled, runtime_capability_ids=tuple(
        getattr(b.exec_ledger, "runtime_capabilities", set()) or ()))
    caps = contract.get("run_command", ())
    if not caps:
        return not_run("not run: no command capability is available")
    action_id = f"challenger-check-{cycle}"
    check_turn = SolverTurn(kind="act", summary=f"Diagnosis check {check.check_id}: {check.description}"[:300],
        actions=(ActionRequest(
            action_id=action_id, kind="run_command", capability_id=caps[0],
            arguments={"command": check.command},
            intent=f"discriminating check: {check.description}"[:300],
            expected_observation="command output separating the top hypotheses",
            if_fail_next="report the failure; the pending action proceeds"),))
    refreshed = run_act_turn(b.kernel, check_turn, step, b.compiled, b.executor, envmap,
                             b.exec_ledger, b.world_state)
    receipt_id = f"step-{step}:{action_id}:cmd"
    receipt = next((r for r in b.exec_ledger.all_receipts() if r.receipt_id == receipt_id), None)
    if receipt is None:
        return not_run("not run: the ordinary action path refused the command"), refreshed
    payload = receipt.payload or {}
    excerpt = (str(payload.get("stdout") or "") + str(payload.get("stderr") or ""))[:MAX_CHECK_OUTPUT_CHARS]
    exit_code = payload.get("exit_code")
    return CheckResult(check.check_id, cycle, True, int(exit_code if exit_code is not None else -1),
                       receipt_id, sha256(excerpt.encode()).hexdigest(), excerpt), refreshed


def render_diagnosis_feedback(card: DiagnosisCard, answers, kind: ActionKind,
                              result: CheckResult | None, checks, fc: FlowContext) -> dict[str, Any]:
    ranked = [(i, p, h) for i, (h, p) in enumerate(hypothesis_ranking(card, answers), 1)]
    lines = ["Diagnosis review of your card against the symptom you stated (ranked by probability of best explaining it):"]
    lines += [f"  {rank}. {h.hypothesis_id} (probability {conf:.2f}): {h.statement}" for rank, conf, h in ranked]
    if result is None:
        lines.append("No check was run: the review was not confident in a separating check or a top hypothesis (advisory only).")
    else:
        check = checks[result.check_id]
        lines.append(f"Check chosen to separate the leading hypotheses ({check.check_id}): {check.description}")
        lines.append(f"Command run by Aether before your pending action: {check.command}")
        if result.ran:
            lines.append(f"Result: exit_code={result.exit_code}; evidence {result.evidence_ref}")
            lines.append("Output (excerpt): " + result.output_excerpt[:OUTPUT_FEEDBACK_CHARS])
        else:
            lines.append(f"Result: {result.output_excerpt}")
    lines.append("Your pending action then ran unchanged. Revisit it if this review bears on your diagnosis.")
    order = ">".join(h.hypothesis_id for _, _, h in ranked)
    if result is None:
        brief = "no check selected"
    elif result.ran:
        brief = (f"check `{checks[result.check_id].command[:90]}` exit_code={result.exit_code} "
                 f"({result.evidence_ref}): {' '.join(result.output_excerpt.split())[:110]}")
    else:
        brief = f"check not run ({result.output_excerpt})"
    return {"schema": "aether.challenger.feedback.v1", "kind": "diagnosis", "text": "\n".join(lines),
            "note": f"CHALLENGER diagnosis review: ranking {order}; {brief}"}

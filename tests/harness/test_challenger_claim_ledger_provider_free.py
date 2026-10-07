from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from aether.challenger_claim_ledger import (
    ActionContext,
    ActionDecision,
    ActionKind,
    ActionObservation,
    CheckKind,
    CheckOrigin,
    CheckResult,
    CompletionCard,
    Criterion,
    CriterionClaim,
    DiagnosisCard,
    FileWrite,
    Hypothesis,
    LedgerIdentity,
    MechanicalFacts,
    ProgressClaimCard,
    QuestionAnswer,
    QuestionnaireContext,
    QuestionnaireRunner,
    RepairCycleLimitError,
    RunnableCheck,
    TaskLocalClaimLedger,
    TaskLocalLedgerStore,
    TriggerKind,
    build_followup_check_questions,
    build_followup_result_questions,
    choose_action,
    execute_action,
    render_feedback,
)


def _identity(run_id: str = "provider-free-challenger") -> LedgerIdentity:
    return LedgerIdentity(run_id, sha256(b"synthetic public task prompt").hexdigest())


def _check(check_id: str = "check-a", *, criterion_id: str = "c1") -> RunnableCheck:
    return RunnableCheck(
        check_id=check_id,
        criterion_id=criterion_id,
        description=f"Inspect synthetic criterion {criterion_id}",
        command=f"inspect {criterion_id}",
        origin=CheckOrigin.GLM,
        kind=CheckKind.READ_ONLY_INSPECTION,
    )


def _complete_answers(questions: dict[str, dict]) -> dict[str, dict]:
    selected: dict[str, dict] = {}
    for key, question in questions.items():
        dimension = question["dimension"]
        choices = question["choices"]
        if dimension == "completeness":
            choice = "direct_and_current"
        elif dimension == "check_exercises_requirement":
            choice = "fully"
        elif dimension == "check_independence":
            choice = "independent"
        elif dimension == "check_result_implies_requirement":
            choice = "yes"
        elif dimension == "hypothesis_rank":
            choice = choices[0]
        elif dimension == "separating_check":
            choice = choices[0]
        elif dimension == "followup_check":
            choice = choices[0]
        else:
            choice = choices[0]
        selected[key] = {
            "choice": choice,
            "probabilities": {choice: 0.98},
            "evidence_refs": list(question.get("evidence_refs", ())),
        }
    return selected


def _completion_fixture(trigger_id: str = "trigger:1:finish_intent") -> tuple[CompletionCard, QuestionnaireContext, dict[str, RunnableCheck]]:
    check = _check()
    card = CompletionCard(
        card_id="completion-1",
        trigger_id=trigger_id,
        claims=(CriterionClaim("c1", ("ev:artifact",), (check.check_id,)),),
    )
    context = QuestionnaireContext(
        criteria=(Criterion("c1", "The synthetic artifact contains the required value."),),
        evidence_views={"ev:artifact": "Synthetic observed artifact value: expected."},
    )
    return card, context, {check.check_id: check}


def test_challenger_vertical_behavior_triggers_questionnaire_action_table_and_executor(tmp_path: Path) -> None:
    ledger = TaskLocalClaimLedger(
        _identity(), no_change_actions=2, material_action_interval=2,
    )
    first = ledger.observe_action(ActionObservation(
        "a1", True, "state-0", material=True,
        writes=(FileWrite("scratch.tmp", is_scratch=True),),
        repeat_signature="read:scratch.tmp",
    ))
    second = ledger.observe_action(ActionObservation(
        "a2", True, "state-0", material=True,
        writes=(FileWrite("artifact.txt", is_scratch=False),),
        repeat_signature="read:scratch.tmp",
    ))
    third = ledger.observe_action(ActionObservation(
        "a3", True, "state-0", unexpected_failure=True, finish_intent=True,
        repeat_signature="read:scratch.tmp",
    ))
    trigger_kinds = {item.kind for item in (*first, *second, *third)}
    assert trigger_kinds == set(TriggerKind)
    assert any(item.kind == TriggerKind.STUCK_OR_CONTRADICTED and "no_task_state_change_threshold" in item.reasons for item in third)

    t1 = next(item for item in (*first, *second, *third) if item.kind == TriggerKind.FIRST_PRODUCTION_WRITE)
    t3 = next(item for item in (*first, *second, *third) if item.kind == TriggerKind.PROGRESS_MILESTONE)
    check_a = _check("check-a")
    check_b = _check("check-b")
    ledger.record_card(DiagnosisCard(
        "diagnosis-first-write", t1.trigger_id, "A production file was first written.",
        (
            Hypothesis("write-visible", "The output is visible.", "considered", check_a),
            Hypothesis("write-stale", "The output is stale.", "dismissed", check_b),
        ),
    ))
    ledger.record_card(ProgressClaimCard(
        "progress-milestone", t3.trigger_id, "c1", "The artifact changed.", ("ev:artifact",),
    ))
    contradiction = ledger.observe_action(ActionObservation(
        "a4", True, "state-0", contradicted_claim_ids=("progress-milestone",),
    ))
    assert any(
        item.kind == TriggerKind.STUCK_OR_CONTRADICTED and "claim_contradicted" in item.reasons
        for item in contradiction
    )

    finish_trigger = next(item for item in (*first, *second, *third) if item.kind == TriggerKind.FINISH_INTENT)
    card, context, checks = _completion_fixture(finish_trigger.trigger_id)
    ledger.record_card(card)

    check = checks["check-a"]
    check_result = CheckResult(
        check_id=check.check_id,
        cycle=1,
        ran=True,
        exit_code=0,
        evidence_ref="ev:check-result",
        result_sha256=sha256(b"synthetic check result").hexdigest(),
        output_excerpt="Synthetic check passed.",
    )
    facts = MechanicalFacts(
        check_results=(check_result,),
        changed_files=("artifact.txt",),
        previously_passing_checks={"baseline": True},
        previous_checks_snapshot_complete=True,
    )

    # The injected evaluator is a deterministic provider-free fixture. The
    # questionnaire state contains only the synthetic public criterion and
    # visible evidence supplied above.
    def evaluator(state, questions):
        assert "task_prompt" not in state
        assert "hidden_tests" not in state and "hidden_truth" not in state
        return _complete_answers(dict(questions))

    round_ = QuestionnaireRunner().begin_and_ask(
        ledger, card=card, context=context, checks=checks, evaluator=evaluator,
    )
    assert len(round_.questions) == 4
    assert len(round_.answers) == 4
    ledger.record_check_result(check_result)
    decision = choose_action(ActionContext(
        card=card, criteria=context.criteria, checks=checks,
        answers=round_.answers, mechanical_facts=facts,
    ))
    assert decision.kind == ActionKind.ADMIT_FINISH
    assert render_feedback(decision) == ""
    execute_action(ledger, decision)
    assert ledger.action_receipts[-1]["action"] == ActionKind.ADMIT_FINISH.value

    # The same action table fails closed on a confident missing criterion.
    missing_answers = dict(round_.answers)
    missing_answers["completeness:c1"] = type(round_.answers["completeness:c1"])(
        "completeness:c1", "none", 0.99, ("ev:artifact",),
    )
    hold = choose_action(ActionContext(
        card=card, criteria=context.criteria, checks=checks,
        answers=missing_answers, mechanical_facts=facts,
    ))
    assert hold.kind == ActionKind.HOLD_FINISH
    assert "Criterion c1 (The synthetic artifact contains the required value.) is not established" in render_feedback(hold)
    execute_action(ledger, hold)

    # T2 refreshes a diagnosis; independent typed ranking selects a bounded
    # check which Aether executes through the injected read-only runner.
    stuck_trigger = next(item for item in (*second, *third) if item.kind == TriggerKind.STUCK_OR_CONTRADICTED)
    check_b = _check("check-b")
    diagnosis = DiagnosisCard(
        "diagnosis-1", stuck_trigger.trigger_id, "No visible state change.",
        (
            Hypothesis("h1", "The write path is wrong.", "considered", check),
            Hypothesis("h2", "The artifact is present but stale.", "dismissed", check_b),
        ),
    )
    ledger.record_card(diagnosis)
    diag_context = QuestionnaireContext(context.criteria, context.evidence_views)
    diag_checks = {check.check_id: check, check_b.check_id: check_b}
    diag_round = QuestionnaireRunner().begin_and_ask(
        ledger, card=diagnosis, context=diag_context, checks=diag_checks,
        evaluator=lambda state, questions: _complete_answers(dict(questions)),
    )
    run_decision = choose_action(ActionContext(
        card=diagnosis, criteria=diag_context.criteria, checks=diag_checks,
        answers=diag_round.answers, mechanical_facts=MechanicalFacts(),
    ))
    assert run_decision.kind == ActionKind.RUN_CHECK
    assert run_decision.check_id == "check-a"
    executed: list[str] = []

    def run_check(selected: RunnableCheck) -> CheckResult:
        executed.append(selected.check_id)
        return CheckResult(
            selected.check_id, ledger.verify_repair_cycles, True, 0,
            "ev:diagnostic", sha256(b"diagnostic output").hexdigest(), "observed",
        )

    result = execute_action(ledger, run_decision, checks=diag_checks, check_runner=run_check)
    assert executed == ["check-a"]
    assert result is not None and ledger.check_results[-1] == result
    assert "Check check-a completed" in render_feedback(run_decision, check_result=result)

    # Persist/reopen within the same run, and fail closed on cross-task reuse.
    store = TaskLocalLedgerStore(tmp_path / "private-run-state")
    store.save(ledger)
    restored = store.load_or_create(_identity())
    assert restored.verify_repair_cycles == 2
    assert len(restored.cards) == 4
    with pytest.raises(ValueError, match="different task/run"):
        store.load_or_create(_identity("another-run"))
    with pytest.raises(ValueError, match="overwrite"):
        store.save(TaskLocalClaimLedger(_identity("another-run")))


def test_bounded_action_table_covers_followup_refresh_request_and_advisory() -> None:
    ledger = TaskLocalClaimLedger(_identity())
    trigger = ledger.observe_action(ActionObservation("finish", True, "state", finish_intent=True))[0]
    card, context, checks = _completion_fixture(trigger.trigger_id)
    ledger.record_card(card)
    cycle = ledger.begin_verify_repair_cycle()
    direct = {
        "completeness:c1": _typed_answer("completeness:c1", "direct_and_current"),
        "check_exercises_requirement:c1:check-a": _typed_answer("check_exercises_requirement:c1:check-a", "fully"),
        "check_independence:c1:check-a": _typed_answer("check_independence:c1:check-a", "independent"),
        "check_result_implies_requirement:c1:check-a": _typed_answer("check_result_implies_requirement:c1:check-a", "yes"),
    }
    indirect = dict(direct)
    indirect["completeness:c1"] = _typed_answer("completeness:c1", "indirect")

    request = choose_action(ActionContext(
        card, context.criteria, checks, indirect, MechanicalFacts(), followup_checks=(),
    ))
    assert request.kind == ActionKind.REQUEST_GLM_CHECK
    execute_action(ledger, request)

    followup_check = _check("menu-check")
    followup_context = ActionContext(
        card, context.criteria, checks, indirect, MechanicalFacts(),
        followup_checks=(followup_check,),
    )
    ask = choose_action(followup_context)
    assert ask.kind == ActionKind.ASK_JUDGE_FOLLOWUP
    execute_action(ledger, ask)
    q = build_followup_check_questions(
        indirect, context, (followup_check,),
    )
    assert len(q) == 1 and q[0].choices == ("menu-check",)
    selected = dict(indirect)
    selected["followup_check:c1"] = _typed_answer("followup_check:c1", "menu-check")
    run = choose_action(ActionContext(
        card, context.criteria, checks, selected, MechanicalFacts(),
        followup_checks=(followup_check,),
    ))
    assert run.kind == ActionKind.RUN_CHECK
    execute_action(
        ledger, run, checks={"menu-check": followup_check},
        check_runner=lambda check: CheckResult(
            check.check_id, cycle, True, 0, "ev:menu-check",
            sha256(b"menu check").hexdigest(), "observed",
        ),
    )
    check_result = ledger.check_results[-1]
    followup_context_with_result = QuestionnaireContext(
        context.criteria,
        {**context.evidence_views, check_result.evidence_ref: check_result.output_excerpt},
    )
    result_questions = build_followup_result_questions(
        "c1", "menu-check", (check_result.evidence_ref,), followup_check,
        followup_context_with_result,
    )
    result_round = QuestionnaireRunner().ask_in_cycle(
        ledger, cycle, card, followup_context_with_result, result_questions,
        lambda state, questions: _complete_answers(dict(questions)),
    )
    completed_followup = dict(selected)
    completed_followup.update(result_round.answers)
    admitted = choose_action(ActionContext(
        card, context.criteria, checks, completed_followup,
        MechanicalFacts(
            check_results=(check_result,),
            previously_passing_checks={"baseline": True},
            previous_checks_snapshot_complete=True,
        ),
        followup_checks=(followup_check,),
    ))
    assert admitted.kind == ActionKind.ADMIT_FINISH
    execute_action(ledger, admitted)

    refresh = choose_action(ActionContext(
        ProgressClaimCard("progress-1", "trigger:1:progress_milestone", "c1", "No progress", ("ev:artifact",)),
        context.criteria, checks,
        {"progress:progress-1": _typed_answer("progress:progress-1", "no_material_change")},
        MechanicalFacts(), no_material_change_count=2,
    ))
    assert refresh.kind == ActionKind.REFRESH_DIAGNOSIS
    assert "refreshed typed diagnosis" in render_feedback(refresh)
    execute_action(ledger, refresh)

    low_confidence = dict(direct)
    low_confidence["check_independence:c1:check-a"] = _typed_answer("check_independence:c1:check-a", "independent", 0.65)
    advisory = choose_action(ActionContext(
        card, context.criteria, checks, low_confidence, MechanicalFacts(),
    ))
    assert advisory.kind == ActionKind.ADVISORY_ONLY
    assert "Advisory only" in render_feedback(advisory)
    execute_action(ledger, advisory)

    assert {row["action"] for row in ledger.action_receipts} >= {
        ActionKind.REQUEST_GLM_CHECK.value,
        ActionKind.ASK_JUDGE_FOLLOWUP.value,
        ActionKind.RUN_CHECK.value,
        ActionKind.REFRESH_DIAGNOSIS.value,
        ActionKind.ADVISORY_ONLY.value,
    }


def test_no_change_and_repeat_triggers_are_mechanical_and_cycle_limit_is_three() -> None:
    ledger = TaskLocalClaimLedger(_identity(), no_change_actions=2)
    ledger.observe_action(ActionObservation("a1", True, "same", repeat_signature="s"))
    ledger.observe_action(ActionObservation("a2", True, "same"))
    events = ledger.observe_action(ActionObservation("a3", True, "same", repeat_signature="s"))
    stuck = next(item for item in events if item.kind == TriggerKind.STUCK_OR_CONTRADICTED)
    assert set(stuck.reasons) == {"repeat_signature", "no_task_state_change_threshold"}
    assert [ledger.begin_verify_repair_cycle() for _ in range(3)] == [1, 2, 3]
    with pytest.raises(RepairCycleLimitError):
        ledger.begin_verify_repair_cycle()


def _answer(choice: str, confidence: float = 0.98) -> dict:
    return {"choice": choice, "probabilities": {choice: confidence}}


def _typed_answer(question_id: str, choice: str, confidence: float = 0.98) -> QuestionAnswer:
    return QuestionAnswer(question_id, choice, confidence)

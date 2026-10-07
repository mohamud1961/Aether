"""Deterministic CHALLENGER action policy and bounded action executor."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Mapping

from .challenger_claim_ledger_state import TaskLocalClaimLedger
from .challenger_claim_types import (
    ActionKind,
    CheckResult,
    ClaimCard,
    CompletionCard,
    Criterion,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DIAGNOSIS_MIN_PROBABILITY,
    DiagnosisCard,
    Hypothesis,
    MechanicalFacts,
    ProgressClaimCard,
    QuestionAnswer,
    QuestionDimension,
    RunnableCheck,
)


@dataclass(frozen=True)
class ActionDecision:
    kind: ActionKind
    reason: str
    criterion_id: str = ""
    check_id: str = ""
    evidence_refs: tuple[str, ...] = ()
    confidence: float | None = None
    criterion_text: str = ""
    _policy_seal: object | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class ActionContext:
    card: ClaimCard
    criteria: tuple[Criterion, ...]
    checks: Mapping[str, RunnableCheck]
    answers: Mapping[str, QuestionAnswer]
    mechanical_facts: MechanicalFacts
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    no_material_change_count: int = 0
    diagnosis_refreshed: bool = False
    followup_checks: tuple[RunnableCheck, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence_threshold <= 1.0:
            raise ValueError("confidence threshold must be in (0, 1]")
        if self.no_material_change_count < 0:
            raise ValueError("no_material_change_count cannot be negative")


_ACTION_POLICY_SEAL = object()


def choose_action(context: ActionContext) -> ActionDecision:
    """Return a policy-issued decision suitable for the bounded executor."""
    return replace(_choose_action_impl(context), _policy_seal=_ACTION_POLICY_SEAL)


def _choose_action_impl(context: ActionContext) -> ActionDecision:
    """Deterministic action table. JUDGE answers never overwrite mechanical facts."""
    threshold = context.confidence_threshold
    criteria = {item.criterion_id: item for item in context.criteria}
    answers = context.answers

    for criterion_id in sorted(criteria):
        answer = answers.get(f"completeness:{criterion_id}")
        if answer and answer.confidence >= threshold and answer.choice in {"none", "contradicted"}:
            refs = _answer_refs(context.card, criterion_id)
            return ActionDecision(
                ActionKind.HOLD_FINISH,
                "high-confidence missing or contradicted criterion evidence",
                criterion_id=criterion_id, evidence_refs=refs, confidence=answer.confidence,
                criterion_text=criteria[criterion_id].text,
            )

    all_answers = tuple(answers.values())
    if all_answers and any(answer.confidence < threshold for answer in all_answers):
        lowest = min(all_answers, key=lambda item: item.confidence)
        return ActionDecision(
            ActionKind.ADVISORY_ONLY,
            "at least one JUDGE answer is below the configured confidence threshold",
            evidence_refs=lowest.evidence_refs, confidence=lowest.confidence,
        )

    if context.no_material_change_count >= 2 and not context.diagnosis_refreshed:
        return ActionDecision(
            ActionKind.REFRESH_DIAGNOSIS,
            "no material task-state change across two accepted actions",
        )

    if isinstance(context.card, DiagnosisCard):
        chosen, why = choose_diagnosis_hypothesis(context.card, answers)
        if chosen is None:
            return ActionDecision(ActionKind.ADVISORY_ONLY, why)
        check = chosen.discriminating_check
        return ActionDecision(
            ActionKind.RUN_CHECK, why,
            criterion_id=check.criterion_id, check_id=check.check_id,
            criterion_text=criteria[check.criterion_id].text,
        )

    if isinstance(context.card, ProgressClaimCard):
        progress = answers.get(f"progress:{context.card.card_id}")
        if progress and progress.choice == "no_material_change" and context.no_material_change_count >= 2:
            return ActionDecision(ActionKind.REFRESH_DIAGNOSIS, "two no-material-change outcomes")

    if isinstance(context.card, CompletionCard):
        claims = {item.criterion_id: item for item in context.card.claims}
        for criterion_id in sorted(criteria):
            completeness = answers.get(f"completeness:{criterion_id}")
            if completeness is None:
                return ActionDecision(ActionKind.ADVISORY_ONLY, f"no completeness answer for {criterion_id}")
            if completeness.choice != "direct_and_current":
                followup = answers.get(f"followup_check:{criterion_id}")
                if followup is None:
                    menu = tuple(item for item in context.followup_checks if item.criterion_id == criterion_id)
                    if menu:
                        return ActionDecision(
                            ActionKind.ASK_JUDGE_FOLLOWUP,
                            "non-direct evidence needs an Aether-menu check selection",
                            criterion_id=criterion_id,
                            evidence_refs=claims[criterion_id].evidence_refs,
                            criterion_text=criteria[criterion_id].text,
                        )
                    return ActionDecision(
                        ActionKind.REQUEST_GLM_CHECK,
                        "non-direct evidence has no existing Aether-menu check",
                        criterion_id=criterion_id,
                        evidence_refs=claims[criterion_id].evidence_refs,
                        criterion_text=criteria[criterion_id].text,
                    )
                check_id = followup.choice
                followup_spec = next((item for item in context.followup_checks if item.check_id == check_id and item.criterion_id == criterion_id), None)
                if followup_spec is None:
                    return ActionDecision(ActionKind.ADVISORY_ONLY, "follow-up check is outside the Aether menu")
                followup_result = context.mechanical_facts.result_for(check_id)
                if followup_result is None:
                    return ActionDecision(
                        ActionKind.RUN_CHECK,
                        "run the Aether-menu check selected by the adaptive follow-up",
                        criterion_id=criterion_id, check_id=check_id,
                        evidence_refs=claims[criterion_id].evidence_refs,
                        criterion_text=criteria[criterion_id].text,
                    )
                if followup_result.exit_code != 0:
                    return ActionDecision(
                        ActionKind.HOLD_FINISH, "Aether-owned follow-up check failed",
                        criterion_id=criterion_id, check_id=check_id,
                        evidence_refs=(followup_result.evidence_ref,),
                        criterion_text=criteria[criterion_id].text,
                    )
                followup_exercises = answers.get(f"followup_check_exercises:{criterion_id}:{check_id}")
                followup_independence = answers.get(f"followup_check_independence:{criterion_id}:{check_id}")
                followup_support = answers.get(f"followup_result:{criterion_id}:{check_id}")
                if not all((followup_exercises, followup_independence, followup_support)):
                    return ActionDecision(
                        ActionKind.ASK_JUDGE_FOLLOWUP,
                        "the selected check ran; its coverage, independence, and result support need typed review",
                        criterion_id=criterion_id, check_id=check_id,
                        evidence_refs=(followup_result.evidence_ref,),
                        criterion_text=criteria[criterion_id].text,
                    )
                if followup_support.choice == "contradicts":
                    return ActionDecision(
                        ActionKind.HOLD_FINISH, "follow-up check result contradicts the criterion",
                        criterion_id=criterion_id, check_id=check_id,
                        evidence_refs=(followup_result.evidence_ref,),
                        confidence=followup_support.confidence,
                        criterion_text=criteria[criterion_id].text,
                    )
                if (followup_exercises.choice != "fully"
                        or followup_independence.choice != "independent"
                        or followup_support.choice != "supports"):
                    candidate = _replacement_check(context, criterion_id, exclude=check_id)
                    if candidate is not None:
                        return ActionDecision(
                            ActionKind.RUN_CHECK,
                            "follow-up check did not fully, independently support the criterion",
                            criterion_id=criterion_id, check_id=candidate.check_id,
                            evidence_refs=(followup_result.evidence_ref,),
                            criterion_text=criteria[criterion_id].text,
                        )
                    return ActionDecision(
                        ActionKind.REQUEST_GLM_CHECK,
                        "follow-up check did not fully, independently support the criterion",
                        criterion_id=criterion_id,
                        evidence_refs=(followup_result.evidence_ref,),
                        criterion_text=criteria[criterion_id].text,
                    )
                # A fresh, fully exercised, independent passing check now
                # directly supports this criterion, so it supersedes the
                # earlier non-direct evidence classification for this cycle.
                continue

            for check_id in claims[criterion_id].check_ids:
                exercise = answers.get(f"{QuestionDimension.CHECK_EXERCISES_REQUIREMENT.value}:{criterion_id}:{check_id}")
                independence = answers.get(f"{QuestionDimension.CHECK_INDEPENDENCE.value}:{criterion_id}:{check_id}")
                implication = answers.get(f"{QuestionDimension.CHECK_RESULT_IMPLIES_REQUIREMENT.value}:{criterion_id}:{check_id}")
                if not all((exercise, independence, implication)):
                    return ActionDecision(ActionKind.ADVISORY_ONLY, "incomplete typed check assessment", criterion_id=criterion_id)
                if exercise.choice != "fully" or independence.choice == "correlated" or implication.choice != "yes":
                    candidate = _replacement_check(context, criterion_id, exclude=check_id)
                    if candidate is not None:
                        return ActionDecision(
                            ActionKind.RUN_CHECK,
                            "existing check misses the requirement because its coverage, independence, or result implication failed; run an independent discriminating check",
                            criterion_id=criterion_id, check_id=candidate.check_id,
                            evidence_refs=claims[criterion_id].evidence_refs,
                            criterion_text=criteria[criterion_id].text,
                        )
                    return ActionDecision(
                        ActionKind.REQUEST_GLM_CHECK,
                        "existing check misses the requirement because its coverage, independence, or result implication failed; request one GLM discriminating check",
                        criterion_id=criterion_id, evidence_refs=claims[criterion_id].evidence_refs,
                        criterion_text=criteria[criterion_id].text,
                    )
                if context.mechanical_facts.result_for(check_id) is None:
                    check = context.checks.get(check_id)
                    if check is not None:
                        return ActionDecision(
                            ActionKind.RUN_CHECK, "Aether has no recorded run for the cited check",
                            criterion_id=criterion_id, check_id=check_id,
                            evidence_refs=claims[criterion_id].evidence_refs,
                            criterion_text=criteria[criterion_id].text,
                        )
                    return ActionDecision(ActionKind.ADVISORY_ONLY, "cited check lacks an Aether-owned run receipt")
                result = context.mechanical_facts.result_for(check_id)
                if result is None or result.exit_code != 0:
                    return ActionDecision(
                        ActionKind.HOLD_FINISH, "Aether-owned check result did not pass",
                        criterion_id=criterion_id, check_id=check_id,
                        evidence_refs=(result.evidence_ref,) if result else (),
                        criterion_text=criteria[criterion_id].text,
                    )

        if not context.mechanical_facts.previous_checks_snapshot_complete:
            return ActionDecision(
                ActionKind.ADVISORY_ONLY,
                "Aether has not supplied a complete prior-check snapshot",
            )
        if not context.mechanical_facts.previous_checks_pass:
            failed = tuple(sorted(key for key, passed in context.mechanical_facts.previously_passing_checks.items() if not passed))
            return ActionDecision(
                ActionKind.HOLD_FINISH, "a previously passing check regressed",
                check_id=failed[0] if failed else "",
            )
        return ActionDecision(
            ActionKind.ADMIT_FINISH,
            "all criteria are direct/current and supported by independent passing checks",
        )

    return ActionDecision(ActionKind.ADVISORY_ONLY, "no bounded action rule matched")


def hypothesis_ranking(card: DiagnosisCard, answers: Mapping[str, QuestionAnswer]) -> list[tuple[Hypothesis, float]]:
    """Hypotheses by JUDGE probability, highest first; ties keep card order. Empty if unanswered."""
    answer = answers.get(f"hypothesis_rank:{card.card_id}")
    if answer is None:
        return []
    probs = dict(answer.probabilities) or {answer.choice: answer.confidence}
    rows = [(h, float(probs.get(h.hypothesis_id, 0.0))) for h in card.hypotheses]
    return sorted(rows, key=lambda row: -row[1])


def choose_diagnosis_hypothesis(
    card: DiagnosisCard, answers: Mapping[str, QuestionAnswer],
) -> tuple[Hypothesis | None, str]:
    """Check to run: the separating-check answer if confident, else the top hypothesis if confident.

    Ties never force advisory: only low probabilities do.
    """
    by_id = {h.hypothesis_id: h for h in card.hypotheses}
    selected = answers.get(f"separating_check:{card.card_id}")
    if selected is not None and selected.choice in by_id and selected.confidence >= DIAGNOSIS_MIN_PROBABILITY:
        return by_id[selected.choice], "run the check JUDGE judged best at separating the top hypotheses"
    ranking = hypothesis_ranking(card, answers)
    if ranking and ranking[0][1] >= DIAGNOSIS_MIN_PROBABILITY:
        return ranking[0][0], "run the check of the top-ranked hypothesis"
    return None, "JUDGE was not confident in a separating check or a top hypothesis"


def render_feedback(decision: ActionDecision, *, check_result: CheckResult | None = None) -> str:
    """Render only the next bounded instruction; admission intentionally emits nothing."""
    if decision.kind == ActionKind.ADMIT_FINISH:
        return ""
    refs = ", ".join(decision.evidence_refs) if decision.evidence_refs else "no cited evidence"
    if decision.kind == ActionKind.HOLD_FINISH:
        target = (
            f"Criterion {decision.criterion_id} ({decision.criterion_text}) is not established"
            if decision.criterion_id else "Finish is held"
        )
        check = f" Run check {decision.check_id}." if decision.check_id else " Rebut with new evidence or request one discriminating check."
        return f"{target}: {decision.reason}; evidence: {refs}.{check}"
    if decision.kind == ActionKind.RUN_CHECK:
        if check_result is None:
            return f"Run the bounded check {decision.check_id} for criterion {decision.criterion_id}; record its output and Aether-owned exit status."
        status = f"exit_code={check_result.exit_code}" if check_result.ran else "not run"
        return f"{decision.reason}. Check {decision.check_id} completed ({status}); evidence {check_result.evidence_ref}. Reassess only this criterion against that result."
    if decision.kind == ActionKind.REQUEST_GLM_CHECK:
        return f"Provide one task-local check for criterion {decision.criterion_id} ({decision.criterion_text}); it must distinguish the cited evidence gap. Current evidence: {refs}. Reason: {decision.reason}."
    if decision.kind == ActionKind.ASK_JUDGE_FOLLOWUP:
        if decision.check_id:
            return f"Assess check {decision.check_id} for criterion {decision.criterion_id} ({decision.criterion_text}): answer coverage, independence, and whether its result supports the criterion. Evidence: {refs}."
        return f"Choose one check from the Aether-provided menu that settles criterion {decision.criterion_id} ({decision.criterion_text}); current evidence: {refs}."
    if decision.kind == ActionKind.REFRESH_DIAGNOSIS:
        return "Write a refreshed typed diagnosis card: state the symptom, list 2–4 considered hypotheses including dismissed ones, and give one discriminating check for each."
    return f"Advisory only: {decision.reason}; confidence={decision.confidence}; evidence: {refs}."


CheckRunner = Callable[[RunnableCheck], CheckResult]


def execute_action(
    ledger: TaskLocalClaimLedger,
    decision: ActionDecision,
    *,
    checks: Mapping[str, RunnableCheck] | None = None,
    check_runner: CheckRunner | None = None,
) -> CheckResult | None:
    """Execute the bounded table action and persist an Aether-side receipt."""
    if ledger.verify_repair_cycles < 1:
        raise ValueError("actions require an open verify/repair cycle")
    if decision._policy_seal is not _ACTION_POLICY_SEAL:
        raise ValueError("executor accepts only decisions issued by the CHALLENGER action table")
    if decision.kind == ActionKind.RUN_CHECK:
        check = (checks or {}).get(decision.check_id)
        if check is None:
            raise ValueError("selected check is not in the task-local check catalog")
        if check_runner is None:
            raise ValueError("a governed check runner is required for RUN_CHECK")
        result = check_runner(check)
        if result.check_id != check.check_id or result.cycle != ledger.verify_repair_cycles:
            raise ValueError("check runner returned a mismatched receipt")
        ledger.record_check_result(result)
        ledger.record_action(decision.kind, check_id=check.check_id, detail=decision.reason)
        return result
    ledger.record_action(decision.kind, check_id=decision.check_id, detail=decision.reason)
    return None


def _replacement_check(context: ActionContext, criterion_id: str, *, exclude: str) -> RunnableCheck | None:
    for check in context.checks.values():
        if check.criterion_id == criterion_id and check.check_id != exclude:
            return check
    for check in context.followup_checks:
        if check.criterion_id == criterion_id and check.check_id != exclude:
            return check
    return None


def _answer_refs(card: ClaimCard, criterion_id: str) -> tuple[str, ...]:
    if isinstance(card, ProgressClaimCard) and card.criterion_id == criterion_id:
        return card.evidence_refs
    if isinstance(card, CompletionCard):
        claim = next((item for item in card.claims if item.criterion_id == criterion_id), None)
        return claim.evidence_refs if claim else ()
    return ()

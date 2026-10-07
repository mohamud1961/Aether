"""Typed CHALLENGER questionnaire construction and evaluator handling."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping, Sequence

from .challenger_claim_ledger_state import TaskLocalClaimLedger, _card_to_dict
from .challenger_claim_types import (
    MAX_CHECK_MENU,
    MAX_EVIDENCE_VIEW_CHARS,
    MAX_EVIDENCE_VIEWS,
    ClaimCard,
    CompletionCard,
    Criterion,
    DiagnosisCard,
    Hypothesis,
    ProgressClaimCard,
    QuestionAnswer,
    QuestionDimension,
    QuestionnaireRound,
    QuestionnaireSchemaError,
    QuestionEvaluator,
    QuestionSpec,
    QUESTIONNAIRE_SCHEMA,
    RunnableCheck,
)


@dataclass(frozen=True)
class QuestionnaireContext:
    criteria: tuple[Criterion, ...]
    evidence_views: Mapping[str, str]

    def __post_init__(self) -> None:
        ids = [item.criterion_id for item in self.criteria]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("questionnaire context needs unique public criteria")
        if any(not ref.strip() or not view.strip() for ref, view in self.evidence_views.items()):
            raise ValueError("evidence views require non-empty refs and bounded views")
        if len(self.evidence_views) > MAX_EVIDENCE_VIEWS:
            raise ValueError("questionnaire context exceeds the evidence reference bound")
        if any(len(view) > MAX_EVIDENCE_VIEW_CHARS for view in self.evidence_views.values()):
            raise ValueError("questionnaire evidence view exceeds the bounded text length")


def build_questions(
    card: ClaimCard,
    context: QuestionnaireContext,
    checks: Mapping[str, RunnableCheck],
) -> tuple[QuestionSpec, ...]:
    criterion_ids = {item.criterion_id for item in context.criteria}
    visible_refs = set(context.evidence_views)
    questions: list[QuestionSpec] = []
    if isinstance(card, ProgressClaimCard):
        _require_criterion(card.criterion_id, criterion_ids)
        refs = _known_refs(card.evidence_refs, visible_refs)
        questions.append(QuestionSpec(
            f"progress:{card.card_id}", QuestionDimension.PROGRESS,
            "Classify the claimed task progress described by these facts.",
            ("advanced_criterion", "no_material_change", "test_only_change", "symptom_moved", "regression"),
            criterion_id=card.criterion_id, evidence_refs=refs,
        ))
        questions.append(QuestionSpec(
            f"active_hypothesis:{card.card_id}", QuestionDimension.ACTIVE_HYPOTHESIS,
            "Classify the active hypothesis against the cited evidence.",
            ("supported", "contradicted", "untested"),
            criterion_id=card.criterion_id, evidence_refs=refs,
        ))
    elif isinstance(card, CompletionCard):
        claims = {claim.criterion_id: claim for claim in card.claims}
        if set(claims) != criterion_ids:
            raise QuestionnaireSchemaError("completion card must cover exactly the raw-task criteria")
        for criterion in context.criteria:
            claim = claims[criterion.criterion_id]
            refs = _known_refs(claim.evidence_refs, visible_refs)
            questions.append(QuestionSpec(
                f"completeness:{criterion.criterion_id}", QuestionDimension.COMPLETENESS,
                f"Classify whether the cited evidence directly and currently establishes criterion {criterion.criterion_id}.",
                ("direct_and_current", "indirect", "self_written_check_only", "none", "contradicted"),
                criterion_id=criterion.criterion_id, evidence_refs=refs,
            ))
            for check_id in claim.check_ids:
                check = checks.get(check_id)
                if check is None or check.criterion_id != criterion.criterion_id:
                    raise QuestionnaireSchemaError("completion card references an unknown or mismatched check")
                for dimension, choices, relation in (
                    (QuestionDimension.CHECK_EXERCISES_REQUIREMENT, ("fully", "partly", "no"), "Does the check exercise this criterion?"),
                    (QuestionDimension.CHECK_INDEPENDENCE, ("independent", "correlated"), "Is this check independent of the claim it evaluates?"),
                    (QuestionDimension.CHECK_RESULT_IMPLIES_REQUIREMENT, ("yes", "no", "unclear"), "Does the observed check result imply this criterion is satisfied?"),
                ):
                    questions.append(QuestionSpec(
                        f"{dimension.value}:{criterion.criterion_id}:{check_id}", dimension,
                        relation, choices, criterion_id=criterion.criterion_id,
                        check_id=check_id, evidence_refs=refs,
                        context_text=f"{check.description}\nCommand: {check.command}",
                    ))
    elif isinstance(card, DiagnosisCard):
        ids = tuple(item.hypothesis_id for item in card.hypotheses)
        questions.append(QuestionSpec(
            f"hypothesis_rank:{card.card_id}", QuestionDimension.HYPOTHESIS_RANK,
            "Which hypothesis best explains the stated symptoms given the evidence so far?", ids,
            choice_details={
                item.hypothesis_id: f"{item.statement} [disposition in the card: {item.disposition}]"
                for item in card.hypotheses
            },
        ))
        for item in card.hypotheses:
            if item.discriminating_check.criterion_id not in criterion_ids:
                raise QuestionnaireSchemaError("diagnosis check references an unknown criterion")
            existing = checks.get(item.discriminating_check.check_id)
            if existing is not None and existing != item.discriminating_check:
                raise QuestionnaireSchemaError("diagnosis check id conflicts with the task-local catalog")
        questions.append(QuestionSpec(
            f"separating_check:{card.card_id}", QuestionDimension.SEPARATING_CHECK,
            "Which hypothesis's check best separates the two most likely hypotheses?", ids,
            choice_details={
                item.hypothesis_id:
                    f"{item.discriminating_check.description}; command: {item.discriminating_check.command}"
                for item in card.hypotheses
            },
        ))
    else:  # pragma: no cover - protected by the ClaimCard union
        raise TypeError("unsupported CHALLENGER claim card")
    return tuple(questions)


def build_followup_check_questions(
    answers: Mapping[str, QuestionAnswer],
    context: QuestionnaireContext,
    check_menu: Sequence[RunnableCheck],
) -> tuple[QuestionSpec, ...]:
    if not check_menu or len(check_menu) > MAX_CHECK_MENU:
        raise ValueError(f"Aether check menu must contain 1 to {MAX_CHECK_MENU} checks")
    criteria = {item.criterion_id for item in context.criteria}
    menu_by_criterion: dict[str, list[RunnableCheck]] = {}
    for check in check_menu:
        _require_criterion(check.criterion_id, criteria)
        menu_by_criterion.setdefault(check.criterion_id, []).append(check)
    questions = []
    for criterion_id in sorted(criteria):
        answer = answers.get(f"completeness:{criterion_id}")
        if answer is None or answer.choice == "direct_and_current":
            continue
        choices = tuple(item.check_id for item in menu_by_criterion.get(criterion_id, ()))
        if choices:
            questions.append(QuestionSpec(
                f"followup_check:{criterion_id}", QuestionDimension.FOLLOWUP_CHECK,
                "Choose the Aether-provided check that settles this criterion.", choices,
                criterion_id=criterion_id,
                choice_details={
                    item.check_id: f"{item.description}; command: {item.command}"
                    for item in menu_by_criterion.get(criterion_id, ())
                },
            ))
    return tuple(questions)


def build_followup_result_questions(
    criterion_id: str,
    check_id: str,
    evidence_refs: Sequence[str],
    check: RunnableCheck,
    context: QuestionnaireContext,
) -> tuple[QuestionSpec, ...]:
    _require_criterion(criterion_id, {item.criterion_id for item in context.criteria})
    if check.criterion_id != criterion_id or check.check_id != check_id:
        raise QuestionnaireSchemaError("follow-up result check does not match its criterion")
    refs = _known_refs(evidence_refs, set(context.evidence_views))
    return (
        QuestionSpec(
            f"followup_check_exercises:{criterion_id}:{check_id}",
            QuestionDimension.CHECK_EXERCISES_REQUIREMENT,
            "Does this check exercise the criterion?",
            ("fully", "partly", "no"), criterion_id=criterion_id,
            check_id=check_id, evidence_refs=refs,
            context_text=f"{check.description}\nCommand: {check.command}",
        ),
        QuestionSpec(
            f"followup_check_independence:{criterion_id}:{check_id}",
            QuestionDimension.CHECK_INDEPENDENCE,
            "Is this check independent of the claim it evaluates?",
            ("independent", "correlated"), criterion_id=criterion_id,
            check_id=check_id, evidence_refs=refs,
            context_text=f"{check.description}\nCommand: {check.command}",
        ),
        QuestionSpec(
            f"followup_result:{criterion_id}:{check_id}", QuestionDimension.FOLLOWUP_RESULT,
            "Does this observed check result support the stated criterion?",
            ("supports", "contradicts", "unclear"),
            criterion_id=criterion_id, check_id=check_id, evidence_refs=refs,
            context_text=f"{check.description}\nCommand: {check.command}",
        ),
    )


class QuestionnaireRunner:
    """Run bounded typed questions through an injected evaluator (provider-agnostic)."""

    def begin_and_ask(
        self,
        ledger: TaskLocalClaimLedger,
        *,
        card: ClaimCard,
        context: QuestionnaireContext,
        checks: Mapping[str, RunnableCheck],
        evaluator: QuestionEvaluator,
    ) -> QuestionnaireRound:
        if not any(existing.card_id == card.card_id for existing in ledger.cards):
            raise ValueError("claim card must be recorded in the task-local ledger before JUDGE review")
        questions = build_questions(card, context, checks)
        cycle = ledger.begin_verify_repair_cycle()
        return self.ask_in_cycle(ledger, cycle, card, context, questions, evaluator)

    def ask_in_cycle(
        self,
        ledger: TaskLocalClaimLedger,
        cycle: int,
        card: ClaimCard,
        context: QuestionnaireContext,
        questions: Sequence[QuestionSpec],
        evaluator: QuestionEvaluator,
    ) -> QuestionnaireRound:
        if cycle != ledger.verify_repair_cycles or cycle < 1:
            raise ValueError("questionnaire must run in the current open verify/repair cycle")
        if not any(existing.card_id == card.card_id for existing in ledger.cards):
            raise ValueError("claim card must be recorded in the task-local ledger before JUDGE review")
        if not questions:
            round_ = QuestionnaireRound(cycle, (), {})
            ledger.record_questionnaire(round_)
            return round_
        state = {
            "schema": QUESTIONNAIRE_SCHEMA,
            "claim_card": _card_to_dict(card),
            "criteria": [asdict(item) for item in context.criteria],
            "visible_evidence": dict(context.evidence_views),
        }
        question_map = {item.question_id: item.to_dict() for item in questions}
        if len(question_map) != len(questions):
            raise QuestionnaireSchemaError("question ids must be unique within a round")
        raw_answers = evaluator(state, question_map)
        if not isinstance(raw_answers, Mapping):
            raise QuestionnaireSchemaError("JUDGE questionnaire response must be an object")
        parsed = _parse_answers(questions, raw_answers, set(context.evidence_views))
        round_ = QuestionnaireRound(cycle, tuple(questions), parsed)
        ledger.record_questionnaire(round_)
        return round_


def _parse_answers(
    questions: Sequence[QuestionSpec],
    raw_answers: Mapping[str, Any],
    known_evidence_refs: set[str],
) -> dict[str, QuestionAnswer]:
    expected = {item.question_id: item for item in questions}
    if set(raw_answers) != set(expected):
        missing = sorted(set(expected) - set(raw_answers))
        extra = sorted(set(raw_answers) - set(expected))
        raise QuestionnaireSchemaError(f"answer ids mismatch; missing={missing}, extra={extra}")
    parsed: dict[str, QuestionAnswer] = {}
    for question_id, question in expected.items():
        raw = raw_answers[question_id]
        if not isinstance(raw, Mapping):
            raise QuestionnaireSchemaError(f"answer {question_id} must be an object")
        choice = str(raw.get("choice") or "")
        if choice not in question.choices:
            raise QuestionnaireSchemaError(f"answer {question_id} chose an undeclared option")
        probabilities = raw.get("probabilities")
        if isinstance(probabilities, Mapping) and choice in probabilities:
            confidence = probabilities[choice]
        else:
            confidence = raw.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise QuestionnaireSchemaError(f"answer {question_id} needs numeric confidence")
        confidence = float(confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise QuestionnaireSchemaError(f"answer {question_id} confidence must be in [0, 1]")
        refs_raw = raw.get("evidence_refs", ())
        if not isinstance(refs_raw, (list, tuple)):
            raise QuestionnaireSchemaError(f"answer {question_id} evidence_refs must be a list")
        refs = tuple(str(item) for item in refs_raw)
        if any(ref not in known_evidence_refs for ref in refs):
            raise QuestionnaireSchemaError(f"answer {question_id} cited an unknown evidence ref")
        probs = {str(k): float(v) for k, v in probabilities.items()
                 if isinstance(v, (int, float)) and not isinstance(v, bool)} if isinstance(probabilities, Mapping) else {}
        parsed[question_id] = QuestionAnswer(question_id, choice, confidence, refs, probs)
    return parsed


def _known_refs(refs: Sequence[str], visible: set[str]) -> tuple[str, ...]:
    cleaned = tuple(dict.fromkeys(str(ref).strip() for ref in refs if str(ref).strip()))
    if any(ref not in visible for ref in cleaned):
        raise QuestionnaireSchemaError("claim card references evidence outside the visible task-local index")
    return cleaned


def _require_criterion(criterion_id: str, known: set[str]) -> None:
    if criterion_id not in known:
        raise QuestionnaireSchemaError(f"unknown public criterion id: {criterion_id}")

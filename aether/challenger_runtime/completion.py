"""T4: completion card at finish intent, JUDGE completeness review, deterministic action table."""
from __future__ import annotations

from dataclasses import dataclass
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from ..challenger_claim_ledger import QuestionnaireContext, QuestionnaireRunner
from ..challenger_claim_types import (
    ActionKind, CompletionCard, Criterion, QuestionAnswer, QuestionDimension, QuestionSpec,
    RunnableCheck,
)
from .artifact_evidence import COMPLETENESS_CHOICES
from .artifact_review import build_artifact_review
from .card_turn import obtain_card
from ..persistent_context import evidence_alias
from .cards import CardError, COMPLETION_PROMPT, COMPLETION_SCHEMA, NO_CHECK_ID, parse_completion
from .evidence import NO_EVIDENCE_REF, command_run_status, evidence_listing, evidence_views, evidence_receipts
from .config import (
    ARTIFACT_MAX_REQUEST_BYTES, EVIDENCE_VARIANT_ARTIFACTS, EVIDENCE_VARIANT_FAILURE_MODE, MAX_HOLD_CYCLES,
)
from .failure_question import BAD_MODES, UNVERIFIED_MODE, FAILURE_DETAILS, FAILURE_QUESTION_ID, failure_question_spec
from .state import FlowContext
from .task_criteria import TASK_SOURCE, merge_task_criteria
from .progress_question import split_criteria
from ..progress_checkpoints import CONTROL, STATE_FINISH_REVIEW, BLIND_FINISH_REVIEW
from .judge_client import _wire_question, _request_bytes
from .progress_question import compact

HOLD_CHOICES = frozenset({"none", "contradicted"})
MAX_HELD_CRITERIA_SHOWN = 3
WEAK_CHOICES = frozenset({"indirect", "self_written_check_only"})
MAX_WEAK_CRITERIA_SHOWN = 6
EVIDENCE_SHOWN_CHARS = 300
STATE_FINISH_CHOICES = ("met_in_observed_state", "partially_met", "not_met", "cannot_tell")
STATE_FINISH_HOLD_THRESHOLD = 0.6
STATE_FINISH_REQUEST_BYTES = 120_000


@dataclass(frozen=True)
class FinishDecision:
    kind: ActionKind  # HOLD_FINISH, ADMIT_FINISH, or ADVISORY_ONLY
    reason: str
    held: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    failure_mode: str = ""  # set only when the failure-mode answer triggered the hold
    failure_confidence: float = 0.0
    strongest: float = 0.0  # highest confidence among all hold signals (none/contradicted/bad mode)


def completeness_questions(card: CompletionCard, criteria: Sequence[Criterion]) -> tuple[QuestionSpec, ...]:
    claims = {c.criterion_id: c for c in card.claims}
    return tuple(QuestionSpec(
        f"completeness:{c.criterion_id}", QuestionDimension.COMPLETENESS,
        f"Classify whether the cited evidence directly and currently establishes criterion {c.criterion_id}.",
        COMPLETENESS_CHOICES, criterion_id=c.criterion_id,
        evidence_refs=claims[c.criterion_id].evidence_refs,
    ) for c in criteria)


def criterion_status_questions(criteria: Sequence[Criterion]) -> tuple[QuestionSpec, ...]:
    return tuple(QuestionSpec(
        f"criterion_status:{c.criterion_id}", QuestionDimension.CRITERION_STATUS,
        f"Using only state.observed_state as a bounded observation window, classify whether criterion {c.criterion_id} is met in the observed workspace state. Do not infer an atomic state at the finish trigger.",
        STATE_FINISH_CHOICES, criterion_id=c.criterion_id,
        choice_details={
            "met_in_observed_state": "The observed workspace state shows the criterion is met.",
            "partially_met": "The observation shows some but not all parts of the criterion.",
            "not_met": "The observed workspace state shows the criterion is not met.",
            "cannot_tell": "The bounded observation does not establish the criterion status.",
        },
    ) for c in criteria)


def blind_completeness_questions(criteria: Sequence[Criterion]) -> tuple[QuestionSpec, ...]:
    return tuple(QuestionSpec(
        f"completeness:{c.criterion_id}", QuestionDimension.COMPLETENESS,
        f"Using only the task requirement and state.observed_state, classify whether criterion {c.criterion_id} is established in the observed workspace state.",
        COMPLETENESS_CHOICES, criterion_id=c.criterion_id,
    ) for c in criteria)


def task_only_criteria(task_text: str) -> tuple[Criterion, ...]:
    rows = split_criteria(task_text, fallback=False)[:12]
    if not rows:
        return (Criterion("T1", str(task_text).strip()[:1000] or "Complete the task"),)
    return tuple(Criterion(f"T{index}", str(row["text"])) for index, row in enumerate(rows, start=1))


def build_state_finish_request(*, model: str, raw_task: str, criteria: Sequence[Criterion],
                               questions: Sequence[QuestionSpec], observed_state: Mapping[str, Any],
                               card_claims: Sequence[Mapping[str, Any]], final_claim: str,
                               visible_evidence: Mapping[str, str], blind: bool) -> dict[str, Any]:
    """Build a bounded finish request; blind mode removes all solver claim text."""
    criteria_rows = [{"criterion_id": c.criterion_id, "text": c.text} for c in criteria]
    criterion_text = {row["criterion_id"]: row["text"] for row in criteria_rows}
    wire_questions = {q.question_id: _wire_question(q.to_dict(), criterion_text) for q in questions}
    evidence = {str(k): compact(str(v), 1200) for k, v in visible_evidence.items()}
    state: dict[str, Any] = {
        "schema": "aether.challenger.questionnaire.v1",
        "raw_task": str(raw_task)[:3000],
        "criteria": criteria_rows,
        "observed_state": deepcopy(dict(observed_state)),
        "visible_evidence": evidence,
    }
    if not blind:
        state["claim_card"] = {"challenger_card": [dict(row) for row in card_claims]}
        state["final_claim"] = str(final_claim)[:1200]
    request = {"model": model, "state": state, "questions": wire_questions}
    if _request_bytes(request) > STATE_FINISH_REQUEST_BYTES:
        for limit in (600, 300, 120, 0):
            state["visible_evidence"] = {key: value[:limit] for key, value in evidence.items()}
            if _request_bytes(request) <= STATE_FINISH_REQUEST_BYTES:
                break
    if _request_bytes(request) > STATE_FINISH_REQUEST_BYTES:
        raise ValueError("state-aware completion request exceeds 120000-byte bound")
    return request


def decide_finish(criteria: Sequence[Criterion], answers: Mapping[str, QuestionAnswer],
                  threshold: float, hold_threshold: float | None = None,
                  unverified_threshold: float | None = None) -> FinishDecision:
    """Deterministic table: confident none/contradicted holds; all direct admits; else advisory.

    ``hold_threshold`` (challenger_v2) separates holding from advisory notes and adds the failure-mode
    signal when that answer is present; without it the table is the original v1 one.
    ``unverified_threshold`` (challenger_v3 P3) additionally holds on a confident done_with_unverified_parts
    when no other hold applies; the caller passes it only while the per-run allowance is unused.
    """
    hold_at = threshold if hold_threshold is None else hold_threshold
    rows = [(c, answers[f"completeness:{c.criterion_id}"]) for c in sorted(criteria, key=lambda c: c.criterion_id)]
    mode = answers.get(FAILURE_QUESTION_ID)
    mode_bad = mode is not None and mode.choice in BAD_MODES
    signals = [a.confidence for _, a in rows if a.choice in HOLD_CHOICES]
    if mode_bad:
        signals.append(mode.confidence)
    strongest = max(signals, default=0.0)
    held = tuple(c.criterion_id for c, a in rows if a.choice in HOLD_CHOICES and a.confidence >= hold_at)
    mode_holds = mode_bad and mode.confidence >= hold_at
    if held or mode_holds:
        return FinishDecision(
            ActionKind.HOLD_FINISH,
            "criteria or the overall state judged missing, wrong or contradicted at or above the hold threshold",
            held, failure_mode=mode.choice if mode_holds else "",
            failure_confidence=mode.confidence if mode_holds else 0.0, strongest=strongest)
    if (unverified_threshold is not None and mode is not None and mode.choice == UNVERIFIED_MODE
            and mode.confidence >= unverified_threshold):
        return FinishDecision(
            ActionKind.HOLD_FINISH, "the work was judged done with parts the evidence does not verify",
            failure_mode=UNVERIFIED_MODE, failure_confidence=mode.confidence, strongest=strongest)
    notes = [f"{c.criterion_id}: judged {a.choice} (confidence {a.confidence:.2f})"
             for c, a in rows if a.choice != "direct_and_current" or a.confidence < threshold]
    if mode_bad:
        notes.append(f"overall state: judged {mode.choice} (confidence {mode.confidence:.2f})")
    if notes:
        return FinishDecision(ActionKind.ADVISORY_ONLY,
                              "not every criterion is direct at or above the confidence threshold",
                              notes=tuple(notes), strongest=strongest)
    return FinishDecision(ActionKind.ADMIT_FINISH, "all criteria are direct and current", strongest=strongest)


def apply_state_status_hold(decision: FinishDecision, criteria: Sequence[Criterion],
                            answers: Mapping[str, QuestionAnswer]) -> tuple[FinishDecision, tuple[str, ...]]:
    held = tuple(
        c.criterion_id for c in criteria
        if (answer := answers.get(f"criterion_status:{c.criterion_id}")) is not None
        and answer.choice == "not_met" and answer.confidence >= STATE_FINISH_HOLD_THRESHOLD
    )
    if not held:
        return decision, ()
    return FinishDecision(
        ActionKind.HOLD_FINISH,
        "observed-state criterion status judged not_met at confidence 0.60 or higher",
        tuple(dict.fromkeys((*decision.held, *held))), notes=decision.notes,
        failure_mode=decision.failure_mode, failure_confidence=decision.failure_confidence,
        strongest=max(decision.strongest, *(answers[f"criterion_status:{cid}"].confidence for cid in held)),
    ), held


def run_completion_review(
    fc: FlowContext, *, messages: Sequence[Mapping[str, Any]], step: int, trigger_id: str,
    hold_no: int, unverified_threshold: float | None = None, embedded_card: Mapping[str, Any] | None = None,
    final_claim: str = "", finish_review_mode: str = CONTROL,
    observed_state: Mapping[str, Any] | None = None,
) -> tuple[FinishDecision, dict[str, Any] | None]:
    binding = fc.binding
    assert binding is not None
    ledger = binding.exec_ledger
    refs = {r.receipt_id for r in evidence_receipts(ledger)}
    def parse(text: str) -> Any:
        return parse_completion(text, card_id=f"completion:{step}", trigger_id=trigger_id, known_refs=refs)

    parsed = _embedded_completion(fc, embedded_card, ledger, parse) if embedded_card is not None else None
    if parsed is None:
        prompt = COMPLETION_PROMPT.format(evidence="\n".join(evidence_listing(ledger)) or "(none)")
        ledger.record_accounting(receipt_id=f"step-{step}:challenger_card_turn:completion", step=step,
                                 counter="challenger_card_turns", event="completion_card")
        parsed = obtain_card(fc, messages, prompt, "Your completion card", COMPLETION_SCHEMA, parse)
    card, criteria, checks, notes = parsed
    blind_mode = finish_review_mode == BLIND_FINISH_REVIEW
    if blind_mode:
        criteria, task_ids = task_only_criteria(fc.task_text), ()
    else:
        card, criteria, task_ids = merge_task_criteria(card, criteria, fc.task_text)
    texts = {c.criterion_id: c.text for c in criteria}
    fc.ledger.record_card(card)
    claim_rows = _claim_rows(card, texts)
    fc.log.append("card", card="completion", card_id=card.card_id, notes=notes, claims=claim_rows)
    cited = [] if blind_mode else [r for claim in card.claims for r in claim.evidence_refs]
    views = evidence_views(ledger, cited)
    state_mode = finish_review_mode in {STATE_FINISH_REVIEW, BLIND_FINISH_REVIEW}
    artifact = (_artifact_review(fc, card, criteria, claim_rows, final_claim, views)
                if fc.artifact_threshold is not None and not state_mode else None)
    judge_views, judge_criteria, hold_at = views, criteria, fc.hold_threshold
    evaluator = fc.evaluator
    if artifact is not None:
        judge_views, judge_criteria, hold_at = artifact.views, artifact.criteria, fc.artifact_threshold
        questions = artifact.questions

        def evaluator(_state: Any, _questions: Any) -> Any:
            return fc.evaluator.send_prepared(artifact.request, max_bytes=ARTIFACT_MAX_REQUEST_BYTES)
    else:
        questions = blind_completeness_questions(criteria) if blind_mode else completeness_questions(card, criteria)
        if fc.failure_mode:
            questions = questions + (failure_question_spec(list(views)),)
    if state_mode:
        questions = questions + criterion_status_questions(criteria)
        prepared = getattr(fc.evaluator, "send_prepared", None)
        if not callable(prepared):
            raise ValueError("state-aware finish review requires prepared-request evaluator support")
        if observed_state is None:
            observed_state = {"status": "unavailable", "reason": "finish snapshot missing"}
        evidence = dict(views)
        request = build_state_finish_request(
            model=str(getattr(fc.evaluator, "model", "")),
            raw_task=str(getattr(fc.evaluator, "raw_task", fc.task_text)), criteria=criteria,
            questions=questions, observed_state=observed_state,
            card_claims=() if blind_mode else claim_rows,
            final_claim="" if blind_mode else final_claim,
            visible_evidence={} if blind_mode else evidence, blind=blind_mode)

        def evaluator(_state: Any, _questions: Any) -> Any:
            return prepared(request, max_bytes=STATE_FINISH_REQUEST_BYTES)
    variant = ({} if fc.artifact_threshold is None else
               {"evidence_variant": EVIDENCE_VARIANT_ARTIFACTS if artifact else EVIDENCE_VARIANT_FAILURE_MODE})
    if state_mode:
        variant.update({"finish_review": finish_review_mode,
                        "state_snapshot_bytes": _request_bytes({"snapshot": observed_state})})
    context = QuestionnaireContext(judge_criteria, judge_views)
    cycle = fc.ledger.begin_verify_repair_cycle()
    fc.log.append("judge_question", card_id=card.card_id, cycle=cycle,
                  questions={q.question_id: q.to_dict() for q in questions}, **variant,
                  **({"request_bytes": artifact.trim["bytes"], "artifact_trim": artifact.trim,
                      "artifact_candidates": artifact.candidates} if artifact else {}))
    round_ = QuestionnaireRunner().ask_in_cycle(fc.ledger, cycle, card, context, questions, evaluator)
    fc.log.append("judge_answer", card_id=card.card_id, cycle=cycle,
                  answers={k: {"choice": a.choice, "confidence": a.confidence, "probabilities": dict(a.probabilities), "evidence_refs": list(a.evidence_refs)}
                           for k, a in round_.answers.items()})
    decision = decide_finish(judge_criteria, round_.answers, fc.threshold, hold_at, unverified_threshold)
    status_held = ()
    if state_mode:
        decision, status_held = apply_state_status_hold(decision, judge_criteria, round_.answers)
    fc.ledger.record_action(decision.kind, detail=decision.reason)
    audit = ({} if fc.artifact_threshold is None else {
        **variant, "hold_threshold": hold_at, "strongest": decision.strongest,
        "request_bytes": artifact.trim["bytes"] if artifact else int(getattr(fc.evaluator, "last_request_bytes", 0))})
    if state_mode:
        audit.update({**variant, "hold_threshold": hold_at, "strongest": decision.strongest,
                      "request_bytes": _request_bytes(request)})
    fc.log.append("action", card_id=card.card_id, kind=decision.kind.value, reason=decision.reason,
                  held=list(decision.held), notes=list(decision.notes), **audit)
    if decision.kind == ActionKind.ADMIT_FINISH:
        return decision, None
    if blind_mode:
        kind = "completion_hold" if decision.kind == ActionKind.HOLD_FINISH else "completion_advisory"
        criteria_text = ", ".join(status_held or decision.held) or "one or more task criteria"
        feedback = {"schema": "aether.challenger.feedback.v1", "kind": kind,
                    "text": ("State-blind completion review held the finish for observed-state criteria: "
                             if decision.kind == ActionKind.HOLD_FINISH else
                             "State-blind completion review did not admit the finish for: ")
                            + criteria_text + ". The snapshot is a bounded observation window, not an atomic state at the finish trigger.",
                    "note": "CHALLENGER state-blind finish review: " + criteria_text}
    elif status_held:
        feedback = {"schema": "aether.challenger.feedback.v1", "kind": "completion_hold",
                    "text": "Completion review held the finish: the observed-state review judged "
                            + ", ".join(status_held) + " not met. The snapshot records a bounded observation window, not an atomic state at the finish trigger.",
                    "note": "CHALLENGER state-aware completion review held the finish for observed-state criteria: " + ", ".join(status_held)}
    else:
        feedback = render_completion_feedback(decision, card, judge_criteria, checks, round_.answers, views, fc, hold_no=hold_no)
    return decision, feedback


def _claim_rows(card: CompletionCard, texts: Mapping[str, str]) -> list[dict[str, Any]]:
    return [{"criterion": c.criterion_id, "evidence_refs": list(c.evidence_refs), "checks": list(c.check_ids),
             "source": c.source, **({"text": texts[c.criterion_id]} if c.source == TASK_SOURCE else {})}
            for c in card.claims]


def _artifact_review(fc: FlowContext, card: CompletionCard, criteria: Sequence[Criterion],
                     claim_rows: Sequence[Mapping[str, Any]], final_claim: str, cited_views: Mapping[str, str]) -> Any:
    """The artifact-evidence request when the run wrote files, else None (the failure-mode request stands)."""
    binding = fc.binding
    assert binding is not None
    if not callable(getattr(fc.evaluator, "send_prepared", None)):
        fc.log.append("artifact_evidence_skipped", reason="evaluator cannot send prepared requests")
        return None
    root = fc.workspace_root or str(getattr(binding.executor, "workspace_root", "") or "")
    try:
        review = build_artifact_review(
            ledger=binding.exec_ledger, executor=binding.executor, workspace_root=root,
            model=fc.evaluator.model, raw_task=fc.evaluator.raw_task, criteria=criteria, card_id=card.card_id,
            card_claims=claim_rows, final_claim=final_claim, cited_views=cited_views)
    except ValueError as exc:  # the evidence cannot be fitted under the byte cap
        fc.log.append("artifact_evidence_skipped", reason=str(exc)[:300])
        return None
    if review is None:
        fc.log.append("artifact_evidence_skipped", reason="no non-scratch workspace file written")
    return review


def _embedded_completion(fc: FlowContext, embedded: Mapping[str, Any], ledger: Any, parse: Any) -> Any:
    """Parse the card carried by the finish call with the card-turn parser; None means fall back.

    The finish call cites the evidence aliases the solver sees; the card parser works on receipt ids.
    """
    by_alias = {evidence_alias(r.receipt_id): r.receipt_id for r in evidence_receipts(ledger)}
    try:
        criteria = embedded.get("criteria")
        rows = [dict(row, evidence_refs=[by_alias.get(str(r), str(r)) for r in row.get("evidence_refs") or ()])
                if isinstance(row, Mapping) and isinstance(row.get("evidence_refs"), (list, tuple)) else row
                for row in criteria] if isinstance(criteria, (list, tuple)) else criteria
        text = json.dumps({**embedded, "criteria": rows})
        parsed = parse(text)
    except (CardError, TypeError, ValueError) as exc:
        fc.log.append("card_invalid", card="Your completion card", attempt=0, source="finish", error=str(exc))
        return None
    fc.log.append("card_response", card="Your completion card", attempt=0, source="finish", text=text)
    return parsed


def render_completion_feedback(decision: FinishDecision, card: CompletionCard,
                               criteria: Sequence[Criterion], checks: Mapping[str, RunnableCheck],
                               answers: Mapping[str, QuestionAnswer], views: Mapping[str, str],
                               fc: FlowContext, *, hold_no: int) -> dict[str, Any]:
    if decision.kind == ActionKind.ADVISORY_ONLY:
        text = "Advisory note from the completion review (finish is not held): " + "; ".join(decision.notes) + "."
        return {"schema": "aether.challenger.feedback.v1", "kind": "completion_advisory", "text": text, "note": "CHALLENGER advisory: " + "; ".join(decision.notes)}
    if decision.failure_mode == UNVERIFIED_MODE and not decision.held:
        return render_verification_hold(decision, criteria, answers, hold_no=hold_no)
    by_id = {c.criterion_id: c for c in criteria}
    claims = {c.criterion_id: c for c in card.claims}
    lines = [f"Completion review: finish held (hold {hold_label(hold_no)}). "
             + ("The evidence you cited does not establish these criteria:" if decision.held
                else "The review judged the overall state of the task:")]
    from_task = {c.criterion_id for c in card.claims if c.source == TASK_SOURCE}
    shown = list(decision.held[:MAX_HELD_CRITERIA_SHOWN]) + [h for h in decision.held[MAX_HELD_CRITERIA_SHOWN:] if h in from_task]
    for cid in shown:
        answer = answers[f"completeness:{cid}"]
        origin = (" [taken from the task text; your completion card did not cover it]" if cid in from_task else "")
        lines.append(f'- {cid}: "{by_id[cid].text}"{origin} judged {answer.choice} (confidence {answer.confidence:.2f}).')
        cited = [r for r in claims[cid].evidence_refs if r != NO_EVIDENCE_REF]
        if not cited:
            lines.append("  Missing: you cited no evidence receipt for this criterion.")
        for ref in cited[:2]:
            lines.append(f"  Cited {ref}: {views.get(ref, '')[:EVIDENCE_SHOWN_CHARS]!r}")
        check = next((checks[i] for i in claims[cid].check_ids if i != NO_CHECK_ID and i in checks), None)
        if check is None:
            lines.append("  Suggested next step: write and run one command that demonstrates this criterion, "
                         "or rebut with specific evidence refs.")
        else:
            lines.append(f"  Suggested check (yours): {check.command}")
            lines.append("  " + command_run_status(fc.binding.exec_ledger, check.command))
    if decision.failure_mode:
        lines.append(f"- The review judged the overall state: {decision.failure_mode} "
                     f"({decision.failure_confidence:.2f}). {FAILURE_DETAILS[decision.failure_mode]}")
        lines.append("  Suggested next step: re-read the task, compare each requirement (content, location, format) "
                     "with what you produced, and verify the produced result directly.")
    lines.append("Run the check or rebut with evidence, then finish again.")
    parts = [f"{cid} judged {answers[f'completeness:{cid}'].choice}" for cid in decision.held]
    if decision.failure_mode:
        parts.append(f"overall state judged {decision.failure_mode} ({decision.failure_confidence:.2f})")
    return {"schema": "aether.challenger.feedback.v1", "kind": "completion_hold", "text": "\n".join(lines),
            "note": f"CHALLENGER completion hold {hold_label(hold_no)}: {'; '.join(parts)}; run the suggested check or rebut with evidence"}


def render_verification_hold(decision: FinishDecision, criteria: Sequence[Criterion],
                             answers: Mapping[str, QuestionAnswer], *, hold_no: int) -> dict[str, Any]:
    """challenger_v3 P3: name the criteria judged indirect or self-written-check-only; ask for direct verification."""
    weak = [(c, answers[f"completeness:{c.criterion_id}"]) for c in sorted(criteria, key=lambda c: c.criterion_id)
            if answers[f"completeness:{c.criterion_id}"].choice in WEAK_CHOICES]
    lines = [f"Completion review: finish held (hold {hold_label(hold_no)}). The review judged the work complete "
             f"but not verified by the evidence ({decision.failure_mode}, {decision.failure_confidence:.2f})."]
    if weak:
        lines.append("These criteria rest only on indirect evidence or on a check you wrote yourself:")
        for c, a in weak[:MAX_WEAK_CRITERIA_SHOWN]:
            lines.append(f'- {c.criterion_id}: "{c.text}" judged {a.choice} (confidence {a.confidence:.2f}).')
        if len(weak) > MAX_WEAK_CRITERIA_SHOWN:
            lines.append(f"- and {len(weak) - MAX_WEAK_CRITERIA_SHOWN} more.")
    lines.append("Verify them directly against the task's stated requirements: run the produced artifact the way "
                 "the task describes and inspect the actual output. Then finish again.")
    names = ", ".join(c.criterion_id for c, _ in weak[:MAX_WEAK_CRITERIA_SHOWN]) or "none singled out"
    return {"schema": "aether.challenger.feedback.v1", "kind": "completion_hold", "text": "\n".join(lines),
            "note": f"CHALLENGER verification hold {hold_label(hold_no)}: {decision.failure_mode} "
                    f"({decision.failure_confidence:.2f}); unverified criteria: {names}; verify directly"}


def hold_label(hold_no: int) -> str:
    """'N of 3' within the cap; past it (challenger_v2 extended holds) there is no fixed total."""
    if hold_no <= MAX_HOLD_CYCLES:
        return f"{hold_no} of {MAX_HOLD_CYCLES}"
    return f"{hold_no}, extended because a hold signal is near-certain"


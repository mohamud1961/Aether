"""T2: one JUDGE progress question per window of accepted actions after T1."""
from __future__ import annotations

from typing import Any, Sequence

from ..challenger_claim_types import QUESTIONNAIRE_SCHEMA
from ..ledger import Receipt
from .config import T2_FLAG_CHOICES, T2_FLAG_THRESHOLD, T2_WINDOW_ACTIONS
from .evidence import evidence_receipts, _view
from .progress_question import compact, progress_question, split_criteria
from .state import FlowContext

VIEW_CHARS = 300


def task_actions(fc: FlowContext) -> list[Receipt]:
    """Evidence receipts of the solver's own actions (CHALLENGER's own checks excluded), oldest first."""
    return [r for r in evidence_receipts(fc.binding.exec_ledger) if ":challenger-check-" not in r.receipt_id]


def ask_progress(fc: FlowContext, actions: Sequence[Receipt], step: int) -> tuple[str, float]:
    """Ask the replay-calibrated progress question over the last window vs the previous one."""
    window = list(actions[-T2_WINDOW_ACTIONS:])
    previous = list(actions[-2 * T2_WINDOW_ACTIONS:-T2_WINDOW_ACTIONS])
    views: dict[str, str] = {}
    new_refs = [f"w{i}" for i in range(len(window))]
    old_refs = [f"p{i}" for i in range(len(previous))]
    for ref, r in zip(new_refs + old_refs, window + previous):
        views[ref] = compact(_view(r), VIEW_CHARS)
    criteria = split_criteria(fc.task_text)
    state: dict[str, Any] = {
        "schema": QUESTIONNAIRE_SCHEMA, "criteria": criteria, "visible_evidence": views,
        "claim_card": {"card_id": f"progress:{step}", "latest_window_refs": new_refs,
                       "previous_window_refs": old_refs},
    }
    questions = {"progress:window": progress_question(new_refs, old_refs)}
    fc.log.append("judge_question", card_id=f"progress:{step}", questions=questions)
    answers = fc.evaluator(state, questions)
    row = answers["progress:window"]
    choice = str(row["choice"])
    probs = row.get("probabilities") or {}
    if choice not in questions["progress:window"]["choices"]:
        raise ValueError("progress answer chose an undeclared option")
    prob = float(probs.get(choice, row.get("confidence", 0.0)))
    fc.log.append("judge_answer", card_id=f"progress:{step}", choice=choice, probabilities=dict(probs))
    return choice, prob


def is_flag(choice: str, prob: float) -> bool:
    return choice in T2_FLAG_CHOICES and prob >= T2_FLAG_THRESHOLD

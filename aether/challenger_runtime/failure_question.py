"""Single source of the CHALLENGER failure-mode question (challenger_v2 T4) and its choices.

Shared by the live T4 completion review and the provider-free JUDGE bench so both
ask JUDGE exactly the same question. The runtime owns it; the bench imports it.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..challenger_claim_types import QuestionDimension, QuestionSpec

FAILURE_QUESTION_ID = "failure_mode"
FAILURE_MODES = ("fully_done", "done_with_unverified_parts", "incomplete", "wrong_output",
                 "wrong_location_or_format", "unknown")
UNVERIFIED_MODE = "done_with_unverified_parts"
BAD_MODES = frozenset({"incomplete", "wrong_output", "wrong_location_or_format"})
FAILURE_DETAILS: Mapping[str, str] = {
    "fully_done": "Every requirement is met and the evidence shows it.",
    "done_with_unverified_parts": "The work looks complete but some requirements are not verified by the evidence.",
    "incomplete": "Some required part of the task was not done.",
    "wrong_output": "Work was done but the produced result is incorrect.",
    "wrong_location_or_format": "The result is right in substance but is in the wrong place or format.",
    "unknown": "The evidence is insufficient to tell.",
}
FAILURE_RELATION = ("Given the evidence, which best describes the most likely state of the task at the moment "
                    "the solver submitted?")


def failure_question(refs: Sequence[str] | None = None, context: str | None = None) -> dict[str, Any]:
    """The question as the plain spec mapping the wire adapter consumes."""
    spec: dict[str, Any] = {"relation": FAILURE_RELATION, "choices": list(FAILURE_MODES),
                            "choice_details": dict(FAILURE_DETAILS)}
    if refs is not None:
        spec["evidence_refs"] = list(refs)
    if context:
        spec["context_text"] = context
    return spec


def failure_question_spec(refs: Sequence[str]) -> QuestionSpec:
    return QuestionSpec(FAILURE_QUESTION_ID, QuestionDimension.FAILURE_MODE, FAILURE_RELATION,
                        FAILURE_MODES, evidence_refs=tuple(refs), choice_details=dict(FAILURE_DETAILS))

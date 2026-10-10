"""Neutral model-visible projection of independent-review semantic advice.

Internal advice records carry experiment, head and mode identifiers that belong
to telemetry and journals only.  The Solver sees just the typed answers under a
neutral heading with neutral instruction text.
"""
from __future__ import annotations

from typing import Any, Mapping

INDEPENDENT_REVIEW_KEY = "independent_review"
_INTERNAL_HEADS = frozenset({"trace_aware_judge", "selective_judge"})
INDEPENDENT_REVIEW_INSTRUCTION = (
    "Independent review of the current public evidence; it has no access to hidden "
    "tests or solutions. Weigh it against your own observations."
)


def project_independent_review(advice: Any) -> dict[str, Any] | None:
    """Return the neutral view for typed-answer advice, else ``None``.

    ``None`` means the advice is not of the typed-answer kind and the caller
    keeps its existing exposure unchanged.
    """
    if not isinstance(advice, Mapping):
        return None
    items = [item for item in (advice.get("items") or ()) if isinstance(item, Mapping)]
    if not items or any(str(item.get("head") or "") not in _INTERNAL_HEADS for item in items):
        return None
    answers: dict[str, Any] = {}
    for item in items:
        for question, answer in dict(item.get("answers") or {}).items():
            answers[str(question)] = {
                "choice": str(answer["choice"]),
                "probabilities": {
                    str(choice): float(p) for choice, p in dict(answer["probabilities"]).items()
                },
            }
    return {"instruction": INDEPENDENT_REVIEW_INSTRUCTION, "answers": answers}


__all__ = ["INDEPENDENT_REVIEW_INSTRUCTION", "INDEPENDENT_REVIEW_KEY", "project_independent_review"]

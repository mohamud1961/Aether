"""T4: acceptance criteria derived from the raw task text, merged with the solver's card criteria."""
from __future__ import annotations

import re
from typing import Sequence

from ..challenger_claim_types import CompletionCard, Criterion, CriterionClaim
from .evidence import NO_EVIDENCE_REF
from .progress_question import MAX_CRITERIA, split_criteria
from .cards import NO_CHECK_ID

TASK_SOURCE = "task_text"
TASK_ID_PREFIX = "T"


def normalize(text: str) -> str:
    """Case-, whitespace-, punctuation- and list-marker-insensitive key for de-duplication."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def merge_task_criteria(
    card: CompletionCard, criteria: Sequence[Criterion], task_text: str,
) -> tuple[CompletionCard, tuple[Criterion, ...], tuple[str, ...]]:
    """Add task-text criteria the card does not already carry (the card's wording wins).

    Added criteria get ids T1..Tn and cite the union of the evidence the card cited, so JUDGE is
    asked the normal completeness question about them. Total is capped at MAX_CRITERIA (12).
    Returns the merged card, the merged criteria, and the ids of the task-derived additions.
    """
    seen = {normalize(c.text) for c in criteria}
    cited = tuple(dict.fromkeys(r for claim in card.claims for r in claim.evidence_refs if r != NO_EVIDENCE_REF))
    claims, merged, added = list(card.claims), list(criteria), []
    for row in split_criteria(task_text, fallback=False):
        key = normalize(row["text"])
        if not key or key in seen or len(merged) >= MAX_CRITERIA:
            continue
        seen.add(key)
        n = len(added) + 1
        while f"{TASK_ID_PREFIX}{n}" in {c.criterion_id for c in merged}:
            n += 1
        cid = f"{TASK_ID_PREFIX}{n}"
        merged.append(Criterion(cid, row["text"]))
        claims.append(CriterionClaim(cid, cited or (NO_EVIDENCE_REF,), (NO_CHECK_ID,), TASK_SOURCE))
        added.append(cid)
    if not added:
        return card, tuple(criteria), ()
    return CompletionCard(card.card_id, card.trigger_id, tuple(claims)), tuple(merged), tuple(added)

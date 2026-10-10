"""Single source of the CHALLENGER progress-window question and the criteria heuristic.

Shared by the live T2 stuck trigger and the provider-free JUDGE replay tool so
both ask JUDGE exactly the same question.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from ..criteria_mode import COMPLETE_V1, resolve_criteria_mode

PROGRESS_CHOICES = ("advanced_criterion", "no_material_change", "test_only_change", "symptom_moved", "regression")
PROGRESS_DETAILS: Mapping[str, str] = {
    "advanced_criterion": "The latest window moved at least one task criterion closer to satisfied.",
    "no_material_change": "The latest window did not materially change the task state relative to the previous one.",
    "test_only_change": "The latest window only added or changed tests/checks/scratch files, not the production result.",
    "symptom_moved": "The latest window moved the symptom elsewhere without resolving the underlying cause.",
    "regression": "The latest window made the task state worse than the previous window.",
}
PROGRESS_RELATION = (
    "Compare the latest window of solver actions (refs w*) with the previous window (refs p*). "
    "Which best describes the change in task state?"
)


def compact(text: str, limit: int) -> str:
    """Keep head and tail of an over-long text so both the command and the verdict survive."""
    if len(text) <= limit:
        return text
    head = max(1, int(limit * 0.4))
    tail = max(1, limit - head - 5)
    return text[:head] + " ... " + text[-tail:]


MAX_CRITERIA = 12
CRITERIA_FALLBACK = (12, 8, 6, 4, 2)  # shrink the criteria list only if evidence trimming cannot fit
CRITERION_CHARS = 300
VIEW_CHARS = 480
_MODAL = re.compile(
    r"\b(must|should|shall|ensure|make sure|needs? to|has to|have to|required|require[sd]?|"
    r"expected to|is expected|will be (?:tested|checked|graded))\b", re.I)
# Prohibitions count only as an instruction at the start of a unit ("Do not modify
# the tests"), never inside a description ("Sessions don't expire properly").
_PROHIBITION = re.compile(r"^(?:\d+[.)]\s*|[-*]\s*)?(?:please\s+)?(?:do not|don't|never|always)\b", re.I)
_IMPERATIVE = re.compile(
    r"^(?:\d+[.)]\s*|[-*]\s*)?(?:please\s+)?(create|write|implement|fix|add|update|make|build|run|configure|"
    r"install|set|remove|generate|produce|return|output|save|use|modify|change|rename|move|copy|define|"
    r"compile|provide|extract|parse|handle|support|validate|print|ensure|delete|replace|train|convert|"
    r"find|compute|calculate|solve|recover|restore|deploy|launch|start|stop|enable|disable|apply)\b", re.I)
_INCOMPLETE_MODAL_END = re.compile(
    r"\b(?:contain(?:s|ed|ing)?|ensure(?:s|d|ing)?|be|being|been)\s*[.!?]*$", re.I)
_ABBREVIATION = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|No|e\.g|i\.e|U\.S|U\.K)\.", re.I)


def _complete_clause_units(task_text: str) -> list[str]:
    """Join wrapped prose before splitting at sentence/list boundaries."""
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for raw_line in task_text.replace("\r", "").split("\n"):
        line = raw_line.strip()
        if not line:
            flush()
            continue
        marker = re.match(r"^(?:\d+[.)]|[-*])\s+", line)
        if marker:
            flush()
            current.append(line)
        else:
            current.append(line)
    flush()

    units: list[str] = []
    for paragraph in paragraphs:
        protected = _ABBREVIATION.sub(lambda m: m.group(0).replace(".", "\ue000"), paragraph)
        sentences = re.split(r"(?<=[.!?])\s+(?=\S)", protected)
        units.extend(s.replace("\ue000", ".").strip() for s in sentences if s.strip())
    return units


def _has_complete_predicate(unit: str) -> bool:
    """Reject modal fragments such as a subject followed only by ``must``."""
    prohibition = _PROHIBITION.match(unit)
    if prohibition:
        return bool(re.search(r"\b[A-Za-z][A-Za-z'-]*\b", unit[prohibition.end():]))
    modal = _MODAL.search(unit)
    if modal:
        tail = unit[modal.end():].strip()
        return (
            bool(re.search(r"\b[A-Za-z][A-Za-z'-]*\b", tail))
            and not _INCOMPLETE_MODAL_END.search(tail)
        )
    return bool(_IMPERATIVE.match(unit))


def split_criteria(
    task_text: str, *, fallback: bool = True, mode: str | None = None,
    max_criteria: int | None = MAX_CRITERIA,
) -> list[dict[str, str]]:
    """Deterministic acceptance-criteria heuristic.

    Control uses the historical line/sentence units. ``complete_v1`` first
    rejoins wrapped prose, then splits on sentence/list boundaries. A unit is
    a criterion when it contains a modal/obligation word or starts with an
    imperative task verb (optionally after a list marker).
    Capped at 12 criteria of <=300 chars by default, de-duplicated, ids C1..Cn.
    Pass ``max_criteria=None`` to inspect the complete qualifying set. When no
    unit qualifies the whole task opening is one criterion.
    """
    selected_mode = resolve_criteria_mode(mode)
    if selected_mode == COMPLETE_V1:
        units = _complete_clause_units(task_text)
    else:
        units = []
        for line in task_text.replace("\r", "").split("\n"):
            line = line.strip()
            if not line:
                continue
            if re.match(r"^(?:\d+[.)]|[-*])\s+", line):
                units.append(line)
                continue
            units.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9`\"'(])", line) if s.strip())
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for unit in units:
        key = unit.lower()
        if key in seen or len(unit) < 12:
            continue
        if (_MODAL.search(unit) or _PROHIBITION.match(unit) or _IMPERATIVE.match(unit)):
            if selected_mode == COMPLETE_V1 and not _has_complete_predicate(unit):
                continue
            seen.add(key)
            criterion = unit if selected_mode == COMPLETE_V1 else compact(unit, CRITERION_CHARS)
            out.append({"criterion_id": f"C{len(out) + 1}", "text": criterion})
            if max_criteria is not None and len(out) == max_criteria:
                break
    if not out and fallback:
        if selected_mode == COMPLETE_V1:
            opening = next(iter(_complete_clause_units(task_text)), "")
            if ((_MODAL.search(opening) or _PROHIBITION.match(opening) or _IMPERATIVE.match(opening))
                    and _has_complete_predicate(opening)):
                out = [{"criterion_id": "C1", "text": opening}]
        else:
            out = [{"criterion_id": "C1", "text": compact(" ".join(task_text.split()), CRITERION_CHARS)
                    or "Complete the task as stated."}]
    return out


def progress_question(new_refs: list[str], old_refs: list[str]) -> dict[str, Any]:
    return {
        "relation": PROGRESS_RELATION,
        "choices": list(PROGRESS_CHOICES), "choice_details": dict(PROGRESS_DETAILS),
        "evidence_refs": list(new_refs) + list(old_refs),
    }

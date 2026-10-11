"""Questionnaire vocabulary and criterion extraction used by Core advisory reviews.

The definitions Core used from the research runtime, unchanged.
"""

from __future__ import annotations

import os
import re
from typing import Any, Mapping, Sequence

CONTROL = "control"
COMPLETE_V1 = "complete_v1"
CRITERIA_MODES = (CONTROL, COMPLETE_V1)
CRITERIA_MODE_ENV = "AETHER_CRITERIA_MODE"


class CriteriaModeError(ValueError):
    """An unsupported task-criteria extraction mode was selected."""


def resolve_criteria_mode(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    selected = str(value if value is not None else env.get(CRITERIA_MODE_ENV, CONTROL)).strip()
    if selected not in CRITERIA_MODES:
        raise CriteriaModeError(f"criteria mode must be one of {', '.join(CRITERIA_MODES)}")
    return selected



QUESTIONNAIRE_SCHEMA = "aether.typed_questionnaire.v1"







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

def compact(text: str, limit: int) -> str:
    """Keep head and tail of an over-long text so both the command and the verdict survive."""
    if len(text) <= limit:
        return text
    head = max(1, int(limit * 0.4))
    tail = max(1, limit - head - 5)
    return text[:head] + " ... " + text[-tail:]

MAX_CRITERIA = 12

CRITERION_CHARS = 300

_MODAL = re.compile(
    r"\b(must|should|shall|ensure|make sure|needs? to|has to|have to|required|require[sd]?|"
    r"expected to|is expected|will be (?:tested|checked|graded))\b", re.I)

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

CHOICE_DESCRIPTIONS: Mapping[str, str] = {
    "direct_and_current": "The cited evidence directly shows the criterion holds in the current task state.",
    "indirect": "The cited evidence only bears on the criterion indirectly.",
    "self_written_check_only": "Only a check or script the solver wrote supports it; nothing independent does.",
    "none": "No cited evidence bears on the criterion.",
    "contradicted": "Cited evidence shows the criterion does not hold.",
}

def _wire_question(spec: Mapping[str, Any], criteria_text: Mapping[str, str]) -> dict[str, Any]:
    details = dict(spec.get("choice_details") or {})
    parts = [str(spec["relation"])]
    criterion_id = str(spec.get("criterion_id") or "")
    if criterion_id:
        parts.append(f"Criterion {criterion_id}: {criteria_text.get(criterion_id, '')}")
    if spec.get("context_text"):
        parts.append(str(spec["context_text"]))
    refs = list(spec.get("evidence_refs", ()))
    if refs:
        parts.append("Cited evidence refs (see state.visible_evidence): " + ", ".join(refs))
    return {
        "type": "choice",
        "instructions": "\n".join(parts),
        "criteria": {
            str(choice): str(
                details.get(choice) or CHOICE_DESCRIPTIONS.get(choice)
                or (f"Rank {choice} (1 = best explains the stated symptom)" if str(choice).isdigit() else choice)
            )
            for choice in spec["choices"]
        },
    }

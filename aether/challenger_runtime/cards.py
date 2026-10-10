"""GLM card prompts and strict parsers for the T1 diagnosis and T4 completion cards."""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from ..challenger_claim_types import (
    CheckKind, CheckOrigin, CompletionCard, Criterion, CriterionClaim, DiagnosisCard,
    Hypothesis, RunnableCheck, MAX_CHECK_COMMAND_CHARS,
)
from .evidence import NO_EVIDENCE_REF

SYMPTOM_CRITERION_ID = "symptom"
MAX_CRITERIA = 8
NO_CHECK_ID = "none"


class CardError(ValueError):
    """The solver's card was not valid JSON of the declared shape."""


DIAGNOSIS_PROMPT = """\
Before your pending action runs, write a diagnosis card as ONE JSON object and nothing else.
Fields:
  "symptom": the symptoms stated in the task, in your own words.
  "hypotheses": 2 to 4 objects, each with "id" (H1, H2, ...), "statement", "status"
    ("considered" or "dismissed"), "reason" (why, required when dismissed), and "check":
    {{"description": ..., "command": ...}}.
Include every hypothesis you have considered, including any you set aside. Each check must be
one read-only shell command (no file writes, installs, or state changes) whose result would
distinguish that hypothesis from the others.

Your pending action: {pending}
"""

COMPLETION_PROMPT = """\
You are about to finish. Write a completion card as ONE JSON object and nothing else.
Field "criteria": a list with one object for each separate acceptance criterion stated in the
task (do not merge or omit any). Each object has "id" (C1, C2, ...), "text" (the criterion),
"evidence_refs" (receipt ids from the list below that show the criterion holds now; [] if none),
and "check": {{"description": ..., "command": ...}} naming the command that demonstrates it.

Available evidence receipts (id | summary):
{evidence}
"""


DIAGNOSIS_SCHEMA = (
    '{"symptom": "...", "hypotheses": [{"id": "H1", "statement": "...", "status": "considered" | "dismissed", '
    '"reason": "required when dismissed", "check": {"description": "...", "command": "one read-only shell command"}}, ...]}'
    " with 2 to 4 hypotheses"
)
COMPLETION_SCHEMA = (
    '{"criteria": [{"id": "C1", "text": "...", "evidence_refs": ["receipt id", ...], '
    '"check": {"description": "...", "command": "shell command"}}, ...]} with one entry per acceptance criterion'
)
DEFAULT_CHECK_DESCRIPTION = "check"


def extract_json(text: str) -> Mapping[str, Any]:
    """First JSON object in the response, whether bare, fenced, or surrounded by prose."""
    decoder = json.JSONDecoder()
    first_error = ""
    start = text.find("{")
    if start < 0:
        raise CardError("no JSON object in card response")
    while start >= 0:
        try:
            value, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError as exc:
            first_error = first_error or f"{exc.msg} (line {exc.lineno} column {exc.colno})"
        else:
            if isinstance(value, Mapping):
                return value
        start = text.find("{", start + 1)
    raise CardError(f"card JSON is invalid: {first_error or 'no object found'}")


def _check(row: Any, check_id: str, criterion_id: str) -> RunnableCheck:
    if isinstance(row, str):  # a bare string is the command
        row = {"command": row}
    if not isinstance(row, Mapping):
        raise CardError(f"check for {check_id} must be an object with a command (or a command string)")
    command = str(row.get("command") or "").strip()
    description = str(row.get("description") or "").strip() or (DEFAULT_CHECK_DESCRIPTION if command else "")
    if not description or not command:
        raise CardError(f"check for {check_id} needs a non-empty command")
    if len(command) > MAX_CHECK_COMMAND_CHARS:
        raise CardError(f"check for {check_id} has a command longer than {MAX_CHECK_COMMAND_CHARS} characters")
    return RunnableCheck(check_id, criterion_id, description, command,
                         CheckOrigin.GLM, CheckKind.READ_ONLY_INSPECTION)


def parse_diagnosis(text: str, *, card_id: str, trigger_id: str) -> DiagnosisCard:
    data = extract_json(text)
    symptom = str(data.get("symptom") or "").strip()
    rows = data.get("hypotheses")
    if not symptom or not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise CardError("diagnosis card needs a symptom and a hypotheses list")
    hypotheses = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise CardError("each hypothesis must be an object")
        hid = str(row.get("id") or "").strip()
        status = str(row.get("status") or "considered").strip().lower()
        statement = str(row.get("statement") or "").strip()
        if status == "dismissed":
            reason = str(row.get("reason") or "").strip()
            if not reason:
                raise CardError(f"dismissed hypothesis {hid} needs a reason")
            statement = f"{statement} (dismissed by the solver because: {reason})"
        try:
            hypotheses.append(Hypothesis(
                hid, statement, "dismissed" if status == "dismissed" else "considered",
                _check(row.get("check"), f"{card_id}:{hid}", SYMPTOM_CRITERION_ID),
            ))
        except ValueError as exc:
            raise CardError(str(exc)) from None
    try:
        return DiagnosisCard(card_id, trigger_id, symptom, tuple(hypotheses))
    except ValueError as exc:
        raise CardError(str(exc)) from None


def parse_completion(
    text: str, *, card_id: str, trigger_id: str, known_refs: set[str],
) -> tuple[CompletionCard, tuple[Criterion, ...], dict[str, RunnableCheck], list[str]]:
    """Parse the card; refs the ledger does not know are dropped and reported as notes."""
    data = extract_json(text)
    rows = data.get("criteria")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise CardError("completion card needs a non-empty criteria list")
    if len(rows) > MAX_CRITERIA:
        raise CardError(f"completion card lists more than {MAX_CRITERIA} criteria")
    claims, criteria, checks, notes = [], [], {}, []
    for row in rows:
        if not isinstance(row, Mapping):
            raise CardError("each criterion must be an object")
        cid = str(row.get("id") or "").strip()
        refs = [str(r).strip() for r in (row.get("evidence_refs") or ()) if str(r).strip()]
        valid = [r for r in dict.fromkeys(refs) if r in known_refs]
        if len(valid) != len(set(refs)):
            notes.append(f"{cid}: dropped unknown evidence refs {sorted(set(refs) - set(valid))}")
        check_ids = [NO_CHECK_ID]
        if row.get("check"):
            check = _check(row["check"], f"{card_id}:{cid}:check", cid)
            checks[check.check_id] = check
            check_ids = [check.check_id]
        try:
            criteria.append(Criterion(cid, str(row.get("text") or "")))
            claims.append(CriterionClaim(cid, tuple(valid) or (NO_EVIDENCE_REF,), tuple(check_ids)))
        except ValueError as exc:
            raise CardError(str(exc)) from None
    try:
        return CompletionCard(card_id, trigger_id, tuple(claims)), tuple(criteria), checks, notes
    except ValueError as exc:
        raise CardError(str(exc)) from None

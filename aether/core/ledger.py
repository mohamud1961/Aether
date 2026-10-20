"""A requirement ledger kept while working, bound to the task's own words (``CoreConfig.ledger``).

Wrong-finish study (CORE_WRONG_FINISH_DIVERGENCE_STUDY_20261015): in 5 of the 6 tasks with recurring wrong
finishes, across harnesses and models, the delivered output broke a requirement the task states explicitly (the
FASTA must match, the alphabetical tie rule, the Tm definition and flags, the criteria list), and the run's own
checks tested its operationalisation of it. The strongest coding agents keep an explicit requirement list while
working (Claude Code's TodoWrite, Codex's update_plan); this one is tied to the task's text:

- the solver keeps the ledger with the ``requirements`` tool, from the start; each call replaces it;
- each item **quotes the task verbatim** (checked mechanically: whitespace and case aside, the quote must occur in
  the task), says how the run reads it, names any other reading it sees, has a status, and once met cites the steps
  whose output shows it;
- **coverage is mechanical**: the task's requirement sentences (bullets and sentences carrying a requirement word:
  must, should, only, exactly, between, at most, assume, format, save, ...) must each be quoted by some item; every
  call lists the ones no item quotes;
- cited steps get evidence's citation-shape check (exists, did not fail, not only writes, not a stale read).

At the first finish the ledger is checked once more; uncovered requirement sentences, items not met, and met items
with citation problems hold that finish once (with time left); the next finish ends the work. Every check is
recorded (``extras.ledger``).

What it cannot do: it does not know whether a reading is right, whether a cited output says what the item says, or
whether the sentence list is complete (a requirement phrased without a requirement word is not listed). A ledger
records the model's beliefs; it is not proof (Codex review). Its bet is narrow: the recurring failures sit on
sentences the task states, and quoting, reading and showing each of them while working moves attention onto them.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from . import evidence

STATUSES = ("open", "met", "not_met", "unsure")
CUES = re.compile(
    r"\b(must|should|shall|needs?|required?|requires|only|exactly|at (?:least|most)|between|no|not|don't|do not|"
    r"never|always|assume|ensure|make sure|use|write|create|format|save|store|output|return|include|exclude|each|"
    r"every|all)\b",
    re.IGNORECASE,
)
BULLET = re.compile(r"^\s*(?:[*\-•]|\d+[.)])\s+")
MIN_WORDS = 4
MIN_OVERLAP = 40  # characters of a sentence a quote must share to cover it (or the whole sentence if shorter)
MAX_LISTED = 25
AUDIT_MIN_S = evidence.AUDIT_MIN_S

LEDGER_TOOL = {
    "type": "function",
    "function": {
        "name": "requirements",
        "description": "Keep your ledger of the task's requirements: call it early and whenever an item changes. "
        "Each call replaces the whole ledger and returns it with the task's requirement sentences that no item "
        "quotes yet, quotes not found in the task, and citation problems.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "quote": {
                                "type": "string",
                                "description": "The task's own words for this requirement, copied exactly.",
                            },
                            "reading": {
                                "type": "string",
                                "description": "How you read it: what exactly must hold, measured how.",
                            },
                            "other_readings": {
                                "type": "string",
                                "description": "Any other way the words can be read, and what decides between "
                                "them. Empty if none.",
                            },
                            "status": {"type": "string", "enum": list(STATUSES)},
                            "shown_by": {
                                "type": "string",
                                "description": "For met: what shows it, ending with the steps, e.g. "
                                "'oligotm on the annealing parts gives a 3.1 C gap [steps 31, 32]'.",
                            },
                        },
                        "required": ["quote", "reading", "status"],
                    },
                }
            },
            "required": ["items"],
        },
    },
}

LEDGER_DOC = """
Requirements: from the start, keep a ledger of the task's requirements with the requirements tool, and update it \
as you work. Each item quotes the task's own words exactly, says how you read them, names any other reading you can \
see and what decides between them, and, once met, cites the steps whose output shows it. Show a requirement the way \
the task states it (its definitions, tools, flags, formats and inputs), not by your own version of it: a check \
that uses your reading cannot reveal that the reading is wrong. The tool lists the task's requirement sentences \
that no item quotes."""

HELD = """[requirements check: the finish did not take effect]
{problems}

Address what is listed, or, if the finish is right as it stands, call finish again; the next finish ends the work."""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def sentences(task: str) -> list[str]:
    """The task's requirement sentences: every bullet or numbered item (with its continuation lines) and every other
    sentence that carries a requirement word, outside code fences."""
    units: list[tuple[bool, str]] = []  # (from a bullet, text)
    prose: list[str] = []
    bullet: list[str] | None = None
    fenced = False

    def flush_prose() -> None:
        text = " ".join(prose).strip()
        prose.clear()
        units.extend((False, p) for p in re.split(r"(?<=[.!?])\s+", text) if p)

    for line in str(task or "").splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if BULLET.match(line):
            flush_prose()
            if bullet:
                units.append((True, " ".join(bullet)))
            bullet = [BULLET.sub("", line).strip()]
        elif not line.strip():
            if bullet:
                units.append((True, " ".join(bullet)))
                bullet = None
            flush_prose()
        elif bullet is not None and (
            line[:1].isspace() or not re.search(r"[.!?:]$", bullet[-1])
        ):  # an indented line, or a wrapped one after an unfinished bullet
            bullet.append(line.strip())
        else:
            if bullet:
                units.append((True, " ".join(bullet)))
                bullet = None
            prose.append(line.strip())
    if bullet:
        units.append((True, " ".join(bullet)))
    flush_prose()
    out, seen = [], set()
    for listed, unit in units:
        unit = unit.strip()
        wanted = listed or (len(unit.split()) >= MIN_WORDS and CUES.search(unit))
        if wanted and len(unit.split()) >= 2 and unit not in seen:
            seen.add(unit)
            out.append(unit)
    return out


def _covers(quote: str, sentence: str) -> bool:
    q, s = _norm(quote), _norm(sentence)
    if not q:
        return False
    if q in s or s in q:
        return True
    match = SequenceMatcher(None, s, q, autojunk=False).find_longest_match(
        0, len(s), 0, len(q)
    )
    return match.size >= min(len(s), MIN_OVERLAP)


def check(
    task: str, items: list[dict[str, Any]], steps: dict[int, Any]
) -> dict[str, Any]:
    """What the ledger leaves open against the task's text and the steps it cites."""
    task_n = _norm(task)
    items = [i for i in items if isinstance(i, dict)]
    not_found = [
        str(i.get("quote", ""))[:160]
        for i in items
        if _norm(i.get("quote")) not in task_n
    ]
    quotes = [str(i.get("quote", "")) for i in items if _norm(i.get("quote")) in task_n]
    uncovered = [s for s in sentences(task) if not any(_covers(q, s) for q in quotes)]
    statuses = {k: 0 for k in STATUSES}
    for item in items:
        statuses[item.get("status") if item.get("status") in STATUSES else "open"] += 1
    met = [
        evidence.Line(
            f"{str(i.get('quote', ''))[:100]} -> {i.get('shown_by', '')}",
            [
                n
                for m in evidence.CITE.finditer(str(i.get("shown_by", "")))
                for n in evidence._steps(m.group(1))
            ],
        )
        for i in items
        if i.get("status") == "met"
    ]
    return {
        "items": len(items),
        "statuses": statuses,
        "not_found": not_found,
        "uncovered": uncovered,
        "citation_problems": evidence._check("met item", met, steps),
        "not_met": [
            str(i.get("quote", ""))[:160]
            for i in items
            if i.get("status") in ("open", "not_met", "unsure")
        ],
    }


def _listed(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    shown = "\n".join(
        f"- {x if x.startswith('- ') is False else x[2:]}" for x in lines[:MAX_LISTED]
    )
    more = len(lines) - MAX_LISTED
    return f"{title}\n{shown}" + (f"\n(and {more} more)" if more > 0 else "") + "\n"


def render(row: dict[str, Any]) -> str:
    counts = ", ".join(f"{v} {k}" for k, v in row["statuses"].items() if v)
    text = f"ledger: {row['items']} items ({counts or 'none'})\n"
    text += _listed(
        "Requirement sentences of the task that no item quotes:", row["uncovered"]
    )
    text += _listed(
        "Quotes not found in the task (copy its words exactly):", row["not_found"]
    )
    text += _listed(
        "Citation problems:", [p.removeprefix("- ") for p in row["citation_problems"]]
    )
    return text.rstrip()


def use(s: Any, args: dict[str, Any]) -> str:
    """The requirements tool: replace the ledger, check it, and return what it leaves open."""
    items = args.get("items")
    if not isinstance(items, list):
        return "error: items must be a list of requirement objects"
    s.ledger = items
    row = check(s.task, items, s.step_tools)
    s.trace("ledger", **{k: v for k, v in row.items() if k != "not_met"})
    return render(row)


def at_finish(s: Any) -> tuple[str, bool] | None:
    """Check the ledger at a finish; the first finish is held once if anything is open. Recorded either way."""
    row = check(s.task, getattr(s, "ledger", []), s.step_tools)
    rows = s.result.extras.setdefault("ledger", [])
    first, left = not rows, s.remaining()
    problems = []
    if not row["items"]:
        problems.append(
            "- no ledger: record the task's requirements with the requirements tool"
        )
    problems += [
        f"- not quoted by any item: {u}" for u in row["uncovered"][:MAX_LISTED]
    ]
    problems += [f"- not met or not settled: {q}" for q in row["not_met"][:MAX_LISTED]]
    problems += row["citation_problems"][:MAX_LISTED]
    shown = bool(first and problems and left > AUDIT_MIN_S)
    rows.append(
        {**row, "shown": shown, "step": s.result.steps, "remaining_s": round(left, 1)}
    )
    s.trace(
        "ledger_check", shown=shown, **{k: v for k, v in row.items() if k != "not_met"}
    )
    return (HELD.format(problems="\n".join(problems)), False) if shown else None

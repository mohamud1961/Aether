"""Step-cited finishing: claims cite the steps they rest on, open choices are named, completion is asserted.

Every N1 P1 wrong finish (12 of 12) claimed "verified" or "validated" in free prose; nothing tied a claim to an
observation, and the choices that decided the outcome were never named.

With ``CoreConfig.evidence`` on:
- every tool result carries its step number;
- the finish takes ``assertion`` (complete | incomplete | uncertain: a report of the delivered state, separate from
  the run's status and from the grade), ``claims`` (one per line, each ending with the steps it rests on, e.g.
  ``[steps 12, 15]``), ``decisions`` (``choice | alternatives | what in the task or input selects it [steps N]``)
  and ``unverified``;
- the first finish is checked for **citation shape only**: a claim or decision citing no step, a step that does not
  exist, a step whose tool failed, only file writes, or a read of a file that a later write_file/edit_file changed.
  It cannot tell whether a cited output says what the claim says, whether every requirement is covered, or whether
  a shell or Python step wrote rather than observed (Codex review, 15 Oct: a red file cited as blue, an omitted
  second deliverable and a shell writer all pass it). A clean result means the citations are well formed, nothing
  more. With problems and an assertion of complete, they are shown once;
- an honest incomplete or uncertain assertion is never treated as a citation problem. When it comes with a real
  share of the time limit left, the finish is held once with the time left, because the objective is the delivered
  task: the assertion reports the state, it is not a way out. The next finish ends the work either way.
Every check is recorded on the row (``extras.evidence``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
import posixpath
from typing import Any

CITE = re.compile(r"\[\s*steps?\s+([0-9][0-9,\s\-–and]*)\]", re.IGNORECASE)
WRITES = frozenset({"write_file", "edit_file"})
NOT_EVIDENCE = WRITES | {"finish"}
AUDIT_MIN_S = 60.0  # with less time left the check is recorded but not shown
ASSERTIONS = ("complete", "incomplete", "uncertain")
PERSIST_MIN_S, PERSIST_SHARE = (
    120.0,
    0.25,
)  # an incomplete finish is held once only with this much time left


@dataclass(frozen=True)
class Step:
    """What the runtime knows about a step without judging it: the tool, whether the tool reported an error, and
    the file a read_file read or a write_file/edit_file wrote (absolute). Shell and Python effects are unknown."""

    tool: str
    failed: bool = False
    read: str = ""
    wrote: str = ""


def step_fact(name: str, args: dict[str, Any], out: str, workdir: str) -> Step:
    path = str(args.get("path") or "")
    path = posixpath.normpath(posixpath.join(workdir, path)) if path else ""
    return Step(
        name,
        failed=out.startswith("error:"),
        read=path if name == "read_file" else "",
        wrote=path if name in WRITES else "",
    )


EVIDENCE_FINISH = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": "End the task. Use when every requirement is met and shown, or no time is left.",
        "parameters": {
            "type": "object",
            "properties": {
                "assertion": {
                    "type": "string",
                    "enum": list(ASSERTIONS),
                    "description": "Your report of the delivered state: complete only if every requirement is met "
                    "and you have shown it. A report, not a way out: while time and useful next steps remain, keep "
                    "working.",
                },
                "summary": {
                    "type": "string",
                    "description": "One or two sentences on the final state.",
                },
                "claims": {
                    "type": "string",
                    "description": "One line per requirement of the task: what holds, ending with the steps whose "
                    "output shows it, e.g. 'out.json parses and has 700 keys [steps 14, 15]'.",
                },
                "decisions": {
                    "type": "string",
                    "description": "One line per choice the task did not dictate (a convention, definition, "
                    "method, source, transform): 'choice | alternatives | what in the task or input selects it "
                    "[steps N]'. Empty only if there were none.",
                },
                "unverified": {
                    "type": "string",
                    "description": "Anything your result rests on that you have not shown. Empty if nothing.",
                },
            },
            "required": ["assertion", "summary", "claims", "decisions", "unverified"],
        },
    },
}

EVIDENCE_DOC = """
Evidence: every tool result shows its step number. When you finish, each claim cites the steps whose output shows \
it, and you name every choice the task did not dictate, with its alternatives and what in the task or its inputs \
selects it. A step supports a claim only if its output would have been different were the claim false: agreement \
between your result and your own reconstruction of it, or with an example's values, shows nothing about a choice \
both share. Say whether the work is complete, incomplete or uncertain as it truly is."""

AUDIT = """[citation check: the finish did not take effect]
{problems}

Fix what is missing, or show it, or, if the finish is right as it stands, call finish again; the next finish \
ends the work."""
PERSIST = """[the finish did not take effect: you report the work as {assertion}, with {left:.0f}s of {limit:.0f}s left]
The task is to deliver it. Keep working on what is missing; if you are sure nothing more can be done, call finish \
again; the next finish ends the work."""


@dataclass
class Line:
    text: str
    steps: list[int] = field(default_factory=list)


def _steps(spec: str) -> list[int]:
    out: list[int] = []
    for part in re.split(r"[,\s]+|and", spec):
        part = part.strip()
        if not part:
            continue
        bounds = re.split(r"[\-–]", part)
        if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
            lo, hi = int(bounds[0]), int(bounds[1])
            out.extend(range(lo, hi + 1) if 0 <= hi - lo <= 50 else (lo, hi))
        elif part.isdigit():
            out.append(int(part))
    return out


def parse(text: str) -> list[Line]:
    """One entry per non-empty line, with every step number it cites."""
    lines = []
    for raw in str(text or "").splitlines():
        raw = raw.strip().lstrip("-*• ").strip()
        if raw:
            lines.append(
                Line(raw, [n for m in CITE.finditer(raw) for n in _steps(m.group(1))])
            )
    return lines


def _check(kind: str, lines: list[Line], steps: dict[int, Step]) -> list[str]:
    problems = []
    for line in lines:
        cited = [steps.get(n) for n in line.steps]
        missing = [n for n in line.steps if n not in steps]
        if not line.steps:
            problems.append(f"- {kind} cites no step: {line.text}")
        elif missing:
            problems.append(
                f"- {kind} cites steps that do not exist ({', '.join(map(str, missing))}): {line.text}"
            )
        elif all(c.tool in NOT_EVIDENCE for c in cited):
            problems.append(
                f"- {kind} cites only file writes, which show what was made, not that it holds: {line.text}"
            )
        else:
            failed = [n for n in line.steps if steps[n].failed]
            stale = [
                n
                for n in line.steps
                if steps[n].read
                and any(m > n and steps[m].wrote == steps[n].read for m in steps)
            ]
            if failed:
                problems.append(
                    f"- {kind} cites steps whose tool failed ({', '.join(map(str, failed))}): {line.text}"
                )
            if stale:
                problems.append(
                    f"- {kind} cites reads of files changed by a later step ({', '.join(map(str, stale))}): "
                    f"{line.text}"
                )
    return problems


def audit(args: dict[str, Any], steps: dict[int, str]) -> dict[str, Any]:
    """The citation-shape check of a finish. ``steps`` maps each step number to what the runtime knows of it."""
    claims, decisions = parse(args.get("claims", "")), parse(args.get("decisions", ""))
    decisions = [
        d for d in decisions if d.text.lower().rstrip(".") not in {"none", "n/a", "no"}
    ]
    unverified = str(args.get("unverified", "")).strip()
    if unverified.lower().rstrip(".") in {"none", "nothing", "n/a", "no"}:
        unverified = ""
    problems = _check("claim", claims, steps) + _check("decision", decisions, steps)
    if not claims:
        problems.append(
            "- no claims: list what holds for each requirement, with the steps that show it"
        )
    assertion = str(args.get("assertion", ""))
    return {
        "assertion": assertion,
        "claims": len(claims),
        "decisions": len(decisions),
        "decision_lines": [d.text for d in decisions],
        "unverified": unverified,
        "citation_problems": problems,
    }


def open_questions(row: dict[str, Any]) -> str:
    """The choices the work made, without its reasons, for the verifier to settle from the task and inputs."""
    lines = []
    for text in row.get("decision_lines", []):
        parts = [p.strip() for p in CITE.sub("", text).split("|")]
        lines.append(" / ".join(p for p in parts[:2] if p))
    if row.get("unverified"):
        lines.append(f"stated as not shown: {row['unverified']}")
    return "\n".join(f"- {x}" for x in lines) or "(none named)"


def at_finish(s: Any, args: dict[str, Any]) -> tuple[str, bool] | None:
    """Check this finish. The first finish is held once: with citation problems under an assertion of complete,
    or with an incomplete/uncertain assertion and a real share of the time left. Otherwise None and the finish
    proceeds. Every check is recorded."""
    row = audit(args, s.step_tools)
    rows = s.result.extras.setdefault("evidence", [])
    left, first = s.remaining(), not rows
    note = ""
    if (
        first
        and row["assertion"] == "complete"
        and row["citation_problems"]
        and left > AUDIT_MIN_S
    ):
        note = AUDIT.format(problems="\n".join(row["citation_problems"]))
    elif (
        first
        and row["assertion"] != "complete"
        and left > max(PERSIST_MIN_S, PERSIST_SHARE * s.timeout_s)
    ):
        note = PERSIST.format(assertion=row["assertion"], left=left, limit=s.timeout_s)
    shown = "citation" if note.startswith("[citation") else "persist" if note else ""
    rows.append(
        {**row, "shown": shown, "step": s.result.steps, "remaining_s": round(left, 1)}
    )
    s.trace("evidence_check", shown=shown, **row)
    return (note, False) if note else None

"""Evidence-linked finishing: claims cite the steps that show them, choices the task left open are named.

Every N1 P1 wrong finish (12 of 12) claimed "verified" or "validated" in free prose; one said its design "remains
unverified" and still ended the run. Nothing tied a claim to an observation, and the choices that decided the
outcome (an address base taken from an example, a melting-temperature method, a sequence source) were never named,
so neither the solver nor the verifier was pointed at them.

With ``CoreConfig.evidence`` on:
- every tool result carries its step number, so a claim can cite it;
- the finish takes ``claims`` (one per line, each ending with the steps that show it, e.g. ``[steps 12, 15]``),
  ``decisions`` (one per line: ``choice | alternatives | what in the task or input selects it [steps N]``) and
  ``unverified`` (anything not shown, or empty);
- the first finish is audited mechanically, never judged: a claim or decision with no cited step, a cited step that
  does not exist, a citation of only file writes (a write shows what was made, not that it works), and anything
  stated as unverified are shown back once. The solver decides; its next finish ends the work (or goes to the
  verifier when that is on). The audit is recorded on the row either way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CITE = re.compile(r"\[\s*steps?\s+([0-9][0-9,\s\-–and]*)\]", re.IGNORECASE)
WRITES = frozenset({"write_file", "edit_file"})
NOT_EVIDENCE = WRITES | {"finish"}
AUDIT_MIN_S = 60.0  # with less time left the audit is recorded but not shown

EVIDENCE_FINISH = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": "End the task. Use when every requirement is met and shown, or no time is left.",
        "parameters": {
            "type": "object",
            "properties": {
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
            "required": ["summary", "claims", "decisions", "unverified"],
        },
    },
}

EVIDENCE_DOC = """
Evidence: every tool result shows its step number. When you finish, each claim cites the steps whose output shows \
it, and you name every choice the task did not dictate, with its alternatives and what in the task or its inputs \
selects it. A step is evidence for a claim only if its output would have been different were the claim false: \
agreement between your result and your own reconstruction of it, or with an example's values, shows nothing about \
a choice both share. Where the task does not ask for a transformation (a rebase, a rescaling, a reordering), the \
reading that applies none is the default; adopting one needs support from the task or its inputs."""

AUDIT = """[evidence audit: the finish did not take effect]
{problems}

Fix what is missing, or show it, or, if the finish is right as it stands, call finish again; the next finish \
ends the work."""


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


def _check(kind: str, lines: list[Line], steps: dict[int, str]) -> list[str]:
    problems = []
    for line in lines:
        if not line.steps:
            problems.append(f"- {kind} cites no step: {line.text}")
            continue
        missing = [n for n in line.steps if n not in steps]
        if missing:
            problems.append(
                f"- {kind} cites steps that do not exist ({', '.join(map(str, missing))}): {line.text}"
            )
        elif all(steps[n] in NOT_EVIDENCE for n in line.steps):
            problems.append(
                f"- {kind} cites only file writes, which show what was made, not that it holds: "
                f"{line.text}"
            )
    return problems


def audit(args: dict[str, Any], steps: dict[int, str]) -> dict[str, Any]:
    """The mechanical audit of a finish. ``steps`` maps each step number to the tool it ran."""
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
    if unverified:
        problems.append(f"- you state this is not shown: {unverified}")
    return {
        "claims": len(claims),
        "decisions": len(decisions),
        "decision_lines": [d.text for d in decisions],
        "unverified": unverified,
        "problems": problems,
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
    """Audit this finish. Returns the audit to show (finish held) the first time it finds a problem with time to
    act on it; otherwise None and the finish proceeds. Every audit is recorded."""
    row = audit(args, s.step_tools)
    rows = s.result.extras.setdefault("evidence", [])
    shown = bool(row["problems"]) and not rows and s.remaining() > AUDIT_MIN_S
    rows.append({**row, "shown": shown, "step": s.result.steps})
    s.trace("evidence_audit", shown=shown, **row)
    if shown:
        return AUDIT.format(problems="\n".join(row["problems"])), False
    return None

"""Run state kept while working: requirements whose status only the harness's own check runs can set, progress
notes, and open failures that stay in view (``CoreConfig.state``; map: RUN_STATE_MAP.md in luna_improve_20261022).

Evidence: B0 (Luna on Core, 10-22) wrong finishes include a known failed check left out of the summary
(code-from-image), requirements dropped or checked one step short of use, and runs ending at a median 8% of their
time. The N2 ledger (10-15) had the model mark its own items "met": adopted fully, no gain. SpecHarness (arXiv
2609.29921) cut false completion over 7 models with the runtime committing check results and the agent unable to mark
an item met; its "no commitment" ablation was the worst. So here:

- the model adds an item quoting the task verbatim (checked mechanically, whitespace and case aside), with a shell
  command that exits 0 only when the item holds on the delivered state;
- ``check`` runs that command in the working directory; the exit status alone sets ``passed`` or ``failed``. The
  model cannot set a status; it can close an item with ``give_up`` and a reason, which is reported as given up;
- a file-tool write after a check marks passed items ``stale`` (shell writes are not tracked during the run; every
  check is re-run at finish anyway);
- ``note`` keeps progress, breakthroughs and where the current best deliverable is; notes are never trimmed and the
  state view is shown again after any change and after a context checkpoint;
- at finish every check is re-run on the delivered state, and the task's requirement sentences that no item quotes
  are listed (the N2 coverage rule). If anything failed, is unchecked or uncovered, or no item exists, and real time
  remains, that finish is held once with the list; the next finish always ends the work.
- the final account (for people, never shown to the model) lists every item with its last harness-run result.

What it cannot do: a check the model writes encodes its own reading of the task (Q1/Q1-R), so a misread
requirement can pass its check. Check commands run with the model's own permissions in the sandbox, as terminal
commands do, and can change state like any command.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import re
import time
from typing import Any

from .env import Environment, run

CHECK_TIMEOUT_S = 60
FINISH_CHECKS_S = 180  # total time the finish re-check may take
TAIL_CHARS = 400
VIEW_NOTES = 6
MAX_ITEMS = 40
HOLD_MIN_S = 60.0  # a finish is held only with at least this much time left (and 10% of the limit)
STATUSES = ("unchecked", "passed", "failed", "stale", "given_up")
CUES = re.compile(
    r"\b(must|should|shall|needs?|required?|requires|only|exactly|at (?:least|most)|between|no|not|don't|do not|"
    r"never|always|assume|ensure|make sure|use|write|create|format|save|store|output|return|include|exclude|each|"
    r"every|all)\b",
    re.IGNORECASE,
)
BULLET = re.compile(r"^\s*(?:[*\-•]|\d+[.)])\s+")
MIN_WORDS = 4
MIN_OVERLAP = 40
MAX_LISTED = 25

STATE_TOOL = {
    "type": "function",
    "function": {
        "name": "state",
        "description": "Your run state, kept by the harness. action=require adds a requirement (quote the task's "
        "own words; give a shell check that exits 0 only when it holds on the delivered state); action=check "
        "runs an item's check now and records the result (only a check run sets passed or failed); action=note "
        "records progress, a breakthrough, or where your current best deliverable is; action=give_up closes an "
        "item you cannot meet, with the reason (it is reported as not met). Every call returns the state.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["require", "check", "note", "give_up", "show"]},
                "quote": {"type": "string", "description": "require: the task's own words, copied exactly."},
                "check": {
                    "type": "string",
                    "description": "require: a shell command, run in the working directory, that exits 0 only "
                    "when this requirement holds on the delivered state (test the real output the way it will be "
                    "used). It may also replace an item's check: give id with action=require.",
                },
                "id": {"type": "integer", "description": "check / give_up / require (replace a check): item id."},
                "text": {"type": "string", "description": "note: the note. give_up: the reason."},
            },
            "required": ["action"],
        },
    },
}

STATE_DOC = """
Run state: keep it with the state tool from the start. Add each requirement of the task with action=require, \
quoting the task's own words and giving a shell check that exits 0 only when the requirement holds on what you \
deliver, tested the way the result will be used (run the real program, fetch the real page, parse the real file, \
compare against any value the task gives). Run checks with action=check; only a check run marks an item passed or \
failed, and a failed check stays listed until it passes or you give it up with a reason. Record progress and \
breakthroughs with action=note, and as soon as you have a working version of the deliverable, save it and note \
where it is; then improve it. A failed or open item with time left means keep working. At finish every check is \
run again on the delivered state."""

FINISH_STATE = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": "End the task. Use it when every requirement's check passes on the delivered state. If an "
        "item is still failed or open and time remains, keep working on it; if you finish anyway, say in the "
        "summary which items are not met.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "One or two sentences on the final state, including anything not met.",
                },
            },
            "required": ["summary"],
        },
    },
}

HELD = """[run state: the finish did not take effect]
{problems}

{state}

Work on what is listed, or, if the finish is right as it stands, call finish again; the next finish ends the work."""


def with_state(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The tool list with the state tool before finish and finish's description tied to the state."""
    out = [s for s in specs if s["function"]["name"] != "finish"]
    return [*out, STATE_TOOL, FINISH_STATE]


@dataclass
class Item:
    id: int
    quote: str
    check: str
    status: str = "unchecked"
    exit: int | None = None
    output: str = ""
    checked_t: float | None = None
    reason: str = ""


# Quotes are matched with whitespace, case, markdown emphasis/code marks and typographic quotes and dashes set aside:
# on the 39 dev tasks a model's quote without the backticks failed 68/244 times, and Q1's anchor matching broke on
# curly quotes. Everything else must be the task's own words.
TYPOGRAPHY = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"})


def _norm(text: Any) -> str:
    text = re.sub(r"[`*]", "", str(text or "").translate(TYPOGRAPHY))
    return re.sub(r"\s+", " ", text).strip().lower()


def sentences(task: str) -> list[str]:
    """The task's requirement sentences (N2 rule): every bullet or numbered item with its continuation lines, and
    every other sentence carrying a requirement word, outside code fences."""
    units: list[tuple[bool, str]] = []
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
        elif bullet is not None and (line[:1].isspace() or not re.search(r"[.!?:]$", bullet[-1])):
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
    match = SequenceMatcher(None, s, q, autojunk=False).find_longest_match(0, len(s), 0, len(q))
    return match.size >= min(len(s), MIN_OVERLAP)


def _tail(text: str) -> str:
    text = text.strip()
    return text if len(text) <= TAIL_CHARS else "…" + text[-TAIL_CHARS:]


class RunState:
    def __init__(self, task: str, workdir: str, clock=time.monotonic) -> None:
        self.task, self.workdir, self._clock = task, workdir, clock
        self._t0 = clock()
        self.items: list[Item] = []
        self.notes: list[tuple[float, str]] = []
        self.held = False
        self.final_checked = False
        self.dirty = False  # the view should be shown again (a change, or a context checkpoint)
        self.events: list[dict[str, Any]] = []

    def _t(self) -> float:
        return round(self._clock() - self._t0, 1)

    def _item(self, args: dict[str, Any]) -> Item:
        ident = args.get("id")
        item = next((i for i in self.items if i.id == ident), None)
        if item is None:
            raise ValueError(f"state: no item with id {ident!r}; ids: {[i.id for i in self.items] or 'none yet'}")
        return item

    async def act(self, env: Environment, args: dict[str, Any], remaining_s: float) -> str:
        """One state tool call. Errors are returned as the tool's result, never raised past the loop."""
        action = args["action"]
        try:
            head = await self._act(env, action, args, remaining_s)
        except ValueError as exc:
            return f"error: {exc}\n\n{self.view()}"
        self.events.append({"t": self._t(), "action": action, "id": args.get("id"), "result": head[:200]})
        self.dirty = False  # the view goes with this result
        return f"{head}\n\n{self.view()}"

    async def _act(self, env: Environment, action: str, args: dict[str, Any], remaining_s: float) -> str:
        if action == "show":
            return "[state]\n" + "\n".join(f"note t={t:.0f}s {n}" for t, n in self.notes)
        if action == "note":
            text = str(args.get("text") or "").strip()
            if not text:
                raise ValueError("note needs text")
            self.notes.append((self._t(), text))
            return f"noted (note {len(self.notes)})"
        if action == "give_up":
            item, reason = self._item(args), str(args.get("text") or "").strip()
            if not reason:
                raise ValueError("give_up needs text: the reason the item cannot be met")
            item.status, item.reason = "given_up", reason
            return f"item {item.id} closed as not met: {reason[:200]}"
        if action == "require":
            check = str(args.get("check") or "").strip()
            if args.get("id") is not None:  # replace the check of an existing item
                item = self._item(args)
                if not check:
                    raise ValueError("require with id replaces that item's check: give check")
                item.check, item.status, item.exit, item.output, item.checked_t = check, "unchecked", None, "", None
                return f"item {item.id}: check replaced; status unchecked until it is run"
            quote = str(args.get("quote") or "").strip()
            if not quote or _norm(quote) not in _norm(self.task):
                raise ValueError("require: quote must be the task's own words, copied exactly (whitespace, case and "
                                 "markdown marks aside); it was not found in the task")
            if len(self.items) >= MAX_ITEMS:
                raise ValueError(f"at most {MAX_ITEMS} items")
            item = Item(len(self.items) + 1, quote, check)
            self.items.append(item)
            return f"item {item.id} added" + ("" if check else " (no check yet: it stays unchecked until it has one)")
        if action == "check":
            item = self._item(args)
            await self._run(env, item, min(CHECK_TIMEOUT_S, remaining_s))
            return f"item {item.id} check: {item.status} (exit {item.exit})\n{item.output}"
        raise ValueError(f"unknown action {action!r}")

    async def _run(self, env: Environment, item: Item, timeout_s: float) -> None:
        if not item.check:
            raise ValueError(f"item {item.id} has no check; give one with action=require and id={item.id}")
        if timeout_s < 1:
            raise ValueError("no time left to run a check")
        try:
            res = await run(env, item.check, timeout_s=int(timeout_s), cwd=self.workdir)
            item.exit, out = res.code, _tail(f"{res.stdout}\n{res.stderr}")
        except Exception as exc:  # a check that cannot run is not a pass
            item.exit, out = None, f"check did not run: {type(exc).__name__}: {str(exc)[:200]}"
        item.status = "passed" if item.exit == 0 else "failed"
        item.output, item.checked_t = out, self._t()

    def wrote(self) -> None:
        """A file tool wrote a file: passed items are stale until re-checked."""
        stale = False
        for item in self.items:
            if item.status == "passed":
                item.status, stale = "stale", True
        self.dirty = self.dirty or stale

    def uncovered(self) -> list[str]:
        quotes = [i.quote for i in self.items]
        return [s for s in sentences(self.task) if not any(_covers(q, s) for q in quotes)]

    def reminder(self) -> str:
        """One line for every tool result while a check is failing (so it cannot drop out of view)."""
        failed = [i for i in self.items if i.status == "failed"]
        if not failed:
            return ""
        return "[state: failing " + ", ".join(f"#{i.id} {i.quote[:50]!r}" for i in failed[:5]) + "]"

    def view(self) -> str:
        lines = ["[run state]"]
        for i in self.items:
            when = f" at t={i.checked_t:.0f}s" if i.checked_t is not None else ""
            extra = f" — {i.reason[:120]}" if i.status == "given_up" else ""
            out = f"\n      {i.output[-160:]}" if i.status == "failed" and i.output else ""
            lines.append(f"  #{i.id} [{i.status}{when}] {i.quote[:120]!r}{extra}{out}")
        if not self.items:
            lines.append("  no requirements yet")
        missing = self.uncovered()
        if missing:
            lines.append(f"  task requirement sentences no item quotes ({len(missing)}):")
            lines.extend(f"    - {s[:160]}" for s in missing[:MAX_LISTED])
        if self.notes:
            lines.append("  notes:")
            lines.extend(f"    t={t:.0f}s {n[:300]}" for t, n in self.notes[-VIEW_NOTES:])
            if len(self.notes) > VIEW_NOTES:
                lines.append(f"    ({len(self.notes) - VIEW_NOTES} earlier notes kept; action=show lists every note)")
        return "\n".join(lines)

    async def at_finish(self, env: Environment, remaining_s: float, timeout_s: float) -> tuple[bool, str]:
        """Re-run every check on the delivered state; hold the first finish once when something is open and real
        time remains. Returns (held, text for the model)."""
        budget = min(FINISH_CHECKS_S, max(0.0, remaining_s - 5))
        started = self._clock()
        for item in self.items:
            if item.check and item.status != "given_up":
                left = budget - (self._clock() - started)
                if left < 1:
                    break
                await self._run(env, item, min(CHECK_TIMEOUT_S, left))
        self.final_checked = True
        problems = []
        if not self.items:
            problems.append("- no requirements are recorded")
        for i in self.items:
            if i.status in ("failed", "unchecked", "stale"):
                problems.append(f"- #{i.id} {i.status}: {i.quote[:120]!r}")
        missing = self.uncovered()
        if missing:
            problems.append(f"- {len(missing)} task requirement sentence(s) no item quotes")
        left = remaining_s - (self._clock() - started)
        hold = bool(problems) and not self.held and left >= max(HOLD_MIN_S, 0.1 * timeout_s)
        self.events.append({"t": self._t(), "action": "finish", "held": hold, "problems": len(problems)})
        if hold:
            self.held = True
            return True, HELD.format(problems="\n".join(problems), state=self.view())
        return False, ""

    def account(self) -> str:
        """For the final account (people only): every item with its last harness-run result."""
        lines = ["## Run state (check results from the harness's own runs)"]
        if not self.final_checked:
            lines.append("- the run did not reach finish: results below are from the last check during the run")
        for i in self.items:
            when = f"t={i.checked_t:.0f}s" if i.checked_t is not None else "never run"
            lines.append(f"- #{i.id} {i.status} ({when}, exit {i.exit}): {i.quote[:200]!r}")
            if i.check:
                lines.append(f"    check: {i.check[:300]}")
            if i.status == "given_up":
                lines.append(f"    given up: {i.reason[:300]}")
            elif i.output and i.status != "passed":
                lines.append(f"    output: {i.output[-300:]}")
        if not self.items:
            lines.append("- no requirements were recorded")
        missing = self.uncovered()
        if missing:
            lines.append(f"- task requirement sentences no item quotes: {len(missing)}")
            lines.extend(f"    - {s[:200]}" for s in missing[:MAX_LISTED])
        for t, n in self.notes:
            lines.append(f"- note t={t:.0f}s: {n[:500]}")
        return "\n".join(lines)

    def record(self) -> dict[str, Any]:
        return {
            "items": [asdict(i) for i in self.items],
            "notes": [{"t": t, "text": n} for t, n in self.notes],
            "uncovered": self.uncovered(),
            "held": self.held,
            "final_checked": self.final_checked,
            "events": self.events,
        }

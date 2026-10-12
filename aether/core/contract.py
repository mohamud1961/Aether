"""Acceptance contract: executable checks written from the task before the work, run when the worker finishes.

Judging a finished answer anchors the judge on it: on fixed known-bad states the finish verifier (verify.py) let
an answer "meet" a stated length of 23, having measured it, and reasoned an edge-direction rule
backwards. Checks written before any answer exists cannot be talked round; their exit code decides.

- At the start, a separate call of the model, with no tools, gets the task and a mechanical description of the
  untouched container (files, first lines, installed tools) and writes one shell check per requirement (exit 0
  = met). Each check is tried on a no-network clone of the untouched state: one that cannot run, or that passes
  before any work was done (so it cannot tell done from not done), is sent back. Those are facts read from exit
  codes, not judgments. With no tools the writer cannot explore, solve the task or leave helper files behind.
- The worker receives the checks as soon as they exist: its definition of done, runnable at any time.
- At finish the harness runs every check in a clone of the final state. A failing check holds the finish with
  its command and output. The worker fixes the work, or disputes the check by quoting the task sentence it
  contradicts; a fresh call rules on that one question (check vs task), never on the work. A voided check is
  dropped; everything is recorded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import time
from typing import Any, Callable

from .env import Environment, run
from .provider import ChatProvider, ProviderError
from . import verify as V

WRITER_BUDGET_S = 300.0
# One writer call may use at most this much of the budget. V2 dna/protein: the first call reasoned past the whole
# 300 s budget (working out primers and melting temperatures, the answer itself) and no contract was written.
# A call that is cut off (time or output limit) is retried at low effort with a note.
WRITER_CALL_S = 150.0
CUT_OVERRIDES = {"reasoning_effort": "low"}
CUT_NOTE = ("Your last attempt was cut off while reasoning, before submitting. Do not work out the answer: write "
            "checks of what the task states about the result, and submit them now with submit_checks.")
CHECK_TIMEOUT_S = 60
MAX_OUTPUT_CHARS = 600

SUBMIT_CHECKS = {"type": "function", "function": {
    "name": "submit_checks",
    "description": "Submit the acceptance checks and stop. One entry per requirement of the task.",
    "parameters": {"type": "object", "properties": {"checks": {"type": "array", "items": {
        "type": "object", "properties": {
            "requirement": {"type": "string", "description": "The requirement, quoted from the task."},
            "command": {"type": "string", "description": "Shell command run from the working directory; exit "
                                                         "0 if and only if the requirement is met."},
            "holds_before": {"type": "boolean", "description": "True only for a requirement already met before "
                                                               "the work (something the work must preserve)."},
            "sentences": {"type": "array", "items": {"type": "integer"},
                          "description": "Numbers of the task sentences this check enforces."},
        }, "required": ["requirement", "command", "sentences"]}},
        "context_sentences": {"type": "array", "items": {"type": "integer"},
                              "description": "Numbers of the task sentences that state no requirement."},
        "example": {"type": "string", "description": "Shell commands that create an invented example of a "
                                                     "finished state (its outputs, with made-up values that "
                                                     "satisfy the task as stated); every check must pass on it."}},
        "required": ["checks", "context_sentences", "example"]}}}

WRITER_PROMPT = """Before anyone works on the task below, write the acceptance checks that will decide whether \
it has been done. You are given the task, split into numbered sentences, and a description of the container as \
it is before the work. The checks will run in that container after the work, with only the tools listed \
(nothing can be installed).

Go through every sentence. A sentence that states an output, constraint, rule, format or convention (lengths, \
orderings, which column means what, tie-breaking rules) is a requirement: write a shell command that exits 0 \
if and only if the finished state satisfies it, and list the sentence numbers it enforces. List every other \
sentence in context_sentences. Each check tests what the task states about the result: parse the produced \
files and compare them with it. Where the task gives a rule, compute the rule in the command and apply it to \
every case it covers. Do not re-derive the answer or how it was obtained (redoing the analysis, searching for \
the answer yourself, testing for a particular value): you do not know the answer, and a blind re-derivation \
would fail correct work. Each command is self-contained (no helper files) and depends only on the outcome.

Also write example: shell commands that create an invented example of a finished state, its outputs only, \
with made-up values that satisfy everything the task states (build them in code where that is easier, for \
example a string of the stated length). It shows your checks accept a correct result they have never seen.

Every check is tried at once in two copies of the container. On the unfinished state it must run (no missing \
tool, module or file of its own, no syntax error) and fail, since the work has not been done; mark \
holds_before only for a requirement that is already met before the work and must stay so. On your example it \
must pass. A check that fails on the example is wrong, or the example is: fix whichever it is."""

RULING = {"type": "function", "function": {
    "name": "ruling",
    "description": "Rule on whether the disputed check is a valid test of the task.",
    "parameters": {"type": "object", "properties": {
        "valid": {"type": "boolean"},
        "task_sentence": {"type": "string", "description": "The sentence of the task your ruling rests on."},
        "reason": {"type": "string"}}, "required": ["valid", "task_sentence", "reason"]}}}

ARBITER_PROMPT = """An acceptance check for the task below failed and is disputed. Rule only on the check, not \
on the work: is it a valid test of what the task states? It is invalid if it demands something the task does \
not state, contradicts the task, or failed for a reason the work cannot change (a missing tool or module, a \
broken command). It is valid if the task states the requirement it tests and its failure reflects the state. \
Quote the task sentence your ruling rests on."""

# Interpreter and shell errors meaning a check cannot run at all (exit codes 126/127 are checked separately).
_CANNOT_RUN = ("ModuleNotFoundError", "ImportError", "SyntaxError", "Syntax error", "can't open file",
               "command not found")


@dataclass(frozen=True)
class Check:
    id: int
    requirement: str
    command: str


@dataclass
class Contract:
    checks: list[Check] = field(default_factory=list)
    turns: int = 0
    error: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    voided: list[dict[str, Any]] = field(default_factory=list)
    dropped: list[dict[str, Any]] = field(default_factory=list)  # could not run, or passed before any work
    unconfirmed: list[dict[str, Any]] = field(default_factory=list)  # kept; disagreed with the writer's example

    def render(self) -> str:
        lines = ["[acceptance checks] Written from the task alone, before your work, by a separate call that saw "
                 "only the task and the starting container. When you call finish, each is run in a copy of your "
                 "final state and must exit 0. Run them yourself whenever useful. Change only the work itself: never "
                 "edit what a check reads just to make it pass (logs, history, timestamps, the check's inputs). If "
                 "one contradicts the task, finish with a dispute quoting the task sentence."]
        for c in self.checks:
            lines += [f"{c.id}. {c.requirement}", f"   $ {c.command}"]
        return "\n".join(lines)


@dataclass(frozen=True)
class CheckResult:
    check: Check
    code: int
    output: str

    @property
    def passed(self) -> bool:
        return self.code == 0


def _cannot_run(code: int, text: str) -> bool:
    return code in (126, 127) or any(m in text for m in _CANNOT_RUN)


async def run_checks(env: Environment, checks: list[Check], workdir: str) -> list[CheckResult]:
    results = []
    for c in checks:
        res = await run(env, c.command, timeout_s=CHECK_TIMEOUT_S, cwd=workdir)
        text = (res.stdout + res.stderr).strip()
        results.append(CheckResult(c, res.code, text[-MAX_OUTPUT_CHARS:]))
    return results


ENV_SUMMARY = r"""cd {workdir} 2>/dev/null || exit 0
echo "== working directory {workdir}"; ls -la | head -40
echo "== files (first lines of text files)"
find . -maxdepth 3 -type f -size -50M 2>/dev/null | head -40 | while read -r f; do
  printf -- '--- %s (%s bytes)\n' "$f" "$(wc -c < "$f")"
  if grep -Iq . "$f" 2>/dev/null; then head -n 5 "$f" | cut -c1-200; else echo "(binary)"; fi
done
echo "== tools"; for t in sh bash python3 perl awk sed grep jq node Rscript gcc file od xxd sqlite3 git curl; do
  command -v "$t" >/dev/null 2>&1 && printf '%s ' "$t"; done; echo
echo "== python modules"; python3 -c "import importlib.util as u; print(' '.join(m for m in ('numpy', 'pandas', \
'scipy', 'networkx', 'PIL', 'yaml', 'requests', 'pytest') if u.find_spec(m)) or '(none of the common ones)')" \
2>/dev/null || echo "(no python3)"
"""
MAX_ROUNDS = 3


def sentences(task: str) -> list[str]:
    """The task split into sentences, for coverage: wrapped lines are joined; blank lines and list items
    (-, *, 1. or 1)) start a new block; blocks are split at sentence ends."""
    blocks: list[str] = []
    for line in task.splitlines():
        text = line.strip()
        if not text:
            blocks.append("")
        elif re.match(r"([-*\u2022]|\d+[.)])\s", text) or not blocks or not blocks[-1]:
            blocks.append(text)
        else:
            blocks[-1] += " " + text
    out = []
    for block in blocks:
        out += [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])", block) if p.strip()]
    return out


def _problem(r: CheckResult, holds_before: bool) -> str:
    if _cannot_run(r.code, r.output):
        return "cannot run"
    if r.code == 124:
        return "timed out"
    if r.passed and not holds_before:
        return "passes before any work was done, so it cannot tell done from not done"
    if not r.passed and holds_before:
        return "is marked holds_before but fails before the work"
    return ""


async def _on_example(env: Environment, example: str, checks: list[Check], workdir: str
                      ) -> tuple[str, list[CheckResult]]:
    """Run the writer's example in a sibling of the untouched clone, then every check there."""
    sibling = await env.sibling()
    try:
        made = await run(sibling, example, timeout_s=CHECK_TIMEOUT_S * 2, cwd=workdir)
        if made.code != 0:
            return f"exit {made.code}: {(made.stdout + made.stderr).strip()[-300:]}", []
        return "", await run_checks(sibling, checks, workdir)
    finally:
        await sibling.close()


async def write(provider: ChatProvider, env: Environment, *, task: str, workdir: str,
                log: Callable[[dict[str, Any]], None] = lambda row: None) -> Contract:
    """Write the contract for ``env``: a no-network clone of the container before any work. The writer has no
    tools (it cannot explore, solve, or leave helper files); each submission is tried on the clone and any check
    that cannot run, or that cannot tell the unfinished state from a finished one, is sent back."""
    contract = Contract()
    summary = (await run(env, ENV_SUMMARY.format(workdir=workdir), timeout_s=60)).stdout[-8_000:]
    numbered = sentences(task)
    listing = "\n".join(f"[{i}] {t}" for i, t in enumerate(numbered, 1))
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": WRITER_PROMPT},
        {"role": "user", "content": f"TASK:\n{task}\n\nTASK SENTENCES:\n{listing}\n\n"
                                    f"CONTAINER BEFORE THE WORK:\n{summary}"}]
    deadline = time.monotonic() + WRITER_BUDGET_S
    overrides: dict[str, Any] | None = None
    try:
        for round_no in range(1, MAX_ROUNDS + 1):
            call_end = min(deadline, time.monotonic() + WRITER_CALL_S)
            contract.turns = round_no
            try:
                turn = await provider.complete(V._request(messages), [SUBMIT_CHECKS], max_tokens=16_384,
                                               remaining_s=lambda: call_end - time.monotonic(), overrides=overrides)
            except ProviderError as exc:
                if not exc.deadline or deadline - time.monotonic() < 30:
                    raise
                log({"round": round_no, "cut": "time", "seconds": WRITER_CALL_S})
                messages.append({"role": "user", "content": CUT_NOTE})
                overrides = CUT_OVERRIDES
                continue
            for k, v in turn.usage.items():
                contract.usage[k] = contract.usage.get(k, 0) + v
            messages.append(turn.assistant_message())
            calls = [c for c in turn.tool_calls if (c.get("function") or {}).get("name") == "submit_checks"]
            overrides = CUT_OVERRIDES if turn.finish_reason == "length" and not calls else None
            if not calls:
                log({"round": round_no, "cut": "length" if overrides else "", "reasoning": turn.reasoning[-2000:]})
                messages.append({"role": "user", "content": CUT_NOTE if overrides else
                                 "Submit the checks with submit_checks."})
                continue
            try:
                args = json.loads(calls[0]["function"].get("arguments") or "{}")
            except json.JSONDecodeError as exc:
                messages.append({"role": "tool", "tool_call_id": calls[0]["id"],
                                 "content": f"Your submission was not valid JSON ({exc}); submit it again."})
                continue
            raw = [c for c in args.get("checks") or [] if isinstance(c, dict) and c.get("command")]
            checks = [Check(i, str(c.get("requirement", "")), str(c["command"])) for i, c in enumerate(raw, 1)]
            before = {c.id: bool(r.get("holds_before")) for c, r in zip(checks, raw)}
            results = await run_checks(env, checks, workdir)
            problems = {r.check.id: _problem(r, before[r.check.id]) for r in results}
            example = str(args.get("example") or "")
            example_error, on_example = (await _on_example(env, example, checks, workdir) if example.strip()
                                         else ("no example given", []))
            disputed = {r.check.id: f"fails on your example of a finished state (exit {r.code}: "
                                    f"{r.output[-200:] or 'no output'})" for r in on_example
                        if not r.passed and not problems[r.check.id]}
            covered = {int(n) for r in raw for n in r.get("sentences") or [] if str(n).isdigit()}
            covered |= {int(n) for n in args.get("context_sentences") or [] if str(n).isdigit()}
            missing = [i for i in range(1, len(numbered) + 1) if i not in covered]
            log({"round": round_no, "reasoning": turn.reasoning, "checks": raw, "missing_sentences": missing,
                 "example": example, "example_error": example_error,
                 "on_example": [{"check": r.check.id, "exit": r.code} for r in on_example],
                 "pristine": [{"check": r.check.id, "exit": r.code, "output": r.output[-200:],
                               "problem": problems[r.check.id]} for r in results]})
            # The example is feedback, not a filter: when a check and the example disagree either may be wrong (a
            # rule computed in code beats a hand-written example), so after the last round a check that passed
            # the trial on the unfinished state is kept and its disagreement recorded.
            good = [c for c in checks if not problems[c.id]]
            settled = not example_error and not disputed and not missing
            if checks and len(good) == len(checks) and settled or round_no == MAX_ROUNDS:
                contract.unconfirmed = [{"check": c.requirement, "problem": disputed.get(c.id) or example_error}
                                        for c in good if c.id in disputed or example_error]
                contract.checks = [Check(i, c.requirement, c.command) for i, c in enumerate(good, 1)]
                contract.dropped = [{"requirement": c.requirement, "command": c.command, "problem": problems[c.id]}
                                    for c in checks if problems[c.id]]
                if not contract.checks:
                    contract.error = "no check survived the trial on the unfinished state"
                return contract
            messages += [
                {"role": "tool", "tool_call_id": calls[0]["id"],
                 "content": "Tried on the unfinished state (and on your example):\n" +
                 "\n".join(f"{r.check.id}. {r.check.requirement[:150]}\n   exit {r.code}: "
                           f"{r.output[-300:] or '(no output)'}" + (
                               f"\n   PROBLEM: it {problems[r.check.id] or disputed.get(r.check.id)}"
                               if problems[r.check.id] or r.check.id in disputed else "")
                           for r in results) +
                 (f"\nSentences neither enforced by a check nor listed as context: {missing}." if missing else "") +
                 (f"\nYour example did not run: {example_error}" if example_error else "") +
                 "\nFix these and submit all checks again."}]
        contract.error = "no checks submitted"
    except Exception as exc:
        contract.error = f"{type(exc).__name__}: {exc}"
    return contract


async def arbitrate(provider: ChatProvider, *, task: str, result: CheckResult, dispute: str,
                    remaining_s: Callable[[], float]) -> dict[str, Any]:
    """One call, no tools: does the disputed check test what the task states? It sees the check, its result and
    the dispute (with any evidence the harness itself ran), never the worker's account of its work."""
    messages = [{"role": "system", "content": ARBITER_PROMPT},
                {"role": "user", "content": f"TASK:\n{task}\n\nREQUIREMENT (as the check's author quoted it):\n"
                                            f"{result.check.requirement}\n\nCHECK:\n{result.check.command}\n\n"
                                            f"RESULT: exit {result.code}\n{result.output}\n\nDISPUTE:\n{dispute}"}]
    turn = await provider.complete(messages, [RULING], max_tokens=8_192, remaining_s=remaining_s)
    for call in turn.tool_calls:
        if (call.get("function") or {}).get("name") == "ruling":
            ruling = json.loads(call["function"].get("arguments") or "{}")
            return {"valid": bool(ruling.get("valid", True)), "task_sentence": str(ruling.get("task_sentence", "")),
                    "reason": str(ruling.get("reason", "")), "usage": turn.usage}
    return {"valid": True, "task_sentence": "", "reason": "the arbiter gave no ruling; the check stands",
            "usage": turn.usage}


def feedback(failed: list[CheckResult], rulings: dict[int, dict[str, Any]]) -> str:
    lines = ["[acceptance] These checks failed in a copy of your final state:"]
    for r in failed:
        lines += [f"{r.check.id}. {r.check.requirement}", f"   $ {r.check.command}",
                  f"   exit {r.code}: {r.output or '(no output)'}"]
        ruling = rulings.get(r.check.id)
        if ruling:
            lines.append(f"   your dispute was rejected: \"{ruling['task_sentence']}\" -- {ruling['reason']}")
    lines.append("Reproduce each failure and fix the work, then finish again. If a check itself contradicts the "
                 "task, do not change correct work to satisfy it: finish with disputes [{check, task_sentence, "
                 "reason, evidence_command}]; the command is run on a copy of your final state and its output "
                 "goes to an independent ruling on the check.")
    return "\n".join(lines)


async def finish_checks(provider: ChatProvider, env: Environment, contract: Contract, *, task: str, workdir: str,
                        disputes: list[dict[str, Any]], make_clone: Callable[[Environment], Any],
                        remaining_s: Callable[[], float]) -> dict[str, Any]:
    """Run the contract in a clone of the final state; resolve disputes of failing checks."""
    t0 = time.monotonic()
    clone = await make_clone(env)
    try:
        results = await run_checks(clone, contract.checks, workdir)
        by_id = {r.check.id: r for r in results}
        open_disputes: list[tuple[CheckResult, str]] = []
        for d in disputes:
            try:
                cid = int(d.get("check"))
            except (TypeError, ValueError):
                continue
            r = by_id.get(cid)
            if r is None or r.passed or any(o[0].check.id == cid for o in open_disputes):
                continue
            dispute = f"\"{d.get('task_sentence', '')}\" -- {d.get('reason', '')}"
            evidence = str(d.get("evidence_command") or "").strip()
            if evidence:  # run by the harness in the same copy, so the arbiter sees real output, not a claim
                ev = await run(clone, evidence, timeout_s=CHECK_TIMEOUT_S, cwd=workdir)
                dispute += (f"\nEVIDENCE (run by the harness in a copy of the final state):\n$ {evidence}\n"
                            f"exit {ev.code}: {(ev.stdout + ev.stderr).strip()[-MAX_OUTPUT_CHARS:]}")
            open_disputes.append((r, dispute))
    finally:
        await clone.close()
    rulings: dict[int, dict[str, Any]] = {}
    for r, dispute in open_disputes:
        cid = r.check.id
        rulings[cid] = await arbitrate(provider, task=task, result=r, dispute=dispute, remaining_s=remaining_s)
        if not rulings[cid]["valid"]:
            contract.voided.append({"check": cid, "requirement": r.check.requirement, "command": r.check.command,
                                    "dispute": dispute, "ruling": rulings[cid]})
    voided = {v["check"] for v in contract.voided}
    contract.checks = [c for c in contract.checks if c.id not in voided]
    failed = [r for r in results if not r.passed and r.check.id not in voided]
    return {"status": "hold" if failed else "pass", "failed": failed, "rulings": rulings,
            "results": [{"check": r.check.id, "exit": r.code, "output": r.output[-200:]} for r in results],
            "seconds": round(time.monotonic() - t0, 1)}


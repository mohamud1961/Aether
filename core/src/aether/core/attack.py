"""Attack checks run on a clone at the finish (AETHER_CORE_RIVAL=attack; CH2, user design, 3 Nov 2026).

Why: asked before any work where finished work is likely to be silently wrong, a fresh Luna names the deciding fork
(fk2 4/6; fk4, which separates explicit requirements from ranked guesses and is told that a promise is not a
dependency, 6/6), but a list of concerns shown to the worker derails literal tasks (dc1 sanitize 0/9) and a raw
fact is read as confirmation (P2 0/12). CH1 forbade installs, hid the machine facts and ran in the live container:
5/9 check sets could not run (research/core_mission_20261028/ch1, fk3, fk4).

Here, at the start, one fresh call sees only the request, the provided file names and the measured machine facts,
and writes attack checks as one script (fk4's prompt plus its lessons: try before UNTESTED; install test tools only,
never what the request says the solution provides). At each of the first two finishes Core runs the script once on a
writable clone of the container (network as the task's own), so nothing touches the work. A script whose checks did
not run gets one repair by the same reader from its own output; the worker never sees that. A check may FAIL only
where the request itself fixes what passes; a check resting on the reader's own assumption (a formula, a scope, a
threshold) prints OBSERVED (xc1: such FAILs flagged 6/6 passing sanitize runs). When any check FAILs,
the worker gets the result blocks only (what ran, what was expected, what happened, PASS/FAIL/UNTESTED), never the
reader's reasoning or ranking, and decides. No FAIL, no script, or too little time: the finish takes effect.
"""

from __future__ import annotations

import asyncio
import posixpath
import re
import shlex
from typing import Any

from . import env_brief
from .card import provided_files, script_of
from .env import run
from .rival import due, mark_start as _mark
from .transfer import put_bytes

MAX_TOKENS = 64_000  # fk4: at 16K, 5/16 answers ran out (3 empty: all reasoning); at 64K 16/16 closed
SCRIPT_S, OUT_CHARS, GOT_CHARS = 600, 9_000, 700
READER_WAIT_S = 900.0  # longest the first finish waits for a reader still writing
OBSERVE_CHARS = 30_000  # the check output kept in the trace row, so checks can be scored against the run's reward
ROUNDS = 2  # the script is re-run at the second finish; the third finish ends the run
PROMPT = (
    "Here is a task someone has asked for, the files that come with it, and facts measured on the machine where it "
    "will be done.\n\nTASK:\n{task}\n\nFILES PROVIDED:\n{files}\n\nMACHINE FACTS:\n{env}\n\n"
    "Someone will soon hand in a solution to this task that looks right to them. Your job is to find where it is "
    "silently wrong. Do not do the task.\n\n"
    "Part 1 - Requirements. List every explicit requirement and every interface the request names (commands, paths, "
    "ports, formats, dates, limits, the way the result will be used). For each, say which of its dependencies the "
    "machine facts show are present and which are only assumed. A promise in the request that someone will set "
    "something up does not show that its dependencies exist. Each requirement gets a check, however unlikely a "
    "failure seems. A check must exercise the interface exactly as the request names it, from a clean place; never "
    "replace it with an easier or supposedly equivalent one.\n\n"
    "Part 2 - Attacks. List at most five other ways a plausible solution could be silently wrong, ranked "
    "most likely-and-costly first, each with the alternatives and an attack that would expose the wrong one.\n\n"
    "Part 3 - Script. Write one shell script, at most 150 lines, in a single ```sh block, that runs every check and "
    "attack. It will be run once by root, in a copy of this machine taken after the work is finished, from the "
    "working directory {workdir}, with network access as the task has it, no input, and {limit} seconds in all. It may "
    "install test tools, fetch data, build, and run edge or hostile inputs; it must not install or configure anything "
    "the request says the solution itself provides. Before printing UNTESTED, a check must try (fetch, install, "
    "launch) and say why the attempt failed. A check may print FAIL only when the request itself fixes what passes - a "
    "command, path, file, format, limit or value the request states - applied exactly as stated, with no assumption "
    "of yours (no formula, scope, convention or threshold that you chose). When a check rests on any such "
    "assumption, it prints OBSERVED instead, with the measured value and the assumption in got:. For each check it "
    "prints one result block:\n"
    "CHECK <name>\nran: <command>\nexpected: <what a correct solution gives>\ngot: <what happened>\n"
    "result: PASS | FAIL | OBSERVED | UNTESTED\n"
    "Do not ask anyone and do not consult any evaluation material."
)
REPAIR = (
    "Your script was run as described on a copy of the finished work. Its output is below. {why} Rewrite the whole "
    "script so that every check actually runs and prints its result block: keep each check's meaning and expected "
    "result, fix errors, install missing test tools or fetch what it needs, and print UNTESTED only after a real "
    "attempt fails. Reply with the corrected script only, in one ```sh block.\n<output exit=\"{code}\">\n{out}\n</output>"
)
HANDBACK = (
    "[finish not taken yet: before you started, a separate reader who saw only your request, the names of the files "
    "provided with it and the measured machine facts (not your work and not this conversation) wrote checks of the "
    "finished work. Core has just run them once on a copy of the current state; your own state is untouched. Below "
    "is each check's result as the checks printed it. The checks are unverified and may be wrong. Decide what, if "
    "anything, they show about your work; make no change the request does not call for. Then call finish again; "
    "{after} {left:.0f}s remain.]\n<check_results>\n{blocks}\n</check_results>"
)
_BLOCK = re.compile(r"^CHECK[ \t]+(.*?)\n(.*?)^result:[ \t]*(PASS|FAIL|OBSERVED|UNTESTED)\b[^\n]*", re.S | re.M)


def blocks(out: str) -> list[dict[str, str]]:
    """The result blocks a script printed: name, body (ran/expected/got, each line clipped) and result."""
    found = []
    for name, body, result in _BLOCK.findall(out):
        lines = [ln if len(ln) <= GOT_CHARS else ln[:GOT_CHARS] + " [...]" for ln in body.strip().splitlines()]
        found.append({"name": name.strip()[:120], "body": "\n".join(lines[:12]), "result": result})
    return found


def render(found: list[dict[str, str]]) -> str:
    text = "\n\n".join(f"CHECK {b['name']}\n{b['body']}\nresult: {b['result']}" for b in found)
    return text if len(text) <= OUT_CHARS else text[:OUT_CHARS] + "\n[remaining results cut]"


def needs_repair(found: list[dict[str, str]], code: int) -> str | None:
    if not found:
        return "It printed no result block."
    untested = sum(b["result"] == "UNTESTED" for b in found)
    if untested:
        return f"{untested} of {len(found)} checks printed UNTESTED."
    return None


async def mark_start(s: Any) -> None:
    """The start marker (as for card and rival) and, in attack mode, the reader call, launched alongside the run."""
    await _mark(s.env, s.config.control_dir)
    if s.config.card_challenge in ("attack", "observe"):
        s.attack_reader = asyncio.ensure_future(_read(s))


async def _read(s: Any) -> dict[str, Any]:
    files = await provided_files(s.env, s.workdir, s.config.control_dir)
    facts, _ = await env_brief.take(s.env, s.workdir)
    messages = [{"role": "user", "content": PROMPT.format(task=s.task, files="\n".join(files) or "(none)",
                                                          env=facts or "(not measured)", workdir=s.workdir, limit=SCRIPT_S)}]
    turn = await s.provider.complete(messages, None, max_tokens=MAX_TOKENS, remaining_s=s.remaining, role="attack")
    text = (turn.content or "").strip()
    return {"messages": messages + [{"role": "assistant", "content": text}], "script": script_of(text),
            "files": len(files), "chars": len(text), "usage": dict(turn.usage)}


async def _run(s: Any, script: str) -> tuple[int, str]:
    """Run the script once on a fresh writable clone with the task's own network; the clone is then discarded."""
    if s.config.make_clone is None:  # only Harbor's host-side clone factory (with_clones); never a container's own lookup
        raise RuntimeError("no host clone factory")
    clone = await s.clone(s.env, timeout_s=SCRIPT_S + 300, read_only=False, egress=True)
    try:
        path = posixpath.join(s.config.control_dir, "attack.sh")
        await put_bytes(clone, script.encode(), path)
        q = shlex.quote
        limit = f"timeout {SCRIPT_S} " if (await run(clone, "command -v timeout")).code == 0 else ""  # else run()'s own
        res = await run(clone, f"cd {q(s.workdir)} && {limit}bash {q(path)} </dev/null 2>&1", timeout_s=SCRIPT_S + 60)
        return res.code, (res.stdout or "") + (res.stderr or "")
    finally:
        try:
            await asyncio.wait_for(clone.close(), 60)
        except Exception:  # noqa: BLE001 - a clone that will not close is the run-end cleanup's
            pass


async def at_finish(s: Any) -> tuple[str | None, dict[str, Any]]:
    """The hand-back text (None: the finish takes effect) and the trace row; called at each finish while
    row["again"] is set."""
    row = dict(s.result.extras.get("rival") or {"mode": "attack", "rounds": 0})
    row["rounds"] += 1
    row["again"] = False
    left, task = s.remaining(), getattr(s, "attack_reader", None)
    if not due(left, s.timeout_s) or task is None:
        return None, {**row, "skipped": "time" if task else "no_reader", "remaining_s": round(left, 1)}
    try:
        reader = await asyncio.wait_for(asyncio.shield(task), min(READER_WAIT_S, max(1.0, left - 120)))
    except Exception as exc:  # an instrument: no checks, the finish takes effect
        return None, {**row, "error": f"reader: {type(exc).__name__}: {exc}"[:300]}
    script = row.get("script_text") or reader["script"]
    row.update(reader_chars=reader["chars"], files=reader["files"], reader_usage=reader["usage"])
    if not script:
        return None, {**row, "script": False}
    try:
        code, out = await _run(s, script)
        found = blocks(out)
        why = needs_repair(found, code) if row["rounds"] == 1 else None
        if why:  # one repair by the same reader, from its own output; the worker never sees it
            msgs = reader["messages"] + [{"role": "user", "content": REPAIR.format(why=why, code=code, out=out[-OUT_CHARS:])}]
            turn = await s.provider.complete(msgs, None, max_tokens=MAX_TOKENS, remaining_s=s.remaining, role="attack")
            fixed = script_of((turn.content or "").strip())
            row.update(repair=why, repair_usage=dict(turn.usage), repaired=fixed is not None)
            if fixed:
                code2, out2 = await _run(s, fixed)
                found2 = blocks(out2)
                ran = lambda f: sum(b["result"] != "UNTESTED" for b in f)  # noqa: E731
                if ran(found2) >= ran(found):
                    script, code, out, found = fixed, code2, out2, found2
    except Exception as exc:  # an instrument: nothing observed, the finish takes effect
        return None, {**row, "error": f"run: {type(exc).__name__}: {exc}"[:300]}
    counts = {k: sum(b["result"] == k for b in found) for k in ("PASS", "FAIL", "OBSERVED", "UNTESTED")}
    row.update(script=True, script_text=script[:8000], exit=code, out_chars=len(out), blocks=len(found), **counts,
               failed=[b["name"] for b in found if b["result"] == "FAIL"][:20], out_text=out[-OBSERVE_CHARS:])
    if not counts["FAIL"] or s.config.card_challenge == "observe":
        return None, row
    row["again"] = row["rounds"] < ROUNDS
    after = ("Core will run the same checks once more at that finish." if row["again"]
             else "the next finish ends the task.")
    return HANDBACK.format(after=after, left=s.remaining(), blocks=render(found)), row

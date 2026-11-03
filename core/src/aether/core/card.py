"""A contract card at the first finish (AETHER_CORE_RIVAL=card).

Why (K1, 31 Oct): failing Luna runs lose the task's contract while building — a date read as a release-date filter,
a required SSH clone judged out of scope, an unrequested history rewrite — yet a fresh Luna call shown only the
request and the names of the provided files restated the missed requirement in 15/15 samples on four such tasks.
The model reads the contract correctly; the working run drifts from it. Luna acts on what comes from outside its own
reasoning (an observation, a rival), not on its own doubts (D1: 0/6), and a rival harmed when it brought its own
yardstick. A card is an outside yardstick taken from the request itself.

At the first finish with enough time left, one plain call in a fresh context sees the task and the names of the files
that were there before the first action (never the run's work, history or reasoning) and writes what the finished
work must satisfy. It is handed back once, unverified; the model checks its work against it and decides. The next
finish ends the run. Core never judges the card or the work.

Probe (AETHER_CORE_RIVAL=probe; K2, 30 Oct): handed a card, Luna re-ran its own checks and re-finished (1 changed
deliverable in 18 handbacks): a reading is a claim, and the model's own yardstick absorbs it. The same call also
writes a script that observes each item, using the request's own commands, paths and addresses as written; Core runs
it once in the current environment and hands back its output with the reading, so a failing item arrives as an
observation the model did not choose. The script is the reader's and may be wrong; Core never interprets its output.

Challenge (AETHER_CORE_RIVAL=challenge; user design, 2 Nov): fk2 put the deciding fork in a fresh reader's top two in
4/6 tasks when asked where the work could be wrong, while dc1 showed that a list of concerns shown to the worker
derails literal tasks (sanitize 0/9). Here the fresh reader (request and provided file names only) writes read-only
checks aimed at where finished work is most likely wrong; Core runs them once at the first finish with `sh -x` and
hands back only each command as run and its raw output, never the reader's reasoning or concerns.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from typing import Any, Awaitable, Callable

from .env import Environment, run
from .rival import due, marker_path
from .transfer import put_bytes

MAX_FILES, MAX_TOKENS = 200, 8_000
PROBE_S, PROBE_CHARS = 120, 6_000
PROBE_MAX_TOKENS = 32_000  # K3 e1: 3 of 4 probe calls spent all 8K on reasoning and wrote nothing
PROMPT = (  # the K1 probe prompt (research/core_mission_20261028/k1_restate/prompt.txt), verbatim apart from layout
    "Here is a request someone gave to an engineer, followed by the names of the files they provided.\n\n"
    "Before any work starts, write down precisely what the finished work must satisfy for the request to be met. "
    "Cover every requirement, including dates or points in time, scope limits (what must and must not be changed), "
    "interfaces, and how the result will be used or invoked. For each item, quote the words of the request it comes "
    "from. Where the request is ambiguous, say so and give the reading you would adopt and why.\n\n"
    "REQUEST:\n{task}\n\nPROVIDED FILES:\n{files}"
)
HANDBACK = (
    "[finish not taken yet: a separate reader, given only your request and the names of the files provided with it "
    "(not your work and not this conversation), wrote the reading below of what the finished work must satisfy. It "
    "is unverified and may be wrong. Check your work against each item by observing the actual state, not by "
    "re-reading your own notes. Where the work fails an item that the request supports, fix it; where you judge an "
    "item wrong or not applicable, say why and leave the work as it is. Make no change the request does not call "
    "for. Then call finish again; the next finish ends the task. {left:.0f}s remain.]\n<reading>\n{card}\n</reading>"
)


async def provided_files(env: Environment, workdir: str, control_dir: str) -> list[str]:
    """Paths under ``workdir`` that existed before the first action (not newer than the start marker)."""
    q = shlex.quote
    script = (f"cd {q(workdir)} && find . -type f ! -newer {q(marker_path(control_dir))} -not -path './.git/*' "
              f"2>/dev/null | sort | head -n {MAX_FILES}")
    result = await run(env, script, timeout_s=60)
    return [posixpath.normpath(posixpath.join(workdir, line)) for line in result.stdout.splitlines() if line.strip()]


PROBE_PROMPT = (
    "\n\nAfter the reading, write one shell script in a single ```sh block that observes, in the environment where "
    "the work was done (working directory {workdir}), whether each item holds in the finished work. For each item, "
    "echo a line naming it, then run the observation. Where the request states a command, path, address or "
    "invocation, use it exactly as written. Change nothing: do not install, edit, create, delete, restart, commit or "
    "push anything, and give no command input it would wait for. Print what is observed, not a verdict."
)
PROBE_HANDBACK = (
    "[finish not taken yet: a separate reader, given only your request and the names of the files provided with it "
    "(not your work and not this conversation), wrote the reading below and a script to observe each item. The "
    "script was run once, as written, in the current environment; its output is below. The reading and the script "
    "are unverified and may be wrong. Where an observation shows the work failing an item that the request supports, "
    "fix it; where the script or the reading is wrong, say why and leave the work as it is. Make no change the "
    "request does not call for. Then call finish again; the next finish ends the task. {left:.0f}s remain.]\n"
    "<reading>\n{card}\n</reading>\n<script>\n{script}\n</script>\n<observed exit=\"{code}\">\n{out}\n</observed>"
)
CHALLENGE_PROMPT = (  # fk2's question (research/core_mission_20261028/fk2/prompt.txt), turned into checks only
    "Here is a request someone gave to an engineer, followed by the names of the files they provided. Do not do the "
    "task.\n\nThink about where finished work for this request is most likely to be wrong without its author "
    "noticing: a reading of the request, or an assumption about facts, behaviour, data or dependencies that could "
    "easily be wrong. Then write one shell script in a single ```sh block that, run in the working directory "
    "{workdir} after the work is finished, would expose those errors: at most five checks, the most likely and costly "
    "first, each observing the finished work directly (run it, read its output, inspect files or state). Where the "
    "request states a command, path or address, use it exactly as written. Write only commands: no comments and no "
    "echo lines explaining them, because only the commands and their raw output will be shown, not your reasoning. "
    "Change nothing: do not install, edit, create, delete, restart, commit or push anything, and give no command "
    "input it would wait for.\n\nREQUEST:\n{task}\n\nPROVIDED FILES:\n{files}"
)
CHALLENGE_HANDBACK = (
    "[finish not taken yet: before you started, a separate reader who saw only your request and the names of the "
    "files provided with it (not your work and not this conversation) wrote read-only checks. Core has just run them "
    "once, as written, on the current state. Below is each command as run (lines starting with +) and its raw output. "
    "The checks are unverified and may be wrong. Decide what, if anything, they show about your work; make no change "
    "the request does not call for. Then call finish again; the next finish ends the task. {left:.0f}s remain.]\n"
    "<observed exit=\"{code}\">\n{out}\n</observed>"
)
_SCRIPT = re.compile(r"```(?:sh|bash|shell)?[ \t]*\n(.*?)```", re.S)


def request(task: str, files: list[str], workdir: str | None = None, challenge: bool = False) -> list[dict[str, Any]]:
    if challenge:
        return [{"role": "user", "content": CHALLENGE_PROMPT.format(task=task, files="\n".join(files) or "(none)",
                                                                     workdir=workdir)}]
    content = PROMPT.format(task=task, files="\n".join(files) or "(none)")
    if workdir is not None:
        content += PROBE_PROMPT.format(workdir=workdir)
    return [{"role": "user", "content": content}]


def script_of(text: str) -> str | None:
    """The last fenced shell block, or None."""
    blocks = [b.strip() for b in _SCRIPT.findall(text) if b.strip()]
    return blocks[-1] if blocks else None


async def observe(env: Environment, script: str, workdir: str, control_dir: str, xtrace: bool = False) -> tuple[int, str]:
    """Run the reader's script once, as written, with no input; its exit code and the tail of its output."""
    path = posixpath.join(control_dir, "probe.sh")
    await put_bytes(env, script.encode(), path)
    q = shlex.quote
    limit = f"timeout {PROBE_S} " if (await run(env, "command -v timeout")).code == 0 else ""  # else run()'s own limit
    result = await run(env, f"cd {q(workdir)} && {limit}sh {'-x ' if xtrace else ''}{q(path)} </dev/null 2>&1", timeout_s=PROBE_S + 30)
    out = (result.stdout or "") + (result.stderr or "")
    if len(out) > PROBE_CHARS:
        out = f"[first {len(out) - PROBE_CHARS} chars cut]\n" + out[-PROBE_CHARS:]
    return result.code, out


async def at_finish(
    env: Environment,
    complete: Callable[..., Awaitable[Any]],
    *,
    task: str,
    workdir: str,
    control_dir: str,
    remaining_s: Callable[[], float],
    timeout_s: float,
    probe: bool = False,
    challenge: bool = False,
) -> tuple[str | None, dict[str, Any]]:
    """The hand-back text (None: the finish takes effect) and a trace row. Called once per run."""
    left = remaining_s()
    if not due(left, timeout_s):
        return None, {"asked": False, "reason": "time", "remaining_s": round(left, 1), "mode": "card"}
    try:
        files = await provided_files(env, workdir, control_dir)
        turn = await complete(request(task, files, workdir if probe or challenge else None, challenge), None,
                              max_tokens=PROBE_MAX_TOKENS if probe or challenge else MAX_TOKENS,
                              remaining_s=remaining_s, role="card")
    except Exception as exc:  # an instrument: no card, the finish takes effect
        return None, {"asked": True, "mode": "card", "error": f"{type(exc).__name__}: {exc}"[:300]}
    text = (turn.content or "").strip()
    row = {"asked": True, "mode": "challenge" if challenge else "probe" if probe else "card", "files": len(files),
           "chars": len(text), "usage": dict(turn.usage)}
    if not text:
        return None, row
    if challenge:  # commands and raw output only; no script means nothing to show, so the finish takes effect
        script = script_of(text)
        row.update(script=script is not None, echo_lines=sum(1 for ln in (script or "").splitlines()
                                                             if ln.lstrip().startswith("echo ")))
        if script is None:
            return None, row
        try:
            code, out = await observe(env, script, workdir, control_dir, xtrace=True)
        except Exception as exc:  # an instrument: nothing observed, the finish takes effect
            row.update(probe_error=f"{type(exc).__name__}: {exc}"[:300])
            return None, row
        row.update(exit=code, out_chars=len(out), script_text=script[:4000])
        return CHALLENGE_HANDBACK.format(left=remaining_s(), code=code, out=out), row
    script = script_of(text) if probe else None
    if script is None:
        row["script"] = False if probe else None
        return HANDBACK.format(left=remaining_s(), card=text), row
    try:
        code, out = await observe(env, script, workdir, control_dir)
    except Exception as exc:  # an instrument: the reading alone
        row.update(script=True, probe_error=f"{type(exc).__name__}: {exc}"[:300])
        return HANDBACK.format(left=remaining_s(), card=text), row
    row.update(script=True, exit=code, out_chars=len(out))
    reading = text[: text.rfind("```", 0, text.rfind("```"))].rstrip() or text
    return PROBE_HANDBACK.format(left=remaining_s(), card=reading, script=script, code=code, out=out), row

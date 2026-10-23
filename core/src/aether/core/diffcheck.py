"""An executable check of the task's output, written from the task alone while the solver works (AETHER_CORE_DIFFCHECK).

Why (semantic study, 23 Oct): Flint's wrong deliverables ran: they were wrong in behaviour (a sharded layer that
diverged from the unsharded one, a port that diverged from the original program, a query that matched the wrong
rows). Every finish-time lever left them unchanged (the model re-finishes at once), reading checks share the
solver's prior, and the solver's own checks are fitted to its own file. What did catch such errors was an
independent, executed comparison against a source of truth the task supplies (the original program, a definition
in the task, a documented interface), written before seeing the candidate.

What it does:
- At the first action, a second run of the Core loop (same model, fresh context, its own call-log role and control
  directory, in the same container) gets the task and a brief (AUTHOR_BRIEF): write ``{dir}/check.py`` comparing
  a candidate's behaviour with a reference built from the task's own sources, plus ``good_candidate.*`` and
  ``broken_candidate.*`` and the path of the file to check in ``{dir}/target``. It never sees the solver's work:
  it starts before there is any, and it is told not to read or change the solver's files.
- The harness accepts the check only if it behaves as claimed: exit 0 on the good candidate and 1 on the broken
  one, run by the harness. A check that cannot tell them apart is never shown (traced as rejected).
- From then on, whenever the target file exists with new content, the harness runs the check (at most once per
  MIN_GAP_S, each run bounded). A disagreement is appended to the solver's current tool result with the check's
  own input / expected / actual lines and the command to re-run it, in the terminal workflow the solver already
  uses. The same disagreement is said once; agreement after a disagreement is said once.
- The check's source is held by the harness: if the file is changed in the container, the harness's copy is
  restored before the next run (so a check is never refitted to the candidate), and that is traced.

What it is not: no hold, no verdict, no finish veto. The check can be wrong and says so. The solver decides.
Limits: the author's terminal commands are not sandboxed; its write_file/edit_file calls outside ``{dir}`` are
traced as boundary breaches, its shell writes are not seen. One target file per run.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import hashlib
import re
import shlex
from typing import Any, Awaitable, Callable

from .env import Environment, put_bytes, run
from .oversight import ReviewPlan

DIFFCHECK_ENV = "AETHER_CORE_DIFFCHECK"
DIFFCHECK_MODES = ("off", "on")
AUTHOR_ROLE = "diffcheck"
AUTHOR_SHARE, AUTHOR_MAX_S, AUTHOR_MIN_S = 0.35, 900.0, 120.0
CHECK_S, MIN_GAP_S, RESERVE_S = 300, 60.0, 90.0
SHOWN_CHARS = 2_500
TRACE_FILE = "diffcheck_trace.jsonl"

AUTHOR_BRIEF = """Someone else is working on the task below in this container; you will not see their work. Your job: \
write an executable check that compares a candidate solution's actual behaviour against the best source of truth \
this task makes available.

1. List each behaviour the task requires, quoting the task.
2. Identify the sources of truth available from the task and the files it supplies: an original implementation or \
program to stay equivalent to, a supplied evaluator or data, a documented format or interface, or a definition in \
the task you can compute directly. Prefer executing supplied originals over re-implementing them.
3. Build an independent reference for the required behaviour from those sources.
4. Choose inputs that discriminate: typical cases, boundaries, unusual combinations, and inputs beyond the examples \
the task gives.
   Where the task leaves a convention open (a tensor or matrix layout, an ordering, a number or text format, a \
rounding, an argument convention), do not pick one: accept every reading the task's wording allows, and flag a \
behaviour only if it is wrong under all of them.
5. Write {dir}/check.py: `python3 {dir}/check.py --candidate PATH` runs the candidate at PATH and the reference on \
the same inputs, through the interface the task specifies, prints each disagreement as input / expected / actual, \
and exits 1 on any disagreement, 2 if the check itself could not run, 0 if none. Under {check_s} seconds.
6. Write the absolute path of the file the task asks for (the candidate to check) as the only line of \
{dir}/target.
7. Validate: write {dir}/good_candidate.<ext> that follows the task (check exits 0) and \
{dir}/broken_candidate.<ext>, a plausible but wrong variant (check exits 1). The harness re-runs both and uses \
your check only if they behave so.

Rules: create, change or delete nothing outside {dir} (copy supplied files there if you must modify them). The \
file the task asks for may not exist yet or be incomplete: do not open it or depend on it. Call finish when the \
check is validated.

The task:
{task}"""

FOUND = """[independent check: {target} disagrees]
A check written separately, from the task alone (it never saw your work; it can be wrong), compared your file's \
behaviour with a reference and found:
{output}
Re-run it: python3 {check} --candidate {target}"""
AGREES = "[independent check: {target} now agrees with it (python3 {check} --candidate {target})]"

_NOISE = re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|seconds)\b|0x[0-9a-f]+", re.I)


def author_config(config: Any) -> Any:
    """The solver's configuration for the author's run: its own role, control directory and context files, and no
    reviews, verifier, record, state or differential check of its own."""
    root = f"{config.control_dir}-diffcheck"
    return dataclasses.replace(
        config, role=AUTHOR_ROLE, diffcheck=False, verify=False, record=False, record_measure=False, record_paths=False,
        state=False, self_check=False, finish_hold="off", fork=False, control_dir=root,
        reviews=ReviewPlan(finish=False),
        clm=dataclasses.replace(config.clm, mirror_path=f"{root}/ctx/LIVE_CTX.txt",
                                history_path=f"{root}/ctx/HISTORY.txt"),
    )


def author_timeout(remaining: float) -> float | None:
    """The author's time: a share of what is left, bounded; None when too little is left to write a check."""
    t = min(AUTHOR_SHARE * remaining, AUTHOR_MAX_S)
    return t if t >= AUTHOR_MIN_S else None


class DiffCheck:
    """``author(brief, timeout_s)`` runs the check's author (the loop passes a fresh Core run in the check directory)."""

    def __init__(self, env: Environment, task: str, check_dir: str, remaining: Callable[[], float],
                 trace: Callable[..., None], author: Callable[[str, float], Awaitable[Any]],
                 clock: Callable[[], float]) -> None:
        self.env, self.task, self.dir = env, task, check_dir
        self.remaining, self.trace, self._author, self.clock = remaining, trace, author, clock
        self.check, self.target = f"{check_dir}/check.py", ""
        self.source = b""  # the accepted check, held by the harness
        self.state = "idle"  # idle | authoring | ready | rejected | failed
        self.job: asyncio.Task[Any] | None = None
        self.last_sha = self.last_shown = ""
        self.last_run = -MIN_GAP_S
        self.runs: list[dict[str, Any]] = []
        self.errors = 0

    def start(self) -> None:
        timeout = author_timeout(self.remaining())
        if timeout is None:
            self.trace("diffcheck_skipped", reason="too little time", remaining=round(self.remaining()))
            return
        brief = AUTHOR_BRIEF.format(dir=self.dir, task=self.task, check_s=CHECK_S)
        self.state, self.job = "authoring", asyncio.ensure_future(self._author(brief, timeout))
        self.trace("diffcheck_author_started", timeout_s=round(timeout))

    async def after_action(self) -> str:
        """Called after each tool result; returns a note for the solver ('' when there is none)."""
        try:
            if self.state == "authoring" and self.job is not None and self.job.done():
                await self._accept()
            if self.state != "ready" or self.remaining() < RESERVE_S:
                return ""
            return await self._run()
        except Exception as exc:  # an instrument: its failure is traced, the run goes on
            self.errors += 1
            self.trace("diffcheck_error", error=f"{type(exc).__name__}: {exc}")
            return ""

    async def _accept(self) -> None:
        exc = self.job.exception() if self.job and not self.job.cancelled() else None
        if exc is not None:
            self.state = "failed"
            self.trace("diffcheck_author_failed", error=f"{type(exc).__name__}: {exc}")
            return
        q = shlex.quote
        found = await run(self.env, f"cat {q(self.dir)}/target 2>/dev/null | head -1; echo; "
                          f"ls {q(self.dir)} 2>/dev/null; echo; base64 < {q(self.check)} 2>/dev/null | tr -d '\\n'",
                          timeout_s=30)
        head, _, rest = found.stdout.partition("\n\n")
        listing, _, encoded = rest.partition("\n\n")
        self.target = head.strip().splitlines()[0].strip() if head.strip() else ""
        names = listing.split()
        good = next((n for n in names if n.startswith("good_candidate")), "")
        broken = next((n for n in names if n.startswith("broken_candidate")), "")
        if not (self.target.startswith("/") and good and broken and encoded.strip()):
            self.state = "rejected"
            self.trace("diffcheck_rejected", reason="incomplete", target=self.target, files=names)
            return
        self.source = base64.b64decode(encoded.strip())
        codes = {}
        for name in (good, broken):
            r = await self._exec(f"{self.dir}/{name}")
            codes[name] = r.code
        if codes[good] != 0 or codes[broken] != 1:
            self.state = "rejected"
            self.trace("diffcheck_rejected", reason="does not separate its own candidates", exits=codes)
            return
        self.state = "ready"
        self.trace("diffcheck_ready", target=self.target, check_sha=hashlib.sha256(self.source).hexdigest()[:12],
                   exits=codes)

    async def _exec(self, candidate: str) -> Any:
        q = shlex.quote
        bound = f"$(command -v timeout >/dev/null 2>&1 && echo 'timeout {CHECK_S}')"  # not every image has it
        return await run(self.env, f"cd {q(self.dir)} && {bound} python3 {q(self.check)} "
                         f"--candidate {q(candidate)} 2>&1", timeout_s=CHECK_S + 30)

    async def _run(self) -> str:
        q = shlex.quote
        if self.clock() - self.last_run < MIN_GAP_S:
            return ""
        got = await run(self.env, f"[ -s {q(self.target)} ] && sha256sum < {q(self.target)} | cut -c1-16; "
                        f"sha256sum < {q(self.check)} | cut -c1-16", timeout_s=30)
        lines = got.stdout.split()
        if len(lines) < 2 or lines[0] == self.last_sha:
            return ""
        if lines[1] != hashlib.sha256(self.source).hexdigest()[:16]:
            await put_bytes(self.env, self.source, self.check)
            self.trace("diffcheck_check_restored", check=self.check)
        self.last_sha, self.last_run = lines[0], self.clock()
        result = await self._exec(self.target)
        out = result.stdout.strip()
        self.runs.append({"t": round(self.clock(), 1), "sha": lines[0], "exit": result.code})
        self.trace("diffcheck_run", target=self.target, sha=lines[0], exit=result.code, output=out[-SHOWN_CHARS:])
        if result.code == 1:
            key = _NOISE.sub("", out)
            if key == self.last_shown:
                return ""
            self.last_shown = key
            return FOUND.format(target=self.target, output=out[-SHOWN_CHARS:], check=self.check)
        if result.code == 0 and self.last_shown:
            self.last_shown = ""
            return AGREES.format(target=self.target, check=self.check)
        return ""

    async def close(self) -> None:
        if self.job is not None and not self.job.done():
            self.job.cancel()
            try:
                await self.job
            except BaseException:  # the author's cancellation is the expected outcome here
                pass
            self.trace("diffcheck_author_cancelled")

    def summary(self) -> dict[str, Any]:
        return {"state": self.state, "target": self.target, "runs": self.runs, "errors": self.errors,
                "shown": sum(1 for r in self.runs if r["exit"] == 1)}

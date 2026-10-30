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
"""

from __future__ import annotations

import posixpath
import shlex
from typing import Any, Awaitable, Callable

from .env import Environment, run
from .rival import due, marker_path

MAX_FILES, MAX_TOKENS = 200, 8_000
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


def request(task: str, files: list[str]) -> list[dict[str, Any]]:
    return [{"role": "user", "content": PROMPT.format(task=task, files="\n".join(files) or "(none)")}]


async def at_finish(
    env: Environment,
    complete: Callable[..., Awaitable[Any]],
    *,
    task: str,
    workdir: str,
    control_dir: str,
    remaining_s: Callable[[], float],
    timeout_s: float,
) -> tuple[str | None, dict[str, Any]]:
    """The hand-back text (None: the finish takes effect) and a trace row. Called once per run."""
    left = remaining_s()
    if not due(left, timeout_s):
        return None, {"asked": False, "reason": "time", "remaining_s": round(left, 1), "mode": "card"}
    try:
        files = await provided_files(env, workdir, control_dir)
        turn = await complete(request(task, files), None, max_tokens=MAX_TOKENS, remaining_s=remaining_s,
                              role="card")
    except Exception as exc:  # an instrument: no card, the finish takes effect
        return None, {"asked": True, "mode": "card", "error": f"{type(exc).__name__}: {exc}"[:300]}
    text = (turn.content or "").strip()
    row = {"asked": True, "mode": "card", "files": len(files), "chars": len(text), "usage": dict(turn.usage)}
    if not text:
        return None, row
    return HANDBACK.format(left=remaining_s(), card=text), row

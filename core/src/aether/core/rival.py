"""A rival answer at the first finish (AETHER_CORE_RIVAL=on).

Why (origin study, 29 Oct): wrong Luna finishes pass the model's own checks because each check is built on the
model's own reading of the task, so it can only confirm it. On query-optimize every failing run checked "same
output, much faster than the original" and stopped; all six final queries (pass and fail) give byte-identical output
and differ only in speed (0.66 s pass, 0.88-1.07 s fail). Offline, a fresh Luna call shown only the task and a failing
query wrote a faster rival with identical output in 9 of 9 tries (0.43-0.78 s). A second candidate gives the model
something its own check can tell apart from its answer; a critique or a reminder does not (finish holds, open
issues and verifiers changed no outcome).

At the first finish with enough time left, one plain call in a fresh context sees the task, the finish summary and
the text files changed since the start, and writes the strongest rival it expects to be better, or NONE. A rival is
handed back once, unverified, and the model decides by testing; the next finish ends the run. The rival call never
sees the run's history, and Core never judges which answer is right.
"""

from __future__ import annotations

import posixpath
import shlex
from typing import Any, Awaitable, Callable

from .env import Environment, run

RIVAL_ENV = "AETHER_CORE_RIVAL"  # off | on (fresh rival call) | exec (ablation: no rival, run-it handback)
MARKER = "rival_start"
MIN_LEFT_S, MIN_LEFT_SHARE = 120.0, 0.15
FILE_CAP, TOTAL_CAP, MAX_FILES = 40_000, 120_000, 40  # y12/y13: 12K cut 8 of 37 candidates mid-file, unmarked
MAX_TOKENS = 16_000
PROMPT = (
    "Someone produced the candidate above for the task. You cannot run anything. A file marked as cut continues "
    "beyond what is shown; do not judge it by the cut.\n"
    "Write the strongest rival to it: a different answer or implementation that you expect to meet the task "
    "better (more correct, more complete, or better on a criterion the task states, such as speed, format or "
    "covering every case). Give the rival concretely: the exact answer, or the full contents of each file that "
    "differs, with its path. Then, in one line starting 'Test:', name an observable test that would show which of "
    "the two is better.\nIf you do not expect any rival to be better, reply with the single word NONE."
)
HANDBACK = (  # choose, never merge: in y14 merging rival features into a tested answer broke it
    "[finish not taken yet: a fresh reviewer who saw only the task and your files proposes the rival below. It is "
    "unverified and may be wrong. Run a test that tells the two apart. Then choose one: keep your answer exactly as it "
    "is, or replace it with the rival where the test shows the rival is better. Do not merge the rival's extra "
    "features into an answer your own tests already passed. Then call finish "
    "again; the next finish ends the task. {left:.0f}s remain.]\n<rival>\n{rival}\n</rival>"
)


EXEC_HANDBACK = (  # ablation (ChatGPT review, 29 Oct): is the rival's gain the rival, or being made to execute?
    "[finish not taken yet: before finishing, run the deliverable itself the way the task will use it, against what "
    "the task states it must do (install anything it needs to run). Reading the code or working an example by hand "
    "does not count. If it already ran that way, say what you ran and finish again. Keep your answer unless that run "
    "shows a fault. The next finish ends the task. {left:.0f}s remain.]"
)


def exec_at_finish(remaining_s: Callable[[], float], timeout_s: float) -> tuple[str | None, dict[str, Any]]:
    """The execution-only handback, once, when enough time is left; no model call."""
    left = remaining_s()
    if not due(left, timeout_s):
        return None, {"asked": False, "reason": "time", "remaining_s": round(left, 1), "mode": "exec"}
    return EXEC_HANDBACK.format(left=left), {"asked": True, "mode": "exec"}


def marker_path(control_dir: str) -> str:
    return posixpath.join(control_dir, MARKER)


async def mark_start(env: Environment, control_dir: str) -> None:
    """Touch the marker that 'changed since the start' is measured against (before the first action)."""
    await run(env, f"touch {shlex.quote(marker_path(control_dir))}", timeout_s=15)


async def changed_files(env: Environment, workdir: str, control_dir: str) -> list[tuple[str, str]]:
    """Text files under ``workdir`` modified after the start marker, each cut to FILE_CAP, within TOTAL_CAP."""
    q = shlex.quote
    script = (
        f"cd {q(workdir)} && find . -type f -newer {q(marker_path(control_dir))} -not -path './.git/*' "
        f"-size -2M 2>/dev/null | sort | head -n {MAX_FILES} | while IFS= read -r f; do "
        f"grep -Iq . \"$f\" 2>/dev/null || continue; printf '\\0FILE %s %s\\0' \"$(wc -c < \"$f\" | tr -d ' ')\" \"$f\"; "
        f"head -c {FILE_CAP} \"$f\"; done"
    )
    result = await run(env, script, timeout_s=60)
    out: list[tuple[str, str]] = []
    total = 0
    parts = result.stdout.split("\0")
    for i in range(1, len(parts) - 1, 2):
        if not parts[i].startswith("FILE "):
            continue
        size, _, rel = parts[i][5:].partition(" ")
        path = posixpath.normpath(posixpath.join(workdir, rel))
        text = parts[i + 1]
        if total + len(text) > TOTAL_CAP:
            out.append((path, f"[not shown: {size} bytes; the shown files reached the size limit]"))
            continue
        if size.isdigit() and int(size) > len(text.encode()):  # a cut file must never read as the whole file
            text += f"\n[... cut here: shown the first {len(text.encode())} of {size} bytes; the file continues]"
        total += len(text)
        out.append((path, text))
    return out


def due(remaining_s: float, timeout_s: float) -> bool:
    return remaining_s >= max(MIN_LEFT_S, MIN_LEFT_SHARE * timeout_s)


def request(task: str, summary: str, files: list[tuple[str, str]]) -> list[dict[str, Any]]:
    shown = "\n".join(f"<file path={p!r}>\n{t}\n</file>" for p, t in files) or "(no text files changed)"
    body = (f"<task>\n{task}\n</task>\n\n<candidate_summary>\n{summary}\n</candidate_summary>\n\n"
            f"<candidate_files>\n{shown}\n</candidate_files>")
    return [{"role": "user", "content": body}, {"role": "user", "content": PROMPT}]


def is_none(text: str) -> bool:
    words = text.strip().strip(".").split()
    return not words or (len(words) == 1 and words[0].upper() == "NONE")


async def at_finish(
    env: Environment,
    complete: Callable[..., Awaitable[Any]],
    *,
    task: str,
    summary: str,
    workdir: str,
    control_dir: str,
    remaining_s: Callable[[], float],
    timeout_s: float,
) -> tuple[str | None, dict[str, Any]]:
    """The hand-back text (None: the finish takes effect) and a trace row. Called once per run."""
    left = remaining_s()
    if not due(left, timeout_s):
        return None, {"asked": False, "reason": "time", "remaining_s": round(left, 1)}
    try:
        files = await changed_files(env, workdir, control_dir)
        turn = await complete(request(task, summary, files), None, max_tokens=MAX_TOKENS,
                              remaining_s=remaining_s, role="rival")
    except Exception as exc:  # an instrument: no rival, the finish takes effect
        return None, {"asked": True, "error": f"{type(exc).__name__}: {exc}"[:300]}
    text = (turn.content or "").strip()
    row = {"asked": True, "files": [p for p, _ in files], "none": is_none(text), "chars": len(text),
           "usage": dict(turn.usage)}
    if is_none(text):
        return None, row
    return HANDBACK.format(left=remaining_s(), rival=text), row

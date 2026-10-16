"""Finish second look (experiment instrument, opt-in): the first finish is held once for one more look.

P1 step 4 found that GLM reads its delivered file back and still accepts a row that contradicts a stated
requirement. Step 2 separates two questions: does the solver repair when it is given *correct, concrete* evidence
of a failure, and how much of any repair comes from the extra look alone? Both arms hold the first finish once with
the same message ("nudge"); the "check" arm adds the output of an executed check of the delivered files, which the
"nudge" arm runs too but only records (never shows), so both arms know whether the first finish was defective. The check
is supplied by the experiment (derived from the task text only, never from hidden tests); Core runs it as given
and names no task. Information, not a gate: the next finish ends the work.
"""

from __future__ import annotations

import shlex

from .env import Environment, exit_code

NUDGE = (
    "[finish] Your finish has not taken effect yet. Before it does, inspect the current state of your deliverables "
    "against each requirement of the task and repair anything that does not meet it. Then call finish again to "
    "end the work. This message is shown once."
)
CHECK_TIMEOUT_S = 120
OUTPUT_CHARS = 4000


async def run_check(env: Environment, check: str) -> tuple[int, str]:
    """Run the experiment's check in the task container: (exit code, output cut to OUTPUT_CHARS)."""
    result = await env.exec(
        command=f"bash -c {shlex.quote(check)}",  # check scripts are bash
        cwd=None,
        env=None,
        timeout_sec=CHECK_TIMEOUT_S,
    )
    out = (
        str(getattr(result, "stdout", "") or "")
        + str(getattr(result, "stderr", "") or "")
    ).strip()
    if len(out) > OUTPUT_CHARS:
        out = out[:OUTPUT_CHARS] + "\n[... output cut]"
    return exit_code(result), out


async def second_look(env: Environment, check: str, show: bool) -> tuple[str, dict[str, object]]:
    """The text shown in place of the first finish, and the check's record for the trace. With ``show`` off the
    check (if any) still runs and is recorded, but the model sees only the nudge: both arms then record whether the
    first finish was defective."""
    if not check:
        return NUDGE, {}
    code, out = await run_check(env, check)
    record = {"check_exit": code, "check_output": out, "check_shown": show}
    if not show:
        return NUDGE, record
    verdict = "PASSED" if code == 0 else "FAILED"
    return (
        f"{NUDGE}\n\nAn executed check of the delivered files {verdict} (exit code {code}). Its output:\n"
        f"{out or '[no output]'}",
        record,
    )

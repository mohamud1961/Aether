"""Completion notices: say when a background terminal command finished, without a model poll.

Off by default (``CoreConfig.completion_notices``). Adapted from Claude Code's background-shell notifications and the
plan's "attach other relevant results already available" rule for selected waits: a command left running in a named
terminal finishes while the model works elsewhere; without a notice the model learns this only by polling or waiting.

At the end of a model tool packet, Core checks the shell's own completion receipt (``done_<seq>``) for every terminal with an
outstanding command and appends one line per newly finished command: its terminal, sequence and exit. The output is
not consumed here; it is delivered once, as before, by the next use of that terminal or a ``terminal_wait``. Each
command is noticed at most once. A failed check adds nothing and is recorded in the trace.
"""

from __future__ import annotations

import shlex

from .env import run
from .terminal_adopt import _DONE

LINE = ("[terminal {name}: command #{seq} finished with exit {exit} (the shell's own receipt). Its output is "
        "delivered when you next use or wait on {name}.]")


async def finished(terminals, seen: set[tuple[str, int]]) -> list[dict]:
    """Outstanding commands whose completion receipt now exists and that were not noticed before."""
    waiting = [(name, s) for name, s in terminals._sessions.items()
               if s.ready and s.pending and (s.root, s.pending) not in seen]
    if not waiting:
        return []
    script = "; ".join(
        f"printf '%s ' {i}; head -c 300 {shlex.quote(f'{s.root}/done_{s.pending}')} 2>/dev/null | tr '\\n' ' '; echo"
        for i, (_, s) in enumerate(waiting)
    )
    response = await run(terminals._env, script, timeout_s=10)
    if response.code != 0:
        raise RuntimeError(f"completion receipt check exited {response.code}")
    found = []
    for line in response.stdout.splitlines():
        index, _, text = line.partition(" ")
        mark = _DONE.search(text)
        if not index.isdigit() or int(index) >= len(waiting) or mark is None:
            continue
        name, session = waiting[int(index)]
        if int(mark.group(1)) == session.pending:
            found.append({"name": name, "owner": session.root, "sequence": session.pending, "exit": int(mark.group(2))})
    return found


async def before_model(s) -> str:
    """Notice lines for the tool result just produced (empty when nothing newly finished)."""
    if not s.config.completion_notices:
        return ""
    seen = s.result.extras.setdefault("completion_notices_seen", [])
    try:
        found = await finished(s.terminals, {(row["owner"], row["sequence"]) for row in seen})
    except Exception as exc:  # substrate failure: no notice, recorded honestly
        s.trace("completion_notice_error", error=f"{type(exc).__name__}: {exc}")
        return ""
    for row in found:
        seen.append({**row, "step": s.result.steps})
        s.trace("completion_notice", **row, step=s.result.steps)
    return "".join("\n" + LINE.format(name=r["name"], seq=r["sequence"], exit=r["exit"]) for r in found)

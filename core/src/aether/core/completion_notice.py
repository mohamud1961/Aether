"""Completion notices: say when a background terminal command finished, without a model poll.

Off by default (``CoreConfig.completion_notices``). Adapted from Claude Code's background-shell notifications and the
plan's "attach other relevant results already available" rule for selected waits: a command left running in a named
terminal finishes while the model works elsewhere; without a notice the model learns this only by polling or waiting.

At the end of a model tool packet, Core checks the shell's own completion receipt (``done_<seq>``) for every terminal with an
outstanding command and appends one line per newly finished command: its terminal, sequence and exit. The output is
normally remains available through the terminal or ``terminal_wait``. With result delivery enabled,
Core attaches the bounded output to the current tool packet instead. Each command is noticed at most once. A failed check adds nothing and is recorded in the trace.
"""

from __future__ import annotations

import shlex
import time

from .env import run
from .operations import DONE

MAX_DELIVERED_PER_BOUNDARY = 2

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
        mark = DONE.search(text)
        if not index.isdigit() or int(index) >= len(waiting) or mark is None:
            continue
        name, session = waiting[int(index)]
        if int(mark.group(1)) == session.pending:
            found.append({"name": name, "owner": session.root, "sequence": session.pending, "exit": int(mark.group(2))})
    return found


async def before_model(s) -> str:
    """Notice lines for the tool result just produced (empty when nothing newly finished)."""
    seen = s.result.extras.setdefault("completion_notices_seen", [])
    try:
        found = await finished(s.terminals, {(row["owner"], row["sequence"]) for row in seen})
    except Exception as exc:  # substrate failure: no notice, recorded honestly
        s.trace("completion_notice_error", error=f"{type(exc).__name__}: {exc}")
        return ""
    deliver = s.config.terminal_result_delivery
    if deliver:
        found = found[:MAX_DELIVERED_PER_BOUNDARY]
    lines = []
    for row in found:
        name, seq = row["name"], row["sequence"]
        if deliver:
            try:
                async with s.terminals._name_locks[name]:
                    session = s.terminals._sessions.get(name)
                    if session is None or session.root != row["owner"] or session.pending != seq:
                        continue
                    first = await s.terminals._poll(session, seq)
                    mark = first[1]
                    if mark is None or int(mark.group(2)) != row["exit"]:
                        continue
                    output = await s.terminals._collect(session, time.monotonic(), 0, first)
            except (OSError, RuntimeError, TimeoutError) as exc:
                s.trace("completion_notice_error", name=name, sequence=seq, error=type(exc).__name__)
                continue
            row["delivered"] = True
            lines.append(f"[terminal {name}: command #{seq} finished with exit {row['exit']}; collected output]\n{output}")
        else:
            lines.append(LINE.format(name=name, seq=seq, exit=row["exit"]))
        seen.append({**row, "step": s.result.steps})
        s.trace("completion_notice", **row, step=s.result.steps)
    return "".join("\n" + line for line in lines)

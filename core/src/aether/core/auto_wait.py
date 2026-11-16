"""Automatic waiting (AETHER_CORE_AUTO_WAIT, default off): a reply with no tool call while work is running means
"wait"; Core sleeps until that work finishes and delivers its result, so the model never polls.

Adapted from Unreal Agent Harness (MIT License, Copyright (c) 2026 Unreal Labs), source in
harnesseng-research-data/agent_sources/unreal:
- harness/contextbuilder/builder.go ``ToolCallRunningPayload``: the running-call text, copied verbatim (RUNNING);
- harness/contextbuilder/prompts/preamble.md: the "ending a turn ... means you sleep" rule, first clause verbatim;
- harness/coordinator/loop.go: sleep until an operation update, and a heartbeat after ten idle minutes
  (``postHeartbeat``; its "Heartbeat: waited %g seconds for tool calls.\\nRunning: %s" text is kept).
Unreal's 1 s tool grace period is available as AETHER_CORE_AUTO_WAIT_GRACE=1; the default keeps Core's own 30 s
blocking window, because a model turn takes ~5-7 s and only 2/732 TB4 calls outlived 30 s (16 Nov census).

Core facts only: nothing here interprets the task. A failed receipt check is recorded and the wait ends honestly.
"""

from __future__ import annotations

import asyncio
import time

from . import completion_notice

RUNNING = ("Tool call is still running. Its result arrives in a later turn: continue with independent work, "
           "or end your turn to wait for it.")
PROMPT = ("\n\nEnding a turn with no tool calls while calls are running means you sleep until one finishes; "
          "Core then shows its result. Use finish (not a plain reply) when the task is complete.")
HEARTBEAT_S = 600.0  # Unreal's default tool heartbeat interval (cmd/internal/agentrunner/run.go)
POLL_S = 1.0  # receipt check interval while sleeping (one docker exec, ~0.07 s)
DEADLINE_MARGIN_S = 30.0  # wake before the run's time limit so the model can still act
GRACE_MODES = ("30", "1")


def grace(config, wait_s: float) -> float:
    """A terminal command's blocking window: the model's own wait_s, capped at the grace when auto-wait is on."""
    if not getattr(config, "auto_wait", False):
        return wait_s
    return min(wait_s, float(getattr(config, "auto_wait_grace_s", 30.0)))


def mark_running(config, out: str) -> str:
    """Unreal's running-call line beside a terminal result whose command is still running."""
    if getattr(config, "auto_wait", False) and "[still running after" in out:
        return f"{out}\n[{RUNNING}]"
    return out


def outstanding(s) -> list[str]:
    """Terminal commands and Python cells that have started and whose result has not been shown."""
    seen = {(row["owner"], row["sequence"]) for row in s.result.extras.get("completion_notices_seen", [])}
    running = [f"terminal {name} command #{session.pending}"
               for name, session in sorted(s.terminals._sessions.items())
               if session.ready and session.pending and (session.root, session.pending) not in seen]
    repl = getattr(s, "repl", None)
    seq = getattr(repl, "pending", 0) if getattr(repl, "track_operations", False) else 0
    if seq and ("python", seq) not in seen:
        running.append(f"python cell #{seq}")
    return running


async def sleep(s, *, clock=time.monotonic, pause=asyncio.sleep) -> str | None:
    """Called on a reply with no tool call. None when nothing is running (the ordinary idle path applies);
    otherwise sleeps until a result arrives, the heartbeat, or the time limit nears, and returns the text to show."""
    running = outstanding(s)
    if not running:
        return None
    started = clock()
    s.trace("auto_wait", phase="sleep", running=running, step=s.result.steps)
    while True:
        text = await completion_notice.before_model(s, deliver=True, others=True)
        waited = clock() - started
        if text:
            s.trace("auto_wait", phase="woke", by="result", waited_s=round(waited, 1), step=s.result.steps)
            return text.strip()
        still = outstanding(s)
        if not still:  # collected elsewhere (e.g. the shell exited): nothing left to wait for
            s.trace("auto_wait", phase="woke", by="none_running", waited_s=round(waited, 1), step=s.result.steps)
            return f"[Waited {waited:.0f}s; nothing is running now.]"
        if waited >= HEARTBEAT_S:
            s.trace("auto_wait", phase="woke", by="heartbeat", waited_s=round(waited, 1), step=s.result.steps)
            return f"Heartbeat: waited {HEARTBEAT_S:g} seconds for tool calls.\nRunning: {'; '.join(still)}"
        if s.remaining() <= DEADLINE_MARGIN_S + POLL_S:
            s.trace("auto_wait", phase="woke", by="time_limit", waited_s=round(waited, 1), step=s.result.steps)
            return f"[Waited {waited:.0f}s; about {s.remaining():.0f}s of the time limit left. Running: {'; '.join(still)}]"
        await pause(POLL_S)

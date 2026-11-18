"""Wait for a selected terminal command without running another model turn."""

from __future__ import annotations

import asyncio
import math
import shlex
import time

from .env import run
from . import terminal_adopt
from .terminal import _NAME
from .terminal_session import _ASKS, clean

# A pending command whose output has not grown for this long is checked for a prompt as its last line.
QUIET_S = 4.0


async def _stalled(terminal, session, quiet_since: dict, now: float,
                   quiet_s: float | None) -> tuple[str, str] | None:
    """("asking", last line) when a pending command has been quiet for QUIET_S and its last line asks for input:
    it cannot finish until someone answers, so a wait on it would only run out its time. ("quiet", last line) when the
    model chose ``quiet_s`` and the command's output has not grown for that long (no output at all counts from the
    start of the wait). None otherwise."""
    size, mark, alive = await terminal._poll(session, session.pending)
    if mark is not None or not alive:
        quiet_since.pop(session.name, None)
        return None
    since = quiet_since.get(session.name)
    if since is None or since[0] != size:
        quiet_since[session.name] = (size, now)
        return None
    quiet_for = now - since[1]
    has_output = size > session.prompt_offset
    check_prompt = has_output and quiet_for >= QUIET_S
    quiet_reached = quiet_s is not None and quiet_for >= quiet_s
    if check_prompt or quiet_reached:
        last = ""
        if has_output:
            offset = max(session.prompt_offset, size - 300)
            tail = clean(await terminal._read(session, offset, size)).rstrip("\n")
            last = tail.rsplit("\n", 1)[-1][-200:]
        if check_prompt and _ASKS.search(last):
            return "asking", last
        if quiet_reached:
            return "quiet", last
    return None


async def _ready(terminal, pending, duration):
    checks = []
    for i, (session, sequence) in enumerate(pending.values()):
        path = shlex.quote(f"{session.root}/done_{sequence}")
        checks.append(f"if [ -s {path} ] || ! kill -0 {session.pid:d} 2>/dev/null; then printf '%s\\n' {i}; fi")
    steps = "; ".join(checks)
    ticks = max(0, min(40, math.ceil(duration * 10)))
    response = await run(
        terminal._env,
        f'i=0; while :; do ready=$({steps}); '
        f'if [ -n "$ready" ] || [ "$i" = {ticks} ]; then printf "%s\\n" "$ready"; exit; fi; '
        'sleep 0.1; i=$((i+1)); done',
        timeout_s=max(2, math.ceil(duration + 2)),
    )
    if response.code != 0 or len(response.stdout) > 64:
        raise RuntimeError("completion observer failed")
    names = list(pending)
    return [names[int(index)] for index in response.stdout.split()
            if index.isdigit() and int(index) < len(names)]


async def wait(terminal, names, *, mode, wait_s, quiet_s=None):
    if (not isinstance(names, list) or not 1 <= len(names) <= 8
            or any(not isinstance(name, str) or not _NAME.fullmatch(name) for name in names)
            or len(set(names)) != len(names)):
        raise ValueError("terminal_wait requires 1–8 distinct terminal names")
    if mode not in ("any", "all") or type(wait_s) not in (int, float) or not math.isfinite(wait_s) or not 0 <= wait_s <= 300:
        raise ValueError("terminal_wait requires mode any/all and a wait of 0–300 seconds")
    if quiet_s is not None and (type(quiet_s) not in (int, float) or not math.isfinite(quiet_s)
                                or not 1 <= quiet_s <= 300):
        raise ValueError("terminal_wait quiet_s must be 1–300 seconds")
    pending, completed, unknown, adopted, asking, quiet = {}, [], [], [], [], []
    for name in names:
        try:
            async with terminal._name_locks.setdefault(name, asyncio.Lock()):
                if await terminal_adopt.ensure(terminal, name):
                    adopted.append(terminal.adoptions[-1])
        except (OSError, RuntimeError, TimeoutError) as error:
            unknown.append({"name": name, "reason": str(error)[:300]})
            continue
        session = terminal._sessions.get(name)
        if session and session.dispatch_unconfirmed and terminal._preserve_existing:
            sequence = session.pending or session.seq
            if await terminal_adopt.resolve(terminal, session):
                unknown.append({"name": name, "sequence": sequence,
                                "reason": "never started: cancelled before the shell took it, so nothing ran"})
                continue
        if session and session.pending:
            pending[name] = (session, session.pending)
        else:
            unknown.append({"name": name, "reason": "no outstanding terminal command"})
    started = time.monotonic()
    deadline = started + min(wait_s, max(0.0, terminal._clock() - 5))
    quiet_since: dict = {}
    while pending:
        left = deadline - time.monotonic()
        try:
            ready = await _ready(terminal, pending, min(max(left, 0), 4))
        except (OSError, RuntimeError, TimeoutError) as error:
            unknown.extend({"name": name, "reason": type(error).__name__} for name in pending)
            pending.clear()
            break
        for name in ready:
            if name not in pending:
                continue
            session, sequence = pending[name]
            async with terminal._name_locks.setdefault(name, asyncio.Lock()):
                if terminal._sessions.get(name) is not session or session.pending != sequence:
                    unknown.append({"name": name, "sequence": sequence, "reason": "command or terminal changed"})
                else:
                    try:
                        first = await terminal._poll(session, sequence)
                        if first[1] is None and first[2]:
                            continue
                        observation = await terminal._collect(session, time.monotonic(), 0, first)
                    except (OSError, RuntimeError, TimeoutError) as error:
                        unknown.append({"name": name, "sequence": sequence, "reason": type(error).__name__})
                    else:
                        receipt = session.exit_receipt
                        if receipt is not None and receipt[0] == sequence and session.pending == 0:
                            completed.append({"name": name, "sequence": sequence, "exit": receipt[1],
                                              "observation": observation})
                        else:
                            unknown.append({"name": name, "sequence": sequence, "reason": "terminal exit unobserved"})
            del pending[name]
        if unknown or mode == "any" and completed or time.monotonic() >= deadline:
            break
        if not ready:
            for name, (session, sequence) in list(pending.items()):
                async with terminal._name_locks.setdefault(name, asyncio.Lock()):
                    if terminal._sessions.get(name) is not session or session.pending != sequence:
                        continue
                    try:
                        stalled = await _stalled(terminal, session, quiet_since, time.monotonic(), quiet_s)
                    except (OSError, RuntimeError, TimeoutError):
                        stalled = None
                if stalled is not None:
                    kind, line = stalled
                    (asking if kind == "asking" else quiet).append(
                        {"name": name, "sequence": sequence, "last_line": line,
                         **({"quiet_s": round(time.monotonic() - quiet_since[name][1], 1)} if kind == "quiet" else {})})
            if asking or quiet:
                break
        # A hint can outlive its marker. Yield before observing again.
        if ready and pending:
            await asyncio.sleep(min(0.1, max(0, deadline - time.monotonic())))
    result = {"completed": completed, "pending": list(pending), "unknown": unknown,
            "elapsed_s": round(time.monotonic() - started, 3),
            "source": "Core-observed terminal command status"}
    if adopted:
        result["adopted"] = adopted
    if asking:  # still pending; listed because they cannot finish without input
        result["waiting_for_input"] = asking
    if quiet:  # still pending; listed because their output stopped for the chosen quiet_s
        result["quiet"] = quiet
    return result

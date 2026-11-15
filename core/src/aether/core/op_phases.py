"""The recovery phase Core can prove for each operation whose result the model has not seen (A22, with A12).

At the first finish, every operation owner (terminals, Python, MCP, browser) may hold work whose outcome was never
shown: a reply lost after dispatch, a command still running, a result that arrived after the last look. "Effect
unknown" for all of them hides what the sandbox records can prove. Each is reported as one of these phases:

- ``never started``  its send was lost before the executor took the start token; Core takes the token as revoked
  now (with the owner's own resolver, so the owner's state stays consistent), so it can never run later.
- ``waiting``        sent and not yet taken by the executor (MCP: the client has not picked the request up).
- ``running``        the executor took the token and is still alive; no result yet.
- ``completed``      a completion receipt exists (with its exit status when the owner records one); not shown.
- ``lost``           the executor took the token and is gone without a receipt; its effect is unknown.
- ``unreadable``     the records could not be read; its effect is unknown.

Facts only, no advice. Earlier evidence: an added late instruction did not move outcomes (SR1, SR2, pp1, P4); this is
the operation-state part of the finish observation, not a new prompt.
"""

from __future__ import annotations

import shlex

from . import operations, terminal_adopt
from .env import alive_test, run

NEVER = "never started: its send was lost before it was taken, and it is now cancelled, so it cannot run later"
WAITING = "sent and not yet taken; it may still run"
RUNNING = "started and still running; no result yet"
LOST = "started, but its runner is gone with no completion receipt; effect unknown"
UNREADABLE = "its records could not be read; effect unknown"
PROBE_S = 5


def completed(exit_status: str | int | None) -> str:
    return (f"completed with exit {exit_status}" if exit_status not in (None, "") else "completed") + "; result not shown"


async def settle(s) -> list[str]:
    """Resolve every unconfirmed send with its owner's own resolver. Lines for those now proven never started."""
    lines = []
    terminals = s.terminals
    for name, session in sorted(terminals._sessions.items()):
        if session.dispatch_unconfirmed and terminals._preserve_existing:
            seq = session.pending or session.seq
            if await terminal_adopt.resolve(terminals, session):
                lines.append(f"terminal {name}: command #{seq} {NEVER}")
    repl = getattr(s, "repl", None)
    if repl is not None and getattr(repl, "unconfirmed", False) and getattr(repl, "track_operations", False):
        seq = repl.pending
        if await repl._resolve():
            lines.append(f"python: cell #{seq} {NEVER}")
    mcp = getattr(s, "mcp", None)
    for ident, op in sorted(getattr(mcp, "ops", {}).items()):
        if not op.get("published") and await mcp.revoke_unpublished(ident) == operations.REVOKED:
            lines.append(f"mcp {op.get('server')}: request #{ident} ({op.get('tool') or op.get('action')}) {NEVER}")
    runs = getattr(getattr(getattr(s, "browser", None), "sidecar", None), "runs", None)
    for n, op in sorted(getattr(runs, "open", {}).items()):
        if not op.get("launched") and await runs.resolve(n) == operations.REVOKED:
            lines.append(f"browser run #{n}: {NEVER}")
    return lines


async def python_phase(repl) -> list[str]:
    seq = getattr(repl, "pending", 0)
    if not seq:
        return []
    if getattr(repl, "unconfirmed", False):
        return [f"python: cell #{seq} {UNREADABLE}"]
    q = shlex.quote
    probe = (f"cd {q(repl.base)} 2>/dev/null || {{ echo unreadable; exit 0; }}; "
             f"t=$(readlink ops/start_{seq} 2>/dev/null); "
             f"if [ -f out/{seq}.done ]; then echo completed; elif {alive_test(repl.pid)}; then "
             f"if [ -z \"$t\" ] && [ {int(bool(repl.track_operations))} = 1 ]; then echo waiting; else echo running; fi; "
             "else echo lost; fi")
    phase = await _probe(repl._env, probe)
    return [f"python: cell #{seq} " + {"completed": completed(None), "running": RUNNING, "waiting": WAITING,
                                         "lost": LOST}.get(phase, UNREADABLE)]


async def mcp_phases(mcp) -> list[str]:
    lines, q = [], shlex.quote
    for ident, op in sorted(getattr(mcp, "ops", {}).items()):
        label = f"mcp {op.get('server')}: request #{ident} ({op.get('tool') or op.get('action')})"
        d = mcp.started.get(op.get("server"))
        if not op.get("published") or d is None:
            lines.append(f"{label} {UNREADABLE}")
            continue
        probe = (f"cd {q(d)} 2>/dev/null || {{ echo unreadable; exit 0; }}; t=$(readlink start_{ident} 2>/dev/null); "
                 f"if [ -s resp_{ident}.json ]; then echo completed; elif [ -z \"$t\" ]; then echo waiting; "
                 f"elif [ \"$t\" = {operations.RUN} ]; then echo sent; else echo unreadable; fi")
        phase = await _probe(mcp.env, probe)
        lines.append(f"{label} " + {"completed": "answered; answer not shown", "waiting": WAITING,
                                    "sent": "sent to the server; no answer yet; effect unknown"}.get(phase, UNREADABLE))
    return lines


_BROWSER_PROBE = (
    'cd "$1" 2>/dev/null || { echo unreadable; exit 0; }; t=$(readlink "start_$2" 2>/dev/null); '
    'if [ -f "done_$2" ]; then echo "completed $(head -c 16 "done_$2")"; '
    'elif [ "$t" = run ]; then kill -0 "$(cat "pid_$2" 2>/dev/null)" 2>/dev/null && echo running || echo lost; '
    'elif [ -z "$t" ]; then echo waiting; else echo unreadable; fi'
)


async def browser_phases(runs) -> list[str]:
    lines = []
    for n in sorted(getattr(runs, "open", {})):
        try:
            status, out, _ = await runs._sh(_BROWSER_PROBE, runs.ops_dir, str(n), timeout=PROBE_S)
        except (OSError, RuntimeError, TimeoutError):
            status, out = 1, ""
        phase, _, rc = out.strip().partition(" ")
        text = {"running": RUNNING, "waiting": WAITING, "lost": LOST}.get(phase, UNREADABLE)
        if status == 0 and phase == "completed":
            text = completed(rc.strip())
        lines.append(f"browser run #{n}: {text}")
    return lines


async def _probe(env, script: str) -> str:
    try:
        res = await run(env, script, timeout_s=PROBE_S)
    except (OSError, RuntimeError, TimeoutError):
        return "unreadable"
    return res.stdout.strip() if res.code == 0 else "unreadable"

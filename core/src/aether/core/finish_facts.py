"""Delivered state at the first finish request, as facts from Core's own records (AETHER_CORE_FINISH_FACTS=on).

Plan §7 change 6: at finish, report delivered state as facts — files changed against the start, processes still
running, and operations whose result was not shown or whose effect is unknown. No advice and no judgement: the model
reads what is there and decides. Shown once per run; calling finish again ends the work.

Why one observation: the finish path grew separate holds (pending terminals, a settle check). Each reported part of the
same state at a different moment. This module reads every operation owner (terminals, Python, MCP, browser) from the
same records the operation state machine keeps, and replaces the pending-terminal hold when on.

Earlier evidence bounds the claim. Added instructions at late decisions did not move outcomes (SR1, SR2, pp1, P4), and
a decisive history fact at finish was read as confirmation 0/12 (P2). The start snapshot did move outcomes in replay
(SN1). Whether this observation changes graded results is a model-facing question for a paired screen.
"""

from __future__ import annotations

import shlex
from typing import Any

from .env import alive_test, list_process_tree, run
from .finish_report import _files
from .operations import DONE

MAX_LISTED = 12


async def terminal_operations(terminals) -> list[str]:
    """Sample outstanding terminal receipts without waiting for work or consuming output."""
    pending = [(name, session) for name, session in sorted(terminals._sessions.items())
               if session.pending or session.dispatch_unconfirmed]
    if not pending:
        return []
    q = shlex.quote
    commands = []
    for index, (_, session) in enumerate(pending):
        path = q(f"{session.root}/done_{session.pending or session.seq}")
        # A matching receipt takes precedence over process liveness.
        commands.append(f"printf '%s ' {index}; if [ -s {path} ]; then head -c 160 {path} | tr '\\n' ' '; "
                        f"elif {alive_test(session.pid)}; then printf alive; "
                        "else printf absent; fi; printf '\\n'")
    try:
        response = await run(terminals._env, "; ".join(commands), timeout_s=2)
        statuses = dict((i, state.strip()) for i, _, state in
                        (line.partition(" ") for line in response.stdout.splitlines())) if response.code == 0 else {}
    except (OSError, RuntimeError, TimeoutError):
        statuses = {}
    lines = []
    for index, (name, session) in enumerate(pending):
        seq = session.pending or session.seq
        state = statuses.get(str(index), "")
        marker = DONE.match(state)
        if marker and int(marker[1]) == seq:
            status = f"completed with exit {marker[2]}; result not shown"
        elif state == "alive" and not session.dispatch_unconfirmed:
            status = "still running" + ("; result not shown" if session.unseen else "")
        else:
            status = "no verified completion; effect unknown"
        lines.append(f"terminal {name}: command #{seq} {status}")
    return lines


async def operations(s) -> list[str]:
    lines = await terminal_operations(s.terminals)
    repl = getattr(s, "repl", None)
    if repl is not None:
        if getattr(repl, "unconfirmed", False):
            lines.append(f"python: cell #{repl.pending or repl.seq} submission unconfirmed; effect unknown")
        elif getattr(repl, "pending", 0):
            lines.append(f"python: no completion collected for cell #{repl.pending}")
    mcp = getattr(s, "mcp", None)
    for ident, op in sorted(getattr(mcp, "ops", {}).items()):
        state = "no answer yet" if op.get("published") else "sending unconfirmed"
        lines.append(f"mcp {op.get('server')}: request #{ident} ({op.get('action')} {op.get('tool') or ''}".rstrip()
                     + f") {state}; effect unknown")
    car = getattr(getattr(s, "browser", None), "sidecar", None)
    for n, run in sorted(getattr(getattr(car, "runs", None), "open", {}).items()):
        lines.append(f"browser run #{n}: " + ("result not shown yet" if run.get("launched") else
                                               "launch unconfirmed; effect unknown"))
    return lines


async def observe(s) -> dict[str, Any]:
    written = {step.wrote for step in s.report_steps if step.wrote and not step.failed}
    files, total = await _files(s.env, s.workdir, s.config.control_dir, written, check_absence=True)
    identities = {pid: token for t in s.terminals._sessions.values() for pid, token in t.identity.items()}
    try:
        processes = await list_process_tree(s.env, [t.pid for t in s.terminals._sessions.values()], identities=identities)
    except OSError as exc:
        processes = [f"(process listing unavailable: {exc})"]
    return {"files": files, "files_total": total, "processes": processes, "operations": await operations(s)}


def render(row: dict[str, Any]) -> str:
    files = row["files"]
    if isinstance(files, str):
        changed = f"Changed files: unmeasured ({files})."
    elif not files:
        changed = "Current changed regular files since the task started: none observed."
    else:
        listed = "\n".join(f"- {f['path']}: " + ("deleted" if f.get("sha256") in (None, "-") else
                                                 f"{f['bytes']} bytes, sha256 {str(f['sha256'])[:12]}")
                           for f in files[:MAX_LISTED])
        more = row["files_total"] - min(len(files), MAX_LISTED)
        changed = (f"Changed files since the task started ({len(files)} current files measured):\n{listed}"
                   + (f"\n- {more} additional candidates omitted or unavailable" if more > 0 else ""))
    procs = row["processes"]
    running = ("Processes still running under your terminals:\n" + "\n".join(f"- {p}" for p in procs[:MAX_LISTED])
               if procs else "Processes still running under your terminals: none observed.")
    ops = row["operations"]
    pending = ("Operations not finished or not shown:\n" + "\n".join(f"- {o}" for o in ops)
               if ops else "Operations not finished or not shown: none.")
    return ("Delivered state at your finish request, as observed by Core:\n"
            f"{changed}\n{running}\n{pending}\nCalling finish again ends the work.")


async def at_finish(s) -> str | None:
    """The facts for the first finish of a worker run, or None (switch off, already shown, or too little time)."""
    if not getattr(s.config, "finish_facts", False) or s.result.extras.get("finish_facts") or s.remaining() < 15:
        return None
    row = await observe(s)
    s.result.extras["finish_facts"] = {k: (v if k != "files" or isinstance(v, str) else len(v)) for k, v in row.items()}
    s.trace("finish_facts", **{k: v for k, v in row.items() if k != "files"},
            files=row["files"] if isinstance(row["files"], str) else [f["path"] for f in row["files"]])
    return render(row)

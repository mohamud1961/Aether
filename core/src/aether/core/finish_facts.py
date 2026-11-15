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
import uuid
from typing import Any

from .env import alive_test, list_process_tree, run
from .finish_report import _files
from . import op_phases
from .operations import DONE, RUN

MAX_LISTED = 12
# Processes started after the run's start marker, from /proc (no ps or awk needed): "pid ppid command" per line.
# The scanning shell and its own children are skipped. Start times are boot time + start ticks, in whole seconds.
_STARTED_SINCE = (
    'm="$1/start_marker"; [ -e "$m" ] || { echo __NO_MARKER__; exit 0; }; t0=$(stat -c %Y "$m") || exit 3; '
    'bt=$(sed -n "s/^btime //p" /proc/stat); hz=$(getconf CLK_TCK 2>/dev/null || echo 100); me=$$; '
    'for d in /proc/[0-9]*; do p=${d#/proc/}; [ "$p" = "$me" ] && continue; '
    's=$(cat "$d/stat" 2>/dev/null) || continue; set -- ${s##*) }; [ "$2" = "$me" ] && continue; '
    '[ $((bt + ${20} / hz)) -ge "$t0" ] || continue; '
    'c=$(tr "\\000" " " < "$d/cmdline" 2>/dev/null); [ -n "$c" ] && echo "$p $2 $c"; done; true'
)


async def terminal_operations(terminals) -> list[str]:
    """Sample outstanding terminal receipts and start tokens without waiting for work or consuming output."""
    pending = [(name, session) for name, session in sorted(terminals._sessions.items())
               if session.pending or session.dispatch_unconfirmed]
    if not pending:
        return []
    q = shlex.quote
    commands = []
    for index, (_, session) in enumerate(pending):
        seq = session.pending or session.seq
        path, token = q(f"{session.root}/done_{seq}"), q(f"{session.root}/start_{seq}")
        # A matching receipt takes precedence over process liveness.
        commands.append(f"printf '%s ' {index}; if [ -s {path} ]; then head -c 160 {path} | tr '\\n' ' '; "
                        f"elif {alive_test(session.pid)}; then printf 'alive '; readlink {token} 2>/dev/null; "
                        f"else printf 'absent '; readlink {token} 2>/dev/null; fi; printf '\\n'")
    try:
        response = await run(terminals._env, "; ".join(commands), timeout_s=2)
        statuses = dict((i, state.strip()) for i, _, state in
                        (line.partition(" ") for line in response.stdout.splitlines())) if response.code == 0 else {}
    except (OSError, RuntimeError, TimeoutError):
        statuses = {}
    gated = terminals._preserve_existing  # commands run only after taking their start token
    lines = []
    for index, (name, session) in enumerate(pending):
        seq = session.pending or session.seq
        state, _, token = statuses.get(str(index), "").partition(" ")
        marker = DONE.match(state)
        if marker and int(marker[1]) == seq:
            status = op_phases.completed(marker[2])
        elif state == "alive" and (token == RUN or not (gated or session.dispatch_unconfirmed)):
            status = op_phases.RUNNING
        elif state == "alive" and not token:
            status = op_phases.WAITING
        elif state == "absent" and (token == RUN or not (gated or session.dispatch_unconfirmed)):
            status = op_phases.LOST
        else:
            status = op_phases.UNREADABLE
        lines.append(f"terminal {name}: command #{seq} {status}")
    return lines


async def operations(s) -> list[str]:
    """One line per operation whose result the model has not seen, stating the phase Core can prove (op_phases)."""
    lines = await op_phases.settle(s)
    lines += await terminal_operations(s.terminals)
    repl = getattr(s, "repl", None)
    if repl is not None:
        lines += await op_phases.python_phase(repl)
    if getattr(s, "mcp", None) is not None:
        lines += await op_phases.mcp_phases(s.mcp)
    runs = getattr(getattr(getattr(s, "browser", None), "sidecar", None), "runs", None)
    if runs is not None:
        lines += await op_phases.browser_phases(runs)
    return lines


async def started_elsewhere(s, listed: list[str]) -> list[str] | str:
    """Processes started during the run and still running that are not under a terminal (a daemon that forked away,
    a job run with setsid), excluding Core's own helpers. A string when the scan was unavailable (A6/A9)."""
    control, nonce = s.config.control_dir, f"aether-scan-{uuid.uuid4().hex}"
    try:  # the nonce marks the scan's own wrapper processes, which are skipped
        res = await run(s.env, f"sh -c {shlex.quote(_STARTED_SINCE)} {nonce} {shlex.quote(control)}", timeout_s=5)
    except (OSError, RuntimeError, TimeoutError) as exc:
        return f"unavailable ({type(exc).__name__})"
    if res.code != 0 or res.stdout.strip() == "__NO_MARKER__":
        return "unavailable (no start marker)" if res.code == 0 else f"unavailable (exit {res.code})"
    known = {int(t.pid) for t in s.terminals._sessions.values() if t.pid}
    known |= {int(line.split()[0]) for line in listed if line.split() and line.split()[0].isdecimal()}
    rows = []
    for line in res.stdout.splitlines():
        pid, _, rest = line.partition(" ")
        ppid, _, command = rest.partition(" ")
        if not pid.isdecimal() or int(pid) in known or int(ppid or 0) in known:
            continue
        if control in command or nonce in command or not command.strip():
            continue  # Core's own helpers (REPL server, MCP client, probes) run from the control directory
        rows.append(f"{pid} {command.strip()[:200]}")
    return rows


async def observe(s) -> dict[str, Any]:
    written = {step.wrote for step in s.report_steps if step.wrote and not step.failed}
    files, total = await _files(s.env, s.workdir, s.config.control_dir, written, check_absence=True)
    identities = {pid: token for t in s.terminals._sessions.values() for pid, token in t.identity.items()}
    try:
        processes = await list_process_tree(s.env, [t.pid for t in s.terminals._sessions.values()], identities=identities)
    except OSError as exc:
        processes = [f"(process listing unavailable: {exc})"]
    elsewhere = await started_elsewhere(s, processes if isinstance(processes, list) else [])
    return {"files": files, "files_total": total, "processes": processes, "started_elsewhere": elsewhere,
            "operations": await operations(s)}


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
    others = row.get("started_elsewhere", [])
    if isinstance(others, str):
        running += f"\nOther processes started during this run: {others}."
    else:
        running += ("\nOther processes started during this run and still running:\n"
                    + "\n".join(f"- {p}" for p in others[:MAX_LISTED]) if others else
                    "\nOther processes started during this run and still running: none observed.")
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

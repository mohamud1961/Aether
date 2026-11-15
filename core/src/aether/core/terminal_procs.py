"""What a terminal's command is doing: its live processes, busiest first, from /proc.

Split from terminal.py (module-size cap, 2026-10-26) with the code unchanged.
"""

from __future__ import annotations

import shlex

from .env import Environment, run

# One line per process: /proc/<pid>/stat, wait channel, command line. Plain sh + /proc, because many task images
# have no procps. Used to say what a still-running command is doing (D1 compcert: `opam install ... | tail` sat
# silent and asleep for 1300 s and the model saw only "(no new output)" five times before it looked).
_PROCS = (
    "cut -d' ' -f1 /proc/uptime 2>/dev/null; getconf CLK_TCK 2>/dev/null || echo 100; "
    "for d in /proc/[0-9]*; do s=$(cat $d/stat 2>/dev/null) || continue; w=$(cat $d/wchan 2>/dev/null); "
    "c=$(tr '\\0' ' ' < $d/cmdline 2>/dev/null | cut -c1-90); printf '%s\\t%s\\t%s\\n' \"$s\" \"$w\" \"$c\"; done"
)

_PY_PROCS = r"""
import os
import sys

with open("/proc/uptime", "rb") as f:
    uptime = f.read().split()[0]
hz = str(os.sysconf("SC_CLK_TCK")).encode()
lines = [uptime, hz]
for pid in sorted(os.listdir("/proc")):
    if not pid.isascii() or not pid.isdigit():
        continue
    root = "/proc/" + pid
    try:
        with open(root + "/stat", "rb") as f:
            stat = f.read().rstrip(b"\n")
    except OSError:
        continue
    try:
        with open(root + "/wchan", "rb") as f:
            wchan = f.read().rstrip(b"\n")
    except OSError:
        wchan = b""
    try:
        with open(root + "/cmdline", "rb") as f:
            raw = f.read().replace(b"\0", b" ")
        cmd = b"\n".join(part[:90] for part in raw.split(b"\n")).rstrip(b"\n")
    except OSError:
        cmd = b""
    lines.append(stat + b"\t" + wchan + b"\t" + cmd)
sys.stdout.buffer.write(b"\n".join(lines) + b"\n__AETHER_PROCESS_SCAN_COMPLETE__\n")
"""

# Publish only a complete fast result, and retain the shell observer when Python
# is absent, fails, or returns a partial snapshot.
_FAST_PROCS = (
    "if command -v python3 >/dev/null 2>&1 && "
    f"output=$(python3 -c {shlex.quote(_PY_PROCS)} 2>/dev/null); then "
    "case \"$output\" in *__AETHER_PROCESS_SCAN_COMPLETE__) "
    "output=${output%__AETHER_PROCESS_SCAN_COMPLETE__}; printf '%s' \"$output\"; exit 0;; esac; fi; "
    + _PROCS
)
_WRAPPERS = ("run.sh", "script -qfc", "bash --noprofile --norc")
_STATES = {
    "R": "running",
    "S": "sleeping",
    "D": "in uninterruptible I/O",
    "T": "stopped",
    "t": "stopped by a tracer",
    "Z": "exited (zombie)",
}


async def describe_processes(env: Environment, root_pid: int, limit: int = 4, *, fast: bool = False) -> list[str]:
    """What the terminal's command is doing: its live processes, busiest first (empty without /proc)."""
    res = await run(env, _FAST_PROCS if fast else _PROCS)
    head = res.stdout.split("\n", 2)
    try:
        if res.code != 0 or len(head) < 3:
            raise ValueError("process snapshot has no header")
        uptime, hz = float(head[0]), float(head[1]) or 100.0
    except ValueError:
        if fast:
            return await describe_processes(env, root_pid, limit)
        return []
    procs: dict[int, tuple[int, str, float, float, str, str]] = {}
    for line in head[2].splitlines():
        stat, _, rest = line.partition("\t")
        wchan, _, cmd = rest.partition("\t")
        pid_s, _, after = stat.partition(" (")
        comm, _, fields = after.rpartition(") ")
        f = fields.split()
        if not pid_s.isdigit() or len(f) < 20:
            continue
        cpu = (int(f[11]) + int(f[12])) / hz
        procs[int(pid_s)] = (
            int(f[1]),
            f[0],
            cpu,
            uptime - int(f[19]) / hz,
            wchan.strip(),
            cmd.strip() or comm,
        )
    tree, frontier = set(), {root_pid}
    while frontier:
        frontier = {
            p for p, v in procs.items() if v[0] in frontier and p not in tree
        }
        tree |= frontier
    shown = [
        (p, procs[p]) for p in tree if not any(w in procs[p][5] for w in _WRAPPERS)
    ]
    shown.sort(key=lambda item: -item[1][2])
    out = []
    for pid, (_ppid, state, cpu, age, wchan, cmd) in shown[:limit]:
        what = _STATES.get(state, state) + (
            f" in {wchan}" if state in "SD" and wchan not in ("", "0") else ""
        )
        out.append(f"{cmd} (pid {pid}, {what}, {cpu:.0f}s CPU in {age:.0f}s)")
    if len(shown) > limit:
        out.append(f"{len(shown) - limit} more")
    return out

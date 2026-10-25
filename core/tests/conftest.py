"""Every test stops the processes it left behind, and only those.

Core keeps a run's processes by default (END_PROCESSES=keep): in a task container they die with it, but these tests
run Core on the host, where each terminal shell and REPL server outlived its test. One full suite left ~60, and
repeated runs exhausted the process table (42 tests then failed with "fork failed").

Ownership, not command matching: a process is this test's if it appeared during the test and either descends from
this pytest process or works inside this pytest session's own temp directory (a terminal's shell cds into its
workdir, and keeps it after its run.sh exits or a test kills it and it is orphaned to init). Its descendants go with
it. Matching Core's shared /tmp/.aether directory or its wrapper commands would also select another session's Core
run. Never pytest itself or its ancestors. (Not by process group: a terminal's shell starts in a group of its own.)
"""

from __future__ import annotations

import os
from pathlib import Path
import signal
import shutil
import subprocess
import time

import pytest


def processes() -> dict[int, tuple[int, int, str]]:
    """pid -> (ppid, pgid, command) for every live process visible to this user (zombies are already dead)."""
    ps = subprocess.Popen(["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="], stdout=subprocess.PIPE, text=True)
    out = ps.communicate()[0]
    table = {}
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) == 5 and parts[0].isdigit() and int(parts[0]) != ps.pid and not parts[3].startswith("Z"):
            table[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[4])
    return table


def cwds(pids: set[int]) -> dict[int, str]:
    """pid -> working directory, for those of ``pids`` that can be read (/proc on Linux, lsof elsewhere)."""
    if not pids:
        return {}
    if Path("/proc/self/cwd").exists():
        found = {}
        for pid in pids:
            try:
                found[pid] = os.readlink(f"/proc/{pid}/cwd")
            except OSError:
                pass
        return found
    # The macOS system lsof is normally /usr/sbin/lsof, absent from the
    # intentionally reduced PATH of the local Gateway test runner. Preserve
    # process ownership cleanup instead of silently skipping leaked shells.
    lsof = shutil.which("lsof")
    if not lsof and Path("/usr/sbin/lsof").is_file():
        lsof = "/usr/sbin/lsof"
    if not lsof:
        raise RuntimeError(
            "test process cleanup unavailable: lsof not installed and /proc absent"
        )
    out = subprocess.run(
        [lsof, "-a", "-d", "cwd", "-Fpn", "-p", ",".join(map(str, sorted(pids)))], capture_output=True, text=True
    ).stdout
    found, pid = {}, None
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid is not None:
            found[pid] = line[1:]
    return found


def leftovers(before: set[int], root: str) -> list[int]:
    """Processes started since ``before`` that this pytest owns (see the module docstring), and every descendant."""
    table = processes()
    protected, pid = set(), os.getpid()
    while pid > 1 and pid not in protected:  # pytest and its ancestors are never touched
        protected.add(pid)
        pid = table.get(pid, (1, 0, ""))[0]
    new = {p for p in table if p not in before and p not in protected}
    mine = set()
    for p in new:
        q = table[p][0]
        while q > 1 and q not in mine and q != os.getpid():
            q = table.get(q, (1, 0, ""))[0]
        if q == os.getpid() or q in mine:
            mine.add(p)
    root = os.path.realpath(root)
    mine |= {p for p, d in cwds(new - mine).items() if os.path.realpath(d) == root or os.path.realpath(d).startswith(root + os.sep)}
    found, frontier = set(mine), set(mine)
    while frontier:
        frontier = {p for p, (ppid, _, _) in table.items() if ppid in frontier and p not in found | protected}
        found |= frontier
    return sorted(found)


def stop(pids: list[int]) -> None:
    if not pids:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in pids:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(0.2)


@pytest.fixture(autouse=True)
def stop_leftover_processes(tmp_path_factory):
    before = set(processes())
    yield
    stop(leftovers(before, str(tmp_path_factory.getbasetemp())))

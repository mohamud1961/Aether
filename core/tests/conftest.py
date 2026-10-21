"""Every test stops the processes it left behind.

Core keeps a run's processes by default (END_PROCESSES=keep): in a task container they die with it, but these tests
run Core on the host, where each terminal shell and REPL server outlived its test. One full suite left ~60, and
repeated runs exhausted the process table (42 tests then failed with "fork failed"). The kill is narrow: only
processes that appeared during the test whose command line names this session's temp directory or Core's control
directory, plus their descendants. Never pytest itself or its ancestors. (Not by process group: a terminal's shell
starts in a group of its own.) A terminal shell whose run.sh a test killed (to simulate a terminal dying) is
orphaned to init and names no marker, so a new orphan running Core's own wrapper shell command is stopped too.
"""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time

import pytest

from aether.core.env import _WRAPPER_CMDS, CONTROL_DIR


def processes() -> dict[int, tuple[int, int, str]]:
    """pid -> (ppid, pgid, command) for every process visible to this user."""
    out = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,pgid=,command="], capture_output=True, text=True, check=True
    ).stdout
    table = {}
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0].isdigit():
            table[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[3])
    return table


def leftovers(before: set[int], markers: list[str]) -> list[int]:
    """Processes started since ``before`` that a test owns: those naming one of ``markers``, and every descendant."""
    table = processes()
    protected, pid = set(), os.getpid()
    while pid > 1 and pid not in protected:  # pytest and its ancestors are never touched
        protected.add(pid)
        pid = table.get(pid, (1, 0, ""))[0]
    roots = {
        p
        for p, (ppid, _, cmd) in table.items()
        if p not in before
        and p not in protected
        and (any(m in cmd for m in markers) or (ppid == 1 and any(w in cmd for w in _WRAPPER_CMDS)))
    }
    found, frontier = set(roots), set(roots)
    while frontier:
        frontier = {p for p, (ppid, _, _) in table.items() if ppid in frontier and p not in found | protected}
        found |= frontier
    return sorted(found)


def stop(pids: list[int]) -> None:
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
    stop(leftovers(before, [str(Path(tmp_path_factory.getbasetemp()).resolve()), f"{CONTROL_DIR}/"]))

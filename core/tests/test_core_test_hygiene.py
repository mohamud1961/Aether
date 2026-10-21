"""The suite's process cleanup (conftest.py) finds what a keep-mode run leaves on the host, and nothing else."""

from __future__ import annotations

import asyncio
import os
import subprocess

from aether.core.terminal import Terminals
from tests.conftest import leftovers, processes, stop
from tests.core_fakes import LocalEnv


def test_a_kept_terminal_and_its_service_are_found_and_stopped(tmp_path):
    before = set(processes())
    work = tmp_path / "work"
    work.mkdir()

    async def go():
        t = Terminals(LocalEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl"))
        await t.use(input="nohup python3 -c 'import time; time.sleep(300)' > /dev/null 2>&1 & echo started")
        await asyncio.sleep(0.5)
        await t.close(keep=True)  # what run_agent does by default (END_PROCESSES=keep)
        return t.left_running

    kept = [int(line.split()[0]) for line in asyncio.run(go())]
    found = leftovers(before, [str(tmp_path.resolve())])
    shells = [p for p in found if "run.sh" in processes().get(p, (0, 0, ""))[2]]
    assert shells  # the terminal's own shell, which starts in a process group of its own
    assert kept and set(kept) <= set(found)  # the service is a descendant of the terminal shell that names tmp_path
    stop(found)
    assert not leftovers(before, [str(tmp_path.resolve())])
    for pid in kept:
        try:
            os.kill(pid, 0)
            alive = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout
            assert alive.strip().startswith("Z"), f"{pid} still running"
        except ProcessLookupError:
            pass


def test_processes_that_are_not_the_tests_are_left_alone(tmp_path):
    before = set(processes())
    other = subprocess.Popen(["sleep", "30"])  # started during the test, but names no marker
    try:
        assert other.pid not in leftovers(before, [str(tmp_path.resolve())])
        assert os.getpid() not in leftovers(set(), ["python", "pytest"])  # pytest itself is never a leftover
    finally:
        other.kill()
        other.wait()


def test_a_shell_orphaned_by_killing_its_run_sh_is_found(tmp_path):
    """test_core_terminal kills run.sh to simulate a dead terminal; the shell under it outlives it, orphaned to init."""
    before = set(processes())
    work = tmp_path / "work"
    work.mkdir()

    async def go():
        t = Terminals(LocalEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl"))
        await t.use(input="echo ready")
        pid = t._sessions["main"].pid
        os.kill(pid, 9)
        await asyncio.sleep(0.5)
        return pid

    killed = asyncio.run(go())
    table = processes()
    orphans = [p for p in set(table) - before if table[p][0] == 1 and "--noprofile" in table[p][2]]
    assert orphans, "the shell under the killed run.sh should outlive it"
    assert killed not in table and set(orphans) <= set(leftovers(before, [str(tmp_path.resolve())]))
    stop(leftovers(before, [str(tmp_path.resolve())]))

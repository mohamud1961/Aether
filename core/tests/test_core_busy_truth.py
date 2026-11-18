"""Busy tools tell the truth (reconcile 10-21): a call made while a REPL cell or terminal command is still running
reports the real state of that work, never a stale "still running", and never silently queues new work behind it.

Reproduces gcode-to-text e2 T12-T22 (REPL: six "a cell is still running" replies, interrupt=true never took effect)
and overfull-hbox e1 T24-T26 (terminal: kill commands queued behind the running solver for ~100 s).
"""

from __future__ import annotations

import asyncio
import os
import signal
import time

import pytest

from aether.core.repl import Repl
from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv


async def _repl(tmp_path):
    repl = Repl(LocalEnv(tmp_path), str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"))
    assert await repl.start()
    return repl


def _stop(repl):
    if repl.pid:
        try:
            os.kill(repl.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_repl_code_after_the_pending_cell_finished_runs_and_reports_that_cell(tmp_path):
    async def go():
        repl = await _repl(tmp_path)
        try:
            first = await repl.run("import time\ntime.sleep(1.5)\nprint('first-done')", wait_s=0.2)
            assert "still running" in first
            time.sleep(2.5)  # the cell finishes while nobody is waiting on it
            out = await repl.run("print('second-ran')")
            # known-bad (before the fix): "a cell is still running" although it had finished, and nothing ran
            assert "still running" not in out
            assert "first-done" in out and "second-ran" in out
        finally:
            _stop(repl)

    asyncio.run(go())


def test_repl_interrupt_with_code_stops_the_cell_then_runs_the_code(tmp_path):
    async def go():
        repl = await _repl(tmp_path)
        try:
            await repl.run("import time\ntime.sleep(60)", wait_s=0.5)
            started = time.monotonic()
            out = await repl.run("print('after-interrupt')", interrupt=True, wait_s=5)
            assert time.monotonic() - started < 15
            assert "KeyboardInterrupt" in out and "after-interrupt" in out
            assert "still running" not in out
        finally:
            _stop(repl)

    asyncio.run(go())


def test_repl_code_sent_while_a_cell_really_runs_is_not_run_and_says_so(tmp_path):
    async def go():
        repl = await _repl(tmp_path)
        try:
            await repl.run("import time\ntime.sleep(60)", wait_s=0.3)
            out = await repl.run("marker = 1")
            assert "still running" in out and "not run" in out
            await repl.run("", interrupt=True, wait_s=5)
            assert "False" in await repl.run("print('marker' in globals())")  # it really was not run
        finally:
            _stop(repl)

    asyncio.run(go())


_OPEN: list[Terminals] = []


@pytest.fixture(autouse=True)
def _close_terminals():
    yield
    while _OPEN:
        asyncio.run(_OPEN.pop().close())


def _terms(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    t = Terminals(LocalEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl"))
    _OPEN.append(t)
    return t


def test_terminal_command_sent_while_another_runs_is_not_queued_and_says_so(tmp_path):
    async def go():
        t = _terms(tmp_path)
        await t.use(input="sleep 3; echo first-done", wait_s=0.3)
        busy = await t.use(input="echo second-ran", wait_s=0.3)
        rest = await t.use(input="", wait_s=10)
        return busy, rest

    busy, rest = asyncio.run(go())
    assert "not sent" in busy and "still running" in busy
    # known-bad (before the fix): the second command was queued and ran once the first finished
    assert "first-done" in rest and "second-ran" not in rest


def test_terminal_command_after_the_previous_finished_unwatched_runs(tmp_path):
    async def go():
        t = _terms(tmp_path)
        await t.use(input="sleep 1; echo first-done", wait_s=0.2)
        time.sleep(2)
        return await t.use(input="echo second-ran", wait_s=5)

    out = asyncio.run(go())
    assert "first-done" in out and "second-ran" in out and "not sent" not in out

"""Aether Core terminals against a real local shell (no pty on macOS; pipe fallback)."""
from __future__ import annotations

import asyncio

from aether.core.terminal import Terminals
from tests.core.core_fakes import LocalEnv


def _terms(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    return Terminals(LocalEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl")), work


def test_shell_state_persists_and_exit_code_is_reported(tmp_path):
    async def go():
        t, work = _terms(tmp_path)
        out1 = await t.use(input="mkdir -p sub && cd sub && export FOO=bar")
        out2 = await t.use(input="pwd; echo $FOO; false")
        return out1, out2, work
    out1, out2, work = asyncio.run(go())
    assert "[terminal main started" in out1 and "[exit 0" in out1
    assert str(work / "sub") in out2 and "bar" in out2
    assert "[exit 1" in out2  # known-bad: a failing command must not be reported as success
    assert "__AETHER_DONE" not in out2


def test_long_command_returns_running_then_completes(tmp_path):
    async def go():
        t, _ = _terms(tmp_path)
        first = await t.use(input="sleep 2; echo finished-now", wait_s=0.5)
        second = await t.use(input="", wait_s=10)
        return first, second
    first, second = asyncio.run(go())
    assert "still running" in first and "finished-now" not in first
    assert "finished-now" in second and "[exit 0" in second


def test_interrupt_stops_a_running_command(tmp_path):
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="sleep 60", wait_s=0.5)
        stopped = await t.use(input="", interrupt=True, wait_s=10)
        after = await t.use(input="echo alive")
        return stopped, after
    stopped, after = asyncio.run(go())
    assert "[exit" in stopped and "alive" in after


def test_large_output_is_head_and_tail_with_log_path(tmp_path):
    async def go():
        t, _ = _terms(tmp_path)
        return await t.use(input="seq 1 20000")
    out = asyncio.run(go())
    assert out.startswith("[terminal main started")
    assert "\n1\n" in out and "20000" in out and "bytes omitted" in out and "out.log" in out
    assert len(out) < 13_000


def test_named_terminals_run_in_parallel(tmp_path):
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(name="build", input="sleep 3; echo built", wait_s=0.3)
        other = await t.use(name="explore", input="echo exploring")
        built = await t.use(name="build", input="", wait_s=10)
        return other, built, t.names
    other, built, names = asyncio.run(go())
    assert "exploring" in other and "built" in built and names == ["build", "explore"]


def test_a_command_that_reads_stdin_cannot_swallow_the_completion_marker(tmp_path):
    # D1 verified-compiler-build: apt-get/dpkg read the terminal's stdin, ate the queued marker line, and every
    # install was reported "still running" until wait_s ran out (240-600 s each).
    async def go():
        t, _ = _terms(tmp_path)
        first = await t.use(input="read -t 1 x; echo \"read-rc=$?\"", wait_s=8)
        multi = await t.use(input="read -t 1 y\necho second-line-ran", wait_s=8)
        return first, multi
    first, multi = asyncio.run(go())
    assert "[exit" in first and "still running" not in first and "read-rc=" in first
    assert "second-line-ran" in multi and "[exit 0" in multi

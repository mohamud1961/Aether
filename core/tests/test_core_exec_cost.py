"""Substrate round trips: three environment calls per inline file write and two per fast terminal command.

A file write keeps three calls on purpose: stage, commit and readback are each a boundary that a concurrent change
can fall between, and the file-lifecycle fault tests inject exactly there (a destination swapped before the commit,
a parent symlink pivoted after staging, bytes changed after the rename). Everything inside one of them is one call.

Every ``environment.exec`` is a network round trip on a remote sandbox (~0.2-0.5 s), so these tests count
environment calls, not seconds. The same behaviour is asserted next to each count: a lower count that lost a
symlink target, a directory refusal, output or a status line would be a regression, not a win.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from aether.core.env import put_bytes
from aether.core.terminal import TerminalGone, Terminals
from tests.core_fakes import LocalEnv

_OPEN: list[Terminals] = []


@pytest.fixture(autouse=True)
def _close_terminals():
    yield
    while _OPEN:  # a terminal outlives its test unless closed (no disposable container here)
        asyncio.run(_OPEN.pop().close())


def _terms(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    env = LocalEnv(work)
    terminals = Terminals(env, str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl"))
    _OPEN.append(terminals)
    return terminals, env


def test_an_inline_write_costs_three_environment_calls(tmp_path):
    env = LocalEnv(tmp_path)
    before = len(env.commands)
    asyncio.run(put_bytes(env, b"hello\n", str(tmp_path / "out.txt"), mode="640"))
    assert len(env.commands) - before == 3  # stage, commit, readback
    assert (tmp_path / "out.txt").read_text() == "hello\n"
    assert (tmp_path / "out.txt").stat().st_mode & 0o777 == 0o640


def test_a_symlink_write_target_is_followed_in_three_environment_calls(tmp_path):
    target = tmp_path / "target"
    target.write_text("before")
    (tmp_path / "alias").symlink_to("target")
    env = LocalEnv(tmp_path)
    before = len(env.commands)
    asyncio.run(put_bytes(env, b"after", str(tmp_path / "alias")))
    assert len(env.commands) - before == 3
    assert (tmp_path / "alias").is_symlink() and target.read_text() == "after"


def test_a_directory_write_target_is_refused_in_one_environment_call(tmp_path):
    directory = tmp_path / "out"
    directory.mkdir()
    (tmp_path / "alias").symlink_to(directory)
    env = LocalEnv(tmp_path)
    for path in (directory, tmp_path / "alias"):
        before = len(env.commands)
        with pytest.raises(OSError, match="write target is a directory"):
            asyncio.run(put_bytes(env, b"content", str(path)))
        assert len(env.commands) - before == 1
    assert list(directory.iterdir()) == [] and not list(tmp_path.glob("*.aether-*.tmp"))


def test_a_fast_command_costs_two_environment_calls(tmp_path):
    async def run():
        terminals, env = _terms(tmp_path)
        await terminals.use(input="true")
        before = len(env.commands)
        out = await terminals.use(input="echo hi")
        return len(env.commands) - before, out

    calls, out = asyncio.run(run())
    assert calls == 2  # the send (which also waits for the marker) and the read
    assert "hi\n" in out and "[exit 0" in out


def test_a_long_command_still_reports_its_output_and_status(tmp_path):
    async def run():
        terminals, env = _terms(tmp_path)
        await terminals.use(input="true")
        before = len(env.commands)
        first = await terminals.use(input="sleep 5; echo finished-later", wait_s=0.2)
        sent = len(env.commands) - before
        second = await terminals.use(input="", wait_s=15)
        return sent, first, second

    sent, first, second = asyncio.run(run())
    # The send (its short in-container wait finds nothing), the read, and the still-running process report.
    assert sent == 3
    assert "still running" in first and "finished-later" not in first
    assert "finished-later" in second and "[exit 0" in second


def test_a_dead_terminal_still_raises_terminal_gone_in_one_environment_call(tmp_path):
    async def run():
        terminals, env = _terms(tmp_path)
        await terminals.use(input="true")
        session = terminals._sessions["main"]
        os.kill(session.pid, 9)
        await asyncio.sleep(0.3)
        before = len(env.commands)
        with pytest.raises(TerminalGone):
            await terminals._write(session, "echo never\n")
        calls = len(env.commands) - before
        # The test killed this root itself; cleanup would truthfully report it unverified (missing before observation).
        terminals._sessions.pop("main")
        return calls

    assert asyncio.run(run()) == 1

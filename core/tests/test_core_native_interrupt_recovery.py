"""Actual PTY interruption, inherited signal state, and task prompt hooks."""

import asyncio
import os
import shlex
import sys
import time

import pytest

from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="native Linux PTY qualification"
)


class IgnoredInterruptEnv(LocalEnv):
    async def exec(self, command, **kwargs):
        # A real supervisor can inherit SIG_IGN from a background launcher.
        # Reproduce that disposition in the real subprocess, not a fake result.
        command = shlex.join(
            [
                sys.executable,
                "-c",
                'import os,signal,sys;signal.signal(signal.SIGINT,signal.SIG_IGN);os.execvp("/bin/sh",["sh","-c",sys.argv[1]])',
                command,
            ]
        )
        return await super().exec(command, **kwargs)


def test_interrupt_recovers_when_supervisor_ignores_sigint(tmp_path):
    async def go():
        terminal = Terminals(
            IgnoredInterruptEnv(tmp_path),
            str(tmp_path),
            lambda: 1000.0,
            control_dir=str(tmp_path / "ctl"),
        )
        try:
            assert "still running" in await terminal.use(input="sleep 60", wait_s=0.3)
            assert terminal._sessions["main"].pty
            started = time.monotonic()
            stopped = await terminal.use(interrupt=True, wait_s=4)
            assert time.monotonic() - started < 6
            assert "[exit 130" in stopped and "still running" not in stopped
            assert "recovered" in await terminal.use(input="echo recovered")
        finally:
            await terminal.close()

    asyncio.run(go())


@pytest.mark.parametrize("array", [False, True])
@pytest.mark.parametrize("prompt_exit", ["true", "false"])
def test_prompt_callback_and_shell_state_survive_interrupt(
    tmp_path, array, prompt_exit
):
    async def go():
        terminal = Terminals(
            LocalEnv(tmp_path),
            str(tmp_path),
            lambda: 1000.0,
            control_dir=str(tmp_path / "ctl"),
        )
        try:
            callback = shlex.quote("printf '%s\\n' $? >> prompt-status.log")
            callback = shlex.quote(shlex.split(callback)[0] + "; " + prompt_exit)
            value = f"({callback})" if array else callback
            assert "still running" in await terminal.use(
                input=f"PROMPT_COMMAND={value}; model_state=preserved; sleep 60",
                wait_s=0.3,
            )
            stopped = await terminal.use(interrupt=True, wait_s=4)
            assert "[exit 130" in stopped and "still running" not in stopped
            report = await terminal.use(
                input='echo "$model_state"; declare -p PROMPT_COMMAND'
            )
            assert "preserved" in report
            assert ("declare -a" in report) == array
            assert "130" in (tmp_path / "prompt-status.log").read_text().splitlines()
        finally:
            await terminal.close()

    asyncio.run(go())


def test_nested_bash_does_not_inherit_an_undefined_prompt_callback(tmp_path):
    async def go():
        terminal = Terminals(
            LocalEnv(tmp_path),
            str(tmp_path),
            lambda: 1000.0,
            control_dir=str(tmp_path / "ctl"),
        )
        try:
            out = await terminal.use(
                input="printf 'echo nested-ok\\nexit\\n' | bash --noprofile --norc -i"
            )
            assert "nested-ok" in out and "[exit 0" in out
            assert "command not found" not in out
        finally:
            await terminal.close()

    asyncio.run(go())


def test_nested_prompt_cannot_complete_the_parent_command(tmp_path):
    async def go():
        terminal = Terminals(
            LocalEnv(tmp_path),
            str(tmp_path),
            lambda: 1000.0,
            control_dir=str(tmp_path / "ctl"),
        )
        try:
            out = await terminal.use(
                input="export -f __aether_prompt_receipt; export __aether_prompt_owner __aether_prompt_seq; bash --noprofile --norc -i",
                wait_s=0.3,
            )
            assert "still running" in out and "[exit" not in out
            session = terminal._sessions["main"]
            assert not (tmp_path / "ctl/term/main" / f"done_{session.pending}").exists()
            out = await terminal.use(input="exit\n", mode="keys", wait_s=4)
            assert "[exit 0" in out
        finally:
            await terminal.close()

    asyncio.run(go())


def test_task_prompt_tail_is_preserved(tmp_path):
    async def go():
        terminal = Terminals(
            LocalEnv(tmp_path),
            str(tmp_path),
            lambda: 1000.0,
            control_dir=str(tmp_path / "ctl"),
        )
        try:
            await terminal.use(input="PS1='task-prompt> '")
            await terminal.use(input="sleep 60", wait_s=0.3)
            out = await terminal.use(interrupt=True, wait_s=4)
            assert "[exit 130" in out and "task-prompt>" in out
        finally:
            await terminal.close()

    asyncio.run(go())

"""The terminal must start in a task image without python3.

Found in the 2026-10-26 Flint baseline on Modal: 9 of 32 runs (every ``FROM ubuntu:24.04`` task image without a
Python install) had no terminal at all, because the launch ran ``python3 -c`` to reset SIGINT. The fault suite never
saw it: its image probe requires python3. This test pins a bare ``ubuntu:24.04`` (bash, setsid and script, no
python3). Skipped without Linux and docker, like the fault suite.
"""

from __future__ import annotations

import asyncio
import subprocess
import uuid

import pytest

from tests.test_core_faults_linux import DockerEnv, _terms, pytestmark  # noqa: F401 (skip marker)

BARE = "ubuntu:24.04"


@pytest.fixture
def bare():
    probe = subprocess.run(["docker", "run", "--rm", "--entrypoint", "sh", BARE, "-c",
                            "command -v bash && command -v setsid && ! command -v python3"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip(f"{BARE} is not available as a bare image (bash and setsid, no python3)")
    name = f"aether-bare-{uuid.uuid4().hex[:8]}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "--entrypoint", "sh", BARE, "-c",
                    "mkdir -p /app; while :; do sleep 3600; done"], check=True, capture_output=True)
    yield DockerEnv(name)
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def test_a_terminal_runs_commands_in_an_image_without_python3(bare):
    async def run():
        terminals = _terms(bare)
        try:
            first = await terminals.use(input="echo hello-$((40+2))", wait_s=10)
            second = await terminals.use(input="false", wait_s=10)
            return first, second
        finally:
            await terminals.close()

    first, second = asyncio.run(run())
    assert "hello-42" in first and "[exit 0" in first, first
    assert "[exit 1" in second, second


def test_ctrl_c_interrupts_a_foreground_command_without_python3(bare):
    """The python3 step existed to reset SIGINT; its replacement must keep Ctrl-C working."""
    async def run():
        terminals = _terms(bare)
        try:
            await terminals.use(input="sleep 300", wait_s=1)
            interrupted = await terminals.use(interrupt=True, wait_s=10)
            after = await terminals.use(input="echo still-alive", wait_s=10)
            return interrupted, after
        finally:
            await terminals.close()

    interrupted, after = asyncio.run(run())
    assert "still running" not in after and "still-alive" in after and "[exit 0" in after, (interrupted, after)


def _sleepers(env) -> list[str]:
    """PIDs of live `sleep 4242` processes, read from /proc (the bare image has no ps)."""
    script = ("for d in /proc/[0-9]*; do c=$(tr '\\000' ' ' < $d/cmdline 2>/dev/null); "
              "case \"$c\" in 'sleep 4242 '*) s=$(cat $d/stat); r=${s##*) }; "
              "[ \"${r%% *}\" != Z ] && echo ${d#/proc/};; esac; done")
    out = subprocess.run(["docker", "exec", env.container, "sh", "-c", script], capture_output=True, text=True)
    return out.stdout.split()


def test_close_stops_and_verifies_a_background_job_without_python3(bare):
    async def run():
        terminals = _terms(bare)
        await terminals.use(input="sleep 4242 & sleep 4242 & echo started", wait_s=10)
        before = _sleepers(bare)
        await terminals.close()
        return before, terminals.cleanup_receipt

    before, receipt = asyncio.run(run())
    assert len(before) == 2, before
    assert receipt.get("status") == "confirmed_stopped", receipt
    assert _sleepers(bare) == [], "a background job outlived a cleanup reported as confirmed"


def _sigint_ignored(env, body: str) -> bool:
    """Run ``body`` as a script started with SIGINT ignored; report whether the script's shell still ignores it."""
    script = body + "\ngrep '^SigIgn' /proc/$$/status\n"
    subprocess.run(["docker", "exec", "-i", env.container, "sh", "-c", "cat > /tmp/reset_probe.sh"],
                   input=script, text=True, check=True)
    out = subprocess.run(["docker", "exec", env.container, "sh", "-c", "trap '' INT; sh /tmp/reset_probe.sh"],
                         capture_output=True, text=True).stdout
    mask = int(out.split()[-1], 16)
    return bool(mask & (1 << 1))  # SIGINT is signal 2: bit 1


def test_the_launch_preamble_restores_sigint_without_python3(bare):
    """Without the preamble, a shell that starts with SIGINT ignored keeps it ignored and Ctrl-C does nothing."""
    from aether.core.terminal_session import SIGINT_RESET

    assert _sigint_ignored(bare, "true"), "probe cannot see an ignored SIGINT"
    assert not _sigint_ignored(bare, SIGINT_RESET)

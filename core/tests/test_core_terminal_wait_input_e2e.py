"""A selected wait ends when a pending command asks for input (real Linux shells).

Without this, a wait on a command blocked at a prompt ran out its whole time: the command cannot finish until someone
answers, and the model learned that only when the wait expired.
"""

import asyncio
import os
import time

import pytest

from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="native Linux shell qualification"
)


@pytest.mark.parametrize("preserve", [False, True])
def test_wait_wakes_on_a_prompt_and_the_answered_command_completes(tmp_path, preserve):
    async def go():
        t = Terminals(LocalEnv(tmp_path), str(tmp_path), lambda: 1000.0,
                      control_dir=str(tmp_path / "ctl"), preserve_existing=preserve)
        try:
            await t.use(name="ask", input="printf 'Proceed? [y/N] '; read answer; echo got-$answer", wait_s=0)
            started = time.monotonic()
            seen = await t.wait_events(["ask"], mode="all", wait_s=60)
            assert time.monotonic() - started < 45  # well under the 60 s wait; the wake needs two 4 s quiet rounds
            assert seen["pending"] == ["ask"] and not seen["completed"]
            assert seen["waiting_for_input"][0]["last_line"].rstrip().endswith("Proceed? [y/N]")
            answered = await t.use(name="ask", input="y\n", mode="keys", wait_s=0)
            done = await t.wait_events(["ask"], mode="all", wait_s=10)
            assert done["completed"][0]["exit"] == 0
            assert "got-y" in answered + done["completed"][0]["observation"]
        finally:
            await t.close()

    asyncio.run(go())


def test_a_quiet_command_without_a_prompt_does_not_end_the_wait(tmp_path):
    async def go():
        t = Terminals(LocalEnv(tmp_path), str(tmp_path), lambda: 1000.0, control_dir=str(tmp_path / "ctl"))
        try:
            await t.use(name="q", input="echo building; sleep 12; echo built", wait_s=0)
            seen = await t.wait_events(["q"], mode="all", wait_s=30)
            assert "waiting_for_input" not in seen
            assert seen["completed"][0]["exit"] == 0
        finally:
            await t.close()

    asyncio.run(go())

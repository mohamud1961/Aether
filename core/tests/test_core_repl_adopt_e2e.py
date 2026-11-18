"""A restarted controller adopts the Python REPL server the earlier one left running (real Linux, real server).

The first controller is dropped without close(), as a killed process leaves it: its server keeps running in the
sandbox with the model's variables. A second controller then starts from the same directory.
"""

import asyncio
import os
import signal

import pytest

from aether.core.repl import Repl
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")


def controller(tmp_path, track=True, conversation=None):
    repl = Repl(LocalEnv(tmp_path), str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"),
                track_operations=track)
    repl.conversation = conversation
    return repl


def test_variables_survive_and_a_running_cell_is_shown_once(tmp_path):
    async def go():
        first = controller(tmp_path, conversation=set())
        first.delivery_tag = lambda: "call_1"
        assert await first.start()
        assert "[python cell 1: ok" in await first.run("x = 41", wait_s=10)
        slow = "import time\ntime.sleep(3)\nx += 1\nprint('cell-done', x)"
        assert "still running" in await first.run(slow, wait_s=0)
        server = first.pid
        del first  # the controller dies; its server does not

        second = controller(tmp_path, conversation={"call_1"})
        try:
            assert await second.start()
            assert second.pid == server  # adopted, not relaunched
            shown = await second.run("print('fresh-output')", wait_s=10)
            assert "adopted from an earlier controller" in shown and "variables are kept" in shown
            assert "[code not run" in shown and "fresh-output" not in shown  # the unseen cell comes first
            waited = await second.run("", wait_s=10)
            assert (shown + waited).count("cell-done 42") == 1
            again = await second.run("print('x is', x)", wait_s=10)
            assert "x is 42" in again and "cell-done" not in again  # shown once; variables kept
            assert "[python cell 3: ok" in again  # numbering continues after the adopted cell 2
        finally:
            await second.close()

    asyncio.run(go())


def test_a_staged_submission_that_never_became_a_cell_is_cancelled(tmp_path):
    async def go():
        first = controller(tmp_path, conversation=set())
        assert await first.start()
        assert "[python cell 1: ok" in await first.run("y = 1", wait_s=10)
        (tmp_path / "repl" / "in" / "2.tmp").write_text("open('effect', 'w').write('ran')")  # mv never happened
        del first

        second = controller(tmp_path, conversation=set())
        try:
            assert await second.start()
            shown = await second.run("print('after', y)", wait_s=10)
            assert "cell 2 was never started" in shown and "after 1" in shown
            (tmp_path / "repl" / "in" / "2.tmp").rename(tmp_path / "repl" / "in" / "2.py")  # a late arrival
            await asyncio.sleep(0.5)
            assert not (tmp_path / "effect").exists()  # the revoked cell never runs
        finally:
            await second.close()

    asyncio.run(go())


def test_a_result_read_by_a_controller_that_died_is_shown_again_once(tmp_path):
    async def go():
        first = controller(tmp_path, conversation=set())
        first.delivery_tag = lambda: "call_7"
        assert await first.start()
        assert "only-once" in await first.run("print('only-once')", wait_s=10)
        del first  # it read the result for call_7, but call_7 never reached the conversation below

        second = controller(tmp_path, conversation={"call_6"})
        try:
            assert await second.start()
            shown = await second.run("", wait_s=5)
            assert shown.count("only-once") == 1
            assert "only-once" not in await second.run("print('next')", wait_s=10)
        finally:
            await second.close()

    asyncio.run(go())


def test_without_tracking_a_new_controller_loses_the_variables(tmp_path):
    """Known-bad: the untracked REPL wipes and relaunches, so the model's variables are gone."""
    async def go():
        first = controller(tmp_path, track=False)
        assert await first.start()
        await first.run("x = 41", wait_s=10)
        server = first.pid
        del first
        second = controller(tmp_path, track=False)
        try:
            assert await second.start()
            assert second.pid != server
            assert "NameError" in await second.run("print(x)", wait_s=10)
        finally:
            await second.close()
            try:
                os.kill(server, signal.SIGKILL)  # the first server, left behind by the untracked relaunch
            except ProcessLookupError:
                pass

    asyncio.run(go())

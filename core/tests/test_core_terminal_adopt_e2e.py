"""A restarted controller adopts terminals from the sandbox records of the one that died (real Linux shells).

The first controller is dropped without close(), as a killed process would leave it: its detached shell and
command keep running in the sandbox. A second controller then works from the same control directory.
"""

import asyncio
import os
import signal
from pathlib import Path

import pytest

from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="native Linux shell qualification"
)

GATED = "printf started > marker; while [ ! -e release ]; do sleep .1; done; printf once >> output; (exit 3)"


def controller(tmp_path, preserve=True):
    return Terminals(LocalEnv(tmp_path), str(tmp_path), lambda: 1000.0,
                     control_dir=str(tmp_path / "ctl"), preserve_existing=preserve)


async def until(path: Path, timeout=10.0):
    for _ in range(int(timeout * 10)):
        if path.exists():
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(path)


def test_running_command_is_adopted_and_completes_once(tmp_path):
    async def go():
        first = controller(tmp_path)
        assert "still running" in await first.use(name="export", input=GATED, wait_s=0.3)
        await until(tmp_path / "marker")
        del first  # the controller dies; its shell does not

        second = controller(tmp_path)
        try:
            seen = await second.wait_events(["export"], mode="all", wait_s=0)
            assert seen["adopted"][0]["state"] == "running" and seen["adopted"][0]["sequence"] == 1
            assert seen["pending"] == ["export"] and not seen["unknown"]
            refused = await second.use(name="export", input="printf duplicate >> output", wait_s=1)
            assert "still running its previous command" in refused
            (tmp_path / "release").touch()
            done = await second.wait_events(["export"], mode="all", wait_s=10)
            assert [(c["sequence"], c["exit"]) for c in done["completed"]] == [(1, 3)]
            assert (tmp_path / "output").read_text() == "once"
            again = await second.wait_events(["export"], mode="all", wait_s=0)
            assert not again["completed"]  # a completion is delivered once
            assert "[exit 0" in await second.use(name="export", input="printf next > after", wait_s=5)
            assert (tmp_path / "after").read_text() == "next"
        finally:
            await second.close()

    asyncio.run(go())


def test_completion_during_the_gap_is_delivered_once_with_its_output(tmp_path):
    async def go():
        first = controller(tmp_path)
        assert "still running" in await first.use(name="job", input="sleep 0.5; echo finished-output; (exit 4)",
                                                  wait_s=0.1)
        del first
        await until(tmp_path / "ctl" / "term" / "job" / "done_1")

        second = controller(tmp_path)
        try:
            seen = await second.wait_events(["job"], mode="all", wait_s=2)
            assert seen["adopted"][0]["state"] == "completed"
            (only,) = seen["completed"]
            assert (only["sequence"], only["exit"]) == (1, 4) and "finished-output" in only["observation"]
            assert not (await second.wait_events(["job"], mode="all", wait_s=0))["completed"]
        finally:
            await second.close()

    asyncio.run(go())


def test_an_earlier_receipt_never_completes_the_next_command(tmp_path):
    async def go():
        first = controller(tmp_path)
        assert "[exit 0" in await first.use(name="main", input="true", wait_s=5)
        del first

        second = controller(tmp_path)
        try:
            note = await second.use(name="main", input=GATED, wait_s=0.5)
            assert "adopted" in note and "still running" in note
            root = tmp_path / "ctl" / "term" / "main"
            assert (root / "done_1").exists() and not (root / "done_2").exists()
            assert second._sessions["main"].pending == 2
            (tmp_path / "release").touch()
            done = await second.wait_events(["main"], mode="all", wait_s=10)
            assert [(c["sequence"], c["exit"]) for c in done["completed"]] == [(2, 3)]
        finally:
            await second.close()

    asyncio.run(go())


def test_written_but_unconfirmed_command_is_reported_and_never_run(tmp_path):
    async def go():
        first = controller(tmp_path)
        assert "[exit 0" in await first.use(name="w", input="true", wait_s=5)
        root = tmp_path / "ctl" / "term" / "w"
        # The controller died after staging command 2 and before writing it to the shell.
        staged = (root / "pending").read_text().replace("' 1 \"$__aether_s\"", "' 2 \"$__aether_s\"")
        (root / "pending").write_text(staged.replace("cmd_1.sh", "cmd_2.sh"))
        (root / "cmd_2.sh").write_text("printf ran > unconfirmed\n")
        del first

        second = controller(tmp_path)
        try:
            out = await second.use(name="w", input="printf fresh > fresh", wait_s=0)
            assert "never confirmed delivered" in out and "input not sent" in out
            assert second.adoptions[0]["state"] == "dispatch_unconfirmed"
            assert not (tmp_path / "unconfirmed").exists() and not (tmp_path / "fresh").exists()
            assert "[exit 0" in await second.use(name="separate", input="printf fresh > fresh", wait_s=5)
            assert (tmp_path / "fresh").read_text() == "fresh"
        finally:
            await second.close()

    asyncio.run(go())


def test_delivered_command_without_ack_cannot_queue_a_second_effect(tmp_path):
    async def go():
        first = controller(tmp_path)
        assert "still running" in await first.use(name="export", input=GATED, wait_s=0.3)
        shell = first._sessions["export"]
        await until(tmp_path / "marker")
        # Reproduce the visible state at the gap between FIFO delivery and acknowledgement.
        (Path(shell.root) / "sent_1").unlink()
        second = controller(tmp_path)
        try:
            note = await second.use(name="export", input="printf duplicate >> output", wait_s=0)
            (tmp_path / "release").touch()
            seen = await second.wait_events(["export"], mode="all", wait_s=5)
            assert "input not sent" in note
            assert [(r["sequence"], r["exit"]) for r in seen["completed"]] == [(1, 3)]
            assert (tmp_path / "output").read_bytes() == b"once"
        finally:
            (tmp_path / "release").touch()
            await first.close()

    asyncio.run(go())


def test_interactive_input_preserves_the_outstanding_command_on_restart(tmp_path):
    async def go():
        first = controller(tmp_path)
        second = controller(tmp_path)
        try:
            command = (
                "printf ready > prompt; read -r answer; printf '%s' \"$answer\" > accepted; "
                "while [ ! -e release ]; do sleep .1; done; printf exported > result; (exit 3)"
            )
            await first.use(name="job", input=command, wait_s=0)
            await until(tmp_path / "prompt")
            await first.use(name="job", input="violet\n", mode="keys", wait_s=0)
            await until(tmp_path / "accepted")
            assert (tmp_path / "accepted").read_text() == "violet"
            outcome = await second.wait_events(["job"], mode="all", wait_s=0)
            assert outcome["pending"] == ["job"] and not outcome["unknown"]
            assert outcome["adopted"][0]["sequence"] == 1
            (tmp_path / "release").touch()
            complete = await second.wait_events(["job"], mode="all", wait_s=5)
            assert [(row["sequence"], row["exit"]) for row in complete["completed"]] == [(1, 3)]
            assert (tmp_path / "result").read_text() == "exported"
        finally:
            (tmp_path / "release").touch()
            await first.close()

    asyncio.run(go())


def test_dead_shell_with_no_receipt_is_observed_before_replacement(tmp_path):
    async def go():
        first = controller(tmp_path)
        assert "still running" in await first.use(name="d", input=GATED, wait_s=0.3)
        pid = first._sessions["d"].pid
        del first
        os.kill(pid, signal.SIGKILL)
        await asyncio.sleep(0.3)

        second = controller(tmp_path)
        try:
            out = await second.use(name="d", input="printf hi > hi", wait_s=5)
            assert "effect is unknown" in out and "input not sent" in out
            assert not (tmp_path / "hi").exists()
            assert second.adoptions[0]["state"] == "lost"
            await second.use(name="d", input="", wait_s=0)
            await second.use(name="d", input="printf hi > hi", wait_s=5)
            assert second._sessions["d"].root.endswith("/d.1")
            assert (tmp_path / "hi").read_text() == "hi"
        finally:
            (tmp_path / "release").touch()  # the orphaned command of the killed shell
            await second.close()

    asyncio.run(go())


def test_a_shell_whose_start_time_differs_is_not_adopted(tmp_path):
    async def go():
        first = controller(tmp_path)
        assert "still running" in await first.use(name="x", input=GATED, wait_s=0.3)
        (tmp_path / "ctl" / "term" / "x" / "birth").write_text("1\n")
        del first
        second = controller(tmp_path)
        try:
            with pytest.raises(RuntimeError, match="not the shell recorded"):
                await second.use(name="x", input="true", wait_s=1)
        finally:
            (tmp_path / "release").touch()
            await second.close()

    asyncio.run(go())


def test_without_preservation_no_records_are_written(tmp_path):
    async def go():
        stock = controller(tmp_path, preserve=False)
        try:
            assert "[exit 0" in await stock.use(name="s", input="true", wait_s=5)
            root = tmp_path / "ctl" / "term" / "s"
            assert not (root / "sent_1").exists() and not (root / "mode").exists()
        finally:
            await stock.close()

    asyncio.run(go())

"""Aether Core terminals against a real local shell (no pty on macOS; pipe fallback)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from aether.core.terminal import Terminals
from tests.core.core_fakes import LocalEnv


_OPEN: list[Terminals] = []


@pytest.fixture(autouse=True)
def _close_terminals():
    yield
    while (
        _OPEN
    ):  # a terminal outlives its test unless closed (no disposable container here)
        asyncio.run(_OPEN.pop().close())


def _terms(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    t = Terminals(
        LocalEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl")
    )
    _OPEN.append(t)
    return t, work


def test_shell_state_persists_and_exit_code_is_reported(tmp_path):
    async def go():
        t, work = _terms(tmp_path)
        out1 = await t.use(input="mkdir -p sub && cd sub && export FOO=bar")
        out2 = await t.use(input="pwd; echo $FOO; false")
        return out1, out2, work

    out1, out2, work = asyncio.run(go())
    assert "[terminal main started" in out1 and "[exit 0" in out1
    assert str(work / "sub") in out2 and "bar" in out2
    assert (
        "[exit 1" in out2
    )  # known-bad: a failing command must not be reported as success
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
    assert (
        "\n1\n" in out
        and "20000" in out
        and "bytes omitted" in out
        and "out.log" in out
    )
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
        first = await t.use(input='read -t 1 x; echo "read-rc=$?"', wait_s=8)
        multi = await t.use(input="read -t 1 y\necho second-line-ran", wait_s=8)
        return first, multi

    first, multi = asyncio.run(go())
    assert "[exit" in first and "still running" not in first and "read-rc=" in first
    assert "second-line-ran" in multi and "[exit 0" in multi


def test_one_call_blocks_at_most_max_wait(tmp_path, monkeypatch):
    # D1 extract-moves: a single 900 s wait starved the review schedule; waits are capped.
    from aether.core import terminal

    monkeypatch.setattr(terminal, "MAX_WAIT_S", 1.0)

    async def go():
        t, _ = _terms(tmp_path)
        return await t.use(input="sleep 5; echo late", wait_s=900)

    out = asyncio.run(go())
    assert "still running after 1s" in out or "still running after 2s" in out


@pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="process report reads /proc (Linux)"
)
def test_still_running_reports_what_the_command_is_doing(tmp_path):
    # D1 compcert: a silent `opam install | tail` slept for 1300 s behind five bare "(no new output)" results.
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="true")
        out = await t.use(input="sleep 40 | cat", wait_s=11)
        await t.use(interrupt=True)
        return out

    out = asyncio.run(go())
    assert "still running" in out and "no new output for 1" in out
    line = out.split("[its processes: ", 1)[1]
    assert "sleep 40 (pid " in line and "sleeping" in line and "s CPU in " in line
    assert (
        "bash --noprofile" not in line and "run.sh" not in line
    )  # the terminal's own wrappers are not listed


@pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="needs a pty (Linux script)"
)
def test_ctrl_c_typed_as_keys_does_not_wait_for_the_killed_command(tmp_path):
    # D1 compcert: "\x03" sent in keys mode killed opam, then the call waited 31 s for a marker that never came.
    import time

    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="sleep 60", wait_s=0.5)
        start = time.monotonic()
        stopped = await t.use(input="\\x03", mode="keys", wait_s=20)
        took = time.monotonic() - start
        after = await t.use(input="echo alive")
        return stopped, took, after

    stopped, took, after = asyncio.run(go())
    assert took < 6 and "still running" not in stopped
    assert "alive" in after and "[exit 0" in after


def test_close_stops_every_terminal_and_what_runs_in_it(tmp_path):
    # Tests and clones run outside a disposable container: leftover shells exhausted the host's process table.
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="true")
        await t.use(name="b", input="sleep 300", wait_s=0.5)
        pids = [s.pid for s in t._sessions.values()]
        await t.close()
        await asyncio.sleep(0.5)
        alive = []
        for pid in pids:
            try:
                os.kill(pid, 0)
                alive.append(pid)
            except ProcessLookupError:
                pass
        return alive, t.names

    alive, names = asyncio.run(go())
    assert alive == [] and names == []


def test_close_keep_leaves_a_started_service_running_and_records_it(tmp_path):
    # E0 package-server: a server the task needs at grading was started with nohup ... & and killed at run end.
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="nohup python3 -c 'import time; time.sleep(300)' > /dev/null 2>&1 & echo started")
        await asyncio.sleep(0.5)
        await t.close(keep=True)
        return t.left_running

    left = asyncio.run(go())
    services = [line for line in left if "time.sleep(300)" in line]
    try:
        assert len(services) == 1
        pid = int(services[0].split()[0])
        os.kill(pid, 0)  # still alive: keep killed nothing
        assert not any("script -qfc" in line or "--noprofile" in line for line in left)
    finally:
        for line in left:  # this test runs on the host, not in a disposable container
            try:
                os.kill(int(line.split()[0]), 9)
            except (ProcessLookupError, ValueError):
                pass


@pytest.mark.skipif(not os.path.isdir("/proc/1"), reason="the /proc tree walk (task containers) is what reaches nohup'd jobs")
def test_close_stop_kills_a_nohup_service(tmp_path):
    # The baseline: the same service does not survive close() (known-bad for keep).
    async def go():
        t, _ = _terms(tmp_path)
        out = await t.use(input="nohup python3 -c 'import time; time.sleep(301)' > /dev/null 2>&1 & echo $!")
        pid = int([w for w in out.split() if w.isdigit()][0])
        await t.close()
        await asyncio.sleep(0.5)
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    assert asyncio.run(go()) is False


def test_a_fast_command_s_output_is_complete_when_its_exit_is_reported(tmp_path):
    """The marker is found before the size is read; the other way round, output was sometimes cut short."""

    async def go():
        t, _ = _terms(tmp_path)
        return [await t.use(input=f"seq 1 2000; echo end-{i}") for i in range(15)]

    for i, out in enumerate(asyncio.run(go())):
        assert "[exit 0 " in out and f"end-{i}" in out and "\n2000\n" in out, out[-300:]


def test_a_terminal_that_died_between_calls_is_restarted_and_the_input_runs(tmp_path):
    # V3: once a terminal's shell was gone, every later call to it returned "terminal is not running"
    async def go():
        t, work = _terms(tmp_path)
        await t.use(input="export FOO=old")
        os.kill(t._sessions["main"].pid, 9)
        await asyncio.sleep(0.5)
        out = await t.use(input="echo ran-$FOO-here")
        again = await t.use(input="echo second")
        return out, again

    out, again = asyncio.run(go())
    assert (
        "not running" in out
        and "fresh terminal main was started" in out
        and "state" in out
    )
    assert (
        "ran--here" in out and "[exit 0" in out
    )  # it ran, in a new shell without the old variable
    assert "[exit 0" in again and "fresh" not in again


def test_a_deleted_control_directory_restarts_the_terminal_without_crashing(tmp_path):
    import shutil

    async def go():
        t, work = _terms(tmp_path)
        await t.use(input="echo first")
        shutil.rmtree(tmp_path / "ctl")
        return await t.use(input="echo after-delete")

    out = asyncio.run(go())
    assert "after-delete" in out and "[exit 0" in out and "fresh terminal main" in out


def test_keys_for_a_dead_interactive_program_are_not_replayed_as_shell_commands(
    tmp_path,
):
    import shutil

    async def go():
        t, work = _terms(tmp_path)
        await t.use(input="echo initialized")
        shutil.rmtree(tmp_path / "ctl")
        out = await t.use(input="touch UNINTENDED\n", mode="keys")
        return out, work

    out, work = asyncio.run(go())
    assert "keystrokes were not sent" in out and not (work / "UNINTENDED").exists()


def test_restart_preserves_the_full_log_at_its_original_handle(tmp_path):
    import re

    async def go():
        t, work = _terms(tmp_path)
        first = await t.use(input="printf 'ORIGINAL-LOG\\n'; seq 1 20000")
        path = re.search(r"full output is in ([^\s\]]+)", first).group(1)
        os.kill(t._sessions["main"].pid, 9)
        await asyncio.sleep(0.3)
        again = await t.use(input="echo NEW-LOG")
        return path, again

    path, again = asyncio.run(go())
    assert "NEW-LOG" in again
    assert (
        "ORIGINAL-LOG" in Path(path).read_text()
        and len(Path(path).read_bytes()) > 100000
    )


def test_restart_cannot_collide_with_another_valid_terminal_name(tmp_path):
    async def go():
        terminals, _ = _terms(tmp_path)
        await terminals.use(
            name="main-1", input="export KEEP=independent; echo ORIGINAL"
        )
        other_log = Path(terminals._sessions["main-1"].log)
        await terminals.use(name="main", input="echo first")
        os.kill(terminals._sessions["main"].pid, 9)
        await asyncio.sleep(0.3)
        await terminals.use(name="main", input="echo restarted")
        observed = await terminals.use(name="main-1", input="echo $KEEP")
        return observed, other_log.read_text()

    observed, log = asyncio.run(go())
    assert "independent" in observed and "ORIGINAL" in log


@pytest.mark.parametrize("lose_launch_reply", [False, True])
def test_failed_startup_after_launch_still_has_an_owned_process_to_close(
    tmp_path, lose_launch_reply
):
    class StartupFails(LocalEnv):
        async def exec(self, command, **kwargs):
            result = await super().exec(command, **kwargs)
            if lose_launch_reply and "nohup" in command:
                raise OSError("launch reply lost after actual launch")
            return result

    async def go():
        work = tmp_path / "work"
        work.mkdir()
        terminals = Terminals(
            StartupFails(work),
            str(work),
            lambda: 1000,
            control_dir=str(tmp_path / "ctl"),
        )
        if not lose_launch_reply:

            async def fail_init(session, text):
                raise OSError("initial input failed after actual launch")

            terminals._write = fail_init
        try:
            with pytest.raises(OSError):
                await terminals.use(input="echo never")
            pid = int((tmp_path / "ctl/term/main/pid").read_text())
            await terminals.close()
            await asyncio.sleep(0.1)
            from aether.core.env import alive_test, run

            alive = await run(terminals._env, alive_test(pid))
            assert alive.code != 0, f"owned startup process {pid} survived close"
        finally:
            # The before-fix control must not leak its real process.
            pid_file = tmp_path / "ctl/term/main/pid"
            if pid_file.exists():
                from aether.core.env import stop_process_tree

                await stop_process_tree(terminals._env, [int(pid_file.read_text())])

    asyncio.run(go())

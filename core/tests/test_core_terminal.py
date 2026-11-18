"""Aether Core terminals against a real local shell (no pty on macOS; pipe fallback)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv


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
    # D1 compile-compcert: apt-get/dpkg read the terminal's stdin, ate the queued marker line, and every
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
    # E0 pypi-server: a server the task needs at grading was started with nohup ... & and killed at run end.
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

                # Cleanup now rejects an already absent root as unverified
                # rather than inventing descendant ownership. Do not request
                # another cleanup after the independent liveness check passed.
                from aether.core.env import alive_test, run
                check = await run(terminals._env, alive_test(int(pid_file.read_text())))
                if check.code == 0:
                    await stop_process_tree(terminals._env, [int(pid_file.read_text())])

    asyncio.run(go())


def test_a_failing_pipeline_stage_is_reported_not_hidden(tmp_path):
    # `cmd | tee log` exits 0 when cmd fails; the shell's exit stays as it is, the failed stage is shown
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="true")
        masked = await t.use(input="echo a; false | cat")
        clean = await t.use(input="true | cat")
        failed_last = await t.use(input="echo x | { cat >/dev/null; false; }")
        returned = await t.use(input="f() { return 4; }; f")
        continued = await t.use(input="echo one \\\n two")
        return masked, clean, failed_last, returned, continued

    masked, clean, failed_last, returned, continued = asyncio.run(go())
    assert "[exit 0 · last pipeline's stage exits 1 | 0 ·" in masked
    assert "[exit 0 ·" in clean and "stage exits" not in clean
    assert "[exit 1 · last pipeline's stage exits 0 | 1 ·" in failed_last
    assert "[exit 4 ·" in returned
    assert "one two" in continued and "[exit 0 ·" in continued
    for out in (masked, clean, failed_last, returned, continued):
        assert "__AETHER_DONE" not in out and "__aether" not in out


def test_a_models_xtrace_traces_its_commands_not_the_terminal_bookkeeping(tmp_path):
    # configure-git, 30 Oct: after `set -eux` every result was our wrapper's trace, and head/tail truncation hid the
    # real output. The model's own command stays traced; exits and stage exits are unchanged; `set +x` ends it.
    async def go():
        t, _ = _terms(tmp_path)
        on = await t.use(input="set -x")
        traced = await t.use(input="echo visible-out; false | cat")
        failed = await t.use(input="echo x | { cat >/dev/null; false; }")
        off = await t.use(input="set +x; echo after")
        quiet = await t.use(input="echo plain")
        return on, traced, failed, off, quiet

    on, traced, failed, off, quiet = asyncio.run(go())
    assert "+ echo visible-out" in traced and "visible-out" in traced
    assert "[exit 0 · last pipeline's stage exits 1 | 0 ·" in traced
    assert "[exit 1 · last pipeline's stage exits 0 | 1 ·" in failed
    assert "+ echo plain" not in quiet and "plain" in quiet and "[exit 0 ·" in quiet
    for out in (on, traced, failed, off, quiet):
        assert "__aether" not in out and "__AETHER_DONE" not in out, out


def test_return_from_a_command_file_keeps_its_own_exit(tmp_path):
    # `return` leaves the sourced file before the capture line: the exit must be the return's, not a stale one
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="false | true")
        return await t.use(input="return 3")

    out = asyncio.run(go())
    assert "[exit 3 ·" in out and "stage exits" not in out


def test_an_unterminated_heredoc_body_is_run_unchanged(tmp_path):
    # the pipe-stage capture must not add text to the command: a heredoc missing its end marker writes only its own
    async def go():
        t, work = _terms(tmp_path)
        out = await t.use(input="cat > hd.txt <<EOF\nonly line")
        return out, (work / "hd.txt").read_text()

    out, written = asyncio.run(go())
    assert written == "only line\n"
    assert "__AETHER_DONE" not in out


def test_ctrl_c_sent_as_a_command_interrupts_the_busy_terminal(tmp_path):
    # P2 (10-22) sqlite-db-truncate: "\x03" sent in command mode was refused as "input not sent" again and again.
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="sleep 60", wait_s=0.5)
        stopped = await t.use(input="\x03", wait_s=10)
        after = await t.use(input="echo alive")
        return stopped, after

    stopped, after = asyncio.run(go())
    assert "input not sent" not in stopped and "interrupt" in stopped
    assert "alive" in after and "[exit 0" in after


def test_input_refused_by_a_busy_terminal_names_every_way_out(tmp_path):
    # P2 (10-22) sqlite-db-truncate state: an interactive python3 sat at ">>>" while "exit" and "print" were
    # refused 20+ times; nothing said that keys mode types into the running program.
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="sleep 60", wait_s=0.5)
        return await t.use(input="echo next")

    refused = asyncio.run(go())
    first = refused.splitlines()[0]
    assert "input not sent" in first and "interrupt=true" in first and 'name="main2"' in first
    assert 'mode="keys"' in first


def test_quiet_shell_prompt_waits_for_enter_before_executing_raw_keys(tmp_path):
    # At a quiet shell prompt, input may be buffered until Enter; silence alone is not a delivery receipt.
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="true")
        typed = await t.use(input="echo hi", mode="keys", wait_s=1)
        entered = await t.use(input="\n", mode="keys", wait_s=2)
        return typed, entered

    typed, entered = asyncio.run(go())
    assert "(no new output)" in typed
    assert "nothing was submitted" not in typed
    assert "no new output after these keys" in typed
    assert "hi" in entered


def test_quiet_foreground_reader_may_consume_keys_without_enter(tmp_path):
    # A quiet foreground stdin reader can consume raw bytes even when its output is empty.
    async def go():
        t, work = _terms(tmp_path)
        command = (
            "stty -icanon -echo 2>/dev/null || true; "
            "python3 -c 'import sys; from pathlib import Path; "
            "Path(\"captured-keys\").write_bytes(sys.stdin.buffer.read(3))'"
        )
        started = await t.use(input=command, wait_s=0.5)
        sent = await t.use(input="abc", mode="keys", wait_s=2)
        return started, sent, (work / "captured-keys").read_bytes()

    started, sent, captured = asyncio.run(go())
    assert "still running" in started
    assert captured == b"abc"
    assert "[exit 0" in sent
    assert "nothing was submitted" not in sent
    assert "no new output after these keys" in sent
    assert "Silence cannot show whether the input was accepted" in sent


class _StrictEnv(LocalEnv):
    """Decodes command output as strict UTF-8, as the Harbor environments do (LocalEnv replaces bad bytes)."""

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        self.commands.append(command)
        proc = await asyncio.create_subprocess_shell(
            command, cwd=cwd or str(self.root), stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.DEVNULL,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec or 30)
        from types import SimpleNamespace

        return SimpleNamespace(return_code=proc.returncode, stdout=out.decode(), stderr=err.decode())


@pytest.mark.parametrize("command", [
    "printf 'bin \\203\\377 tail\\n'",  # bytes that are not UTF-8 (path-tracing baseline: `strings` on a binary)
    # a large view cut into head and tail: where the cut falls depends on how many bytes the log holds before the
    # output, so the two byte offsets below make one of them cut inside a 2-byte character on any host
    "python3 -c \"print('é' * 6000)\"",
    "python3 -c \"print('x' + 'é' * 6000)\"",
])
def test_output_that_is_not_valid_utf8_is_shown_and_does_not_wedge_the_terminal(tmp_path, command):
    async def go():
        work = tmp_path / "work"
        work.mkdir()
        t = Terminals(_StrictEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl"))
        _OPEN.append(t)
        first = await t.use(input=command)
        second = await t.use(input="echo still-works")
        return first, second

    first, second = asyncio.run(go())
    assert "[exit 0" in first
    if command.startswith("printf"):
        assert "�" in first
    assert "still-works" in second and "[exit 0" in second


def test_keys_to_a_running_program_return_once_its_output_settles(tmp_path):
    # A program reading lines behind a running command (a VM console, a REPL): keys used to wait the full wait_s.
    async def go():
        t, _ = _terms(tmp_path)
        await t.use(input="while read l; do echo got:$l; done", wait_s=1)
        started = asyncio.get_running_loop().time()
        out = await t.use(input="hello\n", mode="keys", wait_s=60)
        return out, asyncio.get_running_loop().time() - started

    out, took = asyncio.run(go())
    assert "got:hello" in out
    assert took < 15, took  # known-bad (old source): ~60 s


def test_a_running_command_asking_for_input_returns_early_and_says_so(tmp_path):
    async def go():
        t, _ = _terms(tmp_path)
        started = asyncio.get_running_loop().time()
        out = await t.use(input='printf "Do you want to continue? [Y/n] "; read a; echo answered:$a', wait_s=60)
        took = asyncio.get_running_loop().time() - started
        reply = await t.use(input="y\n", mode="keys", wait_s=30)
        return out, took, reply

    out, took, reply = asyncio.run(go())
    assert took < 20, took  # known-bad (old source): ~60 s
    assert "looks like a prompt waiting for input" in out and "still running" in out
    assert "answered:y" in reply


def test_a_quiet_command_without_a_prompt_still_waits(tmp_path):
    async def go():
        t, _ = _terms(tmp_path)
        return await t.use(input="echo building; sleep 8; echo built", wait_s=30)

    out = asyncio.run(go())
    assert "built" in out and "[exit 0" in out and "looks like a prompt" not in out

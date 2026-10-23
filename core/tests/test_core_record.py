"""The run record (AETHER_CORE_RECORD): real terminal commands, real files, real re-runs. Each fact below is the
mechanism's whole point, and each test fails without it (no record: no fact, no hold, no restore)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import time

import pytest

from aether.core import receipt
from aether.core.harbor_agent import ConfigError, build_config
from aether.core.record import Record, is_check
from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv

BASE = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}


class Rig:
    def __init__(self, root: Path) -> None:
        self.work = root / "app"
        self.control = root / "ctl"
        self.work.mkdir()
        self.control.mkdir()
        self.env = LocalEnv(root)
        self.rows: list[tuple[str, dict]] = []
        self.terms = Terminals(self.env, str(self.work), lambda: 600.0, control_dir=str(self.control))
        self.record = Record(self.env, str(self.work), str(self.control), lambda: 600.0,
                             lambda event, **data: self.rows.append((event, data)))
        self.t = 0.0

    async def start(self) -> None:
        await receipt.mark(self.env, str(self.control))
        time.sleep(0.05)

    async def cmd(self, text: str) -> str:
        args = {"name": "main", "input": text}
        out = await self.terms.use(**args, wait_s=20)
        self.t += 10
        fact = await self.record.after_terminal(args, out, self.t)
        return out + ("\n" + fact if fact else "")


def run(coro_fn, tmp_path):
    async def go():
        rig = Rig(tmp_path)
        await rig.start()
        try:
            return await coro_fn(rig)
        finally:
            await rig.terms.close()

    return asyncio.run(go())


def test_is_check_runs_code_but_not_reads_or_installs():
    for c in ("python3 app.py", "cd /app && pytest -q", "FOO=1 ./run.sh", "timeout 60 node x.js", "diff a b",
              "gcc -o x x.c && ./x", "/usr/bin/python3 t.py | tail -5"):
        assert is_check(c), c
    for c in ("cat app.py", "ls -la", "pip install numpy", "python3 -m pip install x", "grep -n foo x.py",
              "python3 server.py &", "apt-get install -y gcc"):
        assert not is_check(c), c


def test_a_check_that_passed_and_now_fails_names_the_saved_passing_version(tmp_path):
    async def go(rig):
        app = rig.work / "app.py"
        app.write_text("print('ok')\n")
        assert "harness record" not in await rig.cmd("python3 app.py")
        app.write_text("raise SystemExit(3)\n")
        out = await rig.cmd("python3 app.py")
        assert "exited 0 at t=10s and exits 3 now" in out
        saved = next(line.split(": ", 1)[1] for line in out.splitlines() if line.strip().startswith("app.py:"))
        assert Path(saved).read_text() == "print('ok')\n"  # restoring is a plain cp of a real copy

    run(go, tmp_path)


def test_finish_reruns_in_a_fresh_shell_and_holds_when_terminal_state_carried_the_pass(tmp_path):
    async def go(rig):
        (rig.work / "check.py").write_text("import os, sys\nsys.exit(0 if os.environ.get('TOKEN') else 1)\n")
        await rig.cmd("export TOKEN=yes")
        assert "exit 0" in await rig.cmd("python3 check.py")  # passes only because of the terminal's variable
        hold, text, row = await rig.record.at_finish()
        assert hold and "fresh shell" in text and "it exits 1" in text
        assert row["reruns"][0]["orig_exit"] == 0 and row["reruns"][0]["exit"] == 1
        again = await rig.record.at_finish()
        assert again[0] is False  # the next finish is always accepted

    run(go, tmp_path)


def test_finish_is_accepted_when_the_rerun_agrees(tmp_path):
    async def go(rig):
        (rig.work / "ok.py").write_text("print('fine')\n")
        await rig.cmd("python3 ok.py")
        hold, text, row = await rig.record.at_finish()
        assert not hold and text == "" and row["reruns"][0]["exit"] == 0

    run(go, tmp_path)


def test_finish_holds_when_a_check_that_passed_fails_on_its_newest_run(tmp_path):
    async def go(rig):
        t = rig.work / "t.py"
        t.write_text("print('ok')\n")
        await rig.cmd("python3 t.py")
        t.write_text("raise SystemExit(2)\n")
        await rig.cmd("python3 t.py")
        hold, text, _ = await rig.record.at_finish()
        assert hold and "passed earlier; its newest run (t=20s) exited 2" in text

    run(go, tmp_path)


def test_a_one_off_command_that_failed_once_does_not_hold_the_finish(tmp_path):
    async def go(rig):
        (rig.work / "explore.py").write_text("raise SystemExit(1)\n")
        await rig.cmd("python3 explore.py")
        hold, _text, row = await rig.record.at_finish()
        assert not hold and row["failing"] == []

    run(go, tmp_path)


def test_a_rerun_that_changes_delivered_files_is_undone(tmp_path):
    async def go(rig):
        (rig.work / "gen.py").write_text("open('out.txt', 'a').write('x')\n")
        await rig.cmd("python3 gen.py")
        delivered = (rig.work / "out.txt").read_text()
        hold, _text, row = await rig.record.at_finish()
        assert row["reruns"][0]["restored"] == ["out.txt"]
        assert (rig.work / "out.txt").read_text() == delivered

    run(go, tmp_path)


def test_after_checkpoint_restates_exact_results_and_staleness(tmp_path):
    async def go(rig):
        app = rig.work / "a.py"
        app.write_text("print(1)\n")
        await rig.cmd("python3 a.py")
        app.write_text("print(2)\n")
        note = await rig.record.after_checkpoint()
        assert "exit 0: python3 a.py (files changed since: a.py)" in note

    run(go, tmp_path)


def test_a_command_finishing_on_a_later_call_is_attributed_to_it(tmp_path):
    async def go(rig):
        (rig.work / "slow.py").write_text("import time\ntime.sleep(2)\nraise SystemExit(4)\n")
        args = {"name": "main", "input": "python3 slow.py"}
        out = await rig.terms.use(**args, wait_s=0.3)
        assert "still running" in out
        await rig.record.after_terminal(args, out, 1)
        time.sleep(2.5)
        args2 = {"name": "main", "input": ""}
        out2 = await rig.terms.use(**args2, wait_s=5)
        await rig.record.after_terminal(args2, out2, 2)
        assert [(c.command, c.exit) for c in rig.record.checks] == [("python3 slow.py", 4)]

    run(go, tmp_path)


def test_config_record_and_neutral_hold_are_exclusive_and_default_off():
    base = build_config(environ=BASE)
    assert base.record is False and base.finish_hold == "off"
    assert build_config(environ={**BASE, "AETHER_CORE_RECORD": "on"}).record is True
    assert build_config(environ={**BASE, "AETHER_CORE_FINISH_HOLD": "neutral"}).finish_hold == "neutral"
    with pytest.raises(ConfigError):
        build_config(environ={**BASE, "AETHER_CORE_RECORD": "on", "AETHER_CORE_FINISH_HOLD": "neutral"})


def test_effort_none_sends_no_reasoning_effort_even_after_a_cut_turn():
    from aether.core.harbor_agent import build_provider
    from aether.core.loop import AFTER_CUT

    env = {"AETHER_FW_GLM_53_FLASH_ENDPOINT": "http://127.0.0.1:9/v1", "AETHER_FW_GLM_53_FLASH_KEY": "k",
           "AETHER_FW_GLM_53_FLASH_DEPLOYMENT": "flint", "AETHER_CORE_API": "openai",
           "AETHER_TB4_REASONING_EFFORT": "none"}
    provider = build_provider(environ=env)
    assert provider.params["reasoning_effort"] is None
    request = provider._request([{"role": "user", "content": "x"}], None, 16, AFTER_CUT)
    assert "reasoning_effort" not in str(request)


def _loop(tmp_path, events, **config):
    from aether.core.loop import CoreConfig, Trace, run_agent
    from tests.test_core_responses import ResponsesClient, provider

    work = tmp_path / "w"
    work.mkdir()
    client = ResponsesClient(events)
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Make t.py exit 0.", workdir=str(work), provider=provider(client, tmp_path),
        timeout_s=600, trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(tmp_path / "ctl"), **config),
    ))
    return result, client


def test_the_loop_holds_a_finish_on_a_failing_check_then_ends_on_the_next(tmp_path):
    from tests.test_core_responses import turn_events

    events = [
        turn_events(1, call=("terminal", {"input": "printf 'print(1)\\n' > t.py"}, "c1")),
        turn_events(2, call=("terminal", {"input": "python3 t.py"}, "c2")),
        turn_events(3, call=("terminal", {"input": "printf 'raise SystemExit(5)\\n' > t.py"}, "c3")),
        turn_events(4, call=("terminal", {"input": "python3 t.py"}, "c4")),
        turn_events(5, call=("finish", {"summary": "done"}, "c5")),
        turn_events(6, call=("finish", {"summary": "done anyway"}, "c6")),
    ]
    result, client = _loop(tmp_path, events, record=True)
    assert result.status == "finished"
    assert "exits 5 now" in str(client.requests[4]["input"])  # the regression, in the stream
    assert "its newest run" in str(client.requests[5]["input"])  # and at the held finish
    assert result.extras["record"]["failed"] == 1


def test_the_neutral_hold_holds_the_first_finish_without_facts(tmp_path):
    from tests.test_core_responses import turn_events

    events = [turn_events(1, call=("finish", {"summary": "a"}, "c1")), turn_events(2, call=("finish", {"summary": "b"}, "c2"))]
    result, client = _loop(tmp_path, events, finish_hold="neutral")
    after = str(client.requests[1]["input"])
    assert result.status == "finished" and "finish not yet accepted" in after and "harness record" not in after


class MeasureRig(Rig):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.record = Record(self.env, str(self.work), str(self.control), lambda: 600.0,
                             lambda event, **data: self.rows.append((event, data)), measure=True)


def run_measure(coro_fn, tmp_path):
    async def go():
        rig = MeasureRig(tmp_path)
        await rig.start()
        try:
            return await coro_fn(rig)
        finally:
            await rig.terms.close()

    return asyncio.run(go())


def test_measure_names_the_saved_version_that_scored_differently(tmp_path):
    """path-tracing shape: a scorer exits 0 both times; the better earlier version is not the one being delivered."""
    async def go(rig):
        (rig.work / "score.py").write_text("print('similarity', open('render.txt').read().strip())\n")
        render = rig.work / "render.txt"
        render.write_text("0.9143\n")
        await rig.cmd("python3 score.py")
        render.write_text("0.8657\n")
        await rig.cmd("python3 score.py")
        hold, text, row = await rig.record.at_finish()
        assert hold and row["measured"] >= 1
        assert "similarity 0.9143" in text and "similarity 0.8657" in text
        saved = text.split("render.txt saved at ", 1)[1].split(")", 1)[0]
        assert Path(saved).read_text() == "0.9143\n"  # the better version is really there to restore

    run_measure(go, tmp_path)


def test_measure_holds_when_the_fresh_rerun_prints_a_different_result(tmp_path):
    async def go(rig):
        (rig.work / "check.py").write_text("import os\nprint('score', 1.0 if os.environ.get('GOOD') else 0.2)\n")
        await rig.cmd("export GOOD=1")
        await rig.cmd("python3 check.py")
        hold, text, row = await rig.record.at_finish()
        assert hold and "exits 0 but prints: score 0.2" in text and "score 1.0" in text
        assert "passed again" not in text

    run_measure(go, tmp_path)


def test_measure_reports_files_changed_after_the_last_check(tmp_path):
    async def go(rig):
        (rig.work / "a.py").write_text("print('ok 1')\n")
        await rig.cmd("python3 a.py")
        (rig.work / "a.py").write_text("print('ok 2')\n")
        hold, text, _ = await rig.record.at_finish()
        assert hold and "Changed or created after your last check ran" in text and "a.py" in text

    run_measure(go, tmp_path)


def test_measure_accepts_a_finish_when_results_are_stable_control(tmp_path):
    """Passing control: same file, same result, nothing changed after: no hold, nothing said."""
    async def go(rig):
        (rig.work / "a.py").write_text("print('total 42')\n")
        await rig.cmd("python3 a.py")
        await rig.cmd("python3 a.py")
        hold, text, row = await rig.record.at_finish()
        assert not hold and text == "" and row["measured"] == 0

    run_measure(go, tmp_path)


def test_record_on_keeps_v2_behaviour_without_measure(tmp_path):
    async def go(rig):
        (rig.work / "score.py").write_text("print('similarity', open('r.txt').read().strip())\n")
        (rig.work / "r.txt").write_text("0.9\n")
        await rig.cmd("python3 score.py")
        (rig.work / "r.txt").write_text("0.5\n")
        await rig.cmd("python3 score.py")
        hold, _text, row = await rig.record.at_finish()
        assert not hold and "measured" in row and row["measured"] == 0

    run(go, tmp_path)


def test_config_measure_mode():
    c = build_config(environ={**BASE, "AETHER_CORE_RECORD": "measure"})
    assert c.record is True and c.record_measure is True
    assert build_config(environ={**BASE, "AETHER_CORE_RECORD": "on"}).record_measure is False


def test_measure_ignores_timing_and_pid_noise_control(tmp_path):
    """Only the wall-clock and process id differ between versions: not a result, no hold."""
    async def go(rig):
        app = rig.work / "srv.py"
        app.write_text("import os\nprint('Server started with PID', os.getpid())\nprint('took 0.31s')\n")
        await rig.cmd("python3 srv.py")
        app.write_text("import os\nprint('Server started with PID', os.getpid())\nprint('took 0.52s')\n# v2\n")
        await rig.cmd("python3 srv.py")
        hold, text, row = await rig.record.at_finish()
        assert row["measured"] == 0 and not hold, text

    run_measure(go, tmp_path)

"""A22 with A12: at finish, each unseen operation's phase is stated, and it is true at every kill point (real Linux).

Method: the shared every-exec harness (core_fault_sweep) cuts each exec of one Python cell or one terminal command at
every simple command, and drops each exec's reply. Right after the loss the model asks to finish, and the finish
observation lists the operation's phase. The sandbox then runs on, and the phase is checked against what happened:

- "never started": the effect never occurs, also after waiting (it was cancelled, so it cannot run later);
- "completed": the effect had occurred when the fact was given;
- "started and still running" / "sent and not yet taken": the effect occurs at most once (running: exactly once);
- no line: nothing is pending, so the result was shown or the operation was never handed over (no effect);
- "runner is gone" / "could not be read": never, while the sandbox is healthy.

Known-bad: without settling unconfirmed sends first, a lost Python submission is reported as unreadable, which the
contract rejects.
"""

import asyncio
import os
import time
from types import SimpleNamespace

import pytest

from aether.core import finish_facts, op_phases
from aether.core.repl import Repl
from aether.core.terminal import Terminals
from tests.core_fault_sweep import CutExecs, kill_points

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")

CELL = {
    "slow": "open('effects', 'a').write('x')\nimport time\ntime.sleep(1)\nprint('OPSM-' + 'RAN')",
    "fast": "open('effects', 'a').write('x')\nprint('OPSM-' + 'RAN')",
}
COMMAND = {"slow": "printf x >> effects; sleep 1; echo OPSM-RAN", "fast": "printf x >> effects; echo OPSM-RAN"}
SETTLE_S = 2.5


def effects(root) -> int:
    path = root / "effects"
    return len(path.read_text()) if path.exists() else 0


def session(terminals, repl=None) -> SimpleNamespace:
    return SimpleNamespace(terminals=terminals, repl=repl, mcp=None, browser=None)


def judge(lines: list[str], prefix: str, now: int, later: int, shown: bool) -> str | None:
    """None when the reported phase agrees with what happened, else why not."""
    mine = [line for line in lines if line.startswith(prefix)]
    if len(mine) > 1:
        return f"{len(mine)} lines for one operation"
    if not mine:
        return None if (shown and later == 1) or later == 0 else f"no fact, but the effect ran {later}x unseen"
    line = mine[0]
    if op_phases.NEVER in line:
        return None if later == 0 else f"said never started, effect ran {later}x"
    if "completed" in line:
        return None if now == 1 and later == 1 else f"said completed with effects {now}/{later}"
    if op_phases.RUNNING in line:
        return None if later == 1 else f"said running, effect ran {later}x"
    if op_phases.WAITING in line:
        return None if later <= 1 else f"said waiting, effect ran {later}x"
    return f"phase not proven: {line}"


def phase_of(lines: list[str], prefix: str) -> str:
    mine = [line for line in lines if line.startswith(prefix)]
    if not mine:
        return "none"
    line = mine[0]
    return next((name for name, text in (("never", op_phases.NEVER), ("running", op_phases.RUNNING),
                                         ("waiting", op_phases.WAITING), ("completed", "completed")) if text in line),
                "other")


async def python_case(root, target=None, cut=None, speed="slow") -> dict:
    env = CutExecs(root, target, cut)
    repl = Repl(env, str(root), lambda: 600.0, None, base=str(root / "repl"), track_operations=True)
    terminals = SimpleNamespace(_sessions={}, _preserve_existing=True, _env=env)
    assert await repl.start()
    try:
        assert "[python cell 1: ok" in await repl.run("pass", wait_s=10)
        env.armed, out = True, ""
        try:
            out = await repl.run(CELL[speed], wait_s=0.3)
        except ConnectionError:
            pass
        env.armed = False
        lines = await finish_facts.operations(session(terminals, repl))
        now = effects(root)
        time.sleep(SETTLE_S)
        return {"lines": lines, "now": now, "later": effects(root), "shown": "OPSM-RAN" in out,
                "counts": env.counts}
    finally:
        env.armed = False
        await repl.close()


async def terminal_case(root, target=None, cut=None, speed="slow") -> dict:
    env = CutExecs(root, target, cut)
    terminals = Terminals(env, str(root), lambda: 1000.0, control_dir=str(root / "ctl"), preserve_existing=True)
    try:
        assert "[exit 0" in await terminals.use(name="job", input="true", wait_s=5)
        env.armed, out = True, ""
        try:
            out = await terminals.use(name="job", input=COMMAND[speed], wait_s=0.3)
        except ConnectionError:
            pass
        env.armed = False
        lines = await finish_facts.operations(session(terminals))
        now = effects(root)
        time.sleep(SETTLE_S)
        return {"lines": lines, "now": now, "later": effects(root), "shown": "OPSM-RAN" in out,
                "counts": env.counts}
    finally:
        env.armed = False
        await terminals.close()


def sweep(tmp_path, case, prefix: str, speed: str):
    (tmp_path / "discover").mkdir()
    points = kill_points(asyncio.run(case(tmp_path / "discover", speed=speed))["counts"])
    failures, phases = [], {}
    for n, (target, cut) in enumerate(points):
        root = tmp_path / f"p{n}"
        root.mkdir()
        got = asyncio.run(case(root, target, cut, speed))
        phase = phase_of(got["lines"], prefix)
        phases[phase] = phases.get(phase, 0) + 1
        why = judge(got["lines"], prefix, got["now"], got["later"], got["shown"])
        if why:
            failures.append((target, cut, why))
    return points, failures, phases


@pytest.mark.parametrize("speed", ["slow", "fast"])
def test_python_phase_at_finish_is_true_at_every_kill_point(tmp_path, speed):
    points, failures, phases = sweep(tmp_path, python_case, "python:", speed)
    assert len(points) >= 8, points
    assert not failures, f"{len(failures)}/{len(points)} kill points: {failures}; phases {phases}"
    assert phases.get("never", 0) >= 1, phases  # the sweep reaches a submission lost before the REPL took it


@pytest.mark.parametrize("speed", ["slow", "fast"])
def test_terminal_phase_at_finish_is_true_at_every_kill_point(tmp_path, speed):
    points, failures, phases = sweep(tmp_path, terminal_case, "terminal job:", speed)
    assert len(points) >= 5, points
    assert not failures, f"{len(failures)}/{len(points)} kill points: {failures}; phases {phases}"


def test_known_bad_without_settling_lost_sends_the_python_sweep_fails(tmp_path, monkeypatch):
    async def no_settle(s):
        return []

    monkeypatch.setattr(op_phases, "settle", no_settle)
    _, failures, _ = sweep(tmp_path, python_case, "python:", "slow")
    assert failures, "reporting lost submissions without settling them passed the phase sweep"

"""Kill a Python cell submission at every point and check the operation contract (real Linux, real REPL server).

Same contract and method as test_core_operation_faults_e2e.py for terminals: the submit exec runs under a bash DEBUG
trap that exits before its K-th simple command, for every K, and the last case drops only the reply. A model that knows
only its intent keeps trying: it re-sends the cell, observes when told code was not run, and re-sends only when told
the cell never started. The cell makes its effect at once and finishes a second later.

At every kill point: the cell runs at most once, at least once within a few turns, and its output reaches the model
exactly once. This sweep covers a surviving controller; a restarted controller adopting the interpreter is covered
in ``test_core_repl_adopt_e2e.py``.
"""

import asyncio
import os
import shlex

import pytest

from aether.core.repl import Repl
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="native Linux qualification"
)

# Slow: still running when the controller recovers. Fast: finished before the model's re-send arrives.
INTENTS = {
    "slow": "open('effects', 'a').write('x')\nimport time\ntime.sleep(1)\nprint('OPSM-' + 'RAN')",
    "fast": "open('effects', 'a').write('x')\nprint('OPSM-' + 'RAN')",
}
TURNS = 8


class CutSubmit(LocalEnv):
    """Runs the first cell submission after ``arm()`` under a DEBUG trap; that exec's reply never arrives."""

    def __init__(self, root, cut: int | None):
        super().__init__(root)
        self.cut, self.armed, self.fired = cut, False, False
        self.counter = root / "simple-commands"

    async def exec(self, command, **kwargs):
        if self.armed and not self.fired and "/in/2.tmp" in command and " mv " in command:
            self.fired = True
            stop = f'[ "$n" -ge {self.cut} ] && exit 99; ' if self.cut is not None else ""
            trap = f"n=$((n+1)); echo $n > {shlex.quote(str(self.counter))}; {stop}"
            wrapped = f"bash -c {shlex.quote('n=0; trap ' + shlex.quote(trap) + ' DEBUG; eval \"$1\"')} _ {shlex.quote(command)}"
            await super().exec(wrapped, **kwargs)
            raise ConnectionError("the controller lost the submit exec")
        return await super().exec(command, **kwargs)


async def scenario(tmp_path, cut: int | None, track: bool = True, intent: str = INTENTS["slow"]) -> dict:
    env = CutSubmit(tmp_path, cut)
    repl = Repl(env, str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"), track_operations=track)
    shown: list[str] = []
    assert await repl.start()
    try:
        assert "[python cell 1: ok" in await repl.run("pass", wait_s=10)
        env.armed = True
        with pytest.raises(ConnectionError):
            await repl.run(intent, wait_s=0)
        send = True
        for _ in range(TURNS):
            out = await repl.run(intent if send else "", wait_s=2)
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = "never started" in out
        effects = (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
        return {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown), "shown": shown}
    finally:
        await repl.close()


def count_steps(tmp_path) -> int:
    asyncio.run(scenario(tmp_path / "count", None))
    return int((tmp_path / "count" / "simple-commands").read_text())


def sweep(tmp_path, track: bool = True, intent: str = INTENTS["slow"]) -> tuple[int, list]:
    (tmp_path / "count").mkdir()
    steps = count_steps(tmp_path)
    results = []
    for cut in range(1, steps + 2):  # steps + 1: every step ran, only the reply was lost
        case = tmp_path / f"cut{cut}"
        case.mkdir()
        got = asyncio.run(scenario(case, cut, track, intent))
        results.append((cut, got["effects"], got["delivered"], got["shown"][-1][-160:]))
    return steps, results


@pytest.mark.parametrize("speed", ["slow", "fast"])
def test_every_submit_kill_point_runs_the_cell_once_and_delivers_it_once(tmp_path, speed):
    steps, results = sweep(tmp_path, intent=INTENTS[speed])
    assert steps >= 3
    failures = [r for r in results if (r[1], r[2]) != (1, 1)]
    assert not failures, f"{len(failures)}/{steps + 1} kill points broke the contract: {failures}"


@pytest.mark.parametrize("speed", ["slow", "fast"])
def test_without_tracking_the_sweep_finds_stranded_or_doubled_cells(tmp_path, speed):
    """Known-bad: the untracked REPL (the stock protocol) breaks the contract at some kill point."""
    steps, results = sweep(tmp_path, track=False, intent=INTENTS[speed])
    print("OPSM-REPL-STOCK", speed, steps + 1, [(r[0], r[1], r[2]) for r in results if (r[1], r[2]) != (1, 1)])
    assert [r for r in results if (r[1], r[2]) != (1, 1)], "the stock protocol passed every kill point"


# ----- every exec of the operation, on the shared sweep harness (A15) --------------------------------------------------
from tests.core_fault_sweep import CutExecs, kill_points  # noqa: E402


async def scenario_all(tmp_path, target=None, cut=None, track=True, intent=INTENTS["slow"]) -> dict:
    """Like ``scenario``, but any exec after arming can be cut (submit, polls, reads), at every simple command; a
    lost reply leaves the model knowing only its intent, so it re-sends the same cell."""
    env = CutExecs(tmp_path, target, cut)
    repl = Repl(env, str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"), track_operations=track)
    shown: list[str] = []
    assert await repl.start()
    try:
        assert "[python cell 1: ok" in await repl.run("pass", wait_s=10)
        env.armed = True
        send = True
        for _ in range(TURNS + 1):
            try:
                out = await repl.run(intent if send else "", wait_s=2)
            except ConnectionError:
                send = True
                continue
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = "never started" in out
        env.armed = False  # the turns are over: cleanup is not part of the contract under test
        effects = (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
        return {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown),
                "counts": env.counts, "last": shown[-1][-160:] if shown else ""}
    finally:
        env.armed = False
        await repl.close()


def sweep_all(tmp_path, track=True):
    (tmp_path / "discover").mkdir()
    found = asyncio.run(scenario_all(tmp_path / "discover", track=track))
    points = kill_points(found["counts"])
    failures = []
    for n, (target, cut) in enumerate(points):
        case = tmp_path / f"p{n}"
        case.mkdir()
        got = asyncio.run(scenario_all(case, target, cut, track))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, cut, got["effects"], got["delivered"], got["last"]))
    return points, failures


def test_every_exec_kill_point_of_a_cell_runs_it_once_and_delivers_it_once(tmp_path):
    points, failures = sweep_all(tmp_path)
    assert len(points) >= 8, points
    assert not failures, f"{len(failures)}/{len(points)} kill points broke the contract: {failures}"


def test_known_bad_untracked_cells_break_the_every_exec_sweep(tmp_path):
    _, failures = sweep_all(tmp_path, track=False)
    assert failures, "the untracked REPL passed every exec kill point"

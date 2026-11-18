"""Kill a terminal command dispatch at every point and check the operation contract (real Linux shells).

The dispatch of one command is a single container exec of many shell steps (claim, stage, offer to the shell, delivery
record, receipt wait). A controller can lose that exec anywhere: the exec dies part-way, or it completes and the reply
is lost. This suite does not hand-pick crash points. It runs the dispatch exec under a bash DEBUG trap that exits
before its K-th simple command, for every K from the first command to past the last (the lost-reply case), so every
interleaving point inside the exec is a kill point, whatever the script's structure is.

After each cut a simulated model, which only knows its intent and the text it is shown, keeps trying to get that
intent done: it re-sends the command, observes when told input was not sent, and re-sends only when told nothing ran.
Two controller fates are covered: the controller survives the failed exec (same object), or it dies with it and a new
controller takes over the sandbox.

The contract at every kill point:
- at most one execution (the effect file never holds two marks), and
- liveness: the intent is executed exactly once within a few turns, never stranded behind an unknown state, and
- single delivery: the command's output reaches the model exactly once.
"""

import asyncio
import os
import shlex

import pytest

from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="native Linux shell qualification"
)
pytestmark = [pytestmark, pytest.mark.sweep]  # exhaustive kill-point sweep: tens of minutes

# The effect lands at once; the receipt only a second later. A command that is still running when the controller
# recovers is the case the start token exists for: a fast command has its receipt before any recovery looks.
INTENT = "printf x >> effects; sleep 1; echo OPSM-RAN"
TURNS = 8


class CutDispatch(LocalEnv):
    """Runs the first command dispatch after ``arm()`` under a DEBUG trap; that exec's reply never arrives."""

    def __init__(self, root, cut: int | None):
        super().__init__(root)
        self.cut, self.armed, self.fired = cut, False, False
        self.counter = root / "simple-commands"

    async def exec(self, command, **kwargs):
        if self.armed and not self.fired and "mkdir" in command and "/claim_" in command:
            self.fired = True
            stop = f'[ "$n" -ge {self.cut} ] && exit 99; ' if self.cut is not None else ""
            trap = f"n=$((n+1)); echo $n > {shlex.quote(str(self.counter))}; {stop}"
            wrapped = f"bash -c {shlex.quote('n=0; trap ' + shlex.quote(trap) + ' DEBUG; eval \"$1\"')} _ {shlex.quote(command)}"
            await super().exec(wrapped, **kwargs)
            raise ConnectionError("the controller lost the dispatch exec")
        return await super().exec(command, **kwargs)


def make(tmp_path, env):
    return Terminals(env, str(tmp_path), lambda: 1000.0, control_dir=str(tmp_path / "ctl"), preserve_existing=True)


async def scenario(tmp_path, cut: int | None, restart: bool) -> dict:
    env = CutDispatch(tmp_path, cut)
    first = make(tmp_path, env)
    shown: list[str] = []
    controllers = [first]
    try:
        assert "[exit 0" in await first.use(name="job", input="true", wait_s=5)
        env.armed = True
        with pytest.raises(ConnectionError):
            await first.use(name="job", input=INTENT, wait_s=0)
        if restart:
            first._sessions.clear()  # the controller died with its exec; the shell lives on in the sandbox
            controllers.append(make(tmp_path, LocalEnv(tmp_path)))
        ctrl = controllers[-1]
        send = True
        for _ in range(TURNS):
            out = await ctrl.use(name="job", input=INTENT if send else "", wait_s=2)
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = "never started" in out
        effects = (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
        return {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown), "shown": shown}
    finally:
        for c in controllers:
            await c.close()


def count_steps(tmp_path) -> int:
    asyncio.run(scenario(tmp_path / "count", None, restart=False))
    return int((tmp_path / "count" / "simple-commands").read_text())


@pytest.mark.parametrize("restart", [False, True], ids=["same-controller", "new-controller"])
def test_every_dispatch_kill_point_executes_the_intent_once_and_delivers_it_once(tmp_path, restart):
    (tmp_path / "count").mkdir()
    steps = count_steps(tmp_path)
    assert steps >= 5
    failures = []
    for cut in range(1, steps + 2):  # steps + 1: every step ran, only the reply was lost
        case = tmp_path / f"cut{cut}"
        case.mkdir()
        got = asyncio.run(scenario(case, cut, restart))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((cut, got["effects"], got["delivered"], got["shown"][-1][-160:]))
    assert not failures, f"{len(failures)}/{steps + 1} kill points broke the contract: {failures}"


def test_without_the_start_token_the_sweep_finds_a_second_execution(tmp_path, monkeypatch):
    """Falsifier: with the shell running the line unconditionally, a revoked command still runs, so the model's
    re-send after "never started" executes the intent twice at some kill point."""
    from aether.core import operations

    monkeypatch.setattr(operations, "start_gate", lambda root, seq: "true")
    (tmp_path / "count").mkdir()
    steps = count_steps(tmp_path)
    doubled = []
    for cut in range(1, steps + 2):
        case = tmp_path / f"cut{cut}"
        case.mkdir()
        got = asyncio.run(scenario(case, cut, restart=True))
        if got["effects"] > 1:
            doubled.append(cut)
    assert doubled, "no kill point produced a second execution without the start token"

"""T2 (audit, 15 Nov): an exec that took effect but whose reply says it failed, at every exec of an operation.

The lost-reply sweeps cut an exec and raise, so the controller knows it does not know. Here the target exec runs to
completion and its reply arrives altered: failure status, no output (``CutExecs(misreport=True)``). A protocol that
reads that status as proof that nothing happened (for example "mv is atomic: a failed rename published nothing")
tells the model the operation failed while it ran, and the model's retry runs it twice.

Drivers are the most naive models: MCP resends the identical call until it sees the tool's result (the existing MCP
driver); the REPL driver resends the identical cell unless Core says that cell is still running or that its effect is not
known (a truthful 'unknown' is the model's to resolve; a stated failure is not).
Contract: the effect happens exactly once and its result is shown exactly once.
"""

import asyncio
import functools
import os
import sys

import pytest

from aether.core.env import ProcessCleanupError
from aether.core.mcp import Mcp
from aether.core.repl import Repl
from aether.core.terminal import Terminals
from tests import test_core_browser_operation_faults_e2e as browser_sweep
from tests import test_core_mcp_operation_faults_e2e as mcp_sweep
from tests.core_fakes import LocalEnv
from tests.core_fault_sweep import CutExecs, misreport_points

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
HOLD = ("still running", "may have", "unknown", "not known")
CELL = "open('effects', 'a').write('x')\nimport time\ntime.sleep(1)\nprint('OPSM-' + 'RAN')"


def test_mcp_every_misreported_exec_runs_the_tool_once_and_shows_it_once(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_sweep, "CutExecs", functools.partial(CutExecs, misreport=True))
    (tmp_path / "discover").mkdir()
    found = asyncio.run(mcp_sweep.scenario(tmp_path / "discover"))
    points = misreport_points(found["counts"])
    assert len(points) >= 3
    failures = []
    for n, (target, _) in enumerate(points):
        case = tmp_path / f"p{n}"
        case.mkdir()
        got = asyncio.run(mcp_sweep.scenario(case, target, None))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, got["effects"], got["delivered"], [s[-160:] for s in got["shown"]]))
    print("T2-MCP", len(points), failures)
    assert not failures, f"{len(failures)}/{len(points)} misreported execs broke the contract: {failures}"


async def repl_case(tmp_path, target=None):
    env = CutExecs(tmp_path, target, None, misreport=True)
    repl = Repl(env, str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"), track_operations=True)
    shown: list[str] = []
    assert await repl.start()
    try:
        assert "[python cell 1: ok" in await repl.run("pass", wait_s=10)
        env.armed = True
        send = True
        for _ in range(8):
            try:
                out = await repl.run(CELL if send else "", wait_s=2)
            except Exception as exc:  # the loop shows a tool's exception to the model as this text (loop_calls._invoke)
                out = f"error: {type(exc).__name__}: {exc}"
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            # resend unless Core says the cell is running or that its effect is not known
            send = not any(k in out for k in HOLD)
        env.armed = False
        effects = (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
        return {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown),
                "counts": env.counts, "shown": [o[-160:] for o in shown]}
    finally:
        env.armed = False
        await repl.close()


def test_repl_every_misreported_exec_runs_the_cell_once_and_shows_it_once(tmp_path):
    (tmp_path / "discover").mkdir()
    found = asyncio.run(repl_case(tmp_path / "discover"))
    assert (found["effects"], found["delivered"]) == (1, 1), found
    points = misreport_points(found["counts"])
    failures = []
    for n, (target, _) in enumerate(points):
        case = tmp_path / f"p{n}"
        case.mkdir()
        got = asyncio.run(repl_case(case, target))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, got["effects"], got["delivered"], got["shown"]))
    print("T2-REPL", len(points), failures)
    assert not failures, f"{len(failures)}/{len(points)} misreported execs broke the contract: {failures}"


TERMINAL_INTENT = "printf x >> effects; sleep 1; echo OPSM-RAN"


async def terminal_case(tmp_path, target=None):
    env = CutExecs(tmp_path, target, None, misreport=True)
    ctrl = Terminals(env, str(tmp_path), lambda: 1000.0, control_dir=str(tmp_path / "ctl"), preserve_existing=True)
    shown: list[str] = []
    try:
        assert "[exit 0" in await ctrl.use(name="job", input="true", wait_s=5)
        env.armed = True
        send = True
        for _ in range(8):
            try:
                out = await ctrl.use(name="job", input=TERMINAL_INTENT if send else "", wait_s=2)
            except Exception as exc:  # as the loop shows it
                out = f"error: {type(exc).__name__}: {exc}"
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = not any(k in out for k in HOLD)
        env.armed = False
        effects = (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
        return {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown),
                "counts": env.counts, "shown": [o[-160:] for o in shown]}
    finally:
        env.armed = False
        await ctrl.close()


def test_terminal_every_misreported_exec_runs_the_command_once_and_shows_it_once(tmp_path):
    (tmp_path / "discover").mkdir()
    found = asyncio.run(terminal_case(tmp_path / "discover"))
    assert (found["effects"], found["delivered"]) == (1, 1), found
    points = misreport_points(found["counts"])
    failures = []
    for n, (target, _) in enumerate(points):
        case = tmp_path / f"p{n}"
        case.mkdir()
        got = asyncio.run(terminal_case(case, target))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, got["effects"], got["delivered"], got["shown"]))
    print("T2-TERMINAL", len(points), failures)
    assert not failures, f"{len(failures)}/{len(points)} misreported execs broke the contract: {failures}"


class MisreportHost(browser_sweep.CutHost):
    """The browser's host calls: call ``target`` runs to completion and its reply says failure with no output."""

    async def __call__(self, argv, timeout_s):
        if not self.armed or self.fired or self.target is None or self.index != self.target:
            return await super().__call__(argv, timeout_s)
        self.index += 1
        self.fired = True
        await browser_sweep.local_host(argv, timeout_s)
        return 1, "", ""


def test_browser_every_misreported_host_call_runs_the_code_once_and_shows_it_once(tmp_path, monkeypatch):
    monkeypatch.setattr(browser_sweep, "CutHost", MisreportHost)
    (tmp_path / "discover").mkdir()
    found = asyncio.run(browser_sweep.scenario(tmp_path / "discover"))
    assert (found["effects"], found["delivered"]) == (1, 1), found["shown"]
    points = misreport_points(found["counts"])
    failures = []
    for n, (target, _) in enumerate(points):
        case = tmp_path / f"p{n}"
        case.mkdir()
        try:
            got = asyncio.run(browser_sweep.scenario(case, target, None))
        except Exception as exc:  # the sweep's driver does not render exceptions: record, do not hide
            failures.append((target, "raised", f"{type(exc).__name__}: {exc}"[:200]))
            continue
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, got["effects"], got["delivered"], [s[-160:] for s in got["shown"]]))
    print("T2-BROWSER", len(points), failures)
    assert not failures, f"{len(failures)}/{len(points)} misreported host calls broke the contract: {failures}"


# Composite (audit T1 x T2): a hostile payload written by a command whose execs are misreported one at a time. Both
# contracts at once: the effect once, its result shown once, and the bytes the shell received equal the emitted text.
HOSTILE = "hé \U0001f680\t\\x41 $HOME `id` 'q' \"d\"\r\n\x1b[0m EOF"


async def composite_case(tmp_path, target=None):
    env = CutExecs(tmp_path, target, None, misreport=True)
    ctrl = Terminals(env, str(tmp_path), lambda: 1000.0, control_dir=str(tmp_path / "ctl"), preserve_existing=True)
    intent = f"printf x >> effects; cat >> got <<'T1EOF'\n{HOSTILE}\nT1EOF\nsleep 1; echo OPSM-RAN"
    shown: list[str] = []
    try:
        assert "[exit 0" in await ctrl.use(name="job", input="true", wait_s=5)
        env.armed = True
        send = True
        for _ in range(8):
            try:
                out = await ctrl.use(name="job", input=intent if send else "", wait_s=3)
            except Exception as exc:
                out = f"error: {type(exc).__name__}: {exc}"
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = not any(k in out for k in HOLD)
        env.armed = False
        effects = (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
        got = (tmp_path / "got").read_bytes() if (tmp_path / "got").exists() else b""
        return {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown),
                "bytes_exact": got == (HOSTILE + "\n").encode(), "counts": env.counts, "shown": [o[-160:] for o in shown]}
    finally:
        env.armed = False
        await ctrl.close()


def test_composite_hostile_payload_under_every_misreported_exec(tmp_path):
    (tmp_path / "discover").mkdir()
    found = asyncio.run(composite_case(tmp_path / "discover"))
    assert (found["effects"], found["delivered"], found["bytes_exact"]) == (1, 1, True), found
    failures = []
    for n, (target, _) in enumerate(misreport_points(found["counts"])):
        case = tmp_path / f"p{n}"
        case.mkdir()
        got = asyncio.run(composite_case(case, target))
        if (got["effects"], got["delivered"], got["bytes_exact"]) != (1, 1, True):
            failures.append((target, got["effects"], got["delivered"], got["bytes_exact"], got["shown"]))
    print("T1xT2-TERMINAL", len(found["counts"]), failures)
    assert not failures, failures


async def composite_mcp_case(tmp_path, target=None):
    env = CutExecs(tmp_path, target, None, misreport=True)
    spec = {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable,
            "args": [mcp_sweep.FIXTURE, "stdio"]}
    mcp = Mcp(env, str(tmp_path / "control"), [spec])
    got = tmp_path / "got"
    intent = {"server": "fx", "action": "call", "tool": "record", "arguments": {"path": str(got), "text": HOSTILE},
              "timeout_s": 30}
    shown: list[str] = []
    try:
        assert (await mcp.use({"server": "fx", "action": "list"}, 120)).startswith("5 tools:")
        env.armed = True
        for _ in range(8):  # the naive model: the identical call again until it sees the result
            try:
                out = await mcp.use(intent, 120)
            except Exception as exc:
                out = f"error: {type(exc).__name__}: {exc}"
            shown.append(out)
            if "recorded" in out:
                break
        env.armed = False
        data = got.read_bytes() if got.exists() else b""
        want = HOSTILE.encode()
        return {"effects": data.count(want), "delivered": sum(o.count("recorded") for o in shown),
                "bytes_exact": data == want, "counts": env.counts, "shown": [o[-160:] for o in shown]}
    finally:
        env.armed = False
        await mcp.close()


async def composite_repl_case(tmp_path, target=None):
    env = CutExecs(tmp_path, target, None, misreport=True)
    repl = Repl(env, str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"), track_operations=True)
    got = tmp_path / "got"
    cell = (f"open({str(got)!r}, 'a', encoding='utf-8', newline='').write({HOSTILE!r})\n"
            "import time\ntime.sleep(1)\nprint('OPSM-' + 'RAN')")
    shown: list[str] = []
    assert await repl.start()
    try:
        assert "[python cell 1: ok" in await repl.run("pass", wait_s=10)
        env.armed = True
        send = True
        for _ in range(8):
            try:
                out = await repl.run(cell if send else "", wait_s=2)
            except Exception as exc:
                out = f"error: {type(exc).__name__}: {exc}"
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = not any(k in out for k in HOLD)
        env.armed = False
        data = got.read_bytes() if got.exists() else b""
        want = HOSTILE.encode()
        return {"effects": data.count(want), "delivered": sum(o.count("OPSM-RAN") for o in shown),
                "bytes_exact": data == want, "counts": env.counts, "shown": [o[-160:] for o in shown]}
    finally:
        env.armed = False
        await repl.close()


@pytest.mark.parametrize("owner", ["mcp", "repl"])
def test_composite_mcp_and_repl_under_every_misreported_exec(tmp_path, owner):
    case_fn = {"mcp": composite_mcp_case, "repl": composite_repl_case}[owner]
    (tmp_path / "discover").mkdir()
    found = asyncio.run(case_fn(tmp_path / "discover"))
    assert (found["effects"], found["delivered"], found["bytes_exact"]) == (1, 1, True), found
    failures = []
    for n, (target, _) in enumerate(misreport_points(found["counts"])):
        case = tmp_path / f"p{n}"
        case.mkdir()
        got = asyncio.run(case_fn(case, target))
        if (got["effects"], got["delivered"], got["bytes_exact"]) != (1, 1, True):
            failures.append((target, got["effects"], got["delivered"], got["bytes_exact"], got["shown"]))
    print(f"T1xT2-{owner.upper()}", len(found["counts"]), failures)
    assert not failures, failures


# Adoption (A24 remaining): the earlier controller dies with its operation running; every exec of the restarted
# controller (adoption reads, liveness checks, observation, delivery records) is misreported in turn.
async def adopt_terminal_case(tmp_path, target=None):
    first = Terminals(LocalEnv(tmp_path), str(tmp_path), lambda: 1000.0, control_dir=str(tmp_path / "ctl"),
                      preserve_existing=True)
    assert "[exit 0" in await first.use(name="job", input="true", wait_s=5)
    await first.use(name="job", input=TERMINAL_INTENT, wait_s=0)
    first._sessions.clear()  # the controller died; the shell lives on in the sandbox
    env = CutExecs(tmp_path, target, None, misreport=True)
    ctrl = Terminals(env, str(tmp_path), lambda: 1000.0, control_dir=str(tmp_path / "ctl"), preserve_existing=True)
    shown: list[str] = []
    try:
        env.armed = True
        send = True
        for _ in range(8):
            try:
                out = await ctrl.use(name="job", input=TERMINAL_INTENT if send else "", wait_s=2)
            except Exception as exc:
                out = f"error: {type(exc).__name__}: {exc}"
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = not any(k in out for k in HOLD + ("adopted", "unverified", "could not be read"))
        env.armed = False
        effects = (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
        result = {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown),
                  "counts": env.counts, "shown": [o[-200:] for o in shown]}
    finally:
        env.armed = False
    result["cleanup"] = await closed(ctrl)
    return result


async def closed(owner) -> str:
    """Close an owner and return its cleanup verdict: a truthful 'unverified' is recorded, not a contract failure."""
    try:
        await owner.close()
        return "verified"
    except ProcessCleanupError as exc:
        return f"unverified: {str(exc)[:120]}"


async def adopt_repl_case(tmp_path, target=None):
    first = Repl(LocalEnv(tmp_path), str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"),
                 track_operations=True)
    assert await first.start()
    assert "[python cell 1: ok" in await first.run("pass", wait_s=10)
    assert "still running" in await first.run(CELL, wait_s=0)
    env = CutExecs(tmp_path, target, None, misreport=True)
    ctrl = Repl(env, str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"), track_operations=True)
    shown: list[str] = []
    try:
        env.armed = True
        await ctrl.start()
        send = True
        for _ in range(8):
            try:
                out = await ctrl.run(CELL if send else "", wait_s=2)
            except Exception as exc:
                out = f"error: {type(exc).__name__}: {exc}"
            shown.append(out)
            if "OPSM-RAN" in out:
                break
            send = not any(k in out for k in HOLD + ("adopted", "unverified", "could not be read"))
        env.armed = False
        effects = (tmp_path / "effects").read_text() if (tmp_path / "effects").exists() else ""
        result = {"effects": len(effects), "delivered": sum(o.count("OPSM-RAN") for o in shown),
                  "counts": env.counts, "shown": [o[-200:] for o in shown]}
    finally:
        env.armed = False
    result["cleanup"] = await closed(ctrl)  # the first controller is dead: the adopter owns the server now
    return result


@pytest.mark.parametrize("owner", ["terminal", "repl"])
def test_a_restarted_controller_with_every_exec_misreported_runs_the_operation_once(tmp_path, owner):
    case_fn = {"terminal": adopt_terminal_case, "repl": adopt_repl_case}[owner]
    (tmp_path / "discover").mkdir()
    found = asyncio.run(case_fn(tmp_path / "discover"))
    assert (found["effects"], found["delivered"]) == (1, 1), found
    failures = []
    for n, (target, _) in enumerate(misreport_points(found["counts"])):
        case = tmp_path / f"p{n}"
        case.mkdir()
        got = asyncio.run(case_fn(case, target))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, got["effects"], got["delivered"], got["shown"]))
    print(f"T2-ADOPT-{owner.upper()}", len(found["counts"]), failures)
    print(f"T2-ADOPT-{owner.upper()}-CLEANUP", found["cleanup"])
    assert not failures, failures

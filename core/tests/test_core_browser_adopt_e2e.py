"""A11/A13 for the browser: a restarted controller adopts the task's sidecar and its runs (real Linux processes).

As in test_core_browser_operation_faults_e2e.py, ``docker exec``/``docker cp`` run as local processes, so the run
protocol (code file, detached runner, start token, receipt, delivery record) is real; ``docker ps`` answers with the
sidecar the first controller started for the task container. The first controller dies (it is dropped), and a new
one, continuing the conversation, makes the next browser call:

- a run still going when the first controller died is attached to, not run again, and shown once;
- a run whose result the continued conversation already holds is not shown again;
- a run marked delivered whose tool result never reached the conversation (lost retained acknowledgement) is shown;
- a run whose launch was lost before its runner took the token is cancelled, and never runs.

Known-bad: without adoption, the new controller starts a fresh sidecar and an identical call runs the code twice.
"""

import asyncio
import os
import time

import pytest

from aether.core import browser, browser_ops
from tests.test_core_browser_operation_faults_e2e import local_host

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
CID = "c" * 64
NAME = "aether-browser-first"


def make_host(running: dict[str, str]):
    async def host(argv, timeout_s):
        if argv[:2] == ["docker", "ps"]:
            cid = argv[argv.index("--filter") + 1].rsplit("=", 1)[1]
            return 0, (running[cid] + "\n") if cid in running else "", ""
        if argv[:2] == ["docker", "run"]:
            return 0, "", ""
        return await local_host(argv, timeout_s)
    return host


def controller(tmp_path, host, conversation: set[str], tag: str, adopt: bool = True, ops: str = "ops"):
    async def factory(env):
        return CID

    session = browser.BrowserSession(factory, None, host=host)
    session.adopt, session.conversation, session.delivery_tag = adopt, conversation, (lambda: tag)
    return session, str(tmp_path / ops)


def code(tmp_path, delay: float) -> str:
    return (f"open({str(tmp_path / 'effects')!r}, 'a').write('x')\nimport time\ntime.sleep({delay})\n"
            "print('effect-' + 'done')")


async def first_controller(tmp_path, host, conversation, delay, wait_s):
    session, ops = controller(tmp_path, host, conversation, "tag-first")
    car = browser.Sidecar(CID, host, NAME)
    car.runs.ops_dir, car.runs.conversation, car.runs.delivery_tag = ops, conversation, session.delivery_tag
    session.sidecar = car
    return await session.use({"code": code(tmp_path, delay), "wait_s": wait_s}, 300.0)


async def second_controller(tmp_path, host, conversation, args, adopt=True, ops="ops"):
    session, ops_dir = controller(tmp_path, host, conversation, "tag-second", adopt, ops)
    original = browser.Sidecar.__init__

    def init(self, cid, host_run, name=None):
        original(self, cid, host_run, name)
        self.runs.ops_dir = ops_dir  # the sidecar's fixed records directory, here under the test root

    browser.Sidecar.__init__ = init
    try:
        out = await session.use(args, 300.0)
    finally:
        browser.Sidecar.__init__ = original
    return out


def effects(tmp_path) -> int:
    path = tmp_path / "effects"
    return len(path.read_text()) if path.exists() else 0


def test_a_run_still_going_at_restart_is_attached_to_and_shown_once(tmp_path):
    host = make_host({CID: NAME})
    first = asyncio.run(first_controller(tmp_path, host, set(), delay=2, wait_s=0.5))
    assert "still running" in first
    second = asyncio.run(second_controller(tmp_path, host, set(), {"code": code(tmp_path, 2), "wait_s": 10}))
    assert "adopted" in second and "run #1" in second
    assert second.count("effect-done") == 1
    time.sleep(0.5)
    assert effects(tmp_path) == 1


def test_a_result_the_conversation_holds_is_not_shown_again(tmp_path):
    host = make_host({CID: NAME})
    conversation: set[str] = set()
    first = asyncio.run(first_controller(tmp_path, host, conversation, delay=0, wait_s=10))
    assert "effect-done" in first and (tmp_path / "ops" / "delivered_1").read_text() == "tag-first"
    second = asyncio.run(second_controller(tmp_path, host, {"tag-first"}, {"code": "print('other')", "wait_s": 10}))
    assert "adopted" in second and "effect-done" not in second and "other" in second


def test_lost_retained_acknowledgement_shows_the_result_again(tmp_path):
    host = make_host({CID: NAME})
    first = asyncio.run(first_controller(tmp_path, host, set(), delay=0, wait_s=10))
    assert "effect-done" in first  # marked delivered, but the tool result never reached the continued conversation
    second = asyncio.run(second_controller(tmp_path, host, set(), {"code": "print('other')", "wait_s": 10}))
    assert second.count("effect-done") == 1 and "other" in second
    assert effects(tmp_path) == 1


def test_a_launch_lost_before_the_runner_took_it_is_cancelled_and_never_runs(tmp_path):
    host = make_host({CID: NAME})
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "code_1.py").write_text(code(tmp_path, 0))  # copied in; the detached launch never happened
    second = asyncio.run(second_controller(tmp_path, host, set(), {"code": "print('other')", "wait_s": 10}))
    assert "run #1 never started" in second and "other" in second
    launch = ["docker", "exec", "-d", NAME, "sh", "-c", browser_ops._LAUNCH, "core-browser-op", str(ops), "1", "30",
              "", "100", "k"]
    asyncio.run(local_host(launch, 10))  # the lost launch arrives late: the revoked token stops it
    time.sleep(1.0)
    assert effects(tmp_path) == 0


def test_known_bad_without_adoption_an_identical_call_runs_twice(tmp_path):
    host = make_host({CID: NAME})
    asyncio.run(first_controller(tmp_path, host, set(), delay=1, wait_s=0.3))
    second = asyncio.run(second_controller(tmp_path, host, set(), {"code": code(tmp_path, 1), "wait_s": 10},
                                           adopt=False, ops="ops-fresh-sidecar"))
    assert "effect-done" in second
    time.sleep(1.5)
    assert effects(tmp_path) == 2

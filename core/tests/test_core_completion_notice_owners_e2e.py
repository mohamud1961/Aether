"""A7: one promotion rule across owners (real Core loop, real REPL server, scripted model).

A Python cell outlives its wait and is promoted ("still running"). The model then works in the terminal. When the cell
finishes, the next tool result carries one line saying so, from the REPL's own completion record, and the cell's
output is still shown in full at the next python call (the notice consumes nothing). Known-bad: with notices off the
terminal result says nothing about the cell.
"""

import asyncio
from pathlib import Path
import shutil

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

pytestmark = pytest.mark.skipif(not shutil.which("python3"), reason="needs python3 for the REPL")


def scenario(tmp_path, notices: bool):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([
        call("python", {"code": "import time\ntime.sleep(1.5)\nprint('cell-' + 'done')", "wait_s": 0.3}, "p1"),
        call("terminal", {"input": "sleep 2.5; echo shell-done", "wait_s": 10}, "t1"),
        call("python", {"code": "", "wait_s": 5}, "p2"),
        call("finish", {"summary": "done"}, "f"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Run the cell.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(trace), timeout_s=60,
        config=CoreConfig(completion_notices=notices, terminal_events=True, repl=True,
                          control_dir=str(tmp_path / "control")),
    ))
    # What the model received (the trace's tool row is written before notices are appended).
    seen = [m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
    return result, seen


def test_a_promoted_cell_is_noticed_once_at_the_next_tool_result_and_still_shown_in_full(tmp_path):
    result, tools = scenario(tmp_path, notices=True)
    assert result.status == "finished", result.error
    first, shell, collect = tools[0], tools[1], tools[2]
    assert "still running" in first and "cell-done" not in first
    assert "[python cell #1 finished (ok); its output is shown at your next python call]" in shell, shell
    assert "cell-done" in collect  # the notice consumed nothing
    assert sum("finished (ok)" in t for t in tools) == 1  # noticed once


def test_known_bad_without_notices_the_terminal_result_is_silent(tmp_path):
    result, tools = scenario(tmp_path, notices=False)
    assert result.status == "finished", result.error
    assert "python cell" not in tools[1] and "cell-done" in tools[2]


def test_browser_notice_names_how_to_collect_a_pending_screenshot(tmp_path, monkeypatch):
    import os

    if not os.path.exists("/proc/self/stat"):
        pytest.skip("needs the Linux browser runner")
    from aether.core import browser
    from tests.test_core_browser_operation_faults_e2e import local_host

    if not browser.images.available():
        pytest.skip("needs image support")
    work, ops = tmp_path / "work", tmp_path / "ops"
    work.mkdir()
    effect = work / "effect"
    screenshot = f"{tmp_path.name}.png"
    output = f"/tmp/{screenshot}"
    original = browser.BrowserSession

    def with_local_transport(factory, env, **kw):
        session = original(factory, env, host=local_host, **kw)
        car = browser.Sidecar("c" * 64, local_host)
        car.started, car.runs.ops_dir = True, str(ops)
        session.sidecar = car
        return session

    monkeypatch.setattr(browser, "BrowserSession", with_local_transport)
    args = {
        "code": f"import time\nfrom PIL import Image\ntime.sleep(2)\n"
                f"open({str(effect)!r}, 'a').write('x')\n"
                f"Image.new('RGB', (24, 24), 'green').save({output!r})\nprint('browser-effect-complete')",
        "screenshot": screenshot,
        "wait_s": 1,
    }
    client = ScriptedClient([
        call("browser", args, "start"),
        call("terminal", {"input": f"while [ ! -s '{ops}/done_1' ]; do sleep 0.1; done; echo independently-observed",
                          "wait_s": 10}, "work"),
        call("browser", {"code": "print('different browser work')"}, "other"),
        call("browser", {**args, "wait_s": 4}, "collect"),
        call("finish", {"summary": "Done."}, "finish"),
    ])

    async def factory(_):
        return "c" * 64

    try:
        result = asyncio.run(run_agent(
            env=LocalEnv(work), task="Observe the result of the browser fixture.", workdir=str(work),
            provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
            timeout_s=60, config=CoreConfig(browser=factory, images=True, completion_notices=True,
                                           control_dir=str(tmp_path / "ctl")),
        ))
        assert result.status == "finished" and len(client.requests) == 5
        seen = [m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
        assert "still running" in seen[0] and "repeat that browser call to collect its screenshot" in seen[1]
        assert "different browser work" in seen[2] and "browser-effect-complete" not in seen[2]
        assert "browser-effect-complete" in seen[3] and effect.read_text() == "x"
        assert f"browser screenshot {screenshot}" in seen[3]
    finally:
        Path(output).unlink(missing_ok=True)

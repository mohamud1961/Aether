"""A7: one promotion rule across owners (real Core loop, real REPL server, scripted model).

A Python cell outlives its wait and is promoted ("still running"). The model then works in the terminal. When the cell
finishes, the next tool result carries one line saying so, from the REPL's own completion record, and the cell's
output is still shown in full at the next python call (the notice consumes nothing). Known-bad: with notices off the
terminal result says nothing about the cell.
"""

import asyncio
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

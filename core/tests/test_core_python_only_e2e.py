"""B18: the Python-only interface (toolset "python") through the real Core loop, REPL server and MCP client daemon.

The model is offered only ``python`` and ``finish``; ``bash()`` handles and ``mcp()`` live in the REPL namespace.

Known-bads (each check can fail):
- with the switch off the terminal and file tools are offered and the library is absent from the namespace;
- a library whose notice hook prints nothing leaves an unseen finished command unreported, and the check sees it;
- a killed MCP client is reported as "never sent", not as a result or a hang.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from aether.core import repl_lib_src
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))
SPEC = {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable, "args": [FIXTURE, "stdio"]}


def run(tmp_path, cells, **overrides):
    work = tmp_path / "work"
    work.mkdir()
    steps = [call("python", {"code": code, "wait_s": 60}, f"c{i}") for i, code in enumerate(cells)]
    client = ScriptedClient([*steps, call("finish", {"summary": "done."}, "done")])
    config = dict(toolset="python", repl=True, mcp_servers=(SPEC,), control_dir=str(tmp_path / "control"),
                  end_processes="stop")
    config.update(overrides)
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Use the fx server.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=120, config=CoreConfig(**config)))
    outputs = {m["tool_call_id"]: m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"}
    return result, client, [outputs[f"c{i}"] for i in range(len(cells))]


def test_only_python_and_finish_are_offered_and_the_prompt_describes_the_library(tmp_path):
    result, client, (out,) = run(tmp_path, ["print(callable(bash), callable(mcp), callable(mcp_many))"])
    assert result.status == "finished"
    assert [t["function"]["name"] for t in client.requests[0]["tools"]] == ["python", "finish"]
    system = client.requests[0]["messages"][0]["content"]
    assert "bash(cmd" in system and "mcp(server, tool" in system and "(fx)" in system
    assert "- terminal:" not in system and "read_file" not in system
    assert out.startswith("True True True")


def test_known_bad_switch_off_offers_stock_tools_and_no_library(tmp_path):
    result, client, (out,) = run(tmp_path, ["print('bash' in globals(), 'mcp' in globals())"], toolset="full")
    names = [t["function"]["name"] for t in client.requests[0]["tools"]]
    assert "terminal" in names and "read_file" in names and "mcp" in names
    assert out.startswith("False False")


BASH_CELLS = [
    "h = bash('echo fast; sleep 0.5; echo done')\nprint('code', h.code)",
    "import time\ntime.sleep(1.5)\nprint('slept')",
    "print(repr(h.output()))",
    "k = bash('sleep 30')\nk.kill()\nprint('killed', k.code)",
    "t = bash('sleep 30', timeout=1)\nt.wait(10)\nt",
    "import asyncio\nh4 = bash('echo awaited')\nawait h4\nprint(h4.code, h4.output().strip())",
]


def test_background_handles_report_completion_kill_timeout_and_await(tmp_path):
    result, _, (started, slept, output, killed, timed, awaited) = run(tmp_path, BASH_CELLS)
    assert result.status == "finished"
    assert started.startswith("code None")  # bash() returns at once
    assert "slept" in slept and "[bash #1 finished: exit 0" in slept  # ended unseen during the cell: told once
    assert "'fast\\ndone\\n'" in output and "[bash #1 finished" not in output  # not told twice
    assert "killed -15" in killed
    assert "timed out, killed" in timed
    assert awaited.startswith("0 awaited")


def test_known_bad_silent_notice_hook_is_detected(tmp_path, monkeypatch):
    silent = repl_lib_src.SOURCE.replace(
        'print("[bash #%d finished: %s: %s]" % (handle.id, handle._state(), handle.cmd[:200]))', "pass")
    assert silent != repl_lib_src.SOURCE
    monkeypatch.setattr(repl_lib_src, "SOURCE", silent)
    _, _, (_, slept, *_rest) = run(tmp_path, BASH_CELLS[:2])
    assert "[bash #1 finished" not in slept


MCP_CELLS = [
    "tools = mcp('fx')\nprint(sorted(t['name'] for t in tools))",
    "print(mcp('fx', 'count'), mcp('fx', 'count'))",
    "try:\n    mcp('fx', 'fail')\nexcept McpError as e:\n    print('error:', e)",
    "try:\n    mcp('nope', 'count')\nexcept McpError as e:\n    print('error:', e)",
    "r = mcp_many('fx', [('count', {}), ('fail', {}), ('count', {})])\nprint([type(x).__name__ for x in r], sorted([r[0], r[2]]))",
    "print(mcp('fx', 'effect', path=EFFECT, delay=0))",
]


def test_in_cell_mcp_lists_calls_reports_errors_and_keeps_one_session(tmp_path):
    effect = tmp_path / "effect"
    cells = [f"EFFECT = {str(effect)!r}\n" + MCP_CELLS[0], *MCP_CELLS[1:]]
    result, _, (listed, counted, failed, unknown, many, effected) = run(tmp_path, cells)
    assert result.status == "finished"
    assert "'count'" in listed and "'fail'" in listed
    assert counted.startswith("count=1 count=2")
    assert failed.startswith("error: fail: it broke")
    assert unknown.startswith("error: no declared MCP server named 'nope'")
    assert many.startswith("['str', 'McpError', 'str'] ['count=3', 'count=4']")  # one session; a failure keeps the rest
    assert effected.startswith("effect-done") and effect.read_bytes() == b"x"
    receipts = list((tmp_path / "control" / "mcp").glob("session-*/resp_py*.json"))
    assert len(receipts) == 8  # every published in-cell request left its response file as a receipt


def test_killed_client_is_reported_never_sent_not_a_result(tmp_path):
    cells = ["print(mcp('fx', 'count'))",
             "import os, signal\nd = _client('fx')\nos.kill(int(open(d + '/owner').read().split()[0]), signal.SIGKILL)",
             "import time\ntime.sleep(0.5)\ntry:\n    mcp('fx', 'count', timeout=10)\nexcept McpError as e:\n    print('error:', e)"]
    result, _, (first, _, after) = run(tmp_path, cells)
    assert result.status == "finished" and first.startswith("count=1")
    assert after.startswith("error:") and "never sent" in after


@pytest.mark.parametrize("overrides", [{"repl": False}, {"terminal_events": True}, {"workspace_search": True},
                                       {"verify": True}])
def test_python_toolset_refuses_combinations_it_cannot_serve(overrides):
    with pytest.raises(ValueError, match="python toolset"):
        CoreConfig(**{"toolset": "python", "repl": True, **overrides})


LATENCY_CELL = ("import time, statistics\nmcp('fx', 'count')\nlat = []\nfor _ in range(30):\n"
                "    t = time.perf_counter(); mcp('fx', 'count'); lat.append(time.perf_counter() - t)\n"
                "print('median_ms %.2f' % (statistics.median(lat) * 1000))")


def _median_ms(out):
    return float(out.split("median_ms ", 1)[1].split()[0])


def test_wake_pipe_makes_dependent_calls_fast_and_without_it_they_wait_for_the_poll(tmp_path, monkeypatch):
    (tmp_path / "woken").mkdir()
    _, _, (woken,) = run(tmp_path / "woken", [LATENCY_CELL])
    silent = repl_lib_src.SOURCE.replace("    _wake(d)\n    return ident", "    return ident")
    assert silent != repl_lib_src.SOURCE  # known-bad: publish without waking the client
    monkeypatch.setattr(repl_lib_src, "SOURCE", silent)
    (tmp_path / "polled").mkdir()
    _, _, (polled,) = run(tmp_path / "polled", [LATENCY_CELL])
    assert _median_ms(woken) < 12, woken
    assert _median_ms(polled) > 18, polled  # the client's 0.05 s look is the only wake

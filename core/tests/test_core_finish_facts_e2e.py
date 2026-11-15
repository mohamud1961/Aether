"""Delivered-state facts at the first finish (real shell, real Core loop, AETHER_CORE_FINISH_FACTS).

The run writes one file with a file tool, changes another in the shell, deletes nothing, and leaves a command running
in a second terminal. The first finish returns the facts once: both changed files with their sizes, the running
process, and the unfinished command by terminal and number. The second finish ends the work. Facts only: the text
carries no advice.
"""

import asyncio
import json

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


def run(tmp_path, facts, terminal_events=True, *, command="sleep 30", synchronize=False):
    work = tmp_path / "work"
    work.mkdir()
    (work / "kept.txt").write_text("untouched\n")
    script = [
        call("write_file", {"path": "answer.txt", "content": "42\n"}, "write"),
        call("terminal", {"input": "printf 'abc' > notes.txt", "wait_s": 5}, "shell"),
        call("terminal", {"name": "server", "input": command, "wait_s": 0.3}, "serve"),
    ]
    if synchronize:
        done = str(tmp_path / "control" / "term" / "server" / "done_1")
        script.append(call("terminal", {"input": f"touch release; while [ ! -s '{done}' ]; do sleep .05; done"}, "release"))
    client = ScriptedClient([*script,
        call("finish", {"summary": "answer.txt holds 42."}, "first"),
        call("finish", {"summary": "Done."}, "second"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Write the answer to answer.txt.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(trace), timeout_s=90,
        config=CoreConfig(finish_facts=facts, terminal_events=terminal_events,
                          control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    return result, client, rows


def test_first_finish_returns_delivered_state_facts_once(tmp_path):
    result, client, rows = run(tmp_path, facts=True)
    assert result.status == "finished" and len(client.requests) == 5
    shown = [m for m in client.requests[4]["messages"] if m["role"] == "tool"][-1]["content"]
    assert shown.startswith("Delivered state at your finish request, as observed by Core:")
    assert "Changed files since the task started (2 current files measured):" in shown
    assert "answer.txt: 3 bytes" in shown and "notes.txt: 3 bytes" in shown and "kept.txt" not in shown
    assert "sleep 30" in shown  # the process still running
    assert "terminal server: command #1 started and still running; no result yet" in shown
    assert "should" not in shown.lower() and "consider" not in shown.lower()  # facts, no advice
    (row,) = [r for r in rows if r["event"] == "finish_facts"]
    assert row["operations"] == ["terminal server: command #1 started and still running; no result yet"]
    assert not [r for r in rows if r["event"] == "finish_pending_terminal_observation"]  # one hold, not two
    assert result.extras["switches"]["finish_facts"] is True


def test_switch_off_keeps_the_previous_finish_path(tmp_path):
    result, client, rows = run(tmp_path, facts=False)
    assert not [r for r in rows if r["event"] == "finish_facts"]
    held = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"][-1]["content"]
    assert "Delivered state" not in held


def test_finish_observes_a_completion_that_arrived_without_a_terminal_poll(tmp_path):
    result, client, rows = run(tmp_path, facts=True, synchronize=True,
                                 command="while [ ! -f release ]; do sleep .05; done; (exit 7)")
    assert result.status == "finished"
    (observation,) = [row for row in rows if row["event"] == "finish_facts"]
    assert observation["operations"] == ["terminal server: command #1 completed with exit 7; result not shown"]
    assert "still running" not in observation["operations"][0]


def test_a_daemon_that_left_the_terminal_tree_is_still_reported(tmp_path):
    """A6/A9: a service that double-forks (as `service x start` does) is reparented out of the terminal's process tree.
    It was started during the run and still runs at finish, so the observation names it."""
    result, client, rows = run(tmp_path, facts=True, command="(exec -a aether-daemon-probe sleep 37 &) ; sleep 30")
    assert result.status == "finished"
    (row,) = [r for r in rows if r["event"] == "finish_facts"]
    assert any("aether-daemon-probe" in p or "sleep 37" in p for p in row["started_elsewhere"]), row["started_elsewhere"]
    assert not any("sleep 30" in p for p in row["started_elsewhere"])  # inside a terminal: listed there, not twice
    # Known-bad: the terminal-tree listing alone (the observation before A6) does not see the daemon.
    assert not any("aether-daemon-probe" in p or "sleep 37" in p for p in row["processes"]), row["processes"]
    shown = [m for m in client.requests[4]["messages"] if m["role"] == "tool"][-1]["content"]
    assert "Other processes started during this run and still running:" in shown

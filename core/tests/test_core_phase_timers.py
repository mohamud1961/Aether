"""H11 phase timers: ``prep_s`` on model events and ``pre_s``/``post_s`` on tool events tile the run's wall time.

The census (research H11) found ~1 s per model call outside model and tool time that the trace could not attribute.
With these fields every second between events belongs to a named phase. Known-bad: work inserted after a tool
returns (a slow post-tool step) must show up in that tool's ``post_s``; summing without ``post_s`` must then leave
the run visibly uncovered, so the coverage check can fail.
"""

import asyncio
import json
import time

from aether.core import finish_report
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


def run(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    steps = [call("terminal", {"input": f"sleep 0.2; echo step{i}"}, f"c{i}") for i in range(3)]
    client = ScriptedClient([*steps, call("finish", {"summary": "done."}, "done")])
    asyncio.run(run_agent(env=LocalEnv(work), task="Run three steps.", workdir=str(work),
                          provider=ChatProvider(client, model="offline", params={}),
                          trace=Trace(tmp_path / "trace.jsonl"), timeout_s=60,
                          config=CoreConfig(control_dir=str(tmp_path / "control"))))
    return [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]


def coverage(events, with_post=True):
    span = events[-1]["t"] - events[0]["t"]
    timed = sum((e.get("prep_s") or 0) + (e.get("latency_s") or 0) for e in events if e["event"] == "model")
    timed += sum((e.get("pre_s") or 0) + (e.get("duration_s") or 0) + ((e.get("post_s") or 0) if with_post else 0)
                 for e in events if e["event"] == "tool")
    return timed / span


def test_model_and_tool_events_carry_phase_timers_that_cover_the_run(tmp_path):
    events = run(tmp_path)
    models = [e for e in events if e["event"] == "model"]
    tools = [e for e in events if e["event"] == "tool"]
    assert len(models) == 4 and len(tools) == 4
    assert all(isinstance(e["prep_s"], float) and e["prep_s"] >= 0 for e in models)
    assert all(isinstance(e["pre_s"], float) and isinstance(e["post_s"], float) for e in tools)
    assert 0.85 <= coverage(events) <= 1.05, coverage(events)


def test_known_bad_slow_post_tool_step_is_caught_in_post_s(tmp_path, monkeypatch):
    original = finish_report.record

    def slow_record(*args, **kwargs):
        time.sleep(0.4)
        return original(*args, **kwargs)

    monkeypatch.setattr(finish_report, "record", slow_record)
    events = run(tmp_path)
    terminal = [e for e in events if e["event"] == "tool" and e["name"] == "terminal"]
    assert all(e["post_s"] >= 0.4 for e in terminal)
    assert 0.85 <= coverage(events) <= 1.05
    assert coverage(events, with_post=False) < 0.7  # without the timer the inserted work is unattributed

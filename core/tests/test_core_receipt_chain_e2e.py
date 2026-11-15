"""H1 on the real loop: a Core run's own trace and calls log form a holding receipt chain, and each terminal
effect's delivery tag equals the tag the terminal wrote beside its operation record on disk.

With terminal events off (stock) no operation record is written, so the effect is identified by its call id alone.
Known-bad: the same trace with call ids stripped (as before H1) is reported as unidentified, not as a chain.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from receipt_chain import build  # noqa: E402

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")


def paid(turn_chunks, rid):
    for c in turn_chunks:
        c.id = rid  # what a real stream carries; ScriptedClient chunks have none
    return turn_chunks


def run_trial(tmp_path, events=True):
    agent = tmp_path / "trial" / "agent"
    agent.mkdir(parents=True)
    script = [
        paid(call("terminal", {"input": "echo one > a.txt"}, "c1"), "r1"),
        paid(call("terminal", {"input": "cat a.txt"}, "c2"), "r2"),
        paid(call("finish", {"summary": "done"}, "c3"), "r3"),
    ]
    control = tmp_path / "ctl"
    asyncio.run(run_agent(
        env=LocalEnv(tmp_path), task="write a.txt", workdir=str(tmp_path),
        provider=ChatProvider(ScriptedClient(script), model="scripted", params={}, log=CallLog(agent / "core_calls.jsonl")),
        timeout_s=60, trace=Trace(agent / "core_trace.jsonl"), config=CoreConfig(control_dir=str(control), terminal_events=events),
    ))
    (tmp_path / "trial" / "result.json").write_text(json.dumps({"verifier_result": {"rewards": {"reward": 1.0}}}))
    return tmp_path / "trial", control


def test_a_real_run_forms_a_holding_chain_and_tags_match_the_disk(tmp_path):
    trial, control = run_trial(tmp_path)
    receipts, breaks = build(str(trial))
    assert breaks == [], breaks
    effects = {r["id"]: r for r in receipts if r["kind"] == "effect"}
    assert [effects[c]["parent"] for c in ("c1", "c2", "c3")] == ["r1", "r2", "r3"]
    on_disk = {p.read_text() for p in control.rglob("delivered_*")}
    shown = {effects[c]["fields"]["delivery"] for c in ("c1", "c2")}
    assert None not in shown and shown <= on_disk, (shown, on_disk)


def test_known_bad_a_trace_without_call_ids_is_not_a_chain(tmp_path):
    trial, _ = run_trial(tmp_path)
    path = trial / "agent" / "core_trace.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    path.write_text("".join(json.dumps({k: v for k, v in r.items() if k != "call_id"}) + "\n" for r in rows))
    _, breaks = build(str(trial))
    assert any("no identified effects" in b for b in breaks)


def test_stock_terminal_identifies_effects_by_call_id_alone(tmp_path):
    trial, control = run_trial(tmp_path, events=False)
    receipts, breaks = build(str(trial))
    assert breaks == []
    assert all(r["fields"]["delivery"] is None for r in receipts if r["kind"] == "effect")
    assert not list(control.rglob("delivered_*"))

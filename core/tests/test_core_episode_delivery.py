"""Recreated interface/repair episodes inspired by archived failures, not VM replays.

The artifact oracle is independent of the scripted actor's checker. These tests
exercise real Core dispatch, terminal processes, file tools and finish reporting.
Only fixed synthetic commands run, in each test's disposable working directory.
"""
import asyncio
import hashlib
import json
import shlex
from pathlib import Path

import pytest

from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


@pytest.mark.parametrize("repair", [False, True], ids=["known-bad", "repaired"])
def test_schema_repair_repeated_actions_and_false_checker_preserve_real_delivery(tmp_path, repair):
    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    # Public task contract, separate from both the actor and its checker.
    task = 'Write result.json as exactly {"value":7}, encoded as JSON. Then finish.'
    checker = "import json; d=json.load(open('result.json')); assert d == {'value': 7}"
    script = [
        call("write_file", {"path": "result.json", "content": '{"val":7}\n'}, "initial"),
        call("terminal", {"input": "python3 -c " + shlex.quote(checker)}, "check-bad"),
        call("read_file", {"path": "result.json"}, "inspect"),
    ]
    if repair:
        script.extend([
            call("edit_file", {"path": "result.json", "old_str": '"val"', "new_str": '"value"'}, "repair"),
            call("terminal", {"input": "python3 -c " + shlex.quote(checker)}, "check-good"),
        ])
    # Same action executed twice must produce distinct actual observations.
    repeated = "printf 'tick\\n' >> ticks.txt; wc -l < ticks.txt"
    script.extend([
        call("terminal", {"input": repeated}, "repeat-1"),
        call("terminal", {"input": repeated}, "repeat-2"),
        call("terminal", {"input": "printf 'FAIL: use val instead of value (synthetic incorrect checker)\\n'"}, "false-checker"),
        call("read_file", {"path": "result.json"}, "inspect-final"),
        call("finish", {"summary": "scripted completion; independent oracle grades artifact"}, "done"),
    ])
    client = ScriptedClient(script)
    provider = ChatProvider(client, model="scripted-no-inference", params={}, log=CallLog(tmp_path / "calls.jsonl"))
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task=task, workdir=str(work), provider=provider,
        timeout_s=120, trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(control), end_processes="stop"),
    ))
    assert result.status == "finished"
    rows = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    terminal = [r for r in rows if r["event"] == "tool" and r.get("name") == "terminal"]
    assert "[exit 1" in terminal[0]["result"]  # actual failed independent checker
    if repair:
        assert "[exit 0" in terminal[1]["result"]
    ticks = [r for r in terminal if r["args"]["input"] == repeated]
    assert len(ticks) == 2 and ticks[0]["result"] != ticks[1]["result"]
    assert (work / "ticks.txt").read_bytes() == b"tick\ntick\n"
    # A false tool result is evidence for the model, never automatic authority to mutate.
    data = (work / "result.json").read_bytes()
    assert (json.loads(data) == {"value": 7}) is repair
    report = result.extras["finish_report"]
    delivered = {Path(row["path"]).name: row for row in report["delivered_files"]}
    assert delivered["result.json"]["sha256"] == hashlib.sha256(data).hexdigest()
    assert delivered["result.json"]["bytes"] == len(data)
    assert not result.extras["left_running"] and not result.extras["cleanup_errors"]
    final_messages = client.requests[-1]["messages"]
    tool_ids = [m["tool_call_id"] for m in final_messages if m["role"] == "tool"]
    assert tool_ids.count("repeat-1") == 1 and tool_ids.count("repeat-2") == 1

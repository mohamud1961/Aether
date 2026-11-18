"""A finish held for a real terminal result must allow a fresh decision."""

import asyncio
import json
import shutil

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk, tool_chunk


def test_held_finish_defers_all_queued_actions_until_a_new_turn(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "staged").write_bytes(b"old\n")
    client = ScriptedClient([
        call("terminal", {
            "input": "sleep 0.8; printf 'ready\\n' > prerequisite",
            "name": "build", "wait_s": 0.1,
        }, "start"),
        [
            tool_chunk("finish", {"summary": "Ready."}, index=0, call_id="held"),
            tool_chunk("terminal", {"input": "cat staged >> published"}, index=1, call_id="early"),
            tool_chunk("finish", {"summary": "Published."}, index=2, call_id="early-finish"),
            chunk(finish="tool_calls"),
        ],
        call("write_file", {"path": "staged", "content": "new\n"}, "prepare"),
        call("terminal", {"input": "test -f prerequisite && cat staged >> published"}, "publish"),
        call("finish", {"summary": "Published."}, "done"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Publish the new release exactly once when the prerequisite is ready.",
        workdir=str(work), provider=ChatProvider(client, model="offline", params={}),
        trace=Trace(trace), timeout_s=45,
        config=CoreConfig(terminal_events=True, control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    assert result.status == "finished"
    assert (work / "prerequisite").read_bytes() == b"ready\n"
    assert (work / "published").read_bytes() == b"new\n"
    tools = [msg for msg in client.requests[2]["messages"] if msg["role"] == "tool"]
    assert [msg["tool_call_id"] for msg in tools[-3:]] == ["held", "early", "early-finish"]
    observed, _ = json.JSONDecoder().raw_decode(tools[-3]["content"].split("\n", 1)[1])
    assert [event["name"] for event in observed["completed"]] == ["build"]
    assert not observed["pending"] and not observed["unknown"]
    assert all("not dispatched" in msg["content"] for msg in tools[-2:])
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    skipped = [row["call_id"] for row in rows if row["event"] == "action_skipped"]
    assert skipped == ["early", "early-finish"]


@pytest.mark.skipif(shutil.which("python3") is None, reason="requires Python HTTP server")
def test_finish_does_not_wait_for_an_intentionally_running_service(tmp_path):
    work = tmp_path / "service"
    work.mkdir()
    (work / "index.html").write_text("release-violet")
    (work / "serve.py").write_text(
        "from http.server import HTTPServer, SimpleHTTPRequestHandler\n"
        "from pathlib import Path\n"
        "server = HTTPServer(('127.0.0.1', 0), SimpleHTTPRequestHandler)\n"
        "Path('port').write_text(str(server.server_port))\n"
        "server.serve_forever()\n"
    )
    client = ScriptedClient([
        call("terminal", {"name": "service", "input": "python3 serve.py", "wait_s": 0.1}, "start-service"),
        call("terminal", {"input": "python3 -c \"from pathlib import Path; import urllib.request as u; "
              "assert u.urlopen('http://127.0.0.1:' + Path('port').read_text()).read() == b'release-violet'\""}, "check"),
        call("finish", {"summary": "The service is running and responding."}, "finish-first"),
        call("finish", {"summary": "The service should remain running."}, "finish-confirmed"),
    ])
    trace = tmp_path / "service.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Serve the release document and leave it available.",
        workdir=str(work), provider=ChatProvider(client, model="offline", params={}),
        trace=Trace(trace), timeout_s=38,
        config=CoreConfig(terminal_events=True, control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    assert result.status == "finished"
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    check = next(row for row in rows if row["event"] == "tool" and "urlopen" in row["args"].get("input", ""))
    assert "[exit 0" in check["result"]
    probe = next((row for row in rows if row["event"] == "finish_pending_terminal_observation"), None)
    assert probe is not None, [row["result"] for row in rows if row["event"] == "tool"]
    assert probe["pending"] == ["service"] and not probe["completed"] and not probe["unknown"]
    assert probe["elapsed_s"] < 4, "automatic finish consumed the solve budget waiting for the service to stop"

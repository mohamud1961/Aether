"""Check bounded workspace search through the real Core loop and Linux filesystem."""

import asyncio
import hashlib
import json
import os
import sys

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


@pytest.mark.skipif(sys.platform != "linux", reason="Linux file descriptors and mount identity")
def test_literal_lookup_keeps_version_and_reports_unsearched_scope(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    data = work / "data"
    data.mkdir()
    source = data / "input.txt"
    source.write_bytes(b"header\na*[b] literal\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_bytes(source.read_bytes())
    (data / "linked").symlink_to(outside, target_is_directory=True)
    os.mkfifo(data / "pipe")
    client = ScriptedClient([
        call("search_workspace", {"mode": "text", "subdir": "data", "query": "a*[b]"}, "search"),
        call("search_workspace", {"mode": "text", "subdir": "data/linked", "query": "a*[b]"}, "outside"),
        call("read_file", {"path": "data/input.txt"}, "read"),
        call("write_file", {"path": "answer", "content": "data/input.txt:2\n"}, "deliver"),
        call("finish", {"summary": "Done."}, "finish"),
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Record the file and line containing the literal marker.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace"), timeout_s=25,
        config=CoreConfig(workspace_search=True, control_dir=str(tmp_path / "control")),
    ))
    assert result.status == "finished"
    observations = {m["tool_call_id"]: m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"}
    scan, _ = json.JSONDecoder().raw_decode(observations["search"])
    assert scan["status"] == "partial"
    assert scan["matches"] == [{"path": "data/input.txt", "line": 2, "column": 1,
                                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]
    assert '"status":"scope_unavailable"' in observations["outside"]
    assert "private.txt" not in observations["search"]
    assert "a*[b] literal" in observations["read"]
    assert (work / "answer").read_bytes() == b"data/input.txt:2\n"

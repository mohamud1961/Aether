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
                                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "text": "a*[b] literal"}]
    assert scan["matches_total"] == 1 and scan["files_matched"] == 1
    assert '"status":"scope_unavailable"' in observations["outside"]
    assert "private.txt" not in observations["search"]
    assert "a*[b] literal" in observations["read"]
    assert (work / "answer").read_bytes() == b"data/input.txt:2\n"


@pytest.mark.skipif(sys.platform != "linux", reason="Linux file descriptors and mount identity")
def test_search_agrees_with_a_grep_control_and_reports_totals(tmp_path):
    """Control: grep -rn over the same tree, minus .git and node_modules. Every grep hit must be counted, the shown
    lines must be grep's lines, and project directories named tests/ must be searched."""
    import subprocess

    from aether.core import workspace_search

    work = tmp_path / "work"
    for rel, body in {
        "src/app.py": "def handler():\n    return TOKEN_LIMIT\n",
        "tests/test_app.py": "from src.app import handler\nassert handler() == TOKEN_LIMIT\n",
        "docs/notes.md": "TOKEN_LIMIT is 4096\n",
        "node_modules/lib/x.js": "TOKEN_LIMIT\n",
        ".git/config": "TOKEN_LIMIT\n",
        "zz/many.txt": "".join(f"row {i} TOKEN_LIMIT\n" for i in range(60)),
    }.items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(body)
    control = tmp_path / "control"

    def search(**args):
        return json.loads(asyncio.run(workspace_search.search(LocalEnv(work), str(work), str(control), args)))

    grep = subprocess.run(["grep", "-rn", "--exclude-dir=.git", "--exclude-dir=node_modules", "TOKEN_LIMIT", "."],
                          cwd=work, capture_output=True, text=True).stdout.splitlines()
    text = search(mode="text", query="TOKEN_LIMIT")
    assert text["status"] == "searched" and text["matches_total"] == len(grep) == 63
    assert text["files_matched"] == 4 and text["shown"] == 40
    shown = {f"./{m['path']}:{m['line']}:{m['text']}" for m in text["matches"]}
    assert shown <= set(grep)
    assert any(m["path"] == "tests/test_app.py" for m in text["matches"])  # project tests are searched
    assert not any(m["path"].startswith(("node_modules", ".git")) for m in text["matches"])

    regex = search(mode="regex", query=r"return \w+_LIMIT", subdir="src")
    assert [(m["path"], m["line"], m["column"]) for m in regex["matches"]] == [("src/app.py", 2, 5)]
    names = search(mode="filename", query="test_")
    assert [m["path"] for m in names["matches"]] == ["tests/test_app.py"]
    with pytest.raises(ValueError):
        search(mode="regex", query="(unclosed")
    with pytest.raises(ValueError):
        search(mode="text", query="x", subdir="../outside")

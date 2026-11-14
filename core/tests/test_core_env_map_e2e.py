"""Repositories and listening services measured at start (real git, real sockets, real Core loop)."""

import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/net/tcp") or shutil.which("git") is None, reason="native Linux git/socket qualification"
)

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "HOME": "/tmp"}


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True, capture_output=True)


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            h.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
            h.update(str(path.stat().st_mtime_ns).encode())
    return h.hexdigest()


def fixture(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    for i in range(3):
        (work / "app.py").write_text(f"v{i}\n")
        git(work, "add", "app.py")
        git(work, "commit", "-q", "-m", f"change {i}")
    git(work, "tag", "v1")
    git(work, "branch", "feature")
    (work / "app.py").write_text("stashed\n")
    git(work, "stash", "-q")
    (work / "app.py").write_text("edited\n")
    (work / "new.txt").write_text("untracked\n")
    hook = tmp_path / "pwned"
    git(work, "config", "core.fsmonitor", f"touch {hook}; echo")
    nested = work / "data" / "vendor"
    nested.mkdir(parents=True)
    git(nested, "init", "-q", "-b", "trunk")
    (nested / "x").write_text("x\n")
    git(nested, "add", "x")
    git(nested, "commit", "-q", "-m", "vendored")
    outside = tmp_path / "outside"
    outside.mkdir()
    git(outside, "init", "-q")
    (work / "linked").mkdir()
    os.symlink(outside / ".git", work / "linked" / ".git")
    os.mkfifo(work / "pipe")
    return work, hook


def run(tmp_path, work, enabled):
    client = ScriptedClient([call("finish", {"summary": "looked."}, "done")])
    asyncio.run(run_agent(
        env=LocalEnv(work), task="Look around.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=60, config=CoreConfig(env_map=enabled, control_dir=str(tmp_path / "control")),
    ))
    first = "\n".join(str(m["content"]) for m in client.requests[0]["messages"] if m["role"] == "user")
    rows = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return first, rows


def test_map_reports_repositories_and_listeners_without_changing_or_executing_anything(tmp_path):
    work, hook = fixture(tmp_path)
    before = tree_digest(work / ".git")
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    port = server.getsockname()[1]
    try:
        first, rows = run(tmp_path, work, enabled=True)
    finally:
        server.close()
    assert f"git repository {work}: on main; HEAD " in first and "change 2" in first
    assert "5 commits on all refs" in first  # three commits plus the stash's work-tree and index commits
    assert "branches: feature main" in first and "tags 1, stashes 1" in first
    reflog = subprocess.run(["git", "reflog", "show", "--format=%h", "HEAD"], cwd=work, env=GIT_ENV,
                            capture_output=True, text=True, check=True).stdout.count("\n")
    assert reflog >= 3 and f"HEAD reflog entries {reflog};" in first
    assert "changed or untracked paths: 4" in first  # app.py, new.txt, data/, linked/ (git does not list the fifo)
    assert f"git repository {work}/data/vendor: on trunk" in first and "vendored" in first
    assert "outside" not in first and "linked" not in first  # a .git link is never followed
    assert f"127.0.0.1:{port} (" in first
    assert not hook.exists()  # the repository's fsmonitor command never ran
    assert tree_digest(work / ".git") == before  # no index refresh, no lock, no write
    (row,) = [r for r in rows if r["event"] == "env_map"]
    assert row["ok"] and row["repos"] == 2 and row["listening"] >= 1


def test_switch_off_adds_nothing(tmp_path):
    work, _ = fixture(tmp_path)
    first, rows = run(tmp_path, work, enabled=False)
    assert "git repository" not in first and not [r for r in rows if r["event"] == "env_map"]


def test_plain_directory_without_git_or_listeners_adds_no_note(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "data.csv").write_text("a,b\n")
    first, rows = run(tmp_path, work, enabled=True)
    assert "Repositories and services" not in first
    (row,) = [r for r in rows if r["event"] == "env_map"]
    assert row["ok"] and row["repos"] == 0

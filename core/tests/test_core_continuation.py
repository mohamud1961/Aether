"""Continuation runs through the adapter's ``run()``: seed files in, message appended, capture out.

The fake environment only understands the two sandbox commands continuation actually issues (``mkdir -p`` and
``sha256sum <path>``); anything else is a test bug, so an unexpected sandbox call fails the test.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import shlex
import time
from types import SimpleNamespace

import pytest

from aether.core import continuation
from aether.core import harbor_agent as adapter

WORKDIR = "/app"


class FakeEnv:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.dirs: set[str] = set()
        self.commands: list[str] = []
        self.uploads: list[tuple[str, str]] = []
        self.downloads: list[tuple[str, str]] = []
        self.corrupt: set[str] = set()

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        self.commands.append(command)
        argv = shlex.split(command)
        if argv[:2] == ["mkdir", "-p"] and len(argv) == 3:
            self.dirs.add(argv[2])
            return SimpleNamespace(return_code=0, stdout="", stderr="")
        if argv[0] == "sha256sum" and len(argv) == 2:
            path = argv[1]
            if path not in self.files:
                return SimpleNamespace(
                    return_code=1, stdout="", stderr=f"sha256sum: {path}: No such file or directory\n"
                )
            digest = hashlib.sha256(self.files[path]).hexdigest()
            return SimpleNamespace(return_code=0, stdout=f"{digest}  {path}\n", stderr="")
        raise AssertionError(f"unexpected sandbox command: {command}")

    async def upload_file(self, source_path, target_path):
        data = Path(source_path).read_bytes()
        self.files[target_path] = b"CORRUPTED" if target_path in self.corrupt else data
        self.uploads.append((str(source_path), target_path))

    async def download_file(self, source_path, target_path):
        self.downloads.append((source_path, str(target_path)))
        if source_path not in self.files:
            raise FileNotFoundError(source_path)
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        Path(target_path).write_bytes(self.files[source_path])


class FakeProvider:
    async def aclose(self) -> None:
        return None


def _agent(tmp_path, monkeypatch, calls, *, fail=None, environ=None):
    """A real ``AetherCoreAgent.run()`` with the model provider and sandbox discovery replaced."""
    for name in (
        continuation.SEED_ENV,
        continuation.CONTINUE_ENV,
        continuation.FEEDBACK_ENV,
        continuation.CAPTURE_ENV,
        continuation.CAPTURE_TIMEOUT_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    agent = object.__new__(adapter.AetherCoreAgent)
    agent.logs_dir = tmp_path / "logs"
    agent._agent_timeout_sec = 60.0
    agent._extra_env = {
        adapter.REVIEW_ENV: "off",
        adapter.CONTEXT_ENV: "project",
        adapter.REPL_ENV: "off",
        adapter.IMAGES_ENV: "off",
        **(environ or {}),
    }

    async def fake_run_agent(**kwargs):
        calls.append(kwargs)
        if fail is not None:
            raise fail
        return SimpleNamespace(status="finished")

    monkeypatch.setattr(adapter, "build_provider", lambda logs, environ=None: FakeProvider())
    monkeypatch.setattr(adapter, "build_review", lambda logs, environ=None: None)
    monkeypatch.setattr(adapter, "discover_workdir", lambda environment: _workdir())
    monkeypatch.setattr(adapter, "run_agent", fake_run_agent)
    monkeypatch.setattr(adapter, "_write_record", lambda *a, **k: None)
    return agent


async def _workdir() -> str:
    return WORKDIR


def _run(agent, env, instruction="do the task"):
    asyncio.run(agent.run(instruction, env, SimpleNamespace()))


def test_unset_settings_leave_the_default_run_unchanged(tmp_path, monkeypatch):
    env, calls = FakeEnv(), []
    _run(_agent(tmp_path, monkeypatch, calls), env)

    assert calls[0]["task"] == "do the task"
    assert env.commands == [] and env.uploads == [] and env.downloads == []
    assert not (tmp_path / "logs" / "continuation").exists()


def test_seed_files_are_uploaded_read_back_and_recorded(tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    (seed / "sub").mkdir(parents=True)
    (seed / "a.txt").write_text("alpha\n", encoding="utf-8")
    (seed / "sub" / "b.bin").write_bytes(b"\x00\x01")
    env = FakeEnv()
    _run(_agent(tmp_path, monkeypatch, [], environ={continuation.SEED_ENV: str(seed)}), env)

    manifest = json.loads((tmp_path / "logs" / "continuation" / "seed_manifest.json").read_text())
    assert manifest == [
        {"path": "/app/a.txt", "sha256": hashlib.sha256(b"alpha\n").hexdigest(), "bytes": 6},
        {"path": "/app/sub/b.bin", "sha256": hashlib.sha256(b"\x00\x01").hexdigest(), "bytes": 2},
    ]
    assert env.files == {"/app/a.txt": b"alpha\n", "/app/sub/b.bin": b"\x00\x01"}
    assert env.dirs == {"/app", "/app/sub"}
    assert [c for c in env.commands if c.startswith("sha256sum")] == [
        "sha256sum /app/a.txt",
        "sha256sum /app/sub/b.bin",
    ]


def test_a_corrupted_seed_upload_stops_the_run_before_run_agent(tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "a.txt").write_text("alpha\n", encoding="utf-8")
    env, calls = FakeEnv(), []
    env.corrupt.add("/app/a.txt")
    agent = _agent(tmp_path, monkeypatch, calls, environ={continuation.SEED_ENV: str(seed)})

    with pytest.raises(RuntimeError, match="readback"):
        _run(agent, env)
    assert calls == []  # the model never saw a wrong seed
    assert env.uploads == [(str(seed / "a.txt"), "/app/a.txt")]


def test_continue_then_feedback_are_appended_in_order_and_recorded(tmp_path, monkeypatch):
    cont, feedback = tmp_path / "continue.txt", tmp_path / "feedback.txt"
    cont.write_text("FIRST", encoding="utf-8")
    feedback.write_text("SECOND", encoding="utf-8")
    calls = []
    _run(
        _agent(
            tmp_path,
            monkeypatch,
            calls,
            environ={continuation.CONTINUE_ENV: str(cont), continuation.FEEDBACK_ENV: str(feedback)},
        ),
        FakeEnv(),
    )

    assert calls[0]["task"] == "do the task\n\nFIRST\n\nSECOND"
    manifest = json.loads((tmp_path / "logs" / "continuation" / "message_manifest.json").read_text())
    assert manifest["continue"] == {"path": str(cont), "sha256": hashlib.sha256(b"FIRST").hexdigest(), "chars": 5}
    assert manifest["feedback"] == {"path": str(feedback), "sha256": hashlib.sha256(b"SECOND").hexdigest(), "chars": 6}
    assert manifest["instruction_sha256"] == hashlib.sha256(b"do the task\n\nFIRST\n\nSECOND").hexdigest()


def test_feedback_without_a_continuation_file_is_refused(tmp_path, monkeypatch):
    feedback = tmp_path / "feedback.txt"
    feedback.write_text("SECOND", encoding="utf-8")
    calls = []
    agent = _agent(tmp_path, monkeypatch, calls, environ={continuation.FEEDBACK_ENV: str(feedback)})

    with pytest.raises(ValueError, match=continuation.CONTINUE_ENV):
        _run(agent, FakeEnv())
    assert calls == []


def test_capture_writes_files_and_manifest_and_records_a_missing_path(tmp_path, monkeypatch):
    env = FakeEnv()
    env.files["/app/out/result.txt"] = b"done\n"
    env.files["/app/notes.md"] = b"# notes\n"
    calls = []
    agent = _agent(
        tmp_path,
        monkeypatch,
        calls,
        environ={continuation.CAPTURE_ENV: "/app/out/result.txt, notes.md, /app/missing.txt"},
    )
    _run(agent, env)

    manifest = json.loads((tmp_path / "logs" / "continuation" / "capture_manifest.json").read_text())
    rows = {row["path"]: row for row in manifest}
    assert rows["/app/out/result.txt"] == {
        "path": "/app/out/result.txt",
        "status": "captured",
        "sha256": hashlib.sha256(b"done\n").hexdigest(),
        "bytes": 5,
        "error": None,
    }
    assert rows["/app/notes.md"]["status"] == "captured"
    assert rows["/app/missing.txt"]["status"] == "missing"
    assert rows["/app/missing.txt"]["sha256"] is None and rows["/app/missing.txt"]["bytes"] is None
    assert (tmp_path / "logs" / "continuation" / "capture" / "work" / "out" / "result.txt").read_bytes() == b"done\n"
    assert (tmp_path / "logs" / "continuation" / "capture" / "work" / "notes.md").read_bytes() == b"# notes\n"
    assert len(env.downloads) == 3  # the missing path was attempted, not skipped


def test_capture_still_runs_when_the_agent_raised(tmp_path, monkeypatch):
    env = FakeEnv()
    env.files["/app/result.txt"] = b"partial\n"
    agent = _agent(
        tmp_path,
        monkeypatch,
        [],
        fail=RuntimeError("agent failed"),
        environ={continuation.CAPTURE_ENV: "result.txt"},
    )

    with pytest.raises(RuntimeError, match="agent failed"):
        _run(agent, env)

    manifest = json.loads((tmp_path / "logs" / "continuation" / "capture_manifest.json").read_text())
    assert manifest == [
        {
            "path": "/app/result.txt",
            "status": "captured",
            "sha256": hashlib.sha256(b"partial\n").hexdigest(),
            "bytes": 8,
            "error": None,
        }
    ]


def test_a_failed_seed_still_captures_the_targets_and_records_begin_error(tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "a.txt").write_text("alpha\n", encoding="utf-8")
    env, calls = FakeEnv(), []
    env.corrupt.add("/app/a.txt")
    env.files["/app/out.txt"] = b"partial\n"
    agent = _agent(
        tmp_path,
        monkeypatch,
        calls,
        environ={continuation.SEED_ENV: str(seed), continuation.CAPTURE_ENV: "out.txt"},
    )

    with pytest.raises(RuntimeError, match="readback"):
        _run(agent, env)

    assert calls == []  # the model never ran
    manifest = json.loads((tmp_path / "logs" / "continuation" / "capture_manifest.json").read_text())
    assert manifest[0] == {
        "path": "/app/out.txt",
        "status": "captured",
        "sha256": hashlib.sha256(b"partial\n").hexdigest(),
        "bytes": 8,
        "error": None,
    }
    assert "RuntimeError" in manifest[-1]["begin_error"]
    assert (tmp_path / "logs" / "continuation" / "capture" / "work" / "out.txt").read_bytes() == b"partial\n"


def test_a_download_that_never_returns_times_out_and_still_writes_the_manifest(tmp_path, monkeypatch):
    class HangingDownloadEnv(FakeEnv):
        async def download_file(self, source_path, target_path):
            self.downloads.append((source_path, str(target_path)))
            await asyncio.Event().wait()  # ignores cancellation deadlines of its own: only wait_for can bound it

    env = HangingDownloadEnv()
    env.files["/app/out.txt"] = b"done\n"
    agent = _agent(
        tmp_path,
        monkeypatch,
        [],
        environ={continuation.CAPTURE_ENV: "out.txt", continuation.CAPTURE_TIMEOUT_ENV: "0.05"},
    )

    started = time.monotonic()
    _run(agent, env)
    assert time.monotonic() - started < 5  # 0.05s per call, not forever

    manifest = json.loads((tmp_path / "logs" / "continuation" / "capture_manifest.json").read_text())
    assert [(row["path"], row["status"], row["sha256"], row["bytes"]) for row in manifest] == [
        ("/app/out.txt", "timeout", None, None)
    ]
    assert "TimeoutError" in manifest[0]["error"]


def test_a_file_that_changes_between_the_two_container_hashes_is_unstable(tmp_path, monkeypatch):
    class MutatingHashEnv(FakeEnv):
        def __init__(self, path):
            super().__init__()
            self.path, self.hashes = path, 0

        async def exec(self, command, cwd=None, env=None, timeout_sec=None):
            if shlex.split(command)[0] == "sha256sum":
                if self.hashes:  # the first hash was taken; the bytes move before the second one
                    self.files[self.path] = b"second\n"
                self.hashes += 1
            return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec)

    env = MutatingHashEnv("/app/out.txt")
    env.files["/app/out.txt"] = b"first\n"
    agent = _agent(tmp_path, monkeypatch, [], environ={continuation.CAPTURE_ENV: "out.txt"})

    _run(agent, env)

    manifest = json.loads((tmp_path / "logs" / "continuation" / "capture_manifest.json").read_text())
    assert manifest[0]["status"] == "unstable"
    assert manifest[0]["sha256"] == hashlib.sha256(b"first\n").hexdigest()
    assert manifest[0]["sha256_before"] == hashlib.sha256(b"first\n").hexdigest()
    assert manifest[0]["sha256_after"] == hashlib.sha256(b"second\n").hexdigest()


def test_absolute_and_workdir_paths_capture_to_different_files(tmp_path, monkeypatch):
    env = FakeEnv()
    env.files["/etc/result.txt"] = b"absolute\n"
    env.files["/app/etc/result.txt"] = b"relative\n"
    agent = _agent(
        tmp_path,
        monkeypatch,
        [],
        environ={continuation.CAPTURE_ENV: "/etc/result.txt, etc/result.txt, /app/etc/result.txt"},
    )

    _run(agent, env)

    manifest = json.loads((tmp_path / "logs" / "continuation" / "capture_manifest.json").read_text())
    rows = {row["path"]: row for row in manifest}
    assert set(rows) == {"/etc/result.txt", "/app/etc/result.txt"}  # the duplicate is captured once
    assert rows["/etc/result.txt"]["status"] == "captured"
    assert rows["/app/etc/result.txt"]["status"] == "captured"
    base = tmp_path / "logs" / "continuation" / "capture"
    assert (base / "abs" / "etc" / "result.txt").read_bytes() == b"absolute\n"
    assert (base / "work" / "etc" / "result.txt").read_bytes() == b"relative\n"
    assert len(env.downloads) == 2

    escaping = _agent(
        tmp_path, monkeypatch, [], environ={continuation.CAPTURE_ENV: "../escape.txt"}
    )
    with pytest.raises(ValueError, match=continuation.CAPTURE_ENV):
        _run(escaping, FakeEnv())

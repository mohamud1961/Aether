"""Continuation runs through the adapter's ``run()``: seed files in, message appended, capture out.

The fake environment is a real directory standing in for the container: every container path is mapped into it
and ``exec`` runs the shell command for real (sha256sum/tar included), so the snapshot is exercised rather than
imitated. A command containing a registered ``hang`` marker never returns.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from types import SimpleNamespace

import pytest

from aether.core import continuation
from aether.core import harbor_agent as adapter

WORKDIR = "/app"


class FakeEnv:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.commands: list[str] = []
        self.uploads: list[tuple[str, str]] = []
        self.downloads: list[tuple[str, str]] = []
        self.corrupt: set[str] = set()
        self.hang: set[str] = set()  # a command containing one of these never returns
        self.mutate: str | None = None  # shell lines inserted once, after the ``mutate_at`` marker
        self.mutate_at: str = continuation.BEFORE_MARK
        self._mutated = False

    def host(self, remote: str) -> Path:
        assert remote.startswith("/"), remote
        return self.root / remote.lstrip("/")

    def put(self, remote: str, data: bytes) -> None:
        path = self.host(remote)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, remote: str) -> bytes:
        return self.host(remote).read_bytes()

    def _mapped(self, command: str) -> str:
        """Container paths are the only quoted absolute paths in a command: map each into this root."""
        script = command.replace(" -C / ", f" -C {shlex.quote(str(self.root))} ")
        return script.replace("'/", f"'{self.root}/")

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        self.commands.append(command)
        if any(marker in command for marker in self.hang):
            await asyncio.Event().wait()
        script = self._mapped(command)
        if self.mutate is not None and not self._mutated and self.mutate_at in script:
            self._mutated = True
            lines = script.splitlines()
            for index, line in enumerate(lines):
                if self.mutate_at in line:
                    lines[index + 1:index + 1] = self.mutate.splitlines()
                    break
            script = "\n".join(lines) + "\n"
        self.host("/tmp").mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(["/bin/sh", "-c", script], capture_output=True, text=True,
                                   timeout=timeout_sec)
        return SimpleNamespace(return_code=completed.returncode, stdout=completed.stdout,
                               stderr=completed.stderr)

    async def upload_file(self, source_path, target_path):
        data = Path(source_path).read_bytes()
        self.uploads.append((str(source_path), target_path))
        self.put(target_path, b"CORRUPTED" if target_path in self.corrupt else data)

    async def download_file(self, source_path, target_path):
        self.downloads.append((source_path, str(target_path)))
        source = self.host(source_path)
        if not source.is_file():
            raise FileNotFoundError(source_path)
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        Path(target_path).write_bytes(source.read_bytes())


class FakeProvider:
    async def aclose(self) -> None:
        return None


def _agent(tmp_path, monkeypatch, calls, *, fail=None, environ=None, extras=None):
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
    agent.logs_dir.mkdir(exist_ok=True)  # Harbor creates the log directory before invoking the adapter.
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
        return SimpleNamespace(status="finished", extras=extras or {})

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


def _manifest(tmp_path) -> dict:
    return json.loads((tmp_path / "logs" / "continuation" / "capture_manifest.json").read_text())


def _rows(manifest: dict) -> dict[str, dict]:
    return {row["remote"]: row for row in manifest["rows"]}


def _capture_dir(tmp_path) -> Path:
    return tmp_path / "logs" / "continuation" / "capture"


def test_unset_settings_leave_the_default_run_unchanged(tmp_path, monkeypatch):
    env, calls = FakeEnv(tmp_path / "container"), []
    _run(_agent(tmp_path, monkeypatch, calls), env)

    assert calls[0]["task"] == "do the task"
    assert env.commands == [] and env.uploads == [] and env.downloads == []
    assert not (tmp_path / "logs" / "continuation").exists()


def test_seed_files_are_uploaded_read_back_and_recorded(tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    (seed / "sub").mkdir(parents=True)
    (seed / "a.txt").write_text("alpha\n", encoding="utf-8")
    (seed / "sub" / "b.bin").write_bytes(b"\x00\x01")
    env = FakeEnv(tmp_path / "container")
    _run(_agent(tmp_path, monkeypatch, [], environ={continuation.SEED_ENV: str(seed)}), env)

    manifest = json.loads((tmp_path / "logs" / "continuation" / "seed_manifest.json").read_text())
    assert manifest == [
        {"path": "/app/a.txt", "sha256": hashlib.sha256(b"alpha\n").hexdigest(), "bytes": 6},
        {"path": "/app/sub/b.bin", "sha256": hashlib.sha256(b"\x00\x01").hexdigest(), "bytes": 2},
    ]
    assert env.get("/app/a.txt") == b"alpha\n"
    assert env.get("/app/sub/b.bin") == b"\x00\x01"
    assert [c for c in env.commands if c.startswith("sha256sum")] == [
        "sha256sum '/app/a.txt'",
        "sha256sum '/app/sub/b.bin'",
    ]


def test_a_corrupted_seed_upload_stops_the_run_before_run_agent(tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "a.txt").write_text("alpha\n", encoding="utf-8")
    env, calls = FakeEnv(tmp_path / "container"), []
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
        FakeEnv(tmp_path / "container"),
    )

    assert calls[0]["task"] == "do the task\n\nFIRST\n\nSECOND"
    manifest = json.loads((tmp_path / "logs" / "continuation" / "message_manifest.json").read_text())
    assert manifest["continue"] == {"path": str(cont), "sha256": hashlib.sha256(b"FIRST").hexdigest(), "chars": 5}
    assert manifest["feedback"] == {"path": str(feedback), "sha256": hashlib.sha256(b"SECOND").hexdigest(),
                                    "chars": 6}
    assert manifest["instruction_sha256"] == hashlib.sha256(b"do the task\n\nFIRST\n\nSECOND").hexdigest()


def test_feedback_without_a_continuation_file_is_refused(tmp_path, monkeypatch):
    feedback = tmp_path / "feedback.txt"
    feedback.write_text("SECOND", encoding="utf-8")
    calls = []
    agent = _agent(tmp_path, monkeypatch, calls, environ={continuation.FEEDBACK_ENV: str(feedback)})

    with pytest.raises(ValueError, match=continuation.CONTINUE_ENV):
        _run(agent, FakeEnv(tmp_path / "container"))
    assert calls == []


def test_capture_writes_files_and_manifest_and_records_a_missing_path(tmp_path, monkeypatch):
    env = FakeEnv(tmp_path / "container")
    env.put("/app/out/result.txt", b"done\n")
    env.put("/app/notes.md", b"# notes\n")
    agent = _agent(
        tmp_path,
        monkeypatch,
        [],
        environ={continuation.CAPTURE_ENV: "/app/out/result.txt, notes.md, /app/missing.txt"},
    )
    _run(agent, env)

    manifest = _manifest(tmp_path)
    assert manifest["version"] == 1 and manifest["workdir"] == "/app"
    assert manifest["cancelled"] is False and manifest["begin_error"] is None
    assert manifest["active_writers"] == []
    assert manifest["snapshot"]["method"] == "tar"
    rows = _rows(manifest)
    assert rows["/app/out/result.txt"] == {
        "remote": "/app/out/result.txt",
        "local": "work/out/result.txt",
        "target": "out/result.txt",
        "status": "captured",
        "sha256": hashlib.sha256(b"done\n").hexdigest(),
        "bytes": 5,
        "error": None,
    }
    assert rows["/app/notes.md"]["status"] == "captured"
    assert rows["/app/notes.md"]["target"] == "notes.md"
    assert rows["/app/missing.txt"]["status"] == "missing"
    assert rows["/app/missing.txt"]["sha256"] is None and rows["/app/missing.txt"]["bytes"] is None
    assert manifest["complete"] is False  # a target is missing
    assert manifest["snapshot"]["sha256_before"] is None  # no digest over an incomplete set
    assert (_capture_dir(tmp_path) / "work" / "out" / "result.txt").read_bytes() == b"done\n"
    assert (_capture_dir(tmp_path) / "work" / "notes.md").read_bytes() == b"# notes\n"
    assert not (_capture_dir(tmp_path) / "work" / "missing.txt").exists()
    assert len(env.downloads) == 1  # one archive, not one download per file


def test_a_complete_capture_records_matching_snapshot_hashes(tmp_path, monkeypatch):
    env = FakeEnv(tmp_path / "container")
    env.put("/app/out.txt", b"done\n")
    agent = _agent(tmp_path, monkeypatch, [], environ={continuation.CAPTURE_ENV: "out.txt"})
    _run(agent, env)

    manifest = _manifest(tmp_path)
    assert manifest["complete"] is True
    assert manifest["snapshot"]["sha256_before"] == manifest["snapshot"]["sha256_after"]
    assert len(manifest["snapshot"]["sha256_before"]) == 64
    assert _rows(manifest)["/app/out.txt"]["status"] == "captured"


def test_capture_still_runs_when_the_agent_raised(tmp_path, monkeypatch):
    env = FakeEnv(tmp_path / "container")
    env.put("/app/result.txt", b"partial\n")
    agent = _agent(
        tmp_path,
        monkeypatch,
        [],
        fail=RuntimeError("agent failed"),
        environ={continuation.CAPTURE_ENV: "result.txt"},
    )

    with pytest.raises(RuntimeError, match="agent failed"):
        _run(agent, env)

    manifest = _manifest(tmp_path)
    assert manifest["complete"] is True
    assert _rows(manifest)["/app/result.txt"]["status"] == "captured"


def test_left_running_processes_make_the_capture_incomplete(tmp_path, monkeypatch):
    env = FakeEnv(tmp_path / "container")
    env.put("/app/out.txt", b"done\n")
    agent = _agent(
        tmp_path,
        monkeypatch,
        [],
        environ={continuation.CAPTURE_ENV: "out.txt"},
        extras={"left_running": ["4242 sleep 300"]},
    )
    _run(agent, env)

    manifest = _manifest(tmp_path)
    assert manifest["active_writers"] == ["4242 sleep 300"]
    assert manifest["complete"] is False
    assert _rows(manifest)["/app/out.txt"]["status"] == "captured"  # recorded, never killed


def test_a_failed_seed_still_captures_the_targets_and_records_begin_error(tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "a.txt").write_text("alpha\n", encoding="utf-8")
    env, calls = FakeEnv(tmp_path / "container"), []
    env.corrupt.add("/app/a.txt")
    env.put("/app/out.txt", b"partial\n")
    agent = _agent(
        tmp_path,
        monkeypatch,
        calls,
        environ={continuation.SEED_ENV: str(seed), continuation.CAPTURE_ENV: "out.txt"},
    )

    with pytest.raises(RuntimeError, match="readback"):
        _run(agent, env)

    assert calls == []  # the model never ran
    manifest = _manifest(tmp_path)
    assert "RuntimeError" in manifest["begin_error"]
    assert manifest["complete"] is False
    assert _rows(manifest)["/app/out.txt"]["status"] == "captured"
    assert (_capture_dir(tmp_path) / "work" / "out.txt").read_bytes() == b"partial\n"


def test_a_snapshot_that_never_returns_times_out_and_still_writes_the_manifest(tmp_path, monkeypatch):
    env = FakeEnv(tmp_path / "container")
    env.put("/app/out.txt", b"done\n")
    env.hang.add(continuation.BEFORE_MARK)
    agent = _agent(
        tmp_path,
        monkeypatch,
        [],
        environ={continuation.CAPTURE_ENV: "out.txt", continuation.CAPTURE_TIMEOUT_ENV: "0.05"},
    )

    _run(agent, env)

    manifest = _manifest(tmp_path)
    assert [(row["remote"], row["status"], row["sha256"], row["bytes"]) for row in manifest["rows"]] == [
        ("/app/out.txt", "timeout", None, None)
    ]
    assert "TimeoutError" in manifest["rows"][0]["error"]


def test_a_file_that_moves_during_the_snapshot_is_unstable(tmp_path, monkeypatch):
    env = FakeEnv(tmp_path / "container")
    env.put("/app/out.txt", b"first\n")
    env.mutate_at = continuation.AFTER_MARK  # moves after the tar, so the extracted bytes still match the before hash
    env.mutate = f"printf 'second\\n' > {shlex.quote(str(env.host('/app/out.txt')))}"
    agent = _agent(tmp_path, monkeypatch, [], environ={continuation.CAPTURE_ENV: "out.txt"})

    _run(agent, env)

    manifest = _manifest(tmp_path)
    row = _rows(manifest)["/app/out.txt"]
    assert row["status"] == "unstable"
    assert "snapshot hashes disagree" in row["error"]
    assert manifest["complete"] is False
    assert manifest["snapshot"]["sha256_before"] != manifest["snapshot"]["sha256_after"]
    assert not (_capture_dir(tmp_path) / "work" / "out.txt").exists()


def test_absolute_and_workdir_paths_capture_to_different_files(tmp_path, monkeypatch):
    env = FakeEnv(tmp_path / "container")
    env.put("/etc/result.txt", b"absolute\n")
    env.put("/app/etc/result.txt", b"relative\n")
    agent = _agent(
        tmp_path,
        monkeypatch,
        [],
        environ={continuation.CAPTURE_ENV: "/etc/result.txt, etc/result.txt, /app/etc/result.txt"},
    )

    _run(agent, env)

    manifest = _manifest(tmp_path)
    rows = _rows(manifest)
    assert set(rows) == {"/etc/result.txt", "/app/etc/result.txt"}  # the duplicate is captured once
    assert rows["/etc/result.txt"]["target"] is None and rows["/etc/result.txt"]["local"] == "abs/etc/result.txt"
    assert rows["/app/etc/result.txt"]["target"] == "etc/result.txt"
    base = _capture_dir(tmp_path)
    assert (base / "abs" / "etc" / "result.txt").read_bytes() == b"absolute\n"
    assert (base / "work" / "etc" / "result.txt").read_bytes() == b"relative\n"

    escaping = _agent(tmp_path, monkeypatch, [], environ={continuation.CAPTURE_ENV: "../escape.txt"})
    with pytest.raises(ValueError, match=continuation.CAPTURE_ENV):
        _run(escaping, FakeEnv(tmp_path / "other"))

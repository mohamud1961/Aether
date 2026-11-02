"""Real local filesystem checks for Core's bounded state observations."""

import asyncio
import json
import os
import shlex
import sys
from types import SimpleNamespace

from aether.core import facts_probe
from aether.core.facts import Facts
from tests.core_fakes import LocalEnv


def _state(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    env = LocalEnv(work)
    monkeypatch.setattr(facts_probe, "COMMANDS", ("sh",))
    monkeypatch.setattr(facts_probe, "LANGUAGES", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),), raising=False)
    state = Facts(env, str(work), lambda: 100, lambda *_args, **_kwargs: None, hosts=())
    return state, work


class OutageEnv(LocalEnv):
    fail_probe = False

    async def exec(self, command, **kwargs):
        if self.fail_probe and "AETHER_FACTS_V1" in command:
            return SimpleNamespace(return_code=1, stdout="", stderr="unavailable")
        return await super().exec(command, **kwargs)


def test_external_change_before_a_read_only_action_is_visible(tmp_path, monkeypatch):
    state, work = _state(tmp_path, monkeypatch)

    async def run():
        await state.start()
        (work / "report.txt").write_text("created by another process")
        update = await state.after_action(1, "read_file", {"path": "existing.txt"}, "read result")
        assert "report.txt" in update and "step 1" in update
        assert await state.after_action(2, "read_file", {"path": "existing.txt"}, "read result") == ""

    asyncio.run(run())


def test_default_observation_does_not_read_unclassified_file_contents(tmp_path, monkeypatch):
    import pytest

    state, work = _state(tmp_path, monkeypatch)
    candidate = work / "ordinary.txt"
    candidate.write_text("synthetic private data")
    mtime = candidate.stat().st_mtime_ns
    os.utime(candidate, ns=(1, mtime))
    candidate.read_bytes()
    if candidate.stat().st_atime_ns == 1:
        pytest.skip("filesystem does not provide a usable read-access-time signal")
    os.utime(candidate, ns=(1, mtime))

    async def run():
        await state.start()
        await state.after_action(1, "terminal", {"input": "cat ordinary.txt"}, "synthetic output")
        assert candidate.stat().st_atime_ns == 1
        assert state.record()["bindings"] == {}

    asyncio.run(run())


def test_mentioned_file_fingerprint_changes_once_but_touch_and_unrelated_files_do_not(tmp_path, monkeypatch):
    state, work = _state(tmp_path, monkeypatch)
    state.allow_fingerprints = True  # synthetic key-free fixture only
    program = work / "solver.py"
    program.write_text("original\n")

    async def run():
        await state.start()
        await state.after_action(1, "terminal", {"input": "python solver.py"}, "output")
        before = program.stat()
        os.utime(program, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
        touched = await state.after_action(2, "read_file", {"path": "else.txt"}, "output")
        assert "fingerprint" not in touched
        (work / "unrelated.txt").write_text("unrelated")
        unrelated = await state.after_action(3, "terminal", {"input": "true"}, "output")
        assert "solver.py" not in unrelated or "fingerprint" not in unrelated
        program.write_text("changed\n")
        changed = await state.after_action(4, "read_file", {"path": "else.txt"}, "output")
        assert "solver.py" in changed and "fingerprint" in changed and "step 1" in changed and "step 4" in changed
        assert "solver.py" not in await state.after_action(5, "read_file", {}, "output")

    asyncio.run(run())


def test_linked_or_protected_files_are_not_read_or_claimed_as_tracked(tmp_path, monkeypatch):
    state, work = _state(tmp_path, monkeypatch)
    state.allow_fingerprints = True  # synthetic key-free fixture only
    (work / "tests").mkdir()
    (work / "private-key.pem").write_text("synthetic canary, not a real key")
    outside = tmp_path / "outside.py"
    outside.write_text("external content")
    (work / "linked.py").symlink_to(outside)
    (work / "safe.py").write_text("safe")

    async def run():
        initial = await state.start()
        await state.after_action(1, "terminal", {"input": "cat linked.py private-key.pem safe.py"}, "output")
        record = state.record()
        rendered = json.dumps(record) + initial
        assert "private-key.pem" not in rendered
        assert "synthetic canary" not in rendered and "external content" not in rendered
        assert record["workspace"]["complete"] is False
        assert "linked.py" not in record["bindings"]

    asyncio.run(run())


def test_unavailable_workspace_observer_does_not_assert_unchanged(tmp_path, monkeypatch):
    state, _work = _state(tmp_path, monkeypatch)
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", ("/does/not/exist",), raising=False)

    async def run():
        initial = await state.start()
        assert "workspace" in initial.lower() and "unmeasured" in initial.lower()
        assert state.record()["workspace"]["status"] == "unknown"

    asyncio.run(run())


def test_later_probe_outage_invalidates_current_state_without_fabricating_recovery(tmp_path, monkeypatch):
    state, work = _state(tmp_path, monkeypatch)
    state.allow_fingerprints = True  # synthetic key-free fixture only
    state.env = OutageEnv(work)
    program = work / "solver.py"
    program.write_text("original\n")

    async def run():
        await state.start()
        await state.after_action(1, "terminal", {"input": "python solver.py"}, "output")
        assert state.record()["bindings"]["solver.py"]["status"] == "observed"
        state.env.fail_probe = True
        failed = await state.after_action(2, "read_file", {}, "output")
        assert "unmeasured" in failed
        assert state.record()["workspace"]["status"] == "unknown"
        assert state.record()["bindings"]["solver.py"]["status"] == "unknown"
        program.write_text("changed during outage\n")
        state.env.fail_probe = False
        recovered = await state.after_action(3, "read_file", {}, "output")
        assert "observed again" in recovered
        assert "fingerprint differs" not in recovered
        initial_change = state.record()["initial_workspace_changes"]
        assert initial_change == [{"path": "solver.py", "first_observed_step": 3, "kind": "metadata_changed"}]

    asyncio.run(run())


def test_replaced_workspace_is_not_confused_with_the_old_one(tmp_path, monkeypatch):
    state, work = _state(tmp_path, monkeypatch)
    state.allow_fingerprints = True  # synthetic key-free fixture only
    (work / "solver.py").write_text("original\n")

    async def run():
        await state.start()
        await state.after_action(1, "terminal", {"input": "python solver.py"}, "output")
        work.rename(tmp_path / "old-work")
        work.mkdir()
        (work / "solver.py").write_text("different workspace\n")
        update = await state.after_action(2, "read_file", {}, "output")
        assert "workspace root identity changed" in update.lower()
        assert "fingerprint differs" not in update
        assert state.record()["initial_workspace_changes"] == []

    asyncio.run(run())


def test_incomplete_scan_does_not_claim_initial_file_was_removed(tmp_path, monkeypatch):
    state, work = _state(tmp_path, monkeypatch)
    initial = work / "source.txt"
    initial.write_text("ordinary data")
    outside = tmp_path / "outside.txt"
    outside.write_text("external data")

    async def run():
        await state.start()
        initial.unlink()
        initial.symlink_to(outside)
        update = await state.after_action(1, "read_file", {}, "output")
        assert state.record()["workspace"]["complete"] is False
        assert state.record()["initial_workspace_changes"] == []
        assert "external data" not in update

    asyncio.run(run())


def test_workspace_observer_does_not_execute_interpreter_through_linked_parent(tmp_path, monkeypatch):
    state, work = _state(tmp_path, monkeypatch)
    bindir = work / "bin"
    bindir.mkdir()
    marker = work / "fake-interpreter-ran"
    executable = bindir / "fakepython"
    executable.write_text(f"#!/bin/sh\nprintf touched > {shlex.quote(str(marker))}\n")
    executable.chmod(0o755)
    link = tmp_path / "linked-bin"
    link.symlink_to(bindir, target_is_directory=True)
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (str(link / "fakepython"),))
    asyncio.run(state.start())
    assert not marker.exists()
    assert state.record()["workspace"]["status"] == "unknown"


def test_hardlinked_external_file_never_becomes_a_fingerprinted_binding(tmp_path, monkeypatch):
    state, work = _state(tmp_path, monkeypatch)
    state.allow_fingerprints = True  # synthetic key-free fixture only
    external = tmp_path / "external.py"
    external.write_text("synthetic external contents")
    os.link(external, work / "shared.py")

    async def run():
        await state.start()
        await state.after_action(1, "terminal", {"input": "cat shared.py"}, "output")
        record = state.record()
        assert "shared.py" not in record["bindings"]
        assert record["workspace"]["complete"] is False
        assert "synthetic external contents" not in json.dumps(record)

    asyncio.run(run())

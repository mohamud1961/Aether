"""Provider-free state transitions using the real probe and synthetic task files."""

import asyncio
import json
import shlex

from aether.core import facts_probe
from aether.core.facts import Facts
from tests.core_fakes import LocalEnv


class ScopedEnv(LocalEnv):
    def __init__(self, root, bindir):
        super().__init__(root)
        self.bindir = bindir
        self.fail_probe = False

    async def exec(self, command, **kwargs):
        if self.fail_probe and "AETHER_FACTS_V1" in command:
            raise TimeoutError("synthetic observer outage")
        command = f"PATH={shlex.quote(str(self.bindir))}:/usr/bin:/bin; export PATH\n" + command
        return await super().exec(command, **kwargs)


def _setup(tmp_path, monkeypatch, terminal=None):
    work = tmp_path / "work"
    work.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setattr(facts_probe, "COMMANDS", ("afprobe",))
    monkeypatch.setattr(facts_probe, "LANGUAGES", ())
    rows = []
    env = ScopedEnv(work, bindir)
    state = Facts(env, str(work), lambda: 100, lambda event, **data: rows.append((event, data)),
                  terminal_state=terminal, hosts=())
    return state, env, work, bindir, rows


def test_added_and_removed_command_updates_once_while_stable_state_is_silent(tmp_path, monkeypatch):
    state, _env, _work, bindir, rows = _setup(tmp_path, monkeypatch)

    async def exercise():
        initial = await state.start()
        assert "afprobe" in initial and "not resolved" in initial
        executable = bindir / "afprobe"
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        added = await state.after_action(1, "terminal", {"input": "true"}, "(no new output)")
        assert "afprobe" in added and "Shared PATH" in added
        assert await state.after_action(2, "terminal", {"input": "true"}, "(no new output)") == ""
        executable.unlink()
        removed = await state.after_action(3, "terminal", {"input": "true"}, "(no new output)")
        assert "afprobe=not resolved" in removed
        assert len(rows) == 4

    asyncio.run(exercise())


def test_failed_probe_becomes_unknown_then_recovery_is_visible(tmp_path, monkeypatch):
    state, env, _work, _bindir, _rows = _setup(tmp_path, monkeypatch)

    async def exercise():
        await state.start()
        env.fail_probe = True
        first = await state.after_action(1, "terminal", {"input": "true"}, "output")
        assert "unmeasured" in first and not state.record()["shared_known"]
        assert await state.after_action(2, "terminal", {"input": "true"}, "output") == ""
        env.fail_probe = False
        restored = await state.after_action(3, "terminal", {"input": "true"}, "output")
        assert "observed again" in restored and state.record()["shared_known"]

    asyncio.run(exercise())


def test_first_failed_probe_then_recovery_presents_actual_fields(tmp_path, monkeypatch):
    state, env, _work, _bindir, _rows = _setup(tmp_path, monkeypatch)
    env.fail_probe = True

    async def exercise():
        assert "unmeasured" in await state.start()
        env.fail_probe = False
        restored = await state.after_action(1, "terminal", {"input": "true"}, "output")
        assert "Shared probe PATH at step 1" in restored
        assert "afprobe" in restored

    asyncio.run(exercise())


def test_direct_file_write_is_not_repeated_as_independent_change(tmp_path, monkeypatch):
    state, _env, work, _bindir, _rows = _setup(tmp_path, monkeypatch)

    async def exercise():
        await state.start()
        (work / "answer.txt").write_text("authored")
        update = await state.after_action(1, "write_file", {"path": "answer.txt"}, "wrote 8 bytes")
        assert "answer.txt" not in update
        assert "answer.txt" in state.record()["snapshot"]["files"]

    asyncio.run(exercise())


def test_failed_file_write_does_not_hide_an_observed_change(tmp_path, monkeypatch):
    state, _env, work, _bindir, _rows = _setup(tmp_path, monkeypatch)

    async def exercise():
        await state.start()
        (work / "answer.txt").write_text("appeared while the write failed")
        update = await state.after_action(1, "write_file", {"path": "answer.txt"}, "error: write failed")
        assert "answer.txt" in update

    asyncio.run(exercise())


def test_named_terminal_observations_are_separate_and_lost_visibility_is_unknown(tmp_path, monkeypatch):
    sessions = {}
    state, _env, _work, _bindir, _rows = _setup(tmp_path, monkeypatch, terminal=sessions.get)

    def terminal(value):
        return {"command_resolution": {"status": "observed", "resolved": {"afprobe": value}}}

    async def exercise():
        await state.start()
        sessions["alpha"] = terminal(True)
        sessions["beta"] = terminal(False)
        alpha = await state.after_action(1, "terminal", {"name": "alpha", "input": "true"}, "output")
        assert 'Terminal "alpha"' in alpha and "afprobe=resolved" in alpha
        beta = await state.after_action(2, "terminal", {"name": "beta", "input": "true"}, "output")
        assert 'Terminal "alpha"' not in beta
        sessions["alpha"] = {"command_resolution": {"status": "unknown"}}
        lost = await state.after_action(3, "terminal", {"name": "alpha", "input": "true"}, "output")
        assert 'Terminal "alpha"' in lost and "unmeasured" in lost
        sessions["alpha"] = terminal(True)
        resumed = await state.after_action(4, "terminal", {"name": "alpha", "input": "true"}, "output")
        assert 'Terminal "alpha"' in resumed and "observed again" in resumed
        assert state.record()["terminal_paths"]["beta"] == {"afprobe": False}

    asyncio.run(exercise())


def test_finish_only_records_late_change_without_extra_instruction(tmp_path, monkeypatch):
    state, _env, work, _bindir, _rows = _setup(tmp_path, monkeypatch)

    async def exercise():
        await state.start()
        (work / "output.txt").write_text("later")
        assert await state.after_action(1, "finish", {}, "done") == ""
        assert "output.txt" in json.dumps(state.record()["finish_observations_not_shown"])

    asyncio.run(exercise())

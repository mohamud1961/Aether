"""Provider-free state transitions using the real probe and synthetic task files."""

import asyncio
import hashlib
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


def test_failed_observation_on_unrestored_continuation_does_not_invent_baseline(tmp_path, monkeypatch):
    state, env, _work, _bindir, _rows = _setup(tmp_path, monkeypatch)
    state.initial_workspace.prepare_resume()
    env.fail_probe = True

    async def exercise():
        note = await state.start()
        assert "continuation baseline is unmeasured" in note
        assert state.record()["initial_workspace"]["status"] == "unknown"
        assert state.record()["initial_workspace"]["scope"] == "continuation_start"

    asyncio.run(exercise())


def test_full_environment_refresh_replaces_memory_observation_and_handles_unknown(tmp_path, monkeypatch):
    state, _env, _work, _bindir, _rows = _setup(tmp_path, monkeypatch)
    actual_probe = facts_probe.probe
    measurements = iter((100, 50, None))

    async def measured(*args, **kwargs):
        result = await actual_probe(*args, **kwargs)
        if result["ok"] and kwargs["full"]:
            result["facts"]["host_available_memory_kib"] = next(measurements)
        return result

    monkeypatch.setattr(facts_probe, "probe", measured)

    async def exercise():
        assert "100 KiB" in await state.start()
        changed = await state.after_action(1, "terminal", {"input": "pip --version"}, "output")
        assert "50 KiB" in changed and "step 1" in changed
        assert "50 KiB" in state.context_summary()
        unavailable = await state.after_action(2, "terminal", {"input": "pip --version"}, "output")
        assert "unmeasured" in unavailable and "step 2" in unavailable
        assert "100 KiB" not in state.context_summary() and "50 KiB" not in state.context_summary()

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


def test_tool_receipts_bind_only_to_the_post_action_observation(tmp_path, monkeypatch):
    state, _env, _work, _bindir, _rows = _setup(tmp_path, monkeypatch)

    async def exercise():
        await state.start()
        await state.after_action(1, "read_file", {"path": "sample.txt"}, "sample output", call_id="c1")
        await state.after_action(2, "finish", {}, "done", call_id="c2")
        events = state.record()["events"]
        assert [row["step"] for row in events] == [1, 2]
        assert events[0]["call_id"] == "c1"
        assert events[0]["tool_output_sha256"] == hashlib.sha256(b"sample output").hexdigest()
        assert "after action" in events[0]["state_scope"]
        assert "sample output" not in json.dumps(events)

    asyncio.run(exercise())


def test_prior_tool_observation_can_be_compared_with_the_current_bounded_state(tmp_path, monkeypatch):
    state, env, work, _bindir, _rows = _setup(tmp_path, monkeypatch)
    source = work / "source.txt"
    source.write_text("first\n")

    async def exercise():
        await state.start()
        await state.after_action(1, "read_file", {"path": "source.txt"}, "first\n", call_id="c1")
        initial = state.observation_state("c1")
        assert initial["status"] == "sample_matches" and initial["observation_step"] == 1
        assert "not proof" in initial["scope"]

        # Hidden files are outside the sample: a matching sample must not be
        # presented as evidence that the entire environment is unchanged.
        (work / ".hidden").write_text("outside the observed sample\n")
        await state.after_action(2, "terminal", {"input": "true"}, "ok", call_id="c2")
        partial = state.observation_state("c1")
        assert partial["status"] == "sample_matches" and partial["latest_complete"] is False

        source.write_text("second version\n")
        await state.after_action(3, "terminal", {"input": "true"}, "ok", call_id="c3")
        assert state.observation_state("c1")["status"] == "sample_differs"
        env.fail_probe = True
        await state.after_action(4, "terminal", {"input": "true"}, "ok", call_id="c4")
        assert state.observation_state("c1")["status"] == "unknown"
        env.fail_probe = False
        await state.after_action(5, "terminal", {"input": "true"}, "ok", call_id="c1")
        assert state.observation_state("c1")["reason"] == "missing_or_ambiguous_call_id"
        assert state.observation_state("c1", step=1)["status"] == "sample_differs"
        assert state.observation_state("missing")["status"] == "unknown"
        for index in range(129):
            state._record_event(6 + index, "read_file", f"extra_{index}", "")
        state.last_shared_step = 134  # The synthetic receipts use this same observed snapshot.
        assert state.observation_state("extra_128")["reason"] == "history_truncated"
        assert state.observation_state("extra_128", step=134)["status"] == "sample_matches"
        assert state.record()["recent_observation_states"][-1]["status"] == "sample_matches"
        assert state.observation_state("extra_0", step=6)["status"] == "unknown"
        state._record_event(1, "read_file", "out_of_order", "")
        assert state.observation_state("extra_128", step=134)["reason"] == "non_monotonic_steps"

    asyncio.run(exercise())

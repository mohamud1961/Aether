"""Real Core loop, real local shell, scripted provider: no model or cloud calls."""

import asyncio
import dataclasses
import json
import os
import shlex
import sys
from types import SimpleNamespace

from aether.core import facts_probe
from aether.core.loop import CoreConfig, Trace, run_agent
from tests.core_fakes import LocalEnv
from tests.test_core_responses import ResponsesClient, provider, turn_events


class SharedPathEnv(LocalEnv):
    def __init__(self, work, bindir, *, fail_probe=False):
        super().__init__(work)
        self.bindir = bindir
        self.fail_probe = fail_probe

    async def exec(self, command, **kwargs):
        if self.fail_probe and "AETHER_FACTS_V1" in command:
            return SimpleNamespace(return_code=1, stdout="", stderr="observer unavailable")
        command = f"PATH={shlex.quote(str(self.bindir))}:/usr/bin:/bin; export PATH\n" + command
        return await super().exec(command, **kwargs)


def _setup(tmp_path, monkeypatch, commands):
    work = tmp_path / "work"
    work.mkdir()
    bindir = work / "bin"
    bindir.mkdir()
    monkeypatch.setattr(facts_probe, "COMMANDS", commands)
    monkeypatch.setattr(facts_probe, "LANGUAGES", ())
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    return work, bindir


def _run(tmp_path, work, env, calls):
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}"))
        for i, (name, args) in enumerate(calls, 1)
    ])
    result = asyncio.run(run_agent(
        env=env, task="Observe the working environment.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(tmp_path / "ctl"), end_processes="stop",
                          managed_facts=True),
    ))
    return result, client


def _private_clm_config(tmp_path, **kwargs):
    from tests.test_core_v2 import _clm_config

    config = _clm_config(tmp_path, **kwargs)
    return dataclasses.replace(
        config, clm=dataclasses.replace(config.clm, history_path=str(tmp_path / "ctx" / "HISTORY.txt")),
    )


def test_facts_are_separate_from_the_task_and_changes_reach_next_request(tmp_path, monkeypatch):
    work, bindir = _setup(tmp_path, monkeypatch, ("afprobe",))
    calls = [
        ("terminal", {"input": "printf '#!/bin/sh\\nexit 0\\n' > bin/afprobe; chmod +x bin/afprobe"}),
        ("finish", {"summary": "done"}),
    ]
    result, client = _run(tmp_path, work, SharedPathEnv(work, bindir), calls)
    assert result.status == "finished"
    initial = client.requests[0]["input"]
    task = next(item for item in initial if item.get("role") == "user"
                and "Observe the working environment." in item.get("content", ""))
    assert "[core facts]" not in task["content"]
    facts = [item["content"] for item in initial if item.get("role") == "user"
             and item.get("content", "").startswith("[core facts]")]
    assert len(facts) == 1 and "afprobe" in facts[0] and "not resolved" in facts[0]
    output = next(item["output"] for item in client.requests[1]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c1")
    assert "[core facts]" in output and "afprobe" in output and "Shared PATH" in output
    assert len(client.requests) == 2  # The facts mechanism did not add a model turn.
    assert result.extras["core_facts"]["last_shared_step"] >= 1


def test_harbor_configuration_enables_the_state_service_in_a_real_loop(tmp_path, monkeypatch):
    import pytest

    from aether.core.harbor_agent import ConfigError, build_config
    from tests.test_core_start_copy import BASE

    work, bindir = _setup(tmp_path, monkeypatch, ("sh",))
    settings = {**BASE, "AETHER_CORE_CONTEXT": "project", "AETHER_CORE_START_COPY": "off",
                "AETHER_CORE_MANAGED_FACTS": "on"}
    config = dataclasses.replace(build_config(environ=settings), control_dir=str(tmp_path / "ctl"),
                                 end_processes="stop")
    client = ResponsesClient([turn_events(1, call=("finish", {"summary": "done"}, "c1"))])
    result = asyncio.run(run_agent(
        env=SharedPathEnv(work, bindir), task="Observe the environment.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"), config=config,
    ))
    assert result.status == "finished"
    assert any(isinstance(item.get("content"), str) and item["content"].startswith("[core facts]\n")
               for item in client.requests[0]["input"])
    with pytest.raises(ConfigError):
        build_config(environ={**settings, "AETHER_CORE_MANAGED_FACTS": "invalid"})
    with pytest.raises(ValueError):
        build_config(environ={**settings, "AETHER_CORE_ENV_BRIEF": "on"})


def test_resolved_command_paths_are_grouped_without_losing_names(tmp_path, monkeypatch):
    import tempfile
    from pathlib import Path

    work, _ = _setup(tmp_path, monkeypatch, ("afprobe", "bfprobe", "missingprobe"))
    # macOS resolves pytest's temporary path through /private; that name is
    # deliberately withheld by the path privacy filter. Use an owned /tmp
    # path to exercise the observable-path contract separately.
    with tempfile.TemporaryDirectory(prefix="codex-facts-path-", dir="/tmp") as safe_bin:
        bindir = Path(safe_bin)
        for name in ("afprobe", "bfprobe"):
            path = bindir / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        result, client = _run(tmp_path, work, SharedPathEnv(work, bindir), [("finish", {"summary": "done"})])
        assert result.status == "finished"
        note = next(item["content"] for item in client.requests[0]["input"] if item.get("role") == "user"
                    and isinstance(item.get("content"), str) and item["content"].startswith("[core facts]\n"))
        assert f"{json.dumps(str(bindir))}: afprobe, bfprobe" in note
        assert "Names not resolved on that PATH: missingprobe." in note
        assert "step 0" in note


def test_project_context_refreshes_the_pinned_state_after_environment_change(tmp_path, monkeypatch):
    work, bindir = _setup(tmp_path, monkeypatch, ("afprobe",))
    result, client = _run(tmp_path, work, SharedPathEnv(work, bindir), [
        ("terminal", {"input": "printf '#!/bin/sh\\nexit 0\\n' > bin/afprobe; chmod +x bin/afprobe"}),
        ("finish", {"summary": "done"}),
    ])
    assert result.status == "finished"

    def initial_note(request):
        return next(item["content"] for item in request["input"] if item.get("role") == "user"
                    and isinstance(item.get("content"), str) and item["content"].startswith("[core facts]\n"))

    assert "Names not resolved on that PATH: afprobe." in initial_note(client.requests[0])
    assert "Names not resolved on that PATH: none." in initial_note(client.requests[1])


def test_project_fork_resume_refreshes_its_own_note_and_keeps_task(tmp_path, monkeypatch):
    import pickle

    from aether.core import fork

    work, bindir = _setup(tmp_path, monkeypatch, ("afprobe",))
    task = "[core facts]\nThis text is part of the task."
    checkpoint = {}
    source = work / "source.txt"
    source.write_text("original\n")

    async def capture(session):
        checkpoint["history"] = fork.continued(session, "Continue working.")
        return "finished", True

    monkeypatch.setattr(fork, "at_finish", capture)

    def run(resume, name, *, make_fork, current_work=work, current_bin=bindir):
        client = ResponsesClient([turn_events(1, call=("finish", {"summary": "done"}, "c1"))])
        config = CoreConfig(control_dir=str(tmp_path / f"ctl-{name}"), end_processes="stop",
                            managed_facts=True, fork=make_fork)
        result = asyncio.run(run_agent(
            env=SharedPathEnv(current_work, current_bin), task=task, workdir=str(current_work),
            provider=provider(client, tmp_path / f"calls-{name}"), timeout_s=600,
            trace=Trace(tmp_path / f"trace-{name}.jsonl"), config=config, resume=resume,
        ))
        assert result.status == "finished"
        return result, client.requests[0]["input"]

    original_result, _ = run(None, "first", make_fork=True)
    assert original_result.extras["core_facts"]["initial_workspace"]["scope"] == "run_start"
    (bindir / "afprobe").write_text("#!/bin/sh\nexit 0\n")
    (bindir / "afprobe").chmod(0o755)
    source.write_text("changed before continuation\n")
    resumed_result, resumed = run(checkpoint["history"], "resumed", make_fork=False)
    state = resumed_result.extras["core_facts"]
    assert state["initial_workspace"]["scope"] == "run_start"
    assert any(x["path"] == "source.txt" and x["first_observed_step"] == 0
               for x in state["initial_workspace_changes"])
    assert any(item.get("content", "").startswith(task) for item in resumed if item.get("role") == "user")
    notes = [item["content"] for item in resumed if item.get("role") == "user"
             and isinstance(item.get("content"), str) and item["content"].startswith("[core facts]\n")
             and "Shared probe PATH" in item["content"]]
    assert len(notes) == 1 and "Names not resolved on that PATH: none." in notes[0]
    assert "source.txt" in notes[0] and "continuation 1 step 0" in notes[0]

    restored_history = pickle.loads(pickle.dumps(checkpoint["history"]))
    restored_result, _ = run(restored_history, "restored", make_fork=False)
    assert restored_result.extras["core_facts"]["initial_workspace"]["scope"] == "run_start"

    import shutil

    cloned_work = tmp_path / "clone"
    shutil.copytree(work, cloned_work)
    cloned_result, cloned = run(checkpoint["history"], "clone", make_fork=False,
                                current_work=cloned_work, current_bin=cloned_work / "bin")
    cloned_state = cloned_result.extras["core_facts"]
    assert cloned_state["initial_workspace"]["scope"] == "continuation_start"
    assert cloned_state["initial_workspace_changes"] == []
    cloned_note = next(item["content"] for item in cloned if item.get("role") == "user"
                       and isinstance(item.get("content"), str) and "Shared probe PATH" in item["content"])
    assert "original starting state was not retained" in cloned_note


def test_terminal_path_observation_belongs_to_the_named_session(tmp_path, monkeypatch):
    work, bindir = _setup(tmp_path, monkeypatch, ("afprobe",))
    (bindir / "afprobe").write_text("#!/bin/sh\nexit 0\n")
    (bindir / "afprobe").chmod(0o755)
    calls = [
        ("terminal", {"name": "alpha", "input": 'export PATH=/usr/bin:/bin; true'}),
        ("terminal", {"name": "beta", "input": "true"}),
        ("finish", {"summary": "done"}),
    ]
    result, client = _run(tmp_path, work, SharedPathEnv(work, bindir), calls)
    assert result.status == "finished"
    alpha = next(item["output"] for item in client.requests[1]["input"]
                 if item.get("type") == "function_call_output" and item.get("call_id") == "c1")
    assert 'Terminal "alpha" PATH' in alpha and "afprobe=not resolved" in alpha
    beta = next(item["output"] for item in client.requests[2]["input"]
                if item.get("type") == "function_call_output" and item.get("call_id") == "c2")
    assert 'Terminal "alpha"' not in beta
    terminal_paths = result.extras["core_facts"]["terminal_paths"]
    assert terminal_paths["alpha"]["afprobe"] is False
    assert terminal_paths["beta"]["afprobe"] is True
    sessions = result.extras["core_facts"]["terminal_sessions"]
    assert sessions["alpha"]["foreground"] == "idle_at_last_observation"
    assert sessions["alpha"]["last_observed_cwd"] == str(work)


def test_running_terminal_does_not_present_previous_cwd_as_current(tmp_path, monkeypatch):
    work, bindir = _setup(tmp_path, monkeypatch, ("sh",))
    result, client = _run(tmp_path, work, SharedPathEnv(work, bindir), [
        ("terminal", {"input": "mkdir -p before after; cd before"}),
        ("terminal", {"input": "cd ../after; sleep 3", "wait_s": 0.2}),
        ("terminal", {"input": "", "wait_s": 10}),
        ("finish", {"summary": "done"}),
    ])
    assert result.status == "finished"

    def note(request):
        return next(item["content"] for item in request["input"] if item.get("role") == "user"
                    and isinstance(item.get("content"), str)
                    and item["content"].startswith("[core facts]\n"))

    pending = note(client.requests[2])
    assert "completion_not_observed" in pending
    assert str(work / "before") in pending
    assert "last observed cwd" in pending and "current cwd is unknown" in pending
    completed = note(client.requests[3])
    assert "idle_at_last_observation" in completed
    assert str(work / "after") in completed


def test_unavailable_observer_is_unknown_and_does_not_stop_the_task(tmp_path, monkeypatch):
    work, bindir = _setup(tmp_path, monkeypatch, ("afprobe",))
    result, client = _run(tmp_path, work, SharedPathEnv(work, bindir, fail_probe=True), [
        ("terminal", {"input": "printf 'ran\\n'"}),
        ("finish", {"summary": "done"}),
    ])
    assert result.status == "finished"
    initial = json.dumps(client.requests[0]["input"])
    assert "[core facts]" in initial and "unmeasured" in initial
    output = next(item["output"] for item in client.requests[1]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c1")
    assert "ran" in output
    assert result.extras["core_facts"]["shared_known"] is False


def test_unexpected_facts_failure_does_not_prevent_the_task_from_finishing(tmp_path, monkeypatch):
    from aether.core.facts import Facts

    work, bindir = _setup(tmp_path, monkeypatch, ("sh",))

    def fail_record(*_args, **_kwargs):
        raise RuntimeError("synthetic internal failure")

    monkeypatch.setattr(Facts, "_record_event", fail_record)
    result, client = _run(tmp_path, work, SharedPathEnv(work, bindir), [
        ("terminal", {"input": "printf 'delivered\\n' > result.txt"}),
        ("finish", {"summary": "done"}),
    ])
    assert result.status == "finished"
    assert (work / "result.txt").read_text() == "delivered\n"
    output = next(item["output"] for item in client.requests[1]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c1")
    assert "unmeasured" in output and "synthetic internal failure" not in output
    assert result.extras["core_facts"]["internal_failures"] >= 1


def test_facts_record_failure_does_not_destroy_a_completed_result(tmp_path, monkeypatch):
    from aether.core.facts import Facts

    work, bindir = _setup(tmp_path, monkeypatch, ("sh",))

    def fail_record(_self):
        raise RuntimeError("synthetic record failure")

    monkeypatch.setattr(Facts, "record", fail_record)
    result, _client = _run(tmp_path, work, SharedPathEnv(work, bindir), [
        ("terminal", {"input": "printf 'delivered\\n' > result.txt"}),
        ("finish", {"summary": "done"}),
    ])
    assert result.status == "finished"
    assert (work / "result.txt").read_text() == "delivered\n"
    assert result.extras["core_facts"]["status"] == "unknown"


def test_python_session_state_tracks_completed_cells_without_reading_variables(tmp_path, monkeypatch):
    work, _bindir = _setup(tmp_path, monkeypatch, ("sh",))
    client = ResponsesClient([
        turn_events(1, call=("python", {"code": "x = 41"}, "c1")),
        turn_events(2, call=("python", {"code": "print(x + 1)"}, "c2")),
        turn_events(3, call=("finish", {"summary": "done"}, "c3")),
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Use Python.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(tmp_path / "ctl"), end_processes="stop",
                          managed_facts=True, repl=True),
    ))
    assert result.status == "finished"
    session = result.extras["core_facts"]["python_session"]
    assert session["last_cell"] == 2 and session["foreground"] == "idle_at_last_observation"
    assert session["variables"] == "not inspected"
    assert session["preflight_python_version"].startswith("3.")
    assert session["version_scope"] == "python3 preflight before REPL launch"
    output = next(item["output"] for item in client.requests[2]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c2")
    assert "42" in output


def test_python_cwd_uses_cell_receipts_and_marks_pending_state_unknown(tmp_path, monkeypatch):
    work, _bindir = _setup(tmp_path, monkeypatch, ("sh",))
    (work / "before").mkdir()
    (work / "after").mkdir()
    calls = [
        ("python", {"code": "import os; os.chdir('before')"}),
        ("python", {"code": "import time; os.chdir('../after'); time.sleep(3)", "wait_s": 0.2}),
        ("python", {"code": "", "wait_s": 10}),
        ("python", {"code": "os._exit(0)", "wait_s": 5}),
        ("python", {"code": "print('restarted')"}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}"))
        for i, (name, args) in enumerate(calls, 1)
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Use Python.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(tmp_path / "ctl"), end_processes="stop",
                          managed_facts=True, repl=True),
    ))
    assert result.status == "finished"

    def note(request):
        return next(item["content"] for item in request["input"] if item.get("role") == "user"
                    and isinstance(item.get("content"), str)
                    and item["content"].startswith("[core facts]\n"))

    pending = note(client.requests[2])
    assert "Python session" in pending and "completion_not_observed" in pending
    assert str(work / "before") in pending
    assert "Python last observed cwd" in pending and "current cwd is unknown" in pending
    completed = note(client.requests[3])
    assert "idle_at_last_observation" in completed and str(work / "after") in completed
    exited = note(client.requests[4])
    assert "exited_at_last_observation" in exited and "current cwd is unknown" in exited
    restarted = note(client.requests[5])
    assert "idle_at_last_observation" in restarted and str(work) in restarted
    assert str(work / "after") not in restarted
    session = result.extras["core_facts"]["python_session"]
    assert session["generation"] == 2 and session["last_observed_cwd"] == str(work)
    assert session["cwd_receipt_cell"] == 1


def test_real_loop_reports_a_later_metadata_change_to_an_initial_file(tmp_path, monkeypatch):
    work, bindir = _setup(tmp_path, monkeypatch, ("sh",))
    (work / "solver.py").write_text("original\n")
    result, client = _run(tmp_path, work, SharedPathEnv(work, bindir), [
        ("terminal", {"input": "cat solver.py"}),
        ("terminal", {"input": "printf 'changed\\n' > solver.py"}),
        ("finish", {"summary": "done"}),
    ])
    assert result.status == "finished"
    update = next(item["output"] for item in client.requests[2]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c2")
    assert "solver.py" in update and "metadata" in update and "step 2" in update
    assert "content is not established by metadata" in update


def test_state_remains_available_after_context_checkpoint(tmp_path, monkeypatch):
    from aether.core.provider import ChatProvider
    from tests.core_fakes import ScriptedClient, call
    from tests.test_core_v2 import _text

    work, bindir = _setup(tmp_path, monkeypatch, ("afprobe",))
    script = [call("terminal", {
        "input": "printf '#!/bin/sh\\nexit 0\\n' > bin/afprobe; chmod +x bin/afprobe",
    }, "first")]
    script += [call("terminal", {"input": f"echo {i}" + "y" * 3000}, f"c{i}") for i in range(6)]
    script += [call("finish", {"summary": "done"}, "finish")]
    client = ScriptedClient(script, [_text(f"SUMMARY-MARKER-{i}") for i in range(4)])
    core_provider = ChatProvider(client, model="synthetic", params={"tool_choice": "required",
                                                                    "parallel_tool_calls": False})
    config = dataclasses.replace(
        _private_clm_config(tmp_path, budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=2500),
        managed_facts=True, end_processes="stop",
    )
    result = asyncio.run(run_agent(
        env=SharedPathEnv(work, bindir), task="Observe the working environment.", workdir=str(work),
        provider=core_provider, timeout_s=600, trace=Trace(tmp_path / "trace.jsonl"), config=config,
    ))
    assert result.status == "finished"
    requests = [r for r in client.requests if "tools" in r and "SUMMARY-MARKER" in json.dumps(r["messages"])]
    assert requests, "the test must actually exercise a context checkpoint"
    assert "afprobe" in json.dumps(requests[-1]["messages"])
    assert "[core facts]" in json.dumps(requests[-1]["messages"])


def test_pinned_facts_update_when_a_terminal_changes_directory(tmp_path, monkeypatch):
    from aether.core.provider import ChatProvider
    from tests.core_fakes import ScriptedClient, call

    work, bindir = _setup(tmp_path, monkeypatch, ("sh",))
    (work / "sub").mkdir()
    client = ScriptedClient([
        call("terminal", {"name": "alpha", "input": "cd sub"}, "first"),
        call("finish", {"summary": "done"}, "finish"),
    ])
    core_provider = ChatProvider(client, model="synthetic", params={"tool_choice": "required"})
    config = dataclasses.replace(_private_clm_config(tmp_path), managed_facts=True, end_processes="stop")
    result = asyncio.run(run_agent(
        env=SharedPathEnv(work, bindir), task="Observe the working environment.", workdir=str(work),
        provider=core_provider, timeout_s=600, trace=Trace(tmp_path / "trace.jsonl"), config=config,
    ))
    assert result.status == "finished"
    notes = [m["content"] for m in client.requests[1]["messages"] if m.get("role") == "user"
             and isinstance(m.get("content"), str) and m["content"].startswith("[core facts]")]
    assert len(notes) == 1 and 'Terminal "alpha" last observed cwd' in notes[0] and str(work / "sub") in notes[0]


def test_updating_pinned_facts_does_not_rewrite_a_previous_request(tmp_path, monkeypatch):
    from aether.core.provider import ChatProvider
    from tests.core_fakes import ScriptedClient, call

    work, bindir = _setup(tmp_path, monkeypatch, ("afprobe",))
    client = ScriptedClient([
        call("terminal", {"input": "printf '#!/bin/sh\\nexit 0\\n' > bin/afprobe; chmod +x bin/afprobe"}, "first"),
        call("finish", {"summary": "done"}, "finish"),
    ])
    config = dataclasses.replace(_private_clm_config(tmp_path), managed_facts=True, end_processes="stop")
    result = asyncio.run(run_agent(
        env=SharedPathEnv(work, bindir), task="Observe the working environment.", workdir=str(work),
        provider=ChatProvider(client, model="synthetic", params={"tool_choice": "required"}),
        timeout_s=600, trace=Trace(tmp_path / "trace.jsonl"), config=config,
    ))
    assert result.status == "finished"
    def note(request):
        return next(m["content"] for m in request["messages"] if m.get("role") == "user"
                    and isinstance(m.get("content"), str) and m["content"].startswith("[core facts]"))
    assert "Names not resolved on that PATH: afprobe." in note(client.requests[0])
    assert "Names not resolved on that PATH: none." in note(client.requests[1])


def test_resumed_context_refreshes_its_own_facts_without_replacing_task_text(tmp_path, monkeypatch):
    import pickle
    from copy import deepcopy

    from aether.core import fork
    from aether.core.provider import ChatProvider
    from tests.core_fakes import ScriptedClient, call

    work, bindir = _setup(tmp_path, monkeypatch, ("afprobe",))
    config = dataclasses.replace(_private_clm_config(tmp_path), managed_facts=True, end_processes="stop")
    task_text = "[core facts] is literal task text and must be retained."
    source = work / "source.txt"
    source.write_text("original\n")
    checkpoint = {}

    async def capture(session):
        checkpoint["history"] = fork.continued(session, "Continue working.")
        return "finished", True

    monkeypatch.setattr(fork, "at_finish", capture)

    def run(context, suffix, *, make_fork=False):
        client = ScriptedClient([call("finish", {"summary": "done"}, "finish")])
        result = asyncio.run(run_agent(
            env=SharedPathEnv(work, bindir), task=task_text, workdir=str(work),
            provider=ChatProvider(client, model="synthetic", params={"tool_choice": "required"}),
            timeout_s=600, trace=Trace(tmp_path / f"trace-{suffix}.jsonl"),
            config=dataclasses.replace(config, fork=make_fork), resume=context,
        ))
        assert result.status == "finished"
        return result, client.requests[0]["messages"]

    _, first = run(None, "first", make_fork=True)
    assert any("Names not resolved on that PATH: afprobe." in m.get("content", "") for m in first)
    (bindir / "afprobe").write_text("#!/bin/sh\nexit 0\n")
    (bindir / "afprobe").chmod(0o755)
    source.write_text("changed before continuation\n")
    resumed_result, resumed = run(deepcopy(checkpoint["history"]), "resume")
    assert any(isinstance(m.get("content"), str) and m["content"].startswith(task_text) for m in resumed)
    notes = [m["content"] for m in resumed if m.get("role") == "user"
             and isinstance(m.get("content"), str) and m["content"].startswith("[core facts]\n")]
    assert len(notes) == 1
    assert "Names not resolved on that PATH: none." in notes[0]
    assert "source.txt" in notes[0] and "continuation 1 step 0" in notes[0]
    assert resumed_result.extras["core_facts"]["initial_workspace"]["scope"] == "run_start"

    restored = pickle.loads(pickle.dumps(checkpoint["history"]))
    restored_result, _ = run(restored, "restored")
    assert restored_result.extras["core_facts"]["initial_workspace"]["scope"] == "run_start"

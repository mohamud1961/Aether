"""Real Core loop, real local shell, scripted provider: no model or cloud calls."""

import asyncio
import json
import shlex
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

"""Exercise the pull interface through the real Core loop and a local shell."""

import asyncio
import json
import os
import re
import shlex
import subprocess
import sys

from aether.core import facts_probe
from aether.core.loop import CoreConfig, Trace, run_agent
from tests.core_fakes import LocalEnv
from tests.test_core_responses import ResponsesClient, provider, turn_events


def test_pull_mode_is_explicit_and_default_is_v2():
    from aether.core.harbor_agent import build_config
    from tests.test_core_start_copy import BASE

    baseline = build_config(environ=BASE)
    pull = build_config(environ={**BASE, "AETHER_CORE_MANAGED_FACTS": "pull"})
    assert baseline.managed_facts and baseline.facts_v2 and not baseline.facts_pull
    assert pull.managed_facts and pull.facts_pull


def test_agent_can_read_observed_workspace_changes_from_shell(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "source.txt").write_text("before\n")
    control = tmp_path / "control"
    state = control / "state"
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    calls = [
        ("terminal", {"input": "printf 'after\\n' > source.txt"}),
        ("terminal", {"input": f"cat {shlex.quote(str(state / 'changes.txt'))}"}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}")) for i, (name, args) in enumerate(calls, 1)
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Edit source.txt.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(control), end_processes="stop", start_copy=True,
                          managed_facts=True, facts_pull=True),
    ))

    assert result.status == "finished"
    task = next(item["content"] for item in client.requests[0]["input"]
                if item.get("role") == "user" and "Edit source.txt." in item.get("content", ""))
    assert str(state) in task and all(name in task for name in ("changes.txt", "checks.txt", "unobserved.txt"))
    output = next(item["output"] for item in client.requests[2]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c2")
    assert "source.txt" in output and "step 1" in output and "metadata" in output
    assert "[core facts]" not in output


def test_execution_history_reports_later_observed_changes_and_unknown_opens(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "source.txt").write_text("before\n")
    control = tmp_path / "control"
    state = control / "state"
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    calls = [
        ("terminal", {"input": "cat source.txt >/dev/null"}),
        ("terminal", {"input": "printf 'after\n' > source.txt"}),
        ("terminal", {"input": f"cat {shlex.quote(str(state / 'checks.txt'))} "
                               f"{shlex.quote(str(state / 'unobserved.txt'))}"}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}")) for i, (name, args) in enumerate(calls, 1)
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Inspect and edit source.txt.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(control), end_processes="stop", start_copy=True,
                          managed_facts=True, facts_pull=True),
    ))
    assert result.status == "finished"
    output = next(item["output"] for item in client.requests[3]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c3")
    assert re.search(r"step 1.*terminal.*observed.*step 2", output)
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", output)
    assert "unopened files are unknown" in output


def test_unobserved_list_is_scoped_to_direct_read_receipts(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "seen.txt").write_text("seen\n")
    (work / "other.txt").write_text("other\n")
    control = tmp_path / "control"
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    calls = [
        ("read_file", {"path": "seen.txt"}),
        ("terminal", {"input": f"cat {shlex.quote(str(control / 'state' / 'unobserved.txt'))}"}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}")) for i, (name, args) in enumerate(calls, 1)
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Inspect the files.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(control), end_processes="stop", start_copy=True,
                          managed_facts=True, facts_pull=True),
    ))
    assert result.status == "finished"
    output = next(item["output"] for item in client.requests[2]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c2")
    assert "other.txt" in output and "seen.txt" not in output
    assert "unopened files are unknown" in output


def test_changes_file_reports_git_head_and_start_ancestry(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "source.txt").write_text("before\n")
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "add", "source.txt"], check=True)
    subprocess.run(["git", "-C", str(work), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-q", "-m", "initial"], check=True)
    initial = subprocess.check_output(["git", "-C", str(work), "rev-parse", "HEAD"], text=True).strip()
    control = tmp_path / "control"
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    calls = [
        ("terminal", {"input": "printf 'after\\n' > source.txt; git add source.txt; "
                               "git -c user.name=Fixture -c user.email=fixture@example.invalid commit -q -m next"}),
        ("terminal", {"input": f"cat {shlex.quote(str(control / 'state' / 'changes.txt'))}"}),
        ("terminal", {"input": "git checkout -q --orphan independent; git rm -q -r .; "
                               "printf 'separate\\n' > source.txt; git add source.txt; "
                               "git -c user.name=Fixture -c user.email=fixture@example.invalid commit -q -m separate"}),
        ("terminal", {"input": f"cat {shlex.quote(str(control / 'state' / 'changes.txt'))}"}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}")) for i, (name, args) in enumerate(calls, 1)
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Edit the repository.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(control), end_processes="stop", start_copy=True,
                          managed_facts=True, facts_pull=True),
    ))
    assert result.status == "finished"
    current = subprocess.check_output(["git", "-C", str(work), "rev-parse", "HEAD"], text=True).strip()
    output = next(item["output"] for item in client.requests[2]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c2")
    assert initial != current and initial in output
    assert "start commit is an ancestor" in output
    rewritten = next(item["output"] for item in client.requests[4]["input"]
                     if item.get("type") == "function_call_output" and item.get("call_id") == "c4")
    assert initial in rewritten and current in rewritten
    assert "start commit is not an ancestor" in rewritten


def test_changes_file_includes_created_and_removed_workspace_paths(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "original.txt").write_text("before\n")
    control = tmp_path / "control"
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    calls = [
        ("terminal", {"input": "rm original.txt; printf 'new\\n' > created.txt"}),
        ("terminal", {"input": f"cat {shlex.quote(str(control / 'state' / 'changes.txt'))}"}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}")) for i, (name, args) in enumerate(calls, 1)
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Replace the file.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(control), end_processes="stop", start_copy=True,
                          managed_facts=True, facts_pull=True),
    ))
    assert result.status == "finished"
    output = next(item["output"] for item in client.requests[2]["input"]
                  if item.get("type") == "function_call_output" and item.get("call_id") == "c2")
    assert "original.txt" in output and "created.txt" in output
    assert "initial" in output and "step 1" in output


def test_state_directory_symlink_is_not_followed(tmp_path, monkeypatch):
    work, control, outside = tmp_path / "work", tmp_path / "control", tmp_path / "outside"
    work.mkdir()
    control.mkdir()
    outside.mkdir()
    marker = outside / "changes.txt"
    marker.write_text("keep\n")
    (control / "state").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    client = ResponsesClient([turn_events(1, call=("finish", {"summary": "done"}, "c1"))])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Finish.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600,
        trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(control), end_processes="stop", managed_facts=True, facts_pull=True),
    ))
    assert result.status == "finished" and marker.read_text() == "keep\n"
    task = next(item["content"] for item in client.requests[0]["input"]
                if item.get("role") == "user" and "Finish." in item.get("content", ""))
    assert "Core state directory" not in task


def test_trace_records_observed_terminal_state_and_keys_mode(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "sub").mkdir()
    (work / "source.txt").write_text("fixture\n")
    control = tmp_path / "control"
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    monkeypatch.setenv("AETHER_FIXTURE_TOKEN", "fixture-canary-value")
    calls = [
        ("terminal", {"input": "cd sub; export DEMO_FLAG=ready"}),
        ("terminal", {"input": "read -r answer", "wait_s": 0.2}),
        ("terminal", {"input": "hello\n", "mode": "keys", "wait_s": 2}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}")) for i, (name, args) in enumerate(calls, 1)
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Use a terminal.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600, trace=Trace(trace),
        config=CoreConfig(control_dir=str(control), end_processes="stop", start_copy=True,
                          managed_facts=True, facts_pull=True),
    ))
    assert result.status == "finished"
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    start = next(row for row in rows if row["event"] == "core_state_start")
    assert start["start_copy"]["source"] == str(work)
    assert start["start_copy"]["path"] == str(control / "start" / "work")
    assert start["image_workdir"]["status"] == "unknown"
    events = [row for row in rows if row["event"] == "core_state_step"]
    assert [row["mode"] for row in events] == ["command", "command", "keys"]
    assert events[0]["pre_cwd"]["value"] == str(work)
    assert events[0]["post_cwd"]["value"] == str(work / "sub")
    assert events[1]["pre_cwd"]["value"] == str(work / "sub")
    assert all(row["environment_delta"]["status"] == "unknown" for row in events)
    assert "fixture-canary-value" not in json.dumps([start, *events])


def test_trace_reports_safe_exported_name_changes_without_values(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    control = tmp_path / "control"
    monkeypatch.setattr(facts_probe, "HOSTS", ())
    monkeypatch.setattr(facts_probe, "SYSTEM_PYTHON_PATHS", (os.path.realpath(sys.executable),))
    monkeypatch.setenv("AETHER_FIXTURE_TOKEN", "fixture-canary-value")
    monkeypatch.setenv("AETHER_ENV_NAMES_V1", "marker-canary")
    calls = [
        ("terminal", {"input": "true"}),
        ("terminal", {"input": "export REPLAY_FIXTURE_FLAG=ready AETHER_ENV_NAMES_END=marker"}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}")) for i, (name, args) in enumerate(calls, 1)
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Use a terminal.", workdir=str(work),
        provider=provider(client, tmp_path / "calls"), timeout_s=600, trace=Trace(trace),
        config=CoreConfig(control_dir=str(control), end_processes="stop", managed_facts=True, facts_pull=True),
    ))
    assert result.status == "finished"
    events = [json.loads(line) for line in trace.read_text().splitlines() if '"event": "core_state_step"' in line]
    delta = events[1]["environment_delta"]
    assert delta["status"] == "names_observed" and "REPLAY_FIXTURE_FLAG" in delta["added"]
    assert delta["values"] == "not recorded"
    assert "AETHER_FIXTURE_TOKEN" not in json.dumps(events) and "fixture-canary-value" not in json.dumps(events)

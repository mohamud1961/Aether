"""The real Core loop reports a running command while preserving its eventual effect."""

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import shlex

import pytest

from aether.core.harbor_config import build_config
from aether.core.loop import Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


pytestmark = pytest.mark.skipif(
    not os.path.exists("/proc/self/stat"), reason="process reporting requires Linux /proc"
)


def without_python(monkeypatch, root, *, replacement):
    """Use the real shell and installed tools with Python unavailable or failing."""
    commands = root / "commands"
    commands.mkdir()
    for directory in (Path("/usr/local/bin"), Path("/usr/bin"), Path("/bin")):
        if not directory.is_dir():
            continue
        for executable in directory.iterdir():
            if executable.name.startswith("python") or not os.access(executable, os.X_OK):
                continue
            link = commands / executable.name
            if not link.exists():
                link.symlink_to(executable)
    if replacement == "partial":
        executable = commands / "python3"
        executable.write_text("#!/bin/sh\nprintf '123.45\\n100\\n'\n")
        executable.chmod(0o755)
    elif replacement:
        (commands / "python3").symlink_to(replacement)
    monkeypatch.setenv("PATH", str(commands))


@pytest.mark.parametrize("python_mode", ["available", "missing", "broken", "empty", "partial"])
def test_fast_process_report_preserves_real_loop_effect_and_evidence(tmp_path, monkeypatch, python_mode):
    if python_mode != "available":
        replacement = {"missing": "", "broken": "/bin/false", "empty": "/bin/true", "partial": "partial"}[python_mode]
        without_python(monkeypatch, tmp_path, replacement=replacement)

    work = tmp_path / "work"
    work.mkdir()
    control = tmp_path / "control"
    settings = {
        "AETHER_CORE_REVIEW": "off",
        "AETHER_CORE_CONTEXT": "project",
        "AETHER_CORE_REPL": "off",
        "AETHER_CORE_IMAGES": "off",
        "AETHER_CORE_START_COPY": "off",
        "AETHER_CORE_TERMINAL_EVENTS": "on",
        "AETHER_CORE_END_PROCESSES": "stop",
        "AETHER_CORE_FAST_PROCESS_SCAN": "on",
    }
    assert not build_config(environ={**settings, "AETHER_CORE_FAST_PROCESS_SCAN": "off"}).fast_process_scan
    config = build_config(environ=settings)
    assert config.fast_process_scan

    command = (
        'cp "$(command -v sleep)" "odd ) name"; "./odd ) name" 60 & child=$!; '
        "while [ ! -e release ]; do sleep 0.1; done; "
        'kill "$child"; wait "$child" 2>/dev/null || :; '
        "printf x >> effects; echo finished"
    )
    client = ScriptedClient([
        call("terminal", {"name": "job", "input": command, "wait_s": 0.1}, "start"),
        call("write_file", {"path": str(work / "release"), "content": "go"}, "release"),
        call("terminal_wait", {"names": ["job"], "mode": "all", "wait_s": 20}, "wait"),
        call("finish", {"summary": "done"}, "done"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Run the background job once and wait for completion.", workdir=str(work),
        provider=ChatProvider(client, model="scripted", params={}), trace=Trace(trace), timeout_s=90,
        config=replace(config, control_dir=str(control)),
    ))
    assert result.status == "finished", result.error
    first = [m for m in client.requests[1]["messages"] if m["role"] == "tool"][-1]["content"]
    assert "still running" in first
    assert "[its processes:" in first and "./odd ) name 60 (pid " in first
    assert (work / "effects").read_text() == "x"
    waited = [m for m in client.requests[3]["messages"] if m["role"] == "tool"][-1]["content"]
    result_json = json.loads(waited[:waited.rindex("}") + 1])
    assert [(item["name"], item["exit"]) for item in result_json["completed"]] == [("job", 0)]
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    assert next(event for event in events if event["event"] == "start")["fast_process_scan"] is True


def test_fast_process_report_handles_zombie_and_process_churn(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    program = "\n".join([
        "import os, subprocess, time",
        "zombie = os.fork()",
        "if zombie == 0: os._exit(0)",
        "with open('zpid', 'w') as f: f.write(str(zombie))",
        "worker = subprocess.Popen(['sleep', '60'])",
        "try:",
        " while not os.path.exists('release'):",
        "  subprocess.run(['true'], check=True); time.sleep(0.02)",
        "finally:",
        " worker.terminate(); worker.wait(); os.waitpid(zombie, 0)",
        "with open('effects', 'a') as f: f.write('x')",
    ])
    client = ScriptedClient([
        call("terminal", {"name": "job", "input": "python3 -c " + shlex.quote(program), "wait_s": 0.5}, "start"),
        call("write_file", {"path": str(work / "release"), "content": "go"}, "release"),
        call("terminal_wait", {"names": ["job"], "mode": "all", "wait_s": 20}, "wait"),
        call("finish", {"summary": "done"}, "done"),
    ])
    settings = {
        "AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "project", "AETHER_CORE_REPL": "off",
        "AETHER_CORE_IMAGES": "off", "AETHER_CORE_START_COPY": "off", "AETHER_CORE_TERMINAL_EVENTS": "on",
        "AETHER_CORE_END_PROCESSES": "stop", "AETHER_CORE_FAST_PROCESS_SCAN": "on",
    }
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Run the background job once and wait for completion.", workdir=str(work),
        provider=ChatProvider(client, model="scripted", params={}), trace=Trace(tmp_path / "trace.jsonl"), timeout_s=90,
        config=replace(build_config(environ=settings), control_dir=str(tmp_path / "control")),
    ))
    assert result.status == "finished", result.error
    first = [m for m in client.requests[1]["messages"] if m["role"] == "tool"][-1]["content"]
    zombie_pid = (work / "zpid").read_text()
    assert f"python3 (pid {zombie_pid}, exited (zombie)" in first
    assert "sleep 60 (pid " in first
    assert (work / "effects").read_text() == "x"

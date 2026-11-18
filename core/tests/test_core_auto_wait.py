"""auto_wait: a reply with no tool call while work runs sleeps until it finishes (Unreal-style, default off)."""

import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from aether.core import auto_wait, completion_notice
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk

USAGE = {"prompt_tokens": 1000, "completion_tokens": 10, "prompt_tokens_details": {"cached_tokens": 0},
         "completion_tokens_details": {"reasoning_tokens": 0}}


def say(text):
    """One model turn with text and no tool call."""
    return [chunk(content=text), chunk(finish="stop"), chunk(usage=USAGE)]


# --- units (no shell) -------------------------------------------------------------------------------------------

def test_switch_is_off_by_default_and_wired():
    from aether.core import harbor_agent
    from aether.core import harbor_config as hc

    base = {hc.REVIEW_ENV: "off", hc.CONTEXT_ENV: "clm", hc.REPL_ENV: "off", hc.IMAGES_ENV: "on"}
    assert CoreConfig().auto_wait is False and CoreConfig().auto_wait_grace_s == 30.0
    assert hc.build_config(environ=base).auto_wait is False
    on = hc.build_config(environ={**base, "AETHER_CORE_AUTO_WAIT": "on", "AETHER_CORE_AUTO_WAIT_GRACE": "1"})
    assert on.auto_wait is True and on.auto_wait_grace_s == 1.0
    with pytest.raises(hc.ConfigError):
        hc.build_config(environ={**base, "AETHER_CORE_AUTO_WAIT_GRACE": "5"})
    provider_env = {harbor_agent.ENDPOINT_ENV: "http://127.0.0.1:9/", harbor_agent.KEY_ENV: "k",
                    harbor_agent.DEPLOYMENT_ENV: "m"}
    assert harbor_agent.build_provider(environ=provider_env).params["tool_choice"] == "required"
    assert harbor_agent.build_provider(environ={**provider_env, "AETHER_CORE_AUTO_WAIT": "on"}).params[
        "tool_choice"] == "auto"


def test_grace_caps_only_when_on():
    assert auto_wait.grace(CoreConfig(), 120.0) == 120.0
    assert auto_wait.grace(CoreConfig(auto_wait=True), 120.0) == 30.0
    assert auto_wait.grace(CoreConfig(auto_wait=True, auto_wait_grace_s=1.0), 30.0) == 1.0
    assert auto_wait.grace(CoreConfig(auto_wait=True), 5.0) == 5.0


def test_running_line_is_unreal_text_and_only_on_running_results():
    out = "x\n[still running after 31s · terminal main; call again]"
    assert auto_wait.mark_running(CoreConfig(), out) == out
    marked = auto_wait.mark_running(CoreConfig(auto_wait=True), out)
    assert marked.endswith("[Tool call is still running. Its result arrives in a later turn: continue with "
                           "independent work, or end your turn to wait for it.]")
    assert auto_wait.mark_running(CoreConfig(auto_wait=True), "done\n[0.2s · terminal main]") == "done\n[0.2s · terminal main]"


def fake_session(pending=1, notices=(), remaining=3600.0):
    sess = SimpleNamespace(ready=True, pending=pending, root="/ctl/term/main")
    rows = []
    return SimpleNamespace(
        terminals=SimpleNamespace(_sessions={"main": sess}),
        result=SimpleNamespace(extras={"completion_notices_seen": []}, steps=3),
        trace=lambda event, **kw: rows.append({"event": event, **kw}),
        remaining=lambda: remaining, rows=rows, sess=sess, repl=None)


def test_nothing_running_returns_none_so_the_idle_path_applies():
    s = fake_session(pending=0)
    assert asyncio.run(auto_wait.sleep(s)) is None
    assert s.rows == []


def test_sleeps_until_a_result_arrives(monkeypatch):
    s = fake_session()
    answers = iter(["", "", "\n[terminal main: command #1 finished with exit 0; collected output]\nbuilt"])
    calls = []

    async def before_model(sess, *, deliver=None, others=None):
        calls.append((deliver, others))
        return next(answers)
    monkeypatch.setattr(completion_notice, "before_model", before_model)
    t = [0.0]

    async def pause(dt):
        t[0] += dt
    text = asyncio.run(auto_wait.sleep(s, clock=lambda: t[0], pause=pause))
    assert text.startswith("[terminal main: command #1 finished") and text.endswith("built")
    assert calls == [(True, True)] * 3  # results are delivered, other owners looked at
    assert [r["phase"] for r in s.rows] == ["sleep", "woke"] and s.rows[1]["by"] == "result"


def test_heartbeat_after_ten_minutes(monkeypatch):
    s = fake_session()

    async def before_model(sess, **kw):
        return ""
    monkeypatch.setattr(completion_notice, "before_model", before_model)
    t = [0.0]

    async def pause(dt):
        t[0] += 60.0
    text = asyncio.run(auto_wait.sleep(s, clock=lambda: t[0], pause=pause))
    assert text == "Heartbeat: waited 600 seconds for tool calls.\nRunning: terminal main command #1"
    assert s.rows[-1]["by"] == "heartbeat" and s.rows[-1]["waited_s"] >= 600


def test_wakes_before_the_time_limit(monkeypatch):
    s = fake_session(remaining=20.0)

    async def before_model(sess, **kw):
        return ""
    monkeypatch.setattr(completion_notice, "before_model", before_model)
    text = asyncio.run(auto_wait.sleep(s, clock=lambda: 0.0, pause=lambda dt: asyncio.sleep(0)))
    assert "of the time limit left" in text and s.rows[-1]["by"] == "time_limit"


def test_already_shown_command_is_not_waited_for():
    s = fake_session()
    s.result.extras["completion_notices_seen"].append({"owner": "/ctl/term/main", "sequence": 1})
    assert asyncio.run(auto_wait.sleep(s)) is None


# --- real loop, real shell ---------------------------------------------------------------------------------------

linux = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux shell qualification")


def run(tmp_path, on):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([
        call("terminal", {"name": "build", "input": "sleep 2; echo built-ok > out.txt; echo build-finished",
                          "wait_s": 0.2}, "start"),
        say("The build is running; I will wait for it."),
        call("read_file", {"path": "out.txt"}, "check"),
        call("finish", {"summary": "built."}, "done"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Build out.txt.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(trace), timeout_s=60,
        config=CoreConfig(auto_wait=on, control_dir=str(tmp_path / "control"), end_processes="stop"),
    ))
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    return result, client, rows


@linux
def test_plain_reply_while_running_sleeps_and_delivers_the_result(tmp_path):
    result, client, rows = run(tmp_path, on=True)
    assert result.status == "finished"
    first_tool = [m["content"] for m in client.requests[1]["messages"] if m["role"] == "tool"][-1]
    assert auto_wait.RUNNING in first_tool
    after_wait = client.requests[2]["messages"][-1]
    assert after_wait["role"] == "user" and "build-finished" in after_wait["content"]  # delivered, no poll
    waits = [r for r in rows if r["event"] == "auto_wait"]
    assert [w["phase"] for w in waits] == ["sleep", "woke"] and waits[1]["by"] == "result"
    assert 1.0 <= waits[1]["waited_s"] <= 10
    assert auto_wait.PROMPT.strip() in client.requests[0]["messages"][0]["content"]
    assert (tmp_path / "work" / "out.txt").read_text().strip() == "built-ok"


@linux
def test_switch_off_a_plain_reply_is_an_idle_turn_and_nothing_waits(tmp_path):
    result, client, rows = run(tmp_path, on=False)
    assert not [r for r in rows if r["event"] == "auto_wait"]
    after = client.requests[2]["messages"][-1]
    assert after["role"] == "user" and after["content"].startswith("Continue by using a tool")
    assert auto_wait.PROMPT.strip() not in client.requests[0]["messages"][0]["content"]

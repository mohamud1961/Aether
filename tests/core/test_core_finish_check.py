"""Finish second look (experiment instrument): the first finish is held once; "check" adds an executed check."""

import asyncio
import json

import pytest

from aether.core import harbor_agent as adapter
from aether.core.calls import CallLog
from aether.core.finish_check import NUDGE
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core.core_fakes import LocalEnv, ScriptedClient, chunk, tool_chunk

CHECK = 'grep -q "^ok$" out.txt && echo "out.txt says ok" || { echo "VIOLATION: out.txt must say ok"; exit 1; }'


def _turn(name, args, call_id):
    return [
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(usage={"prompt_tokens": 5, "completion_tokens": 2}),
    ]


def _run(tmp_path, script, timeout_s=300, **config):
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    client = ScriptedClient(script)
    provider = ChatProvider(client, model="scripted", params={}, log=CallLog(tmp_path / "calls"))
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=timeout_s,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), **config),
        )
    )
    rows = [json.loads(x) for x in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return result, client, rows


def _script(first):
    return [
        _turn("write_file", {"path": "out.txt", "content": first}, "c1"),
        _turn("finish", {"summary": "done"}, "c2"),
        _turn("write_file", {"path": "out.txt", "content": "ok\n"}, "c3"),
        _turn("finish", {"summary": "repaired"}, "c4"),
    ]


def test_nudge_holds_the_first_finish_once_without_a_check(tmp_path):
    result, client, rows = _run(tmp_path, _script("bad\n"), finish_nudge=True)
    assert result.status == "finished" and len(client.requests) == 4
    shown = client.requests[2]["messages"][-1]["content"]
    assert shown.startswith(NUDGE) and "check" not in shown.removeprefix(NUDGE)
    assert [r["event"] for r in rows].count("finish_second_look") == 1


def test_check_shows_a_failing_check_and_the_next_finish_ends_the_work(tmp_path):
    result, client, _ = _run(tmp_path, _script("bad\n"), finish_nudge=True, finish_check=CHECK,
                             finish_show_check=True)
    shown = client.requests[2]["messages"][-1]["content"]
    assert shown.startswith(NUDGE) and "FAILED (exit code 1)" in shown and "VIOLATION: out.txt must say ok" in shown
    assert result.status == "finished" and len(client.requests) == 4


def test_a_passing_check_is_reported_as_passed(tmp_path):
    script = [_turn("write_file", {"path": "out.txt", "content": "ok\n"}, "c1"),
              _turn("finish", {"summary": "done"}, "c2"), _turn("finish", {"summary": "done"}, "c3")]
    _, client, _ = _run(tmp_path, script, finish_check=CHECK, finish_show_check=True)
    assert "PASSED (exit code 0)" in client.requests[2]["messages"][-1]["content"]


def test_a_hidden_check_is_recorded_but_the_model_sees_only_the_nudge(tmp_path):
    result, client, rows = _run(tmp_path, _script("bad\n"), finish_nudge=True, finish_check=CHECK)
    shown = client.requests[2]["messages"][-1]["content"]
    assert shown.startswith(NUDGE) and "VIOLATION" not in shown and "check" not in shown.removeprefix(NUDGE)
    row = next(r for r in rows if r["event"] == "finish_second_look")
    assert row["check_exit"] == 1 and "VIOLATION" in row["check_output"] and row["check_shown"] is False
    assert result.extras["finish_check"]["check_exit"] == 1


def test_off_is_the_unchanged_baseline_and_no_hold_when_little_time_is_left(tmp_path):
    script = [_turn("finish", {"summary": "done"}, "c1")]
    result, client, rows = _run(tmp_path, script)
    assert result.status == "finished" and len(client.requests) == 1
    assert not any(r["event"] == "finish_second_look" for r in rows)
    result, client, _ = _run(tmp_path / "late", script, timeout_s=70, finish_nudge=True)
    assert result.status == "finished" and len(client.requests) == 1


def test_env_modes_nudge_and_check(monkeypatch, tmp_path):
    for name, value in ((adapter.REVIEW_ENV, "off"), (adapter.CONTEXT_ENV, "project"),
                        (adapter.REPL_ENV, "off"), (adapter.IMAGES_ENV, "off")):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(adapter.FINISH_CHECK_ENV, raising=False)
    monkeypatch.setenv(adapter.FINISH_ENV, "nudge")
    config = adapter.build_config()
    assert config.finish_nudge is True and config.finish_check == ""
    monkeypatch.setenv(adapter.FINISH_ENV, "check")
    with pytest.raises(adapter.ConfigError):  # check without a script path stops the run
        adapter.build_config()
    path = tmp_path / "check.sh"
    path.write_text(CHECK)
    monkeypatch.setenv(adapter.FINISH_CHECK_ENV, str(path))
    config = adapter.build_config()
    assert config.finish_nudge is True and config.finish_check == CHECK and config.finish_show_check is True
    monkeypatch.setenv(adapter.FINISH_ENV, "nudge")  # with a script: recorded, never shown
    config = adapter.build_config()
    assert config.finish_check == CHECK and config.finish_show_check is False


def test_think_reminder_follows_every_turn_only_when_on(tmp_path):
    from aether.core.tools import THINK_REMINDER

    script = [_turn("write_file", {"path": "out.txt", "content": "ok\n"}, "c1"), _turn("finish", {"summary": "d"}, "c2")]
    _, client, _ = _run(tmp_path / "on", script, think_reminder=True)
    msgs = client.requests[1]["messages"]
    assert msgs[-1] == {"role": "user", "content": THINK_REMINDER} and msgs[-2]["role"] == "tool"
    _, client, _ = _run(tmp_path / "off", script)
    assert all(m.get("content") != THINK_REMINDER for m in client.requests[1]["messages"])

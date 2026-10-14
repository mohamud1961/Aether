"""JSON text turns: same tools and validation as native calls, a written reply per action, no tools parameter."""

import asyncio
import json

import pytest

from aether.core import textturn
from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.tools import tools
from tests.core.core_fakes import LocalEnv, ScriptedClient, chunk


@pytest.mark.parametrize(
    "content, protocol",
    [
        (
            '{"analysis": "a", "plan": "p", "actions": [], "task_complete": true}',
            "strict",
        ),
        (
            '```json\n{"analysis": "a", "actions": [], "task_complete": true}\n```',
            "strict",
        ),
        (
            'Here: {"analysis": "a", "actions": [], "task_complete": true} done',
            "embedded",
        ),
        ("no json at all", "invalid"),
        ('{"just": "an object without actions"} trailing', "invalid"),
        ("[1, 2]", "invalid"),
    ],
)
def test_read_reply_classes(content, protocol):
    assert textturn.read_reply(content)[1] == protocol


def test_calls_from_runs_actions_then_finishes_on_task_complete():
    obj = {
        "analysis": "all checked",
        "actions": [{"tool": "terminal", "args": {"input": "ls"}}],
        "task_complete": True,
    }
    calls, problem = textturn.calls_from(obj, 3)
    assert problem == "" and [c["function"]["name"] for c in calls] == [
        "terminal",
        "finish",
    ]
    assert json.loads(calls[0]["function"]["arguments"]) == {"input": "ls"}
    assert json.loads(calls[1]["function"]["arguments"]) == {"summary": "all checked"}
    assert len({c["id"] for c in calls}) == 2


@pytest.mark.parametrize(
    "obj",
    [
        {"actions": [], "task_complete": False},
        {"actions": "ls"},
        {"actions": [{"args": {}}]},
        {"actions": [{"tool": "terminal", "args": "ls"}]},
    ],
)
def test_calls_from_reports_unrunnable_replies(obj):
    calls, problem = textturn.calls_from(obj, 1)
    assert calls == [] and problem


def test_reply_doc_lists_every_tool_but_finish_with_required_marks():
    doc = textturn.reply_doc(tools(python=True))
    assert "- terminal(input*: string" in doc and "- python(code*: string" in doc
    assert "- finish(" not in doc and "task_complete" in doc


def _run(tmp_path, replies, timeout_s=60):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    script = [
        [
            chunk(content=r),
            chunk(finish="stop"),
            chunk(usage={"prompt_tokens": 5, "completion_tokens": 2}),
        ]
        for r in replies
    ]
    client = ScriptedClient(script)
    provider = ChatProvider(
        client,
        model="scripted",
        params={"tool_choice": "required"},
        log=CallLog(tmp_path / "calls"),
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=timeout_s,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), turn="json"),
        )
    )
    rows = [json.loads(x) for x in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return result, client, rows, work


def test_json_turns_run_real_tools_and_return_results_as_one_user_message(tmp_path):
    write = {
        "analysis": "nothing yet",
        "plan": "write the file, expect ok",
        "actions": [
            {"tool": "write_file", "args": {"path": "out.txt", "content": "hi\n"}},
            {"tool": "read_file", "args": {"path": "out.txt"}},
        ],
        "task_complete": False,
    }
    done = {
        "analysis": "out.txt holds hi",
        "plan": "",
        "actions": [],
        "task_complete": True,
    }
    result, client, rows, work = _run(tmp_path, [json.dumps(write), json.dumps(done)])
    assert result.status == "finished" and (work / "out.txt").read_text() == "hi\n"
    assert all("tools" not in r and "tool_choice" not in r for r in client.requests)
    second = client.requests[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-1]["role"] == "user"
    assert "Result of action 1 (write_file)" in second[-1]["content"]
    assert (
        "Result of action 2 (read_file)" in second[-1]["content"]
        and "hi" in second[-1]["content"]
    )
    assert (
        textturn.REPLY_DOC.strip()[:40] in client.requests[0]["messages"][0]["content"]
    )
    assert [r["protocol"] for r in rows if r["event"] == "text_turn"] == [
        "strict",
        "strict",
    ]


def test_an_unreadable_reply_is_shown_its_problem_and_three_in_a_row_stop_the_run(
    tmp_path,
):
    result, client, rows, _ = _run(tmp_path, ["not json", "still not", "nope"])
    assert result.status == "no_tool_loop"
    assert (
        "could not be run: not valid JSON"
        in client.requests[1]["messages"][-1]["content"]
    )
    assert [r["protocol"] for r in rows if r["event"] == "text_turn"] == ["invalid"] * 3


def test_an_invalid_tool_is_reported_in_the_results_not_dropped(tmp_path):
    bad = {
        "analysis": "a",
        "plan": "p",
        "actions": [{"tool": "rm_rf", "args": {}}],
        "task_complete": False,
    }
    done = {"analysis": "a", "plan": "", "actions": [], "task_complete": True}
    result, client, _, _ = _run(tmp_path, [json.dumps(bad), json.dumps(done)])
    assert result.status == "finished"
    assert "unknown tool 'rm_rf'" in client.requests[1]["messages"][-1]["content"]


def test_json_turns_work_under_model_managed_context(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    replies = [
        {
            "analysis": "start",
            "plan": "look",
            "actions": [{"tool": "terminal", "args": {"input": "echo hi"}}],
            "task_complete": False,
        },
        {"analysis": "saw hi", "plan": "", "actions": [], "task_complete": True},
    ]
    script = [
        [
            chunk(content=json.dumps(r)),
            chunk(finish="stop"),
            chunk(usage={"prompt_tokens": 5, "completion_tokens": 2}),
        ]
        for r in replies
    ]
    client = ScriptedClient(script)
    provider = ChatProvider(
        client, model="scripted", params={}, log=CallLog(tmp_path / "calls")
    )
    ctl = tmp_path / "ctl"
    from aether.core.clm import ClmSettings

    cfg = CoreConfig(
        control_dir=str(ctl),
        turn="json",
        context="clm",
        clm=ClmSettings(
            mirror_path=str(ctl / "ctx.txt"), history_path=str(ctl / "hist.txt")
        ),
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=60,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=cfg,
        )
    )
    assert result.status == "finished"
    assert (
        "Result of action 1 (terminal)" in client.requests[1]["messages"][-1]["content"]
    )
    assert "hi" in client.requests[1]["messages"][-1]["content"]

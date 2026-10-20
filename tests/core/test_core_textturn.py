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


def test_unreadable_replies_are_shown_their_problem_and_do_not_stop_the_run(tmp_path):
    done = {"analysis": "a", "plan": "", "actions": [], "task_complete": True}
    result, client, rows, _ = _run(
        tmp_path, ["not json", "still not", "nope", json.dumps(done)]
    )
    assert (
        result.status == "finished"
    )  # S5: three escaping errors must not end a run with time left
    assert (
        "could not be run: the reply has no JSON object"
        in client.requests[1]["messages"][-1]["content"]
    )
    assert [r["protocol"] for r in rows if r["event"] == "text_turn"] == [
        "invalid"
    ] * 3 + ["strict"]


def test_three_readable_replies_without_actions_stop_the_run_like_idle_turns(tmp_path):
    idle = json.dumps(
        {"analysis": "thinking", "plan": "", "actions": [], "task_complete": False}
    )
    result, _, _, _ = _run(tmp_path, [idle, idle, idle])
    assert result.status == "no_tool_loop"


@pytest.mark.parametrize(
    "content, tools, note",
    [
        # S5 feal/elf: the action object left unclosed before the next action
        (
            '{"analysis": "a", "plan": "p", "actions": [{"tool": "write_file", "args": {"path": "x.py", "content": "pass\\n"}, '
            '{"tool": "terminal", "args": {"input": "python x.py"}}], "task_complete": false}',
            ["write_file", "terminal"],
            "added '}'",
        ),
        # unclosed at the end of the list: the brace goes before "]", keeping wait_s inside args
        (
            '{"analysis": "a", "plan": "p", "actions": [{"tool": "terminal", "args": {"input": "ls", "wait_s": 120}], '
            '"task_complete": false}',
            ["terminal"],
            "added '}'",
        ),
        # S5 protein/sparql: a double quote left unescaped inside a string
        (
            '{"analysis": "the page says ("Just a moment") so retry", "plan": "p", "actions": [{"tool": "terminal", '
            '"args": {"input": "ls"}}], "task_complete": false}',
            ["terminal"],
            "escaped the quote",
        ),
    ],
)
def test_repair_mends_s5_slips_and_says_what_it_changed(content, tools, note):
    obj, protocol, message = textturn.read_reply(content)
    assert (
        protocol == "repaired"
        and [a["tool"] for a in obj["actions"]] == tools
        and note in message
    )
    if tools == ["terminal"] and "wait_s" in content:
        assert obj["actions"][0]["args"] == {"input": "ls", "wait_s": 120}
    if "Just a moment" in content:
        assert obj["analysis"] == 'the page says ("Just a moment") so retry'


def test_a_repaired_reply_runs_and_its_note_precedes_the_results(tmp_path):
    broken = (
        '{"analysis": "a", "plan": "p", "actions": [{"tool": "write_file", "args": {"path": "o.txt", '
        '"content": "hi"}, {"tool": "read_file", "args": {"path": "o.txt"}}], "task_complete": false}'
    )
    done = json.dumps(
        {"analysis": "a", "plan": "", "actions": [], "task_complete": True}
    )
    result, client, rows, work = _run(tmp_path, [broken, done])
    assert result.status == "finished" and (work / "o.txt").read_text() == "hi"
    shown = client.requests[1]["messages"][-1]["content"]
    assert (
        shown.startswith("[your reply was not valid JSON and was mended")
        and "Result of action 2 (read_file)" in shown
    )


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

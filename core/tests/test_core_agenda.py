"""The investigation agenda (study flag AETHER_CORE_AGENDA): one no-tools call whose list follows the task."""

import asyncio
from types import SimpleNamespace

from aether.core import agenda


class _Provider:
    def __init__(self, content):
        self.content, self.calls = content, []

    async def complete(self, messages, tools, **kwargs):
        self.calls.append((messages, tools, kwargs))
        return SimpleNamespace(content=self.content, usage={"input": 10, "output": 5})


def _ask(provider, task="Fix the thing.\n"):
    events = []
    text = asyncio.run(agenda.ask(provider, task, lambda: 100.0, lambda name, **row: events.append((name, row))))
    return text, events


def test_the_call_sees_only_the_question_and_the_task_and_has_no_tools():
    provider = _Provider("a -> MACHINE: look; if x then y; otherwise z")
    _ask(provider)
    (messages, tools, kwargs), = provider.calls
    assert tools is None and kwargs["role"] == agenda.ROLE and kwargs["max_tokens"] == agenda.MAX_TOKENS
    assert messages == [{"role": "user", "content": agenda.QUESTION + "Fix the thing."}]


def test_the_list_follows_the_task_under_the_legend_and_is_traced():
    text, events = _ask(_Provider("  a -> TEXT: as written\n"))
    assert text == f"\n\n{agenda.HEADER}\na -> TEXT: as written"
    (name, row), = events
    assert name == "agenda" and row["text"] == "a -> TEXT: as written" and row["empty"] is False
    assert row["usage"] == {"input": 10, "output": 5}


def test_no_list_adds_nothing_and_says_so_in_the_trace():
    text, events = _ask(_Provider(None))
    assert text == ""
    assert events[0][1]["empty"] is True


def test_the_question_asks_for_no_answer_on_machine_points_and_names_no_task():
    q = agenda.QUESTION
    assert "do not write an answer" in q and "if <outcome> then <action>; otherwise <action>" in q
    assert q.endswith("\n\n")  # the task text follows directly


# --- in the loop: flag off changes nothing; flag on makes one extra no-tools call and the list follows the task

from aether.core.loop import CoreConfig, Trace, run_agent  # noqa: E402
from aether.core.provider import ChatProvider  # noqa: E402
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk  # noqa: E402

TASK = "Create /app/out.txt containing hello."
LIST = "where out.txt goes -> TEXT: /app/out.txt as written"


def _loop(tmp_path, mode):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient(
        [call("finish", {"summary": "done"}, "c1")],
        text_script=[[chunk(content=LIST), chunk(finish="stop"), chunk(usage={"prompt_tokens": 400, "completion_tokens": 30})]],
    )
    provider = ChatProvider(client, model="glm", params={})
    result = asyncio.run(
        run_agent(env=LocalEnv(work), task=TASK, workdir=str(work), provider=provider, timeout_s=600.0,
                  trace=Trace(tmp_path / "trace.jsonl"), config=CoreConfig(agenda=mode, start_copy=False))
    )
    import json
    rows = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return result, rows, client.requests


def _task_message(request):
    return next(m["content"] for m in request["messages"] if m["role"] == "user")


def test_flag_off_makes_no_extra_call_and_leaves_the_task_message_alone(tmp_path):
    result, rows, requests = _loop(tmp_path, "off")
    assert result.status == "finished" and len(requests) == 1
    assert agenda.HEADER not in _task_message(requests[0]) and not [r for r in rows if r["event"] == "agenda"]


def test_flag_on_asks_first_without_tools_then_carries_the_list_after_the_task(tmp_path):
    result, rows, requests = _loop(tmp_path, "on")
    assert result.status == "finished" and len(requests) == 2
    assert "tools" not in requests[0] and requests[0]["messages"] == [{"role": "user", "content": agenda.QUESTION + TASK}]
    message = _task_message(requests[1])
    assert message.startswith(f"{TASK}\n\n{agenda.HEADER}\n{LIST}\n\n(Working directory:")
    assert [r["text"] for r in rows if r["event"] == "agenda"] == [LIST]
    assert result.sub_usage.get("input") == 400  # the extra call is counted, apart from the solver's own usage


# --- consensus mode: five lists, one merge; a missing list means no agenda


class _Seq:
    def __init__(self, contents):
        self.contents, self.calls = list(contents), []

    async def complete(self, messages, tools, **kwargs):
        self.calls.append(messages[0]["content"])
        return SimpleNamespace(content=self.contents[len(self.calls) - 1], usage={"input": 10, "output": 5})


def _consensus(contents):
    provider, events = _Seq(contents), []
    text = asyncio.run(agenda.ask(provider, "T", lambda: 100.0, lambda name, **row: events.append((name, row)), "consensus"))
    return text, events, provider


def test_consensus_asks_five_times_then_merges_the_models_own_lists():
    text, events, provider = _consensus(["L1", "L2", "L3", "L4", "L5", "kept -> TEXT: x"])
    assert len(provider.calls) == agenda.LISTS + 1 and provider.calls[:5] == [agenda.QUESTION + "T"] * 5
    assert provider.calls[5].startswith(agenda.MERGE) and "List 1:\nL1" in provider.calls[5] and "List 5:\nL5" in provider.calls[5]
    assert "T" not in provider.calls[5].replace(agenda.MERGE, "").replace("List", "").replace("L", "").replace("TEXT", "")  # no task text
    assert text == f"\n\n{agenda.HEADER}\nkept -> TEXT: x"
    row = events[0][1]
    assert row["mode"] == "consensus" and row["lists"] == ["L1", "L2", "L3", "L4", "L5"] and row["usage"] == {"input": 60, "output": 30}


def test_consensus_with_a_missing_list_adds_nothing_and_does_not_merge():
    text, events, provider = _consensus(["L1", "", "L3", "L4", "L5"])
    assert text == "" and len(provider.calls) == agenda.LISTS and events[0][1]["empty"] is True


def test_the_merge_rule_is_four_of_five_on_substance_and_adds_nothing():
    m = agenda.MERGE
    assert "at least four of the five lists agree in substance" in m and "Do not add points" in m
    assert "keep the check alone" in m and m.endswith("\n\n")

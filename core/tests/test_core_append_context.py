"""Context "append": the history is never edited between cuts, so every request extends the previous one.

Through the real loop. Checks: below the threshold each request is the previous one plus new messages (the prompt
cache keeps the whole prefix), with no model-edit doc, no history tools and no nudges; over the threshold one
summary call replaces the older turns, the newest turns come back verbatim starting at an assistant turn, and the
requests extend again after the cut. Known-bads: the stock "project" view shortens old results, so the prefix check
fails on it; a failed summary call ends the run as a context error, never a silent drop.
"""

import asyncio
import json

import pytest

from aether.core import context_append_policies
from aether.core.clm import ClmSettings
from aether.core.context_append import AppendPolicy
from aether.core.context_append_policies import _core_insert
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk

BIG = "python3 -c \"print('x' * 9000)\""


async def _summary(provider, task, older, previous, *, remaining_s):
    turn = await provider.complete([{"role": "user", "content": "summarise"}], None, max_tokens=100,
                                   remaining_s=remaining_s, role="checkpoint")
    return turn.content, turn.usage


def text(content):
    return [chunk(content=content), chunk(finish="stop"),
            chunk(usage={"prompt_tokens": 10, "completion_tokens": 5})]


@pytest.fixture
def small_policy(monkeypatch):
    policy = AppendPolicy("tiny", lambda w: 4_000, 1_200, _summary, _core_insert, "test")
    monkeypatch.setitem(context_append_policies.POLICIES, "tiny", policy)


def run(tmp_path, n, context="append", text_script=None):
    work = tmp_path / "work"
    work.mkdir()
    steps = [call("terminal", {"input": BIG}, f"c{i}") for i in range(n)]
    client = ScriptedClient([*steps, call("finish", {"summary": "done."}, "done")], text_script=text_script)
    extra = ({"append_policy": "tiny", "context_window": 32_000, "clm": ClmSettings(replay_reasoning="all")}
             if context == "append" else {})
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Print it.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=120, config=CoreConfig(context=context, control_dir=str(tmp_path / "control"), **extra)))
    worker = [r for r in client.requests if "tools" in r]
    return result, client, worker


def extends(a, b):
    return len(b) > len(a) and json.dumps(b[: len(a)]) == json.dumps(a)


def test_requests_only_grow_at_the_end_below_the_threshold(tmp_path, small_policy):
    result, client, worker = run(tmp_path, 2)
    assert result.status == "finished"
    assert all(extends(a["messages"], b["messages"]) for a, b in zip(worker, worker[1:]))
    names = [t["function"]["name"] for t in worker[0]["tools"]]
    assert "read_history" not in names
    system = worker[0]["messages"][0]["content"]
    assert "You manage it yourself" not in system
    assert not any("context" in json.dumps(m).lower() and "budget" in json.dumps(m).lower()
                   for m in worker[-1]["messages"][2:])  # no nudge


def test_over_the_threshold_one_summary_replaces_older_turns_and_extension_resumes(tmp_path, small_policy):
    result, client, worker = run(tmp_path, 8, text_script=[text("SUMMARY-OF-OLDER"), text("SUMMARY-2")])
    assert result.status == "finished", result.error
    events = [json.loads(x) for x in (tmp_path / "trace.jsonl").read_text().splitlines()]
    cuts = [e for e in events if e["event"] == "context_append_cut" and e["ok"]]
    assert cuts and all(e["tokens"] < e["tokens_before"] for e in cuts)
    after = [r for r in worker if any("SUMMARY-" in json.dumps(m) for m in r["messages"])]
    assert after
    first = after[0]["messages"]
    assert "SUMMARY-OF-OLDER" in first[2]["content"] and first[3]["role"] == "assistant"
    breaks = sum(not extends(a["messages"], b["messages"]) for a, b in zip(worker, worker[1:]))
    assert breaks == len(cuts)  # the prefix breaks only at a cut


def test_known_bad_project_view_edits_the_middle(tmp_path):
    _, _, worker = run(tmp_path, 16, context="project")
    assert not all(extends(a["messages"], b["messages"]) for a, b in zip(worker, worker[1:]))


def test_failed_summary_is_a_context_error_not_a_silent_drop(tmp_path, small_policy):
    result, _, _ = run(tmp_path, 8, text_script=[RuntimeError("summary down")])
    assert result.status == "context_error" and "append summary failed" in result.error


def test_append_needs_a_known_policy_and_the_window():
    with pytest.raises(ValueError, match="context_window"):
        CoreConfig(context="append", clm=ClmSettings(replay_reasoning="all"))
    with pytest.raises(ValueError, match="append_policy"):
        CoreConfig(context="append", context_window=272_000, append_policy="nope", clm=ClmSettings(replay_reasoning="all"))


@pytest.fixture
def index_policy(monkeypatch):
    policy = AppendPolicy("tinyidx", lambda w: 4_000, 1_200, _summary, _core_insert, "test", index=True)
    monkeypatch.setitem(context_append_policies.POLICIES, "tinyidx", policy)


def test_index_saves_every_cut_away_result_exactly_and_lists_it(tmp_path, index_policy):
    work = tmp_path / "work"
    work.mkdir()
    steps = [call("terminal", {"input": f"python3 -c \"print('r{i}' * 3000)\""}, f"c{i}") for i in range(8)]
    client = ScriptedClient([*steps, call("finish", {"summary": "done."}, "done")],
                            text_script=[text("S1"), text("S2"), text("S3")])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Print it.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=120, config=CoreConfig(context="append", append_policy="tinyidx", context_window=32_000,
                                         clm=ClmSettings(
                                             replay_reasoning="all"),
                                         control_dir=str(tmp_path / "control"))))
    assert result.status == "finished", result.error
    worker = [r for r in client.requests if "tools" in r]
    last = worker[-1]["messages"][2]["content"]
    assert "Earlier tool results, saved in full:" in last
    lines = [ln for ln in last.splitlines() if ln.startswith("- terminal(")]
    assert lines
    shown = {m["tool_call_id"]: m["content"] for r in worker for m in r["messages"] if m["role"] == "tool"}
    for ln in lines:
        path = ln.split(" -> ")[1].split(" (", 1)[0]
        saved = (tmp_path / "control" / "evidence" / path.rsplit("/", 1)[1]).read_text()
        assert saved in shown.values()  # the file is exactly a result the model was shown
        head = next(x.strip() for x in saved.splitlines() if x.strip())[:97]
        assert f'; first: {json.dumps(head)[:-1]}' in ln  # the preview is the file's own first line


def test_none_replay_never_sends_reasoning_and_requests_still_extend(tmp_path, small_policy):
    from aether.core.clm import ClmSettings

    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([call("terminal", {"input": "echo hi"}, "c0", reasoning="SECRET-THOUGHT"),
                             call("finish", {"summary": "done."}, "done", reasoning="SECRET-THOUGHT")])
    asyncio.run(run_agent(
        env=LocalEnv(work), task="Say hi.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=60, config=CoreConfig(context="append", append_policy="tiny", context_window=32_000,
                                        clm=ClmSettings(replay_reasoning="none"),
                                        control_dir=str(tmp_path / "control"))))
    assert "SECRET-THOUGHT" not in json.dumps(client.requests[-1]["messages"])
    assert "SECRET-THOUGHT" in (tmp_path / "trace.jsonl").read_text()  # still recorded


def test_known_bad_all_replay_does_send_reasoning(tmp_path, small_policy):
    from aether.core.clm import ClmSettings

    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([call("terminal", {"input": "echo hi"}, "c0", reasoning="SECRET-THOUGHT"),
                             call("finish", {"summary": "done."}, "done")])
    asyncio.run(run_agent(
        env=LocalEnv(work), task="Say hi.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=60, config=CoreConfig(context="append", append_policy="tiny", context_window=32_000,
                                        clm=ClmSettings(replay_reasoning="all"),
                                        control_dir=str(tmp_path / "control"))))
    assert "SECRET-THOUGHT" in json.dumps(client.requests[-1]["messages"])


def test_append_refuses_newest_replay():
    from aether.core.clm import ClmSettings

    with pytest.raises(ValueError, match="'all' or 'none'"):
        CoreConfig(context="append", context_window=272_000, clm=ClmSettings(replay_reasoning="newest"))

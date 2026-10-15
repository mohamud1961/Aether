"""The requirement ledger: requirement sentences found in the task text, quotes bound to it, coverage, citations, and
the one hold at the first finish. Known-bads from the wrong-finish study: a stated rule no item addresses (net-fit's
tie rule), a paraphrase standing in for the task's words, a requirement marked met with nothing shown."""

from __future__ import annotations

import asyncio

from aether.core import ledger as L
from aether.core.calls import CallLog
from aether.core.clm import ClmSettings
from aether.core.evidence import Step
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core.core_fakes import LocalEnv, ScriptedClient
from tests.core.test_core_verify import _turn

TASK = """Write a file colour.txt in the working directory.
Here is what you need to know:
  - The file must contain one colour name and nothing else
  - When the colour is not clear, you
may assume the colour of the sky is meant.
The criteria:
    1. It is lower case.
```
blue
```
Thanks for your help."""

TIE = "may assume the colour of the sky is meant"


def test_requirement_sentences_are_bullets_numbered_items_and_sentences_with_a_requirement_word():
    found = L.sentences(TASK)
    assert (
        found
        == [
            "Write a file colour.txt in the working directory.",
            "Here is what you need to know:",  # a header with a requirement word: listed (over-inclusion is cheap)
            "The file must contain one colour name and nothing else",
            "When the colour is not clear, you may assume the colour of the sky is meant.",
            "It is lower case.",
        ]
    ), found


def test_quotes_must_be_the_task_s_words_and_coverage_lists_what_no_item_quotes():
    items = [
        {
            "quote": "must contain one colour name",
            "reading": "one word",
            "status": "open",
        },
        # a paraphrase is not the task's words
        {
            "quote": "use the sky colour when unclear",
            "reading": "blue",
            "status": "open",
        },
    ]
    row = L.check(TASK, items, {})
    assert row["not_found"] == ["use the sky colour when unclear"]
    assert any(TIE in u for u in row["uncovered"])
    assert (
        "The file must contain one colour name and nothing else" not in row["uncovered"]
    )
    items[1]["quote"] = (
        "you\n  may ASSUME the colour of the sky is meant"  # whitespace and case aside
    )
    assert not any(TIE in u for u in L.check(TASK, items, {})["uncovered"])


def test_a_requirement_marked_met_must_cite_steps_that_show_it():
    steps = {
        1: Step("terminal"),
        2: Step("terminal", failed=True),
        3: Step("write_file", wrote="/w/c"),
    }
    items = [
        {
            "quote": "It is lower case.",
            "reading": "",
            "status": "met",
            "shown_by": "checked",
        },
        {
            "quote": "It is lower case.",
            "reading": "",
            "status": "met",
            "shown_by": "x [step 2]",
        },
        {
            "quote": "It is lower case.",
            "reading": "",
            "status": "met",
            "shown_by": "x [step 3]",
        },
        {
            "quote": "It is lower case.",
            "reading": "",
            "status": "met",
            "shown_by": "x [step 1]",
        },
    ]
    problems = L.check(TASK, items, steps)["citation_problems"]
    assert len(problems) == 3
    assert (
        "cites no step" in problems[0]
        and "failed" in problems[1]
        and "only file writes" in problems[2]
    )


def _run(tmp_path, script, ledger=True, timeout_s=900):
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir(parents=True)
    ctl.mkdir()
    client = ScriptedClient(script)
    provider = ChatProvider(
        client, model="scripted", params={}, log=CallLog(tmp_path / "calls.jsonl")
    )
    config = CoreConfig(
        control_dir=str(ctl),
        ledger=ledger,
        clm=ClmSettings(
            mirror_path=f"{ctl}/ctx/LIVE_CTX.txt", history_path=f"{ctl}/ctx/HISTORY.txt"
        ),
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task=TASK,
            workdir=str(work),
            provider=provider,
            timeout_s=timeout_s,
            trace=Trace(tmp_path / "logs" / "core_trace.jsonl"),
            config=config,
        )
    )
    return result, client


def _results(client, n):
    return [m for m in client.requests[n]["messages"] if m["role"] == "tool"]


def test_the_first_finish_is_held_once_for_an_unaddressed_stated_rule_and_the_next_ends_the_work(
    tmp_path,
):
    partial = {
        "items": [
            {
                "quote": "Write a file colour.txt",
                "reading": "",
                "status": "met",
                "shown_by": "ls [step 2]",
            },
            {
                "quote": "must contain one colour name and nothing else",
                "reading": "",
                "status": "met",
                "shown_by": "cat [step 2]",
            },
            {
                "quote": "It is lower case.",
                "reading": "",
                "status": "met",
                "shown_by": "cat [step 2]",
            },
        ]
    }
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "red\n"}, "s1"),
        _turn("terminal", {"input": "cat colour.txt"}, "s2"),
        _turn("requirements", partial, "s3"),
        _turn("finish", {"summary": "done"}, "s4"),
        _turn("finish", {"summary": "done anyway"}, "s5"),
    ]
    result, client = _run(tmp_path, script)
    ledger_result = _results(client, 3)[-1]["content"]
    assert "no item quotes" in ledger_result and TIE in ledger_result
    held = _results(client, 4)[-1]["content"]
    assert (
        held.startswith("[requirements check: the finish did not take effect]")
        and TIE in held
    )
    assert result.status == "finished" and result.steps == 5
    rows = result.extras["ledger"]
    assert [r["shown"] for r in rows] == [True, False] and rows[0]["items"] == 3


def test_a_complete_ledger_does_not_hold_and_off_means_no_tool(tmp_path):
    full = {
        "items": [
            {"quote": q, "reading": "", "status": "met", "shown_by": "cat [step 2]"}
            for q in L.sentences(TASK)
        ]
    }
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("terminal", {"input": "cat colour.txt"}, "s2"),
        _turn("requirements", full, "s3"),
        _turn("finish", {"summary": "done"}, "s4"),
    ]
    result, client = _run(tmp_path, script)
    assert result.status == "finished" and result.steps == 4
    assert result.extras["ledger"][0]["shown"] is False
    names = [t["function"]["name"] for t in client.requests[0]["tools"]]
    assert "requirements" in names and "step 1;" in _results(client, 1)[-1]["content"]
    off, client = _run(
        tmp_path / "off", [_turn("finish", {"summary": "done"}, "s1")], ledger=False
    )
    assert "requirements" not in [
        t["function"]["name"] for t in client.requests[0]["tools"]
    ]
    assert "ledger" not in off.extras

"""Which acceptance checks may hold a finish (``qualify``): grounded in the task's words, accepting the writer's
invented finished state, rejecting a violation of it. Known-bads, each from A1 (13 Oct): a check resting on an
invented fact (``*.bin``), a check too weak to tell a violation apart, a check that re-implements nothing but calls
a tool the task names and the work installs (kept as pending, not dropped)."""

from __future__ import annotations

import asyncio

from aether.core import contract as C
from aether.core import qualify as Q
from tests.core.core_fakes import call
from tests.core.test_core_contract import EXAMPLE, LEN5, LOWER, FakeClone, _provider

TASK = (
    "Write a word of exactly 5 letters into out.txt in the working directory.\nUse lowercase letters only.\n"
    "The output of the wordcheck tool is the ground truth for whether it is a word."
)
WEAK = "test -s out.txt"  # exists and is non-empty: cannot tell 4 letters from 5
WORDCHECK = "wordcheck out.txt"


def _submit(checks, call_id="s1"):
    return call(
        "submit_checks",
        {
            "checks": [
                {
                    "requirement": r,
                    "command": cmd,
                    "sentences": s,
                    "anchors": a,
                    "violation": v,
                }
                for r, cmd, s, a, v in checks
            ],
            "context_sentences": [],
            "example": EXAMPLE,
        },
        call_id,
    )


def _write(tmp_path, checks):
    root = tmp_path / "pristine"
    root.mkdir()
    provider, _ = _provider([_submit(checks)])
    return asyncio.run(C.write(provider, FakeClone(root), task=TASK, workdir=str(root)))


def test_a_grounded_check_that_rejects_its_violation_is_hard_and_the_others_are_advisory(
    tmp_path,
):
    contract = _write(
        tmp_path,
        [
            (
                "5 letters",
                LEN5,
                [1],
                ["exactly 5 letters", "out.txt"],
                "printf 'abcd' > out.txt",
            ),
            # same check, but relying on something the task does not say
            (
                "5 letters",
                LEN5,
                [1],
                ["exactly 5 letters", "out.bin"],
                "printf 'abcd' > out.txt",
            ),
            # too weak: passes the violation
            (
                "lowercase",
                WEAK,
                [2],
                ["lowercase letters only"],
                "printf 'ABCDE' > out.txt",
            ),
            (
                "lowercase",
                LOWER,
                [2],
                ["lowercase letters only"],
                "printf 'ABCDE' > out.txt",
            ),
            ("word", WORDCHECK, [3], ["wordcheck"], ""),
        ],
    )
    assert [c.hard for c in contract.checks] == [True, False, False, True, False]
    rows = {d["check"]: d for d in contract.dispositions}
    assert "out.bin" in rows[2]["reason"]
    assert (
        rows[3]["rejects_violation"] is False
        and "passes the violation" in rows[3]["reason"]
    )
    # the task names wordcheck; it is not installed before the work, so the check is kept, pending, advisory
    assert contract.checks[4].pending == "wordcheck" and "pending" in rows[5]["reason"]


def test_a_missing_tool_the_task_does_not_name_is_still_sent_back(tmp_path):
    assert Q.pending_tool(127, "sh: 1: nosuchtool: not found", TASK) == ""
    assert Q.pending_tool(127, "sh: 1: wordcheck: not found", TASK) == "wordcheck"
    assert Q.pending_tool(1, "assertion failed", TASK) == ""


def test_anchors_must_be_the_tasks_words_and_at_least_one_is_needed():
    assert Q.grounded(["EXACTLY  5\nletters"], TASK) == (True, [])
    assert Q.grounded([], TASK) == (False, [])
    # quote style and wrapping quotes aside (Q1: GPT-6-Luna wrapped every anchor in curly quotes)
    assert Q.grounded(
        ["\u201cUse lowercase letters only.\u201d", "'out.txt'"], TASK
    ) == (True, [])
    assert Q.grounded(["\u201cUse UPPERCASE letters only.\u201d"], TASK)[0] is False
    assert Q.grounded(["exactly 5 letters", "23 characters"], TASK) == (
        False,
        ["23 characters"],
    )


def test_a_check_with_its_own_perl_syntax_error_cannot_run_and_is_not_a_failure():
    out = "syntax error at -e line 1, at EOF\nExecution of -e aborted due to compilation errors."
    assert C._cannot_run(255, out) and not Q._failed(255, out)
    assert Q._failed(1, "length 14 != 23")

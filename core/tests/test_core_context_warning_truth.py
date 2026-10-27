"""The context warnings state what happens at the limit, and the whole request size (10-27 Flint board)."""

from __future__ import annotations

from aether.core import compaction
from aether.core.clm import ClmContext, ClmSettings

PINNED = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]


def _near_limit(replay: str = "all") -> ClmContext:
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000, replay_reasoning=replay))
    ctx.append({"role": "user", "content": "tool output " * 7500})
    thought = {"role": "assistant", "content": None, "reasoning_content": "r" * 1000}
    ctx.append(thought)
    ctx.note_reasoning(thought, 20000)
    return ctx


def test_the_urgent_nudge_says_the_run_continues_and_counts_the_replayed_reasoning():
    ctx = _near_limit()
    note = ctx.nudge()
    assert note.startswith("[context: urgent]")
    assert "The run continues after that" in note and "not a time or turn limit" in note
    assert f"about {ctx.tokens()} tokens: 20000 of them are your earlier reasoning" in note


def test_the_urgent_nudge_leaves_out_the_reasoning_clause_when_none_is_replayed():
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000))
    ctx.append({"role": "user", "content": "tool output " * 7500})
    note = ctx.nudge()
    assert note.startswith("[context: urgent]") and "earlier reasoning" not in note


def test_the_75_percent_nudge_says_the_run_continues():
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000))
    ctx.append({"role": "user", "content": "tool output " * 6300})
    note = ctx.nudge()
    assert "replaced by a summary and the run continues" in note


def test_a_checkpoint_restates_the_context_size_after_it():
    ctx = _near_limit()
    ctx.append({"role": "assistant", "content": "next"})
    stale = "- Context is nearly exhausted (~29.8k/29.9k tokens)"
    ctx.replace_with_checkpoint(stale, compaction.note("legacy"), len(ctx.editable) - 1)
    head = ctx.editable[0]["content"]
    assert head.index(stale) < head.index("[context] Now, after this summary:")
    assert f"{ctx.held()} of 32000 tokens used" in head or "of 32000 tokens used" in head
    assert "predates the summary" in head


def test_both_summary_prompts_keep_context_and_time_status_out_of_the_summary():
    for prompt in (compaction.SUMMARIZATION_PROMPT, compaction.SUMMARIZATION_PROMPT_OWN):
        assert "Do not record how full the context is or how much time is left" in prompt

"""The two context numbers (B1 O1) and the cut-stream retry at the loop level; no provider calls."""

from __future__ import annotations

import asyncio
import json

import pytest

from aether.core.calls import CallLog
from aether.core.clm import ClmContext, ClmSettings
from aether.core.loop import MAX_OUTPUT_TOKENS, CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core.core_fakes import LocalEnv, ScriptedClient, call, chunk, tool_chunk

PINNED = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]


def test_o1_replay_a_cut_32k_thought_is_kept_and_the_request_exceeds_the_editable_budget_by_design():
    # B1 dna ep 2: ~7.5k held, then a turn cut at `length` after 32,768 reasoning tokens; the next request was
    # 38,707 input tokens against a 32k budget. The budget governs held context only; the thought is preserved.
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000))
    ctx.append({"role": "user", "content": "tool output " * 2400})
    thought = {"role": "assistant", "content": None, "reasoning_content": "r" * 1000}
    ctx.append(thought)
    ctx.note_reasoning(thought, 32768)
    assert not ctx.over_limit()  # no checkpoint discards the live thought
    assert ctx.held() < ctx.settings.limit < ctx.settings.budget_tokens < ctx.tokens()
    assert (
        ctx.tokens() - ctx.held() == 32768
    )  # the excess is exactly the replayed reasoning, now measurable


@pytest.mark.parametrize(
    "limit, ok", [(None, True), (131_072, True), (97_536, True), (97_535, False)]
)
def test_request_limit_is_checked_at_configuration_against_the_worst_case(limit, ok):
    settings = ClmSettings(budget_tokens=32000, request_limit_tokens=limit)
    if ok:
        CoreConfig(context="clm", clm=settings)
    else:
        with pytest.raises(ValueError, match="exceeds the provider request limit"):
            CoreConfig(context="clm", clm=settings)
    assert 32000 + 2 * MAX_OUTPUT_TOKENS == 97_536


def test_every_model_call_traces_held_and_whole_request_tokens(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=ChatProvider(
                ScriptedClient([call("finish", {"summary": "done"})]),
                model="s",
                params={},
            ),
            timeout_s=60,
            trace=Trace(tmp_path / "trace"),
            config=CoreConfig(context="clm", control_dir=str(tmp_path / "control")),
        )
    )
    rows = [json.loads(line) for line in (tmp_path / "trace").read_text().splitlines()]
    sizes = [r["context_tokens"] for r in rows if r["event"] == "model"]
    assert sizes and all(s["request"] >= s["held"] > 0 for s in sizes)


def test_a_cut_tool_call_is_retried_and_its_effect_happens_exactly_once(tmp_path):
    # GPT-6-Astra's loop-level follow-up to c7679c1cc: the cut partial call is never dispatched; only the retried one is.
    work = tmp_path / "work"
    work.mkdir()
    effect = {"input": f"echo once >> {work / 'effects.txt'}"}
    cut = [tool_chunk("terminal", effect)]  # stream ends without a finish_reason
    whole = [tool_chunk("terminal", effect), chunk(finish="tool_calls")]
    provider = ChatProvider(
        ScriptedClient([cut, whole, call("finish", {"summary": "done"}, "c2")]),
        model="s",
        params={},
        log=CallLog(tmp_path / "calls"),
        sleep=lambda s: asyncio.sleep(0),
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=60,
            trace=Trace(tmp_path / "trace"),
            config=CoreConfig(control_dir=str(tmp_path / "control")),
        )
    )
    assert result.status == "finished"
    assert (work / "effects.txt").read_text() == "once\n"
    assert provider.log.totals()["all"]["failed"] == 1

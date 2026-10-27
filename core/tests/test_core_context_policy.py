"""Context-policy study (2026-10-27): the ``segment`` replay mode and the provider reasoning wire. No provider calls."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from aether.core import reasoning_wire as wire
from aether.core.clm import ClmContext, ClmSettings
from aether.core.harbor_agent import ConfigError, build_config, build_provider
from aether.core.provider import ChatProvider, Turn
from tests.core_fakes import ScriptedClient, chunk, tool_chunk

PINNED = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]


def _ctx(mode: str) -> ClmContext:
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000, replay_reasoning=mode))
    for i in range(3):
        msg = {"role": "assistant", "content": None, "reasoning_content": f"r{i}" * 500}
        ctx.append(msg)
        ctx.note_reasoning(msg, 4000)
        ctx.append({"role": "user", "content": "out"})
    newest = {"role": "assistant", "content": None, "reasoning_content": "n" * 500}
    ctx.append(newest)
    ctx.note_reasoning(newest, 5000)
    return ctx


def test_all_and_segment_replay_the_same_request_newest_drops_older_reasoning():
    seg, alll, newest = _ctx("segment"), _ctx("all"), _ctx("newest")
    assert seg.request() == alll.request()
    kept = [m for m in newest.request() if m.get("reasoning_content")]
    assert len(kept) == 1 and kept[0]["reasoning_content"] == "n" * 500


def test_segment_budget_counts_older_reasoning_but_not_the_newest_turn():
    seg, alll = _ctx("segment"), _ctx("all")
    assert seg.tokens() == alll.tokens()
    assert alll.tokens() - alll.held() == 3 * 4000 + 5000  # "all": no replayed reasoning is counted (the defect)
    assert seg.tokens() - seg.held() == 5000  # segment: only the live newest thought is outside the budget


def test_segment_makes_a_checkpoint_fire_where_all_does_not():
    seg, alll = _ctx("segment"), _ctx("all")
    for ctx in (seg, alll):
        for _ in range(4):
            m = {"role": "assistant", "content": None, "reasoning_content": "x"}
            ctx.append(m)
            ctx.note_reasoning(m, 6000)
            ctx.append({"role": "user", "content": "out"})
    assert seg.over_limit() and not alll.over_limit()


def test_segment_is_refused_without_model_managed_context():
    base = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off",
            "AETHER_CORE_REASONING": "segment"}
    assert build_config(environ={**base, "AETHER_CORE_CONTEXT": "clm"}).clm.replay_reasoning == "segment"
    with pytest.raises(ConfigError, match="AETHER_CORE_REASONING=segment needs"):
        build_config(environ={**base, "AETHER_CORE_CONTEXT": "project"})


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("reasoning_content", {"role": "assistant", "content": "a", "reasoning_content": "R"}),
        ("reasoning", {"role": "assistant", "content": "a", "reasoning": "R"}),
        ("think_tags", {"role": "assistant", "content": "<think>R</think>\n\na"}),
        ("reasoning_details", {"role": "assistant", "content": "a", "reasoning_details": "R"}),
    ],
)
def test_outgoing_moves_reasoning_to_the_provider_field(mode, expected):
    msgs = [{"role": "user", "content": "u"}, {"role": "assistant", "content": "a", "reasoning_content": "R"}]
    assert wire.outgoing(mode, msgs) == [msgs[0], expected]
    assert msgs[1] == {"role": "assistant", "content": "a", "reasoning_content": "R"}  # input not mutated


def test_outgoing_leaves_an_assistant_turn_without_reasoning_alone():
    msgs = [{"role": "assistant", "content": "a"}]
    for mode in wire.WIRES:
        assert wire.outgoing(mode, msgs) == msgs


def _delta(**fields):
    return SimpleNamespace(content=None, reasoning_content=fields.pop("reasoning_content", None), tool_calls=None,
                           model_extra=fields)


def test_read_delta_takes_only_the_configured_field():
    t = Turn()
    wire.read_delta("reasoning", _delta(reasoning="abc", reasoning_content="zzz"), t)
    assert t.reasoning == "abc"
    t = Turn()
    wire.read_delta("reasoning_content", _delta(reasoning="abc", reasoning_content="zzz"), t)
    assert t.reasoning == "zzz"
    t = Turn()
    wire.read_delta("reasoning_details", _delta(reasoning_details=[{"type": "reasoning.encrypted", "data": "x"}]), t)
    assert t.reasoning_items == [{"type": "reasoning.encrypted", "data": "x"}] and t.reasoning == ""
    assert t.assistant_message()["reasoning_content"] == t.reasoning_items


@pytest.mark.parametrize(
    "content, reasoning, rest",
    [
        ("<think>plan it</think>\n\nanswer", "plan it", "answer"),
        ("plan it</think>answer", "plan it", "answer"),  # opening tag in the template, not the output
        ("no tags here", "", "no tags here"),
        ("<think>run git log first\n", "run git log first\n", ""),  # tool-call turn: no closing tag
    ],
)
def test_finish_splits_inline_think_tags(content, reasoning, rest):
    t = Turn(content=content)
    wire.finish("think_tags", t)
    assert (t.reasoning, t.content) == (reasoning, rest)
    t = Turn(content=content)
    wire.finish("reasoning", t)
    assert t.content == content  # other wires never touch content


def test_provider_round_trip_think_tags_policy_controls_replay():
    stream = [chunk(content="<think>check the file</think>\n\n"), tool_chunk("terminal", {"input": "ls"}),
              chunk(finish="tool_calls", usage={"prompt_tokens": 10, "completion_tokens": 5})]
    client = ScriptedClient([stream])
    p = ChatProvider(client, model="m", params={}, reasoning_wire="think_tags")
    turn = asyncio.run(p.complete([{"role": "user", "content": "go"}], [], max_tokens=100, remaining_s=lambda: 60.0))
    assert turn.reasoning == "check the file" and turn.content == ""
    msg = turn.assistant_message()
    assert msg["reasoning_content"] == "check the file"
    sent = p._request([msg], [], 100, None)["messages"][0]
    assert sent["content"].startswith("<think>check the file</think>") and "reasoning_content" not in sent


def test_default_wire_is_unchanged_and_an_unknown_wire_stops_the_run():
    env = {"AETHER_FW_GLM_53_FLASH_ENDPOINT": "https://x.example/v1", "AETHER_FW_GLM_53_FLASH_KEY": "k",
           "AETHER_FW_GLM_53_FLASH_DEPLOYMENT": "m", "AETHER_CORE_API": "openai"}
    assert build_provider(environ=env).reasoning_wire == "reasoning_content"
    assert build_provider(environ={**env, "AETHER_CORE_REASONING_WIRE": "think_tags"}).reasoning_wire == "think_tags"
    with pytest.raises(ConfigError):
        build_provider(environ={**env, "AETHER_CORE_REASONING_WIRE": "bogus"})

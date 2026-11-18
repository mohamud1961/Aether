"""Context study arms (16 Nov) and context fault injection.

Arms: Meta's published CLM defaults (AETHER_CORE_CLM_PROFILE=meta: nudges 25/50/75, urgent every turn, roll back
the newest turns until 2048 tokens are free, no summary, one final turn then stop) and the lossless append policy
(one cut near the window, every cut-away result saved and listed). Faults: the mirror cannot be written, an index
file cannot be saved, the context stays over its limit after the final turn. Each fault must surface honestly.
"""

import asyncio
import json
import re
from types import SimpleNamespace

import pytest

from aether.core import context_append_policies, loop_context
from aether.core import harbor_config as hc
from aether.core.clm import ClmContext, ClmSettings
from aether.core.clm_settings import META_PROFILE
from aether.core.context_append import AppendPolicy
from aether.core.context_append_policies import _core_insert
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk

BASE = {hc.REVIEW_ENV: "off", hc.CONTEXT_ENV: "clm", hc.REPL_ENV: "off", hc.IMAGES_ENV: "on"}


# --- configuration -----------------------------------------------------------------------------------------------

def test_profile_is_core_by_default_and_meta_sets_the_published_defaults():
    core = hc.build_config(environ=BASE).clm
    assert (core.nudge_ratios, core.urgent_every_turns, core.max_rollbacks, core.rollback_margin_tokens,
            core.checkpoint_policy) == ((0.5, 0.75), 3, 0, 0, "summary")
    meta = hc.build_config(environ={**BASE, "AETHER_CORE_CLM_PROFILE": "meta"}).clm
    assert {k: getattr(meta, k) for k in META_PROFILE} == META_PROFILE
    assert meta.budget_tokens == 32_000 and meta.reserve_tokens == 2_048  # Meta's CLI default budget and reserve


def test_meta_profile_refuses_a_second_checkpoint_policy_and_non_clm_context():
    with pytest.raises(hc.ConfigError, match="its own checkpoint policy"):
        hc.build_config(environ={**BASE, "AETHER_CORE_CLM_PROFILE": "meta", hc.CHECKPOINT_POLICY_ENV: "summary"})
    with pytest.raises(hc.ConfigError):
        hc.build_config(environ={**BASE, "AETHER_CORE_CLM_PROFILE": "pure"})
    with pytest.raises(hc.ConfigError, match="needs AETHER_CORE_CONTEXT=clm"):
        hc.build_config(environ={**BASE, hc.CONTEXT_ENV: "append", "AETHER_CORE_CONTEXT_WINDOW": "272000",
                                 "AETHER_CORE_REASONING": "all", "AETHER_CORE_CLM_PROFILE": "meta"})


def test_lossless_policy_cuts_near_the_window_and_indexes():
    policy = context_append_policies.POLICIES["lossless"]
    assert policy.threshold(272_000) == 231_200 and policy.index and policy.keep_recent_tokens == 40_000


def test_default_nudge_text_is_unchanged_and_meta_text_is_truthful():
    def at(ratio_tokens, policy):
        ctx = ClmContext(pinned=[], settings=ClmSettings(budget_tokens=10_000, reserve_tokens=0,
                                                         checkpoint_policy=policy, nudge_ratios=(0.75,)))
        ctx.chars_per_token = 1.0
        ctx.append({"role": "user", "content": "x" * ratio_tokens})
        return ctx.nudge()
    assert at(6_200, "summary").endswith("above the limit older turns are replaced by a summary and the run continues.")
    assert ("left before older turns are replaced by a summary. The run continues after that: this is not a time or "
            "turn limit. Condense") in at(9_000, "summary")  # the stock urgent text, byte for byte
    stop = at(6_200, "stop")
    assert "your newest turn is rolled back" in stop and "still cannot fit after that stops" in stop
    assert "summary" not in stop


# --- the final turn (fault: still over the limit) ----------------------------------------------------------------

def fake_session(tmp_path, held_chars):
    ctx = ClmContext(pinned=[{"role": "system", "content": "s"}],
                     settings=ClmSettings(budget_tokens=10_000, reserve_tokens=0, max_rollbacks=0,
                                          checkpoint_policy="stop", mirror_path=str(tmp_path / "LIVE.txt")))
    ctx.chars_per_token = 1.0
    ctx.append({"role": "user", "content": "x" * held_chars})
    rows = []
    s = SimpleNamespace(clm=ctx, rehydrate_due=False, state=None, record=None,
                        result=SimpleNamespace(extras={}, steps=4, status="running", error=None),
                        trace=lambda event, **kw: rows.append({"event": event, **kw}))
    return s, rows


def test_over_the_limit_with_no_rollback_gets_one_final_turn_then_stops(tmp_path):
    s, rows = fake_session(tmp_path, 12_000)
    assert asyncio.run(loop_context._fit_context(s)) is True  # the final turn is given
    assert "the run stops" in json.dumps(s.clm.editable) and s.result.status == "running"
    assert asyncio.run(loop_context._fit_context(s)) is False  # still over at the next request
    assert s.result.status == "context_error" and "after its final turn" in s.result.error
    assert [r["phase"] for r in rows if r["event"] == "context_final_turn"] == ["given", "stop"]
    assert not [r for r in rows if r["event"] == "context_checkpoint"]  # no summary is ever written


def test_a_model_that_condenses_in_its_final_turn_continues_and_is_warned_afresh_later(tmp_path):
    s, rows = fake_session(tmp_path, 12_000)
    assert asyncio.run(loop_context._fit_context(s)) is True
    s.clm.editable[:] = [{"role": "user", "content": "condensed"}]  # the model's mirror edit
    assert asyncio.run(loop_context._fit_context(s)) is True and "context_final_turn" not in s.result.extras
    s.clm.append({"role": "user", "content": "y" * 12_000})  # over again much later: a new final turn, not a stop
    assert asyncio.run(loop_context._fit_context(s)) is True and s.result.status == "running"
    assert [r["phase"] for r in rows if r["event"] == "context_final_turn"] == ["given", "given"]


# --- real loop -----------------------------------------------------------------------------------------------------

def run(tmp_path, steps, config, text_script=None):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    client = ScriptedClient([*steps, call("finish", {"summary": "done."}, "done")], text_script=text_script)
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Print it.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(trace), timeout_s=120,
        config=config))
    return result, client, [json.loads(line) for line in trace.read_text().splitlines()]


def big(i, n=9000):
    return call("terminal", {"input": f"python3 -c \"print('r{i}' * {n // 2})\""}, f"c{i}")


def test_meta_profile_rolls_back_never_summarises_and_nudges_from_25_percent(tmp_path):
    settings = ClmSettings(budget_tokens=16_000, mirror_path=str(tmp_path / "ctx" / "LIVE_CTX.txt"), **META_PROFILE)
    config = CoreConfig(context="clm", clm=settings, control_dir=str(tmp_path / "ctl"))
    result, client, rows = run(tmp_path, [big(i) for i in range(12)], config)
    assert result.status == "finished", result.error
    assert [r for r in rows if r["event"] == "context_rollback"]
    assert not [r for r in rows if r["event"] == "context_checkpoint"]
    assert all("tools" in r for r in client.requests)  # no auxiliary summary call was made
    nudges = [r["note"] for r in rows if r["event"] == "context_nudge"]
    first = int(re.search(r"at (\d+)% of its", nudges[0]).group(1))
    assert 25 <= first < 50  # the 25% threshold exists (Core's stock profile starts at 50%)
    assert any("[context limit] Your newest turn was rolled back" in json.dumps(r["messages"])
               for r in client.requests)


def test_fault_mirror_cannot_be_written_the_model_is_told_and_the_run_continues(tmp_path):
    (tmp_path / "blocker").write_text("a file where the mirror's directory should be")
    config = CoreConfig(context="clm", control_dir=str(tmp_path / "ctl"),
                        clm=ClmSettings(mirror_path=str(tmp_path / "blocker" / "LIVE_CTX.txt")))
    result, client, rows = run(tmp_path, [call("terminal", {"input": "echo hi"}, "c1")], config)
    assert result.status == "finished", result.error
    assert [r for r in rows if r["event"] == "context_mirror_error"]
    tool_texts = [m["content"] for r in client.requests for m in r["messages"] if m["role"] == "tool"]
    assert any("[context mirror unavailable:" in t and "context unchanged" in t for t in tool_texts)


async def _summary(provider, task, older, previous, *, remaining_s):
    turn = await provider.complete([{"role": "user", "content": "summarise"}], None, max_tokens=100,
                                   remaining_s=remaining_s, role="checkpoint")
    return turn.content, turn.usage


def text(content):
    return [chunk(content=content), chunk(finish="stop"), chunk(usage={"prompt_tokens": 10, "completion_tokens": 5})]


def test_fault_an_index_file_cannot_be_saved_the_run_stops_honestly_and_no_cut_is_made(tmp_path, monkeypatch):
    policy = AppendPolicy("tinyidx", lambda w: 4_000, 1_200, _summary, _core_insert, "test", index=True)
    monkeypatch.setitem(context_append_policies.POLICIES, "tinyidx", policy)
    real = loop_context.put_bytes

    async def put_bytes(env, data, path):
        if "/evidence/" in path:
            raise OSError("No space left on device")
        return await real(env, data, path)
    monkeypatch.setattr(loop_context, "put_bytes", put_bytes)
    config = CoreConfig(context="append", append_policy="tinyidx", context_window=32_000,
                        clm=ClmSettings(replay_reasoning="all"), control_dir=str(tmp_path / "ctl"))
    result, client, rows = run(tmp_path, [big(i, 6000) for i in range(8)], config, text_script=[text("S1")])
    assert result.status == "context_error" and result.error.startswith("append index save failed: IndexSaveError")
    assert not [r for r in rows if r["event"] == "context_append_cut" and r.get("ok")]
    worker = [r for r in client.requests if "tools" in r]
    assert "S1" not in json.dumps(worker[-1]["messages"])  # the summary never became the only copy


# --- late reminder (AETHER_CORE_CLM_NUDGES=late) -------------------------------------------------------------------

def test_late_reminder_is_the_default_and_core_nudges_stay_selectable():
    assert hc.build_config(environ=BASE).clm.reminder_room_tokens == 2_048
    assert hc.build_config(environ={**BASE, "AETHER_CORE_CLM_NUDGES": "core"}).clm.reminder_room_tokens == 0
    assert hc.build_config(environ={**BASE, "AETHER_CORE_CLM_PROFILE": "meta"}).clm.reminder_room_tokens == 0
    with pytest.raises(hc.ConfigError):
        hc.build_config(environ={**BASE, "AETHER_CORE_CLM_NUDGES": "early"})


def test_late_reminder_fires_once_near_the_limit_and_rearms_after_room_returns():
    ctx = ClmContext(pinned=[], settings=ClmSettings(budget_tokens=10_000, reserve_tokens=0,
                                                     reminder_room_tokens=2_048))
    ctx.chars_per_token = 1.0
    ctx.append({"role": "user", "content": "x" * 1_000})  # held counts ~1,500 tokens of tool overhead too
    notes = []
    for size in (1_000, 1_500, 1_500, 1_000):  # ~35%, 50%, 65%, 75%: no ratio or urgent nudge
        ctx.append({"role": "user", "content": "x" * size})
        notes.append(ctx.nudge())
    assert notes == ["", "", "", ""]
    ctx.append({"role": "user", "content": "x" * 500})  # room now under 2,048
    first = ctx.nudge()
    assert first.startswith("[context] ") and "left before older turns are replaced by a summary" in first
    assert ctx.nudge() == ""  # once, not every turn
    ctx.editable[:] = [{"role": "user", "content": "short"}]  # the model condensed
    assert ctx.nudge() == ""
    ctx.append({"role": "user", "content": "x" * 9_500})
    assert ctx.nudge().startswith("[context] ")  # re-armed after the room came back


def test_late_reminder_in_the_real_loop_replaces_every_ratio_and_urgent_nudge(tmp_path):
    settings = ClmSettings(budget_tokens=16_000, mirror_path=str(tmp_path / "ctx" / "LIVE_CTX.txt"),
                           reminder_room_tokens=2_048)
    config = CoreConfig(context="clm", clm=settings, control_dir=str(tmp_path / "ctl"))
    result, _, rows = run(tmp_path, [big(i) for i in range(10)], config,
                          text_script=[text(f"## Goal\nS{k}") for k in range(6)])
    assert result.status == "finished", result.error
    notes = [r["note"] for r in rows if r["event"] == "context_nudge"]
    assert notes and all(n.startswith("[context] ") and "left before" in n for n in notes)
    assert not any("% of its" in n or "[context: urgent]" in n for n in notes)

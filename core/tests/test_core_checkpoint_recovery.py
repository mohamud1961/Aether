"""Checkpoint recovery (2026-10-28 audit defects D01-D03): a checkpoint must size its kept window the way the budget
counts it, a failed summary call must not end a working run, and a reported 0 next to reasoning text is not a count."""

from __future__ import annotations

import json

from aether.core.clm import ClmContext, ClmSettings
from tests.core_fakes import StatusError, call
from tests.test_core_v2 import _clm_config, _run, _text

PINNED = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]


def test_segment_kept_window_counts_older_reasoning_at_its_reported_cost():
    # Short reasoning text (encrypted or dense) that the provider counted at 4000 tokens a turn.
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000, keep_recent_tokens=3000,
                                                         replay_reasoning="segment"))
    for i in range(4):
        msg = {"role": "assistant", "content": None, "reasoning_content": f"e{i}" * 50}
        ctx.append(msg)
        ctx.note_reasoning(msg, 4000)
        ctx.append({"role": "user", "content": "out"})
    newest = max(i for i, m in enumerate(ctx.editable) if m.get("role") == "assistant")
    # Only the newest turn fits: each older one costs 4000 tokens of budget; by characters all four looked tiny.
    assert ctx.checkpoint_split() == newest
    assert ctx.window_tokens(ctx.editable[newest - 2:]) >= 4000


def test_a_reported_zero_next_to_reasoning_text_is_estimated_not_trusted():
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000, replay_reasoning="all"))
    msg = {"role": "assistant", "content": None, "reasoning_content": "t" * 3000}
    ctx.append(msg)
    ctx.note_reasoning(msg, 0)
    assert ctx._counted(msg) is None and ctx._replayed_reasoning()[1] > 500
    empty = {"role": "assistant", "content": "x"}
    ctx.append(empty)
    ctx.note_reasoning(empty, 0)
    assert ctx._counted(empty) == 0  # no reasoning text: 0 is a real count


def test_a_failed_summary_call_drops_old_turns_unsummarised_and_the_run_continues(tmp_path):
    big = "y" * 3000
    script = [call("terminal", {"input": f"echo {i}{big}"}, f"c{i}") for i in range(6)]
    script += [call("finish", {"summary": "done"}, "c9")]
    config = _clm_config(tmp_path, budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=2500)
    texts = [StatusError(400, "summary refused")] + [_text(f"## Goal\nSUMMARY-MARKER-{k}") for k in range(3)]
    result, rows, client = _run(tmp_path, script, config=config, text_script=texts)
    assert result.status == "finished", result.error
    cps = [r for r in rows if r["event"] == "context_checkpoint"]
    assert cps[0]["ok"] is False and cps[1]["ok"] is True and "No summary is available" in cps[1]["summary"]
    assert "echo 5" + "y" * 50 in json.dumps(client.requests[-1]["messages"])  # newest turn kept verbatim


def test_a_checkpoint_still_over_budget_is_fitted_instead_of_ending_the_run(tmp_path):
    big = "y" * 6000
    script = [call("terminal", {"input": f"echo {i}{big}"}, f"c{i}") for i in range(6)]
    script += [call("finish", {"summary": "done"}, "c9")]
    # The kept window (8000) alone is close to the limit (8500): with the summary on top it is over.
    config = _clm_config(tmp_path, budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=8000)
    texts = [_text("## Goal\n" + "S" * 6000) for _ in range(12)]
    result, rows, _ = _run(tmp_path, script, config=config, text_script=texts)
    assert result.status == "finished", result.error
    cps = [r for r in rows if r["event"] == "context_checkpoint" and r["ok"]]
    assert cps and all("trimmed_turns" in r for r in cps)  # fitted by trimming kept turns or cutting the summary


def test_context_budget_is_configurable_and_validated():
    import pytest

    from aether.core.harbor_agent import ConfigError, _budget

    assert _budget({}) == {}
    assert _budget({"AETHER_CORE_CONTEXT_BUDGET": "128000"}) == {"budget_tokens": 128000, "keep_recent_tokens": 32000}
    for bad in ("12000", "lots", "-5"):
        with pytest.raises(ConfigError):
            _budget({"AETHER_CORE_CONTEXT_BUDGET": bad})


def test_output_ceiling_is_configurable_and_reaches_the_request():
    import pytest

    from aether.core.harbor_agent import ConfigError, _max_output
    from aether.core.loop import CoreConfig

    assert _max_output({}) == {} and CoreConfig().max_output_tokens == 16_384
    assert _max_output({"AETHER_CORE_MAX_OUTPUT": "12288"}) == {"max_output_tokens": 12288}
    for bad in ("1000", "big"):
        with pytest.raises(ConfigError):
            _max_output({"AETHER_CORE_MAX_OUTPUT": bad})


def test_the_output_ceiling_is_what_each_turn_requests(tmp_path):
    script = [call("terminal", {"input": "echo hi"}, "c0"), call("finish", {"summary": "done"}, "c1")]
    import dataclasses

    config = dataclasses.replace(_clm_config(tmp_path), max_output_tokens=12288)
    result, _, client = _run(tmp_path, script, config=config)
    assert result.status == "finished"
    limits = {r.get("max_tokens") or r.get("max_completion_tokens") or r.get("max_output_tokens") for r in client.requests}
    assert limits == {12288}, limits


def test_chained_requests_send_only_new_items_after_the_previous_response():
    from aether.core.responses import ResponsesProvider

    p = ResponsesProvider(object(), model="m", params={}, chain=True)
    sys_ = {"role": "system", "content": "s"}
    first = [sys_, {"role": "user", "content": "task"}]
    assert p._chained(first) == {}  # nothing to chain from
    p._last = (first, "resp_1")
    turn = [{"type": "reasoning", "encrypted_content": "x"}, {"type": "function_call", "call_id": "c1", "name": "t",
                                                               "arguments": "{}"}]
    out = {"type": "function_call_output", "call_id": "c1", "output": "ok"}
    assert p._chained(first + turn + [out]) == {"input": [out], "previous_response_id": "resp_1"}
    edited = [sys_, {"role": "user", "content": "task (condensed)"}] + turn + [out]
    assert p._chained(edited) == {}  # an edited history is sent whole
    assert p._chained(first + turn) == {}  # nothing new after the turn's own output

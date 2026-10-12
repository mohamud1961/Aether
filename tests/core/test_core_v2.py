"""Aether Core v2: Python REPL (real local server), CLM context, checkpoints, reviews, retry tracing."""
from __future__ import annotations

import asyncio
import json
import os
import signal

import pytest

from aether.core import oversight as core_oversight
from aether.core.clm import ClmContext, ClmSettings
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.oversight import ReviewPlan
from aether.core.provider import ChatProvider
from aether.core.repl import Repl
from tests.core.core_fakes import LocalEnv, ScriptedClient, StatusError, call, chunk

TASK = "Create out.txt containing hello."


# ----- REPL ------------------------------------------------------------------------------------------------
async def _repl(tmp_path, llm=None):
    env = LocalEnv(tmp_path)
    repl = Repl(env, str(tmp_path), lambda: 600.0, llm, base=str(tmp_path / "repl"))
    assert await repl.start()
    return env, repl


def _stop(repl):
    if repl.pid:
        try:
            os.kill(repl.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_repl_state_persists_and_fast_cells_take_one_exec(tmp_path):
    async def go():
        env, repl = await _repl(tmp_path)
        try:
            await repl.run("data = list(range(10))\nfrom pathlib import Path")
            n = len(env.commands)
            out = await repl.run("sum(data) + 1")
            assert "46" in out and "ok" in out
            assert len(env.commands) - n == 1  # submit + wait + read in a single container call
            out = await repl.run("r = sh('echo from-shell; exit 3'); print(r.code, r.output.strip())")
            assert "3 from-shell" in out
            out = await repl.run("1/0")
            assert "ZeroDivisionError" in out and "error" in out
            assert "46" in await repl.run("sum(data) + 1")  # an error does not lose state
        finally:
            _stop(repl)
    asyncio.run(go())


def test_repl_long_cell_can_be_waited_on_and_interrupted(tmp_path):
    async def go():
        _, repl = await _repl(tmp_path)
        try:
            out = await repl.run("import time\nprint('start', flush=True)\ntime.sleep(30)", wait_s=1)
            assert "still running" in out and "start" in out
            assert "still running" in await repl.run("x = 1")  # one cell at a time, said plainly
            out = await repl.run("", interrupt=True, wait_s=5)
            assert "interrupted" in out and "KeyboardInterrupt" in out
            assert "7" in await repl.run("3 + 4")  # the REPL survives the interrupt
        finally:
            _stop(repl)
    asyncio.run(go())


def test_repl_llm_bridge_answers_on_the_host_and_errors_reach_the_cell(tmp_path):
    seen = []

    async def answer(prompt, max_tokens):
        seen.append((prompt, max_tokens))
        return f"summary of {len(prompt)} chars"

    async def go():
        _, repl = await _repl(tmp_path, answer)
        try:
            out = await repl.run("big = 'x' * 5000\nllm('summarise: ' + big, max_tokens=300)", wait_s=20)
            assert "summary of 5011 chars" in out and seen[0][1] == 300 and repl.llm_calls == 1
            out = await repl.run("llm('y' * 200_001)", wait_s=20)
            assert "RuntimeError" in out and "limit" in out and repl.llm_errors == 1
        finally:
            _stop(repl)
    asyncio.run(go())


def test_repl_reports_unavailable_without_python(tmp_path):
    class NoPython(LocalEnv):
        async def exec(self, command, cwd=None, env=None, timeout_sec=None):
            if "command -v python3" in command:
                command = "false"
            return await super().exec(command, cwd, env, timeout_sec)

    async def go():
        repl = Repl(NoPython(tmp_path), str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"))
        assert await repl.start() == ""
        with pytest.raises(RuntimeError):
            await repl.run("1")
    asyncio.run(go())


# ----- CLM context -----------------------------------------------------------------------------------------
PINNED = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]


def _turn(i, size=100):
    return [{"role": "assistant", "content": None, "tool_calls": [
                {"id": f"c{i}", "type": "function", "function": {"name": "terminal", "arguments": f'{{"input": "cmd{i}"}}'}}]},
            {"role": "tool", "tool_call_id": f"c{i}", "content": f"out{i} " + "z" * size}]


def test_clm_mirror_round_trip_and_fit_gate():
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=6000, reserve_tokens=500))
    for i in range(3):
        ctx.append(*_turn(i))
    text = ctx.render()
    assert "[[CTX_TURN 0 role=assistant]]" in text and "[tool_call terminal]" in text and "out2" in text
    parsed = ClmContext.parse(text)
    assert [m["role"] for m in parsed] == ["assistant", "user"] * 3
    ok, receipt = ctx.apply_edit("[[CTX_TURN 0 role=user]]\nfacts: cmd0..cmd2 ran fine", upto=len(ctx.editable))
    assert ok and "accepted" in receipt and ctx.editable == [{"role": "user", "content": "facts: cmd0..cmd2 ran fine"}]
    ok, receipt = ctx.apply_edit("x" * 60_000, upto=len(ctx.editable))
    assert not ok and "rejected" in receipt and "facts" in ctx.editable[0]["content"]


def test_clm_nudges_fire_once_and_rearm_after_shrinking():
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=4000, reserve_tokens=200))
    assert ctx.nudge() == ""
    for i in range(6):
        ctx.append(*_turn(i, 400))
    first = ctx.nudge()
    assert "[context]" in first and ctx.nudge() in ("",) or "urgent" in ctx.nudge()
    ctx.apply_edit("short", upto=len(ctx.editable))
    for i in range(6):
        ctx.append(*_turn(10 + i, 400))
    assert ctx.nudge() != ""  # re-armed after the context shrank


def test_clm_checkpoint_split_keeps_recent_turns_whole():
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(keep_recent_tokens=600))
    for i in range(10):
        ctx.append(*_turn(i, 600))
    keep = ctx.checkpoint_split()
    assert 0 < keep < len(ctx.editable) and ctx.editable[keep]["role"] == "assistant"
    ctx.replace_with_checkpoint("## Goal\nx", "[context checkpoint]", keep)
    assert ctx.editable[0]["role"] == "user" and "## Goal" in ctx.editable[0]["content"]
    assert ctx.editable[1]["role"] == "assistant" and ctx.editable[-1]["content"].startswith("out9")


# ----- the loop with CLM, checkpoints and reviews ----------------------------------------------------------
def _text(content):
    return [chunk(content=content), chunk(finish="stop"),
            chunk(usage={"prompt_tokens": 900, "completion_tokens": 80})]


def _run(tmp_path, script, *, config, transport=None, timeout_s=600.0, sleep=None, text_script=None):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    client = ScriptedClient(script, text_script)
    provider = ChatProvider(client, model="glm", params={"tool_choice": "required", "parallel_tool_calls": False},
                            **({"sleep": sleep} if sleep else {}))

    async def review_call(t, request):
        return t(request)
    result = asyncio.run(run_agent(env=LocalEnv(work), task=TASK, workdir=str(work), provider=provider,
                                   timeout_s=timeout_s, trace=Trace(tmp_path / "trace.jsonl"),
                                   review_transport=transport, review_call=review_call if transport else None,
                                   config=config))
    rows = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return result, rows, client


def _clm_config(tmp_path, **kw):
    return CoreConfig(context="clm", clm=ClmSettings(mirror_path=str(tmp_path / "ctx" / "LIVE_CTX.txt"), **kw),
                      control_dir=str(tmp_path / "ctl"))


def test_model_edit_of_the_mirror_replaces_its_history(tmp_path):
    mirror = str(tmp_path / "ctx" / "LIVE_CTX.txt")
    script = [call("terminal", {"input": "echo SECRET-OLD-OUTPUT"}, "c1"),
              call("write_file", {"path": mirror, "content": "[[CTX_TURN 0 role=user]]\nnote: echo worked"}, "c2"),
              call("finish", {"summary": "done"}, "c3")]
    result, rows, client = _run(tmp_path, script, config=_clm_config(tmp_path))
    assert result.status == "finished"
    last = json.dumps(client.requests[-1]["messages"])
    assert "note: echo worked" in last and "SECRET-OLD-OUTPUT" not in last  # history really replaced
    assert [r for r in rows if r["event"] == "context_edit"][0]["accepted"] is True
    assert result.extras["clm"]["edits_accepted"] == 1


def test_over_budget_context_is_checkpointed_keeping_recent_turns(tmp_path):
    big = "y" * 3000
    script = [call("terminal", {"input": f"echo {i}{big}"}, f"c{i}") for i in range(6)]
    script += [call("finish", {"summary": "done"}, "c9")]
    config = _clm_config(tmp_path, budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=2500)
    texts = [_text(f"## Goal\nSUMMARY-MARKER-{k}") for k in range(3)]
    result, rows, client = _run(tmp_path, script, config=config, text_script=texts)
    assert result.status == "finished"
    cp = [r for r in client.requests if "tools" not in r]
    assert cp and all("tool_choice" not in r for r in cp)  # checkpoints are plain text calls
    final = json.dumps(client.requests[-1]["messages"])
    assert "SUMMARY-MARKER" in final and "echo 5" + "y" * 50 in final  # summary plus the newest turn verbatim
    assert "echo 0" + "y" * 50 not in final  # the oldest turn really left the request
    cps = [r for r in rows if r["event"] == "context_checkpoint"]
    assert cps and all(r["ok"] and r["tokens"] < r["tokens_before"] for r in cps)
    budget_chars = 9000 * 3.0  # the estimator's initial chars-per-token
    assert max(result.request_chars) < budget_chars * 1.1 and result.sub_usage.get("output") == 80 * len(cps)


def _answers(mode, conf, crit="none"):
    return {"result": {"answers": {"failure_mode": {"choice": mode, "confidence": conf},
                                   "completeness:C1": {"choice": crit, "confidence": 0.9}}}}


def test_progress_and_final_reviews_inform_without_blocking(tmp_path, monkeypatch):
    monkeypatch.setattr(core_oversight, "FINAL_WINDOW_MIN_S", 0)
    script = [call("terminal", {"input": "true"}, "c1"), call("terminal", {"input": "true"}, "c2"),
              call("finish", {"summary": "x"}, "c3")]
    plan = ReviewPlan(finish=False, progress_at=(0.0,), final=False)
    result, rows, client = _run(tmp_path, script, config=CoreConfig(reviews=plan),
                                transport=lambda req: _answers("incomplete", 0.9))
    assert result.status == "finished" and [r["kind"] for r in result.reviews] == ["progress"]
    second = json.dumps(client.requests[1]["messages"])
    assert "[progress review at" in second and "C1" in second


def test_final_review_fires_near_the_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(core_oversight, "FINAL_WINDOW_MIN_S", 10_000)
    script = [call("terminal", {"input": "true"}, "c1"), call("finish", {"summary": "x"}, "c2")]
    plan = ReviewPlan(finish=False, final=True)
    result, _, client = _run(tmp_path, script, config=CoreConfig(reviews=plan),
                             transport=lambda req: _answers("incomplete", 0.9))
    assert [r["kind"] for r in result.reviews] == ["final"]
    assert "[final review" in json.dumps(client.requests[0]["messages"]) + json.dumps(client.requests[1]["messages"])


def test_review_errors_are_recorded_and_the_run_continues(tmp_path):
    def broken(_):
        raise RuntimeError("reviewer down")
    plan = ReviewPlan(finish=True, progress_at=(0.0,))
    result, _, _ = _run(tmp_path, [call("finish", {"summary": "x"})], config=CoreConfig(reviews=plan),
                        transport=broken)
    assert result.status == "finished" and [r["status"] for r in result.reviews] == ["error", "error"]


# ----- provider retries --------------------------------------------------------------------------------------
def test_every_retry_is_traced_with_status_and_wait(tmp_path):
    waits = []

    async def sleep(s):
        waits.append(s)
    script = [StatusError(429, headers={"retry-after": "2"}), call("finish", {"summary": "x"})]
    result, rows, _ = _run(tmp_path, script, config=CoreConfig(), sleep=sleep)
    model = [r for r in rows if r["event"] == "model"][0]
    assert model["failures"][0]["status"] == 429 and model["failures"][0]["wait_s"] == 2.0 and waits == [2.0]
    assert result.extras["provider_failures_by_status"] == {"429": 1}


def test_a_retry_past_the_deadline_ends_as_timeout_not_provider_error(tmp_path):
    script = [StatusError(429, headers={"retry-after": "59"})]
    result, rows, _ = _run(tmp_path, script, config=CoreConfig(), timeout_s=60.0)
    assert result.status == "timeout" and [r for r in rows if r["event"] == "provider_error"][0]["deadline"]

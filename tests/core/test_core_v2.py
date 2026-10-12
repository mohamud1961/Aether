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


# ----- view_image -------------------------------------------------------------------------------------------
def _bmp(path, colour, size=(64, 40)):
    from PIL import Image
    Image.new("RGB", size, colour).save(path, format="BMP")


def test_view_image_shows_a_real_bmp_as_png_after_the_tool_results(tmp_path):
    pytest.importorskip("PIL")
    import base64
    import io
    from PIL import Image
    work = tmp_path / "work"
    work.mkdir()
    _bmp(work / "frame.bmp", (0, 128, 128))
    script = [call("view_image", {"path": "frame.bmp"}, "c1"), call("finish", {"summary": "x"}, "c2")]
    result, rows, client = _run(tmp_path, script, config=CoreConfig(images=True))
    msgs = client.requests[1]["messages"]
    tool_i = next(i for i, m in enumerate(msgs) if m.get("role") == "tool")
    assert "BMP 64x40" in msgs[tool_i]["content"]
    img_msg = msgs[tool_i + 1]  # the image follows the tool result, never between call and result
    url = img_msg["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    decoded = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert decoded.getpixel((10, 10))[:3] == (0, 128, 128)  # the real pixels, not a placeholder
    assert result.extras["images_viewed"] == 1
    assert any(t["function"]["name"] == "view_image" for t in client.requests[0]["tools"])


def test_only_the_newest_images_are_sent_and_base64_never_counts_or_reaches_the_mirror(tmp_path):
    pytest.importorskip("PIL")
    work = tmp_path / "work"
    work.mkdir()
    for i, c in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        _bmp(work / f"f{i}.bmp", c, size=(400, 300))
    script = [call("view_image", {"path": f"f{i}.bmp"}, f"c{i}") for i in range(3)]
    script += [call("finish", {"summary": "x"}, "c9")]
    config = CoreConfig(context="clm", images=True, clm=ClmSettings(mirror_path=str(tmp_path / "ctx/LIVE_CTX.txt")),
                        control_dir=str(tmp_path / "ctl"))
    result, rows, client = _run(tmp_path, script, config=config)
    last = client.requests[-1]["messages"]
    shown = [m for m in last if isinstance(m.get("content"), list)]
    assert len(shown) == 2 and "f1.bmp" in shown[0]["content"][0]["text"]
    assert any("no longer shown" in str(m.get("content")) for m in last)
    assert max(result.request_chars) < 40_000  # an image is budgeted at its token cost, not its base64 size
    from aether.core.clm import ClmContext as C
    ctx = C(pinned=[], settings=ClmSettings())
    ctx.append(*last[2:])
    assert "base64" not in ctx.render() and "[image" in ctx.render()


def test_view_image_reports_unreadable_files_plainly(tmp_path):
    pytest.importorskip("PIL")
    work = tmp_path / "work"
    work.mkdir()
    (work / "notimg.bmp").write_text("hello")
    script = [call("view_image", {"path": "notimg.bmp"}, "c1"), call("finish", {"summary": "x"}, "c2")]
    _, rows, _ = _run(tmp_path, script, config=CoreConfig(images=True))
    out = [r for r in rows if r["event"] == "tool"][0]["result"]
    assert "not a readable image" in out


def test_view_image_refuses_oversized_files_before_copying_and_pixel_bombs_before_decoding(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    from PIL import Image
    from aether.core import images as core_images
    work = tmp_path / "work"
    work.mkdir()
    (work / "big.bin").write_bytes(b"\0" * 2048)
    Image.new("RGB", (300, 300)).save(work / "wide.png")
    monkeypatch.setattr(core_images, "MAX_FILE_BYTES", 1024)
    copied = []
    real_get = core_images.get_bytes

    async def spy(env, path):
        copied.append(path)
        return await real_get(env, path)
    monkeypatch.setattr(core_images, "get_bytes", spy)
    with pytest.raises(ValueError, match="limit"):
        asyncio.run(core_images.load(LocalEnv(work), str(work / "big.bin")))
    assert copied == []  # refused inside the sandbox; nothing reached the host
    monkeypatch.setattr(core_images, "MAX_FILE_BYTES", 30_000_000)
    monkeypatch.setattr(core_images, "MAX_PIXELS", 10_000)
    with pytest.raises(ValueError, match="pixel limit"):
        asyncio.run(core_images.load(LocalEnv(work), str(work / "wide.png")))


# ----- verifier sees real program output ----------------------------------------------------------------------
def test_reviewer_reads_terminal_logs_itself_and_garbled_bytes_are_visible(tmp_path):
    seen = []

    def reviewer(req):
        seen.append(req)
        return {"result": {"answers": {"failure_mode": {"choice": "fully_done", "confidence": 0.9},
                                       "malfunction": {"choice": "garbled_or_binary_output", "confidence": 0.9}}}}
    script = [call("terminal", {"input": "printf 'DOOM Shareware\\n\\303\\100\\000\\000K\\n' > run.log; cat run.log"}, "c1"),
              call("write_file", {"path": "out.txt", "content": "hello\n"}, "c2"),  # the solver's last actions hide it
              call("terminal", {"input": "ls"}, "c3"),
              call("finish", {"summary": "x"}, "c4"), call("finish", {"summary": "x"}, "c5"),
              call("finish", {"summary": "x"}, "c6")]
    config = CoreConfig(reviews=ReviewPlan(), control_dir=str(tmp_path / "ctl"))
    result, rows, client = _run(tmp_path, script, config=config, transport=reviewer)
    logs = seen[0]["state"]["visible_evidence"]["output_logs"]
    assert "DOOM Shareware" in logs and "^@" in logs  # non-printing bytes shown, from the log, not the solver's view
    assert "malfunction" in seen[0]["questions"]
    assert result.reviews[0]["malfunction"] == "garbled_or_binary_output"
    # a malfunction finding alone does not hold a finish whose failure-mode reading is done (D1 false holds)
    assert [r["status"] for r in result.reviews] == ["pass"] and result.status == "finished"


def test_urgent_nudge_is_rate_limited():
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=4000, reserve_tokens=200, nudge_ratios=()))
    i = 0
    while ctx.settings.limit - ctx.tokens() >= 0.10 * ctx.settings.limit:  # fill to the urgent zone, not past it
        ctx.append(*_turn(i, 100))
        i += 1
    assert not ctx.over_limit()
    fired = [("urgent" in ctx.nudge()) for _ in range(7)]
    assert fired == [True, False, False, True, False, False, True]




def test_checkpoint_runs_at_low_effort_and_retries_an_empty_summary():
    # D1: with a 4096-token cap GLM's reasoning used the whole budget and the run ended "no text".
    from aether.core import compaction
    from aether.core.provider import ChatProvider
    from tests.core.core_fakes import chunk
    empty = [chunk(reasoning="r" * 50), chunk(finish="length"),
             chunk(usage={"prompt_tokens": 900, "completion_tokens": 4096})]
    good = [chunk(content="## Summary\nstate"), chunk(finish="stop"),
            chunk(usage={"prompt_tokens": 900, "completion_tokens": 300})]
    client = ScriptedClient([], [empty, good])
    provider = ChatProvider(client, model="glm", params={"reasoning_effort": "high"})
    summary, usage = asyncio.run(compaction.checkpoint(provider, "task", "transcript", repl=False,
                                                       remaining_s=lambda: 100.0))
    assert summary.startswith("## Summary") and usage["output"] == 4396
    assert client.requests[0]["max_tokens"] == compaction.MAX_SUMMARY_TOKENS >= 16_000
    assert client.requests[0]["reasoning_effort"] == "low" and client.requests[1]["reasoning_effort"] == "high"
    client2 = ScriptedClient([], [empty, empty])
    provider2 = ChatProvider(client2, model="glm", params={"reasoning_effort": "high"})
    with pytest.raises(ValueError, match="finish_reason=length"):
        asyncio.run(compaction.checkpoint(provider2, "t", "x", repl=False, remaining_s=lambda: 100.0))


def test_replayed_reasoning_is_counted_by_its_provider_token_count():
    # D1 feal-linear: a 32k-token reasoning turn was estimated at 27.7k and counted at 38.2k (budget 32k).
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000))
    dense = "0x9f3a^" * 6000  # 42k chars that tokenize far denser than the chars-per-token estimate
    msg = {"role": "assistant", "content": None, "reasoning_content": dense}
    ctx.append(msg)
    estimated = ctx.tokens()
    ctx.note_reasoning(msg, 20000)
    assert ctx.tokens() >= 20000 > estimated  # the exact count replaces the character estimate
    before = ctx.chars_per_token
    ctx.calibrate(request_chars=len(json.dumps(ctx.request())), input_tokens=ctx.tokens())
    assert abs(ctx.chars_per_token - before) < 0.5  # the dense reasoning does not skew calibration
    ctx.append({"role": "user", "content": "next"}, {"role": "assistant", "content": "x", "reasoning_content": "r"})
    assert ctx.tokens() < 2000  # only the newest assistant turn's reasoning is replayed and counted


def test_a_turn_cut_off_by_the_output_limit_is_reported_as_such(tmp_path):
    cut = [chunk(reasoning="thinking " * 20), chunk(finish="length"),
           chunk(usage={"prompt_tokens": 500, "completion_tokens": 3000,
                        "completion_tokens_details": {"reasoning_tokens": 3000}})]
    script = [cut, call("finish", {"summary": "x"}, "c1")]
    result, rows, client = _run(tmp_path, script, config=_clm_config(tmp_path))
    second = client.requests[1]["messages"]
    assert "output limit before any tool call" in json.dumps(second[-1])
    assert result.status == "finished"


def test_one_long_thought_does_not_trigger_a_checkpoint_that_discards_it(tmp_path):
    # D1 circuit-math: each 32k-token reasoning turn pushed the count over budget; the checkpoint (which never
    # sees reasoning) then summarised everything away, and the model re-derived its plan from a 3k summary, 3 times.
    thought = "PLAN-STEP " * 3000
    cut = [chunk(reasoning=thought), chunk(finish="length"),
           chunk(usage={"prompt_tokens": 2000, "completion_tokens": 32768,
                        "completion_tokens_details": {"reasoning_tokens": 32768}})]
    script = [cut, call("finish", {"summary": "x"}, "c1")]
    result, rows, client = _run(tmp_path, script, config=_clm_config(tmp_path))
    assert not [r for r in rows if r.get("event") == "context_checkpoint"]
    replayed = [m for m in client.requests[1]["messages"] if m.get("role") == "assistant"][-1]
    assert "PLAN-STEP" in replayed.get("reasoning_content", "")  # the thought reaches the next turn intact
    assert result.status == "finished"


def test_held_context_still_triggers_a_checkpoint_when_it_is_over_budget():
    # known-bad guard: excluding the replayed reasoning must not exempt the rest of the context from the budget
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(budget_tokens=32000))
    ctx.append({"role": "user", "content": "x" * 200_000})
    msg = {"role": "assistant", "content": None, "reasoning_content": "r" * 1000}
    ctx.append(msg)
    ctx.note_reasoning(msg, 30000)
    assert ctx.over_limit() and ctx.held() == ctx.tokens() - 30000


def _ended(finish, **kw):
    return [chunk(**kw), chunk(finish=finish),
            chunk(usage={"prompt_tokens": 500, "completion_tokens": 100, "completion_tokens_details": {"reasoning_tokens": 90}})]


def test_turns_cut_off_by_the_output_limit_do_not_end_the_run_as_idle(tmp_path):
    # D1 regex-game: three 32k-token thoughts in a row ended the run as "no_tool_loop" with 30 minutes left.
    cut = _ended("length", reasoning="deep thought ")
    script = [cut, cut, cut, cut, call("finish", {"summary": "x"}, "c1")]
    result, _rows, _client = _run(tmp_path, script, config=_clm_config(tmp_path))
    assert result.status == "finished"


def test_text_replies_without_tools_still_end_the_run(tmp_path):
    # known-bad guard: a model that only chats is still stopped
    chat = _ended("stop", content="I will now think about it.")
    result, _rows, _client = _run(tmp_path, [chat, chat, chat, call("finish", {"summary": "x"}, "c1")],
                                  config=_clm_config(tmp_path))
    assert result.status == "no_tool_loop"

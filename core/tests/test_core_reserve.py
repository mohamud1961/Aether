"""Delivery reserve: a long wait must leave the model a turn before the deadline (loop.RESERVE_*)."""

import asyncio
import time

import pytest

from aether.core import harbor_agent as adapter
from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, reserve_s, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, chunk, tool_chunk

# 40 s budget: work deadline at 25 s; reserve min(120, 10) = 10 s, so with it a wait ends at t = 15.
TIMEOUT_S, MODEL_TURN_S = 40.0, 7.0


def _turn(name, args, call_id):
    return [
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(usage={"prompt_tokens": 5, "completion_tokens": 2}),
    ]


class _SlowAfterWait(ScriptedClient):
    """The turn after the long wait takes MODEL_TURN_S, as a real model turn does."""

    async def _create(self, **kwargs):
        if len(self.requests) == 1:
            await asyncio.sleep(MODEL_TURN_S)
        return await super()._create(**kwargs)


def _run(tmp_path, reserve: bool):
    work = tmp_path / "work"
    work.mkdir()
    client = _SlowAfterWait(
        [
            _turn("terminal", {"input": "sleep 120", "wait_s": 300}, "c1"),
            _turn("write_file", {"path": str(work / "model.xml"), "content": "best\n"}, "c2"),
            _turn("finish", {"summary": "saved the best setting"}, "c3"),
        ]
    )
    provider = ChatProvider(client, model="scripted", params={}, log=CallLog(tmp_path / "calls"))
    started = time.monotonic()
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=TIMEOUT_S,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), delivery_reserve=reserve),
        )
    )
    return result, client, work, time.monotonic() - started


@pytest.mark.parametrize("reserve", [False, True])
def test_a_long_wait_leaves_a_turn_to_deliver_only_with_the_reserve(tmp_path, reserve):
    result, client, work, _ = _run(tmp_path, reserve)
    if reserve:
        assert result.status == "finished"
        assert (work / "model.xml").read_text() == "best\n"
        shown = str(client.requests[1]["messages"][-1]["content"])
        assert "final window: " in shown and "the run ends then" in shown
    else:  # the known-bad: the wait ends 5 s before the deadline and the next turn does not fit
        assert result.status == "timeout"
        assert not (work / "model.xml").exists()


def test_the_reserve_is_off_unless_set():
    required = {
        adapter.REVIEW_ENV: "off",
        adapter.CONTEXT_ENV: "project",
        adapter.REPL_ENV: "off",
        adapter.IMAGES_ENV: "off",
    }
    assert adapter.build_config(environ=required).delivery_reserve is False
    on = {**required, adapter.RESERVE_ENV: "on"}
    assert adapter.build_config(environ=on).delivery_reserve is True
    with pytest.raises(adapter.ConfigError):
        adapter.build_config(environ={**required, adapter.RESERVE_ENV: "maybe"})


def test_a_wait_ended_by_the_reserve_leaves_the_command_running_and_its_exit_is_reported_later(tmp_path):
    """The reserve only ends the wait: the command keeps running, reports no exit it does not have, and a later
    wait collects its output and real exit code."""
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient(
        [
            _turn("terminal", {"input": "sleep 18; echo DONE; exit_code=3; (exit $exit_code)", "wait_s": 300}, "c1"),
            _turn("terminal", {"input": "", "wait_s": 300}, "c2"),
            _turn("finish", {"summary": "done"}, "c3"),
        ]
    )
    provider = ChatProvider(client, model="scripted", params={}, log=CallLog(tmp_path / "calls"))
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=TIMEOUT_S,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), delivery_reserve=True),
        )
    )
    first = str(client.requests[1]["messages"][-1]["content"])
    second = str(client.requests[2]["messages"][-1]["content"])
    assert "still running" in first and "[exit" not in first and "DONE" not in first
    assert "DONE" in second and "[exit 3" in second
    assert result.status == "finished"


@pytest.mark.parametrize("budget, window", [(40, 10), (300, 75), (480, 120), (900, 120), (3600, 120)])
def test_the_window_is_one_slow_turn_capped_at_a_quarter_of_short_budgets(budget, window):
    assert reserve_s(budget) == window

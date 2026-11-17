"""Window cut margin: one cut frees room for many turns instead of re-cutting (and moving the cached prefix) every turn."""

import asyncio
import json

import pytest

from aether.core.clm import ClmSettings
from aether.core.harbor_agent import build_config
from aether.core.harbor_config import ConfigError
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call
from tests.test_core_v2 import _text


def run(root, margin):
    work, control = root / "work", root / "control"
    work.mkdir(parents=True)
    script = [call("terminal", {"input": "printf '%s' '" + str(i) + "x" * 3000 + "'"}, f"noise{i}") for i in range(16)]
    script += [call("write_file", {"path": "done.txt", "content": "ok"}, "deliver"), call("finish", {"summary": "done"}, "f")]
    client = ScriptedClient(script, text_script=[_text("unused") for _ in range(5)])
    settings = ClmSettings(budget_tokens=9000, reserve_tokens=500, checkpoint_policy="window",
                           window_cut_margin_tokens=margin, mirror_path=str(control / "live"),
                           history_path=str(control / "history"))
    trace = root / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Print noise, then write done.txt.", workdir=str(work),
        provider=ChatProvider(client, model="offline-script", params={}), timeout_s=120, trace=Trace(trace),
        config=CoreConfig(context="clm", control_dir=str(control), clm=settings),
    ))
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    cuts = [e for e in events if e["event"] == "context_window_cut"]
    return result, cuts, work


def test_margin_cuts_less_often_than_just_under_the_limit(tmp_path):
    base, base_cuts, base_work = run(tmp_path / "zero", 0)
    wide, wide_cuts, wide_work = run(tmp_path / "wide", 4000)
    assert base.status == wide.status == "finished", (base.error, wide.error)
    assert (base_work / "done.txt").read_text() == (wide_work / "done.txt").read_text() == "ok"
    assert all(c["ok"] for c in base_cuts + wide_cuts)
    # Known-bad: without a margin the context is cut again on most turns once it reaches the limit.
    assert len(base_cuts) >= 4
    assert 1 <= len(wide_cuts) <= len(base_cuts) // 2
    # A margin cut actually frees the room it promises.
    assert all(c["tokens"] <= 9000 - 500 - 4000 + 1500 for c in wide_cuts)


def test_margin_is_opt_in_and_validated():
    env = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off",
           "AETHER_CORE_IMAGES": "off", "AETHER_CORE_CHECKPOINT_POLICY": "window"}
    assert build_config(environ=env).clm.window_cut_margin_tokens == 0
    assert build_config(environ={**env, "AETHER_CORE_WINDOW_CUT_MARGIN": "32000"}).clm.window_cut_margin_tokens == 32000
    with pytest.raises(ConfigError):
        build_config(environ={**env, "AETHER_CORE_WINDOW_CUT_MARGIN": "lots"})

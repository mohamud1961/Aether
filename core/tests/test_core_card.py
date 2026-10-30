"""AETHER_CORE_RIVAL=card: at the first finish a fresh reading of the request alone is handed back once."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import time

from aether.core import card, rival
from aether.core.harbor_agent import build_config
from tests.core_fakes import LocalEnv, call, chunk
from tests.test_core_start_copy import BASE
from tests.test_core_v2 import _clm_config, _run


def _text(content: str) -> list:
    return [chunk(content=content), chunk(finish="stop")]


def test_card_mode_is_its_own_flag_value():
    c = build_config(environ={**BASE, "AETHER_CORE_RIVAL": "card"})
    assert c.card is True and c.rival is False and c.exec_check is False
    assert build_config(environ=BASE).card is False


def test_only_files_present_before_the_first_action_are_named(tmp_path):
    work, ctl = tmp_path / "app", tmp_path / "ctl"
    work.mkdir(), ctl.mkdir()
    (work / "given.csv").write_text("x\n")
    old = time.time() - 60
    os.utime(work / "given.csv", (old, old))
    env = LocalEnv(tmp_path)
    asyncio.run(rival.mark_start(env, str(ctl)))
    os.utime(ctl / rival.MARKER, (old + 30, old + 30))
    (work / "made.py").write_text("print(1)\n")
    assert asyncio.run(card.provided_files(env, str(work), str(ctl))) == [str(work / "given.csv")]


def test_a_card_is_handed_back_once_and_never_sees_the_work(tmp_path):
    script = [
        call("write_file", {"path": str(tmp_path / "work" / "sol.sql"), "content": "SELECT 1;\n"}, "c0"),
        call("terminal", {"input": "echo private-step"}, "c1"),
        call("finish", {"summary": "query saved"}, "c2"),
        call("terminal", {"input": "echo checked"}, "c3"),
        call("finish", {"summary": "checked against the reading"}, "c4"),
    ]
    reading = "1. The query must return the same rows as the original."
    config = dataclasses.replace(_clm_config(tmp_path), card=True)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text(reading)])
    assert result.status == "finished"
    row = next(r for r in rows if r["event"] == "rival")
    assert row["handed_back"] and row["mode"] == "card"
    card_request = json.dumps(next(r for r in client.requests if "tools" not in r)["messages"])
    assert "REQUEST:" in card_request
    for leaked in ("SELECT 1;", "private-step", "query saved", "sol.sql"):  # not the work, history or summary
        assert leaked not in card_request
    handback = json.dumps(client.requests[-1]["messages"])
    assert "<reading>" in handback and "same rows as the original" in handback
    assert len([r for r in rows if r["event"] == "rival"]) == 1


def test_an_empty_card_lets_the_first_finish_end_the_run(tmp_path):
    config = dataclasses.replace(_clm_config(tmp_path), card=True)
    result, rows, client = _run(tmp_path, [call("finish", {"summary": "done"}, "c0")], config=config,
                                text_script=[_text("")])
    assert result.status == "finished"
    assert next(r for r in rows if r["event"] == "rival")["handed_back"] is False

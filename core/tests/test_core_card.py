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


def test_probe_mode_sets_both_flags():
    c = build_config(environ={**BASE, "AETHER_CORE_RIVAL": "probe"})
    assert c.card is True and c.card_probe is True and c.rival is False
    assert build_config(environ={**BASE, "AETHER_CORE_RIVAL": "card"}).card_probe is False


def test_script_of_takes_the_last_shell_block():
    text = "1. item\n```sh\necho a\n```\nmore\n```bash\necho b\n```\n"
    assert card.script_of(text) == "echo b"
    assert card.script_of("no script here") is None


def test_a_probe_runs_the_readers_script_on_the_current_state_and_hands_back_its_output(tmp_path):
    out = tmp_path / "work" / "out.txt"
    script = [
        call("write_file", {"path": str(out), "content": "41\n"}, "c0"),
        call("finish", {"summary": "answer written"}, "c1"),
        call("terminal", {"input": "echo checked"}, "c2"),
        call("finish", {"summary": "checked"}, "c3"),
    ]
    reading = f"1. out.txt must hold 42.\n```sh\necho \"item 1 bytes=$(wc -c < {out} | tr -d ' ')\"\n```\n"
    config = dataclasses.replace(_clm_config(tmp_path), card=True, card_probe=True)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text(reading)])
    assert result.status == "finished"
    row = next(r for r in rows if r["event"] == "rival")
    assert row["mode"] == "probe" and row["script"] is True and row["exit"] == 0
    probe_request = json.dumps(next(r for r in client.requests if "tools" not in r)["messages"])
    assert "Change nothing" in probe_request and "answer written" not in probe_request and "41" not in probe_request
    handback = json.dumps(client.requests[-1]["messages"])
    assert "<observed exit=" in handback and "item 1 bytes=3" in handback  # only running the script prints this
    assert len([r for r in rows if r["event"] == "rival"]) == 1


def test_a_probe_without_a_script_falls_back_to_the_reading(tmp_path):
    script = [call("finish", {"summary": "done"}, "c0"), call("finish", {"summary": "done again"}, "c1")]
    config = dataclasses.replace(_clm_config(tmp_path), card=True, card_probe=True)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text("1. something")])
    row = next(r for r in rows if r["event"] == "rival")
    assert row["handed_back"] and row["script"] is False
    handback = json.dumps(client.requests[-1]["messages"])
    assert "<reading>" in handback and "<observed" not in handback


def test_challenge_mode_sets_its_own_flag():
    c = build_config(environ={**BASE, "AETHER_CORE_RIVAL": "challenge"})
    assert c.card is True and c.card_challenge == "challenge" and c.card_probe is False and c.rival is False
    assert build_config(environ={**BASE, "AETHER_CORE_RIVAL": "probe"}).card_challenge == ""


def test_challenge_hands_back_only_commands_and_raw_output_never_the_readers_reasoning(tmp_path):
    out = tmp_path / "work" / "out.txt"
    script = [
        call("write_file", {"path": str(out), "content": "41\n"}, "c0"),
        call("finish", {"summary": "answer written"}, "c1"),
        call("terminal", {"input": "echo checked"}, "c2"),
        call("finish", {"summary": "checked"}, "c3"),
    ]
    reader = f"The likeliest error is an off-by-one CONCERN_TEXT.\n```sh\nwc -c < {out}\ncat {out}\n```\n"
    config = dataclasses.replace(_clm_config(tmp_path), card=True, card_challenge="challenge")
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text(reader)])
    assert result.status == "finished"
    row = next(r for r in rows if r["event"] == "rival")
    assert row["mode"] == "challenge" and row["script"] is True and row["exit"] == 0 and row["echo_lines"] == 0
    reader_request = json.dumps(next(r for r in client.requests if "tools" not in r)["messages"])
    assert "Do not do the task" in reader_request and "answer written" not in reader_request
    handback = json.dumps(client.requests[-1]["messages"])
    assert "<observed exit=" in handback and "+ cat" in handback and "41" in handback  # sh -x commands + raw output
    assert "CONCERN_TEXT" not in handback and "<reading>" not in handback and "<script>" not in handback
    assert len([r for r in rows if r["event"] == "rival"]) == 1


def test_challenge_without_a_script_lets_the_first_finish_end_the_run(tmp_path):
    script = [call("finish", {"summary": "done"}, "c0")]
    config = dataclasses.replace(_clm_config(tmp_path), card=True, card_challenge="challenge")
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text("only prose, no checks")])
    row = next(r for r in rows if r["event"] == "rival")
    assert result.status == "finished" and row["handed_back"] is False and row["script"] is False

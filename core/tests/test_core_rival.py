"""AETHER_CORE_RIVAL: at the first finish a fresh call writes a rival; it is handed back once, or NONE ends the run."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import time

from aether.core import rival
from aether.core.harbor_agent import build_config
from tests.core_fakes import LocalEnv, call, chunk
from tests.test_core_start_copy import BASE
from tests.test_core_v2 import _clm_config, _run


def _text(content: str) -> list:
    return [chunk(content=content), chunk(finish="stop")]


def test_only_files_changed_after_the_start_marker_are_shown(tmp_path):
    work, ctl = tmp_path / "app", tmp_path / "ctl"
    work.mkdir(), ctl.mkdir()
    (work / "input.csv").write_text("given\n")
    old = time.time() - 60
    os.utime(work / "input.csv", (old, old))
    env = LocalEnv(tmp_path)
    asyncio.run(rival.mark_start(env, str(ctl)))
    os.utime(ctl / rival.MARKER, (old + 30, old + 30))
    (work / "sol.sql").write_text("SELECT 1;\n")
    (work / "blob.bin").write_bytes(b"\x00\x01\x02" * 10)
    files = asyncio.run(rival.changed_files(env, str(work), str(ctl)))
    assert files == [(str(work / "sol.sql"), "SELECT 1;\n")]  # unchanged input and binary files are not shown


def test_a_cut_file_says_it_was_cut(tmp_path, monkeypatch):
    work, ctl = tmp_path / "app", tmp_path / "ctl"
    work.mkdir(), ctl.mkdir()
    env = LocalEnv(tmp_path)
    asyncio.run(rival.mark_start(env, str(ctl)))
    os.utime(ctl / rival.MARKER, (time.time() - 30, time.time() - 30))
    (work / "big.py").write_text("x = 1\n" * 20)
    monkeypatch.setattr(rival, "FILE_CAP", 30)
    [(path, text)] = asyncio.run(rival.changed_files(env, str(work), str(ctl)))
    assert text.startswith("x = 1\n") and "cut here: shown the first 30 of 120 bytes" in text


def test_none_and_late_finishes_ask_nothing_back():
    assert rival.is_none("NONE") and rival.is_none(" none. ") and not rival.is_none("NONE of the moves; use e2e4")
    assert rival.due(500, 900) and not rival.due(100, 900) and not rival.due(200, 1800)


def test_flag_is_off_by_default():
    assert build_config(environ=BASE).rival is False
    assert build_config(environ={**BASE, "AETHER_CORE_RIVAL": "on"}).rival is True


def test_a_rival_is_handed_back_once_then_the_next_finish_ends(tmp_path):
    script = [
        call("write_file", {"path": str(tmp_path / "work" / "sol.sql"), "content": "SELECT 1;\n"}, "c0"),
        call("finish", {"summary": "query saved"}, "c1"),
        call("terminal", {"input": "echo compared"}, "c2"),
        call("finish", {"summary": "kept the faster one"}, "c3"),
    ]
    text_script = [_text("Rival: SELECT 2;\nTest: time both on the database.")]
    config = dataclasses.replace(_clm_config(tmp_path), rival=True)
    result, rows, client = _run(tmp_path, script, config=config, text_script=text_script)
    assert result.status == "finished"
    row = next(r for r in rows if r["event"] == "rival")
    assert row["handed_back"] and str(tmp_path / "work" / "sol.sql") in row["files"]
    rival_request = next(r for r in client.requests if "tools" not in r)
    assert "SELECT 1;" in json.dumps(rival_request["messages"])  # the rival sees the candidate's file
    assert "echo compared" not in json.dumps(rival_request["messages"])  # and not the run's history
    assert "<rival>" in json.dumps(client.requests[3]["messages"]) and "SELECT 2;" in json.dumps(client.requests[3]["messages"])
    assert len([r for r in rows if r["event"] == "rival"]) == 1


def test_a_none_rival_lets_the_first_finish_end_the_run(tmp_path):
    script = [call("finish", {"summary": "done"}, "c0")]
    config = dataclasses.replace(_clm_config(tmp_path), rival=True)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text("NONE")])
    assert result.status == "finished"
    assert next(r for r in rows if r["event"] == "rival")["handed_back"] is False

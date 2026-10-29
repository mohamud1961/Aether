"""The start copy: taken before the first action, named in the task message, bounded."""

from __future__ import annotations

import asyncio

from aether.core import start_copy
from aether.core.harbor_agent import build_config
from tests.core_fakes import LocalEnv

BASE = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}


def test_the_copy_holds_the_starting_bytes_after_the_original_is_destroyed(tmp_path):
    app, ctl = tmp_path / "app", tmp_path / "ctl"
    app.mkdir()
    (app / "db.wal").write_bytes(b"\x00wal-frames\xff")
    note, row = asyncio.run(start_copy.take(LocalEnv(tmp_path), str(app), str(ctl)))
    (app / "db.wal").unlink()  # what a wrong run did: opened the database and lost its log
    copy = ctl / "start" / "app" / "db.wal"
    assert copy.read_bytes() == b"\x00wal-frames\xff"
    assert row["copied"] and str(ctl / "start" / "app") in note and str(app) in note


def test_an_oversized_working_directory_is_not_copied_and_nothing_is_said(tmp_path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    (app / "big").write_bytes(b"x" * 8192)
    monkeypatch.setattr(start_copy, "LIMIT_BYTES", 1024)
    note, row = asyncio.run(start_copy.take(LocalEnv(tmp_path), str(app), str(tmp_path / "ctl")))
    assert note == "" and not row["copied"] and "too_large" in row["reason"]
    assert not (tmp_path / "ctl" / "start").exists()


def test_a_missing_working_directory_gives_no_note(tmp_path):
    note, row = asyncio.run(start_copy.take(LocalEnv(tmp_path), str(tmp_path / "none"), str(tmp_path / "ctl")))
    assert note == "" and not row["copied"]


def test_the_flag_is_off_by_default_and_on_when_asked():
    assert build_config(environ=BASE).start_copy is True  # default on
    assert build_config(environ={**BASE, "AETHER_CORE_START_COPY": "off"}).start_copy is False
    assert build_config(environ={**BASE, "AETHER_CORE_START_COPY": "on"}).start_copy is True

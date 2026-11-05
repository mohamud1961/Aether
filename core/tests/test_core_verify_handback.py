"""After a bound defect finding, the solver keeps its reasoning (default) or loses it once (fresh); both are traced."""

from __future__ import annotations

import pytest

from aether.core import verify


class Session:
    def __init__(self):
        self.history = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "", "reasoning_content": [{"id": "r1"}], "tool_calls": [{"id": "c"}]},
            {"role": "tool", "content": "out"},
            {"role": "assistant", "content": "done", "reasoning_content": "thought"},
        ]
        self.rows = []

    def trace(self, event, **row):
        self.rows.append((event, row))


def test_keep_is_the_default_and_changes_nothing(monkeypatch):
    monkeypatch.delenv(verify.HANDBACK_ENV, raising=False)
    s = Session()
    verify._handback(s)
    assert sum("reasoning_content" in m for m in s.history) == 2
    assert s.rows == [("verify_handback", {"mode": "keep", "reasoning_dropped": 0})]


def test_fresh_drops_every_reasoning_item_once_and_keeps_the_record(monkeypatch):
    monkeypatch.setenv(verify.HANDBACK_ENV, "fresh")
    s = Session()
    verify._handback(s)
    assert not any("reasoning_content" in m for m in s.history)
    assert s.history[2]["tool_calls"] == [{"id": "c"}] and s.history[4]["content"] == "done"
    assert s.rows == [("verify_handback", {"mode": "fresh", "reasoning_dropped": 2})]


def test_an_unknown_mode_is_refused(monkeypatch):
    monkeypatch.setenv(verify.HANDBACK_ENV, "maybe")
    with pytest.raises(ValueError):
        verify._handback(Session())

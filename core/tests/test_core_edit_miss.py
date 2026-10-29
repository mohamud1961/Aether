"""A missed edit shows the file's own nearby lines, so the model does not need a full re-read."""

from __future__ import annotations


def test_an_edit_miss_shows_the_files_own_lines(tmp_path):
    # y12-y14: 34/456 edits missed; the message led with a sha256 and the model re-read the whole file
    from aether.core.files import _edit_miss_evidence

    text = "def f():\n    x = 1\n    return x\n"
    told = _edit_miss_evidence("a.py", text.encode(), text, "def f():\n  x = 1\n")
    assert "matches lines 1-2 apart from whitespace" in told and "     2      x = 1" in told
    told = _edit_miss_evidence("a.py", text.encode(), text, "    return x_value\n")
    assert "     3      return x" in told and "is 3" in told

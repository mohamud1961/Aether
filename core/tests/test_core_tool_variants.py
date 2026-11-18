"""AETHER_CORE_MULTI_EDIT and AETHER_CORE_WAIT_CAP (18 Nov Core-vs-Codex study; tool_variants)."""

import pytest

from aether.core import tool_variants
from aether.core.harbor_config import ConfigError, build_config
from aether.core.loop import CoreConfig
from tests.core_fakes import call
from tests.test_core_v2 import _run

SRC = "alpha = 1\nbeta = 2\ngamma = 3\n"
EDITS = [{"old_str": "alpha = 1", "new_str": "alpha = 10"}, {"old_str": "beta = 2", "new_str": "beta = 20"},
         {"old_str": "gamma = 3", "new_str": "gamma = 30"}]


def _edit_run(tmp_path, edits, multi):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "m.py").write_text(SRC)
    script = [call("edit_file", {"path": "m.py", "edits": edits}, "e1"), call("finish", {"summary": "done"}, "f")]
    result, rows, client = _run(tmp_path, script, config=CoreConfig(multi_edit=multi))
    out = next(r["result"] for r in rows if r["event"] == "tool" and r["name"] == "edit_file")
    return (tmp_path / "work" / "m.py").read_text(), out, client


def test_several_edits_land_in_one_call(tmp_path):
    text, out, client = _edit_run(tmp_path, EDITS, True)
    assert text == "alpha = 10\nbeta = 20\ngamma = 30\n"
    assert out.startswith("edited ") and "3 edits" in out
    spec = next(t for t in client.requests[0]["tools"] if t["function"]["name"] == "edit_file")
    assert "edits" in spec["function"]["parameters"]["properties"]


def test_known_bad_without_the_switch_edits_are_not_offered_or_applied(tmp_path):
    text, out, client = _edit_run(tmp_path, EDITS, False)
    assert text == SRC and "error" in out.lower()
    spec = next(t for t in client.requests[0]["tools"] if t["function"]["name"] == "edit_file")
    assert "edits" not in spec["function"]["parameters"]["properties"]


def test_one_missing_edit_writes_nothing(tmp_path):
    bad = [EDITS[0], {"old_str": "delta = 4", "new_str": "delta = 40"}, EDITS[2]]
    text, out, _ = _edit_run(tmp_path, bad, True)
    assert text == SRC
    assert "edit 2 of 3" in out and "no write attempted" in out


def test_later_edits_see_the_earlier_ones(tmp_path):
    chained = [{"old_str": "alpha = 1", "new_str": "alpha = 1\nalpha2 = 1"},
               {"old_str": "alpha2 = 1", "new_str": "alpha2 = 2"}]
    text, out, _ = _edit_run(tmp_path, chained, True)
    assert text == "alpha = 1\nalpha2 = 2\nbeta = 2\ngamma = 3\n"


def _cell(tmp_path, cap):
    (tmp_path / "work").mkdir()
    script = [call("python", {"code": "import time\ntime.sleep(4)\nprint('cell-' + 'done')", "wait_s": 300}, "p1"),
              *[call("python", {"code": "", "wait_s": 300}, f"p{i}") for i in range(2, 8)],
              call("finish", {"summary": "done"}, "f")]
    result, rows, client = _run(tmp_path, script, config=CoreConfig(repl=True, wait_cap_s=cap,
                                                                    control_dir=str(tmp_path / "control")))
    first = next(r for r in rows if r["event"] == "tool" and r["name"] == "python")
    return result, first, rows, client


def test_wait_cap_returns_the_call_while_the_cell_keeps_running(tmp_path):
    result, first, rows, client = _cell(tmp_path, 1.0)
    assert result.status == "finished"
    assert first["duration_s"] < 3 and "still running" in first["result"]
    later = [r["result"] for r in rows if r["event"] == "tool" and r["name"] == "python"][1:]
    assert any("cell-done" in r for r in later)  # the cap returned the call; it did not stop the work
    spec = next(t for t in client.requests[0]["tools"] if t["function"]["name"] == "python")
    assert "at most 1" in spec["function"]["parameters"]["properties"]["wait_s"]["description"]


def test_known_bad_without_the_cap_the_call_blocks_until_the_cell_ends(tmp_path):
    _, first, _, _ = _cell(tmp_path, 0.0)
    assert first["duration_s"] >= 3.5 and "cell-done" in first["result"]


def test_terminal_wait_is_capped_too():
    assert tool_variants.wait(CoreConfig(wait_cap_s=30.0), 300.0) == 30.0
    assert tool_variants.wait(CoreConfig(wait_cap_s=30.0), 10.0) == 10.0
    assert tool_variants.wait(CoreConfig(), 300.0) == 300.0


def test_switches_are_opt_in_and_validated():
    env = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off",
           "AETHER_CORE_IMAGES": "off"}
    base = build_config(environ=env)
    assert not base.multi_edit and base.wait_cap_s == 0.0
    on = build_config(environ={**env, "AETHER_CORE_MULTI_EDIT": "on", "AETHER_CORE_WAIT_CAP": "30"})
    assert on.multi_edit and on.wait_cap_s == 30.0
    for name in ("AETHER_CORE_MULTI_EDIT", "AETHER_CORE_WAIT_CAP"):
        with pytest.raises(ConfigError):
            build_config(environ={**env, name: "sometimes"})

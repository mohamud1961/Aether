"""CLM history: what a context edit, rollback or checkpoint removes stays, exactly as first shown, in a sandbox
file the model is told about; when that file cannot be written, the model is not told it exists."""
from __future__ import annotations

import json

from aether.core.clm import ClmContext, ClmSettings
from aether.core.loop import CoreConfig
from tests.core.core_fakes import call
from tests.core.test_core_v2 import _run, _text


def _config(tmp_path, history=None, **kw):
    history = history or str(tmp_path / "ctx" / "HISTORY.txt")
    return CoreConfig(context="clm", control_dir=str(tmp_path / "ctl"),
                      clm=ClmSettings(mirror_path=str(tmp_path / "ctx" / "LIVE_CTX.txt"), history_path=history, **kw))


def test_an_edit_keeps_what_it_removed_in_the_history_file(tmp_path):
    mirror, history = tmp_path / "ctx" / "LIVE_CTX.txt", tmp_path / "ctx" / "HISTORY.txt"
    script = [call("terminal", {"input": "echo SECRET-OLD-OUTPUT"}, "c1"),
              call("write_file", {"path": str(mirror), "content": "[[CTX_TURN 0 role=user]]\nnote: echo worked"}, "c2"),
              call("finish", {"summary": "done"}, "c3")]
    result, rows, client = _run(tmp_path, script, config=_config(tmp_path))
    last = json.dumps(client.requests[-1]["messages"])
    assert "SECRET-OLD-OUTPUT" not in last and f"kept unchanged in {history}" in last
    text = history.read_text()
    assert "[[MSG 0 role=assistant]]" in text and "[[MSG 1 role=tool]]" in text
    assert "SECRET-OLD-OUTPUT" in text.split("[[MSG 1 role=tool]]")[1]  # the result itself, not only the command


def test_a_checkpoint_keeps_the_summarised_turns_in_the_history_file(tmp_path):
    big = "y" * 3000
    script = [call("terminal", {"input": f"echo {i}{big}"}, f"c{i}") for i in range(6)]
    script += [call("finish", {"summary": "done"}, "c9")]
    config = _config(tmp_path, budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=2500)
    result, rows, client = _run(tmp_path, script, config=config,
                                text_script=[_text(f"## Goal\nSUMMARY-{k}") for k in range(3)])
    final = json.dumps(client.requests[-1]["messages"])
    assert "echo 0" + "y" * 50 not in final and "kept unchanged in" in final
    assert "0" + big in (tmp_path / "ctx" / "HISTORY.txt").read_text()


def test_a_history_that_cannot_be_written_is_traced_and_never_claimed(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    mirror = tmp_path / "ctx" / "LIVE_CTX.txt"
    script = [call("terminal", {"input": "echo OLD"}, "c1"),
              call("write_file", {"path": str(mirror), "content": "[[CTX_TURN 0 role=user]]\nnote"}, "c2"),
              call("finish", {"summary": "done"}, "c3")]
    result, rows, client = _run(tmp_path, script, config=_config(tmp_path, history=str(blocker / "HISTORY.txt")))
    assert result.status == "finished"
    assert any(r["event"] == "history_save_error" for r in rows)
    assert "kept unchanged" not in json.dumps(client.requests[-1]["messages"])
    assert [r for r in rows if r["event"] == "context_edit"][0]["accepted"] is True  # the edit itself still applies


def test_a_rollback_says_where_the_dropped_output_is_kept():
    ctx = ClmContext(pinned=[{"role": "system", "content": "s"}], settings=ClmSettings(max_rollbacks=1))
    ctx.append({"role": "assistant", "content": None, "tool_calls": [
        {"id": "a", "type": "function", "function": {"name": "terminal", "arguments": '{"input": "cat big"}'}}]},
        {"role": "tool", "tool_call_id": "a", "content": "BIG-OUTPUT"})
    note = ctx.roll_back(" (kept in H)")
    assert "dropped from your context (kept in H)" in note and "BIG-OUTPUT" not in json.dumps(ctx.editable)
    assert "BIG-OUTPUT" in ctx.render_history()

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
    return CoreConfig(
        context="clm",
        control_dir=str(tmp_path / "ctl"),
        clm=ClmSettings(
            mirror_path=str(tmp_path / "ctx" / "LIVE_CTX.txt"),
            history_path=history,
            **kw,
        ),
    )


def test_an_edit_keeps_what_it_removed_in_the_history_file(tmp_path):
    mirror, history = (
        tmp_path / "ctx" / "LIVE_CTX.txt",
        tmp_path / "ctx" / "HISTORY.txt",
    )
    script = [
        call("terminal", {"input": "echo SECRET-OLD-OUTPUT"}, "c1"),
        call(
            "write_file",
            {
                "path": str(mirror),
                "content": "[[CTX_TURN 0 role=user]]\nnote: echo worked",
            },
            "c2",
        ),
        call("finish", {"summary": "done"}, "c3"),
    ]
    result, rows, client = _run(tmp_path, script, config=_config(tmp_path))
    last = json.dumps(client.requests[-1]["messages"])
    assert "SECRET-OLD-OUTPUT" not in last and f"kept unchanged in {history}" in last
    text = history.read_text()
    assert "[[MSG 0 role=assistant]]" in text and "[[MSG 1 role=tool]]" in text
    assert (
        "SECRET-OLD-OUTPUT" in text.split("[[MSG 1 role=tool]]")[1]
    )  # the result itself, not only the command


def test_a_checkpoint_keeps_the_summarised_turns_in_the_history_file(tmp_path):
    big = "y" * 3000
    script = [call("terminal", {"input": f"echo {i}{big}"}, f"c{i}") for i in range(6)]
    script += [call("finish", {"summary": "done"}, "c9")]
    config = _config(
        tmp_path, budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=2500
    )
    result, rows, client = _run(
        tmp_path,
        script,
        config=config,
        text_script=[_text(f"## Goal\nSUMMARY-{k}") for k in range(3)],
    )
    final = json.dumps(client.requests[-1]["messages"])
    assert "echo 0" + "y" * 50 not in final and "kept unchanged in" in final
    assert "0" + big in (tmp_path / "ctx" / "HISTORY.txt").read_text()


def test_a_history_that_cannot_be_written_is_traced_and_never_claimed(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    mirror = tmp_path / "ctx" / "LIVE_CTX.txt"
    script = [
        call("terminal", {"input": "echo OLD"}, "c1"),
        call(
            "write_file",
            {"path": str(mirror), "content": "[[CTX_TURN 0 role=user]]\nnote"},
            "c2",
        ),
        call("read_history", {"message_id": 1}, "c3"),
        call("finish", {"summary": "done"}, "c4"),
    ]
    result, rows, client = _run(
        tmp_path, script, config=_config(tmp_path, history=str(blocker / "HISTORY.txt"))
    )
    assert result.status == "finished"
    assert any(r["event"] == "history_save_error" for r in rows)
    assert "kept unchanged" not in json.dumps(client.requests[-1]["messages"])
    assert "history save failed" in json.dumps(client.requests[-1]["messages"])
    assert [r for r in rows if r["event"] == "context_edit"][0][
        "accepted"
    ] is True  # the edit itself still applies
    recovered = next(
        r["result"]
        for r in rows
        if r["event"] == "tool" and r["name"] == "read_history"
    )
    message = json.loads(recovered.split("\n", 1)[1])
    assert message["tool_call_id"] == "c1" and "OLD" in message["content"]


def test_a_rollback_says_where_the_dropped_output_is_kept():
    ctx = ClmContext(
        pinned=[{"role": "system", "content": "s"}],
        settings=ClmSettings(max_rollbacks=1),
    )
    ctx.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "a",
                    "type": "function",
                    "function": {
                        "name": "terminal",
                        "arguments": '{"input": "cat big"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "a", "content": "BIG-OUTPUT"},
    )
    note = ctx.roll_back(" (kept in H)")
    assert (
        "dropped from your context (kept in H)" in note
        and "BIG-OUTPUT" not in json.dumps(ctx.editable)
    )
    assert "BIG-OUTPUT" in ctx.render_history()


def test_original_observation_and_reasoning_survive_later_annotations():
    ctx = ClmContext(pinned=[])
    ctx.append(
        {
            "role": "assistant",
            "content": None,
            "reasoning_content": "original derivation",
        },
        {"role": "tool", "tool_call_id": "a", "content": "original result"},
    )
    before = ctx.render_history()
    ctx.editable[-1]["content"] += "\nnew annotation"
    assert ctx.render_history() == before
    assert "original derivation" in before and '"tool_call_id": "a"' in before


def test_historical_message_pages_reassemble_exactly():
    ctx = ClmContext(pinned=[])
    original = {"role": "tool", "tool_call_id": "a", "content": "α" * 25000}
    ctx.append(original)
    first = ctx.read_history(0, limit=20000)
    rest = ctx.read_history(0, offset=20000, limit=20000)
    assert "next offset=20000" in first and "; complete]" in rest
    assert json.loads(first.split("\n", 1)[1] + rest.split("\n", 1)[1]) == original


def test_context_edit_via_shell_variable_uses_configured_paths(tmp_path):
    import shlex

    mirror = tmp_path / "ctx" / "custom-view.txt"
    script = [
        call("terminal", {"input": "echo OLD-OBSERVATION"}, "c1"),
        call(
            "terminal",
            {"input": f"export CONTEXT_FILE={shlex.quote(str(mirror))}"},
            "c2",
        ),
        call(
            "terminal",
            {
                "input": "printf '[[CTX_TURN 0 role=user]]\\nKEEP-ONLY\\n' > \"$CONTEXT_FILE\""
            },
            "c3",
        ),
        call("read_history", {"message_id": 1}, "c4"),
        call("finish", {"summary": "done"}, "c5"),
    ]
    config = _config(tmp_path)
    config.clm.mirror_path = str(mirror)
    result, rows, client = _run(tmp_path, script, config=config)
    assert str(mirror) in client.requests[0]["messages"][0]["content"]
    assert any(r["event"] == "context_edit" and r["accepted"] for r in rows)
    assert "KEEP-ONLY" in json.dumps(client.requests[-1]["messages"])
    recovered = next(
        r["result"]
        for r in rows
        if r["event"] == "tool" and r["name"] == "read_history"
    )
    assert "OLD-OBSERVATION" in recovered and result.status == "finished"


def test_missing_reasoning_usage_does_not_make_replayed_text_cost_zero():
    ctx = ClmContext(pinned=[])
    message = {"role": "assistant", "content": None, "reasoning_content": "x" * 30000}
    ctx.append(message)
    ctx.note_reasoning(message, None)
    assert (
        ctx.tokens() >= 10000
    )  # bytes remain in the request even when the provider omits their count
    ctx.calibrate(36000, 12000)
    assert 1.5 <= ctx.chars_per_token <= 6

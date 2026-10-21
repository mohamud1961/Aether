"""A context edit changes only what the model changed (P1, 2026-10-21).

R5.base.protein-assembly e1r2: after a one-line edit of LIVE_CTX.txt the next request held 52 user messages instead
of 2: every untouched tool result came back as role=user labelled "[your notes]", and every tool call as
"[tool_call ...]" text. Blocks the model left exactly as rendered keep their original message; a tool call and its
results stay native only together, so the request never carries an orphaned call or result.
"""

import pytest

from aether.core.clm import NOTES_TAG, ClmContext, ClmSettings

PINNED = [{"role": "system", "content": "sys"}, {"role": "user", "content": "the task"}]


def _call(cid, name, args):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": args}}


def _history():
    return [
        {"role": "assistant", "content": "", "reasoning_content": "plan", "tool_calls": [_call("c1", "terminal", '{"input": "ls"}')]},
        {"role": "tool", "tool_call_id": "c1", "content": "a.txt\n[exit 0 · 0.1s · terminal main · cwd /app]"},
        {"role": "assistant", "content": "", "tool_calls": [_call("c2", "read_file", '{"path": "a.txt"}'), _call("c3", "read_file", '{"path": "b.txt"}')]},
        {"role": "tool", "tool_call_id": "c2", "content": "alpha"},
        {"role": "tool", "tool_call_id": "c3", "content": "beta"},
        {"role": "user", "content": "[context] a harness note"},
    ]


def _ctx(voice):
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(notes_voice=voice))
    ctx.append(*_history())
    return ctx


@pytest.mark.parametrize("voice", ["own", "legacy"])
def test_an_edit_elsewhere_keeps_untouched_calls_and_results_native(voice):
    ctx = _ctx(voice)
    upto = len(ctx.editable)
    text = ctx.render(upto).replace("[context] a harness note", "my summary: a.txt holds alpha")
    ok, _ = ctx.apply_edit(text, upto)
    assert ok
    roles = [m["role"] for m in ctx.editable]
    assert roles == ["assistant", "tool", "assistant", "tool", "tool", "user"]
    assert ctx.editable[0]["tool_calls"][0]["id"] == "c1" and ctx.editable[1]["tool_call_id"] == "c1"
    assert ctx.editable[0].get("reasoning_content") == "plan"  # the original message, not a rebuilt one
    assert not any(str(m.get("content", "")).startswith(NOTES_TAG) for m in ctx.editable[:5])
    assert "my summary" in ctx.editable[5]["content"]  # what the model wrote is still its own record


def test_a_changed_result_takes_its_call_with_it_to_text():
    ctx = _ctx("own")
    upto = len(ctx.editable)
    text = ctx.render(upto).replace("beta", "beta (checked)")
    ok, _ = ctx.apply_edit(text, upto)
    assert ok
    assert [m["role"] for m in ctx.editable[:2]] == ["assistant", "tool"]  # the untouched unit stays native
    tail = ctx.editable[2:]
    assert all("tool_calls" not in m and m["role"] in ("assistant", "user") for m in tail)
    assert any("beta (checked)" in m["content"] and m["content"].startswith(NOTES_TAG) for m in tail)


def test_a_dropped_result_never_leaves_an_orphaned_call():
    ctx = _ctx("legacy")
    upto = len(ctx.editable)
    text = ctx.render(upto)
    start = text.index("[[CTX_TURN 4 role=tool]]")
    text = text[:start] + text[text.index("[[CTX_TURN 5 role=user]]"):]
    ok, _ = ctx.apply_edit(text, upto)
    assert ok
    ids = {c["id"] for m in ctx.editable for c in m.get("tool_calls") or ()}
    answered = {m["tool_call_id"] for m in ctx.editable if m["role"] == "tool"}
    assert ids == answered == {"c1"}


def test_a_marker_naming_another_turn_is_not_trusted():
    ctx = _ctx("legacy")
    upto = len(ctx.editable)
    text = ctx.render(upto).replace("[[CTX_TURN 1 role=tool]]", "[[CTX_TURN 4 role=tool]]")
    ok, _ = ctx.apply_edit(text, upto)
    assert ok
    assert ctx.editable[0]["role"] == "assistant" and "tool_calls" not in ctx.editable[0]

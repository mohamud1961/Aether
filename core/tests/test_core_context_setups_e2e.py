"""E18 context setups through the real Core loop: K1 provider-native compaction, K2 rehydration, both off = stock.

K1: the request asks the provider to compact past a threshold; the opaque compaction item it returns is replayed,
and nothing older than it is sent again. K2: after the context is shortened, the files the run changed are shown
again with their current bytes. Known-bads: without CLM's cut at the compaction item the older call is resent; with
the switch off no rehydration note appears even though the file changed.
"""

import asyncio

import pytest

from aether.core import clm as clm_mod
from aether.core import rehydrate
from aether.core.clm import ClmSettings
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.responses import ResponsesProvider
from tests.core_fakes import LocalEnv
from tests.test_core_responses import ResponsesClient, ev, item, provider, turn_events


def compacting(n, call):
    """A response whose output starts with the provider's opaque compaction item."""
    events = turn_events(n, call=call)
    events.insert(1, ev("response.output_item.done",
                        item=item(type="compaction", id=f"cmp{n}", encrypted_content=f"packed{n}")))
    return events


def native(client, tmp_path, threshold=20_000):
    tmp_path.mkdir(exist_ok=True)
    from aether.core.calls import CallLog
    return ResponsesProvider(client, model="GPT-6-Luna", log=CallLog(tmp_path / "calls"),
                             params={"reasoning_effort": "high", "tool_choice": "required",
                                     "parallel_tool_calls": False},
                             native_compaction=threshold)


def run(tmp_path, prov, client, rehydrate_on=False):
    work = tmp_path / "w"
    work.mkdir(parents=True, exist_ok=True)
    control = tmp_path / "ctl"
    clm = ClmSettings(replay_reasoning="all", mirror_path=str(control / "live.txt"),
                      history_path=str(control / "history.txt"))
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="write notes.txt then finish", workdir=str(work), provider=prov,
        timeout_s=60, trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(context="clm", clm=clm, rehydrate=rehydrate_on, control_dir=str(control)),
    ))
    return work, result


def script(work_hint="notes.txt"):
    return [
        turn_events(1, call=("write_file", {"path": work_hint, "content": "draft one\n"}, "c1")),
        compacting(2, ("terminal", {"input": f"echo final >> {work_hint}"}, "c2")),
        turn_events(3, call=("finish", {"summary": "done"}, "c3")),
    ]


def ids(request):
    return [(i.get("type"), i.get("id") or i.get("call_id")) for i in request["input"] if "type" in i]


def test_request_asks_for_compaction_only_when_switched_on(tmp_path):
    on = ResponsesClient([turn_events(1, call=("finish", {"summary": "x"}, "c1"))])
    off = ResponsesClient([turn_events(1, call=("finish", {"summary": "x"}, "c1"))])
    run(tmp_path / "on", native(on, tmp_path / "p-on"), on)
    run(tmp_path / "off", provider(off, tmp_path / "p-off"), off)
    assert on.requests[0]["extra_body"]["context_management"] == [{"type": "compaction", "compact_threshold": 20_000}]
    assert "extra_body" not in off.requests[0]
    import json
    stripped = {k: v for k, v in on.requests[0].items() if k not in ("extra_body", "prompt_cache_key")}
    same = {k: v for k, v in off.requests[0].items() if k != "prompt_cache_key"}
    # identical apart from the switch (the two runs differ only in their working directory name)
    assert json.dumps(stripped, sort_keys=True).replace("/on/", "/X/") == \
        json.dumps(same, sort_keys=True).replace("/off/", "/X/")


def test_misconfiguration_stops_rather_than_falling_back(tmp_path):
    with pytest.raises(ValueError):
        ResponsesProvider(ResponsesClient([]), model="m", params={}, chain=True, native_compaction=20_000)
    with pytest.raises(ValueError):
        ResponsesProvider(ResponsesClient([]), model="m", params={}, native_compaction=10)
    from aether.core.harbor_agent import _native_compaction
    assert _native_compaction({}) is None and _native_compaction({"AETHER_CORE_NATIVE_COMPACTION": "off"}) is None
    assert _native_compaction({"AETHER_CORE_NATIVE_COMPACTION": "48000"}) == 48000
    with pytest.raises(ValueError):
        _native_compaction({"AETHER_CORE_NATIVE_COMPACTION": "yes"})


def test_compaction_item_is_replayed_and_nothing_older_is_sent(tmp_path):
    client = ResponsesClient(script())
    work, result = run(tmp_path, native(client, tmp_path / "p"), client)
    assert result.status == "finished" and (work / "notes.txt").read_text() == "draft one\nfinal\n"
    third = ids(client.requests[2])
    assert third[0] == ("compaction", "cmp2")  # the opaque item comes first, before that turn's own output
    assert ("function_call", "c2") in third and ("function_call_output", "c2") in third
    assert ("function_call", "c1") not in third and ("reasoning", "rs1") not in third  # folded into the item
    roles = [i.get("role") for i in client.requests[2]["input"] if "role" in i]
    assert roles[:2] == ["system", "user"]  # the pinned system prompt and task are still sent


def test_known_bad_without_the_cut_the_older_call_is_resent(tmp_path, monkeypatch):
    append = clm_mod.ClmContext.append

    def keep_folded_turns(self, *messages):
        old = list(self.editable)
        append(self, *messages)
        if any(m.get("compaction") for m in messages):
            self.editable[:0] = old

    monkeypatch.setattr(clm_mod.ClmContext, "append", keep_folded_turns)
    client = ResponsesClient(script())
    run(tmp_path, native(client, tmp_path / "p"), client)
    assert ("function_call", "c1") in ids(client.requests[2])


@pytest.mark.parametrize("on", [True, False])
def test_rehydration_shows_current_bytes_after_compaction_only_when_on(tmp_path, on):
    client = ResponsesClient(script())
    run(tmp_path, native(client, tmp_path / "p"), client, rehydrate_on=on)
    text = "\n".join(str(i.get("output", "")) for i in client.requests[2]["input"] if i.get("type") == "function_call_output")
    if on:
        assert rehydrate.HEADER in text
        assert "notes.txt (16 bytes)\ndraft one\nfinal" in text  # current bytes, including the shell's append
    else:
        assert rehydrate.HEADER not in text
    rows = (tmp_path / "trace.jsonl").read_text()
    assert ('"rehydrate"' in rows) is on and '"native_compaction"' in rows


def test_rehydrate_note_reports_missing_binary_and_cut_files(tmp_path):
    (tmp_path / "big.txt").write_text("x" * 50)
    (tmp_path / "bin.dat").write_bytes(b"ab\x00cd")
    (tmp_path / "keep.txt").write_text("k\n")
    written = [str(tmp_path / p) for p in ("keep.txt", "gone.txt", "bin.dat", "big.txt")]
    note, row = asyncio.run(rehydrate.note(LocalEnv(tmp_path), written, max_chars=10))
    lines = note.split("\n")
    assert lines[0] == rehydrate.HEADER
    assert lines[1].startswith(f"--- {tmp_path}/big.txt (50 bytes; first 10 characters)") and lines[2] == "x" * 10
    assert f"--- {tmp_path}/bin.dat (5 bytes, binary; not shown)" in note
    assert f"--- {tmp_path}/gone.txt: no longer exists" in note
    assert row == {"files": 4, "shown": 2, "missing": 1}
    assert asyncio.run(rehydrate.note(LocalEnv(tmp_path), [])) == ("", {"files": 0})


@pytest.mark.parametrize("on", [True, False])
def test_rehydration_after_cores_own_checkpoint(tmp_path, on):
    """K2 on the CLM path: a checkpoint replaces old turns with a summary; the changed file is shown again."""
    import dataclasses
    import json

    from tests.test_core_v2 import _clm_config, _run, _text
    from tests.core_fakes import call

    big = "y" * 3000
    script = [call("write_file", {"path": "plan.txt", "content": "v1\n"}, "w1")]
    script += [call("terminal", {"input": f"echo {i}{big}"}, f"c{i}") for i in range(6)]
    script += [call("finish", {"summary": "done"}, "c9")]
    config = dataclasses.replace(
        _clm_config(tmp_path, budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=2500), rehydrate=on)
    texts = [_text(f"## Goal\nSUMMARY-MARKER-{k}") for k in range(4)]
    result, rows, client = _run(tmp_path, script, config=config, text_script=texts)
    assert result.status == "finished"
    assert any(r["event"] == "context_checkpoint" and r["ok"] for r in rows), "no checkpoint: the test proves nothing"
    after = json.dumps([r["messages"] for r in client.requests if "tools" in r][-1])
    assert (rehydrate.HEADER in after) is on
    if on:
        assert "plan.txt (3 bytes)\\nv1" in after
        assert any(r["event"] == "rehydrate" and r["cause"] == "checkpoint" and r["shown"] == 1 for r in rows)



def test_a_mirror_edit_cannot_drop_the_provider_compaction_anchor(tmp_path):
    from json import loads

    tape = script()
    tape[2:] = [
        turn_events(3, call=("write_file", {"path": str(tmp_path / "ctl/live.txt"),
                                           "content": "## Notes\nKeep the final draft.\n"}, "c3")),
        turn_events(4, call=("read_history", {"message_id": 0}, "c4")),
        turn_events(5, call=("finish", {"summary": "done"}, "c5")),
    ]
    client = ResponsesClient(tape)
    work, result = run(tmp_path, native(client, tmp_path / "p"), client)
    assert result.status == "finished" and (work / "notes.txt").read_text() == "draft one\nfinal\n"
    events = [loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert any(e["event"] == "context_edit" and e["accepted"] for e in events)
    assert ("compaction", "cmp2") in ids(client.requests[3])
    assert ("function_call", "c1") not in ids(client.requests[3])
    outputs = [i for i in client.requests[4]["input"] if i.get("call_id") == "c4"]
    assert any("draft one" in i.get("output", "") for i in outputs)



def test_missing_opaque_content_does_not_discard_history_or_dispatch_the_incomplete_turn(tmp_path):
    tape = script()
    bad = turn_events(2, call=("terminal", {"input": "echo incomplete > wrong-action"}, "bad"))
    bad.insert(1, ev("response.output_item.done", item=item(type="compaction", id="invalid", encrypted_content="")))
    client = ResponsesClient([tape[0], bad, tape[1], tape[2]])
    work, result = run(tmp_path, native(client, tmp_path / "p"), client)
    assert result.status == "finished"
    assert not (work / "wrong-action").exists()
    assert ("function_call", "c1") in ids(client.requests[2])
    assert ("compaction", "cmp2") in ids(client.requests[3])

"""Run state: only harness-run checks set a status, failures stay in view, finish re-checks and holds once."""

import asyncio

import pytest

from aether.core.runstate import STATE_TOOL, RunState, with_state
from aether.core.tools import tools, validate_call
from tests.core_fakes import LocalEnv

TASK = """Write the answer to /app/out.txt.
- The answer must start with bee26a.
- Print every mate-in-one move, one per line.
"""


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _state(tmp_path, clock=None):
    return RunState(TASK, str(tmp_path), clock=clock or Clock()), LocalEnv(tmp_path)


def act(state, env, **args):
    return asyncio.run(state.act(env, args, remaining_s=600))


def test_with_state_adds_the_tool_and_ties_finish_to_it():
    out = with_state(tools(python=False))
    names = [t["function"]["name"] for t in out]
    assert names.count("finish") == 1 and names[-2:] == ["state", "finish"]
    assert "every requirement's check passes" in out[-1]["function"]["description"]
    validate_call("state", {"action": "require", "quote": "x", "check": "true"}, out)
    with pytest.raises(ValueError, match="unknown argument 'status'"):  # the model cannot set a status
        validate_call("state", {"action": "check", "id": 1, "status": "passed"}, out)
    assert STATE_TOOL["function"]["parameters"]["properties"]["action"]["enum"][-1] == "show"


def test_require_takes_only_the_tasks_own_words(tmp_path):
    state, env = _state(tmp_path)
    out = act(state, env, action="require", quote="the answer must be blue", check="true")
    assert out.startswith("error:") and not state.items
    out = act(state, env, action="require", quote="the answer  MUST start with bee26a", check="true")
    assert "item 1 added" in out and state.items[0].status == "unchecked"


def test_only_a_check_run_sets_passed_or_failed(tmp_path):
    state, env = _state(tmp_path)
    (tmp_path / "out.txt").write_text("0804ab\n")
    act(state, env, action="require", quote="must start with bee26a", check="grep -q '^bee26a' out.txt")
    out = act(state, env, action="check", id=1)
    assert state.items[0].status == "failed" and state.items[0].exit == 1 and "failed (exit 1)" in out
    assert "failing #1" in state.reminder()
    (tmp_path / "out.txt").write_text("bee26a77\n")
    act(state, env, action="check", id=1)
    assert state.items[0].status == "passed" and state.reminder() == ""


def test_a_write_makes_passed_items_stale(tmp_path):
    state, env = _state(tmp_path)
    act(state, env, action="require", quote="must start with bee26a", check="true")
    act(state, env, action="check", id=1)
    state.wrote()
    assert state.items[0].status == "stale" and state.dirty


def test_an_item_without_a_check_or_with_a_bad_id_is_an_error_not_a_pass(tmp_path):
    state, env = _state(tmp_path)
    act(state, env, action="require", quote="must start with bee26a")
    assert act(state, env, action="check", id=1).startswith("error:")
    assert act(state, env, action="check", id=9).startswith("error:")
    assert state.items[0].status == "unchecked"


def test_uncovered_requirement_sentences_are_listed(tmp_path):
    state, env = _state(tmp_path)
    act(state, env, action="require", quote="The answer must start with bee26a.", check="true")
    missing = state.uncovered()
    assert any("mate-in-one" in s for s in missing) and not any("bee26a" in s for s in missing)
    assert "no item quotes" in state.view()


def test_finish_rechecks_and_holds_once_with_time_left(tmp_path):
    state, env = _state(tmp_path)
    (tmp_path / "out.txt").write_text("bee26a\n")
    act(state, env, action="require", quote="must start with bee26a", check="grep -q '^bee26a' out.txt")
    act(state, env, action="require", quote="Print every mate-in-one move, one per line.", check="test -s moves.txt")
    act(state, env, action="check", id=1)
    held, text = asyncio.run(state.at_finish(env, remaining_s=600, timeout_s=900))
    assert held and "#2 failed" in text and "next finish ends the work" in text
    assert state.items[0].status == "passed"  # re-run on the delivered state
    held, _ = asyncio.run(state.at_finish(env, remaining_s=600, timeout_s=900))
    assert not held  # never a second hold


def test_no_hold_when_little_time_remains_or_nothing_is_open(tmp_path):
    state, env = _state(tmp_path)
    act(state, env, action="require", quote="must start with bee26a", check="false")
    held, _ = asyncio.run(state.at_finish(env, remaining_s=50, timeout_s=900))
    assert not held and state.final_checked
    ok, env2 = _state(tmp_path)
    act(ok, env2, action="require", quote="The answer must start with bee26a.", check="true")
    act(ok, env2, action="require", quote="Print every mate-in-one move, one per line.", check="true")
    act(ok, env2, action="require", quote="Write the answer to /app/out.txt.", check="true")
    assert ok.uncovered() == []
    held, _ = asyncio.run(ok.at_finish(env2, remaining_s=600, timeout_s=900))
    assert not held


def test_give_up_and_notes_are_reported_truthfully(tmp_path):
    state, env = _state(tmp_path)
    act(state, env, action="require", quote="must start with bee26a", check="false")
    act(state, env, action="check", id=1)
    act(state, env, action="note", text="best deliverable so far: /app/out.txt (hash of image bytes)")
    act(state, env, action="give_up", id=1, text="cannot read the salt from the image")
    acct = state.account()
    assert "#1 given_up" in acct and "cannot read the salt" in acct and "best deliverable" in acct
    assert "did not reach finish" in acct
    assert act(state, env, action="give_up", id=1).startswith("error:")  # a reason is required


def test_the_flag_reaches_the_core_config():
    from aether.core.harbor_agent import build_config

    base = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off",
            "AETHER_CORE_IMAGES": "off"}
    assert build_config(environ=base).state is False
    assert build_config(environ={**base, "AETHER_CORE_STATE": "on"}).state is True


def _run(tmp_path, events, state):
    from aether.core.loop import CoreConfig, Trace, run_agent
    from tests.test_core_responses import ResponsesClient, provider

    work = tmp_path / "w"
    work.mkdir()
    client = ResponsesClient(events)
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="Write hi to f.txt.\n- f.txt must contain hi.",
            workdir=str(work),
            provider=provider(client, tmp_path),
            timeout_s=600,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), state=state),
        )
    )
    return result, client, work


def test_the_loop_holds_a_finish_with_a_failing_check_then_ends_on_the_next(tmp_path):
    from tests.test_core_responses import turn_events

    events = [
        turn_events(1, call=("state", {"action": "require", "quote": "f.txt must contain hi",
                                       "check": "grep -q hi f.txt"}, "c1")),
        turn_events(2, call=("finish", {"summary": "done"}, "c2")),
        turn_events(3, call=("terminal", {"input": "echo hi > f.txt"}, "c3")),
        turn_events(4, call=("finish", {"summary": "wrote f.txt"}, "c4")),
    ]
    result, client, work = _run(tmp_path, events, state=True)
    assert result.status == "finished" and (work / "f.txt").read_text().strip() == "hi"
    names = [t["name"] for t in client.requests[0]["tools"]]
    assert "state" in names
    after_hold = str(client.requests[2]["input"])
    assert "the finish did not take effect" in after_hold and "#1 failed" in after_hold
    rs = result.extras["run_state"]
    assert rs["held"] and rs["items"][0]["status"] == "passed" and rs["final_checked"]
    assert "## Run state" in result.final_account and "#1 passed" in result.final_account


def test_flag_off_is_the_baseline(tmp_path):
    from tests.test_core_responses import turn_events

    events = [turn_events(1, call=("finish", {"summary": "done"}, "c1"))]
    result, client, _ = _run(tmp_path, events, state=False)
    assert result.status == "finished"
    assert "state" not in [t["name"] for t in client.requests[0]["tools"]]
    assert "run_state" not in result.extras and "## Run state" not in result.final_account


def test_notes_and_failures_survive_a_context_checkpoint(tmp_path):
    """The checkpoint summary is the model's; the run state (notes, failing checks) is shown again whole after it."""
    import dataclasses
    import json

    from tests.core_fakes import call
    from tests.test_core_v2 import TASK as V2_TASK, _clm_config, _run, _text

    quote = V2_TASK.split(".")[0].strip()
    big = "y" * 3000
    script = [
        call("state", {"action": "require", "quote": quote, "check": "test -f never-made.txt"}, "s1"),
        call("state", {"action": "check", "id": 1}, "s2"),
        call("state", {"action": "note", "text": "KEY-PROGRESS-NOTE best result in /tmp/best.bin"}, "s3"),
    ]
    script += [call("terminal", {"input": f"echo {i}{big}"}, f"c{i}") for i in range(6)]
    script += [call("finish", {"summary": "done"}, "f1"), call("finish", {"summary": "done"}, "f2")]
    config = dataclasses.replace(
        _clm_config(tmp_path, budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=2500), state=True
    )
    texts = [_text(f"## Goal\nSUMMARY-MARKER-{k}") for k in range(4)]
    result, rows, client = _run(tmp_path, script, config=config, text_script=texts)
    assert result.status == "finished"
    assert [r for r in rows if r["event"] == "context_checkpoint" and r["ok"]], "no checkpoint happened"
    tool_requests = [r for r in client.requests if "tools" in r]
    after = next(i for i, r in enumerate(tool_requests) if "SUMMARY-MARKER" in json.dumps(r["messages"]))
    later = json.dumps(tool_requests[after + 1]["messages"]) if after + 1 < len(tool_requests) else ""
    assert "KEY-PROGRESS-NOTE" in later and "#1 [failed" in later  # re-shown after the checkpoint
    assert "[state: failing #1" in json.dumps(tool_requests[-1]["messages"])  # the reminder rides every result
    assert result.extras["run_state"]["held"] is True

"""Task artifact and original evidence across repeated portable context cuts."""

import asyncio
import json
from dataclasses import replace

import pytest

from aether.core.clm import ClmSettings
from aether.core.harbor_agent import build_config
from aether.core.harbor_config import ConfigError
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.responses import ResponsesProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk, tool_chunk
from tests.test_core_responses import ResponsesClient, ev, item, turn_events
from tests.test_core_v2 import _text


class EvidenceClient(ScriptedClient):
    """A scripted client reads a real history response before writing its artifact."""

    async def _create(self, **kwargs):
        if "tools" in kwargs and not getattr(self, "delivered", False):
            recall = next((m for m in kwargs["messages"]
                           if m.get("role") == "tool" and m.get("tool_call_id") == "recall"), None)
            if recall:
                original, _ = json.JSONDecoder().raw_decode(recall["content"].split("\n", 1)[1])
                label = next(line.split("label=", 1)[1] for line in original["content"].splitlines()
                             if "label=" in line)
                self.script.insert(0, call("write_file", {"path": "report.txt", "content": label}, "deliver"))
                self.delivered = True
        return await super()._create(**kwargs)


def score(work, expected):
    path = work / "report.txt"
    return int(path.exists() and path.read_text() == expected)


def execute(root, policy, *, rehydrate=False):
    work, control = root / "work", root / "control"
    work.mkdir(parents=True)
    expected = "North-α"
    (work / "source.txt").write_text(f"label={expected}\n")
    (work / "other.txt").write_text("independent\n")
    first = [tool_chunk("read_file", {"path": "source.txt"}, 0, "old"),
             tool_chunk("read_file", {"path": "other.txt"}, 1, "other"), chunk(finish="tool_calls")]
    script = [first,
              call("write_file", {"path": "source.txt", "content": "label=South\n"}, "change")]
    script += [call("terminal", {"input": "printf '%s' '" + str(i) + "x" * 6000 + "'"}, f"noise{i}")
               for i in range(12)]
    script += [call("read_history", {"message_id": 1}, "recall"), call("finish", {"summary": "done"}, "finish")]
    client = EvidenceClient(script, text_script=[_text("## Progress\nThe earlier label is in the original history.")
                                                  for _ in range(20)])
    settings = ClmSettings(budget_tokens=9000, reserve_tokens=500, keep_recent_tokens=2500,
                           mirror_path=str(control / "live"), history_path=str(control / "history"))
    if policy == "window":
        settings = replace(settings, checkpoint_policy="window")
    config = CoreConfig(context="clm", control_dir=str(control), clm=settings, rehydrate=rehydrate)
    trace = root / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Record the original label from source.txt after changing that file.",
        workdir=str(work), provider=ChatProvider(client, model="offline-script", params={}),
        timeout_s=120, trace=Trace(trace), config=config,
    ))
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    return result, events, client, work, expected


def test_existing_summary_baseline_can_recover_overwritten_observation(tmp_path):
    result, events, client, work, expected = execute(tmp_path, "summary")
    assert result.status == "finished", result.error
    assert score(work, expected) == 1
    assert any(event["event"] == "context_checkpoint" and event.get("ok") for event in events)
    assert any("tools" not in request for request in client.requests)
    (work / "report.txt").write_text("South")
    assert score(work, expected) == 0


@pytest.mark.parametrize("fail_history", [False, True])
def test_window_recovers_original_without_summary_call(tmp_path, monkeypatch, fail_history):
    if fail_history:
        from aether.core import loop_context
        original = loop_context.put_bytes

        async def fail_history_write(env, content, path):
            if path.endswith("/history"):
                raise OSError("fixture prevents history file writes")
            return await original(env, content, path)

        monkeypatch.setattr(loop_context, "put_bytes", fail_history_write)
    result, events, client, work, expected = execute(tmp_path, "window")
    assert result.status == "finished"
    assert score(work, expected) == 1 and (work / "source.txt").read_text() == "label=South\n"
    assert len([event for event in events if event["event"] == "context_window_cut"]) >= 2
    assert not any("tools" not in request for request in client.requests)
    shown = json.dumps(client.requests, ensure_ascii=False)
    assert "Older turns were removed without a summary" in shown
    assert any("original label from source.txt" in str(m.get("content"))
               for m in client.requests[-1]["messages"])
    for request in client.requests:
        pending = []
        for message in request["messages"]:
            if message["role"] == "assistant":
                assert not pending
                pending = [item["id"] for item in message.get("tool_calls") or []]
            elif message["role"] == "tool":
                assert pending and message["tool_call_id"] == pending.pop(0)
        assert not pending
    if fail_history:
        assert any(event["event"] == "history_save_error" for event in events)
        assert "history save failed" in shown


def test_window_profile_is_opt_in_and_rejects_unavailable_history():
    env = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm",
           "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}
    assert build_config(environ=env).clm.checkpoint_policy == "summary"
    assert build_config(environ={**env, "AETHER_CORE_CHECKPOINT_POLICY": "window"}).clm.checkpoint_policy == "window"
    with pytest.raises(ValueError):
        build_config(environ={**env, "AETHER_CORE_CONTEXT": "project", "AETHER_CORE_CHECKPOINT_POLICY": "window"})
    with pytest.raises(ConfigError):
        build_config(environ={**env, "AETHER_CORE_CHECKPOINT_POLICY": "unrecognized"})


def test_window_and_current_file_rehydration_work_together(tmp_path):
    result, events, client, work, expected = execute(tmp_path, "window", rehydrate=True)
    assert result.status == "finished" and score(work, expected) == 1
    assert any(event["event"] == "rehydrate" and event["cause"] == "window_cut" and event.get("shown") == 1
               for event in events)
    assert any("[after the context was shortened: files this run changed, read again now]" in str(message.get("content"))
               and "label=South" in str(message.get("content"))
               for request in client.requests for message in request["messages"])


def test_window_preserves_complete_responses_tool_exchanges(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    (work / "source.txt").write_text("label=North-α\n")
    (work / "other.txt").write_text("independent\n")
    first = turn_events(0, call=("read_file", {"path": "source.txt"}, "old"))
    first.insert(-1, ev("response.output_item.done", item=item(
        type="function_call", call_id="other", name="read_file", arguments='{"path":"other.txt"}')))
    script = [first, turn_events(1, call=("write_file", {"path": "source.txt", "content": "label=South\n"}, "change"))]
    script += [turn_events(i + 2, call=("terminal", {"input": "printf '%s' '" + str(i) + "x" * 6000 + "'"}, f"n{i}"))
               for i in range(12)]
    script += [turn_events(20, call=("read_history", {"message_id": 1}, "recall")),
               turn_events(22, call=("finish", {"summary": "done"}, "finish"))]

    class RespondingClient(ResponsesClient):
        async def _create(self, **packet):
            if not getattr(self, "delivered", False):
                recall = next((x for x in packet["input"]
                               if x.get("type") == "function_call_output" and x.get("call_id") == "recall"), None)
                if recall:
                    original, _ = json.JSONDecoder().raw_decode(recall["output"].split("\n", 1)[1])
                    label = next(line.split("label=", 1)[1] for line in original["content"].splitlines()
                                 if "label=" in line)
                    self.script.insert(0, turn_events(21, call=("write_file", {"path": "report.txt", "content": label}, "deliver")))
                    self.delivered = True
            return await super()._create(**packet)

    client = RespondingClient(script)
    trace = tmp_path / "trace"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Record the original label after changing source.txt.", workdir=str(work),
        provider=ResponsesProvider(client, model="offline-script", params={}), timeout_s=120, trace=Trace(trace),
        config=CoreConfig(context="clm", control_dir=str(ctl),
                          clm=ClmSettings(budget_tokens=9000, reserve_tokens=500, checkpoint_policy="window",
                                          mirror_path=str(ctl / "live"), history_path=str(ctl / "history"))),
    ))
    assert result.status == "finished" and score(work, "North-α") == 1
    assert len([row for row in map(json.loads, trace.read_text().splitlines())
                if row["event"] == "context_window_cut" and row["ok"]]) >= 2
    for request in client.requests:
        calls = [x["call_id"] for x in request["input"] if x.get("type") == "function_call"]
        outputs = [x["call_id"] for x in request["input"] if x.get("type") == "function_call_output"]
        assert calls == outputs
    assert all("tools" in request for request in client.requests)


def test_oversize_latest_turn_fails_without_repeating_its_effect(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    command = "printf 'once\\n' >> effects.txt; printf '%s' '" + "x" * 9500 + "'"
    client = EvidenceClient([call("terminal", {"input": command}, "large"),
                             call("finish", {"summary": "done"}, "finish")])
    trace = tmp_path / "trace"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Run the supplied command once.", workdir=str(work),
        provider=ChatProvider(client, model="offline-script", params={}), timeout_s=60, trace=Trace(trace),
        config=CoreConfig(context="clm", control_dir=str(ctl),
                          clm=ClmSettings(budget_tokens=4000, reserve_tokens=500, checkpoint_policy="window",
                                          mirror_path=str(ctl / "live"), history_path=str(ctl / "history"))),
    ))
    assert result.status == "context_error"
    assert (work / "effects.txt").read_text() == "once\n"
    assert len(client.requests) == 1
    assert any(row["event"] == "context_window_cut" and not row["ok"]
               for row in map(json.loads, trace.read_text().splitlines()))


@pytest.mark.parametrize("policy", ["summary", "window"])
def test_short_task_does_not_checkpoint_or_change_effect(tmp_path, policy):
    work, ctl = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    client = EvidenceClient([call("write_file", {"path": "report.txt", "content": "ok"}, "write"),
                             call("finish", {"summary": "done"}, "finish")])
    trace = tmp_path / "trace"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Write ok to report.txt.", workdir=str(work),
        provider=ChatProvider(client, model="offline-script", params={}), timeout_s=60, trace=Trace(trace),
        config=CoreConfig(context="clm", control_dir=str(ctl),
                          clm=ClmSettings(checkpoint_policy=policy, mirror_path=str(ctl / "live"),
                                          history_path=str(ctl / "history"))),
    ))
    assert result.status == "finished" and (work / "report.txt").read_text() == "ok"
    assert len(client.requests) == 2 and all("tools" in request for request in client.requests)
    assert not any(row["event"] in ("context_window_cut", "context_checkpoint")
                   for row in map(json.loads, trace.read_text().splitlines()))

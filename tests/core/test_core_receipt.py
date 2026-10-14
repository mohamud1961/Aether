"""Finish receipt: the first finish shows the delivered files' bytes; the next finish ends the work."""

import asyncio
import json

from aether.core import harbor_agent as adapter
from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core.core_fakes import LocalEnv, ScriptedClient, chunk, tool_chunk


def _turn(name, args, call_id):
    return [
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(usage={"prompt_tokens": 5, "completion_tokens": 2}),
    ]


def _run(tmp_path, script, receipt, timeout_s=300):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    (work / "old.txt").write_text("present before the run\n")
    client = ScriptedClient(script)
    provider = ChatProvider(
        client, model="scripted", params={}, log=CallLog(tmp_path / "calls")
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=timeout_s,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), receipt=receipt),
        )
    )
    rows = [json.loads(x) for x in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return result, client, rows


def test_first_finish_shows_changed_files_and_the_second_ends_the_work(tmp_path):
    script = [
        _turn("write_file", {"path": "out.csv", "content": "to,from\nM,R\n"}, "c1"),
        _turn("finish", {"summary": "R->M written"}, "c2"),
        _turn("finish", {"summary": "checked"}, "c3"),
    ]
    result, client, rows = _run(tmp_path, script, receipt=True)
    assert result.status == "finished" and len(client.requests) == 3
    shown = client.requests[2]["messages"][-1]["content"]
    assert (
        shown.startswith("[finish receipt]")
        and "=== ./out.csv" in shown
        and "to,from\nM,R" in shown
    )
    assert "old.txt" not in shown  # unchanged files are not listed
    assert [r["event"] for r in rows].count("finish_receipt") == 1


def test_receipt_off_is_the_unchanged_baseline(tmp_path):
    script = [_turn("finish", {"summary": "done"}, "c1")]
    result, client, rows = _run(tmp_path, script, receipt=False)
    assert result.status == "finished" and len(client.requests) == 1
    assert not any(r["event"] == "finish_receipt" for r in rows)


def test_no_receipt_when_little_time_is_left(tmp_path):
    script = [_turn("finish", {"summary": "done"}, "c1")]
    result, client, _ = _run(
        tmp_path, script, receipt=True, timeout_s=70
    )  # 70 s - 15 s margin < 60 s
    assert result.status == "finished" and len(client.requests) == 1


def test_finish_mode_env_defaults_to_direct_and_rejects_unknown(monkeypatch):
    import pytest

    for name, value in (
        (adapter.REVIEW_ENV, "off"),
        (adapter.CONTEXT_ENV, "project"),
        (adapter.REPL_ENV, "off"),
        (adapter.IMAGES_ENV, "off"),
    ):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(adapter.FINISH_ENV, raising=False)
    assert adapter.build_config().receipt is False
    monkeypatch.setenv(adapter.FINISH_ENV, "receipt")
    assert adapter.build_config().receipt is True
    monkeypatch.setenv(adapter.FINISH_ENV, "veto")
    with pytest.raises(adapter.ConfigError):
        adapter.build_config()

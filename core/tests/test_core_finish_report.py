"""Finish report: harness-observed facts beside the model's account, never shown to the model."""

import asyncio
import json

from aether.core import finish_report
from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, chunk, tool_chunk


def _turn(name, args, call_id):
    return [
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(usage={"prompt_tokens": 5, "completion_tokens": 2}),
    ]


def _run(tmp_path, script):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    (work / "old.txt").write_text("present before the run\n")
    client = ScriptedClient(script)
    provider = ChatProvider(client, model="scripted", params={}, log=CallLog(tmp_path / "calls"))
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=300,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl")),
        )
    )
    return result, client, work


def test_report_lists_delivered_files_and_which_later_steps_named_them(tmp_path):
    script = [
        _turn("write_file", {"path": "a.csv", "content": "to,from\nM,R\n"}, "c1"),
        _turn("write_file", {"path": "b.txt", "content": "flag\n"}, "c2"),
        _turn("read_file", {"path": "a.csv"}, "c3"),
        _turn("finish", {"summary": "All 17 documents verified: 10 invoices, 10 other."}, "c4"),
    ]
    result, client, work = _run(tmp_path, script)
    report = result.extras["finish_report"]
    files = {f["path"]: f for f in report["delivered_files"]}
    a, b = files[str(work / "a.csv")], files[str(work / "b.txt")]
    assert str(work / "old.txt") not in files  # unchanged before-run file is not delivered work
    assert a["last_file_tool_write"] == 1 and a["steps_naming_it_after"] == [3]
    assert b["last_file_tool_write"] == 2 and b["steps_naming_it_after"] == []  # a claim with nothing behind it
    assert a["bytes"] == len("to,from\nM,R\n") and len(a["sha256"]) == 64
    assert report["model_account"] == "All 17 documents verified: 10 invoices, 10 other."
    text = finish_report.render(report)
    assert text.index("## Observed by the harness") < text.index("## The model's account")
    assert "not named by any later step" in text and "named by later steps 3" in text
    # end to end through the loop: the total 17 is in no output; the verification claim names no file
    claimed = report["unbacked_claims"]
    assert "17" in claimed["numbers_not_found_verbatim"]
    assert claimed["verification_unscoped"] == ["All 17 documents verified: 10 invoices, 10 other."]
    assert "## Claims in the model's account with no supporting observation identified" in text
    assert text.index("## Claims in the model's account") < text.index("## The model's account")
    assert "does not mean the claim is false" in text
    # the delivered account is the report: the model's summary appears only inside it, under its own heading
    assert result.final_account == text
    assert result.final_account.index("## Observed by the harness") < result.final_account.index(
        "All 17 documents verified"
    )


def test_the_model_never_sees_the_report(tmp_path):
    script = [
        _turn("write_file", {"path": "a.txt", "content": "x\n"}, "c1"),
        _turn("finish", {"summary": "done"}, "c2"),
    ]
    result, client, _ = _run(tmp_path, script)
    assert "finish_report" in result.extras and len(client.requests) == 2
    assert "Finish report" not in json.dumps(client.requests)


def test_terminal_exit_codes_are_read_from_the_terminal_status_line():
    out = "boom\n[exit 2 · 0.1s · terminal main · cwd /app]"
    rec = finish_report.record(5, "terminal", {"input": "python3 run.py"}, out, "/app")
    assert rec.exit == 2 and rec.text == "python3 run.py" and not rec.wrote
    still = finish_report.record(6, "terminal", {"input": "sleep 99"}, "[still running after 30s · terminal main]", "/app")
    assert still.exit is None
    wrote = finish_report.record(7, "write_file", {"path": "x/y.txt"}, "wrote 3 bytes", "/app")
    assert wrote.wrote == "/app/x/y.txt" and wrote.exit is None


def test_a_listing_failure_is_reported_not_raised():
    report = {
        "status": "finished", "delivered_files": "the changed files could not be listed: no marker",
        "commands": 0, "commands_nonzero_exit": [], "commands_without_exit": [],
        "left_running": [], "model_account": None,
    }
    text = finish_report.render(report)
    assert "delivered files: unknown (the changed files could not be listed" in text
    assert "[no finish summary: the run did not finish]" in text


def test_over_the_listing_cap_the_count_is_true_and_file_tool_writes_are_listed_first(tmp_path):
    # R5.base.build-cython-ext e1: 200+ build artefacts; the report said "200 changed" (the cap) and the two sources
    # the model edited, which sorted after the artefacts, were not listed.
    script = [
        _turn("terminal", {"input": "mkdir -p build && for i in $(seq 1 205); do echo $i > build/f$i; done"}, "c1"),
        _turn("write_file", {"path": "zz_source.py", "content": "print(1)\n"}, "c2"),
        _turn("finish", {"summary": "done"}, "c3"),
    ]
    result, client, work = _run(tmp_path, script)
    report = result.extras["finish_report"]
    listed = [f["path"] for f in report["delivered_files"]]
    assert len(listed) == finish_report.MAX_FILES
    assert listed[0] == str(work / "zz_source.py")  # what a file tool wrote comes before unattributed files
    assert report["delivered_files_total"] == 206
    text = finish_report.render(report)
    assert f"206 changed under {work} since the run started; {finish_report.MAX_FILES} listed" in text

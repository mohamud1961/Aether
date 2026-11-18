"""H10: the append-only session log is the run's recovery object. A controller killed mid-run is replaced by a new
process that resumes from the log and loses or duplicates nothing; without the log there is nothing to resume."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

from aether.core import session_log

CHILD = textwrap.dedent("""
    import asyncio, json, os, sys
    from pathlib import Path
    from aether.core import session_log
    from aether.core.calls import CallLog
    from aether.core.clm import ClmSettings
    from aether.core.loop import CoreConfig, Trace, run_agent
    from aether.core.provider import ChatProvider
    from tests.core_fakes import LocalEnv, ScriptedClient, call

    box, logs, mode, context, die_at = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], int(sys.argv[5])
    ctl, work = box / "ctl", box / "work"
    (box / "controller.pid").write_text(str(os.getpid()))
    effects = work / "effects.txt"
    if mode == "first":
        script = [call("terminal", {"input": f"echo a >> {effects}"}, "t1"),
                  call("terminal", {"input": f"echo b >> {effects}"}, "t2"),
                  call("terminal", {"input": f"echo c >> {effects}; kill -9 $(cat {box}/controller.pid)"}, "t3"),
                  call("finish", {"summary": "unreachable"}, "t4")]
    else:
        script = [call("finish", {"summary": "resumed"}, "r1")]

    class Client(ScriptedClient):
        async def _create(self, **kwargs):
            if len(self.requests) + 1 == die_at:
                os._exit(9)  # the controller dies at its next provider call
            return await super()._create(**kwargs)

    client = Client(script)
    resume = None
    if mode == "resume":
        resume, account = session_log.recover(Path(sys.argv[6]))
        (logs / "recovery.json").write_text(json.dumps(account))
    config = CoreConfig(control_dir=str(ctl), context=context, session_log=True,
                        clm=ClmSettings(mirror_path=f"{ctl}/ctx/LIVE_CTX.txt", history_path=f"{ctl}/ctx/HISTORY.txt"))
    result = asyncio.run(run_agent(env=LocalEnv(box), task="append three lines", workdir=str(work),
                                   provider=ChatProvider(client, model="scripted", params={},
                                                         log=CallLog(logs / "calls.jsonl")),
                                   timeout_s=120, trace=Trace(logs / "core_trace.jsonl"), config=config,
                                   resume=resume))
    (logs / "requests.json").write_text(json.dumps(client.requests, default=str))
    print(result.status)
""")


def _box(tmp_path):
    box = tmp_path / "box"
    (box / "work").mkdir(parents=True)
    (box / "ctl").mkdir()
    return box


def _child(box, logs, mode, context, die_at, session=""):
    logs.mkdir(parents=True, exist_ok=True)
    return subprocess.run([sys.executable, "-c", CHILD, str(box), str(logs), mode, context, str(die_at), session],
                          capture_output=True, text=True, timeout=180, env=os.environ.copy())


def _tool_texts(logs):
    requests = json.loads((logs / "requests.json").read_text())
    return {m.get("tool_call_id"): str(m.get("content")) for m in requests[0]["messages"] if m.get("role") == "tool"}


@pytest.mark.parametrize("context", ["project", "clm"])
def test_a_controller_killed_between_turns_resumes_with_nothing_lost_or_repeated(tmp_path, context):
    box = _box(tmp_path)
    first = _child(box, tmp_path / "logs1", "first", context, die_at=3)  # dies asking for turn 3
    assert first.returncode != 0, first.stdout + first.stderr
    rows = [json.loads(x) for x in (tmp_path / "logs1" / "session" / "log.jsonl").read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["asked", "done", "asked", "done"]
    second = _child(box, tmp_path / "logs2", "resume", context, die_at=0, session=str(tmp_path / "logs1" / "session"))
    assert second.stdout.strip().endswith("finished"), second.stdout + second.stderr
    assert (box / "work" / "effects.txt").read_text() == "a\nb\n"  # each effect once, none repeated
    texts = _tool_texts(tmp_path / "logs2")
    assert set(texts) >= {"t1", "t2"} and not any(session_log.UNKNOWN in t for t in texts.values())
    account = json.loads((tmp_path / "logs2" / "recovery.json").read_text())
    assert account["kind"] == "done" and account["unanswered"] == []


@pytest.mark.parametrize("context", ["project", "clm"])
def test_a_controller_killed_inside_a_call_is_resumed_with_that_call_unknown_and_not_rerun(tmp_path, context):
    box = _box(tmp_path)
    first = _child(box, tmp_path / "logs1", "first", context, die_at=99)  # t3's own command kills the controller
    assert first.returncode != 0, first.stdout + first.stderr
    second = _child(box, tmp_path / "logs2", "resume", context, die_at=0, session=str(tmp_path / "logs1" / "session"))
    assert second.stdout.strip().endswith("finished"), second.stdout + second.stderr
    assert (box / "work" / "effects.txt").read_text() == "a\nb\nc\n"  # c ran once, before the kill; not again
    texts = _tool_texts(tmp_path / "logs2")
    assert session_log.UNKNOWN in texts["t3"] and session_log.UNKNOWN not in texts["t2"]
    account = json.loads((tmp_path / "logs2" / "recovery.json").read_text())
    assert account["kind"] == "asked" and account["unanswered"] == ["t3"]


def test_known_bad_without_the_log_there_is_nothing_to_resume(tmp_path):
    box = _box(tmp_path)
    second = _child(box, tmp_path / "logs2", "resume", "project", die_at=0, session=str(tmp_path / "no-session"))
    assert second.returncode != 0 and "SessionLogError" in second.stderr


def _write(tmp_path, n):
    log = session_log.SessionLog(tmp_path / "s")
    for i in range(n):
        log.write("done", i, {"context": [{"role": "user", "content": f"m{i}"}], "steps": i, "calls": i})
    return tmp_path / "s"


def test_a_torn_last_line_falls_back_to_the_previous_record(tmp_path):
    root = _write(tmp_path, 2)
    with open(root / session_log.LOG, "a") as fh:
        fh.write('{"seq": 2, "kind": "do')
    row, state, rejected = session_log.latest(root)
    assert row["seq"] == 1 and state["context"][0]["content"] == "m1" and rejected


def test_known_bad_a_snapshot_that_changed_after_logging_is_not_trusted(tmp_path):
    root = _write(tmp_path, 2)
    newest = root / json.loads((root / session_log.LOG).read_text().splitlines()[-1])["file"]
    newest.write_bytes(newest.read_bytes() + b"x")
    row, _, rejected = session_log.latest(root)
    assert row["seq"] == 0 and any("hash differs" in r for r in rejected)


def test_known_bad_a_snapshot_name_outside_the_log_directory_is_never_loaded(tmp_path):
    root = _write(tmp_path, 1)
    elsewhere = tmp_path / "evil.pkl"
    elsewhere.write_bytes(b"not loaded")
    import hashlib
    row = {"seq": 1, "kind": "done", "turn": 1, "file": "../evil.pkl",
           "sha256": hashlib.sha256(b"not loaded").hexdigest(), "bytes": 10}
    with open(root / session_log.LOG, "a") as fh:
        fh.write(json.dumps(row) + "\n")
    row, _, rejected = session_log.latest(root)
    assert row["seq"] == 0 and any("name not allowed" in r for r in rejected)


def test_known_bad_a_directory_others_can_write_is_refused(tmp_path):
    root = _write(tmp_path, 1)
    root.chmod(0o777)
    with pytest.raises(session_log.SessionLogError, match="writable by group or others"):
        session_log.latest(root)
    root.chmod(0o700)
    (root / "000000-done.pkl").chmod(0o666)
    with pytest.raises(session_log.SessionLogError, match="seq 0: .* writable by group or others"):
        session_log.latest(root)


def test_the_switch_maps_to_the_config():
    from aether.core.harbor_agent import build_config
    base = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off",
            "AETHER_CORE_IMAGES": "off"}
    assert build_config(environ=base).session_log is False
    assert build_config(environ={**base, "AETHER_CORE_SESSION_LOG": "on"}).session_log is True

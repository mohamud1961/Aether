"""D18: ``keep_cut_outputs`` copies the hidden middle of every cut terminal result next to the trace at run end.

Checks through the real loop and terminal: the marker printed in the middle of a long output is absent from what the
model was shown, present in the kept file, and the kept file is byte-exact. Known-bads: with the switch off nothing is
kept; a span whose log vanished is recorded with its error instead of being dropped; the per-run cap truncates and says so.
"""

import asyncio
import json

from aether.core import cut_outputs
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

LONG = "python3 -c \"print('a' * 6000); print('HIDDEN-MIDDLE-MARK'); print('z' * 12000)\""


def run(tmp_path, **overrides):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([call("terminal", {"input": LONG}, "c0"), call("finish", {"summary": "done."}, "done")])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Print it.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=60, config=CoreConfig(control_dir=str(tmp_path / "control"), **overrides)))
    shown = next(m["content"] for m in client.requests[-1]["messages"] if m.get("tool_call_id") == "c0")
    return result, shown


def test_cut_middle_is_kept_byte_exact_and_never_shown(tmp_path):
    result, shown = run(tmp_path, keep_cut_outputs=True)
    assert "bytes omitted" in shown and "HIDDEN-MIDDLE-MARK" not in shown
    index = json.loads((tmp_path / "cut_outputs" / "index.json").read_text())
    (span,) = index["spans"]
    kept = (tmp_path / "cut_outputs" / span["file"]).read_bytes()
    assert b"HIDDEN-MIDDLE-MARK" in kept and len(kept) == span["bytes"] and not span["truncated"]
    assert kept.count(b"a") >= 6000 and kept.count(b"z") >= 12000
    assert result.extras["cut_outputs"]["kept_bytes"] == len(kept)
    assert not any("cut outputs" in e for e in result.extras["cleanup_errors"])


def test_known_bad_switch_off_keeps_nothing(tmp_path):
    result, shown = run(tmp_path)
    assert "bytes omitted" in shown
    assert not (tmp_path / "cut_outputs").exists() and "cut_outputs" not in result.extras


def test_missing_log_is_recorded_and_cap_truncates(tmp_path, monkeypatch):
    log = tmp_path / "log"
    log.write_bytes(b"0123456789" * 10)
    monkeypatch.setattr(cut_outputs, "TOTAL_CAP", 25)
    index = asyncio.run(cut_outputs.keep(LocalEnv(tmp_path), tmp_path / "out",
                                         [(str(tmp_path / "gone"), 0, 10), (str(log), 5, 45), (str(log), 0, 10)]))
    gone, cut, starved = index["spans"]
    assert "error" in gone and gone["kept"] == 0
    assert cut["kept"] == 25 and cut["truncated"] and (tmp_path / "out" / cut["file"]).read_bytes() == (b"0123456789" * 10)[5:30]
    assert starved["kept"] == 0 and starved["truncated"]

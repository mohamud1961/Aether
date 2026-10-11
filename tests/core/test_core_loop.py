"""Aether Core loop and the reviewer finish review, with a scripted model and a real local shell."""
from __future__ import annotations

import asyncio
import json

from aether.core import loop as core_loop
from aether.core.loop import Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.review import answers_of, build_request, judge
from tests.core.core_fakes import LocalEnv, ScriptedClient, StatusError, call

TASK = "Create /app/out.txt containing hello. The file must end with a newline."


def _answers(mode: str, conf: float, crit: str = "direct_and_current") -> dict:
    return {"result": {"answers": {"failure_mode": {"choice": mode, "confidence": conf},
                                   "completeness:C1": {"choice": crit, "confidence": 0.9}}}}


def _run(tmp_path, script, *, transport=None, timeout_s=600.0):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    provider = ChatProvider(ScriptedClient(script), model="glm", params={})
    calls = []

    async def review_call(t, request):
        calls.append(request)
        return t(request)
    result = asyncio.run(run_agent(env=LocalEnv(work), task=TASK, workdir=str(work), provider=provider,
                                   timeout_s=timeout_s, trace=Trace(tmp_path / "trace.jsonl"),
                                   review_transport=transport, review_call=review_call if transport else None))
    rows = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return result, rows, calls, provider


def test_tools_run_and_finish_without_review(tmp_path):
    script = [call("terminal", {"input": "echo hi > note.txt; cat note.txt"}, "c1"),
              call("write_file", {"path": "out.txt", "content": "hello\n"}, "c2"),
              call("finish", {"summary": "done"}, "c3")]
    result, rows, _, _ = _run(tmp_path, script)
    assert result.status == "finished" and result.steps == 3 and result.calls == 3
    assert (tmp_path / "work/out.txt").read_text() == "hello\n"
    tool_rows = [r for r in rows if r["event"] == "tool"]
    assert "hi" in tool_rows[0]["result"] and "[exit 0" in tool_rows[0]["result"]
    assert [r for r in rows if r["event"] == "finish"][0]["reason"] == "review_off"
    assert rows[-1]["event"] == "end" and result.usage["input"] == 3000


def test_review_hold_feeds_back_then_pass_finishes(tmp_path):
    verdicts = iter([_answers("incomplete", 0.9, "none"), _answers("fully_done", 0.95)])
    script = [call("finish", {"summary": "SOLVER-CLAIM-MARKER"}, "c1"),
              call("write_file", {"path": "out.txt", "content": "hello\n"}, "c2"),
              call("finish", {"summary": "SOLVER-CLAIM-MARKER"}, "c3")]
    result, rows, requests, provider = _run(tmp_path, script, transport=lambda req: next(verdicts))
    assert result.status == "finished" and [r["status"] for r in result.reviews] == ["hold", "pass"]
    held = [r for r in rows if r["event"] == "tool" and r["name"] == "finish"][0]["result"]
    assert "[independent review]" in held and "C1" in held
    # the reviewer never sees the solver's summary or claims
    assert all("SOLVER-CLAIM-MARKER" not in json.dumps(r) for r in requests)
    assert requests[0]["state"]["claim_card"] is None and "hello" in json.dumps(requests[1])


def test_review_error_is_recorded_not_silent(tmp_path):
    def broken(_req):
        raise RuntimeError("reviewer down")
    result, rows, _, _ = _run(tmp_path, [call("finish", {"summary": "x"})], transport=broken)
    assert result.status == "finished" and result.reviews[0]["status"] == "error"
    assert "reviewer down" in result.reviews[0]["reason"]
    assert [r for r in rows if r["event"] == "review"][0]["status"] == "error"


def test_review_skipped_when_little_time_remains(tmp_path, monkeypatch):
    monkeypatch.setattr(core_loop, "REVIEW_MIN_REMAINING_S", 10_000)
    result, rows, requests, _ = _run(tmp_path, [call("finish", {"summary": "x"})], transport=lambda r: {})
    assert result.reviews == [] and not requests
    assert [r for r in rows if r["event"] == "finish"][0]["reason"] == "low_time"


def test_review_hold_limit_lets_the_solver_finish(tmp_path):
    script = [call("finish", {"summary": "x"}, f"c{i}") for i in range(3)]
    result, _, _, _ = _run(tmp_path, script, transport=lambda r: _answers("wrong_output", 0.99))
    assert result.status == "finished" and [r["status"] for r in result.reviews] == ["hold", "hold"]


def test_tool_errors_are_returned_to_the_model(tmp_path):
    script = [call("edit_file", {"path": "missing.txt", "old_str": "a", "new_str": "b"}, "c1"),
              call("bogus", {}, "c2"), call("finish", {"summary": "x"}, "c3")]
    result, rows, _, _ = _run(tmp_path, script)
    results = [r["result"] for r in rows if r["event"] == "tool"]
    assert results[0].startswith("error: FileNotFoundError") and "unknown tool" in results[1]
    assert result.status == "finished"


def test_provider_failure_ends_the_run_honestly(tmp_path):
    result, rows, _, _ = _run(tmp_path, [StatusError(401, "unauthorized")])
    assert result.status == "provider_error" and "unauthorized" in result.error
    assert rows[-1]["status"] == "provider_error"


def test_review_request_fits_budget_and_judge_thresholds():
    actions = [f"[terminal main] $ make\n-> {'x' * 5000}" for _ in range(12)]
    request, criteria = build_request(TASK + " " + "Also do more. " * 50, actions, "state " * 3000)
    assert len(json.dumps(request, separators=(",", ":")).encode()) <= 15_000
    assert "failure_mode" in request["questions"] and criteria
    low = judge(answers_of(_answers("incomplete", 0.5)), criteria, 1)
    high = judge(answers_of(_answers("incomplete", 0.85, "contradicted")), criteria, 1)
    assert low.status == "pass" and high.status == "hold" and high.unmet

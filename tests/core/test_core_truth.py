"""Unknown is never reported as success or zero: exit codes, usage, attempts, reviewer answers, and the
exact record of every model request."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from aether.core import calls as call_log
from aether.core.env import put_bytes, run
from aether.core.loop import Trace, run_agent
from aether.core.provider import ChatProvider, ProviderError
from aether.core.review import answers_of, judge
from tests.core.core_fakes import LocalEnv, ScriptedClient, StatusError, call, chunk, tool_chunk

CRITERIA = [{"criterion_id": "C1", "text": "out.txt holds hello"}, {"criterion_id": "C2", "text": "ends in newline"}]


class NoStatusEnv:
    """An environment that returns output but no exit status."""

    async def exec(self, **kwargs):
        return SimpleNamespace(stdout="partial", stderr="")


def test_a_missing_exit_status_is_unknown_and_never_success():
    res = asyncio.run(run(NoStatusEnv(), "true"))
    assert res.code is None and res.stdout == "partial"
    with pytest.raises(OSError):  # a write whose outcome is unknown is not reported as done
        asyncio.run(put_bytes(NoStatusEnv(), b"x", "/tmp/never"))


def test_every_request_is_rebuilt_exactly_from_the_call_log(tmp_path):
    work = tmp_path / "work"; work.mkdir()
    client = ScriptedClient([StatusError(503), call("terminal", {"input": "echo hi"}, "c1"),
                             call("write_file", {"path": "out.txt", "content": "hello\n"}, "c2"),
                             call("finish", {"summary": "done"}, "c3")])
    provider = ChatProvider(client, model="glm", params={"temperature": 1.0}, sleep=lambda s: asyncio.sleep(0),
                            log=call_log.CallLog(tmp_path / "calls.jsonl"))
    asyncio.run(run_agent(env=LocalEnv(work), task="Write hello to out.txt.", workdir=str(work), provider=provider,
                          timeout_s=600.0, trace=Trace(tmp_path / "trace.jsonl")))
    rebuilt = list(call_log.requests(tmp_path / "calls.jsonl"))
    assert [r["request"] for r in rebuilt] == client.requests  # byte-exact, including the failed attempt
    assert [r["ok"] for r in rebuilt] == [False, True, True, True]
    assert rebuilt[0]["status"] == 503 and rebuilt[0]["usage_missing"] == list(call_log.USAGE_FIELDS)
    totals = provider.log.totals()["worker"]
    assert totals["attempts"] == 4 and totals["failed"] == 1 and totals["usage_unknown"] == 1
    assert totals["input"] == 3000  # three answered calls of 1000 input tokens each
    # the shared prefix is stored once, not once per request
    blobs = sum(1 for line in (tmp_path / "calls.jsonl").read_text().splitlines() if '"kind":"blob"' in line)
    assert blobs < sum(len(r["request"]["messages"]) for r in rebuilt)


def test_usage_fields_the_provider_omits_are_unknown_not_zero(tmp_path):
    turn = [tool_chunk("finish", {"summary": "x"}), chunk(finish="tool_calls"),
            chunk(usage={"prompt_tokens": 10, "completion_tokens": 5})]
    provider = ChatProvider(ScriptedClient([turn]), model="glm", params={})
    out = asyncio.run(provider.complete([{"role": "user", "content": "hi"}], [], max_tokens=10,
                                        remaining_s=lambda: 60.0))
    assert out.usage == {"input": 10, "output": 5}
    assert provider.log.totals()["worker"]["usage_unknown"] == 1


def test_a_non_retryable_failure_is_counted(tmp_path):
    provider = ChatProvider(ScriptedClient([StatusError(401)]), model="glm", params={})
    with pytest.raises(ProviderError):
        asyncio.run(provider.complete([{"role": "user", "content": "hi"}], [], max_tokens=10,
                                      remaining_s=lambda: 60.0, role="llm"))
    assert provider.failed_attempts == 1 and provider.log.totals()["llm"]["failed"] == 1


def test_retry_after_is_honoured_beyond_a_minute_when_time_allows():
    waits = []

    async def sleep(s):
        waits.append(s)
    client = ScriptedClient([StatusError(429, headers={"retry-after": "180"}), call("finish", {"summary": "x"})])
    provider = ChatProvider(client, model="glm", params={}, sleep=sleep)
    asyncio.run(provider.complete([{"role": "user", "content": "hi"}], [], max_tokens=10,
                                  remaining_s=lambda: 600.0))
    assert waits == [180.0]
    provider = ChatProvider(ScriptedClient([StatusError(429, headers={"retry-after": "180"})]), model="glm",
                            params={}, sleep=sleep)
    with pytest.raises(ProviderError) as err:  # a wait longer than the time left ends the call honestly
        asyncio.run(provider.complete([{"role": "user", "content": "hi"}], [], max_tokens=10,
                                      remaining_s=lambda: 100.0))
    assert err.value.deadline


def test_no_call_is_made_without_time_left():
    client = ScriptedClient([call("finish", {"summary": "x"})])
    provider = ChatProvider(client, model="glm", params={})
    with pytest.raises(ProviderError) as err:
        asyncio.run(provider.complete([{"role": "user", "content": "hi"}], [], max_tokens=10,
                                      remaining_s=lambda: 0.0))
    assert err.value.deadline and client.requests == []


def _response(answers: dict) -> dict:
    return {"result": {"answers": answers}}


@pytest.mark.parametrize("bad", [
    {"failure_mode": {"choice": "anything_unrecognized", "confidence": 0.9}},
    {"failure_mode": {"choice": "fully_done", "confidence": 2.0}},
    {"failure_mode": {"choice": "fully_done"}},
    {"failure_mode": {"choice": "fully_done", "confidence": 0.9},
     "completeness:C1": {"choice": "probably", "confidence": 0.9}},
])
def test_a_malformed_review_answer_is_an_error_not_a_pass(bad):
    with pytest.raises(ValueError):
        answers_of(_response(bad))


def test_an_unanswered_criterion_is_unconfirmed_and_a_pass_with_gaps_is_not_verified():
    answers = answers_of(_response({"failure_mode": {"choice": "fully_done", "confidence": 0.95},
                                    "completeness:C1": {"choice": "contradicted", "confidence": 0.9}}))
    v = judge(answers, CRITERIA, 100)
    assert v.status == "pass"  # only the failure-mode reading holds a finish
    assert len(v.unmet) == 2 and "C2 (the reviewer gave no answer)" in v.unmet[1]

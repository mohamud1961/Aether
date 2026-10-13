"""Aether Core file tools, context projection and provider client."""
from __future__ import annotations

import asyncio
import json
import os

import pytest

from aether.core.context import project
from aether.core.files import Files
from aether.core.provider import ChatProvider, ProviderError, parse_arguments
from tests.core.core_fakes import LocalEnv, ScriptedClient, StatusError, call


def _files(tmp_path):
    return Files(LocalEnv(tmp_path), str(tmp_path))


def test_write_read_edit_roundtrip_keeps_permissions(tmp_path):
    f = _files(tmp_path)
    script = tmp_path / "run.sh"
    script.write_text("#!/bin/sh\necho old\n")
    os.chmod(script, 0o755)

    async def go():
        w = await f.write("run.sh", "#!/bin/sh\necho one\necho two\n")
        e = await f.edit("run.sh", "echo two", "echo TWO")
        r = await f.read("run.sh", 2, 1)
        n = await f.write("deep/dir/new.txt", "x")
        return w, e, r, n
    w, e, r, n = asyncio.run(go())
    assert "wrote" in w and os.stat(script).st_mode & 0o777 == 0o755
    assert "echo TWO" in script.read_text() and "edited" in e
    assert "     2  echo one" in r and "lines 2-2 of 3" in r and "next: start_line=3" in r
    assert (tmp_path / "deep/dir/new.txt").read_text() == "x" and "(new file)" in n


def test_edit_rejects_missing_and_ambiguous_text(tmp_path):
    f = _files(tmp_path)
    (tmp_path / "a.txt").write_text("x x\n")
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(f.edit("a.txt", "y", "z"))
    with pytest.raises(ValueError, match="occurs 2 times"):
        asyncio.run(f.edit("a.txt", "x", "z"))
    assert (tmp_path / "a.txt").read_text() == "x x\n"  # known-bad: a failed edit must not change the file
    asyncio.run(f.edit("a.txt", "x", "z", replace_all=True))
    assert (tmp_path / "a.txt").read_text() == "z z\n"


def _history(n_turns: int) -> list[dict]:
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "task"}]
    for i in range(n_turns):
        args = {"path": f"f{i}.c", "content": "B" * 5000}
        msgs.append({"role": "assistant", "content": None, "reasoning_content": f"r{i}" * 100,
                     "tool_calls": [{"id": f"c{i}", "type": "function",
                                     "function": {"name": "write_file", "arguments": json.dumps(args)}}]})
        msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": f"out{i}" + "O" * 6000})
    return msgs


def test_projection_trims_old_turns_in_blocks_and_keeps_recent_verbatim():
    msgs = _history(20)
    view = project(msgs)
    assistants = [m for m in view if m["role"] == "assistant"]
    assert len(view) == len(msgs)  # nothing dropped, only shortened
    assert all("reasoning_content" not in m for m in assistants[:12])
    assert all("reasoning_content" in m for m in assistants[-4:])  # known-bad: recent reasoning must survive
    assert "chars; the file on disk" in assistants[0]["tool_calls"][0]["function"]["arguments"]
    assert msgs[2]["reasoning_content"]  # the stored history is never mutated
    tools = [m for m in view if m["role"] == "tool"]
    assert "omitted" in tools[0]["content"] and "omitted" not in tools[-1]["content"]
    # cache stability: one more turn inside the same block leaves the trimmed prefix byte-identical
    assert project(_history(21))[:30] == view[:30]


def test_tight_projection_keeps_only_two_recent_turns():
    view = project(_history(6), tight=True)
    assistants = [m for m in view if m["role"] == "assistant"]
    assert sum("reasoning_content" in m for m in assistants) == 2


def test_provider_assembles_streamed_tool_call_and_usage():
    client = ScriptedClient([call("terminal", {"input": "ls"})])
    p = ChatProvider(client, model="m", params={"temperature": 1.0})
    turn = asyncio.run(p.complete([], [], max_tokens=10, remaining_s=lambda: 100))
    assert turn.tool_calls[0]["function"]["name"] == "terminal"
    assert json.loads(turn.tool_calls[0]["function"]["arguments"]) == {"input": "ls"}
    assert turn.reasoning == "thinking" and turn.usage == {"input": 1000, "cached": 200, "output": 50, "reasoning": 20}
    assert client.requests[0]["stream"] is True and client.requests[0]["temperature"] == 1.0


def test_provider_retries_429_with_retry_after_then_succeeds():
    waits = []

    async def sleep(s):
        waits.append(s)
    client = ScriptedClient([StatusError(429, headers={"retry-after": "3"}), StatusError(503),
                             call("finish", {"summary": "x"})])
    p = ChatProvider(client, model="m", params={}, sleep=sleep)
    turn = asyncio.run(p.complete([], [], max_tokens=10, remaining_s=lambda: 500))
    assert turn.attempts == 3 and waits[0] == 3.0 and p.failed_attempts == 2


def test_provider_does_not_retry_bad_request_and_flags_context_overflow():
    p = ChatProvider(ScriptedClient([StatusError(400, "maximum context length exceeded")]), model="m", params={})
    with pytest.raises(ProviderError) as info:
        asyncio.run(p.complete([], [], max_tokens=10, remaining_s=lambda: 500))
    assert info.value.context_overflow
    p = ChatProvider(ScriptedClient([StatusError(401, "bad key")]), model="m", params={})
    with pytest.raises(ProviderError) as info:
        asyncio.run(p.complete([], [], max_tokens=10, remaining_s=lambda: 500))
    assert info.value.status == 401 and not info.value.context_overflow


def test_parse_arguments_unwraps_one_level_only():
    assert parse_arguments('{"input": "ls"}') == {"input": "ls"}
    assert parse_arguments(json.dumps(json.dumps({"input": "ls"}))) == {"input": "ls"}
    assert parse_arguments(json.dumps({"arguments": {"path": "a"}})) == {"path": "a"}
    with pytest.raises(ValueError):
        parse_arguments("[1, 2]")


def test_a_long_result_is_saved_exactly_and_its_trimmed_view_points_there(tmp_path):
    import asyncio
    import json as _json
    from aether.core.context import project
    from aether.core.loop import CoreConfig, Trace, run_agent
    from aether.core.provider import ChatProvider
    from tests.core.core_fakes import LocalEnv, ScriptedClient, call
    work = tmp_path / "work"; work.mkdir()
    big = "".join(f"line {i}\n" for i in range(800))
    (work / "big.txt").write_text(big)
    script = [call("terminal", {"input": "cat big.txt"}, "c1")] + [
        call("terminal", {"input": f"echo {i}"}, f"c{i + 2}") for i in range(12)] + [call("finish", {"summary": "x"}, "f")]
    provider = ChatProvider(ScriptedClient(script), model="glm", params={})
    asyncio.run(run_agent(env=LocalEnv(work), task="t", workdir=str(work), provider=provider, timeout_s=600,
                          trace=Trace(tmp_path / "t.jsonl"), config=CoreConfig(control_dir=str(tmp_path / "ctl"))))
    saved = tmp_path / "ctl/results/1.txt"
    assert "line 0\n" in saved.read_text() and "line 799" in saved.read_text()  # what the model saw, exactly
    last = provider._client.requests[-1]["messages"]
    first_result = next(m for m in last if m.get("role") == "tool")
    assert "omitted; its full text is saved at the path below" in first_result["content"]
    assert f"saved in full at {saved}" in first_result["content"]

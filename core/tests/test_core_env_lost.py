"""A sandbox that disappears mid-run ends the run; a tool error in a live sandbox does not (P2 A3, 2026-10-22).

Daytona deleted two sandboxes mid-run and Core kept calling the model for 13 and 25 more minutes, every tool
failing with "sandbox ... not found". No provider calls: scripted model, local shell.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from aether.core import loop
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call, chunk, tool_chunk


class DeletableEnv(LocalEnv):
    def __init__(self, root) -> None:
        super().__init__(root)
        self.lost = False

    def _check(self) -> None:
        if self.lost:
            raise RuntimeError("sandbox 73a8 not found (it has been deleted)")

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        self._check()
        return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec)

    async def upload_file(self, source_path, target_path):
        self._check()
        return await super().upload_file(source_path, target_path)

    async def download_file(self, source_path, target_path):
        self._check()
        return await super().download_file(source_path, target_path)


class ProbeStatusEnv(LocalEnv):
    """A live fake environment whose health probe returns a chosen reported status."""

    def __init__(self, root, probe_code) -> None:
        super().__init__(root)
        self.probe_code = probe_code
        self.probes = 0

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        if command == "true":
            self.probes += 1
            return SimpleNamespace(return_code=self.probe_code, stdout="", stderr="")
        return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec)


def _run(tmp_path, env, client):
    return asyncio.run(
        loop.run_agent(
            env=env,
            task="task",
            workdir=str(env.root),
            provider=ChatProvider(client, model="scripted", params={}),
            timeout_s=120,
            trace=loop.Trace(tmp_path / "trace"),
            config=loop.CoreConfig(control_dir=str(tmp_path / "ctl")),
        )
    )


def test_a_deleted_sandbox_ends_the_run_instead_of_calling_the_model_on(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    env = DeletableEnv(work)
    script = [call("terminal", {"input": "echo hi"}, call_id=f"c{i}") for i in range(6)]
    script.append(call("finish", {"summary": "done"}, call_id="cf"))
    client = ScriptedClient(script)
    original = client.chat.completions.create

    async def create(**kwargs):
        if len(client.requests) == 1:  # deleted after the first turn's tools ran
            env.lost = True
        return await original(**kwargs)

    client.chat.completions.create = create
    result = _run(tmp_path, env, client)
    assert result.status == "environment_error" and "deleted" in result.error
    assert len(client.requests) == 2  # the turn whose tools failed is the last one


def test_a_tool_error_in_a_live_sandbox_keeps_the_run_going(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient(
        [
            call("read_file", {"path": str(work / "missing.txt")}, call_id="c1"),
            call("finish", {"summary": "done"}, call_id="c2"),
        ]
    )
    result = _run(tmp_path, DeletableEnv(work), client)
    assert result.status == "finished" and len(client.requests) == 2


@pytest.mark.parametrize("probe_code", [1, None])
def test_environment_probe_requires_a_reported_zero_after_a_tool_error(tmp_path, probe_code):
    work = tmp_path / "work"
    work.mkdir()
    env = ProbeStatusEnv(work, probe_code)
    client = ScriptedClient(
        [
            call("read_file", {"path": str(work / "missing.txt")}, call_id="c1"),
            call("finish", {"summary": "done"}, call_id="c2"),
        ]
    )

    result = _run(tmp_path, env, client)

    assert result.status == "environment_error"
    assert "could not be confirmed live" in result.error
    assert f"reported {probe_code}" in result.error
    assert env.probes == 2  # bounded probe and one retry, then terminate
    assert len(client.requests) == 1  # do not ask the model to continue unverified
    events = [json.loads(line)["event"] for line in (tmp_path / "trace").read_text().splitlines()]
    assert "environment_unverified" in events and "environment_lost" not in events


def test_a_finish_in_the_same_response_cannot_hide_a_lost_environment(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    env = DeletableEnv(work)
    client = ScriptedClient(
        [
            [
                chunk(reasoning="first try the terminal"),
                tool_chunk("terminal", {"input": "echo hi"}, index=0, call_id="c1"),
                tool_chunk("finish", {"summary": "done"}, index=1, call_id="c2"),
                chunk(finish="tool_calls"),
            ]
        ]
    )
    original = client.chat.completions.create

    async def create(**kwargs):
        response = await original(**kwargs)
        env.lost = True  # the sandbox disappears before this response's tools run
        return response

    client.chat.completions.create = create
    result = _run(tmp_path, env, client)

    assert result.status == "environment_error" and "deleted" in result.error
    assert len(client.requests) == 1

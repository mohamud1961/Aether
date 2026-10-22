"""A sandbox that disappears mid-run ends the run; a tool error in a live sandbox does not (P2 A3, 2026-10-22).

Daytona deleted two sandboxes mid-run and Core kept calling the model for 13 and 25 more minutes, every tool
failing with "sandbox ... not found". No provider calls: scripted model, local shell.
"""

import asyncio

from aether.core import loop
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


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

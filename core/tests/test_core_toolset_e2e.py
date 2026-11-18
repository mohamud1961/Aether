"""Exercise the minimal tool profile through Core's actual configuration and loop."""

import asyncio
from dataclasses import replace

import pytest

from aether.core.harbor_config import build_config
from aether.core.loop import Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.route_modality import check as check_route
from tests.core_fakes import LocalEnv, ScriptedClient, call


BASE = {
    "AETHER_CORE_REVIEW": "off",
    "AETHER_CORE_CONTEXT": "clm",
    "AETHER_CORE_REPL": "off",
    "AETHER_CORE_IMAGES": "off",
    "AETHER_CORE_TOOLSET": "minimal",
    "AETHER_CORE_START_COPY": "off",
    "AETHER_CORE_MANAGED_FACTS": "off",
    "AETHER_CORE_STATE_VIEW": "off",
}


def test_minimal_profile_keeps_history_recall_and_completes_shell_work(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    client = ScriptedClient([
        call("terminal", {"input": "printf 'ready\\n' > result.txt"}, "write"),
        call("finish", {"summary": "done"}, "finish"),
    ])
    config = replace(build_config(environ=BASE), control_dir=str(tmp_path / "control"))
    route = tmp_path / "route.json"
    route.write_text('{"deployment":"fixture","images":true,"evidence":"measured"}')
    check_route({"AETHER_CORE_ROUTE_MODALITY": str(route)}, deployment="fixture", images=config.images)
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Create result.txt", workdir=str(work),
        provider=ChatProvider(client, model="scripted", params={}), timeout_s=60,
        trace=Trace(tmp_path / "trace.jsonl"), config=config,
    ))
    names = [tool["function"]["name"] for tool in client.requests[0]["tools"]]
    assert names == ["terminal", "read_history", "finish"]
    assert result.status == "finished"
    assert (work / "result.txt").read_text() == "ready\n"


@pytest.mark.parametrize("setting", ["AETHER_CORE_REPL", "AETHER_CORE_IMAGES"])
def test_minimal_profile_rejects_competing_tool_switches_before_a_run(setting):
    with pytest.raises(ValueError, match="minimal toolset"):
        build_config(environ={**BASE, setting: "on"})

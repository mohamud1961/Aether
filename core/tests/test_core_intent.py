"""Intent-bound actions: the flag adds a required intent to action tools only, and the loop accepts and keeps it."""

import asyncio

import pytest

from aether.core.intent import INTENT_TOOLS, with_intent
from aether.core.tools import tools, validate_call


def test_intent_is_required_on_action_tools_and_absent_elsewhere():
    base = tools(python=True, images=True, history=True)
    out = with_intent(base)
    for spec in out:
        fn = spec["function"]
        has = "intent" in fn["parameters"]["properties"]
        assert has == (fn["name"] in INTENT_TOOLS), fn["name"]
        if has:
            assert fn["parameters"]["required"][0] == "intent"
    # the shared definitions are not mutated
    assert all("intent" not in s["function"]["parameters"]["properties"] for s in base)


def test_a_call_without_intent_is_rejected_and_one_with_it_is_valid():
    out = with_intent(tools(python=False))
    with pytest.raises(ValueError, match="missing required arguments: intent"):
        validate_call("terminal", {"input": "ls"}, out)
    validate_call("terminal", {"intent": "see what is here", "input": "ls"}, out)
    validate_call("finish", {"summary": "done"}, out)


def test_the_flag_reaches_the_core_config():
    from aether.core.harbor_agent import build_config

    base = {
        "AETHER_CORE_REVIEW": "off",
        "AETHER_CORE_CONTEXT": "clm",
        "AETHER_CORE_REPL": "off",
        "AETHER_CORE_IMAGES": "off",
    }
    assert build_config(environ=base).intent is False
    assert build_config(environ={**base, "AETHER_CORE_INTENT": "on"}).intent is True


def test_the_loop_advertises_intent_and_keeps_it_in_the_history(tmp_path):
    from aether.core.loop import CoreConfig, run_agent
    from tests.core_fakes import LocalEnv
    from aether.core.loop import Trace
    from tests.test_core_responses import ResponsesClient, provider, turn_events

    work = tmp_path / "w"
    work.mkdir()
    client = ResponsesClient(
        [
            turn_events(1, call=("terminal", {"intent": "make f.txt; expect it to hold hi", "input": "echo hi > f.txt"}, "c1")),
            turn_events(2, call=("finish", {"summary": "wrote f.txt"}, "c2")),
        ]
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="write f.txt",
            workdir=str(work),
            provider=provider(client, tmp_path),
            timeout_s=60,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), intent=True),
        )
    )
    assert result.status == "finished" and (work / "f.txt").read_text().strip() == "hi"
    terminal = next(t for t in client.requests[0]["tools"] if t["name"] == "terminal")
    assert terminal["parameters"]["required"][0] == "intent"
    second = client.requests[1]["input"]
    call = next(i for i in second if i.get("type") == "function_call")
    assert "expect it to hold hi" in call["arguments"]

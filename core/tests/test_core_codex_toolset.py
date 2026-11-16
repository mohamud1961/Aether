"""Study arms from the Codex source comparison (16 Nov): CX (toolset codex: terminal + freeform apply_patch),
SF (strict=false on Responses tools) and R2 (the first task message repeated). All default off."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from aether.core import apply_patch
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.responses import input_items, tool_spec
from aether.core.step0 import task_messages
from tests.core_fakes import LocalEnv
from tests.test_core_responses import ResponsesClient, ev, item, provider, turn_events

# ---- apply_patch semantics (Codex's patch format) ----------------------------------------------------------------

SRC = "def f():\n    return 1\n\n\ndef g():\n    return 2\n"


def _update(body):
    return apply_patch.parse(f"*** Begin Patch\n*** Update File: a.py\n{body}*** End Patch")[0]


def test_update_with_context_anchor_changes_only_the_anchored_chunk():
    hunk = _update("@@ def g():\n-    return 2\n+    return 3\n")
    assert apply_patch.updated(SRC, hunk) == SRC.replace("return 2", "return 3")


def test_chunks_apply_in_order_and_whitespace_fallback_matches():
    hunk = _update(" def f():\n-    return 1   \n+    return 10\n@@ def g():\n-    return 2\n+    return 20\n")
    out = apply_patch.updated(SRC, hunk)
    assert "return 10" in out and "return 20" in out and out.endswith("\n")


def test_missing_old_lines_are_refused_with_the_lines():
    hunk = _update("-    return 99\n+    return 3\n")
    with pytest.raises(apply_patch.PatchError, match="return 99"):
        apply_patch.updated(SRC, hunk)


def test_malformed_patches_are_refused():
    for text in ("*** Update File: a.py\n-x\n*** End Patch", "*** Begin Patch\n*** End Patch",
                 "*** Begin Patch\n*** Frobnicate: a\n*** End Patch", "*** Begin Patch\n*** Add File: a\n*** End Patch"):
        with pytest.raises(apply_patch.PatchError):
            apply_patch.parse(text)


def test_end_of_file_chunk_matches_at_the_end():
    text = "x\ny\nx\n"
    hunk = _update("-x\n+z\n*** End of File\n")
    assert apply_patch.updated(text, hunk) == "x\ny\nz\n"


# ---- Responses: strict default and freeform conversion ----------------------------------------------------------

FN = {"type": "function", "function": {"name": "view_image", "parameters": {"type": "object", "properties": {}}}}


def test_strict_is_sent_only_when_configured():
    assert "strict" not in tool_spec(FN)  # default: the provider decides (Luna then fills every field)
    assert tool_spec(FN, False)["strict"] is False
    pinned = {"type": "function", "function": {**FN["function"], "strict": True}}
    assert tool_spec(pinned, False)["strict"] is True  # a tool's own setting wins


def test_apply_patch_goes_out_as_a_grammar_tool_and_replays_as_custom_items():
    spec = tool_spec(apply_patch.TOOL, False)
    assert spec["type"] == "custom" and spec["format"]["syntax"] == "lark" and "parameters" not in spec
    patch = "*** Begin Patch\n*** Add File: x\n+1\n*** End Patch\n"
    history = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "apply_patch", "arguments": json.dumps({"input": patch})}},
            {"id": "c2", "type": "function", "function": {"name": "terminal", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "Success."},
        {"role": "tool", "tool_call_id": "c2", "content": "ok"},
    ]
    items = input_items(history, frozenset({"apply_patch"}))
    assert items[0] == {"type": "custom_tool_call", "call_id": "c1", "name": "apply_patch", "input": patch}
    assert [i["type"] for i in items[1:]] == ["function_call", "custom_tool_call_output", "function_call_output"]
    # known-bad: without the freeform set the same history is sent as function calls
    assert input_items(history)[0]["type"] == "function_call"


def _custom_turn(n, patch, cid):
    events = turn_events(n)
    events.insert(-1, ev("response.output_item.done",
                         item=item(type="custom_tool_call", call_id=cid, name="apply_patch", input=patch)))
    return events


def test_codex_toolset_end_to_end_through_the_loop(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    (work / "a.py").write_text(SRC)
    patch = ("*** Begin Patch\n*** Update File: a.py\n@@ def g():\n-    return 2\n+    return 3\n"
             "*** Add File: sub/new.txt\n+hello\n*** End Patch\n")
    bad = "*** Begin Patch\n*** Update File: a.py\n-    return 2\n+    return 4\n*** Add File: b.txt\n+x\n*** End Patch\n"
    client = ResponsesClient([
        _custom_turn(1, patch, "c1"),
        _custom_turn(2, bad, "c2"),  # return 2 no longer exists: nothing of this patch may be written
        turn_events(3, call=("finish", {"summary": "done"}, "c3")),
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="change g", workdir=str(work), provider=provider(client, tmp_path),
        timeout_s=60, trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(tmp_path / "ctl"), toolset="codex", repl=False)))
    assert result.status == "finished"
    assert (work / "a.py").read_text() == SRC.replace("return 2", "return 3")
    assert (work / "sub" / "new.txt").read_text() == "hello\n" and not (work / "b.txt").exists()
    names = [t.get("name") for t in client.requests[0]["tools"]]
    assert "apply_patch" in names and not {"read_file", "write_file", "edit_file", "python"} & set(names)
    assert "apply_patch:" in client.requests[0]["input"][0]["content"] and "edit_file" not in client.requests[0]["input"][0]["content"]
    second = client.requests[1]["input"]
    out = next(i for i in second if i.get("type") == "custom_tool_call_output")
    assert out["call_id"] == "c1" and out["output"].startswith("Success.")
    third = client.requests[2]["input"]
    refused = next(i for i in third if i.get("type") == "custom_tool_call_output" and i["call_id"] == "c2")
    assert "not found" in refused["output"]


def test_codex_toolset_rejects_the_repl():
    with pytest.raises(ValueError, match="repl"):
        CoreConfig(toolset="codex", repl=True)


# ---- R2: prompt repetition ----------------------------------------------------------------------------------------

def test_task_repeat_gives_the_whole_first_message_identically_twice():
    once = task_messages("", "Do X.", "", "(Working directory: /app.)")[0]["content"]
    twice = task_messages("", "Do X.", "", "(Working directory: /app.)", repeat=2)[0]["content"]
    assert twice == f"{once}\n\n{once}" and twice.count("Do X.") == 2
    with pytest.raises(ValueError):
        CoreConfig(task_repeat=5)


def test_harbor_env_sets_strict_off_and_codex_needs_responses():
    from aether.core.harbor_agent import build_provider

    env = {"AETHER_FW_GLM_53_FLASH_ENDPOINT": "https://x.example/v1", "AETHER_FW_GLM_53_FLASH_KEY": "k",
           "AETHER_FW_GLM_53_FLASH_DEPLOYMENT": "m", "AETHER_CORE_API": "openai", "AETHER_CORE_REQUEST": "responses"}
    assert build_provider(environ=env).tool_strict is None
    assert build_provider(environ={**env, "AETHER_CORE_TOOL_STRICT": "off"}).tool_strict is False
    from aether.core.harbor_config import ConfigError

    with pytest.raises(ConfigError):
        build_provider(environ={**env, "AETHER_CORE_TOOL_STRICT": "maybe"})
    with pytest.raises(ValueError, match="Responses"):
        build_provider(environ={**env, "AETHER_CORE_REQUEST": "chat", "AETHER_CORE_TOOLSET": "codex"})

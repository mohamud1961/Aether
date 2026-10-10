"""W0-C: static_kernel_v1 must never advertise tools the model cannot call."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

import pytest

from aether.execution import MemoryExecutor
from aether.model_hooks import ModelHooks
from aether.persistent_provider_protocol import (
    PERSISTENT_CHAT_PROVIDER_TOOLS,
    PERSISTENT_CHAT_STATIC_TOOL_KERNEL_V1_NAMES,
    PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES,
)
from aether.providers.chat_model import ChatCompletionsModelCallable
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.thin_loop import ThinLoopConfig, run_thin_loop

CANONICAL = tuple(
    tool["name"] for tool in PERSISTENT_CHAT_PROVIDER_TOOLS
    if tool["name"] != "update_completion_record"
)
EXPOSED = frozenset(PERSISTENT_CHAT_STATIC_TOOL_KERNEL_V1_NAMES)
CANONICAL_EXPOSED = frozenset(PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES)
HIDDEN = tuple(name for name in CANONICAL if name not in EXPOSED)


def _response(index: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"response-{index}",
        "choices": [{
            "index": 0,
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": f"call-{index}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }],
            },
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class _Transport:
    """Read a file, then read_output the exact receipt handle the packet exposed."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> dict[str, Any]:
        self.requests.append(deepcopy(request))
        count = len(self.requests)
        if count == 1:
            return _response(1, "read_file", {"arguments": {"path": "/app/workspace/x.txt"}})
        packet = json.dumps(request["messages"][-1])
        receipt = re.search(r'index_receipt_id\\?":\\?"([^"\\]+)', packet)
        assert receipt, packet
        handle = (
            "receipt:" + receipt.group(1).removesuffix("primary_action_result_index") + "read"
        )
        return _response(
            count, "read_output", {"arguments": {"handle": handle}})


def _run(mode: str):
    transport = _Transport()
    model = ChatCompletionsModelCallable(
        transport=transport, deployment="glm-test", native_persistent_tools=True,
        tool_surface_mode=mode,
    )
    hooks = ModelHooks(model, lambda *_a, **_k: "{}", run_id="w0c", task_id="w0c")
    env = EnvMap(
        task_prompt="Inspect x.txt.",
        workspace_root="/app/workspace",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file"),
            ),
            "shell": CapabilityDescriptor("shell", "shell", tool_names=("run_command",)),
        },
    )
    result = run_thin_loop(
        env,
        MemoryExecutor(workspace_root="/app/workspace", files={"/app/workspace/x.txt": "X-BYTES"}),
        hooks,
        config=ThinLoopConfig(
            max_steps=3, max_solver_turns=3, probe_runtime_capabilities=False,
            solver_tool_surface_mode=mode,
        ),
    )
    return result, transport


def _mentions(request: dict[str, Any], name: str) -> bool:
    text = "\n".join(json.dumps(message) for message in request["messages"])
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text) is not None


def test_t1_surface_includes_history_retrieval_and_advanced_run_command() -> None:
    assert {"read_output", "query_history", "finish_intent", "finish"} <= EXPOSED
    assert "run_command" in CANONICAL_EXPOSED
    assert "run_command_advanced" in EXPOSED


def test_t1_request_text_names_no_unexposed_tool_and_read_output_round_trips() -> None:
    result, transport = _run("static_kernel_v1")
    assert len(transport.requests) == 3
    for request in transport.requests:
        offered = {tool["function"]["name"] for tool in request["tools"]}
        assert offered == EXPOSED
        for name in HIDDEN:
            assert not _mentions(request, name), name
    context_text = "\n".join(
        str(message.get("content")) for message in transport.requests[1]["messages"]
    )
    assert '"action_kinds":["inspect_diff","query_history","read_file","read_output",' in context_text
    assert '"history_access"' in context_text
    reads = [r for r in result.receipts if r.kind == "read_output"]
    assert reads and reads[0].success
    assert "X-BYTES" in json.dumps(reads[0].payload)


def test_control_request_still_names_unexposed_tools_so_the_scan_is_falsifiable() -> None:
    _result, transport = _run("control")
    request = transport.requests[0]
    assert len(request["tools"]) == 27
    assert _mentions(request, "start_job")
    assert _mentions(request, "bootstrap_acquire")
    assert any(_mentions(request, name) for name in HIDDEN)


def test_control_tool_semantics_text_is_byte_identical_to_incumbent() -> None:
    from aether.compiler_prefix import PERSISTENT_PROTOCOL_CARD_SECTIONS, protocol_card_sections

    assert protocol_card_sections() is PERSISTENT_PROTOCOL_CARD_SECTIONS
    assert protocol_card_sections("control") is PERSISTENT_PROTOCOL_CARD_SECTIONS
    kernel = dict(protocol_card_sections("static_kernel_v1"))
    for name in HIDDEN:
        assert not re.search(rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])", kernel["tool_semantics"])


def test_filter_leaves_control_context_object_unchanged() -> None:
    from aether.persistent_provider_protocol import persistent_filter_context_for_tool_surface

    context = {"available_capabilities": {"action_kinds": list(CANONICAL)}, "history_access": {"a": 1}}
    assert persistent_filter_context_for_tool_surface(context, "control") is context


def test_filter_drops_retrieval_hints_for_unexposed_retrieval_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    import aether.persistent_provider_protocol as protocol

    monkeypatch.setattr(protocol, "PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES", ("read_file", "read_output"))
    context = {
        "available_capabilities": {"action_kinds": ["read_file", "start_job"]},
        "history_access": {"action": "query_history", "exact_receipts_via": "read_output"},
    }
    out = protocol.persistent_filter_context_for_tool_surface(context, "static_kernel_v1")
    assert "history_access" not in out
    assert out["available_capabilities"]["action_kinds"] == ["read_file"]
    monkeypatch.setattr(protocol, "PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES", ("read_file", "query_history"))
    out = protocol.persistent_filter_context_for_tool_surface(context, "static_kernel_v1")
    assert out["history_access"] == {"action": "query_history"}


def test_static_kernel_jobs_v1_restores_only_managed_job_lifecycle() -> None:
    from aether.compiler_prefix import protocol_card_sections
    from aether.persistent_provider_protocol import (
        PERSISTENT_CHAT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES,
        persistent_exposed_action_names,
    )

    expected_extra = {"start_job", "probe_job", "stop_process"}
    jobs = frozenset(PERSISTENT_CHAT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES)
    assert EXPOSED < jobs
    assert jobs - EXPOSED == expected_extra
    assert persistent_exposed_action_names("static_kernel_jobs_v1") == (
        CANONICAL_EXPOSED | expected_extra
    )

    semantics = dict(protocol_card_sections("static_kernel_jobs_v1"))["tool_semantics"]
    for name in expected_extra | {"run_command"}:
        assert re.search(rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])", semantics), name
    for name in HIDDEN:
        if name not in expected_extra:
            assert not re.search(
                rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])", semantics
            ), name


def test_static_kernel_jobs_v1_provider_request_matches_truthful_surface() -> None:
    from aether.persistent_provider_protocol import PERSISTENT_CHAT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES

    _result, transport = _run("static_kernel_jobs_v1")
    expected = frozenset(PERSISTENT_CHAT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES)
    assert len(transport.requests) == 3
    for request in transport.requests:
        offered = {tool["function"]["name"] for tool in request["tools"]}
        assert offered == expected
        assert {"start_job", "probe_job", "stop_process"} <= offered
        for name in HIDDEN:
            if name not in {"start_job", "probe_job", "stop_process"}:
                assert not _mentions(request, name), name

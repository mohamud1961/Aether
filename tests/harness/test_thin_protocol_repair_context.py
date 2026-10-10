from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.model_hooks import ModelHooks, ModelOutputError
from aether.providers.chat_model import (
    ChatCompletionsModelCallable,
    ChatModelOutputError,
)
from aether.thin_loop import _thin_protocol_retry_messages


def _malformed_run_command_response(raw_arguments: str) -> dict:
    return {
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": "tool-1",
                    "type": "function",
                    "function": {
                        "name": "run_command",
                        "arguments": raw_arguments,
                    },
                }],
            },
        }],
    }


def test_chat_parse_preserves_rejected_native_tool_call_for_repair() -> None:
    model = ChatCompletionsModelCallable(
        transport=lambda **_: None,
        deployment="test",
        role="solver",
        native_persistent_tools=True,
    )
    raw_arguments = json.dumps({
        "arguments": '{"command":"python3 verify.py", "timeout_s": 120',
    })

    with pytest.raises(ChatModelOutputError) as caught:
        model._parse(_malformed_run_command_response(raw_arguments))

    exc = caught.value
    assert exc.code == "provider_persistent_v0_direct_arguments_string_not_object"
    assert exc.rejected_tool_name == "run_command"
    assert exc.rejected_tool_arguments == raw_arguments


def test_model_hooks_propagates_rejected_tool_context_without_committing_it() -> None:
    raw_arguments = json.dumps({
        "arguments": '{"command":"python3 verify.py", "timeout_s": 120',
    })

    class RejectingSolver:
        def __call__(self, messages, *, max_output_tokens=None):
            del messages, max_output_tokens
            raise ChatModelOutputError(
                "provider_persistent_v0_direct_action_fields_invalid",
                '["arguments"]',
                rejected_tool_name="run_command",
                rejected_tool_arguments=raw_arguments,
            )

        def reject_pending_response(self, **kwargs):
            del kwargs

    hooks = ModelHooks(
        RejectingSolver(),
        lambda *_args, **_kwargs: "{}",
        task_id="task",
        run_id="run",
    )
    compiled = SimpleNamespace(
        selected_capability_ids=lambda: (),
        config_realization={},
        action_schema=(),
    )

    with pytest.raises(ModelOutputError) as caught:
        hooks.solve([{"role": "system", "content": "stable"}], compiled)

    exc = caught.value
    assert exc.rejected_tool_name == "run_command"
    assert exc.rejected_tool_arguments == raw_arguments


def test_thin_retry_preserves_rejected_tool_as_inert_nonexecuted_context() -> None:
    exc = ModelOutputError(
        'solver output could not be parsed: provider_persistent_v0_direct_action_fields_invalid: ["arguments"]'
    )
    exc.rejected_tool_name = "run_command"
    exc.rejected_tool_arguments = json.dumps({
        "arguments": '{"command":"python3 verify.py"}',
    })

    original = [{"role": "system", "content": "stable observed context"}]
    retry = _thin_protocol_retry_messages(original, exc)

    assert retry[:-1] == original
    notice = retry[-1]
    assert notice["role"] == "user"
    content = notice["content"]
    lower = content.lower()
    assert "rejected tool name: run_command" in lower
    assert "python3 verify.py" in content
    assert "inert non-executed repair context" in lower
    assert "no task action occurred" in lower
    assert "do not re-plan merely because transport serialization failed" in lower
    assert "do not claim the rejected action occurred" in lower


def test_thin_retry_without_provider_repair_context_keeps_generic_fail_closed_prompt() -> None:
    exc = ModelOutputError("invalid response envelope")
    retry = _thin_protocol_retry_messages(
        [{"role": "system", "content": "stable observed context"}],
        exc,
    )

    content = retry[-1]["content"].lower()
    assert "previous response was rejected before execution" in content
    assert "change only the invalid envelope or field" in content
    assert "rejected tool name" not in content

"""Provider-free scenario drivers shared by the context-boundary mechanism tests.

Nothing here talks to a provider: a scripted transport answers every request and
records the exact model-visible payload.
"""
from __future__ import annotations

import json
from typing import Any

from aether.providers.chat_model import ChatCompletionsModelCallable

PACKET = "[context_packet]\n"
RUN, TASK = "run-cap", "task-cap"
REASONING_CHARS = 12_000
TOKEN_LIMIT = 26_000
MAX_OUTPUT = 400
CHECKPOINT_TEXT = "CKPT: REQ-1 done; REQ-2 open; next: run the verifier.\n  keep   spaces"


def tool_response(call_id: str, *, reasoning: str, name: str = "read_file", args: dict | None = None) -> dict[str, Any]:
    return {
        "choices": [{
            "index": 0,
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args or {"arguments": {"path": "/app/workspace/x"}}),
                    },
                }],
                "reasoning_content": reasoning,
            },
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }


def checkpoint_response(content: Any = CHECKPOINT_TEXT) -> dict[str, Any]:
    return tool_response(
        "ckpt-call", reasoning="checkpoint-reasoning", name="write_checkpoint",
        args={"content": content},
    )


class Transport:
    """Normal turns come from `responses`; forced write_checkpoint turns from `checkpoints`."""

    def __init__(
        self, *responses: dict[str, Any] | Exception,
        checkpoints: list[dict[str, Any] | Exception] | None = None,
    ) -> None:
        self.responses = list(responses)
        self.checkpoints = list(checkpoints or [])
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> dict[str, Any]:
        self.requests.append(json.loads(json.dumps(request)))
        item = (self.checkpoints if is_checkpoint_request(request) else self.responses).pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class CapacityPacer:
    """Pacer stand-in with the production estimate rule (bytes/4 + output cap)."""

    def __init__(self, token_limit: int) -> None:
        self.token_limit = token_limit
        self.window_s = 60.0

    @staticmethod
    def approximate_request_tokens(request_bytes: int, max_output_tokens: int) -> int:
        return (int(request_bytes) + 3) // 4 + int(max_output_tokens)

    def admit(self, *, estimated_tokens: int) -> dict[str, Any]:
        return {
            "throughput_token_limit": self.token_limit,
            "throughput_window_s": self.window_s,
            "throughput_estimated_tokens": int(estimated_tokens),
            "throughput_wait_s": 0.0,
            "throughput_single_request_admission": "provider_authoritative",
        }

    def reconcile_success(self, *, input_tokens, requested_output_tokens, output_tokens=None):
        return {"throughput_usage_reconciled": True}

    def note_rate_limit(self) -> None:
        pass


def packet_message(step: int) -> dict[str, str]:
    receipts = [{
        "receipt_id": f"step-{i}:read",
        "exact_access": {"handle": f"receipt-handle-{i}"},
        "bounded_view": {"excerpt": f"observed-{i}"},
    } for i in range(step + 1)]
    payload = {
        "latest_primary_result": {"status": "succeeded", "outcome_receipts": [receipts[-1]]},
        "evidence_index": receipts,
        "budgets": {"used_kernel_steps": step},
    }
    return {"role": "system", "content": PACKET + json.dumps(payload, sort_keys=True, separators=(",", ":"))}


def fresh_messages(step: int) -> list[dict[str, str]]:
    return [{"role": "system", "content": "[raw_user_task]\nT"}, packet_message(step)]


def make_model(
    transport: Transport,
    *,
    mode: str = "off",
    transport_mode: str = "observation_history_v1",
    token_limit: int | None = TOKEN_LIMIT,
) -> ChatCompletionsModelCallable:
    model = ChatCompletionsModelCallable(
        transport=transport,
        deployment="glm-test",
        role="solver",
        native_persistent_tools=True,
        throughput_pacer=CapacityPacer(token_limit) if token_limit else None,  # type: ignore[arg-type]
        capacity_reanchor_recovery_mode=mode,
    )
    model.set_reality_transport_mode(transport_mode, run_id=RUN, task_id=TASK)
    return model


def drive(model: ChatCompletionsModelCallable, steps: range) -> None:
    for step in steps:
        model.call_with_telemetry_scope(
            fresh_messages(step), max_output_tokens=MAX_OUTPUT, run_id=RUN, task_id=TASK,
        )
        model.commit_pending_response(run_id=RUN, task_id=TASK)


def normal_responses(count: int) -> list[dict[str, Any]]:
    return [
        tool_response(f"call-{i}", reasoning=f"reasoning-{i}-" + "r" * REASONING_CHARS)
        for i in range(count)
    ]


def is_checkpoint_request(request: dict[str, Any]) -> bool:
    return isinstance(request.get("tool_choice"), dict)

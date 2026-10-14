"""Small OpenAI-compatible tool loop. No retries; keys are read from environment.

A scripted transport can test protocol wiring. It does not prove model capability.
Provider prices must be explicitly supplied; unpriced runs retain usage and cost_known=false.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import time
import urllib.request
from urllib.parse import urlsplit

from .base import AgentResult

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run bash in the task workspace.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    }
]


class MinimalAgent:
    name = "minimal"

    def __init__(
        self,
        model,
        endpoint=None,
        transport=None,
        max_turns=40,
        input_per_million=None,
        output_per_million=None,
    ):
        if not model or max_turns < 1:
            raise ValueError("model and a positive turn budget are required")
        self.model = model
        self.endpoint = endpoint or os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        parsed = urlsplit(self.endpoint)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint credentials belong in environment, not URL")
        self.transport = transport or self._request
        self.max_turns = max_turns
        self.prices = (input_per_million, output_per_million)
        if any(p is not None and (not math.isfinite(p) or p < 0) for p in self.prices):
            raise ValueError("prices must be finite and nonnegative")

    def _request(self, payload, timeout):
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("provider API credential missing (OPENAI_API_KEY)")
        request = urllib.request.Request(
            self.endpoint.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key,
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def run(self, task, sandbox, budget_s):
        deadline = time.monotonic() + budget_s
        messages = [
            {
                "role": "system",
                "content": "Solve the task using bash. Work in the current workspace. Report completion only when the requested artifacts are correct.",
            },
            {"role": "user", "content": task.prompt},
        ]
        trace, actions = [], []
        tokens_in = tokens_out = calls = 0
        claim, error, finished = "", None, False
        for turn in range(self.max_turns):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            payload = {
                "model": self.model,
                "messages": copy.deepcopy(messages),
                "tools": TOOLS,
            }
            start = time.monotonic()
            try:
                response = self.transport(payload, remaining)
            except Exception as exc:
                # Never serialize request headers or arbitrary provider exception bodies.
                status = getattr(exc, "code", None)
                error = f"provider error {type(exc).__name__}" + (
                    f" HTTP {status}" if status else ""
                )
                trace.append({"request": payload, "error": error, "turn": turn})
                break
            trace.append(
                {
                    "request": payload,
                    "endpoint": self.endpoint,
                    "response": response,
                    "turn": turn,
                    "provider_wall_s": time.monotonic() - start,
                    "request_sha256": hashlib.sha256(
                        json.dumps(payload, sort_keys=True).encode()
                    ).hexdigest(),
                    "response_sha256": hashlib.sha256(
                        json.dumps(response, sort_keys=True).encode()
                    ).hexdigest(),
                    "cost_known": all(p is not None for p in self.prices),
                }
            )
            usage = response.get("usage", {})
            tokens_in += usage.get("prompt_tokens", 0)
            tokens_out += usage.get("completion_tokens", 0)
            choice = response["choices"][0]
            message = choice["message"]
            messages.append(message)
            tools = message.get("tool_calls") or []
            if not tools:
                claim = message.get("content") or ""
                finished = choice.get("finish_reason") == "stop"
                if not finished:
                    error = "provider output truncated or unsupported finish reason"
                break
            for call in tools:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = "task budget exhausted"
                    break
                try:
                    function = call["function"]
                    args = json.loads(function["arguments"])
                    if (
                        function["name"] != "bash"
                        or set(args) != {"command"}
                        or not isinstance(args["command"], str)
                    ):
                        raise ValueError("invalid tool schema")
                    actions.append(args["command"])
                    result = sandbox.exec(args["command"], remaining)
                    calls += 1
                    output = {
                        "exit_code": result.code,
                        "stdout": result.stdout[:20000],
                        "stderr": result.stderr[:20000],
                        "timed_out": result.timed_out,
                        "output_truncated": len(result.stdout) > 20000
                        or len(result.stderr) > 20000,
                    }
                except (ValueError, KeyError, TypeError) as exc:
                    output = {"tool_error": type(exc).__name__}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(output),
                    }
                )
            if error:
                break
        priced = all(p is not None for p in self.prices)
        cost = (
            (tokens_in * self.prices[0] + tokens_out * self.prices[1]) / 1e6
            if priced
            else 0.0
        )
        return AgentResult(
            finished, claim, tokens_in, tokens_out, cost, calls, actions, error, trace
        )


def make(model, **opts):
    return MinimalAgent(model, **opts)

"""OpenAI-compatible chat client: streaming, honest retries, no local throttling.

The provider is the only rate authority: a 429 or 5xx is retried with backoff
(honouring Retry-After); nothing is pre-emptively delayed on the client side.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import random
import time
from typing import Any, Callable
from urllib.parse import urlparse

RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504, 529})
MAX_ATTEMPTS = 8


class ProviderError(RuntimeError):
    """The provider could not produce a response (after retries) or rejected the request."""

    def __init__(self, message: str, *, status: int | None = None, context_overflow: bool = False,
                 deadline: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.context_overflow = context_overflow
        self.deadline = deadline  # the run's time ran out; not a provider fault


@dataclass
class Turn:
    content: str = ""
    reasoning: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    latency_s: float = 0.0
    attempts: int = 1
    failures: list[dict[str, Any]] = field(default_factory=list)  # one row per failed attempt

    def assistant_message(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or None}
        if self.reasoning:
            msg["reasoning_content"] = self.reasoning
        if self.tool_calls:
            msg["tool_calls"] = [_replayable(c) for c in self.tool_calls]
        return msg


def _replayable(call: dict[str, Any]) -> dict[str, Any]:
    """The call as it goes back into the history. The API rejects a request whose history holds arguments that
    are not a JSON object (V2 binary-extract: one malformed submission, then HTTP 400 on every later call), so those
    are replayed as {}; dispatch still sees the raw text and reports the decode error to the model."""
    try:
        if isinstance(json.loads(call["function"]["arguments"] or "{}"), dict):
            return call
    except json.JSONDecodeError:
        pass
    return {**call, "function": {**call["function"], "arguments": "{}"}}


def azure_base_url(endpoint: str) -> str:
    value = endpoint.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        value = f"{parsed.scheme}://{parsed.netloc}"
    return value + "/openai/v1/"


def _usage(raw: Any) -> dict[str, int]:
    if raw is None:
        return {}
    data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
    details = data.get("completion_tokens_details") or {}
    prompt_details = data.get("prompt_tokens_details") or {}
    return {
        "input": int(data.get("prompt_tokens") or 0),
        "cached": int(prompt_details.get("cached_tokens") or 0),
        "output": int(data.get("completion_tokens") or 0),
        "reasoning": int(details.get("reasoning_tokens") or 0),
    }


def _extra(obj: Any, name: str) -> Any:
    value = getattr(obj, name, None)
    if value is None:
        extra = getattr(obj, "model_extra", None) or {}
        value = extra.get(name)
    return value


class ChatProvider:
    def __init__(self, client: Any, *, model: str, params: dict[str, Any],
                 sleep: Callable[[float], Any] = asyncio.sleep) -> None:
        self._client = client
        self.model = model
        self.params = dict(params)
        self._sleep = sleep
        self.failed_attempts = 0
        self.failure_log: list[dict[str, Any]] = []  # every failed attempt in the run, for the record

    async def _stream_once(self, messages: list[dict], tools: list[dict] | None, max_tokens: int,
                           overrides: dict[str, Any] | None = None) -> Turn:
        started = time.monotonic()
        params = {**self.params, **(overrides or {})}
        extra: dict[str, Any] = {"tools": tools}
        if tools is None:  # plain text call (e.g. a context checkpoint): no tool parameters at all
            extra = {}
            params.pop("tool_choice", None)
            params.pop("parallel_tool_calls", None)
        stream = await self._client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=max_tokens, stream=True,
            stream_options={"include_usage": True}, **extra, **params)
        turn = Turn()
        calls: dict[int, dict[str, Any]] = {}
        async for chunk in stream:
            if getattr(chunk, "usage", None):
                turn.usage = _usage(chunk.usage)
            for choice in chunk.choices or ():
                delta = choice.delta
                if delta is not None:
                    turn.content += getattr(delta, "content", None) or ""
                    turn.reasoning += _extra(delta, "reasoning_content") or ""
                    for tc in getattr(delta, "tool_calls", None) or ():
                        slot = calls.setdefault(int(tc.index or 0), {"id": "", "name": "", "arguments": ""})
                        slot["id"] = tc.id or slot["id"]
                        if tc.function is not None:
                            slot["name"] += tc.function.name or ""
                            slot["arguments"] += tc.function.arguments or ""
                if choice.finish_reason:
                    turn.finish_reason = choice.finish_reason
        turn.tool_calls = [
            {"id": c["id"] or f"call_{i}", "type": "function",
             "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
            for i, c in sorted(calls.items())
        ]
        turn.latency_s = time.monotonic() - started
        return turn

    async def complete(self, messages: list[dict], tools: list[dict] | None, *, max_tokens: int,
                       remaining_s: Callable[[], float], overrides: dict[str, Any] | None = None) -> Turn:
        """One model turn. ``tools=None`` makes a plain text call (tool parameters are dropped);
        ``overrides`` replaces sampling parameters for this call only."""
        delay = 2.0
        failures: list[dict[str, Any]] = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.monotonic()
            try:
                turn = await asyncio.wait_for(self._stream_once(messages, tools, max_tokens, overrides),
                                              timeout=max(5.0, remaining_s()))
                turn.attempts, turn.failures = attempt, failures
                return turn
            except asyncio.TimeoutError as exc:
                raise ProviderError("provider call outlived the run deadline", deadline=True) from exc
            except Exception as exc:  # classify, then retry or raise with the real reason
                status = getattr(exc, "status_code", None)
                text = str(exc)
                row = {"attempt": attempt, "status": status, "error": type(exc).__name__,
                       "detail": text[:200], "after_s": round(time.monotonic() - started, 2)}
                if status == 400 and any(k in text.lower() for k in ("context", "too long", "maximum", "tokens")):
                    raise ProviderError(text[:500], status=400, context_overflow=True) from exc
                transient = status in RETRYABLE_STATUS or status is None and _is_transport(exc)
                if not transient or attempt == MAX_ATTEMPTS:
                    self._record(row)
                    raise ProviderError(f"{type(exc).__name__}: {text[:500]}", status=status) from exc
                self.failed_attempts += 1
                hinted = _retry_after(exc)
                wait = hinted or delay * (0.75 + 0.5 * random.random())
                row.update(wait_s=round(wait, 2), retry_after=hinted)
                failures.append(row)
                self._record(row)
                if wait > remaining_s() - 10:
                    raise ProviderError(f"retry wait {wait:.0f}s exceeds remaining time", status=status,
                                        deadline=True) from exc
                await self._sleep(wait)
                delay = min(delay * 2, 60.0)
        raise ProviderError("unreachable")

    def _record(self, row: dict[str, Any]) -> None:
        self.failure_log.append(row)


def _is_transport(exc: Exception) -> bool:
    name = type(exc).__name__
    return name in {"APIConnectionError", "APITimeoutError", "RemoteProtocolError", "ReadTimeout",
                    "ConnectError", "ReadError", "ConnectionResetError"}


def _retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    for key in ("retry-after-ms", "retry-after"):
        value = headers.get(key) if hasattr(headers, "get") else None
        if value:
            try:
                seconds = float(value) / (1000.0 if key.endswith("ms") else 1.0)
                return min(max(seconds, 0.5), 60.0)
            except ValueError:
                return None
    return None


def parse_arguments(raw: str) -> dict[str, Any]:
    """Decode tool arguments; tolerate one level of double-encoding, never guess further."""
    value = json.loads(raw or "{}")
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, dict) and set(value) == {"arguments"} and isinstance(value["arguments"], (dict, str)):
        inner = value["arguments"]
        value = json.loads(inner) if isinstance(inner, str) else inner
    if not isinstance(value, dict):
        raise ValueError("tool arguments must be a JSON object")
    return value

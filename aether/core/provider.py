"""OpenAI-compatible chat client: streaming, honest retries, no local throttling.

The provider is the only rate authority: a 429 or 5xx is retried with backoff
(honouring Retry-After up to the run's deadline); nothing is pre-emptively delayed on
the client side. Every attempt, from every role, goes to the call log (see ``calls``).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import random
import time
from typing import Any, Callable
from urllib.parse import urlparse

from .calls import CallLog

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
    usage: dict[str, int] = field(default_factory=dict)  # only the fields the provider reported
    response_id: str = ""
    response_model: str = ""
    latency_s: float = 0.0
    attempts: int = 1
    failures: list[dict[str, Any]] = field(default_factory=list)  # one row per failed attempt
    streamed_calls: dict[int, dict[str, str]] = field(default_factory=dict)  # tool calls as they stream in

    def response(self) -> dict[str, Any]:
        """What came back, as assembled from the stream (partial if the stream did not finish)."""
        calls = self.tool_calls or [{"id": c["id"], "function": {"name": c["name"], "arguments": c["arguments"]}}
                                    for _, c in sorted(self.streamed_calls.items())]
        return {"content": self.content, "reasoning": self.reasoning, "tool_calls": calls}

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
    """The usage fields the provider reported; a field it left out is absent, not zero."""
    if raw is None:
        return {}
    data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
    sources = {"input": (data, "prompt_tokens"), "output": (data, "completion_tokens"),
               "cached": (data.get("prompt_tokens_details") or {}, "cached_tokens"),
               "reasoning": (data.get("completion_tokens_details") or {}, "reasoning_tokens")}
    out = {}
    for name, (where, key) in sources.items():
        value = where.get(key) if isinstance(where, dict) else None
        if isinstance(value, int) and not isinstance(value, bool):
            out[name] = value
    return out


def _extra(obj: Any, name: str) -> Any:
    value = getattr(obj, name, None)
    if value is None:
        extra = getattr(obj, "model_extra", None) or {}
        value = extra.get(name)
    return value


class ChatProvider:
    def __init__(self, client: Any, *, model: str, params: dict[str, Any],
                 sleep: Callable[[float], Any] = asyncio.sleep, log: CallLog | None = None) -> None:
        self._client = client
        self.model = model
        self.params = dict(params)
        self._sleep = sleep
        self.log = log or CallLog()
        self.failed_attempts = 0
        self.failure_log: list[dict[str, Any]] = []  # every failed attempt in the run, for the record

    def _request(self, messages: list[dict], tools: list[dict] | None, max_tokens: int,
                 overrides: dict[str, Any] | None) -> dict[str, Any]:
        """The exact client arguments, with sampling and tool parameters grouped under ``params``."""
        params = {**self.params, **(overrides or {}), "stream": True, "stream_options": {"include_usage": True}}
        request: dict[str, Any] = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        if tools is None:  # plain text call (e.g. a context checkpoint): no tool parameters at all
            params.pop("tool_choice", None)
            params.pop("parallel_tool_calls", None)
        else:
            request["tools"] = tools
        request["params"] = params
        return request

    async def _stream_once(self, request: dict[str, Any], turn: Turn) -> None:
        """Fill ``turn`` from one streamed attempt (partly filled if the stream fails)."""
        started = time.monotonic()
        args = {k: v for k, v in request.items() if k != "params"}
        stream = await self._client.chat.completions.create(**args, **request["params"])
        calls = turn.streamed_calls
        async for chunk in stream:
            turn.response_id = turn.response_id or str(getattr(chunk, "id", "") or "")
            turn.response_model = turn.response_model or str(getattr(chunk, "model", "") or "")
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

    async def complete(self, messages: list[dict], tools: list[dict] | None, *, max_tokens: int,
                       remaining_s: Callable[[], float], overrides: dict[str, Any] | None = None,
                       role: str = "worker") -> Turn:
        """One model turn. ``tools=None`` makes a plain text call (tool parameters are dropped);
        ``overrides`` replaces sampling parameters for this call only; ``role`` labels it in the call log."""
        delay = 2.0
        failures: list[dict[str, Any]] = []
        request = self._request(messages, tools, max_tokens, overrides)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.monotonic()
            left = remaining_s()
            if left <= 0:
                raise ProviderError("no time left for a provider call", deadline=True)
            turn = Turn()
            seq = self.log.start(role=role, attempt=attempt, request=request)
            try:
                await asyncio.wait_for(self._stream_once(request, turn), timeout=left)
            except asyncio.CancelledError:  # the caller was cancelled: the attempt ends as cancelled, then re-raise
                self.log.end(seq, {"ok": False, "error": "cancelled", "response": turn.response(),
                                   "after_s": round(time.monotonic() - started, 2)})
                raise
            except asyncio.TimeoutError as exc:
                self._failed(seq, role, attempt, turn, started, status=None, error="deadline",
                             detail="the call outlived the run deadline")
                raise ProviderError("provider call outlived the run deadline", deadline=True) from exc
            except Exception as exc:  # classify, then retry or raise with the real reason
                status = getattr(exc, "status_code", None)
                text = str(exc)
                row = self._failed(seq, role, attempt, turn, started, status=status,
                                   error=type(exc).__name__, detail=text[:200])
                if status == 400 and any(k in text.lower() for k in ("context", "too long", "maximum", "tokens")):
                    raise ProviderError(text[:500], status=400, context_overflow=True) from exc
                transient = status in RETRYABLE_STATUS or status is None and _is_transport(exc)
                if not transient or attempt == MAX_ATTEMPTS:
                    raise ProviderError(f"{type(exc).__name__}: {text[:500]}", status=status) from exc
                hinted = _retry_after(exc)
                wait = hinted or delay * (0.75 + 0.5 * random.random())
                row.update(wait_s=round(wait, 2), retry_after=hinted)
                failures.append(row)
                if wait > remaining_s() - 10:
                    raise ProviderError(f"retry wait {wait:.0f}s exceeds remaining time", status=status,
                                        deadline=True) from exc
                await self._sleep(wait)
                delay = min(delay * 2, 60.0)
                continue
            turn.attempts, turn.failures = attempt, failures
            self.log.end(seq, {"ok": True, "usage": turn.usage, "response": turn.response(),
                               "response_id": turn.response_id, "response_model": turn.response_model,
                               "finish_reason": turn.finish_reason, "latency_s": round(turn.latency_s, 3)})
            return turn
        raise ProviderError("unreachable")

    def _failed(self, seq: int, role: str, attempt: int, turn: Turn, started: float, *,
                status: int | None, error: str, detail: str) -> dict[str, Any]:
        """Count and log one failed attempt (its usage is unknown); returns the trace row."""
        row = {"attempt": attempt, "role": role, "status": status, "error": error, "detail": detail,
               "after_s": round(time.monotonic() - started, 2)}
        self.failed_attempts += 1
        self.failure_log.append(row)
        self.log.end(seq, {"ok": False, "status": status, "error": error, "detail": detail,
                           "response_id": turn.response_id, "response": turn.response(), "after_s": row["after_s"]})
        return row


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
                return max(seconds, 0.5)  # the caller gives up if it exceeds the remaining time
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

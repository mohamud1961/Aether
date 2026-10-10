"""Collect a streamed Chat Completions response into the non-streamed shape.

Long GLM generations are dropped by the hosted route when a non-streamed
request runs past roughly 250 s (Wave 1: no completed call above 253 s, every
longer call hung until the client timeout). Streaming keeps the connection
active; the SDK read timeout then bounds the gap between chunks rather than the
whole generation.
"""
from __future__ import annotations

from typing import Any, Callable

DEFAULT_STREAM_IDLE_TIMEOUT_S = 120.0
STREAM_OPTIONS = {"include_usage": True}


class ChatStreamDeadline(Exception):
    """The task deadline expired while chunks were still arriving."""


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    for method in ("model_dump", "to_dict"):
        dump = getattr(value, method, None)
        if callable(dump):
            return _plain(dump())
    return {k: _plain(v) for k, v in vars(value).items() if not k.startswith("_")}


def _stream_request_id(stream: Any) -> str | None:
    """Extract one request-id scalar without retaining the response headers."""
    candidates = (
        _get(stream, "_request_id", None),
        _get(stream, "request_id", None),
    )
    for candidate in candidates:
        if _valid_request_id(candidate):
            return candidate.strip()

    # The installed OpenAI streaming SDK exposes an httpx Response at
    # ``stream.response``; unlike non-streamed model objects it does not
    # expose ``_request_id``. Read only the single correlation header and drop
    # the response/header objects immediately.
    response = _get(stream, "response", None)
    headers = _get(response, "headers", None)
    get_header = getattr(headers, "get", None)
    if callable(get_header):
        candidate = get_header("x-request-id")
        if _valid_request_id(candidate):
            return candidate.strip()
    return None


def _valid_request_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= 512
        and all(ord(char) >= 32 and ord(char) != 127 for char in value)
    )


def collect_chat_stream(
    stream: Any,
    *,
    capture_request_id: bool = False,
    deadline_remaining_s: Callable[[], float | None] | None = None,
) -> dict[str, Any]:
    """Return a ChatCompletion-shaped dict built from every streamed chunk."""
    provider_request_id = _stream_request_id(stream) if capture_request_id else None
    response_id = model = None
    content: list[str] = []
    reasoning: list[str] = []
    tool_calls: dict[int, dict[str, Any]] = {}
    finish_reason = None
    usage = None
    chunk_count = 0
    try:
        for chunk in stream:
            chunk_count += 1
            response_id = _get(chunk, "id", None) or response_id
            model = _get(chunk, "model", None) or model
            chunk_usage = _get(chunk, "usage", None)
            if chunk_usage is not None:
                usage = _plain(chunk_usage)
            for choice in _get(chunk, "choices", None) or ():
                delta = _get(choice, "delta", None)
                if delta is not None:
                    text = _get(delta, "content", None)
                    if text:
                        content.append(text)
                    thought = _get(delta, "reasoning_content", None) or _get(delta, "reasoning", None)
                    if isinstance(thought, str) and thought:
                        reasoning.append(thought)
                    for call in _get(delta, "tool_calls", None) or ():
                        index = int(_get(call, "index", 0) or 0)
                        slot = tool_calls.setdefault(index, {
                            "id": None, "type": "function",
                            "function": {"name": "", "arguments": ""},
                        })
                        slot["id"] = _get(call, "id", None) or slot["id"]
                        slot["type"] = _get(call, "type", None) or slot["type"]
                        function = _get(call, "function", None)
                        if function is not None:
                            slot["function"]["name"] += _get(function, "name", None) or ""
                            slot["function"]["arguments"] += _get(function, "arguments", None) or ""
                finish_reason = _get(choice, "finish_reason", None) or finish_reason
            if deadline_remaining_s is not None:
                remaining = deadline_remaining_s()
                if remaining is not None and remaining <= 0.0:
                    raise ChatStreamDeadline("task run deadline expired while streaming")
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001 - closing must not mask the result.
                pass
    message: dict[str, Any] = {
        "role": "assistant",
        "content": "".join(content) or None,
        "tool_calls": [tool_calls[i] for i in sorted(tool_calls)] or None,
    }
    if reasoning:
        message["reasoning_content"] = "".join(reasoning)
    return {
        "id": response_id,
        "provider_request_id": provider_request_id,
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
        "usage": usage,
        "stream_chunk_count": chunk_count,
    }

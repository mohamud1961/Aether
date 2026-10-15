"""The same provider contract over the OpenAI Responses API, for models that need it (GPT-6-Luna).

On Chat Completions, GPT-6-Luna refuses function tools together with ``reasoning_effort`` and drops its reasoning after
every turn. Over ``/v1/responses`` it takes native tools while reasoning, and returns its reasoning as encrypted
items that can be sent back. Calls are stateless (``store=false``): Core keeps the history, as it does for GLM.

Continuity uses the slot GLM's reasoning already uses. ``Turn.assistant_message`` puts the encrypted reasoning
items in ``reasoning_content``, so the existing policies apply unchanged: the newest assistant turn's reasoning is
replayed in the next request and older turns' is dropped (``clm.request``, ``context``). The readable reasoning
summary goes to ``Turn.reasoning`` for the trace only.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .provider import ChatProvider, IncompleteStream, Turn

INCLUDE = ["reasoning.encrypted_content"]


def tool_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """A Chat Completions tool definition in Responses form (the function fields move up one level)."""
    fn = spec["function"]
    out = {"type": "function", "name": fn["name"], "parameters": fn["parameters"]}
    if fn.get("description"):
        out["description"] = fn["description"]
    return out


def _parts(content: Any) -> Any:
    if not isinstance(content, list):
        return content if content is not None else ""
    out = []
    for part in content:
        if part.get("type") == "image_url":
            out.append({"type": "input_image", "image_url": part["image_url"]["url"]})
        elif part.get("type") == "text":
            out.append({"type": "input_text", "text": part["text"]})
        else:
            raise ValueError(f"unsupported message part {part.get('type')!r}")
    return out


def _text(content: Any) -> str:
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if p.get("type") == "text")
    return content or ""


def input_items(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Core's chat-shaped history as Responses input items, in order."""
    items: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role in ("system", "user", "developer"):
            items.append({"role": role, "content": _parts(msg.get("content"))})
        elif role == "assistant":
            content, calls = msg.get("content"), msg.get("tool_calls") or []
            replay = msg.get("reasoning_content")
            # encrypted items only (a text reasoning field cannot be replayed here); a reasoning item must be
            # followed by the output it produced, so a turn with neither text nor calls replays none
            if isinstance(replay, list) and (content or calls):
                items.extend(replay)
            if content:
                items.append({"role": "assistant", "content": _text(content)})
            for call in calls:
                fn = call["function"]
                items.append(
                    {
                        "type": "function_call",
                        "call_id": call["id"],
                        "name": fn["name"],
                        "arguments": fn["arguments"],
                    }
                )
        elif role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": msg["tool_call_id"],
                    "output": _text(msg.get("content")),
                }
            )
        else:
            raise ValueError(f"unsupported message role {role!r}")
    return items


def _usage(raw: Any) -> dict[str, int]:
    """The usage fields the provider reported; a field it left out is absent, not zero."""
    if raw is None:
        return {}
    data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
    sources = {
        "input": (data, "input_tokens"),
        "output": (data, "output_tokens"),
        "cached": (data.get("input_tokens_details") or {}, "cached_tokens"),
        "reasoning": (data.get("output_tokens_details") or {}, "reasoning_tokens"),
    }
    out = {}
    for name, (where, key) in sources.items():
        value = where.get(key) if isinstance(where, dict) else None
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            out[name] = value
    return out


def _dump(obj: Any) -> dict[str, Any]:
    return (
        obj.model_dump(exclude_none=True) if hasattr(obj, "model_dump") else dict(obj)
    )


class ResponsesProvider(ChatProvider):
    """``ChatProvider`` (retries, deadlines, call log) with the Responses request and stream."""

    def __init__(
        self, client: Any, *, cache_key: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(client, **kwargs)
        self.limit_field = "max_output_tokens"
        # One key per provider (one response chain): the API routes calls with the same key and prefix to the same
        # cache, as Codex does per session. Without it, parallel runs sharing the system prompt are routed by the
        # prefix alone and can overflow one another's cache.
        self.cache_key = (
            f"aether-{uuid.uuid4().hex}" if cache_key is None else cache_key
        )

    def _request(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
        overrides: dict[str, Any] | None,
    ) -> dict[str, Any]:
        params = {**self.params, **(overrides or {})}
        effort = params.pop("reasoning_effort", None)
        params.update(stream=True, store=False, include=list(INCLUDE))
        if self.cache_key:
            params["prompt_cache_key"] = self.cache_key
        if effort:
            params["reasoning"] = {"effort": effort, "summary": "auto"}
        request: dict[str, Any] = {
            "model": self.model,
            "input": input_items(messages),
            "max_output_tokens": max_tokens,
        }
        if tools is None:
            params.pop("tool_choice", None)
            params.pop("parallel_tool_calls", None)
        else:
            request["tools"] = [tool_spec(t) for t in tools]
        request["params"] = params
        return request

    async def _stream_once(self, request: dict[str, Any], turn: Turn) -> None:
        started = time.monotonic()
        args = {k: v for k, v in request.items() if k != "params"}
        stream = await self._client.responses.create(**args, **request["params"])
        reasoning: list[dict[str, Any]] = []
        final = None
        try:
            async for event in stream:
                kind = getattr(event, "type", "")
                if kind == "response.created":
                    turn.response_id = event.response.id or ""
                    turn.response_model = event.response.model or ""
                elif kind == "response.output_text.delta":
                    turn.content += event.delta or ""
                elif kind == "response.reasoning_summary_text.delta":
                    turn.reasoning += event.delta or ""
                elif kind == "response.output_item.done":
                    item = _dump(event.item)
                    if item.get("type") == "reasoning":
                        reasoning.append(item)
                    elif item.get("type") == "function_call":
                        turn.streamed_calls[len(turn.streamed_calls)] = {
                            "id": item.get("call_id", ""),
                            "name": item.get("name", ""),
                            "arguments": item.get("arguments", ""),
                        }
                elif kind in ("response.completed", "response.incomplete"):
                    final = event.response
                elif kind in ("response.failed", "error"):
                    detail = getattr(
                        getattr(event, "response", None), "error", None
                    ) or getattr(event, "message", "")
                    raise IncompleteStream(
                        f"provider reported {kind}: {str(detail)[:300]}"
                    )
        finally:
            close = getattr(stream, "close", None) or getattr(stream, "aclose", None)
            if close is not None:
                try:
                    outcome = close()
                    if hasattr(outcome, "__await__"):
                        await outcome
                except Exception as exc:
                    turn.stream_close_error = f"{type(exc).__name__}: {exc}"
        if final is None:
            raise IncompleteStream(
                "provider stream ended without a final response; partial response retained"
            )
        turn.response_id = turn.response_id or str(getattr(final, "id", "") or "")
        turn.response_model = turn.response_model or str(
            getattr(final, "model", "") or ""
        )
        turn.usage = _usage(getattr(final, "usage", None))
        turn.tool_calls = [
            {
                "id": c["id"] or f"call_{i}",
                "type": "function",
                "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
            }
            for i, c in sorted(turn.streamed_calls.items())
        ]
        turn.reasoning_items = reasoning
        if getattr(final, "status", "") == "incomplete":
            reason = (
                getattr(getattr(final, "incomplete_details", None), "reason", "") or ""
            )
            turn.finish_reason = (
                "length" if reason == "max_output_tokens" else reason or "incomplete"
            )
        else:
            turn.finish_reason = "tool_calls" if turn.tool_calls else "stop"
        turn.latency_s = time.monotonic() - started

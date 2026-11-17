"""The same provider contract over the OpenAI Responses API, for models that need it (GPT-6 Luna).

On Chat Completions, Luna refuses function tools together with ``reasoning_effort`` and drops its reasoning after
every turn. Over ``/v1/responses`` it takes native tools while reasoning, and returns its reasoning as encrypted
items that can be sent back. Calls are stateless (``store=false``): Core keeps the history, as it does for GLM.

Continuity uses the slot GLM's reasoning already uses. ``Turn.assistant_message`` puts the encrypted reasoning
items in ``reasoning_content``, so the existing policies apply unchanged: the newest assistant turn's reasoning is
replayed in the next request and older turns' is dropped (``clm.request``, ``context``). The readable reasoning
summary goes to ``Turn.reasoning`` for the trace only.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from .provider import ChatProvider, IncompleteStream, Turn

INCLUDE = ["reasoning.encrypted_content"]


def tool_spec(spec: dict[str, Any], strict: bool | None = None) -> dict[str, Any]:
    """A Chat Completions tool definition in Responses form (the function fields move up one level).

    ``strict``: the value sent when the tool sets none. ``None`` sends nothing, and the provider's default applies:
    for Luna that default constrains every call to fill every field (16 Nov probe: an optional ``compare`` and
    ``region`` filled 4/4 with the field unset, 0/4 with ``strict: false``; live, 27/27 view_image calls). Codex
    sends ``strict: false`` on its function tools. A tool with ``aether_freeform`` goes out as a freeform grammar
    tool whose call text arrives as ``{"input": text}`` (apply_patch, study arm CX)."""
    fn = spec["function"]
    if spec.get("aether_freeform"):
        return {"type": "custom", "name": fn["name"], "description": fn.get("description", ""),
                "format": spec["aether_freeform"]}
    out = {"type": "function", "name": fn["name"], "parameters": fn["parameters"]}
    if fn.get("description"):
        out["description"] = fn["description"]
    if "strict" in fn:
        out["strict"] = fn["strict"]
    elif strict is not None:
        out["strict"] = strict
    return out


def _parts(content: Any) -> Any:
    if not isinstance(content, list):
        return content if content is not None else ""
    out = []
    for part in content:
        if part.get("type") == "image_url":
            image = {"type": "input_image", "image_url": part["image_url"]["url"]}
            if part["image_url"].get("detail"):
                image["detail"] = part["image_url"]["detail"]
            out.append(image)
        elif part.get("type") == "text":
            out.append({"type": "input_text", "text": part["text"]})
        else:
            raise ValueError(f"unsupported message part {part.get('type')!r}")
    return out


def _text(content: Any) -> str:
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if p.get("type") == "text")
    return content or ""


def input_items(messages: list[dict[str, Any]], freeform: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """Core's chat-shaped history as Responses input items, in order. Calls to a ``freeform`` tool go back as the
    custom tool call and output the provider produced."""
    items: list[dict[str, Any]] = []
    custom: set[str] = set()
    for msg in messages:
        role = msg.get("role")
        if role in ("system", "user", "developer"):
            items.append({"role": role, "content": _parts(msg.get("content"))})
        elif role == "assistant":
            content, calls = msg.get("content"), msg.get("tool_calls") or []
            # the provider's compaction item stands for everything before it (CLM sends nothing older)
            items.extend(msg.get("compaction") or [])
            replay = msg.get("reasoning_content")
            # encrypted items only (a text reasoning field cannot be replayed here); a reasoning item must be
            # followed by the output it produced, so a turn with neither text nor calls replays none
            if isinstance(replay, list) and (content or calls):
                items.extend(replay)
            if content:
                items.append({"role": "assistant", "content": _text(content)})
            for call in calls:
                fn = call["function"]
                if fn["name"] in freeform:
                    custom.add(call["id"])
                    text = json.loads(fn["arguments"] or "{}").get("input", "")
                    items.append({"type": "custom_tool_call", "call_id": call["id"], "name": fn["name"], "input": text})
                    continue
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
                    "type": "custom_tool_call_output" if msg["tool_call_id"] in custom else "function_call_output",
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
        self, client: Any, *, cache_key: str | None = None, chain: bool = False,
        native_compaction: int | None = None, tool_strict: bool | None = None, web_search: bool = False,
        web_search_max: int | None = None, **kwargs: Any
    ) -> None:
        super().__init__(client, **kwargs)
        self.tool_strict = tool_strict  # see tool_spec; None leaves the provider default
        # AETHER_CORE_WEB_SEARCH=on (default off): the provider's hosted web_search tool beside Core's own, as Codex
        # has it. G7 fin (17 Nov): Codex searched the regulation text 10-25 times in 5/5 runs, Core 0 in 5/5. The
        # provider runs the search inside the turn; its call items are not replayed (store=false), only what the
        # model wrote and its reasoning are.
        self.hosted_tools = [{"type": "web_search"}] if web_search else []
        # AETHER_CORE_WEB_SEARCH_MAX (default unset = no limit): stop offering the tool once this many searches ran in
        # the run. One turn may still overshoot it (G10c ran up to 18 in a turn); the spend guard bounds each call.
        if web_search_max is not None and web_search_max < 1:
            raise ValueError("web_search_max must be at least 1")
        self.web_search_max, self.web_searches = web_search_max, 0
        if native_compaction is not None and (chain or native_compaction < 1000):
            # the provider says never to prune a previous_response_id chain; Core prunes before the newest item
            raise ValueError("native compaction needs chain off and a threshold of at least 1000 tokens")
        # native_compaction: the provider compacts its rendered input past this many tokens and returns an opaque
        # compaction item; the next requests send that item and nothing older (E18 candidate K1).
        self.native_compaction = native_compaction
        # chain: stored responses, and a request that only extends the previous one sends the new items after
        # previous_response_id (the provider holds the rest). Any other request, or any failure, sends it all.
        self.chain, self._last = chain, None
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
        if self.native_compaction is not None:
            body = dict(params.get("extra_body") or {})
            body["context_management"] = [{"type": "compaction", "compact_threshold": self.native_compaction}]
            params["extra_body"] = body
        if effort:
            params["reasoning"] = {"effort": effort, "summary": "auto"}
        request: dict[str, Any] = {
            "model": self.model,
            "input": input_items(messages, frozenset(t["function"]["name"] for t in tools or () if t.get("aether_freeform"))),
            "max_output_tokens": max_tokens,
        }
        if tools is None:
            params.pop("tool_choice", None)
            params.pop("parallel_tool_calls", None)
        else:
            spent = self.web_search_max is not None and self.web_searches >= self.web_search_max
            request["tools"] = [tool_spec(t, self.tool_strict) for t in tools] + ([] if spent else self.hosted_tools)
        request["params"] = params
        return request

    async def _stream_once(self, request: dict[str, Any], turn: Turn) -> None:
        started = time.monotonic()
        args = {k: v for k, v in request.items() if k != "params"}
        params = dict(request["params"])
        full = args["input"]
        if self.chain:
            params["store"] = True
            args = {**args, **self._chained(full)}
            self._last = None  # restored only on success: a failed or retried call resends everything
        stream = await self._client.responses.create(**args, **params)
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
                    elif item.get("type") == "compaction" and self.native_compaction is not None:
                        encrypted = item.get("encrypted_content")
                        if not isinstance(encrypted, str) or not encrypted:
                            raise IncompleteStream("provider returned an unusable compaction item")
                        turn.compaction_items[:] = [item]
                    elif item.get("type") == "function_call":
                        turn.streamed_calls[len(turn.streamed_calls)] = {
                            "id": item.get("call_id", ""),
                            "name": item.get("name", ""),
                            "arguments": item.get("arguments", ""),
                        }
                    elif item.get("type") == "web_search_call":
                        turn.web_searches += 1
                        self.web_searches += 1
                    elif item.get("type") == "custom_tool_call":  # freeform tool: its text is the one argument
                        turn.streamed_calls[len(turn.streamed_calls)] = {
                            "id": item.get("call_id", ""),
                            "name": item.get("name", ""),
                            "arguments": json.dumps({"input": item.get("input", "")}),
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
        call_ids = [c["id"] for _, c in sorted(turn.streamed_calls.items())]
        if any(not call_id for call_id in call_ids):
            raise IncompleteStream("provider returned a function call without a call ID")
        if len(call_ids) != len(set(call_ids)):
            raise IncompleteStream("provider returned duplicate function call IDs")
        if any(not c["name"] for c in turn.streamed_calls.values()):
            raise IncompleteStream("provider returned a function call without a name")
        turn.tool_calls = [
            {
                "id": c["id"],
                "type": "function",
                "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
            }
            for _, c in sorted(turn.streamed_calls.items())
        ]
        turn.reasoning_items = reasoning
        if self.chain and turn.response_id:
            self._last = (full, turn.response_id)
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

    def _chained(self, full: list[dict[str, Any]]) -> dict[str, Any]:
        """The input to send: after the previous request's items and that turn's own output items (reasoning,
        text, calls, which the provider stored with the response), only what is new."""
        if self._last is None:
            return {}
        sent, response_id = self._last
        if len(full) <= len(sent) or full[: len(sent)] != sent:
            return {}
        rest = full[len(sent):]
        while rest and (rest[0].get("type") in ("reasoning", "function_call", "custom_tool_call")
                        or rest[0].get("role") == "assistant"):
            rest = rest[1:]
        if not rest:
            return {}
        return {"input": rest, "previous_response_id": response_id}

"""Strict tool schemas (``AETHER_CORE_STRICT_TOOLS=on``, off by default).

Every tool goes out with ``"strict": true`` and closed object schemas, so a server that constrains decoding to the
schema (Flint on SGLang: XGrammar) only produces calls whose argument names and types match it. Without it Flint's
server keeps the call format but not the schema (smoke 10-22: ``terminal`` called with ``command`` for ``input``).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .provider import ChatProvider


def strict(tools: list[dict]) -> list[dict]:
    out = deepcopy(tools)
    for tool in out:
        tool["function"]["strict"] = True
        _close(tool["function"].setdefault("parameters", {"type": "object"}))
    return out


def _close(schema: dict[str, Any]) -> None:
    if schema.get("type") == "object":
        schema.setdefault("properties", {})
        schema.setdefault("additionalProperties", False)
        for sub in schema["properties"].values():
            _close(sub)
    elif schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        _close(schema["items"])


class StrictChatProvider(ChatProvider):
    def _request(self, messages, tools, max_tokens, overrides):  # type: ignore[override]
        return super()._request(messages, None if tools is None else strict(tools), max_tokens, overrides)

"""Settings for self-hosted OpenAI-compatible servers: strict tool schemas (``AETHER_CORE_STRICT_TOOLS=on``, off by
default) and ``top_k`` (``AETHER_CORE_TOP_K``, unset by default).

Every tool goes out with ``"strict": true`` and closed object schemas, so a server that constrains decoding to the
schema (Flint on SGLang: XGrammar) only produces calls whose argument names and types match it. Without it Flint's
server keeps the call format but not the schema (smoke 10-22: ``terminal`` called with ``command`` for ``input``).
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

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


TOP_K_ENV = "AETHER_CORE_TOP_K"


def extra_sampling(environ: Mapping[str, str]) -> dict[str, Any]:
    """``top_k`` is outside the OpenAI request set, so it goes in ``extra_body``. Flint's kit recommends 20; P2 (10-22)
    ran without it. A value that is not a positive integer stops the run."""
    raw = environ.get(TOP_K_ENV, "").strip()
    if not raw:
        return {}
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(f"{TOP_K_ENV} must be a positive integer, got {raw!r}")
    return {"extra_body": {"top_k": int(raw)}}


PROXY_AUTH_ENV = "AETHER_CORE_PROXY_AUTH_FILE"


def proxy_headers(environ: Mapping[str, str]) -> dict[str, str]:
    """Modal proxy-auth headers for a Flint endpoint. The file named by ``AETHER_CORE_PROXY_AUTH_FILE`` holds two
    lines: the token id, then the token secret. Unset means no headers. Errors name the variable, never the contents."""
    raw = environ.get(PROXY_AUTH_ENV, "").strip()
    if not raw:
        return {}
    try:
        text = Path(raw).expanduser().read_text()
    except OSError as exc:
        raise ValueError(f"{PROXY_AUTH_ENV} names a file that cannot be read") from exc
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 2:
        raise ValueError(f"{PROXY_AUTH_ENV} file must hold exactly two non-empty lines: token id, then token secret")
    return {"Modal-Key": lines[0], "Modal-Secret": lines[1]}


class StrictChatProvider(ChatProvider):
    def _request(self, messages, tools, max_tokens, overrides):  # type: ignore[override]
        return super()._request(messages, None if tools is None else strict(tools), max_tokens, overrides)

"""Factual environment-provided extension configuration for Aether-Next.

Harbor owns which MCP servers a task declares. Aether normalizes only the
public transport facts needed to expose those servers through its execution
plane. No server-specific tool semantics or benchmark strategy live here.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


MCP_TRANSPORTS = frozenset({"sse", "streamable-http", "stdio"})


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        row = dump(mode="python", exclude_none=True)
        if isinstance(row, Mapping):
            return {str(k): v for k, v in row.items()}
    result: dict[str, Any] = {}
    for key in ("name", "transport", "url", "command", "args"):
        if hasattr(value, key):
            result[key] = getattr(value, key)
    return result


def normalize_mcp_servers(values: Iterable[Any] | None) -> tuple[dict[str, Any], ...]:
    """Normalize Harbor MCPServerConfig objects into immutable public facts."""
    rows: list[dict[str, Any]] = []
    names: set[str] = set()
    for value in values or ():
        source = _mapping(value)
        name = str(source.get("name") or "").strip()
        raw_transport = source.get("transport") or "sse"
        transport = str(getattr(raw_transport, "value", raw_transport)).strip().lower()
        if transport == "http":
            transport = "streamable-http"
        if not name:
            raise ValueError("MCP server name must be non-empty")
        if name in names:
            raise ValueError(f"duplicate MCP server name: {name}")
        if transport not in MCP_TRANSPORTS:
            raise ValueError(f"unsupported MCP transport for {name}: {transport}")
        row: dict[str, Any] = {"name": name, "transport": transport}
        if transport in {"sse", "streamable-http"}:
            url = str(source.get("url") or "").strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"MCP server {name} requires an http(s) URL")
            row["url"] = url
        else:
            command = str(source.get("command") or "").strip()
            if not command:
                raise ValueError(f"MCP stdio server {name} requires command")
            raw_args = source.get("args") or ()
            if not isinstance(raw_args, (list, tuple)):
                raise ValueError(f"MCP stdio server {name} args must be a list")
            row["command"] = command
            row["args"] = [str(item) for item in raw_args]
        rows.append(row)
        names.add(name)
    return tuple(rows)


def extension_probe_payload(mcp_servers: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [{str(k): v for k, v in row.items()} for row in mcp_servers]
    return {
        "schema_version": "environment_extensions.v1",
        "mcp_servers": rows,
        "mcp_server_count": len(rows),
        "authority": "harbor_task_declared_environment_extension",
    }


__all__ = ["MCP_TRANSPORTS", "normalize_mcp_servers", "extension_probe_payload"]

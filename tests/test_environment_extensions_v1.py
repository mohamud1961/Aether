from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether.environment_extensions import extension_probe_payload, normalize_mcp_servers


def test_normalize_harbor_model_and_mapping_mcp_servers_without_semantic_inference() -> None:
    rows = normalize_mcp_servers([
        SimpleNamespace(
            name="playwright",
            transport="sse",
            url="http://playwright-mcp:3080/sse",
            command=None,
            args=[],
        ),
        {
            "name": "local-tool",
            "transport": "stdio",
            "command": "python3",
            "args": ["server.py", "--stdio"],
        },
        {
            "name": "api",
            "transport": "http",
            "url": "http://api:8000/mcp",
        },
    ])
    assert rows == (
        {"name": "playwright", "transport": "sse", "url": "http://playwright-mcp:3080/sse"},
        {"name": "local-tool", "transport": "stdio", "command": "python3", "args": ["server.py", "--stdio"]},
        {"name": "api", "transport": "streamable-http", "url": "http://api:8000/mcp"},
    )
    probe = extension_probe_payload(rows)
    assert probe["mcp_server_count"] == 3
    assert probe["authority"] == "harbor_task_declared_environment_extension"
    assert probe["mcp_servers"] == list(rows)


def test_mcp_config_rejects_duplicate_names_and_invalid_transport_fields() -> None:
    with pytest.raises(ValueError, match="duplicate MCP server name"):
        normalize_mcp_servers([
            {"name": "x", "transport": "sse", "url": "http://x:1/sse"},
            {"name": "x", "transport": "streamable-http", "url": "http://x:1/mcp"},
        ])
    with pytest.raises(ValueError, match=r"http\(s\) URL"):
        normalize_mcp_servers([{"name": "x", "transport": "sse", "url": "file:///tmp/x"}])
    with pytest.raises(ValueError, match="requires command"):
        normalize_mcp_servers([{"name": "x", "transport": "stdio"}])


def test_mcp_custody_module_contains_no_playwright_or_frontier_strategy() -> None:
    from pathlib import Path
    source = (Path(__file__).parents[1] / "aether" / "environment_extensions.py").read_text(encoding="utf-8").lower()
    for forbidden in (
        "playwright",
        "medical-claims-processing",
        "frontier-bench",
        "browser_navigate",
    ):
        assert forbidden not in source


def test_mcp_transport_enum_values_normalize_by_value() -> None:
    from enum import Enum

    class Transport(Enum):
        SSE = "sse"
        HTTP = "streamable-http"

    rows = normalize_mcp_servers([
        SimpleNamespace(name="one", transport=Transport.SSE, url="http://one:1/sse"),
        SimpleNamespace(name="two", transport=Transport.HTTP, url="http://two:2/mcp"),
    ])
    assert rows[0]["transport"] == "sse"
    assert rows[1]["transport"] == "streamable-http"

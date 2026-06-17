# BigAI SDK: Tools & MCP Integration

**Source URL:** https://tongagents.mybigai.ac.cn/docs/Tong-Agent/sdk/documentation/tool/
**Translated on:** 2026-03-29

## Overview
In the BigAI ecosystem, Tools are the bridges connecting an Agent to the physical world and external data. They enable the agent to gather real-time information and perform actions within an environment.

## Tool 2.0 Architecture
Leveraging the `chuang_agent` core, BigAI 2.0 provides a unified `ToolManager` and `MCPClient`. While the underlying implementation is shared with the open-source core, the high-level API remains specialized for BigAI's workflow and enterprise requirements.

## Categories of Tools
### 1. Local Tools
Directly implemented Python functions or classes passed to the Agent during initialization.
### 2. Remote Tools (`ToolService`)
Tools hosted behind a remote API. Agents fetch and bind these tools using a unique identifier and a `ToolService` URI (e.g., `http://tool-server:8000`).
### 3. MCP Tools (Model Context Protocol)
Integration with the open MCP standard, allowing seamless connection to databases, file systems, and specialized third-party services.

## Defining and Registering Tools
### The `@tool` Annotation (Recommended)
The simplest way to transform a Python function into an agent-ready tool.
- **Automatic Schema Generation**: Framework generates tool descriptions from function signatures and docstrings.
- **Type Safety**: Supports Pydantic `BaseModel` and `dataclass` for automatic input validation and conversion.
- **Nested Types**: Handles complex nested structures (e.g., `dict[str, list[Query]]`).

### Class-based Declaration
For complex tools, developers can subclass the `Tool` base class, defining `name`, `description`, and `parameters` (standard JSON Schema) explicitly.

## MCP Integration Detail
The `MCPClient` manages the connection to MCP servers (either local scripts via `path/to/script.py` or remote services via SSE). 
- **`MCPToolManager`**: Aggregates tools provided by one or more MCP servers.
- **Error Handling**: Built-in support for `retry_attempts` and `timeout` configurations at the protocol level.

## Built-in Tools
- **Web Search**: Integration with search engines.
- **Python Interpreter**: Secure execution of generated code.
- **Weather & Geo**: AMap/High-Precision mapping integration.
- **Multimodal**: Image understanding and document extraction.

# BigAI SDK: Workflows

**Source URL:** https://tongagents.mybigai.ac.cn/docs/Tong-Agent/sdk/documentation/workflow/
**Translated on:** 2026-03-29

## Overview
While single agents are powerful, complex requirements often demand the composition of multiple logical units. BigAI's Workflow framework provides an orchestration engine to combine Nodes and Agents into sophisticated AI applications.

### Key Benefits
- **Out-of-the-box Nodes**: A library of pre-built functional units.
- **Flexible Extensions**: Support for custom Nodes and Agents.
- **Traceability**: Visual execution paths for easier debugging.

## WorkFlowEnv (2.0 Architecture)
WorkFlowEnv serves as an environment-level manager for workflow lifecycles, tool calls, and MCP (Model Context Protocol) dispatch. It leverages the underlying sandbox and workspace capabilities to provide enterprise-grade isolation.

## Orchestration Methods
There are three primary ways to define a workflow:
1. **Direct API (`add_node` / `add_edge`)**: Best for simple, programmatic creation.
2. **Decorator Strategy (`@node_declare`)**: Recommended for subclassing and reusable workflow logic.
3. **Configuration-based (JSON/YAML)**: Ideal for persistent, YAML/JSON-defined workflows that can be updated without code changes.

### Example: A Simple Search-Reasoning Pipeline
`START` -> `Web Search Node` -> `LLM Node` -> `END`

## Types of Nodes
A Workflow can include several types of objects as nodes:
- **Standard Functions**: Any Python function accepting/returning Events.
- **`NodeBase` Subclasses**: Specialized structural nodes.
- **Agents**: Autonomous planning agents treated as a single node.
- **Nested Workflows**: Sub-workflows embedded within a larger flow.

### Built-in Node Library
| Category | Node Type | Description |
| :--- | :--- | :--- |
| **Foundation** | `llm`, `input`, `output` | Core LLM, I/O nodes. |
| **Logic** | `if_else`, `intent_recognition` | Routing and conditional execution. |
| **Protocol** | `http` | External REST API interaction. |
| **Tools** | `tool` | Specialized tool invocation (Search, Python Code Interpreter, Map, etc.). |
| **Embodied** | `mm_info_extract`, `embody_command`| Multimodal extraction and hardware command execution. |

## Dynamic Flow Control
Workflows support advanced features like `Command` protocols for complex pipelines that exceed simple linear chains, and sophisticated intent recognition to branch the execution path based on user input.

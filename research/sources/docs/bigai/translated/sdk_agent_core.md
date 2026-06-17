# BigAI SDK: Agent Core Components

**Source URL:** https://tongagents.mybigai.ac.cn/docs/Tong-Agent/sdk/documentation/agent/
**Translated on:** 2026-03-29

## Introduction
The BigAI Agent is the primary interface for interacting with Large Language Models (LLM) and TongPL. While a single agent can solve many tasks, complex workflows benefit from multi-agent interaction.

### The Agent Container
An Agent is essentially a container for five core components:
1. **Prompt**: Developer-written instructions guiding agent behavior.
2. **Tools**: Mechanisms for interacting with the external world (e.g., weather, terminal commands).
3. **Model**: The reasoning engine (LLM or TongPL).
4. **Memory**: Storage for conversation context and state history.
5. **Knowledge Base**: Enhancement through RAG (Retrieval-Augmented Generation).

## Out-of-the-Box Agents
| Class Name | Description | Key Features |
| :--- | :--- | :--- |
| **ReactAgent** | Standard ReAct pattern agent. | Tool & Knowledge integration. |
| **TypedReactAgent**| ReAct agent with structural enforcement. | Pydantic model parsing (JSON output). |
| **TongLLMAgent** | Platform-aligned agent. | Configurable roles, prologues, and personas. |
| **PlanAgent** | Strategy-first agent using `Planner` protocol. | Autonomous planning and customizable logic. |
| **VoiceChatbot** | Multimodal voice-first agent. | Integrated ASR, LLM, and TTS services. |

## Execution Modes
Agents support several operational patterns:
- **`step`**: Synchronous single call; returns full execution result (e.g., JSON).
- **`stream`**: Single call with streaming response (iterator).
- **`run`**: Long-running session using message iterators; ideal for real-time audio/complex loops.
- **`astep` / `astream` / `arun`**: Asynchronous equivalents of the above.

## Advanced Configuration
- **`AgentSettings`**: A Pydantic-based configuration class allowing custom extra fields.
- **`TongLLMAgentSettings`**: Includes advanced fields like `prologue`, `voice_id`, `figure_id`, and `tool_id_list`.
- **`AgentRunContext`**: Stores runtime state. Default is `SimpleMemory`, but it can be overridden with specialized memory implementations.

## Extensibility & Customization
Developers can create custom agents in two ways:
1. **Inherit from `Agent`**: Implement `run`, `arun`, `step`, and `astep` manually. Highest flexibility but highest complexity.
2. **Inherit from `WorkflowAgent`**: Override specific "nodes" (e.g., replacing a standard LLM node with a custom reasoner). This is the recommended approach for complex enterprise applications.

## Reflection & Self-Correction
ReactAgent and its derivatives include a built-in reflection mechanism. If a tool call fails due to validation errors (e.g., Pydantic mismatch), the error is passed back to the model for a retry. The default retry limit is 1, but this can be adjusted per tool or per agent.

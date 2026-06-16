# Workflow Use Cases

This folder gives task-oriented entry points into the workflow layer.

## Use Cases

| Use case | Start here | What it proves |
|---|---|---|
| Eval-driven development | [eval-driven-development.md](eval-driven-development.md) | The agent does not implement before the check exists. |
| Runtime capability slice | [runtime-capability-slice.md](runtime-capability-slice.md) | Skills, MCP-style tools, hooks, permissions, and subagents are built as bounded Aether capabilities. |
| Multi-agent orchestration | [multi-agent-orchestration.md](multi-agent-orchestration.md) | Orchestrator, specialists, handoffs, review, and durable memory work as a loop. |
| Deep synthesis loop | [deep-synthesis-loop.md](deep-synthesis-loop.md) | Research, planning, contradiction handling, and synthesis become repeatable skills. |

## How To Pick

- If the reviewer asks how agents wrote most of the work, use
  [multi-agent-orchestration.md](multi-agent-orchestration.md).
- If the reviewer asks how agents were kept honest, use
  [eval-driven-development.md](eval-driven-development.md).
- If the reviewer asks for under-the-hood engineering, use
  [runtime-capability-slice.md](runtime-capability-slice.md).
- If the reviewer asks how messy evidence became strategy, use
  [deep-synthesis-loop.md](deep-synthesis-loop.md).

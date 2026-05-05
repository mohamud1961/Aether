# Patterns from Cutting-Edge Agents

_Update this as you analyze research. Each pattern should cite its source._

## Known patterns (seed)

### Forced reasoning via tool schema (KIRA)
KIRA's `execute_commands` tool requires `analysis` + `plan` fields before any commands. Forces chain-of-thought without a separate "planning phase."
- Source: github.com/krafton-ai/KIRA
- Result: 74.8% on TerminalBench 2.0

### Double-confirmation for completion (KIRA)
When agent calls `task_complete`, it receives a checklist and must confirm again. Prevents premature submission.
- Source: github.com/krafton-ai/KIRA

### program.md as the harness (Karpathy/autoresearch)
The entire agent "harness" is a markdown document. The human programs the program, not the code. The agent loop is: analyze → innovate → commit → execute → evaluate → loop.
- Source: github.com/karpathy/autoresearch

### AGENTS.md as a map, not manual (OpenAI/Codex)
~100 lines pointing to where knowledge lives. On-demand context fetching rather than upfront stuffing.
- Source: openai.com/index/harness-engineering/

### Capability-driven recovery (OpenAI/Codex)
On failure, ask "what capability is missing?" not "try harder."
- Source: openai.com/index/harness-engineering/

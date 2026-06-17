# Research Scan: Tool Calling Methods & Architectures

This document summarizes the current landscape of tool calling architectures and methodologies as identified in the `harnesseng` research corpus.

## 1. Schema-Enforced Reasoning
These methods use the tool definition itself to force specific cognitive behaviors.

### Forced Reasoning via Tool Schema (KIRA)
- **Concept**: Requiring mandatory `analysis` and `plan` fields within the tool's JSON arguments.
- **Mechanism**: The model cannot legally emit a tool call without first writing out its reasoning.
- **Benefit**: CoT behavior is enforced at the protocol level without separate planning turns.
- **Reference**: [krafton-ai/KIRA](https://github.com/krafton-ai/KIRA)

### Double-Confirmation for Completion
- **Concept**: A specialized `task_complete` tool that triggers a verification checklist rather than immediate exit.
- **Mechanism**: Human-in-the-loop or agent-self-check protocol.
- **Benefit**: Reduces premature exits on complex terminal tasks.
- **Reference**: [krafton-ai/KIRA](https://github.com/krafton-ai/KIRA)

---

## 2. Token-Level Structural Enforcement

These methods move beyond "prompting for JSON" and into runtime constraint engines.

### Structured Generation / Grammar-Enforced Invocation (XGrammar-2)

- **Concept**: A grammar engine that masks invalid tokens during the model's forward pass.
- **Key Primitives**:
    - **TagDispatch**: Efficiently switching between tool schemas mid-stream.
    - **Cross-Grammar Cache**: Reusing grammar states (e.g., standard JSON number formats) across different tools.
- **Benefit**: Zero-overhead enforcement of complex tool calls.
- **Reference**: [arXiv:2601.04426](https://arxiv.org/abs/2601.04426)

---

## 3. Dynamic Discovery & Fetching
Architectures designed to scale to hundreds of possible tools without overwhelming the context window.

### Tool Search & Runtime Deferral (OpenAI GPT-5.4+)

- **Concept**: Deferring full tool schemas until the model explicitly searches for or selects them.
- **Mechanism**: Metadata-only injection in the system prompt; schema fetching on-demand.
- **Benefit**: Massive context savings and cache preservation for tools the agent might never use.
- **Reference**: [OpenAI API Changelog (March 2026)](https://developers.openai.com/api/docs/changelog)

---

## 4. Multi-Step Execution Frameworks
Architectures that treat tool use as a guarded, iterative process.

### Try, Check and Retry (Divide-and-Conquer)
- **Concept**: A recursive framework for boosting tool-calling performance.
- **Mechanism**: Every tool execution is followed by a "Check" block. Failure triggers a "Retry" block with the error trace.
- **Reference**: [arXiv:2603.11495](https://arxiv.org/abs/2603.11495)

### Graph-Based Self-Healing Tool Routing
- **Concept**: Tools are mapped as nodes in a dependency graph.
- **Mechanism**: The agent selects "routes" through tools; the system can "heal" routes by suggesting alternative tool sequences on API failure.
- **Reference**: [arXiv:2603.01548](https://arxiv.org/abs/2603.01548)

---

## 5. Metadata-Driven Context Engineering
Architectures where the harness itself is an interactive document.

### Program-as-Harness (Karpathy/autoresearch)
- **Concept**: The entire state of the agent is a `program.md` file that the agent edits.
- **Loop**: `Analyze` \u2192 `Innovate` \u2192 `Commit` \u2192 `Execute` \u2192 `Evaluate`.
- **Reference**: [karpathy/autoresearch](https://github.com/karpathy/autoresearch)

### AGENTS.md / Capability-Driven Recovery
- **Concept**: Using a lightweight "map" file (`AGENTS.md`) to guide tool selection rather than long documentation.
- **Reference**: [OpenAI/Codex Early Research](https://openai.com/index/harness-engineering/)

---

## 6. Programmable & Scripted Tool Use
A shift from "JSON emission" to "Model-driven logic execution."

### Deterministic Lifecycle Hooks (Claude Code)
- **Concept**: Attaching logic to tool invocation events (pre/post/stop).
- **Stop Hooks**: A programmable gate that can deny a "task complete" call if verification (e.g., test suite) fails, forcing the model to continue with the error as its next instruction.
- **Handoff via stdout**: Programmable reinjection where hook output is explicitly added back to context.
- **Reference**: [Anthropic: Automate workflows with hooks](https://code.claude.com/docs/en/hooks-guide)

### Self-Coordinating Recursive Handoffs (Cursor)
- **Concept**: A hierarchy of Planners and Workers that communicate via structured "handoff notes."
- **Mechanism**: Planners spawn sub-planners for specific "slices"; workers return a single handoff containing findings, deviations, and feedback.
- **Benefit**: Linear scaling of throughput (up to 1,000 commits/hour) without global synchronization bottlenecks.
- **Reference**: [Cursor: Self-Driving Codebases](https://www.cursor.com/blog/self-driving-codebases)

---

## 7. Emerging Primitives
Recent industry "leaks" and newsletter synthesis (April 2026).

- **Monadic Context Engineering**: Treating context and tool state as a monad that can be chained and mapped reliably.
- **Proof-of-Perception**: Certified reasoning where every tool call produces a proof that it was based on specific environment data.
- **ToolRLA**: Reward decomposition at the tool level to train agents specifically on which tool usage led to success.

> [!TIP]
> **Key Trend**: We are moving away from "The model decides everything" toward "The system enforces the protocol," with tools like XGrammar-2 and OpenAI's Tool Search providing the necessary infrastructure.

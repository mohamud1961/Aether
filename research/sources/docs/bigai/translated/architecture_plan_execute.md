# Tong-Agent Architecture: Planner and Executor

**Source URL:** https://tongagents.mybigai.ac.cn/docs/Tong-Agent/features/agents/plan/ (and subpages)
**Translated on:** 2026-03-29

## The Plan-Examine-Execute Cycle
Tong-Agent implements a rigorous task-solving flow that decouples reasoning from action. This is achieved through three primary roles: **Planner**, **Examiner** (Optional/Implicit), and **Executor**.

### 1. Planner (Planning Node)
The Planner is responsible for high-level reasoning and strategy.
- **Input**: User goal and environment context.
- **Output**: A series of discrete, logical steps or a "Plan".
- **Capabilities**: Decomposes complex problems into manageable sub-tasks. It does NOT call tools directly but decides *which* tools should be deployed in subsequent steps.

### 2. Executor (Execution Node)
The Executor is the action-oriented component.
- **Input**: A specific step or instruction from the Planner.
- **Action**: Invokes the necessary tools (API calls, shell commands, database queries).
- **Output**: Observation data (stdout, response JSONs, file changes).

### 3. Verification & Loop
The system can optionally include a verification step where the Planner reviews the Executor's output against the original plan. If a step fails, the Planner can perform "Reflection" (Self-Correction) and re-plan the remaining steps.

## Multi-Agent Cooperation
Tong-Agent supports sophisticated multi-agent patterns:
- **Sequential Flow**: A linear chain of command.
- **Hierarchical (Manager-Worker)**: A manager agent delegates tasks to specialized sub-agents.
- **Joint-Action**: Multiple agents sharing a common workspace or environment to achieve a collective goal.

## Key Mechanistic Insights
- **Decoupled Reasoning**: By separating the Planner from the Executor, the system avoids "hallucinating" actions while still thinking, and vice-versa.
- **Traceability**: Every plan step and execution result is logged, allowing for detailed debugging of the "Chain of Thought".

# Stage 04: Implementation And Runtime

Purpose: build the smallest verified slice after the eval or contract surface is
clear.

This stage was used for:

- bounded implementation packets;
- runtime capability slices;
- hook, permission, tool, skill, and subagent surfaces;
- focused tests and smoke checks;
- worker handoffs back to the orchestrator.

Exit condition: the implementation has a verified diff, a clear ownership
boundary, and a handoff that names residual risk.

Subfolders:

- [skills](skills/) - implementation skills;
- [prompts](prompts/) - implementation support prompts;
- [artifacts](artifacts/) - verified diff and handoff evidence.

## Relevant Skills

- [Implementation Loop](../../skills/implementation-loop.md)
- [Bounded Implementation Slice](../../skills/bounded-implementation-slice.md)
- [Agentic TDD and Verification](../../skills/agentic-tdd-and-verification.md)
- [Context, Memory, and Token Economy](../../skills/context-memory-token-economy.md)
- [Handoff Writing](../../skills/handoff-writing.md)
- [Git Commit Slicing](../../skills/git-commit-slicing.md)


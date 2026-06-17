# Runtime Capability Slice

## Purpose

Use this workflow for under-the-hood harness work: skills, MCP-style tools,
hooks, permissions, subagents, traces, or runtime control surfaces.

## Why It Matters

This is the best public proof that the project is not only prompt work. It
shows owned runtime engineering: interfaces, contracts, evals, and reviewable
behavior.

## Slice Pattern

1. Name the runtime capability.
2. Define what is intentionally out of scope.
3. Add a deterministic smoke pack or focused regression check.
4. Implement the smallest Aether-native surface.
5. Validate target behavior and neighboring sentinels.
6. Document what shipped, what was deferred, and what evidence supports the
   claim.

## Public Capability Slices

| Capability | Runtime surface | Eval surface |
|---|---|---|
| Hooks | `../../harness/aether2/hooks/` | `../../eval_suite/families/environment/runtime_policy_hook_smoke/` |
| Permissions | `../../harness/aether2/tools/permissions.py` | `../../eval_suite/families/environment/runtime_policy_hook_smoke/` |
| MCP-style tools | `../../harness/aether2/tools/mcp.py` | `../../eval_suite/families/tooling/mcp_registry_contract_smoke/` |
| Skills | `../../harness/aether2/skills/` | `../../eval_suite/families/tooling/skill_loader_contract_smoke/` |
| Subagents | `../../harness/aether2/agents/` | `../../eval_suite/families/orchestration/subagent_handoff_contract_smoke/` |

## Reviewer Story

The story is simple: each runtime capability exists as code, has a public
contract, has a small eval surface, and names what it does not claim.

That is stronger than saying an agent "helped write code." It shows the system
that makes agents useful.

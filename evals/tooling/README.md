# Tooling

Tooling covers tool dispatch and the contracts behind it: tool names, argument shapes, receipts, registries and skill loaders.

The main lesson of the history: a guard that raised the target trials broke a sentinel trial, and a shape-only check passed wrong values. The first attribution tournament found that every failure was a tool-contract failure.

A tool call that uses a retired name or a draft value still returns a success-shaped receipt. Tool tasks check the values the contract sets, not whether the call looked right.

## Failure modes probed

- Using a retired tool alias, or a no-argument call that the contract forbids.
- Using values from a draft or superseded revision instead of the revision in force.
- Copying plausible values from old history rows without reading the contract.
- Receipts and summaries that disagree with each other or with the source.
- Discovery that depends on file order, or drops a broken schema or a skill collision.
- Edits to pristine contract or policy files so that a check passes.

## What the history taught

1. **A guard that fixes its target can still break a sentinel.** In the first pre-registered tournament (May 2026) a combined guard fixed both target tasks (2/2) and failed the sentinel (0/1). The same pattern repeated in the family diagnostic: tooling went from 4/7 to 7/7 with the guard while a sentinel regressed. Promotion now needs sentinels as large as the target set.
2. **A second view of the same rows is not a second result.** A contract classifier re-scored the tournament's 12 trials and added no evidence; it was retired as a duplicate.
3. **Early registry tasks only checked wiring.** The skill-loader and MCP-registry packs had references that copied the grader's answer. The current versions put the registry sources in the workspace, so the audit must be derived.

Every evaluation behind these lessons is listed in the [catalogue](../catalogue.md).

## Current tasks

Validation key: known-bad files, each rejected with its expected reason; careless controls, each rejected; reference solvable from the workspace. All rows pass the grader gate.

| Task | Failure mode | What makes it hard | Validation | Admission |
|---|---|---|---|---|
| `tool_call_composite` | Receipt and summary use the contract in force | Two-hop pointer; draft and superseded revisions; legacy alias in stale notes; old history rows; shape-only visible check | 7 known-bad; 5 careless; solvable | capability |
| `tool_schema_workspace_mix` | Selects the live workspace from an append-only snapshot | Latest event per ticket wins, by sequence, not file order; config indirection; legacy config and archive decoys; stale "fast path" cache note | 6 known-bad; 5 careless; solvable | capability |
| `mcp_registry_contract` | Discovery, schema mapping, invocation results, permission hook | Retired duplicate manifest; v0 schema; a broken schema enabled but not mapped; stale reason codes | 8 known-bad; 5 careless; solvable | capability |
| `skill_loader_contract` | Deterministic skill discovery and frontmatter | Name collision; content duplicate; malformed frontmatter; stale prior audit file | 8 known-bad; 5 careless; solvable | capability |

## Limits

The grader checks final files only. It cannot see whether a tool was invoked, in what order, or whether the visible check ran. A solver that writes both output files by hand passes `tool_call_composite`. Call-order requirements are not graded. The record holds no model result for these tasks, and two tooling ports were raised from smoke to capability at port time.

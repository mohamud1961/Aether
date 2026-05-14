# Aether Runtime Capability Migration Case Study

Status: public-safe case study

This page shows how HarnessEng turned the public `harness.aether2` namespace
into the canonical public surface, then used eval-first runtime capability
slices to add owned Aether features without exposing raw private archives,
hidden graders, or private-eval-sensitive material.

## Problem And Context

The repository needed a public story that was more concrete than "we moved
code around."

The engineering goal was to show real AI-native work in practice:

- a clean public namespace migration into `harness.aether2`;
- bounded Aether-native runtime capability slices instead of broad imitation;
- eval-first evidence gates before any broader claim;
- provenance handling that kept source-study material out of the product
  story;
- a reviewer-facing narrative that stays public-safe.

## Engineering Loop Used

The public loop was deliberately narrow:

1. classify the slice and separate environment issues from capability issues;
2. define a bounded slice with explicit exclusions;
3. add a synthetic smoke pack or regression sentinel before claiming success;
4. implement one small capability slice;
5. validate with unit tests, smoke packs, genericity checks, and adversarial
   review;
6. keep the slice only if the evidence stays clean, otherwise defer it.

That loop is the same pattern shown in the public eval packs and runtime
capability slices below.

## Public Namespace Migration Outcome

The namespace work closed the public migration story around `runner.aether2`
and `harness.aether2`:

- `harness.aether2` is the canonical public namespace;
- `runner.aether2` remains a compatibility layer for legacy imports;
- the legacy modules were reduced to alias-only shims or canonical imports;
- the closeout evidence is public-safe and test-backed, not trace-based.

Public evidence:

- `tracking/collab/public_repo_readiness/aether_namespace_closeout_handoff.md`
- `README.md`
- `docs/architecture/public-architecture.md`

## Bounded Runtime Capability Slices

The runtime capability work was intentionally split into small Aether-native
slices. Each slice kept the public surface visible and deferred UI/auth/provider
or remote runtime behavior that was not needed for the public story.

### Hooks And Permissions

Implemented the hook-first permission substrate so deny/allow behavior stayed
visible, permission decisions were structured, and denied actions did not
quietly mutate tool arguments.

Evidence:

- `harness/aether2/hooks/`
- `harness/aether2/tools/permissions.py`
- `eval_suite/families/environment/runtime_policy_hook_smoke/README.md`

### MCP Registry And Runtime

Implemented the registry/runtime boundary for MCP so typed outcomes,
deterministic discovery, and public-safe naming behavior were available without
a live network client or hidden transport.

Evidence:

- `harness/aether2/tools/mcp.py`
- `harness/aether2/tools/registry.py`
- `eval_suite/families/tooling/mcp_registry_contract_smoke/README.md`

### Skills Loader And Registry

Implemented deterministic skill loading, frontmatter parsing, collision
handling, and visible bounded context rendering so selected skill text appears
only in a recorded, auditable place.

Evidence:

- `harness/aether2/skills/`
- `eval_suite/families/tooling/skill_loader_contract_smoke/README.md`

### Subagent Loader, Task, And Handoff

Implemented the worker packet and handoff boundary so subagent work stays
explicit, bounded, and parent-visible instead of becoming silent background
work.

Evidence:

- `harness/aether2/agents/`
- `eval_suite/families/orchestration/subagent_handoff_contract_smoke/README.md`

## Eval-First Smoke Packs As Evidence Gates

The public eval substrate was built to show how the repo gates claims with
deterministic smoke packs before it talks about broader capability.

The first public-safe pack, `public_manifest_repair_smoke`, established the
pattern:

- synthetic workspace fixture;
- deterministic local grader;
- board and example scoreboard;
- no hidden eval internals;
- no model call required to prove the packaging shape.

That pattern was then reused by the runtime capability slices above.

Public evidence:

- `tracking/collab/public_repo_readiness/public_eval_pack_handoff.md`
- `eval_suite/families/filesystem/public_manifest_repair_smoke/README.md`
- `eval_suite/families/environment/runtime_policy_hook_smoke/README.md`
- `eval_suite/families/tooling/mcp_registry_contract_smoke/README.md`
- `eval_suite/families/tooling/skill_loader_contract_smoke/README.md`
- `eval_suite/families/orchestration/subagent_handoff_contract_smoke/README.md`

## Provenance Guardrail Result

The public story is careful about source-study boundaries:

- private source-study notes stay out of the reviewer-facing artifact set;
- public docs describe Aether-owned runtime interfaces, not external product
  clones;
- provenance policy blocks undisclosed source translation;
- the public case study describes implementation evidence, not affiliation or
  equivalence.

Public evidence:

- `docs/provenance/agent_runtime_adaptation_policy.md`
- `docs/provenance/third_party_notices.md`
- `docs/publication/publication_gap_list.md`

## Validation Summary

| Slice | Validation gate | Result | Reviewer takeaway |
| --- | --- | --- | --- |
| Public eval substrate | `public_manifest_repair_smoke` | `5 passed`; deterministic local grader and smoke runner | established the public eval-pack pattern before broader claims |
| Hooks + permissions | `runtime_policy_hook_smoke` | `80 passed`; `python3 tools/aether2_genericity_check.py` passed | hook ordering, visible denials, and no silent argument rewriting |
| MCP registry/runtime | `mcp_registry_contract_smoke` | `10 passed`; broader regression suite reached `250 passed` in the handoff | typed visible MCP outcomes and no native-tool regression |
| Skills loader/registry | `skill_loader_contract_smoke` | `11 passed`; broader regression suite reached `104 passed` in the handoff | deterministic skill loading and bounded visible context rendering |
| Subagent loader/handoff | `subagent_handoff_contract_smoke` | `43 passed`; bounded local/fake runtime only | explicit worker packets and handoffs without silent background execution |
| Namespace closeout | `aether_namespace_closeout_handoff` | broad baseline reached `239 passed` in the handoff | `runner.aether2` was reduced to compatibility-only behavior |
| Provenance guardrail | `third_party_notices` + `agent_runtime_adaptation_policy` | source-study material stays outside the reviewer path | provenance is explicit and conservative |

## What Remains Out Of Scope

- private raw trajectories, historian inbox files, or other raw private
  evidence;
- official evaluation fixtures, hidden grader logic, or copied evaluation rows;
- claims of production readiness, eval leadership, or universal agent
  reliability;
- claims that private worker threads or source-study material are publicly
  runnable;
- UI/auth/provider/remote-runtime surfaces that were intentionally deferred
  from the runtime capability slices.

## Public Evidence Links

- `README.md`
- `docs/README.md`
- `docs/case-studies/README.md`
- `workflows/loop-engineering.md`
- `workflows/ai-native-engineering-operating-system.md`
- `tracking/collab/public_repo_readiness/public_eval_pack_handoff.md`
- `tracking/collab/public_repo_readiness/aether_namespace_closeout_handoff.md`
- `harness/aether2/hooks/`
- `harness/aether2/tools/mcp.py`
- `harness/aether2/skills/`
- `harness/aether2/agents/`

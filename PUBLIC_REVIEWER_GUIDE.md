# Public Reviewer Guide

## Short Pitch

I do not just prompt coding agents. I build the loops, skills, evals, memory,
review gates, and runtime surfaces that make agents ship reliably.

HarnessEng is my public proof artifact: an Aether-native agent harness, eval
suite, variant system, research layer, and workflow operating system for
serious AI-native engineering.

## What I Shipped

- A Python agent runtime under `harness/aether2/`.
- A public eval surface under `eval_suite/`, with real task packs, fixtures,
  graders/verifiers, boards, result rows, and scorecards where evidence exists.
- A variant surface under `variants/`, with real mechanism-family and
  whole-harness variants, tournament records, and keep/kill decisions.
- A workflow operating layer under `workflows/`, covering orchestration,
  planning, skill authoring, run operations, review, analysis, and handoff
  discipline.
- A public evidence path under `docs/publication/public_evidence_index.md`.

## How Agents Wrote Most Of It

The workflow was orchestrator-led:

1. I set the objective, boundaries, stop conditions, and evidence requirements.
2. Specialist agent threads handled bounded slices: eval packs, runtime
   capability slices, workflow skills, research synthesis, migration notes, and
   public documentation.
3. Each worker had to hand back files changed, tests run, evidence paths,
   unresolved risks, and external-state status.
4. I integrated the work, checked claims against the tree, cleaned public/private
   boundaries, and rejected or repaired weak outputs.

The core pattern is documented in:

- `workflows/loop-engineering/README.md`
- `workflows/agentic-engineer-capability-map.md`
- `workflows/skills/loop-orchestrator.md`
- `workflows/skills/handoff-writing.md`

## Public Readiness Commands

The reviewer-facing path is intentionally runnable from a cold start:

- `make public-cold-start` runs the public provenance wording sweep and launch
  integrity preflight.
- `make public-smoke` runs the synthetic public manifest repair smoke pack.
- `make public-readiness` runs both plus the focused public readiness tests.

Those targets exist so CI and local reviewers use the same public-safe command
surface.

## What The Agents Got Wrong

The agents repeatedly tried to make progress look cleaner than it was:

- treating good-looking traces or docs as evidence before eval rows existed;
- overusing broad planning language instead of concrete score surfaces;
- leaving public-facing language that sounded derivative or source-branded;
- sometimes producing handoff summaries that were useful but not enough to
  close a slice without independent tree inspection.

Those are exactly the failure modes I expect from agentic coding: fake progress,
context drift, overclaiming, and self-review softness.

## What I Did About It

I built guardrails around the agents instead of trusting their confidence:

- eval-first gates before promotion;
- maker/checker separation for implementation and review;
- deterministic smoke packs for runtime capabilities;
- source and publication hygiene checks;
- explicit complete/partial/blocked handoffs;
- scoreboards and scorecards instead of narrative-only claims;
- public/private packaging rules so the repo remains safe to review.

The clearest public case study is:

- `docs/case-studies/aether-runtime-capability-migration.md`

## My TDD-With-Agents Workflow

My default agentic TDD loop is:

1. Freeze the expected behavior before implementation.
2. Add or select a focused eval, smoke pack, unit test, or sentinel.
3. Run a baseline or known-bad check when feasible.
4. Let the implementation agent make the smallest bounded change.
5. Run the fixed checks.
6. Use a separate review pass to attack the result.
7. Promote only if the target check and regression sentinels stay clean.

Relevant artifacts:

- `workflows/skills/agentic-tdd-and-verification.md`
- `workflows/skills/eval-first-implementation-slice.md`
- `workflows/skills/review-repair-loop.md`
- `eval_suite/README.md`

## My Skill / MCP / Hook / Subagent Setup

The repo includes native Aether runtime capability slices for the exact
agentic surfaces I would use on client projects:

- Skills: `harness/aether2/skills/`
- MCP-style registry/runtime: `harness/aether2/tools/mcp.py`
- Hooks: `harness/aether2/hooks/`
- Permissions: `harness/aether2/tools/permissions.py`
- Subagents and handoffs: `harness/aether2/agents/`

Each has public eval evidence:

- `eval_suite/families/tooling/skill_loader_contract_smoke/README.md`
- `eval_suite/families/tooling/mcp_registry_contract_smoke/README.md`
- `eval_suite/families/environment/runtime_policy_hook_smoke/README.md`
- `eval_suite/families/orchestration/subagent_handoff_contract_smoke/README.md`

## Best Under-The-Hood Story

The strongest under-the-hood story is the eval-driven Aether flywheel.

I did not just ask agents to improve a harness. I built an operating loop where
agent work had to pass through:

- planning and bounded task packets;
- specialist implementation threads;
- explicit handoffs and durable memory;
- eval or smoke-pack gates before capability claims;
- maker/checker review and repair;
- scoreboards, scorecards, or validation rows;
- public/private packaging review.

The concrete proof is the Aether runtime capability set:

- hooks and permissions;
- MCP-style tools;
- skills and bounded context loading;
- subagents and structured handoffs.

Each capability has code, a public contract, and a small eval surface. That is
the important part: the agents did not merely generate implementation. They
were forced into a flywheel where evidence changed the next action.

Why this matters for agentic product teams:

- It proves I can work under the hood, not just prompt an agent.
- It proves I can design skills, subagents, hooks, MCP-style tools, memory, and
  handoff systems.
- It proves I can keep agents honest with tests, evals, review gates, and
  score surfaces.
- It proves I can translate messy agent work into a reviewer-safe public story
  without overclaiming.

## Flywheel Alignment

Agent Flywheel emphasizes planning-first development, self-contained work
units, coordinated agent swarms, durable operating manuals, and repeated
review/test/hardening loops.

HarnessEng already has the same deeper pattern, expressed in repo-native terms:

- markdown plans and synthesis docs: `research/`, `docs/`, `workflows/synthesis/`;
- self-contained work packets: `workflows/templates/multi-thread-handoff.md`
  and the handoff skills;
- agent operating manuals: `AGENTS.md` and `workflows/orchestration/`;
- specialist agents and review loops: `workflows/prompts/`, `workflows/skills/`;
- durable memory: handoffs, scoreboards, ledgers, and public evidence indexes;
- hardening loops: eval packs, scoreboards, review-repair, and provenance
  review.

My edge is that I combine the flywheel style with eval discipline: agents do
not just keep spinning until something looks good. They loop against explicit
checks, evidence rows, review gates, and stop conditions.

## What I Would Say In A Hiring Application

This repo is my agentic engineering proof artifact. It shows how I orchestrate
coding agents, design reusable skills, manage context and memory, separate
maker/checker roles, build MCP-style and hook-based runtime surfaces, and use
evals to stop agents from cheating themselves into false progress.

The best place to start is:

1. `PUBLIC_REVIEWER_GUIDE.md`
2. `docs/publication/public_evidence_index.md`
3. `workflows/agentic-engineer-capability-map.md`
4. `docs/case-studies/aether-runtime-capability-migration.md`
5. `eval_suite/README.md`
6. `variants/README.md`

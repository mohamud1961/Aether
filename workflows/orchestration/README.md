# Orchestration

Goal handling, handoffs, review gates, and multi-agent coordination.

This folder contains the governance model for running multiple agents on a
single codebase without losing evidence, control, or scientific clarity.

## Contents

| File | What it contains |
|---|---|
| [governed-multi-agent-model.md](governed-multi-agent-model.md) | Role hierarchy, collaboration modes (single-agent, blind-parallel, role-sequenced, principal-led), stage-aware governance, historian separation |
| [principal-agent-workflow.md](principal-agent-workflow.md) | How the human owner engages the principal agent; how the principal routes specialist agents; step-by-step engagement protocol with explicit external-agent callouts |
| [synthesis-team-spec.md](synthesis-team-spec.md) | Per-artifact cell activation, specialist role specs, run order, and collaboration modes for the deep-synthesis team |
| [codex-goal-governance.md](codex-goal-governance.md) | Goal governance rules: objective declaration, handoff requirements, review gates (none/adversarial/codex-review), escape-hatch discipline, experiment discipline, eval-first rules |

## How these fit in the loop

The loop is `run → analyze → hypothesize → eval → implement → validate → promote/kill`.

Orchestration governs the **implement** and **validate** stages:

- `governed-multi-agent-model.md` defines who may act and how.
- `codex-goal-governance.md` defines what makes a Goal valid and how workers close it.
- `principal-agent-workflow.md` is the human-facing engagement protocol.
- `synthesis-team-spec.md` governs the **analyze** → **hypothesize** specialist team.

For the operator-facing skill that turns these rules into a repeatable workflow,
see [Loop orchestrator skill](../skills/loop-orchestrator.md).

For concrete evidence of this orchestration in action (32-worker build, escape-hatch
use, review-gate diagnosis), see [loop-engineering/](../loop-engineering/).

# Loop Orchestrator

Use this skill when a task needs a bounded agentic loop rather than a single
prompt or an ad hoc manual sequence.

The orchestrator's job is to turn a messy request into a controlled run with a
clear authority map, specialist thread packets, a short evidence chain, and a
truthful stop condition.

## Governing Question

> Who owns the task, which specialist threads should act, what evidence will
> count, and how do we know when the loop should stop or rerun?

## Core Mental Model

The orchestrator is the loop owner. It is responsible for the whole control
cycle:

`discover -> plan -> launch -> receive -> integrate -> review -> decide -> remember`

It does not need to perform every action itself. Its job is to decide which
specialist thread should act, what packet that thread owns, which subagents are
allowed under that specialist, what evidence must return, and when the loop
has enough signal to stop.

The orchestrator should be suspicious of two failure modes:

- under-orchestration: many agents act, but no one owns the integrated truth;
- over-looping: retries continue after they stop producing new evidence.

## Loop Shape

The public loop should be easy to explain:

1. orient the workspace and source surface;
2. write a brief with goal, boundary, evidence, and exit;
3. decide the control map: who acts, who reviews, what is blocked, and what
   must come back to the orchestrator;
4. launch specialist threads with bounded packets;
5. allow specialists to use subagents only under their packet scope;
6. receive handoffs and integrate them into one live project state;
7. verify against evidence, not just output shape;
8. review directly or dispatch a review thread;
9. re-dispatch fixes, reruns, or analysis packets until the decision is clear;
10. compact the state so the next turn inherits the right facts;
11. extract a reusable lesson only if the pattern repeats.

For experiment work, the inner cadence is:

`variant run -> analyze -> review -> propose improvement -> apply -> rerun -> decide`

For review-repair work, the inner cadence is:

`diff -> independent review -> accepted fixes -> focused validation -> finding disposition -> closeout`

For maintenance work, the inner cadence is:

`automation wakes -> triage -> packetize -> specialist work -> review -> memory update`

## What The Skill Owns

Keep these judgments in the skill itself:

- task framing and run-spec design;
- delegation choices, specialist thread shape, and stop conditions;
- source inventory and missing-context detection;
- review gates and completion semantics;
- handoff discipline and replayable notes;
- rerun decisions and keep/kill/iterate framing;
- when to stop because the run has become uninformative.

## Control Map Template

Before launching specialists, write the smallest useful control map.

```text
objective:
scope:
out_of_scope:
context_sources:
specialist_threads:
subagent_permissions:
review_gate:
memory_paths:
success_signal:
retry_cap:
stop_conditions:
handoff_required:
external_state_policy:
```

The map can change when evidence arrives, but success cannot be silently
lowered. Material scope changes become a blocked/partial closeout or a follow-
up goal, not hidden drift.

## Specialist Thread Map

Use specialist threads when separation improves evidence quality or throughput.

| Specialist | When to launch | Expected handoff |
|---|---|---|
| Analysis thread | A run, trace, failure, or artifact needs causal reconstruction | Validity verdict, failure class, evidence paths, next diagnostic |
| Eval design thread | A failure needs a proper test surface before implementation | Task contract, grader plan, baseline/ceiling/known-bad/sentinel plan |
| Implementation thread | The packet is bounded and contract-complete | Files changed, tests run, risks, next action |
| Review thread | A claim or diff could be disproved by an independent pass | Findings, accepted/rejected dispositions, required fixes |
| Publication/provenance thread | Public wording, source adaptation, or privacy boundary matters | Sanitized wording, withheld material list, open notice gaps |

Subagents can support a specialist with inventories, search, fixture comparison,
or matrix work. The specialist remains responsible for integrating subagent
outputs into one handoff.

## Launch Rules

- Launch a specialist only when the packet has a bounded output.
- Give every specialist an owner boundary and a handoff format.
- Allow subagents only under the specialist's packet, not as free-floating
  side channels.
- Prefer isolated branches or worktrees for parallel code edits.
- Cap retries before launch; do not discover the stop rule after the loop is
  already expensive.
- Record where memory will live before the first worker starts.

## What Belongs In Hooks

Move anything that must happen on every tool action into hooks:

- permission checks before side effects;
- pre-tool and post-tool audit events;
- denial of dangerous or out-of-policy actions;
- immutable argument capture and hook traces;
- external process or server lifecycle accounting.

Hooks are for enforcement and visibility. They should not carry the full
workflow logic.

## What Belongs In Automation

Move anything mechanical and repeatable into loop automation:

- tool dispatch;
- receipt capture;
- verification calls;
- compaction and state rebasing;
- completion bookkeeping;
- ledger-friendly trace emission;
- scheduled reruns or monitors for long-running loops;
- follow-up wakeups when an external dependency should be checked later;
- scoreboard or report refresh after new rows land.

Automation is the runner. It should execute the loop reliably, not decide what
the loop means.

## What Belongs In Memory

The loop needs memory outside the live context window:

- current objective and scope;
- packets launched and their owners;
- accepted facts and rejected claims;
- evidence paths and validation commands;
- review findings and dispositions;
- stopped/blocked reasons;
- next exact action.

Use files, ledgers, tickets, or continuation notes. The format matters less
than the rule: the next run must be able to continue without re-inventing what
already happened.

## Control Map

A good orchestrator makes these boundaries explicit:

- what the worker may decide independently;
- what must be escalated;
- what counts as blocked;
- what evidence is required before promotion or closure;
- which review gate applies to the slice;
- which external state must be reported back.

If the control map is missing, the loop usually drifts into either premature
completion or endless churn.

## Handoff Intake

The orchestrator should not accept a worker result until it can answer:

- Did the worker stay inside its packet?
- Which requirements are complete, partial, blocked, or invalid?
- What files changed, and who owns those boundaries?
- Which commands or evidence paths verify the claim?
- Did any subagent output matter to the conclusion?
- Does any process, server, credential home, or external state remain active?
- What is the next exact action: review, repair, rerun, promote, kill, or park?

After intake, the orchestrator integrates the result into the live plan and
decides whether to review directly or launch a review thread.

## Stop Rules

The orchestrator should stop or hand back when:

- the success signal is met and review is complete;
- the retry cap is reached;
- failures repeat without new evidence;
- the needed dependency is unavailable;
- the work would require a material scope change;
- the next decision needs human taste, product direction, or sensitive access;
- continuing would hide uncertainty rather than reduce it.

Valid stop states are complete, partial, blocked, invalid due to environment,
out of scope, parked, killed, or follow-up recommended. A truthful partial
handoff is better than an expensive loop that pretends to be autonomous.

## Handoff Discipline

Every meaningful worker result should include:

- final status;
- objective and scope actually completed;
- files changed;
- validation commands and evidence paths;
- review findings and dispositions;
- unresolved work, blockers, and the next action;
- whether any external process or server remains active.

Use the public handoff template for the compact form:

[Multi-thread orchestration handoff](../templates/multi-thread-handoff.md)

## Rule Of Split

- If it needs judgment and interpretation, keep it in the skill.
- If it must happen before or after every tool use, put it in a hook.
- If it is deterministic and repeated, automate it.
- If it needs independent skepticism, launch a review thread.
- If it needs narrow expertise, launch a specialist thread.
- If it needs taste, direction, or sensitive approval, keep a human in the
  loop.

## Repo Surfaces

- `harness/aether2/control/loop.py`
- `harness/aether2/hooks/`
- `harness/aether2/runtime/context.py`
- `harness/aether2/runtime/verify.py`
- `harness/aether2/runtime/compactor.py`
- `tracking/ledger/`

## Why It Matters

This repo already has loop mechanics, hooks, and a ledger. The missing piece
is the operator skill that explains how to use them together without
collapsing all three into one opaque prompt.

The strong version of the loop is a managed system: orchestrator, specialists,
subagents, review, hooks, automations, handoffs, and scored decisions all
working together.

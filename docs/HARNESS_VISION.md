# Harness Vision & Build Mandate

This is the governing intent for the agent harness. It outranks convenience,
cleverness, and any agent's idea of what "should" be added. Read it before
proposing or building anything in the harness. When a change conflicts with
this document, the change is wrong.

## The one test

> **The better the model, the better the system performs.**

The harness measures model capability. It does not supply it. Every line of
harness code must pass this litmus:

> **Would a smarter model make this code redundant, or want to override it?**
> If yes, it is a crutch — it does not belong in the harness.

Build the *workbench*. Never build the *crutch*.

## The four roles and their hard boundaries

**Architect** — designs the workbench for the specific task. Reads the task,
produces real, compiled harness config, and authors the **true system prompts**
for the solver and the verifier. Declares which tools, checks, and verifier
powers the task needs. The architect configures the specifics; the harness
supplies only generic, task-agnostic mechanism.

**Solver** — a simple execution agent. Receives the task prompt, the architect's
solver system prompt, and its tools. Inspects state, edits files, runs commands,
and decides when it believes the task is done. Nothing more. **Never sees or
interacts with the official grader.**

**Verifier** — an independent, read-only reviewer. Receives the task prompt, the
architect's verifier system prompt, the current workspace state, and its own
read-only verification tools. It **verifies the actual task state, not the
solver's story about it.** It inspects files and runs safe read-only checks
itself. If the task is done, it ends the run. If not, it returns clear,
actionable feedback. **Never sees or interacts with the official grader.**

**Official grader** — external. Part of the benchmark (e.g. Terminal-Bench),
**not part of our harness or agent.** It runs only after the agent has stopped,
purely for final measurement and post-run audit. It **never** influences the
agent loop, and it is never a concern of harness engineering. Do not confuse it
for a component we build or own.

The verifier verifies the task **state**, not the solver's **story**. The solver
hands off a *workspace*, never a *narrative the verifier must trust*.

## Two layers, two different rules (this resolves "no fallbacks")

The harness has two layers, and they are governed by opposite rules. Conflating
them is the single most common way this vision gets violated.

- **Substrate** (docker, filesystem, executor, workspace, process I/O) — must be
  **robust**. Ideally it never fails. A substrate failure is a real bug to fix
  *at the substrate*, not something to work around elsewhere. Making the floor
  solid is not a "fallback" — it is the floor. Aspiration: **the substrate never
  fails.**

- **Judgment / config** (architect config, verifier verdict, completion) — has
  **zero fallbacks**. No silent defaults, no hidden task-specific logic, no
  mechanism that compensates for a weak model. Aspiration: **the architect never
  fails to produce a valid, realizable config.**

The invariant that makes both aspirations safe when reality falls short:

> A substrate failure is **fixed** (at the substrate) and **reported honestly**
> (never counted as a capability failure). A judgment/config failure is
> **surfaced as blocked/flagged**, never silently absorbed by a default.

"Never fail" is the goal. "If it fails, it is surfaced, never hidden" is the
guarantee. A loudly-flagged failure is *not* a fallback — it is the honest
absence of one.

## What does not belong in the harness

- Task-specific hardcoded judgment logic (task-family analyzers, keyword gates,
  per-task proof rules). Generic mechanism only; the architect configures the
  task specifics.
- Any logic that compensates for a weak model, or that a stronger model would
  make redundant or want to override.
- Silent fallbacks in the judgment/config layer.
- Any path by which the official grader touches the agent loop.
- Harness-side completion veto theater — "done" is decided by the verifier
  against the architect's contract, plus at most a thin *generic* floor
  (e.g. the architect's own declared deliverables must exist). Not by
  task-specific harness cleverness.

## Governance — how to build only this, and nothing more

1. **Propose, never blind-build.** New mechanisms, new abstractions, and any
   change to the architecture require explicit approval first. You may always
   propose. You may never build the extra thing you think is needed without a
   yes.

2. **Map before you build.** Before touching code for any non-trivial change,
   answer, in writing:
   - What exists now?
   - What already matches this vision?
   - What violates it?
   - What is missing?
   - What should be removed or simplified?
   - What is the smallest next change that moves toward this exact architecture?

   The current-state map is a *precondition* for building, not an optional
   nicety. Work that skips it is rejected.

3. **Smallest delta.** Move toward the architecture in the smallest reversible
   steps. Removal and simplification are first-class changes, not lesser ones.

4. **Cite this document.** When proposing a harness change, state which part of
   this vision it serves, and confirm it passes the one test.

The goal is not a clever harness that compensates for models. The goal is a
clean, configurable harness where the architect configures the workbench, the
solver works, the verifier independently verifies the task state, and the
official grader stays completely external.

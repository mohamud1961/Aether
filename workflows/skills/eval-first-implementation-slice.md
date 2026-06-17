# Eval-First Implementation Slice

Use this skill before implementing a non-trivial harness or workflow change.

It is the public-safe version of the repo's eval-first discipline: define the
failure family, make the evaluation contract explicit, and keep the slice
small enough that the evidence can actually speak.

## Governing Question

> What exact behavior are we trying to change, and what evidence will tell us
> whether the change is real?

## When To Use

Use this skill when a change affects:

- tool calling or permissions;
- completion or blocker semantics;
- verification or grading;
- context, compaction, or memory;
- orchestration, handoffs, or worker routing;
- any mechanism that could change measured behavior.

## Before Coding

Write down the following before touching implementation:

- the failure family or capability gap;
- the target eval or diagnostic;
- the predicted behavior change;
- the baseline, ceiling, and known-bad cases;
- the regression sentinels;
- the evidence paths you expect to inspect;
- whether the slice is generic or suite-shaped.

If you cannot name the eval contract, do not start the code slice yet.

## What A Good Slice Looks Like

A good slice has one mechanism and one primary claim. It should not quietly
expand into a broad refactor.

Useful patterns:

- one contract repair;
- one visible failure mode;
- one deterministic smoke or board row;
- one round of focused validation;
- one keep, kill, or iterate decision.

Less useful patterns:

- broad cleanup with no target eval;
- several unrelated fixes bundled together;
- a "works on my machine" result with no score row;
- a change that only looks better because the verifier got stricter.

## During The Slice

- Preserve the exact evidence paths for tests, boards, and score rows.
- Record any simplifications or deferred behavior.
- Keep the implementation bounded to one mechanism.
- Treat negative results as data, not as a prompt to widen the scope.
- If the prediction fails, record the failed prediction instead of rewriting it
  after the fact.

## Exit Criteria

The slice is not done until:

- the target eval or diagnostic rerun is complete;
- the regression sentinels rerun is complete;
- the resulting row is recorded or linked;
- the keep/kill/iterate decision is written down;
- residual risks and blocked dependencies are explicit.

## Companion Template

Use [Eval-first implementation slice](../templates/eval-first-implementation-slice.md)
for the compact checklist form.

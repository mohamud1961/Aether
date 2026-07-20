# Aether-Next Patch Admission Policy

## Allowed kernel changes

A trusted-kernel patch is admitted only when it:

1. closes a versioned scorecard invariant;
2. fixes a generic trusted-boundary defect reproduced through production code;
3. adds a genuinely missing generic primitive without embedding task strategy;
4. removes a non-authoritative or duplicate production path; or
5. improves observability/provenance without changing task semantics.

## Insufficient reasons

The following do not independently justify a kernel patch:

- a Solver chose a weak algorithm;
- an Architect produced a poor workflow;
- a Verifier failed to use an available route;
- one benchmark task failed;
- one Gold scenario regressed;
- a prompt change appears likely to improve score;
- a task family would benefit from a special case.

These belong to model/configuration evaluation unless they expose a generic
trusted-invariant violation.

## Required patch packet

Every behavioural patch must state:

- scorecard invariant and failure mode;
- production owner and call path;
- minimum generic reproduction;
- at least two unrelated adversarial homologs for broad kernel rules;
- exact files and symbols changed;
- proof that no task-family semantics were added;
- positive tests;
- adversarial negative tests;
- production-path integration test;
- local result;
- VM result when required;
- source commit/tree/clean status;
- rollback boundary;
- closure verdict.

## Phase discipline

One commit should close one coherent invariant slice. Several coupled files may
change when they implement one invariant, but unrelated architecture changes
must not be bundled.

The next phase does not begin until the current phase has an explicit closure
record.

## Model-run restrictions during certification

Allowed:

- deterministic tests;
- archived provider fixture replay;
- production-path integration tests;
- at most a minimal bounded provider smoke where fixture-only proof is
  impossible.

Not allowed as patch drivers:

- Terminal-Bench boards;
- repeated Gold boards;
- broad model-performance optimisation;
- task-specific score chasing.

## Failure ownership

- poor Solver choice: Solver/model issue;
- weak semantic decomposition or workflow: Architect/config issue;
- unavailable generic primitive: capability issue;
- trusted invariant violation: kernel issue;
- external impossibility: environment issue;
- malformed/incomplete provider response: provider/protocol issue;
- Verifier inspection failure: Verifier tooling issue.

Ownership may transfer only through explicit current evidence.

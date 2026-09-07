# Three-month research programme

## Funding buys the decisive experiment

Aether already exists as a working runtime. The next phase is not "build an agent from scratch"; it is a bounded research programme to test whether the architecture earns its complexity.

The central question is:

> **Can better model → better agent become a dependable property of the system?**

## Experimental principle

The headline observations that motivated Aether are useful signals, but they are not enough for causal claims.

The funded comparison therefore freezes:

```text
SAME MODEL
SAME CHALLENGE
SAME COMPUTER / ENVIRONMENT
SAME TIME LIMIT
SAME EXTERNAL GRADER
```

and changes the agent/runtime treatment.

Where repeated trials are needed to distinguish architecture effects from run variance, repetitions will be fixed before the comparison rather than chosen after seeing the result.

## Month 1 — Harden

Goal: make Aether trustworthy enough that its own mechanics do not dominate the measurement.

### Work

- seal the current production surface;
- remove known Aether-side execution/review failure modes;
- harden provider canonicalisation and continuity;
- tighten workspace/capability boundaries;
- verify provider-free environment preflight;
- improve trace completeness and redaction;
- make task/environment/provider invalidity mechanically separable from model failure;
- run deterministic and live canary qualification without benchmark-specific repairs.

### Exit evidence

- reproducible clean installation;
- deterministic production suite passing;
- provider-free lifecycle smoke passing on the intended host class;
- stable model/tool profile hash;
- complete action/result trace on canaries;
- explicit known-limitations ledger;
- no unresolved generic runtime defect that would make the matched comparison uninterpretable.

## Month 2 — Compare

Goal: measure the effect of the runtime rather than the charisma of one trace.

### Primary comparison

For a fixed model and fixed challenge set, compare Aether with a deliberately simpler or established agent treatment under the same external conditions.

Measure at least:

- task completion / official reward;
- valid versus invalid rows;
- wall-clock time;
- model/provider latency;
- tokens and cost where available;
- action count;
- recovery events;
- parse/protocol failures;
- permission/boundary rejects;
- internal completion-review agreement with external grading;
- trace completeness.

### Attribution rules

A row is not silently converted into a model failure if the environment never started, the provider failed terminally, or official grading could not run.

Likewise, a run is not called a harness success simply because its trace looks coherent. The task-visible external grader remains the performance authority.

### No mid-board rescue

Once a controlled board begins:

- no task-specific patches;
- no model swap for a failing row;
- no hidden retries;
- no substitution of easier tasks;
- no changing time/resource limits;
- no tuning after seeing held-out outcomes.

If the system breaks, that break becomes evidence.

## Month 3 — Simplify + publish

Goal: finish with a smaller, better-understood system rather than a larger pile of mechanisms.

### Ablation questions

For each major mechanism, ask:

- Does it improve externally graded completion?
- Does it improve reliability/attribution without suppressing valid model work?
- Does it reduce cost or wasted action?
- Does it make failures more observable?
- Does it preserve the model-led ownership boundary?
- Is the benefit large enough to justify the complexity?

Mechanisms that do not earn their complexity should be removed or demoted from production.

### Public outputs

The programme should end with:

1. **A frozen architecture** — what Aether owns and what the model owns.
2. **Matched evaluation results** — including variance, invalid rows and negative results.
3. **Public evidence packets** — small redacted traces with provenance and hashes.
4. **Ablation results** — what was kept, changed or deleted and why.
5. **Safety/reliability findings** — permission, isolation, recovery, review and trace observations.
6. **Cost/efficiency accounting** — where provider telemetry allows it.
7. **A final research report** — methods, results, limitations and next questions.
8. **Runnable public code** — a cold-start path for the promoted runtime surface.

## Falsification criteria

The programme should be capable of telling us that Aether's thesis is wrong or overstated.

Evidence against the thesis would include:

- no repeatable improvement over a simpler runtime under matched conditions;
- benefits disappearing after controlling for model, time or compute;
- runtime complexity causing as many failures as it prevents;
- stronger models failing to translate into stronger agent performance;
- verifier/recovery machinery consistently suppressing valid model work;
- safety boundaries requiring so much intervention that the model is no longer meaningfully leading.

The correct response to those outcomes is not to add hidden strategy. It is to simplify the architecture and publish what failed.

## Why three months

Three months is long enough to harden the current runtime, run a controlled comparison and publish the result, while short enough to keep the proposal falsifiable and execution-focused.

The project does not need a long speculative build phase before producing evidence.

## What funding covers

The exact amount is funder-specific, but the categories are stable:

- dedicated researcher runway;
- frontier-model/API and inference costs;
- benchmark/evaluation compute;
- reproducible execution infrastructure;
- evidence packaging and publication;
- modest contingency for repeated controlled runs or provider failures.

A funder should be able to trace the budget directly to the experimental programme above.

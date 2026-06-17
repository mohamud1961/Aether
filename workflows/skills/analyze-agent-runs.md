# Analyze Agent Runs

This skill is the run-analysis practice for the loop's **analyze** stage. It
is a workflow skill, not a product feature. Its job is to make a run legible as
an engineering trace so we can tell the difference between real progress, lucky
passes, harness defects, and pure activity.

## Governing Question

> Did the harness make the model behave like a careful engineer, and where did
> the agentic loop fail to keep that contract?

Treat the run as a coupled system:

`model input → model decision → tool action → observed state → harness interpretation → next input → completion claim → verifier → grader`

Locate the first decisive divergence in that chain.

The answer should come from artifacts, not from the vibe of a long transcript.

## Required Reading

- Always read [references/evidence-and-causality.md](references/evidence-and-causality.md).
- Read [references/failure-taxonomy.md](references/failure-taxonomy.md) for failure classification and component mapping.
- Read [references/trace-workflow.md](references/trace-workflow.md) when raw traces, receipts, model exchanges, or per-step logs exist.
- Read [references/fix-design.md](references/fix-design.md) before proposing fixes or an implementation plan.
- Read [references/output-template.md](references/output-template.md) when producing a full run report.

Use `scripts/inventory_run.py` when a run directory has many nested artifacts.
Treat its output as an inventory aid, never as analysis.

## Non-Negotiable Rules

1. Inspect artifacts before concluding.
2. Separate direct observation, inference, hypothesis, and unknown.
3. Cite exact paths and event or step identifiers for material claims.
4. Do not mistake a downstream missing artifact for the upstream cause.
5. Do not mistake trace prose, verifier confidence, or a completion claim for grader truth.
6. Classify invalid provider, launch, environment, grader, timeout, and resource rows separately from model capability.
7. If decisive artifacts are missing, write `UNCLEAR` and name what is missing.
8. Do not propose task-specific solve packs, task-name branches, expected answers, fixed ports, or suite-specific vocabulary in generic harness code.
9. Public eval rows diagnose and audit. Custom homolog evals prove mechanisms.
10. Do not implement fixes unless the user explicitly asks.

## When To Use

Use this skill when you need to analyze:

- eval or run-board runs;
- terminal or coding agent trajectories;
- service, VM, or job lifecycle runs;
- verifier or grader disagreements;
- fake-progress or repeated-action patterns;
- trace bundles that need a causal summary before a fix is designed.

## What To Gather First

Before writing a conclusion, inventory the authority surface:

- result rows or scoreboard entries;
- runner revision and configuration;
- model route and effort settings;
- task contract and contamination status;
- verifier, grader, and repair outputs;
- raw tool observations and final artifacts;
- environment facts, job logs, and service state;
- any path or workspace translations that affect interpretation.

If a decisive artifact class is missing, say so explicitly and keep the
conclusion provisional.

## Core Method

Treat the run as a coupled chain:

`model input -> model decision -> tool action -> observed state -> harness interpretation -> next input -> completion claim -> verifier -> grader`

The job is to find the first decisive divergence in that chain, then explain
how later symptoms flowed from it.

## Evidence Standards

Use these labels consistently:

- `OBSERVED`: directly present in an artifact;
- `INFERRED`: best causal explanation from multiple observations;
- `HYPOTHESIS`: plausible but not proven;
- `UNCLEAR`: the evidence does not distinguish the alternatives.

Prefer this ranking:

1. immutable result rows and official grader output;
2. suite-native or container execution artifacts;
3. raw tool observations, file hashes or deltas, process state, and visible
   model exchanges;
4. replay receipts or verifier inspection;
5. trace prose and summaries.

Do not treat a completion claim, verifier confidence, or a polished summary as
task truth.

## Workflow

### 1. Freeze The Authority Surface

Record:

- run id and timestamp;
- task family and attempt count;
- runner and harness revision;
- model route and reasoning setting;
- scoreable denominator and invalid rows;
- whether the run is valid for capability conclusions.

Separate invalid provider, launch, environment, grader, timeout, and resource
rows from capability rows.

### 2. Build The Artifact Inventory

Collect the smallest set of artifacts that can still answer the question:

- scoreboards, rows, JSONL/CSV;
- official grader and visible verifier outputs;
- task instruction and system prompt;
- orientation/environment contract;
- completion contract, ledger, blockers, compaction handoff;
- model exchanges and observable reasoning/decision traces;
- tool calls and typed observations;
- file hashes/deltas and final artifacts;
- job/session/service records;
- runner/container/provider/resource evidence.

Record absent artifact classes. Missing evidence changes confidence.

### 3. Establish Overall Truth

Compute:

- pass/fail/invalid/timeout/launch/resource counts;
- scoreable denominator;
- verifier/grader confusion matrix;
- false-clean and false-blocked rows;
- provider/environment/grader invalid counts.

Never fold invalid rows into capability score.

### 4. Reconstruct Each Task in Execution Order

For each sufficiently evidenced task, reconstruct:

1. What the model saw.
2. What it believed the task contract was.
3. First meaningful action.
4. Evidence gained or uncertainty reduced.
5. Strategy changes after observations.
6. First decisive right or wrong turn.
7. Completion claim and declared checks.
8. Verifier interpretation and repair behavior.
9. Official grader result.

Do not summarize only tool names. Explain state transitions.

### 5. Classify Every Step

Use a single primary label for each notable step:

- `evidence_producing`
- `useful_setup`
- `redundant`
- `harmful`
- `premature_completion`
- `no_progress`

Ask whether the step changed semantic state or only activity state.

### 6. Find Fake Progress

Inspect the exact input immediately before fake work begins. Pay special
attention to these patterns:

- candidate lock-in;
- model-authored artifact treated as proof;
- same-method or circular self-check;
- shape or existence mistaken for semantics;
- proxy objective mistaken for full contract;
- partial samples generalized to complete behavior;
- process or port mistaken for service functionality;
- wrong-path artifact success;
- completion ritual pressure;
- blocked status routed through completion;
- repeated-action green hunting.

The key question is why the next action looked rational from the model-visible
state.

### 7. Analyze Passes

Classify each pass:

- `robust`
- `weakly_verified`
- `lucky`
- `overfit`
- `unclear`

A robust pass tests the requested behavior at the relevant boundary with
representative, independently grounded evidence and should generalize to
hidden variants.

### 8. Analyze Failures

Assign:

- first decisive wrong turn;
- primary failure class;
- contributing classes;
- whether the model knew it was failing;
- whether the harness surfaced that truth;
- whether verifier repair changed semantic state;
- missing evidence that would have exposed the failure earlier.

Separate genuine task difficulty from harness-created incentives.

### 9. Evaluate Harness Components

Assess:

- prompt/task wrapper;
- requirement extraction and dynamic model input;
- environment contract;
- tool schema/execution;
- evidence ledger and provenance;
- semantic no-progress detection;
- completion and blocked semantics;
- verifier prompt and evidence classifier;
- blocker persistence;
- compaction;
- service/job/session monitoring;
- runner/container/grader boundary;
- scheduling/resources/provider handling;
- trace instrumentation.

Report both helpful and harmful behavior.

### 10. Design A Generic Fix Only If It Is Proveable

If you propose a fix, make it generic:

- generic failure class;
- owning harness component;
- behavioral change;
- predicted impact;
- proving custom homolog eval;
- baseline, ceiling, and known-bad cases;
- regression sentinels;
- why it is not suite-specific leakage;
- keep/kill criterion.

The fix should be something a reviewer can test without suite-specific
memories.

### 11. Close Out The Run

Use the public checklist template when writing the final analysis note:

[Run analysis closeout checklist](../templates/run-analysis-closeout-checklist.md)

The closeout should include:

- executive conclusion;
- validity summary;
- representative deep dive;
- disagreement notes;
- fake-progress onset, if present;
- prioritized next eval or mechanism;
- missing-artifact appendix.

## Minimum Deliverable

Produce:

1. Executive conclusion.
2. Scoreboard and validity summary.
3. Task-level table.
4. Verifier/grader disagreements.
5. Deep dives into representative passes and highest-value failures.
6. Fake-progress onset analysis.
7. Cross-harness findings by component.
8. Root-cause map.
9. Prioritized generic fix/eval plan.
10. Missing-artifact and uncertainty appendix.

Keep the distinction explicit:

- traces diagnose;
- deterministic tests validate mechanisms;
- scored grader rows decide promotion.

## Why This Matters In HarnessEng

HarnessEng is intentionally skeptical of activity-shaped progress. A long run
can still be low-value if it:

- repeats actions without new evidence;
- treats self-authored artifacts as proof;
- declares completion from shape rather than semantics;
- moves failure from the model into the verifier or grader boundary.

This skill exists to keep those mistakes visible and reviewable.

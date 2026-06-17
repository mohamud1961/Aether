---
name: analyze-agent-runs
description: Analyze agentic harness, benchmark, terminal, coding, service, VM, or long-running task runs as engineering traces. Use when Codex must reconstruct model inputs and decisions, distinguish root causes from downstream symptoms, assess whether passes were earned or lucky, diagnose fake progress or repeated actions, evaluate verifier/grader agreement, inspect EnvContract and service monitoring, compare trajectories or harnesses, map failures to harness components, and propose generic eval-backed improvements without benchmark-specific leakage.
---

# Analyze Agent Runs

Analyze causality, not just outcomes.

## Governing Question

Answer:

> Did the harness make the model behave like a careful engineer, and where did the agentic loop fail to keep that contract?

Treat the run as a coupled system:

`model input -> model decision -> tool action -> observed state -> harness interpretation -> next input -> completion claim -> verifier -> grader`

Locate the first decisive divergence in that chain.

## Required Reading

- Always read [evidence-and-causality.md](references/evidence-and-causality.md).
- Read [failure-taxonomy.md](references/failure-taxonomy.md) for failure classification and component mapping.
- Read [trace-workflow.md](references/trace-workflow.md) when raw traces, receipts, model exchanges, or per-step logs exist.
- Read [fix-design.md](references/fix-design.md) before proposing fixes or an implementation plan.
- Read [output-template.md](references/output-template.md) when producing a full run report.

Use `scripts/inventory_run.py` when a run directory has many nested artifacts. Treat its output as an inventory aid, never as analysis.

## Non-Negotiable Rules

1. Inspect artifacts before concluding.
2. Separate direct observation, inference, hypothesis, and unknown.
3. Cite exact paths and event or step identifiers for material claims.
4. Do not mistake a downstream missing artifact for the upstream cause.
5. Do not mistake trace prose, verifier confidence, or a completion claim for grader truth.
6. Classify invalid provider, launch, environment, grader, timeout, and resource rows separately from model capability.
7. If decisive artifacts are missing, write `UNCLEAR` and name what is missing.
8. Do not propose task-specific solve packs, task-name branches, expected answers, fixed ports, hidden-test assumptions, or benchmark vocabulary in generic harness code.
9. Public benchmark rows diagnose and audit. Custom/private homolog evals prove mechanisms.
10. Do not implement fixes unless the user explicitly asks.

## Workflow

### 1. Freeze the Authority Surface

Identify:

- run id and timestamp;
- runner/harness revision and configuration;
- model route and reasoning effort;
- task set and attempt count;
- scoreboard/result rows;
- contamination status;
- scoreable rows;
- whether the run is valid enough for capability conclusions.

Prefer immutable result rows and grader outputs over summaries.

### 2. Build the Run Inventory

Find, where available:

- scoreboards, rows, JSONL/CSV;
- official grader and visible verifier outputs;
- task instruction and system prompt;
- orientation/EnvContract;
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
- provider/environment/grader invalid counts;
- service/VM and long-job outcomes.

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

Use exactly one primary label:

- `evidence_producing`
- `useful_setup`
- `redundant`
- `harmful`
- `premature_completion`
- `no_progress`

Ask:

- Did this advance a visible requirement?
- Did it reduce uncertainty?
- Was evidence independent of the construction method?
- Did the next step respond to the observation?
- Did semantic state change, or only activity state?

### 6. Locate Fake Progress

Inspect the exact input immediately before fake work begins.

Test these triggers:

- candidate lock-in;
- model-authored artifact treated as proof;
- same-method or circular self-check;
- shape/existence mistaken for semantics;
- proxy objective mistaken for full contract;
- partial samples generalized to complete behavior;
- self-authored client/server universe;
- process/port mistaken for service functionality;
- wrong-path artifact success;
- completion ritual pressure;
- blocked status routed through completion;
- repeated-action green hunting.

Identify why the next action looked rational from the model-visible state.

### 7. Analyze Passes

Classify each pass:

- `robust`
- `weakly_verified`
- `lucky`
- `overfit`
- `unclear`

A robust pass tests the requested behavior at the relevant boundary with representative, independently grounded evidence and should generalize to hidden variants.

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
- EnvContract;
- tool schema/execution;
- evidence ledger and provenance;
- semantic no-progress;
- completion and blocked semantics;
- verifier prompt and evidence classifier;
- blocker persistence;
- compaction;
- service/job/session/VM monitoring;
- runner/container/grader boundary;
- scheduling/resources/provider handling;
- trace instrumentation.

Report both helpful and harmful behavior.

### 10. Compare Other Harnesses Carefully

For trajectory comparisons:

- compare the same task pressure or homologous failure point;
- align at the first shared observation;
- compare next model input, next action, state delta, and verification boundary;
- infer mechanisms, not superiority from one anecdote;
- do not copy task-specific actions or architectures.

Prefer action/state/verifier diffs over prose diffs.

### 11. Design Generic Improvements

For every proposed fix provide:

- generic failure class;
- owning component;
- behavior change;
- proving custom homolog;
- regression sentinels;
- why it is not benchmark-specific leakage;
- downside/regression risk;
- predicted score, agreement, step, or invalid-rate impact;
- keep/kill criterion.

Require baseline, ceiling, known-bad, contamination, deterministic grading, and fresh end-to-end reruns before promotion.

### 12. Report Confidence and Falsifiers

For every major conclusion state:

- confidence: high, medium, or low;
- evidence;
- plausible alternative explanation;
- evidence that would falsify the conclusion.

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


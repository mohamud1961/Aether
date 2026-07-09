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
11. **A grader pass is not a harness success.** If the internal verifier never confirmed completion and the external grader scored the pass, the harness's own judge *failed* and was rescued post-hoc. Report it as a verifier miss, never as a win (see Step 0 and Step 3).
12. **A run with a dead substrate cannot grade judgment quality.** If model calls were largely rate-limited/errored, the verifier/architect/context questions are UNMEASURED for that run — say so; do not infer verifier strictness or prompt quality from a run where the verifier could not call the model.
13. **If you shipped a mechanism, this run may have falsified it.** Verify (by code hash) whether your own recent change was live, then check whether it did what it claimed. Record a failed prediction as failed; do not reinterpret it into a win.
14. **Distinguish "no feedback produced" from "feedback ignored."** Before analyzing how the solver used verifier feedback, confirm feedback verdicts actually existed. Rate-limited/errored verifier rounds produce no feedback to ignore.

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

### 0. Provenance + Substrate-Health Gate (do this FIRST, before any judgment analysis)

Two checks gate everything downstream. If either fails, most per-role conclusions are unsupportable and you must say so up front rather than grade on rescued grader passes.

**0a. Provenance — what code actually ran.** Read `run_provenance.code_tree_hash` and `model_params` from a result row. Compare the hash to the working tree (`run_pilot._tree_hash(<pkg>)`) and to the hashes of recent commits/changes. This tells you, factually, whether a specific mechanism (yours or a prior agent's) was live in this run. Never assume; hash it. Record model/effort and whether solver and verifier shared one deployment.

**0b. Substrate health — could the loop actually call the model.** Before believing any verifier/solver behavior, quantify model-call failures:

- Verifier: count round directories vs rounds that returned a verdict. In the aether_next layout, each `traces/verifier_evidence/*/step_*_solver_submit/` dir is one round; a `verifier_error.txt` means that round produced no verdict. Compute **% of verifier rounds that actually returned a verdict**. Below ~80%, the verifier is effectively non-functional and verifier-quality conclusions are UNMEASURED.
- Solver: `run_metrics.solver_parse_error_count`. If it approaches or exceeds the step count, sample the raw `model_parse_errors` — rate-limit/`ResponseError`/`background job … failed` errors surfacing as `solver_protocol_error` mean the solver was starved too, and the step count is inflated by failed retries, not work.
- Name the infra cause explicitly (e.g., N-way parallelism on one deployment exceeding TPM → 429 storm). This is a **substrate** failure per the vision: fix at the substrate, never count as capability.

If 0b shows a starved run, write the headline as a substrate-starvation finding and mark architect/verifier/context quality UNMEASURED. Then still complete Steps 3–4 for the rows that *did* get real verdicts.

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

**The alignment matrix is the headline, not the grader pass rate.** For each row cross `official_grader_status` with `verifier_alignment_status`:

- `aligned` + pass → real harness success (verifier confirmed what the grader confirmed).
- **`verifier_completion_miss` + pass → NOT a success.** Solver solved it, grader scored it, and the internal verifier never confirmed — the external grader rescued a run the harness could not close itself. Count these separately and loudly; a report that buries them inside a pass-rate is wrong (this is the single most common way a closeout overclaims).
- `verifier_false_clean` + fail → the verifier confirmed a wrong solution. Highest-value judgment failure; deep-dive every one.
- `aligned` + fail → genuine model-capability fail the verifier correctly caught.

Report "official pass rate" and "verifier-aligned rate" as two different numbers. The gap between them is how much the external grader is compensating for the internal judge.

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

### 5b. Step-Efficiency and Wasted-Step Accounting

When a run burned far more steps than `expected_steps`, quantify where they went instead of hand-waving "inefficient":

- **First-believed-done step**: earliest `step_*_solver_submit` round (solver first thought it was complete).
- **Wasted steps** = `final_step − first_submit_step`. Express as a % of the run.
- Attribute the waste to a cause with evidence: verifier-dead resubmit loop (verifier errored every round), verifier-disagreement loop (verifier returned needs_repair repeatedly — quote the findings), per-step model retries (parse-error count ≫ step count), or genuine solver thrash (`repeated_command_count`/`repeated_write_count`/`submit_without_new_evidence_count`). Usually one dominates; name it and show the number.
- Note which terminal bound fired and whether it was evadable: `solver_submit_stalemate` only fires on submits *without new evidence*, so a solver emitting any new action between submits slips it and runs to the step cap. A run that hit the raw cap or the wall-clock while a cheap bound existed is a bounding-logic finding.

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

## Appendix — Concrete extraction recipes (aether_next run layout)

A worker should not re-derive these each time. For a run dir `R` with per-task subdirs each holding `results.json` + `traces/`:

- **Ground-truth table (do not trust the closeout note):** load each `*/results.json` (may be a list; take `[0]`) and print `reward`, `reward_source`, `official_grader_status`, `grader_exit`, `grader_detail.{passed,failed}_count`, `kernel_status`, `internal_completion_status`, `verifier_alignment_status`, `step`, `classifier_label`. `reward_source=reward_txt`/`official_run_tests_exit_code` = grader-real; a reward sourced from the verifier is not a pass.
- **Provenance:** `results.json → run_provenance.code_tree_hash` and `model_params`; compare to `python3.11 -c "import sys;sys.path.insert(0,'<build>');from run_pilot import _tree_hash;from pathlib import Path;print(_tree_hash(Path('<pkg>')))"`.
- **Substrate health:** per task, `find R/<t>/traces/verifier_evidence -type d -name 'step_*_solver_submit' | wc -l` (rounds) vs `... -name 'verifier_error.txt' | wc -l` (dead rounds); grep the error files for `rate_limit`/`429`/`timed out`/`Permission denied`. Verdict rate = (rounds − errored)/rounds.
- **Repeats/efficiency:** `results.json → run_metrics` already carries `solver_parse_error_count`, `repeated_command_count`, `repeated_write_count`, `submit_without_new_evidence_count`, `first_valid_action_step`.
- **Real verifier verdicts:** the few rounds with `parsed_verifier_result.json` are the only ones that returned a verdict; read `verdict`, `summary`, `findings`, and (Phase-1+) `completion_evidence`. A `completed` with a valid `completion_evidence` record that the grader then failed is a false-clean that passed the content-blind gate — a decisive finding about the gate, not just the model.
- **Receipts:** `results.json → receipt_summary` counts by `kind` (`model_verifier_result`, `model_verifier_skipped`, `automatic_memory_advisory`, `no_progress_control`, `solver_parse_error`). Zero `automatic_memory_advisory`/`no_progress_control` during a long repeating run means the no-progress system was blind to the loop (likely a failure-loop it does not count).

Traces (`*.trace.json`) can be tens of MB; prefer `verifier_evidence/` round dirs and `run_metrics` over parsing full traces. Prompt-cache hit rate is currently not captured in any result field — if asked, report it as un-instrumented, not zero.

## Why This Matters In HarnessEng

HarnessEng is intentionally skeptical of activity-shaped progress. A long run
can still be low-value if it:

- repeats actions without new evidence;
- treats self-authored artifacts as proof;
- declares completion from shape rather than semantics;
- moves failure from the model into the verifier or grader boundary.

This skill exists to keep those mistakes visible and reviewable.

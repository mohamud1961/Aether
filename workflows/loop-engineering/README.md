# Loop Engineering

> `orchestrate -> delegate -> integrate -> review -> decide -> re-dispatch`
>
> inside that: `run -> analyze -> hypothesize -> eval -> implement -> validate -> promote/kill`

This is the headline methodology section. It explains how a task becomes a
repeatable agentic engineering loop: an orchestrator thread owns the goal,
specialist threads do bounded work, subagents support those specialists,
handoffs return evidence to the orchestrator, and review threads attack the
claim before the next iteration is promoted, killed, parked, or rerun.

Every stage of the loop has both a skill doc (how to run it) and a real
evidence artifact (proof it ran).

---

## The Loop in One Sentence

Build an orchestration system that can safely repeat. Every worker action either
produces structured evidence for the orchestrator or blocks promotion until it
does.

## What Makes This A Real Loop

A real loop has a heartbeat, a control surface, specialist execution, an
independent check, durable memory, and a stop rule.

| Building block | Purpose | Failure if missing |
|---|---|---|
| Trigger | Starts the loop from a schedule, event, goal, or explicit owner request | Work depends on a human remembering to prompt |
| Orchestrator | Owns scope, packets, evidence, review gates, and final decision | Parallel work becomes a swarm |
| Specialist threads | Do bounded work with the right skill and context | One context window becomes overloaded |
| Subagents | Provide narrow search, inventory, implementation, or checking support | Specialists waste cycles on low-level chores |
| Review thread | Separates maker from checker and tries to disprove completion | The loop grades its own homework |
| Memory | Stores decisions, handoffs, open risks, and next actions outside chat | Every cycle starts cold |
| Stop rule | Caps retries and decides complete, iterate, park, kill, or block | The loop burns tokens without adding evidence |

This is the core distinction: the loop is not "agent, try again." The loop is
an orchestration architecture that decides which agent should act next, what
they are allowed to change, what evidence they must return, and how the result
will be checked.

---

## Thread-Orchestration Model

Loop engineering is a thread topology, not a slogan.

1. The orchestrator gathers context, names the objective, freezes scope, and
   defines what evidence will count.
2. The orchestrator launches specialist threads with narrow packets: analysis,
   implementation, eval design, provenance review, docs packaging, or review.
3. Specialist threads can use their own subagents for bounded support work such
   as file inventory, focused search, fixture comparison, or matrix building.
4. Specialists hand results back with status, changed files, validation,
   evidence paths, risks, and external-state accounting.
5. The orchestrator integrates the handoffs and either reviews directly or
   dispatches a dedicated review thread.
6. Accepted review findings become repair packets; rejected findings need
   evidence; unresolved material findings become blocked or follow-up work.
7. The loop reruns against the target evals, sentinels, and scoreboards until
   the decision is clear.

This is the part that makes the loop powerful for variant work:

`variant run -> trace analysis -> review -> proposed improvement -> bounded patch -> rerun -> keep/kill/iterate`

Hooks and automations support the loop but do not replace orchestration:

- hooks enforce repeated policy such as permission checks, audit capture,
  unsafe-action denial, and external-state logging;
- automations handle repeatable mechanics such as scheduled reruns, monitors,
  smoke checks, receipt capture, scoreboard refresh, and follow-up wakeups;
- skills preserve expert behavior for each role so a specialist thread can run
  consistently without re-learning the process.

## Stacked Loops

HarnessEng treats loop engineering as stacked control loops:

1. **Agent loop**: a model uses tools until a bounded task is complete.
2. **Verification loop**: a checker, test, grader, or rubric evaluates output
   and feeds back repair instructions.
3. **Event loop**: automation or an external event starts the work without a
   human manually reopening every thread.
4. **Improvement loop**: run evidence changes the next mechanism, skill,
   prompt, tool, or guardrail.

The fourth layer is the compounding layer. It is where the system stops merely
doing work and starts improving how it does work.

The orchestrator is the owner of that outer layer. It decides whether evidence
supports another run, a patch, a review, a kill decision, or a blocked handoff.

## Closed Before Autonomous

The practical discipline is to start with closed loops.

Closed loop:

- the work surface is named;
- success can be checked;
- attempts are capped;
- state is written down;
- failures have a handoff path.

Open loop:

- the agent discovers the path;
- the goal is broader or fuzzier;
- success may require taste, strategy, or human judgment;
- the cost and drift risk are higher.

Most production-grade value comes from closed loops around objective feedback:
tests, eval rows, lint, schema checks, review scores, issue criteria, artifact
existence, link checks, or scoreboard deltas. Open loops are useful only after
the closed-loop checks are strong enough to catch drift.

## Orchestrator Control Map

Every serious loop begins with a control map:

```text
objective:
scope:
out_of_scope:
context_sources:
specialist_threads:
review_gate:
memory_paths:
success_signal:
retry_cap:
stop_conditions:
handoff_required:
```

The control map is how the loop keeps authority in one place while still
allowing parallel work. Specialists can be creative inside their packet, but
they cannot silently redefine the goal.

## Handoff As The Return Edge

The handoff is the return edge of the loop. Without it, delegation is only
parallel prompting.

A valid handoff lets the orchestrator answer:

- what changed;
- what passed;
- what failed;
- which requirements remain;
- what evidence supports the claim;
- what external state is still active;
- what the next exact action should be.

Worker final answers, files appearing in the tree, and idle threads are not
handoffs. The originating orchestrator must receive the result and reconcile it
against the live repo before the loop can advance.

## Review As The Quality Gate

The maker and checker should be separated whenever quality matters.

Review can be:

- direct orchestrator review for small or mechanical slices;
- a dedicated review thread for non-trivial diffs;
- adversarial review for strategy, eval design, evidence interpretation, or
  public claims;
- automated checks for deterministic signals;
- human review for taste, direction, sensitive actions, or high-impact
  acceptance.

The loop does not need infinite reviewers. It needs the right independent
check at the right point, with findings either accepted, fixed, rebutted with
evidence, or parked as follow-up.

## Cost And Comprehension Controls

Loops are leverage, not free energy.

Every extra cycle spends tokens and adds state the human owner may not have
read. The loop therefore needs explicit controls:

- attempt caps, usually two or three before handoff;
- narrow packets instead of giant diffs;
- context compaction into durable memory;
- periodic summaries of why the loop chose the next action;
- review before public or high-risk claims;
- stop states that are allowed to be partial or blocked.

The goal is not to remove the engineer. The goal is to move the engineer to
the highest-leverage point: designing the loop, choosing the evidence, and
deciding when the system's output is good enough to trust.

---

## The Loop Stages

### 1. Run

Dispatch a bounded agentic run through an orchestrator-owned control map. The
run may involve one worker or many specialist threads, but the orchestrator
keeps the evidence contract, stop conditions, and handoff requirements stable.

Skills and artifacts:
- Skill: [loop-orchestrator](../skills/loop-orchestrator.md) — how to set up
  the control map, dispatch workers, and know when to stop.
- Skill: [hooks-and-automations](../skills/hooks-and-automations.md) — how to
  decide what belongs in hooks, scheduled wakeups, recurring monitors, and
  durable memory.
- Skill: [run-vm-operations](../skills/run-vm-operations.md) — how to launch,
  monitor, collect, and tear down long-running local, container, and VM runs.
- Skill: [context-memory-token-economy](../skills/context-memory-token-economy.md)
  — how to decide what stays in live context, what becomes durable handoff
  memory, and what remains private.
- Artifact: [orchestration-ledger-case-study.md](orchestration-ledger-case-study.md)
  — a real 32-worker build with worker policy, escape-hatch use, and re-dispatch
  patterns. Demonstrates hour-0 contract discipline, disjoint write scopes, and
  prompt-debt tracking.
- Artifact: [hour-zero-contracts-example.md](hour-zero-contracts-example.md)
  — the pre-execution interface freeze that prevented integration drift across 32
  concurrent workers.

### 2. Analyze

Treat the run as an evidence bundle. Freeze the authority surface. Classify
failures by causal family before proposing any mechanism.

Skills and artifacts:
- Skill: [analyze-agent-runs](../skills/analyze-agent-runs.md) — the full
  12-step analysis workflow with per-step rules, fake-progress detection, and
  harness component evaluation.
- Skill: [deep-synthesis-loop](../skills/deep-synthesis-loop.md) — how to
  orchestrate multi-lane synthesis when one run analysis is not enough.
- Supporting references in `skills/references/`:
  - [evidence-and-causality.md](../skills/references/evidence-and-causality.md)
  - [failure-taxonomy.md](../skills/references/failure-taxonomy.md)
  - [trace-workflow.md](../skills/references/trace-workflow.md)
  - [output-template.md](../skills/references/output-template.md)
  - [fix-design.md](../skills/references/fix-design.md)
- Artifact: [run-analysis-case-study.md](run-analysis-case-study.md)
  — a real run analysis showing: evidence inventory, validity verdict, causal
  family construction (F1–F7), competing-hypothesis rejection, and why only one
  of seven families had actionable evidence despite a large run count.

### 3. Hypothesize

From the failure taxonomy, identify one target failure family. Name the
mechanism hypothesis. Write down what evidence would make the keep/kill
decision before any specialist starts implementation.

Skills and artifacts:
- Skill: [eval-first-implementation-slice](../skills/eval-first-implementation-slice.md)
  — the gate between hypothesis and implementation: define the eval contract
  before writing code.
- Skill: [agentic-tdd-and-verification](../skills/agentic-tdd-and-verification.md)
  — freeze the acceptance surface before implementation and block agent
  self-grading.
- Artifact: [orchestration-decision-log-example.md](orchestration-decision-log-example.md)
  — how orchestration decisions are recorded with explicit rationale and consequence,
  including the mid-build acceptance standard tightening (D-011) and prompt-debt
  attribution (D-012).

### 4. Eval

Build or select the eval that will prove the mechanism. A proper eval has:
- task contract and fixture;
- deterministic grader;
- baseline run, ceiling check, known-bad cases;
- contamination checks;
- regression sentinels.

Skills and artifacts:
- Skill: [eval-design-and-variant-governance](../skills/eval-design-and-variant-governance.md)
  — how to design an eval, govern a variant family, and make keep/kill decisions.
- Skill: [tournament-runner](../skills/tournament-runner.md) — how to compare
  candidates under one fixed score surface with invalid-run accounting.
- Schema: [schemas/variant-family-seed.md](../schemas/variant-family-seed.md)
  — the variant seed struct that anchors each experiment to its source failure
  family and its keep/kill criterion.

### 5. Implement

Execute the implementation as bounded worker slices with disjoint write scopes.
Each slice is contract-complete (not a thin placeholder). Workers hand off to
the orchestrator before the slice is considered closed; subagent notes are
supporting evidence, not substitutes for a specialist handoff.

Skills and artifacts:
- Skill: [implementation-loop](../skills/implementation-loop.md) — how to move
  from contract to verified diff through maker/checker repair cycles.
- Skill: [bounded-implementation-slice](../skills/bounded-implementation-slice.md)
  — the worker-facing complement to eval-first: how to receive a contract-complete
  packet, implement one bounded slice, and produce a handoff.
- Skill: [git-commit-slicing](../skills/git-commit-slicing.md)
  — how to turn completed slices into regular, intentional commits without
  mixed-change debt.
- Artifact: [orchestration-ledger-case-study.md](orchestration-ledger-case-study.md)
  — the 32-worker task table shows exactly how scopes were assigned, how
  spec-incomplete work was reclassified, and how re-dispatch was managed.

### 6. Validate

Run the target eval and regression sentinels. Review code changes through the
appropriate gate: orchestrator self-review for small slices, a dedicated review
thread for higher-risk work, adversarial-only review for strategy/eval claims,
or code-review closeout for code-bearing changes.

Skills and artifacts:
- Skill: [review-repair-loop](../skills/review-repair-loop.md) — how to turn
  review findings into accepted fixes, evidence rebuttals, or follow-up work.
- Skill: [code-review-closeout](../skills/code-review-closeout.md) — the
  4-level review gate taxonomy and closeout discipline.
- Skill: [adversarial-code-review-closeout](../skills/adversarial-code-review-closeout.md)
  — the manual fallback when the automated skill is unavailable.
- Template: [run-analysis-closeout-checklist](../templates/run-analysis-closeout-checklist.md)
  — the standard form for the analyze step output.
- Artifact: [handoff-example-pre-milestone.md](handoff-example-pre-milestone.md)
  — a real milestone handoff showing partial-complete status, finding-by-finding
  disposition, adversarial rebuttal, and blocked review gate accounting.

### 7. Promote or Kill

If the scored eval result is net-positive on target scores, sentinels,
contamination/invalid rates, and cost/step budget: promote. Otherwise: kill,
iterate, or park with evidence.

Skills and artifacts:
- Skill: [provenance-publication-review](../skills/provenance-publication-review.md)
  — the publication gate for public claims and promoted changes.
- Schema: [schemas/failure-card.md](../schemas/failure-card.md)
  — records each failure pattern with causal attribution, evidence paths, and
  recommended eval implications.

---

## What the Loop Is Not

- It is not a vibe check on a long transcript.
- It is not a promotion from traces alone (traces diagnose; evals prove).
- It is not a process where any one stage can be skipped.
- It is not one all-knowing agent doing everything in one context window.
- It is not a worker final answer that never returns to the orchestrator.
- It is not an unlimited retry machine.
- It is not an excuse for the human owner to stop understanding the work.
- It is not a guarantee of success — it is a discipline for making failures legible.

---

## Loop Taxonomy (public/private/future)

For the concise public taxonomy of what is claimed, what is internal, and what
is explicitly future, see [../loop-engineering.md](../loop-engineering.md).

---

## Files in This Directory

| File | Loop stage | What it shows |
|---|---|---|
| [orchestration-ledger-case-study.md](orchestration-ledger-case-study.md) | Run → Implement → Validate | 32-worker build: worker policy, escape hatches, re-dispatch |
| [hour-zero-contracts-example.md](hour-zero-contracts-example.md) | Run (pre-execution) | Interface freeze discipline before worker dispatch |
| [orchestration-decision-log-example.md](orchestration-decision-log-example.md) | Run → Implement (decisions) | Named decision taxonomy with rationale and consequence |
| [run-analysis-case-study.md](run-analysis-case-study.md) | Analyze | Evidence freeze, validity verdict, F1–F7 causal families |
| [handoff-example-pre-milestone.md](handoff-example-pre-milestone.md) | Validate → Promote | Milestone handoff: partial-complete, gate accounting, adversarial rebuttal |

---

## Governance

The loop runs under `workflows/orchestration/codex-goal-governance.md`.
Key constraints:

- No variant without a target eval, predicted delta, and named sentinels.
- No capability conclusion without a validity verdict first.
- Traces diagnose. Evals prove. Scoreboards decide.

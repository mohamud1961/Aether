# Bounded Implementation Slice

Use this skill when a worker receives a contract-complete task packet and must
implement one bounded slice, then produce a handoff.

This is the worker-facing complement to `eval-first-implementation-slice.md`.
Where the eval-first skill governs what gets implemented, this skill governs
*how* a worker executes a received contract and hands it back.

## Governing Question

> Can this slice be completed within the declared write scope, using the
> available evidence, without touching files outside the contract?

If the answer is no, the correct action is to return a partial handoff with
exact missing items — not to expand scope silently or to declare completion
falsely.

## When To Use

Use this skill when:

- you have received a contract-complete task packet with a defined write scope;
- you are implementing one bounded module, component, or slice;
- you need to produce a handoff that the orchestrator can act on.

Do not use this skill for:

- open-ended exploration tasks (use analyze-agent-runs or loop-orchestrator
  instead);
- tasks where the scope is still being negotiated (use task-briefing-and-planning
  first).

## What a Contract-Complete Packet Contains

Before starting implementation, confirm the packet includes:

- exact files you are allowed to create or edit;
- exact files you may inspect (harvest-only);
- explicit do-not-touch list;
- exact acceptance criteria;
- exact tests and checks;
- interface sketch or spec section;
- anti-contamination constraints (no hardcoded task knowledge in harness code);
- required handoff format;
- explicit instruction not to redesign architecture.

If any of these are missing, return the packet to the orchestrator with a clear
list of what is needed before work can begin.

## Workflow

### 1. Packet Reception

Read the full packet before touching any file. Confirm:

- the write scope is disjoint from other active workers;
- the harvest scope is clearly separated from the write scope;
- the acceptance criteria are falsifiable;
- the test commands are runnable in your environment.

If any of these cannot be confirmed, stop and report.

### 2. Contract Review

Before writing code, re-read:

- the spec section for the component (not just the packet summary);
- the interface contract (what producers and consumers expect);
- the cross-cutting constraints (genericity, evidence standards, no
  suite-specific code in harness paths).

Record any ambiguity as a known assumption, not as a silent decision.

### 3. Write-Scope Confirmation

Explicitly confirm which files you will create or edit, and which you will
only read. Record this in your handoff even if it matches the packet exactly.

If you discover during implementation that a file outside your write scope
needs to change, stop, record the finding, and surface it to the orchestrator.
Do not make the edit.

### 4. Implementation

Implement the full file-level contract for your slice. This means:

- every required public interface in the spec section;
- every required behavior, not just the path covered by the smallest test;
- every cross-cutting constraint (no hardcoded task names, genericity clean,
  boundary conditions represented);
- meaningful tests that cover the real contract, not only the green-path happy
  case.

If a required behavior cannot be completed inside the slice, mark it explicitly
in the handoff as `partial` with exact missing items. Do not silently omit it.

### 5. Local Test Run

Run every test command specified in the packet. Record:

- exact command;
- output (pass count, failure messages);
- whether the run was clean in your environment.

If a test fails due to an environment issue (not a code issue), record that
separately from a code failure.

### 6. Handoff Production

Produce a handoff using the multi-thread handoff template:

```text
final_status: complete | partial | blocked | invalid_due_to_environment
objective_completed: <what was actually completed>
scope_respected: yes | no (with explanation if no)
files_changed:
  - <file>: <what changed and why>
harvest_files_inspected:
  - <file>: <what was used from it>
tests_run:
  - command: <exact command>
    result: <pass count / failure message>
review_disposition: <tool name if used, or "manual self-review" with checklist>
accepted_findings:
  - <finding>: <how it was addressed>
rejected_findings:
  - <finding>: <why rejected with evidence>
missing_items:
  - <what was not completed and why>
blockers:
  - <what prevents next steps>
external_state:
  - <any process, container, or service still running>
next_action: <exact recommended next step for the orchestrator>
```

The handoff must be delivered back to the orchestrator, not only written to
the filesystem. A file on disk is not a delivered handoff.

## What "Partial" Means

A `partial` handoff is the correct status when:

- a required behavior is not implemented because the packet omitted part of
  the contract (orchestration prompt debt);
- a required behavior cannot be implemented in this slice due to a dependency
  on another worker's output;
- a test is failing due to an unresolved environment issue.

`partial` is not a failure. It is accurate accounting. The alternative —
marking a thin slice as `complete` — creates rework and misleads the
orchestrator.

## Guardrails

- Never expand write scope without returning it to the orchestrator first.
- Never mark a slice `complete` if a spec-required behavior is absent.
- Never treat a self-authored artifact (a generated file, a passing unit test
  on a mock) as proof that the real contract is satisfied.
- If the code review skill is available, use it. If it is blocked, record the
  blocker explicitly and use the manual review checklist as the fallback.

## Sources

- `workflows/orchestration/codex-goal-governance.md` — Goal governance rules
  (§Orchestrator Handoff Requirement, §Review Gates)
- `workflows/templates/multi-thread-handoff.md` — the handoff template
- `workflows/loop-engineering/orchestration-ledger-case-study.md` — the
  32-worker build: worker policy table, escape-hatch use, re-dispatch on
  spec-incomplete slices (the prompt-debt pattern documented in D-012)

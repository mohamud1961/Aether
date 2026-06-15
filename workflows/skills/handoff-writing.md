# Handoff Writing

Use this skill when you need to produce a handoff that a receiving orchestrator
or reviewer can act on without reopening the full task.

A handoff is the evidence that work is done (or exactly how far it got). It is
not a prose update. It is a structured record that the next actor can read and
trust.

## Governing Question

> Can the receiving orchestrator act on this handoff without reopening the full
> task?

If the answer is no, the handoff is not complete. Common failure modes:

- vague status ("mostly done", "good progress");
- missing evidence paths (the reviewer cannot verify claims independently);
- missing risk enumeration (the orchestrator cannot plan next steps);
- no next-action framing (the handoff lands but nobody knows what to do with it).

## When To Use

Use this skill when:

- completing a bounded worker slice (produce a worker handoff);
- closing a milestone or G-checkpoint (produce a milestone handoff);
- handing off from one thread to another in a multi-worker build;
- producing the final output of an agent session so the next session can resume.

## Workflow

### 1. Determine Status

Before writing, determine the honest status:

- `complete`: every exit criterion in the task packet is satisfied.
- `partial`: some exit criteria are satisfied; exact missing items are recorded.
- `blocked`: progress stopped due to a dependency, environment issue, or missing
  input. The blocker is named specifically.
- `invalid_due_to_environment`: the task could not be executed because the
  environment prevented it.

Do not use `complete` if any spec-required behavior is absent. A partial
handoff with exact missing items is more useful than a falsely complete handoff.

### 2. Scope Summary

Summarize what was actually completed. Be specific about:

- which files were created or modified;
- which files were inspected but not changed (harvest-only);
- which files were explicitly not touched (do-not-touch list respected);
- whether the write scope was respected.

### 3. Evidence Path Listing

List every evidence path the reviewer needs to verify claims:

- test command and output;
- review artifact path (if a code review was run);
- scoreboard or row path (if eval results exist);
- compilation or lint output;
- any external check that was run.

Do not describe what you did without citing where the evidence lives.

### 4. Risk Enumeration

List known risks, unresolved questions, and open concerns:

- spec items that were not reached;
- tests that pass locally but may behave differently in other environments;
- integration surfaces that have not been exercised end-to-end;
- known technical debt or deferred behavior.

A handoff without risks usually means risks were not looked for.

### 5. Next-Action Framing

State the next concrete action explicitly:

- what the orchestrator should do next;
- whether any process, container, VM, or external service is still running;
- whether a decision from the human owner is required before next steps;
- whether a follow-up Goal or task should be created.

### 6. Delivery Receipt

Record that the handoff was delivered to the orchestrator:

- how it was delivered (thread message, file path, etc.);
- whether a delivery confirmation was received.

A file on disk is not a delivered handoff. The originating orchestrator must
receive the handoff explicitly.

## Output Contract

Use the multi-thread handoff template for the compact form:

```text
WORKER_HANDOFF
- final_status: complete | partial | blocked | invalid_due_to_environment
- objective_completed: <exact scope that was completed>
- scope_respected: yes | no (explain if no)
- files_changed:
  - <file>: <what changed and why>
- harvest_files_inspected:
  - <file>: <what was used>
- tests_run:
  - command: <exact command>
    result: <pass count or failure message>
- review_disposition: <tool used, or "manual self-review" with checklist>
- accepted_findings:
  - <finding>: <how addressed>
- rejected_findings:
  - <finding>: <why rejected, with evidence>
- missing_items:
  - <item>: <why missing, what is needed>
- blockers:
  - <blocker>: <what prevents next steps>
- external_state:
  - <process/container/service still running>: <status>
- next_action: <exact recommended next step>
- delivery_receipt:
  - delivered_to: <orchestrator thread or role>
  - method: <how delivered>
  - confirmation: <received | not yet confirmed>
```

## Guardrails

- Never use `complete` when a required behavior is absent.
- Never omit evidence paths. Descriptions without citations cannot be verified.
- Never leave `external_state` blank. If nothing is running, say so explicitly.
- A handoff that only lives in the agent's final response — and is never delivered
  to the orchestrator — is not a handoff.

## Sources

- `workflows/orchestration/codex-goal-governance.md` — §Orchestrator Handoff
  Requirement (the full field list for what orchestrators must require)
- `workflows/templates/multi-thread-handoff.md` — the compact handoff template
- `workflows/loop-engineering/handoff-example-pre-milestone.md` — a real milestone
  handoff showing: partial-complete status, finding-by-finding disposition,
  adversarial rebuttal per finding, blocked review gate accounting, and
  explicit non-runs declaration

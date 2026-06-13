# Context, Memory, And Token Economy

## Governing Question

What should stay in the model context, what should become durable memory, and
what should be deliberately left out?

Long-running agentic work fails when every thread tries to carry the whole
project in working memory. This skill treats context as an engineered resource:
budgeted, tiered, compressed, and backed by filesystem evidence.

## Memory Tiers

| Tier | What belongs there | Examples |
|---|---|---|
| Live context | Current objective, active constraints, files being edited, latest failure | Goal text, current plan, relevant diffs |
| Durable handoff | Facts another agent must trust without replaying the whole thread | Worker handoff, validation commands, external-state status |
| Ledger input | Material research, implementation, experiment, or decision updates | `RAW_LEDGER_UPDATE` records |
| Public artifact | Sanitized, reviewer-facing proof | Workflow skill, case study, eval board, scoreboard |
| Archive/private | Raw traces, hidden graders, private paths, credentials, uncurated logs | Private collab folders and raw run material |

## Workflow

1. Define the active frame.
   - Objective.
   - Scope and out-of-scope.
   - Entry and exit criteria.
   - Review gate.
   - Stop conditions.

2. Build a context inventory.
   - Required files.
   - Current dirty-tree state.
   - Prior handoffs.
   - Relevant tests/evals.
   - Known blockers and external state.

3. Decide what the model needs now.
   - Keep direct source, exact commands, and current failures in context.
   - Summarize stable background.
   - Do not load raw private material unless the current task truly needs it.

4. Turn context into durable memory before delegation.
   - Give each worker a complete packet.
   - Include write ownership and stop conditions.
   - Require handoff fields that let the orchestrator integrate without
     rereading the full transcript.

5. Compact intentionally.
   - Preserve decisions, evidence paths, validation results, and unresolved
     risks.
   - Drop conversational noise.
   - Keep exact file paths and commands when they matter.

6. Spend tokens where uncertainty is highest.
   - Read source and tests before speculating.
   - Use targeted searches instead of broad dumps.
   - Use summaries only after primary evidence is inspected.

7. Close the memory loop.
   - Persist material outcomes through the ledger recorder.
   - Update public artifacts only with curated, non-private evidence.
   - Record what remains unknown rather than smoothing it over.

## Output Contract

For a substantial thread or goal, context management should produce:

- an active goal or task packet;
- a source/evidence inventory;
- a bounded plan;
- worker handoffs or a self-contained closeout;
- ledger update when material;
- explicit private/public boundary notes;
- statement of any process, VM, container, credential home, or server left
  running.

Template: [Context memory handoff checklist](../templates/context-memory-handoff-checklist.md).

## Guardrails

- Do not substitute memory for evidence.
- Do not let a compacted summary silently lower success criteria.
- Do not preserve raw private context in public docs.
- Do not spawn workers with partial packets and hope the missing contract is
  inferred.
- Do not keep a goal open only to wait for approval; close it as partial,
  blocked, or invalid when the approved scope cannot continue.

## Sources

Derived from the Goal governance contract, the orchestrator handoff rules, the
thread/ledger skill-mining report, and the repeated public-readiness handoff
pattern under `tracking/collab/public_repo_readiness/`.

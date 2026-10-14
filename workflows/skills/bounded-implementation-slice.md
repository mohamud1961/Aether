# Bounded implementation slice

Use this when a worker receives a contract-complete packet and must implement one bounded slice, then hand it back.

## Governing question

> Can this slice be completed inside the declared write scope, with the available evidence, without touching files outside the contract?

If not, return a partial handoff with exact missing items. Do not expand scope quietly, and do not declare completion falsely.

## Do not use for

- Open-ended exploration (use the run-analysis or loop-orchestrator skill).
- Scope still being negotiated (settle the brief first).

## A contract-complete packet contains

- exact files the worker may create or edit;
- exact files it may read but not change;
- an explicit do-not-touch list;
- falsifiable acceptance criteria;
- the exact test and check commands;
- an interface sketch or spec section;
- constraints (no task-specific knowledge in harness code, no redesign);
- the handoff format.

If any item is missing, send the packet back before starting.

## Workflow

1. **Receive.** Read the full packet. Confirm the write scope does not overlap other active workers, and that the criteria and commands are runnable here.
2. **Re-read the contract.** Read the spec section and the interface, not only the summary. Record any ambiguity as a stated assumption, not a silent decision.
3. **Confirm write scope.** List the files you will edit and the files you will only read. If a file outside scope must change, stop, record it, and surface it. Do not edit it.
4. **Implement the full slice.** Every required interface and behaviour, not only the path the smallest test covers. Tests must cover the real contract, including failure paths.
5. **Run the packet's commands.** Record the exact command and the result. Keep environment failures separate from code failures.
6. **Hand off.** Use the [multi-thread handoff template](../templates/multi-thread-handoff.md). The handoff must be delivered to the orchestrator, not only written to disk.

## What "partial" means

Partial is the correct status when a required behaviour is missing because the packet left it out, when it depends on another worker's output, or when an environment problem blocks a test. Partial is accurate accounting. Marking a thin slice complete creates rework and misleads the orchestrator.

## Guardrails

- Never widen write scope without returning to the orchestrator first.
- Never mark complete while a spec-required behaviour is absent.
- Never treat a self-written artifact, or a unit test on a mock, as proof the real contract holds.
- If a review skill is available, use it. If it is blocked, record the blocker and use the manual checklist.

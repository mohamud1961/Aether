# Invariant core and configurable surfaces

Every harness generation in this repository is split the same way: a fixed core that no
experiment may weaken, and a small set of surfaces an experiment may change.

## Invariant core

Rules that no variant, configuration or model may weaken or reconfigure:

- workspace and path safety
- tool truthfulness: a tool result reports what happened, never what was hoped
- audit logging of every model turn, tool call and result
- No Fake Work (see [no-fake-work.md](no-fake-work.md))
- executor boundaries: where commands run is fixed by the harness, not the model
- verification must happen before a run can end as done
- cleanup accounting for every process and file the run created
- the evidence ledger
- the baseline loop shape
- model-visible context hygiene: no benchmark, grader or hidden-test framing ever reaches the model

## Configurable surfaces

The task-facing knobs a variant may adapt:

- solver prompt (the task block)
- which context is included
- the exposed tool subset
- the completion contract (what "done" means for this task)
- the verifier's stated requirements and focus
- evidence guidance

## Variants

A variant adapts configurable surfaces around the invariant core for a given task. It never
modifies the core, never adds task-specific branches to the runner, and is always behind a flag
with the baseline path preserved. The model decides what the task needs; the harness decides how
to apply it safely, through one data-driven adapter from a declared contract to a validated run
configuration, not through control-flow branches.

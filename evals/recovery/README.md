# Recovery

Recovery covers what a harness does after a fault: a transport error, a restart after a partial write, or a background job that must be joined and cancelled cleanly.

Recovery was designed more than measured. Fault-injection and restart designs exist, but none has a model result in the record. The one restart diagnostic checks interpretation of authored records, so it tests the classifier, not the harness.

A harness that resumes from a partial state can double-write a batch, keep a torn line, or report a restart as success. These faults appear only when a fault is injected, so a clean run says nothing about them.

## Failure modes probed

- Retrying a fatal error, or retrying a write that is not idempotent.
- Accepting a truncated response as a complete result.
- Labelling a dropped response as a rate limit.
- Giving up on a rate limit that a retry would clear.
- Restarting a batch that duplicates committed rows or keeps a torn output line.
- Background jobs joined to the wrong result, or cancelled across process groups.

## What the history taught

1. **Recovery designs existed long before recovery tasks.** Fault-injection and restart packs were designed with known-bad clients, but recovery was not an evaluated target until the current tasks.
2. **Visibility alone does not rescue a deadline.** Showing the agent its remaining time did not save a task at the time cliff.
3. **Bundled arms cannot attribute.** A walltime-and-status calibration bundled two mechanisms with no control, so its 1/3 could not be attributed to either.

Every evaluation behind these lessons is listed in the catalogue.

## Current tasks

Validation key: known-bad files, each rejected with its expected reason; careless controls, each rejected; reference solvable from the workspace. All rows pass the grader gate.

| Task | Failure mode | What makes it hard | Validation | Admission |
|---|---|---|---|---|
| `transport_fault_recovery` | Classifying each operation under injected faults | Contract in docs; stale README retry policy; a PATCH rule the README gets wrong; truncated body with a value-like fragment; scripted transport | 7 known-bad; 5 careless; solvable | debug |
| `barrier_lifecycle` | Joining overlapping background jobs; cancelling by process group | Stale README suggests SIGTERM and "next finished" joins; a serial draft passes the visible check; grader kills leftover processes | 5 known-bad; 5 careless; solvable | debug |
| `resume_after_partial_failure` | Resuming a batch after a crash without duplicating rows | Journal partly right; torn output line; uncommitted rows from the failed batch; stale "complete" status note; older backup with 8 rows | 7 known-bad; 5 careless; solvable | capability |

## Limits

Two of the three tasks are debug-admitted, because their graders run candidate code in a child interpreter or launch real processes. They are for reference and control runs only, and are not capability evidence. The one capability task checks end state, so it cannot see whether a retry or a restart happened. The record has no fault-injection run through a live harness.

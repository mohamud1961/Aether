# Retrieval

Retrieval covers reducing many sources to the exact evidence IDs and values a task needs, and rejecting rows that are stale or belong to another batch.

The record holds little measured retrieval evidence. One retrieval sentinel was kept as a guard, one Terminal-Bench-derived task was held for lineage, and a third-party retrieval lane was excluded. The design lesson the current tasks carry: a row marked active can still be stale.

Retrieval mistakes look like answers. A value from a lagging mirror is a plausible number. Only the exact IDs and the final value show the error, so these tasks compare a structured result, not a summary.

## Failure modes probed

- Taking a value from a lagging mirror or an archive export instead of the current source.
- Trusting an active status over the revision order.
- Dropping the evidence IDs that support the final value.
- Leaving out the justification for rejected stale rows.
- Mixing in rows from another batch or another shard.
- Using a summary column or a stale total instead of the event record.

## What the history taught

1. **The hard part is rejecting stale evidence, not finding evidence.** The sentinel built for this target required exact evidence IDs and explicit rejection of superseded values.
2. **Lineage matters as much as design.** One retrieval task was built from a Terminal-Bench failure family and its grader read benchmark test files. It was retired and replaced by an original task.

Every evaluation behind these lessons is listed in the catalogue.

## Current tasks

Validation key: known-bad files, each rejected with its expected reason; careless controls, each rejected; reference solvable from the workspace. All rows pass the grader gate.

| Task | Failure mode | What makes it hard | Validation | Admission |
|---|---|---|---|---|
| `retrieval_reduction_closure` | Exact evidence IDs and final scalar from a sharded index | Index lists the shards for one batch; supersession by revision; lagging mirror; archive export; draft note with a stale total; row from another batch | 7 known-bad; 5 careless; solvable | capability |
| `structured_evidence_join` | Joining orders, shipments and corrections across two sources | Export column and event log disagree; `+02:00` promised times; a correction event overrides a shipped time; duplicate event across shards; cancelled order; out-of-date data dictionary | 6 known-bad; 5 careless; solvable | capability |

## Limits

Both tasks are shape-checked in the visible copy and graded on final state. Neither tests ranking, or retrieval over a large corpus. The target has two tasks, one of them new. The record holds no model result for these tasks, so coverage is narrow.

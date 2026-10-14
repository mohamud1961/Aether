# Context

Context covers whether state survives a long horizon: early values, rollbacks and later writes must still be right after a log or transcript has grown past the window.

The key lesson is that growth came from replay, not reasoning. A pre-held-out audit found that the full state snapshot was re-rendered and replayed each turn. By turn 16, 98.8% of the request was non-observed content. Removing dynamic context alone did not stop uncached input from growing.

A harness that loses one early value keeps running until that value decides the answer. A reconstruction task makes the lost value the answer, and checks the final state against the log.

## Failure modes probed

- Taking the final value from the newest log segment instead of replaying every change event.
- Ignoring a rollback that discards writes made after a checkpoint.
- Trusting a handoff note or dashboard export that lags the log.
- Treating the last few hundred lines of a log as the whole history.
- Reading rotated logs, including a gzip file, in name order instead of sequence order.
- Counting audit reads, rejected writes or dry-run sets as state changes.

## What the history taught

1. **Per-call savings can cost more per task.** Deduplicating context cut prefix bytes 29% and raised calls 56%; early compaction raised total tokens 58.8% and 105.1%.
2. **Replay, not reasoning, filled the window.** By turn 16, 98.8% of a 266 KB request was replayed content. A full snapshot was being re-rendered every turn.
3. **Full replay beat minimal context on whole tasks.** On a context-mode screen, full replay solved with 19 calls where latest-exchange needed 45. Full context was kept.
4. **Easy tasks cannot discriminate context strategies.** Every arm solved both screen tasks, so only efficiency could be compared. The current tasks force state to survive rollbacks, renames and long logs.

Every evaluation behind these lessons is listed in the catalogue.

## Current tasks

Validation key: known-bad files, each rejected with its expected reason; careless controls, each rejected; reference solvable from the workspace. All rows pass the grader gate.

| Task | Failure mode | What makes it hard | Validation | Admission |
|---|---|---|---|---|
| `state_reconstruction_long_log` | Final 40-key state and the keys changed since checkpoint C3, from a log of about 3,050 lines | Early seed sets sit in the oldest segment; name-sorted rotation misleads; a rollback to C3 discards later sets; a stale handoff note (28 keys) marked current; a lagging dashboard export; a runbook with the wrong rotation order; a worker log with `op=set` lines | 8 known-bad; 5 careless; solvable | capability |
| `long_handoff_composition` | Artifact identity across four dated handoff notes | Artifact renamed in note 2; note 3 is a deprecated publish flow with a legacy hash; archive decoy with the same ID and near-duplicate content; archived pass record for legacy bytes | 7 known-bad; 5 careless; solvable | capability |

## Limits

Two tasks cover long logs and multi-step handoffs. Neither measures compaction inside a live conversation; they test whether the agent reconstructs state from durable records. Graders check final state, not whether every record was read.

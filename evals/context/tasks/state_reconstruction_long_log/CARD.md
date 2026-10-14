# Task card: state reconstruction from a long operations log (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with any trace contract.

## Design (v2)

- Failure mode: losing early state over a long horizon, which is what context compaction drops. Early seed sets
  for all 40 keys sit in the oldest segment, and the segment with the most recent events sorts first by name.
- Log: about 3,050 lines across four rotated files (three plain, one gzip). Each line carries a global `seq`. Only
  `kind=cfg` lines change state. Rejected sets, dry-run sets and audit reads with `key=`/`value=` tokens are traps.
- Checkpoints C1 to C5. A rollback to C3 at seq 2100 discards the sets applied between C3 and the rollback. Sets
  after the rollback use a narrow working set of 12 keys, so the changed-since-C3 list is small.
- Decoys: a stale handoff note at seq 1200 (28 keys, marked "current"), a dashboard export lagging at seq 1900, a
  runbook with the wrong rotation order, and a worker log under `logs/` that contains `op=set` lines.
- Thresholds are enforced at generation time: the stale note, the lagging export and each replay shortcut must differ
  from the truth by a minimum number of keys, and the rollback must undo at least three keys.
- The visible check (`checks/shape_check.py`) checks shape only.

## Controls

- Known-bad: 8 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| final_state_value_mismatch | known_bad stale_summary_values, ignored_rollback, ignored_gzip, name_order_replay, dashboard_export_values; careless fake_it, skip_check |
| final_state_key_mismatch | known_bad last_600_lines |
| changed_since_c3_mismatch | known_bad c2_compare |
| input_file_modified | known_bad tampered_log_input; careless wrong_target |
| missing_final_state | careless do_nothing |
| missing_changed_since_c3 | careless half_done |
| invalid_*, missing_changed_since_c3 on the untouched workspace | guards only |

Trace-dependent process checks are not established by this final-state grader.
